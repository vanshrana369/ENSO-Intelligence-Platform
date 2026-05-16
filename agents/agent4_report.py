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

    # ── Get TODAY's date in the format the LLM should use ──────────────────────
    today = datetime.now().strftime("%Y-%m-%d")

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
    
    TODAY'S DATE IS: {today}
    
    Return exactly this JSON structure (IMPORTANT: use {today} for report_date):
    {{
        "report_date": "{today}",
        "executive_summary": "2-3 sentence overview",
        "enso_status": {{
            "phase": "El Nino/La Nina/Neutral",
            "mei_value": {latest_mei},
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
        "risk_score": 7
    }}
    """

    response = llm.invoke(prompt)
    raw_output = response.content

    # ── Clean and parse JSON ──────────────────────────────────────────────────
    report = None
    try:
        clean = raw_output.strip()
        
        # Remove markdown code fences if present
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0]
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0]
        
        # Try to parse JSON
        report = json.loads(clean)
        
        # ── CRITICAL: Ensure report_date is TODAY, not what LLM returned ──────
        # (LLM sometimes gets dates wrong; we override it to be safe)
        report["report_date"] = today
        
        logger.info("JSON parsed successfully")
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        logger.error(f"Raw output was: {raw_output}")
        # Fallback: create a minimal valid report
        report = {
            "report_date": today,
            "executive_summary": enso_summary or "Report generation encountered an issue.",
            "enso_status": {
                "phase": enso_phase or "Unknown",
                "mei_value": latest_mei or 0.0,
                "trend": "unknown",
                "outlook": "Unable to generate outlook."
            },
            "market_risks": {
                "wheat": {"risk_level": "Unknown", "outlook": "See raw data"},
                "crude_oil": {"risk_level": "Unknown", "outlook": "See raw data"},
                "soybean": {"risk_level": "Unknown", "outlook": "See raw data"}
            },
            "key_recommendations": [
                "Manual review of market data recommended.",
                "Contact climate intelligence team for detailed analysis.",
                "Check raw LLM output in debug logs."
            ],
            "risk_score": 5,
            "raw_llm_output": raw_output[:500]  # Store truncated LLM response for debugging
        }

    # ── Save report to file ───────────────────────────────────────────────────
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