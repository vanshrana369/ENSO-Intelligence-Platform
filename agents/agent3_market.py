import os
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

def get_commodity_prices():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT date, commodity, price 
            FROM commodity_prices 
            ORDER BY date DESC 
            LIMIT 30
        """))
        rows = result.fetchall()
    return rows

def run_agent3(state):
    logger.info("Agent 3: Market Analyzer starting...")

    enso_phase = state.get("enso_phase", "La Nina")
    enso_summary = state.get("enso_summary", "")
    news_insights = state.get("news_insights", "")

    rows = get_commodity_prices()

    if not rows:
        logger.warning("No commodity data found")
        return {**state, "market_risks": "No commodity data available"}

    # Get latest price for each commodity
    prices = {}
    for row in rows:
        commodity = row[1]
        if commodity not in prices:
            prices[commodity] = row[2]

    prices_text = "\n".join([
        f"- {commodity}: ${price:.2f}"
        for commodity, price in prices.items()
    ])

    prompt = f"""
    You are a commodity market analyst specializing in climate risk.

    Current ENSO Phase: {enso_phase}
    ENSO Summary: {enso_summary}
    News Context: {news_insights[:500]}

    Current Commodity Prices:
    {prices_text}

    Based on historical ENSO patterns (1997, 2015 El Niño; 2010-12 La Niña events),
    assess each commodity listed above:
    1. Risk level: Low / Medium / High / Extreme
    2. Which growing regions or supply chains are exposed under {enso_phase}
    3. One-line price outlook with approximate % move and timeframe

    Cover ALL commodities in the price list. Be specific with numbers and regions.
    """

    response = llm.invoke(prompt)
    market_risks = response.content

    logger.info("Agent 3 complete!")

    print("\n=== AGENT 3: MARKET ANALYZER ===")
    print(f"Commodities analyzed: {list(prices.keys())}")
    print(f"\nMarket Risks:\n{market_risks}")

    return {
        **state,
        "market_risks": market_risks,
        "commodity_prices": prices
    }

if __name__ == "__main__":
    mock_state = {
        "enso_phase": "La Nina",
        "latest_mei": -1.03,
        "enso_summary": "La Nina conditions detected with MEI at -1.03",
        "news_insights": "El Nino expected to return by mid-2026"
    }
    run_agent3(mock_state)