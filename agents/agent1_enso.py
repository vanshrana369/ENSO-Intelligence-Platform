import os
import logging
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = "postgresql://postgres:9213546700@localhost:5432/enso_db"

llm = ChatGroq(
    model="llama-3.1-8b-instant",
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

    rows = get_latest_enso_data()
    latest_mei = rows[0][1]
    latest_date = rows[0][0]
    phase = determine_enso_phase(latest_mei)

    data_summary = "\n".join([
        f"{row[0]}: {row[1]}" for row in rows
    ])

    prompt = f"""
    You are a climate analyst. Based on this ENSO MEI index data:
    
    {data_summary}
    
    Current phase: {phase}
    Latest MEI value: {latest_mei}
    
    Write a 3-sentence professional summary of current ENSO conditions 
    and what trend you observe. Be specific about the numbers.
    """

    response = llm.invoke(prompt)
    summary = response.content

    logger.info("Agent 1 complete!")

    print("\n=== AGENT 1: ENSO MONITOR ===")
    print(f"Phase: {phase}")
    print(f"Latest MEI: {latest_mei}")
    print(f"\nSummary:\n{summary}")

    return {
        "enso_phase": phase,
        "latest_mei": latest_mei,
        "latest_date": str(latest_date),
        "enso_summary": summary
    }

if __name__ == "__main__":
    run_agent1({})