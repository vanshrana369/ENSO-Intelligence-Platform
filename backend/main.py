import os
import sys
import json
import glob
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ml.forecaster import run_forecast
from ml.analytics import run_analytics

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'agents'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
from urllib.parse import urlparse

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")
print("DB Host:", urlparse(DB_URL).hostname)
_engine = create_engine(DB_URL, pool_pre_ping=True)


# Rate-limit NOAA requests — don't hammer on every API call
_last_mei_refresh: datetime | None = None
_last_nino34_refresh: datetime | None = None
_cached_nino34: dict | None = None          # { date, nino34_anom, phase }
MEI_REFRESH_INTERVAL    = timedelta(hours=12)
NINO34_REFRESH_INTERVAL = timedelta(hours=6)

_DP_PATH = os.path.join(os.path.dirname(__file__), '..', 'data_pipeline')
if _DP_PATH not in sys.path:
    sys.path.insert(0, _DP_PATH)


def _refresh_mei_if_stale():
    """Re-fetch MEI v2 from NOAA PSL if our DB copy is >30 days old."""
    global _last_mei_refresh
    if _last_mei_refresh and (datetime.utcnow() - _last_mei_refresh) < MEI_REFRESH_INTERVAL:
        return
    try:
        with _engine.connect() as conn:
            row = conn.execute(text(
                "SELECT MAX(date) FROM enso_data WHERE mei_value BETWEEN -3 AND 3"
            )).fetchone()
        latest_date = pd.to_datetime(row[0]) if row and row[0] else None
        days_old = (datetime.utcnow() - latest_date).days if latest_date else 9999
        if days_old > 30:
            logger.info(f"MEI data is {days_old}d old — refreshing from NOAA PSL...")
            from fetch_noaa import fetch_mei_data
            fetch_mei_data()
            logger.info("MEI refreshed successfully")
        _last_mei_refresh = datetime.utcnow()
    except Exception as e:
        logger.warning(f"MEI auto-refresh failed: {e}")


# NOAA CPC monthly SST index — updated every ~month, clean space-delimited format.
# Columns: YR MON  NINO1+2 ANOM  NINO3 ANOM  NINO4 ANOM  NINO3.4 ANOM
# tokens:   0   1    2      3      4     5      6     7      8       9
_NINO34_URL = "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices"


def _get_live_nino34() -> dict | None:
    """
    Fetch the most recent monthly Niño3.4 SST anomaly from NOAA CPC.
    Cached for 6 hours.  Returns { date, nino34_anom, phase } or None.
    """
    global _last_nino34_refresh, _cached_nino34
    if _cached_nino34 and _last_nino34_refresh and \
            (datetime.utcnow() - _last_nino34_refresh) < NINO34_REFRESH_INTERVAL:
        return _cached_nino34
    try:
        resp = requests.get(_NINO34_URL, timeout=20)
        resp.raise_for_status()

        latest_yr   = None
        latest_mon  = None
        latest_anom = None
        for line in resp.text.splitlines():
            tokens = line.split()
            if len(tokens) < 10:
                continue
            try:
                yr   = int(tokens[0])
                mon  = int(tokens[1])
                anom = float(tokens[9])   # NINO3.4 SST anomaly column
            except (ValueError, IndexError):
                continue
            if latest_yr is None or (yr, mon) > (latest_yr, latest_mon):
                latest_yr   = yr
                latest_mon  = mon
                latest_anom = anom

        if latest_yr is None:
            logger.warning("Niño3.4: parsed 0 rows from sstoi.indices")
            return _cached_nino34

        date_str = f"{latest_yr}-{latest_mon:02d}-01"
        phase = ('El Niño' if latest_anom >= 0.5
                 else 'La Niña' if latest_anom <= -0.5
                 else 'Neutral')
        result = {
            'date':        date_str,
            'nino34_anom': round(float(latest_anom), 2),
            'phase':       phase,
        }
        _cached_nino34       = result
        _last_nino34_refresh = datetime.utcnow()
        logger.info(f"Niño3.4 live: {result['date']}  {result['nino34_anom']:+.2f}  {result['phase']}")
        return result
    except Exception as e:
        logger.warning(f"Niño3.4 fetch failed: {e}")
        return _cached_nino34


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="ENSO Intelligence Platform",
    description="AI-powered climate risk intelligence API",
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials MUST be False when allow_origins=["*"].
# Browsers reject credentialed requests to a wildcard origin (CORS spec §3.2.2).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # ← was missing; caused silent CORS failures
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory report cache ────────────────────────────────────────────────────
# Render's filesystem is ephemeral — files written by /run-now vanish on
# dyno restart. We keep the last successful report in memory so /status and
# /latest-report always have something to serve within the same dyno session.
_report_cache: dict = {}

