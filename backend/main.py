import os
import sys
import json
import glob
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

# Add agents folder to path so we can import pipeline
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'agents'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ENSO Intelligence Platform",
    description="AI-powered climate risk intelligence API",
    version="1.0.0"
)

# ─── ROUTES ───────────────────────────────────────────

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
    """Returns current ENSO status from latest report"""
    files = glob.glob("outputs/report_*.json")
    if not files:
        raise HTTPException(status_code=404, detail="No reports found. Run pipeline first.")
    
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
    """Returns latest report as JSON"""
    files = glob.glob("outputs/report_*.json")
    if not files:
        raise HTTPException(status_code=404, detail="No reports found. Run pipeline first.")
    
    latest = max(files)
    with open(latest) as f:
        report = json.load(f)
    
    return JSONResponse(content=report)

@app.get("/latest-report/download")
def download_report():
    """Downloads latest PDF report"""
    files = glob.glob("outputs/ENSO_Report_*.pdf")
    if not files:
        raise HTTPException(status_code=404, detail="No PDF found. Run pipeline first.")
    
    latest = max(files)
    return FileResponse(
        latest,
        media_type="application/pdf",
        filename=os.path.basename(latest)
    )

@app.post("/run-now")
def run_pipeline_now():
    """Manually triggers the full pipeline"""
    try:
        logger.info("Manual pipeline trigger received...")
        from pipeline import run_pipeline
        from pdf_generator import generate_pdf
        import glob as g

        # Run agents
        result = run_pipeline()

        # Generate PDF from latest JSON
        files = g.glob("outputs/report_*.json")
        latest = max(files)
        with open(latest) as f:
            report = json.load(f)

        pdf_path = generate_pdf(report)

        return {
            "status": "success",
            "enso_phase": result.get("enso_phase", ""),
            "risk_score": result.get("final_report", {}).get("risk_score", 0),
            "pdf_generated": pdf_path,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)