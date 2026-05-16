import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY")
)

def run_agent4(state):
    logger.info("Agent 4: Report Generator starting...")

    enso_phase = state.get("enso_phase", "")
    latest_mei = state.get("latest_mei", "")
    enso_summary = state.get("enso_summary", "")
    news_insights = state.get("news_insights", "")
    market_risks = state.get("market_risks", "")

    prompt = f"""
    You are a senior climate intelligence analyst. 
    Generate a structured professional report in JSON format only.
    No extra text, just valid JSON.
    
    Use this data:
    - ENSO Phase: {enso_phase}
    - MEI Value: {latest_mei}
    - ENSO Analysis: {enso_summary}
    - News Insights: {news_insights[:600]}
    - Market Risks: {market_risks[:600]}
    
    Return exactly this JSON structure:
    {{
        "report_date": "today's date",
        "executive_summary": "2-3 sentence overview",
        "enso_status": {{
            "phase": "El Nino/La Nina/Neutral",
            "mei_value": 0.0,
            "trend": "rising/falling/stable",
            "outlook": "1 sentence outlook"
        }},
        "market_risks": {{
            "wheat": {{"risk_level": "Low/Medium/High", "outlook": "one line"}},
            "crude_oil": {{"risk_level": "Low/Medium/High", "outlook": "one line"}},
            "soybean": {{"risk_level": "Low/Medium/High", "outlook": "one line"}}
        }},
        "key_recommendations": [
            "recommendation 1",
            "recommendation 2",
            "recommendation 3"
        ],
        "risk_score": 0
    }}
    """

    response = llm.invoke(prompt)
    raw_output = response.content

    # Clean and parse JSON
    try:
        clean = raw_output.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0]
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0]
        report = json.loads(clean)
    except Exception as e:
        logger.error(f"JSON parsing failed: {e}")
        report = {"raw_output": raw_output}

    # Save report to file
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/report_{today}.json"
    with open(filename, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Agent 4 complete! Report saved to {filename}")

    print("\n=== AGENT 4: REPORT GENERATOR ===")
    print(json.dumps(report, indent=2))

    return {
        **state,
        "final_report": report
    }

if __name__ == "__main__":
    mock_state = {
        "enso_phase": "La Nina",
        "latest_mei": -1.03,
        "enso_summary": "La Nina conditions detected with MEI at -1.03, intensifying trend",
        "news_insights": "El Nino expected to return by mid-2026, super El Nino warnings",
        "market_risks": "Soybean high risk, crude oil medium risk, wheat low risk"
    }
    run_agent4(mock_state)