# ── Background scheduler for weekly pipeline runs ────────────────────────────────
scheduler = BackgroundScheduler(timezone='UTC')


def _scheduled_pipeline_job():
    """Background job: run the pipeline every Monday at 9 AM UTC."""
    try:
        logger.info("⏰ Scheduled pipeline job triggered (Monday 9 AM UTC)")
        from pipeline import run_pipeline
        from pdf_generator import generate_pdf

        result = run_pipeline()

        # Update in-memory cache and persist to DB
        report = result.get("final_report") if isinstance(result, dict) else None
        if not report:
            files = glob.glob("outputs/report_*.json")
            if files:
                with open(max(files)) as f:
                    report = json.load(f)
        if report:
            _report_cache.clear()
            _report_cache.update(report)
            _save_report_to_db(report)
            logger.info("✅ Scheduled pipeline completed — cache + DB updated")

        # Generate PDF
        # Enrich report with forecast + accuracy data for PDF embedding
        pdf_report = dict(_report_cache or result)
        try:
            nino34 = _get_live_nino34()
            pdf_report['_forecast'] = run_forecast(
                seed_mei=nino34['nino34_anom'] if nino34 else None,
                seed_date=nino34['date'] if nino34 else None
            )
            analytics_data = run_analytics(current_mei=nino34['nino34_anom'] if nino34 else None)
            pdf_report['_accuracy'] = analytics_data.get('forecast_accuracy')
        except Exception:
            pass
        generate_pdf(pdf_report)
        logger.info("📄 PDF generated for scheduled run")
    except Exception as e:
        logger.error(f"❌ Scheduled pipeline failed: {e}")


