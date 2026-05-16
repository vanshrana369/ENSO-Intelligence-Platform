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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def startup():
    try:
        logger.info("Running startup - initializing database...")
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
        import json as json_module
        news_files = glob.glob("data/raw/news/*.json")
        if news_files:
            rows = []
            for f in news_files:
                with open(f) as nf:
                    articles = json_module.load(nf)
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

        logger.info("Startup complete!")
    except Exception as e:
        logger.error(f"Startup failed: {e}")

startup()

@app.get("/")
def root():
    return {
        "name": "ENSO Intelligence Platform",
        "version": "1.0.0",
        "status": "running",
        "endpoints": ["/status", "/latest-report", "/latest-report/download", "/run-now"]
    }

@app.get("/status")
def get_status():
    files = glob.glob("outputs/report_*.json")
    if not files:
        raise HTTPException(status_code=404, detail="No reports found.")
    latest = max(files)
    with open(latest) as f:
        report = json.load(f)
    enso = report.get("enso_status", {})
    return {
        "phase": enso.get("phase", "Unknown"),
        "mei_value": enso.get("mei_value", 0),
        "trend": enso.get("trend", ""),
        "outlook": enso.get("outlook", ""),
        "risk_score": report.get("risk_score", 0),
        "report_date": report.get("report_date", ""),
        "last_updated": datetime.now().isoformat()
    }

@app.get("/latest-report")
def get_latest_report():
    files = glob.glob("outputs/report_*.json")
    if not files:
        raise HTTPException(status_code=404, detail="No reports found.")
    latest = max(files)
    with open(latest) as f:
        report = json.load(f)
    return JSONResponse(content=report)

@app.get("/latest-report/download")
def download_report():
    files = glob.glob("outputs/ENSO_Report_*.pdf")
    if not files:
        raise HTTPException(status_code=404, detail="No PDF found.")
    latest = max(files)
    return FileResponse(latest, media_type="application/pdf", filename=os.path.basename(latest))

@app.post("/run-now")
def run_pipeline_now():
    try:
        from pipeline import run_pipeline
        from pdf_generator import generate_pdf
        result = run_pipeline()
        files = glob.glob("outputs/report_*.json")
        latest = max(files)
        with open(latest) as f:
            report = json.load(f)
        pdf_path = generate_pdf(report)
        return {
            "status": "success",
            "enso_phase": result.get("enso_phase", ""),
            "pdf_generated": pdf_path,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)