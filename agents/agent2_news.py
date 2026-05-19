import os
import sys
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sqlalchemy import create_engine, text

load_dotenv()

# Allow importing from data_pipeline/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data_pipeline'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)

def get_latest_news():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT date, title, source, url
            FROM news_data
            ORDER BY date DESC
            LIMIT 10
        """))
        rows = result.fetchall()
    return rows

_CLIMATE_KEYWORDS = [
    'enso', 'el niño', 'el nino', 'la niña', 'la nina', 'climate', 'weather',
    'drought', 'flood', 'temperature', 'rainfall', 'monsoon', 'pacific', 'ocean',
    'sea surface', 'sst', 'commodity', 'wheat', 'soybean', 'crude oil', 'crop',
    'agriculture', 'harvest', 'storm', 'cyclone', 'hurricane', 'precipitation',
    'food price', 'food security', 'wmo', 'noaa', 'global warming'
]

def _is_climate_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _CLIMATE_KEYWORDS)

def run_agent2(state):
    logger.info("Agent 2: News Analyst starting...")

    # Fetch fresh news from NewsAPI and store to DB before reading
    try:
        from fetch_news import fetch_enso_news
        fetch_enso_news()
    except Exception as e:
        logger.warning(f"Live news fetch failed (using existing DB data): {e}")

    # Get enso context from Agent 1
    enso_summary = state.get("enso_summary", "La Nina conditions detected")
    enso_phase = state.get("enso_phase", "La Nina")

    # Get news from DB and filter to climate-relevant only
    rows = get_latest_news()
    rows = [r for r in rows if _is_climate_relevant(r[1])]

    if not rows:
        logger.warning("No climate-relevant news found in database")
        return {"news_insights": "No recent climate news available"}

    # Format headlines for LLM
    headlines = "\n".join([
        f"- {row[1]} ({row[2]})" for row in rows
    ])

    prompt = f"""
    You are a climate news analyst.
    
    Current ENSO Status: {enso_phase}
    ENSO Summary: {enso_summary}
    
    Recent headlines:
    {headlines}
    
    Based on these headlines and the current {enso_phase} conditions:
    1. Identify top 3 most relevant climate impact stories
    2. For each story mention: affected region and severity
    3. Write a 2-sentence overall news insight summary
    
    Be specific and professional.
    """

    response = llm.invoke(prompt)
    insights = response.content

    logger.info("Agent 2 complete!")

    print("\n=== AGENT 2: NEWS ANALYST ===")
    print(f"Headlines analyzed: {len(rows)}")
    print(f"\nInsights:\n{insights}")

    # Pass raw news items through the pipeline so the final report can include them
    raw_news = [
        {"title": row[1], "source": row[2], "date": str(row[0]), "url": row[3] or ""}
        for row in rows
    ]

    return {
        **state,
        "news_insights": insights,
        "raw_news_items": raw_news
    }

if __name__ == "__main__":
    # Test with mock state from Agent 1
    mock_state = {
        "enso_phase": "La Nina",
        "latest_mei": -1.03,
        "enso_summary": "La Nina conditions detected with MEI at -1.03"
    }
    run_agent2(mock_state)