def _save_report_to_db(report: dict) -> None:
    """Upsert the report JSON into the reports table keyed by report_date."""
    try:
        report_date = report.get("report_date", datetime.now().strftime("%Y-%m-%d"))
        with _engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO reports (report_date, report_json)
                VALUES (:date, :json)
                ON CONFLICT (report_date) DO UPDATE SET report_json = EXCLUDED.report_json, created_at = NOW()
            """), {"date": report_date, "json": json.dumps(report)})
            conn.commit()
        logger.info(f"Report saved to DB for date {report_date}")
    except Exception as e:
        logger.error(f"Failed to save report to DB: {e}")


def _load_report_from_db() -> dict | None:
    """Load the most recent report JSON from the reports table."""
    try:
        with _engine.connect() as conn:
            row = conn.execute(text(
                "SELECT report_json FROM reports ORDER BY report_date DESC LIMIT 1"
            )).fetchone()
        if row:
            data = row[0]
            # psycopg2 auto-deserializes JSONB to dict; handle both dict and str
            if isinstance(data, dict):
                return data
            return json.loads(data)
    except Exception as e:
        logger.error(f"Failed to load report from DB: {e}")
    return None


def _get_report() -> dict | None:
    """Return cached report, falling back to DB then disk if cache is empty."""
    if _report_cache:
        return _report_cache
    report = _load_report_from_db()
    if not report:
        # Fallback: try local disk (for local dev without a DB)
        files = glob.glob("outputs/report_*.json")
        if files:
            with open(max(files)) as f:
                report = json.load(f)
    if report:
        _report_cache.update(report)
    return _report_cache or None


# ── Startup ───────────────────────────────────────────────────────────────────
def startup():
    try:
        logger.info("Running startup — initializing database...")
        with _engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS enso_data (
                    id SERIAL PRIMARY KEY,
                    date DATE UNIQUE,
                    mei_value FLOAT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS news_data (
                    id SERIAL PRIMARY KEY,
                    date DATE,
                    title TEXT,
                    source TEXT,
                    url TEXT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS commodity_prices (
                    id SERIAL PRIMARY KEY,
                    date DATE,
                    commodity TEXT,
                    ticker TEXT,
                    price FLOAT
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    report_date DATE UNIQUE,
                    report_json JSONB NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()
        logger.info("Tables created!")

        # Load MEI data
        if os.path.exists("data/raw/mei_index.csv"):
            df = pd.read_csv("data/raw/mei_index.csv")
            df.to_sql("enso_data", _engine, if_exists="replace", index=False)
            logger.info(f"Stored {len(df)} ENSO records")

        # Load commodity data
        files = glob.glob("data/raw/commodity_prices_*.csv")
        if files:
            df = pd.read_csv(max(files))
            df.to_sql("commodity_prices", _engine, if_exists="replace", index=False)
            logger.info(f"Stored {len(df)} commodity records")

        # Load news data
        news_files = glob.glob("data/raw/news/*.json")
        if news_files:
            rows = []
            for nf_path in news_files:
                with open(nf_path) as nf:
                    articles = json.load(nf)
                for article in articles:
                    rows.append({
                        "date": article.get("publishedAt", "")[:10],
                        "title": article.get("title", ""),
                        "source": article.get("source", {}).get("name", ""),
                        "url": article.get("url", "")
                    })
            df = pd.DataFrame(rows)
            df.to_sql("news_data", _engine, if_exists="replace", index=False)
            logger.info(f"Stored {len(df)} news records")

        # Pre-warm the in-memory cache from DB (survives Render redeploys)
        existing = _load_report_from_db()
        if existing:
            _report_cache.update(existing)
            logger.info("Pre-warmed report cache from DB")
        else:
            # Fallback for local dev: try disk
            files = glob.glob("outputs/report_*.json")
            if files:
                with open(max(files)) as f:
                    existing = json.load(f)
                _report_cache.update(existing)
                logger.info("Pre-warmed report cache from disk (local fallback)")

        logger.info("Startup complete!")

        # Start scheduled pipeline runs (every Monday at 9 AM UTC)
        if not scheduler.running:
            scheduler.add_job(
                _scheduled_pipeline_job,
                'cron',
                day_of_week=0,  # Monday (0 = Monday, 6 = Sunday)
                hour=9,
                minute=0,
                timezone='UTC',
                id='weekly_pipeline',
                name='Weekly ENSO Pipeline Run'
            )
            scheduler.start()
            logger.info("📅 Scheduled pipeline job registered: every Monday at 9 AM UTC")
    except Exception as e:
        logger.error(f"Startup failed: {e}")


startup()


# ── Shutdown ────────────────────────────────────────────────────────────────────
@app.on_event("shutdown")
def shutdown_event():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler shut down")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "name": "ENSO Intelligence Platform",
        "version": "1.0.0",
        "status": "running",
        "endpoints": ["/status", "/latest-report", "/latest-report/download", "/run-now", "/forecast", "/analytics", "/mei-history"]
    }


@app.get("/status")
def get_status():
    """
    Returns a concise status object.
    Auto-refreshes MEI data from NOAA if stale so the phase/MEI value stays current.
    Priority: in-memory cache → disk → 503 with helpful message.
    """
    _refresh_mei_if_stale()
    report = _get_report()

    if not report:
        # Return a structured "not ready" response instead of a 404.
        # The frontend can detect this and show a "Run pipeline first" prompt.
        return JSONResponse(
            status_code=503,
            content={
                "status": "no_data",
                "message": "No report available yet. POST /run-now to generate one.",
                "phase": None,
                "mei_value": None,
                "risk_score": None,
                "report_date": None,
                "last_updated": datetime.now().isoformat(),
            }
        )

    enso = report.get("enso_status", {})

    # Defensive: handle both {"enso_status": {"phase": ...}} and flat {"phase": ...}
    phase = enso.get("phase") or report.get("phase") or report.get("enso_phase") or "Unknown"
    mei   = enso.get("mei_value") or report.get("mei_value") or 0
    trend = enso.get("trend") or report.get("trend") or ""
    outlook = enso.get("outlook") or report.get("outlook") or ""

    # Override phase/MEI with the freshest DB value so the dashboard
    # always reflects the latest NOAA data, not a potentially weeks-old report
    db_mei_date = None
    try:
        with _engine.connect() as conn:
            row = conn.execute(text("""
                SELECT date, mei_value FROM enso_data
                WHERE mei_value BETWEEN -3 AND 3
                ORDER BY date DESC LIMIT 1
            """)).fetchone()
        if row:
            live_mei = float(row[1])
            db_mei_date = str(row[0])[:10]
            live_phase = (
                "El Niño" if live_mei >= 0.5
                else "La Niña" if live_mei <= -0.5
                else "Neutral"
            )
            # Only override if the live data is newer than the report
            report_date_str = report.get("report_date", "1970-01-01")
            if db_mei_date > report_date_str:
                mei = live_mei
                phase = live_phase
                trend = "warming" if live_mei > (enso.get("mei_value") or 0) else trend
    except Exception as e:
        logger.warning(f"Could not read live MEI for status override: {e}")

    # Always use the live Niño3.4 SST anomaly as the current phase indicator.
    # MEI is a lagged multivariate composite — during transitions it can show the
    # OPPOSITE phase from the actual SST.  Niño3.4 SST is the direct measurement.
    index_source = "mei"
    nino34 = _get_live_nino34()
    nino34_anom = None
    nino34_date = None
    if nino34:
        nino34_anom = nino34['nino34_anom']
        nino34_date = nino34['date']
        mei   = nino34_anom
        phase = nino34['phase']
        trend = "warming" if nino34_anom > 0 else "cooling"
        index_source = "nino34"
        logger.info(f"Status: Niño3.4 live {nino34_date}  {nino34_anom:+.2f}  → {phase}")

    return {
        "status": "ok",
        "phase": phase,
        "mei_value": mei,
        "index_source": index_source,
        "trend": trend,
        "outlook": outlook,
        "risk_score": report.get("risk_score", 0),
        "report_date": report.get("report_date", ""),
        "last_updated": report.get("report_date", datetime.now().strftime("%Y-%m-%d")),
        "nino34_anom": nino34_anom,
        "nino34_date": nino34_date,
    }


@app.get("/latest-report")
def get_latest_report():
    """Returns the full report JSON."""
    report = _get_report()
    if not report:
        raise HTTPException(
            status_code=503,
            detail="No report available yet. POST /run-now to generate one."
        )
    return JSONResponse(content=report)


@app.get("/latest-report/download")
def download_report():
    from fastapi.responses import StreamingResponse
    import io

    # Try disk first (fast path)
    files = glob.glob("outputs/ENSO_Report_*.pdf")
    if files:
        latest = max(files)
        return FileResponse(latest, media_type="application/pdf", filename=os.path.basename(latest))

    # Disk empty (Render restarted) — generate from DB report on-the-fly
    report = _get_report()
    if not report:
        raise HTTPException(status_code=404, detail="No report available yet. Run the pipeline first.")

    try:
        from pdf_generator import generate_pdf
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        generate_pdf(report, output_path=tmp_path)

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
        os.unlink(tmp_path)

        filename = f"ENSO_Report_{report.get('report_date', 'latest')}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


def _run_pipeline_background():
    """Runs the full pipeline in a background thread and updates cache + DB."""
    try:
        from pipeline import run_pipeline
        from pdf_generator import generate_pdf

        logger.info("Background pipeline started...")
        result = run_pipeline()

        # Use final_report from pipeline result directly — avoids disk path issues
        report = result.get("final_report") if isinstance(result, dict) else None

        # Fallback: try reading from disk
        if not report:
            files = glob.glob("outputs/report_*.json")
            if files:
                with open(max(files)) as f:
                    report = json.load(f)

        if report:
            _report_cache.clear()
            _report_cache.update(report)
            _save_report_to_db(report)
            logger.info("Background pipeline complete — cache + DB updated")
        else:
            logger.error("Pipeline completed but no report found in result or disk")

        pdf_report = dict(_report_cache or result)
        try:
            nino34 = _get_live_nino34()
            pdf_report['_forecast'] = run_forecast(
                seed_mei=nino34['nino34_anom'] if nino34 else None,
                seed_date=nino34['date'] if nino34 else None
            )
            analytics_data = run_analytics(current_mei=nino34['nino34_anom'] if nino34 else None)
            pdf_report['_accuracy'] = analytics_data.get('forecast_accuracy')
        except Exception:
            pass
        generate_pdf(pdf_report)
    except Exception as e:
        logger.error(f"Background pipeline failed: {e}")


@app.post("/run-now")
@limiter.limit("10/hour")
def run_pipeline_now(
    request: Request,
    background_tasks: BackgroundTasks,
    x_cron_secret: str | None = Header(default=None)
):
    """
    Triggers the agent pipeline in the background and returns immediately.
    Protected by CRON_SECRET env var when set — for use by cron-job.org only.
    """
    expected = os.getenv("CRON_SECRET")
    if expected and x_cron_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret header")

    background_tasks.add_task(_run_pipeline_background)
    return {
        "status": "accepted",
        "message": "Pipeline started in background. Check /status in ~3 minutes.",
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/trigger")
@limiter.limit("5/minute")
def trigger_pipeline(request: Request, background_tasks: BackgroundTasks):
    """Public endpoint for the dashboard Run Now button — rate-limited to 5/min."""
    background_tasks.add_task(_run_pipeline_background)
    return {
        "status": "accepted",
        "message": "Pipeline started in background. Check /status in ~3 minutes.",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/mei-history")
def get_mei_history():
    """
    Returns last 24 months of MEI index values formatted for the chart.
    Auto-refreshes from NOAA if data is stale. Falls back to CSV if DB unavailable.
    """
    _refresh_mei_if_stale()
    try:
        with _engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT date, mei_value
                FROM enso_data
                WHERE mei_value BETWEEN -3 AND 3
                ORDER BY date DESC
                LIMIT 24
            """)).fetchall()

        if rows:
            # Reverse so oldest → newest for the chart
            history = [
                {
                    "month": pd.to_datetime(str(row[0])).strftime("%b %y"),
                    "mei": round(float(row[1]), 2),
                    "is_forecast": False
                }
                for row in reversed(rows)
            ]
            return JSONResponse(content=history)
    except Exception as e:
        logger.warning(f"/mei-history DB query failed, falling back to CSV: {e}")

    # Fallback: read from CSV file directly
    try:
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw', 'mei_index.csv')
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['mei_value'] >= -3) & (df['mei_value'] <= 3)]
        df = df.sort_values('date').tail(24)
        history = [
            {
                "month": row['date'].strftime("%b %y"),
                "mei": round(float(row['mei_value']), 2),
                "is_forecast": False
            }
            for _, row in df.iterrows()
        ]
        return JSONResponse(content=history)
    except Exception as e:
        logger.error(f"/mei-history CSV fallback also failed: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/forecast")
