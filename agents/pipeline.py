import logging
from typing import TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agent1_enso import run_agent1
from agent2_news import run_agent2
from agent3_market import run_agent3
from agent4_report import run_agent4

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared state for all agents
class ENSOState(TypedDict):
    enso_phase: str
    latest_mei: float
    latest_date: str
    enso_summary: str
    news_insights: str
    market_risks: str
    commodity_prices: dict
    final_report: dict

def build_pipeline():
    # Create the graph
    graph = StateGraph(ENSOState)

    # Add all 4 agents as nodes
    graph.add_node("enso_monitor", run_agent1)
    graph.add_node("news_analyst", run_agent2)
    graph.add_node("market_analyzer", run_agent3)
    graph.add_node("report_generator", run_agent4)

    # Connect them in sequence
    graph.add_edge("enso_monitor", "news_analyst")
    graph.add_edge("news_analyst", "market_analyzer")
    graph.add_edge("market_analyzer", "report_generator")
    graph.add_edge("report_generator", END)

    # Set starting point
    graph.set_entry_point("enso_monitor")

    return graph.compile()

def run_pipeline():
    logger.info("Starting ENSO Intelligence Pipeline...")
    print("\n" + "="*50)
    print("ENSO INTELLIGENCE PLATFORM - FULL PIPELINE")
    print("="*50)

    # Build and run
    app = build_pipeline()

    # Empty initial state
    initial_state = {
        "enso_phase": "",
        "latest_mei": 0.0,
        "latest_date": "",
        "enso_summary": "",
        "news_insights": "",
        "market_risks": "",
        "commodity_prices": {},
        "final_report": {}
    }

    result = app.invoke(initial_state)

    print("\n" + "="*50)
    print("PIPELINE COMPLETE!")
    print(f"ENSO Phase: {result['enso_phase']}")
    print(f"MEI Value: {result['latest_mei']}")
    print(f"Risk Score: {result['final_report'].get('risk_score', 'N/A')}")
    print("="*50)

    return result

if __name__ == "__main__":
    run_pipeline()