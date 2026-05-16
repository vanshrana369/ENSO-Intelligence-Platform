import os
import sys
import json
import glob
import logging
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'agents'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'data_pipeline'))
sys.path.append(os.path.join(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'enso_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Schedule: run every Monday at 8am
celery_app.conf.beat_schedule = {
    'weekly-enso-pipeline': {
        'task': 'backend.tasks.run_full_pipeline',
        'schedule': crontab(hour=8, minute=0, day_of_week=1)
    }
}

celery_app.conf.timezone = 'UTC'

@celery_app.task(name='backend.tasks.run_full_pipeline')
def run_full_pipeline():
    """Full pipeline: fetch data → run agents → generate PDF"""
    logger.info("Celery task started: Full Pipeline")

    try:
        # Step 1 — Fetch fresh data
        logger.info("Step 1: Fetching fresh data...")
        from fetch_noaa import fetch_mei_data
        from fetch_news import fetch_enso_news
        from fetch_prices import fetch_commodity_prices
        fetch_mei_data()
        fetch_enso_news()
        fetch_commodity_prices()
        logger.info("Data fetched successfully")

        # Step 2 — Store in DB
        logger.info("Step 2: Storing in database...")
        from store import store_enso_data, store_news_data, store_commodity_data, get_engine
        engine = get_engine()
        store_enso_data(engine)
        store_news_data(engine)
        store_commodity_data(engine)
        logger.info("Data stored successfully")

        # Step 3 — Run agents
        logger.info("Step 3: Running agent pipeline...")
        from pipeline import run_pipeline
        result = run_pipeline()
        logger.info("Agents completed successfully")

        # Step 4 — Generate PDF
        logger.info("Step 4: Generating PDF...")
        files = glob.glob("outputs/report_*.json")
        latest = max(files)
        with open(latest) as f:
            report = json.load(f)

        from pdf_generator import generate_pdf
        pdf_path = generate_pdf(report)
        logger.info(f"PDF generated: {pdf_path}")

        return {
            "status": "success",
            "enso_phase": result.get("enso_phase", ""),
            "pdf_path": pdf_path
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return {"status": "failed", "error": str(e)}


@celery_app.task(name='backend.tasks.test_task')
def test_task():
    """Simple test task"""
    logger.info("Test task executed successfully!")
    return {"status": "success", "message": "Celery is working!"}


if __name__ == "__main__":
    print("Testing Celery task directly...")
    result = test_task()
    print(result)