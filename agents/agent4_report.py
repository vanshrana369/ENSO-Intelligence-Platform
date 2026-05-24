import os
import json
import logging
from datetime import datetime
from typing import Dict, List
from pydantic import BaseModel, field_validator, ValidationError
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Pydantic schema for LLM output validation ─────────────────────────────────

class CommodityRisk(BaseModel):
    risk_level: str
    outlook: str

    @field_validator('risk_level')
    @classmethod
    def valid_risk(cls, v):
        allowed = {'Low', 'Medium', 'High', 'Extreme', 'Unknown'}
        if v not in allowed:
            v = v.capitalize()
            if v not in allowed:
                return 'Unknown'
        return v


class ENSOStatus(BaseModel):
    phase: str
    mei_value: float
    trend: str
    outlook: str


class ReportSchema(BaseModel):
    report_date: str
    executive_summary: str
    enso_status: ENSOStatus
    market_risks: Dict[str, CommodityRisk]
    key_recommendations: List[str]
    risk_score: int

    @field_validator('risk_score')
    @classmethod
    def clamp_risk(cls, v):
        return max(1, min(10, int(v)))

    @field_validator('key_recommendations')
    @classmethod
    def at_least_one(cls, v):
        return v if v else ['Review current ENSO conditions and monitor commodity exposure.']


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
    - Current ENSO indicator (Niño3.4 SST anomaly, in °C): {latest_mei}
    - ENSO Analysis: {enso_summary}
    - News Insights: {news_insights[:800]}
    - Market Risks: {market_risks[:800]}

    TODAY'S DATE IS: {today}

    Return exactly this JSON structure (IMPORTANT: use {today} for report_date):
    {{
        "report_date": "{today}",
        "executive_summary": "3-4 sentence overview covering: current ENSO phase and current index value with correct units (the Niño3.4 SST anomaly reading is in °C; never attach °C to an MEI value), key market implications, and near-term outlook. Be specific about mechanisms and magnitudes.",
        "enso_status": {{
            "phase": "El Nino/La Nina/Neutral",
            "mei_value": {latest_mei},
            "trend": "strengthening/weakening/stable",
            "outlook": "2 sentence outlook covering transition likelihood (qualitative, no invented percentages) and timeline"
        }},
        "market_risks": {{
            "wheat":       {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on growing region exposure, affected countries, expected price direction with % magnitude"}},
            "crude_oil":   {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on energy demand/supply chains under {enso_phase}, price outlook with range"}},
            "soybean":     {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on South American / US growing conditions, yield risk, price direction with % magnitude"}},
            "corn":        {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on corn belt precipitation, US / Brazil exposure, price direction"}},
            "coffee":      {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on Brazil / Vietnam / Colombia growing conditions under {enso_phase}, price direction"}},
            "sugar":       {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on Brazil / India / Thailand cane production under {enso_phase}, price direction"}},
            "cotton":      {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on US / India / Pakistan cotton belt exposure, price direction"}},
            "natural_gas": {{"risk_level": "Low/Medium/High/Extreme", "outlook": "2-3 sentences on heating/cooling demand shifts under {enso_phase}, price outlook"}}
        }},
        "key_recommendations": [
            "Specific actionable recommendation 1 with commodity, action, and timeframe",
            "Specific actionable recommendation 2 referencing ENSO mechanism and hedging strategy",
            "Specific actionable recommendation 3 covering portfolio diversification or climate-resilient assets"
        ],
        "risk_score": 7
    }}

    RULES:
    - risk_score: integer 1-10 only (NOT 0-100). 1-3=low, 4-6=medium, 7-8=high, 9-10=extreme.
    - All outlook text must be specific to {enso_phase} conditions, not generic.
    - Include real geographic regions, crop names, and percentage estimates where possible.
    - Recommendations must start with an action verb and include a commodity and timeframe.
    - MEI is a dimensionless index — NEVER write a °C unit after an MEI value. The current SST anomaly value provided above IS measured in °C; the MEI is not. Do not conflate the two or invent a '°C MEI' value.
    - Do NOT state specific numeric transition-probability percentages (e.g. '50-60% probability of El Niño'). Phase-transition probabilities are computed and displayed elsewhere in the platform. Describe transition likelihood QUALITATIVELY (e.g., 'conditions increasingly favor a transition toward El Niño') and focus on mechanism and timeline.
    - INTERNAL CONSISTENCY: For each commodity, the expected price DIRECTION (up vs down) must be IDENTICAL across executive_summary, market_risks, and key_recommendations. Never describe the same commodity as both rising and falling.
    - TRADE LOGIC must be correct: to profit from an expected price INCREASE, recommend BUY / go long / hold long. To profit from an expected price DECREASE, recommend SELL / short / hedge short. Never pair a 'sell' action with a stated expectation of rising prices, or a 'buy' action with falling prices.
    - Each recommendation must state an action + commodity + timeframe AND a rationale whose price direction matches that commodity's market_risks outlook (and the trade logic rule above).
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
        raw_report = json.loads(clean)

        # ── Pydantic validation — catches bad risk_levels, missing fields, etc. ─
        try:
            validated = ReportSchema(**raw_report)
            report = validated.model_dump()
        except ValidationError as ve:
            logger.warning(f"Pydantic validation warnings: {ve} — using raw parsed JSON")
            report = raw_report

        # ── CRITICAL: Ensure report_date is TODAY, not what LLM returned ──────
        report["report_date"] = today

        # ── Attach real news items from DB (bypasses LLM for accuracy) ─────────
        if raw_news_items:
            report["news_items"] = raw_news_items[:6]

        logger.info("JSON parsed and validated successfully")
        
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