import os
import sys
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sqlalchemy import create_engine, text

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data_pipeline'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:9213546700@localhost:5432/enso_db")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

def get_latest_enso_data():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT date, mei_value 
            FROM enso_data 
            ORDER BY date DESC 
            LIMIT 6
        """))
        rows = result.fetchall()
    return rows

def determine_enso_phase(mei_value):
    if mei_value >= 0.5:
        return "El Nino"
    elif mei_value <= -0.5:
        return "La Nina"
    else:
        return "Neutral"

def run_agent1(state):
    logger.info("Agent 1: ENSO Monitor starting...")

    # Refresh MEI and commodity data from live sources before analysis
    try:
        from fetch_noaa import fetch_mei_data
        fetch_mei_data()
    except Exception as e:
        logger.warning(f"MEI data refresh failed (using existing DB data): {e}")

    try:
        from fetch_prices import fetch_commodity_prices
        fetch_commodity_prices()
    except Exception as e:
        logger.warning(f"Commodity price refresh failed (using existing DB data): {e}")

    rows = get_latest_enso_data()
    latest_mei = float(rows[0][1])
    latest_date = rows[0][0]
    phase = determine_enso_phase(latest_mei)

    # Override phase/MEI with live Niño3.4 SST — the most direct ENSO measurement.
    # MEI is a lagged multivariate composite; during transitions it can show the
    # OPPOSITE phase from the actual Pacific SST.
    nino34_note = ""
    try:
        from fetch_nino34 import fetch_nino34_weekly
        nino34 = fetch_nino34_weekly()
        if nino34:
            latest_mei  = nino34['nino34_anom']
            latest_date = nino34['date']
            phase       = nino34['phase']
            nino34_note = (
                f"\nNOTE: Live Niño3.4 SST anomaly ({nino34['date']}): {latest_mei:+.2f}°C"
                f" — this is the most current ENSO reading and supersedes older MEI values."
            )
            logger.info(f"Agent 1: live Niño3.4 override → {phase}  {latest_mei:+.2f}")
    except Exception as e:
        logger.warning(f"Niño3.4 override skipped: {e}")

    # Build historical context (oldest → newest from DB, plus live reading at top)
    historical_rows = "\n".join([f"  {row[0]}: MEI {row[1]:+.2f}" for row in reversed(rows)])
    data_summary = (
        f"Historical MEI (last 6 months, from DB):\n{historical_rows}"
        f"\n\nCurrent live reading: Niño3.4 SST anomaly = {latest_mei:+.2f}°C  →  Phase: {phase}"
    )

    prompt = f"""You are a senior climate analyst.

ENSO index data:
{data_summary}
{nino34_note}

Current phase: {phase}
Current ENSO index value: {latest_mei:+.2f}

The current reading is a Niño3.4 SST anomaly measured in °C; the MEI is a dimensionless standardized index, so NEVER write "MEI" followed by a °C unit (e.g. never "MEI of +0.8°C") — attach °C only to the SST anomaly, never to the MEI.

Write a 3-sentence professional summary that:
1. States the current phase and the most recent index value precisely.
2. Describes the recent trend (what the historical data shows vs. where we are now).
3. Gives the near-term outlook based on the current trajectory.

Be specific about numbers and the phase transition if one is occurring.
"""

    response = llm.invoke(prompt)
    summary = response.content

    logger.info("Agent 1 complete!")

    print("\n=== AGENT 1: ENSO MONITOR ===")
    print(f"Phase: {phase}")
    print(f"Latest MEI/Niño3.4: {latest_mei}")
    print(f"\nSummary:\n{summary}")

    return {
        "enso_phase": phase,
        "latest_mei": latest_mei,
        "latest_date": str(latest_date),
        "enso_summary": summary
    }

if __name__ == "__main__":
    run_agent1({})