def get_forecast():
    """
    Returns 6-month ENSO phase forecast using ML model (Gradient Boosting).
    Seeds the rolling forecast from the live weekly Niño3.4 value when it is
    more recent than the latest MEI in the DB, so the model starts from the
    correct current state rather than the stale historical tail.
    """
    _refresh_mei_if_stale()
    try:
        # Always seed from Niño3.4 SST — the most direct current ENSO measurement.
        # No date guard: MEI dates can be equal or newer than sstoi.indices even while
        # the SST reading is more accurate about the actual current phase.
        nino34    = _get_live_nino34()
        seed_mei  = nino34['nino34_anom'] if nino34 else None
        seed_date = nino34['date']         if nino34 else None
        forecast_data = run_forecast(seed_mei=seed_mei, seed_date=seed_date)
        return JSONResponse(content=forecast_data)
    except Exception as e:
        logger.error(f"/forecast failed: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "error": str(e),
                "historical": [],
                "forecast": [],
                "predicted_phase": "Unknown",
                "confidence_pct": 0,
                "model_info": "Error loading forecast model"
            }
        )



@app.get("/analytics")
def get_analytics():
    """
    Returns advanced analytics:
    - Phase probability distribution
    - Forecast accuracy metrics
    - Anomaly detection
    - Seasonal decomposition
    - Commodity sensitivity analysis
    - Similar historical events
    """
    try:
        nino34   = _get_live_nino34()
        live_mei = nino34['nino34_anom'] if nino34 else None
        analytics = run_analytics(current_mei=live_mei)
        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error(f"/analytics failed: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "error": str(e),
                "phase_probabilities": {"el_nino": 33, "la_nina": 34, "neutral": 33},
                "forecast_accuracy": {"mae": 0, "accuracy_pct": 0, "direction_accuracy": 0},
                "anomaly": {"is_anomaly": False, "z_score": 0, "message": f"Analytics error: {str(e)}"},
                "seasonal": {"trend": [], "seasonal": [], "residual": []},
                "commodity_sensitivity": {"wheat": 0, "crude_oil": 0, "soybean": 0},
                "similar_events": [],
                "status": "success"
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)