import os
import sys
import json
import glob
import logging
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

app = FastAPI(
    title="ENSO Intelligence Platform",
    description="AI-powered climate risk intelligence API",
    version="1.0.0"
)

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
scheduler = BackgroundScheduler()


def _scheduled_pipeline_job():
    """Background job: run the pipeline every Monday at 9 AM UTC."""
    try:
        logger.info("⏰ Scheduled pipeline job triggered (Monday 9 AM UTC)")
        from pipeline import run_pipeline
        from pdf_generator import generate_pdf

        result = run_pipeline()

        # Update in-memory cache
        files = glob.glob("outputs/report_*.json")
        if files:
            with open(max(files)) as f:
                report = json.load(f)
            _report_cache.clear()
            _report_cache.update(report)
            logger.info("✅ Scheduled pipeline completed — cache updated")

        # Generate PDF
        generate_pdf(_report_cache or result)
        logger.info("📄 PDF generated for scheduled run")
    except Exception as e:
        logger.error(f"❌ Scheduled pipeline failed: {e}")


def _load_report_from_disk() -> dict | None:
    """Try to load the newest report JSON from the outputs/ directory."""
    files = glob.glob("outputs/report_*.json")
    if not files:
        return None
    with open(max(files)) as f:
        return json.load(f)


def _get_report() -> dict | None:
    """Return cached report, falling back to disk if cache is empty."""
    if _report_cache:
        return _report_cache
    report = _load_report_from_disk()
    if report:
        _report_cache.update(report)
    return _report_cache or None


# ── Startup ───────────────────────────────────────────────────────────────────
def startup():
    try:
        logger.info("Running startup — initializing database...")
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
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
            conn.commit()
        logger.info("Tables created!")

        # Load MEI data
        if os.path.exists("data/raw/mei_index.csv"):
            df = pd.read_csv("data/raw/mei_index.csv")
            df.to_sql("enso_data", engine, if_exists="replace", index=False)
            logger.info(f"Stored {len(df)} ENSO records")

        # Load commodity data
        files = glob.glob("data/raw/commodity_prices_*.csv")
        if files:
            df = pd.read_csv(max(files))
            df.to_sql("commodity_prices", engine, if_exists="replace", index=False)
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
            df.to_sql("news_data", engine, if_exists="replace", index=False)
            logger.info(f"Stored {len(df)} news records")

        # Pre-warm the in-memory cache from any existing report on disk
        existing = _load_report_from_disk()
        if existing:
            _report_cache.update(existing)
            logger.info("Pre-warmed report cache from disk")

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
        "endpoints": ["/status", "/latest-report", "/latest-report/download", "/run-now", "/forecast", "/analytics"]
    }


@app.get("/status")
def get_status():
    """
    Returns a concise status object.

    Priority: in-memory cache → disk → 503 with helpful message.
    Never raises 404 on Render where the filesystem may be empty.
    """
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

    return {
        "status": "ok",
        "phase": phase,
        "mei_value": mei,
        "trend": trend,
        "outlook": outlook,
        "risk_score": report.get("risk_score", 0),
        "report_date": report.get("report_date", ""),
        "last_updated": datetime.now().isoformat(),
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
    files = glob.glob("outputs/ENSO_Report_*.pdf")
    if not files:
        raise HTTPException(status_code=404, detail="No PDF found. Run /run-now first.")
    latest = max(files)
    return FileResponse(latest, media_type="application/pdf", filename=os.path.basename(latest))


@app.post("/run-now")
def run_pipeline_now():
    """
    Triggers the agent pipeline.

    On success, populates the in-memory cache so /status and /latest-report
    serve live data immediately — even if Render's disk is wiped on next deploy.
    """
    try:
        from pipeline import run_pipeline
        from pdf_generator import generate_pdf

        result = run_pipeline()

        # ── Update in-memory cache ────────────────────────────────────────────
        # read the report file that run_pipeline() just wrote to disk…
        files = glob.glob("outputs/report_*.json")
        if files:
            with open(max(files)) as f:
                report = json.load(f)
            _report_cache.clear()
            _report_cache.update(report)
            logger.info("In-memory report cache updated after run-now")

        pdf_path = generate_pdf(_report_cache or result)

        return {
            "status": "success",
            "enso_phase": result.get("enso_phase", _report_cache.get("phase", "")),
            "pdf_generated": pdf_path,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"/run-now failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast")
def get_forecast():
    """
    Returns 6-month ENSO phase forecast using ML model (Gradient Boosting).
    Includes historical MEI data (12 months) and confidence intervals.
    """
    try:
        forecast_data = run_forecast()
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
        analytics = run_analytics()
        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error(f"/analytics failed: {e}")
        return JSONResponse(
            status_code=200,
            content={
                "error": str(e),
                "phase_probabilities": {"el_nino": 0, "la_nina": 0, "neutral": 0},
                "forecast_accuracy": {"mae": 0, "accuracy_pct": 0, "direction_accuracy": 0},
                "anomaly": {"is_anomaly": False, "z_score": 0, "message": "Error"},
                "seasonal": {"trend": [], "seasonal": [], "residual": []},
                "commodity_sensitivity": {"wheat": 0, "crude_oil": 0, "soybean": 0},
                "similar_events": []
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)