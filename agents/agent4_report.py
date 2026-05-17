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
    raw_news_items = state.get("raw_news_items", [])

    # ── Get TODAY's date in the format the LLM should use ──────────────────────
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
    You are a senior climate intelligence analyst writing a professional briefing.
    Generate a structured report in JSON format only. No extra text, just valid JSON.

    Use this data:
    - ENSO Phase: {enso_phase}
    - MEI Value: {latest_mei}
    - ENSO Analysis: {enso_summary}
    - News Insights: {news_insights[:800]}
    - Market Risks: {market_risks[:800]}

    TODAY'S DATE IS: {today}

    Return exactly this JSON structure (IMPORTANT: use {today} for report_date):
    {{
        "report_date": "{today}",
        "executive_summary": "3-4 sentence overview covering: current ENSO phase and MEI value, key market implications, and near-term outlook. Be specific about mechanisms and magnitudes.",
        "enso_status": {{
            "phase": "El Nino/La Nina/Neutral",
            "mei_value": {latest_mei},
            "trend": "strengthening/weakening/stable",
            "outlook": "2 sentence outlook covering transition probability and timeline"
        }},
        "market_risks": {{
            "wheat": {{
                "risk_level": "Low/Medium/High/Extreme",
                "outlook": "2-3 sentences: (1) how current {enso_phase} specifically affects wheat growing regions, (2) which countries/regions are most exposed, (3) expected price direction with rough magnitude (e.g. +5-15% upside risk over 6 months)"
            }},
            "crude_oil": {{
                "risk_level": "Low/Medium/High/Extreme",
                "outlook": "2-3 sentences: (1) ENSO impact on energy demand and production regions, (2) specific supply chain or demand drivers, (3) price outlook with direction and rough range"
            }},
            "soybean": {{
                "risk_level": "Low/Medium/High/Extreme",
                "outlook": "2-3 sentences: (1) impact on South American and US growing conditions under {enso_phase}, (2) yield risk and demand dynamics, (3) price direction with rough magnitude"
            }}
        }},
        "key_recommendations": [
            "Specific actionable recommendation 1 with commodity, action, and timeframe (e.g. 'Reduce wheat exposure by 15-20% over next 60 days given elevated drought risk in Black Sea region under La Nina')",
            "Specific actionable recommendation 2 referencing ENSO mechanism and hedging instrument or strategy",
            "Specific actionable recommendation 3 covering portfolio diversification or alternative assets with climate resilience rationale"
        ],
        "risk_score": 7
    }}

    RULES:
    - risk_score: integer 1-10 only (NOT 0-100). 1-3=low, 4-6=medium, 7-8=high, 9-10=extreme.
    - All outlook text must be specific to {enso_phase} conditions, not generic.
    - Include real geographic regions, crop names, and percentage estimates where possible.
    - Recommendations must start with an action verb and include a commodity and timeframe.
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
        report["report_date"] = today

        # ── Attach real news items from DB (bypasses LLM for accuracy) ─────────
        if raw_news_items:
            report["news_items"] = raw_news_items[:6]

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
            "news_items": raw_news_items[:6],
            "raw_llm_output": raw_output[:500]
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