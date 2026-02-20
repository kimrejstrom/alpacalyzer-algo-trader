import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from colorama import init
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from alpacalyzer.agents.agents import get_analyst_nodes
from alpacalyzer.data.models import TopTicker
from alpacalyzer.graph.state import AgentState
from alpacalyzer.trading.portfolio_manager import portfolio_management_agent
from alpacalyzer.trading.risk_manager import risk_management_agent
from alpacalyzer.trading.trading_strategist import trading_strategist_agent
from alpacalyzer.utils.logger import get_logger
from alpacalyzer.utils.progress import progress

# Initialize logger
logger = get_logger(__name__)

# Load environment variables from .env file
load_dotenv()

init(autoreset=True)


def parse_hedge_fund_response(response):
    """Parses a JSON string and returns a dictionary."""
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.debug(f"JSON decoding error: {e}\nResponse: {repr(response)}")
        return None
    except TypeError as e:
        logger.debug(f"Invalid response type (expected string, got {type(response).__name__}): {e}")
        return None
    except Exception as e:
        logger.debug(f"Unexpected error while parsing response: {e}\nResponse: {repr(response)}")
        return None


##### Run the Hedge Fund #####


def call_hedge_fund_agents(
    tickers: list[TopTicker],
    agents: Literal["ALL", "TRADE", "INVEST"] = "ALL",
    show_reasoning: bool = False,
):
    # Start progress tracking
    selected_analysts = None
    progress.start()

    try:
        # Select analysts based on the provided agents parameter
        if agents not in ["ALL", "TRADE", "INVEST"]:
            raise ValueError(f"Invalid agents parameter: {agents}. Must be one of 'ALL', 'TRADE', or 'INVEST'.")
        if agents == "ALL":
            selected_analysts = None
        if agents == "TRADE":
            selected_analysts = [
                # "web_agent",
                "technical_analyst",
                "sentiment_agent",
                "quant_agent",
            ]
        if agents == "INVEST":
            selected_analysts = [
                "fundamental_analyst",
                "ben_graham",
                "bill_ackman",
                "cathie_wood",
                "charlie_munger",
                "warren_buffett",
            ]
        # Create a new workflow
        workflow = create_workflow(selected_analysts=selected_analysts)
        agent = workflow.compile()

        potential_candidates = {}
        for ticker in tickers:
            potential_candidates[ticker.ticker] = {
                "signal": ticker.signal,
                "confidence": ticker.confidence,
                "reasoning": ticker.reasoning,
            }

        final_state = agent.invoke(
            {
                "messages": [
                    HumanMessage(
                        content="Make trading decisions based on the provided data.",
                    )
                ],
                "data": {
                    "tickers": [x.ticker for x in tickers],
                    "end_date": datetime.now(UTC).isoformat(),
                    "start_date": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
                    "analyst_signals": {"potential_candidates_agent": potential_candidates},
                    "portfolio": {},
                },
                "metadata": {
                    "show_reasoning": show_reasoning,
                },
            },
        )

        return {
            "decisions": parse_hedge_fund_response(final_state["messages"][-1].content),
            "analyst_signals": final_state["data"]["analyst_signals"],
        }
    finally:
        # Stop progress tracking
        progress.stop()


def start(state: AgentState):
    """Initialize the workflow with the input message."""
    return state


def create_workflow(selected_analysts=None):
    """Create the workflow with selected analysts."""
    workflow = StateGraph(AgentState)
    workflow.add_node("start_node", start)

    # Get analyst nodes from the configuration
    analyst_nodes = get_analyst_nodes()

    # Default to all analysts if none selected
    if selected_analysts is None:
        selected_analysts = list(analyst_nodes.keys())
    # Add selected analyst nodes
    for analyst_key in selected_analysts:
        node_name, node_func = analyst_nodes[analyst_key]
        workflow.add_node(node_name, node_func)
        workflow.add_edge("start_node", node_name)

    # Always add risk-, portfolio management and trading strategist agents
    workflow.add_node("risk_management_agent", risk_management_agent)
    workflow.add_node("portfolio_management_agent", portfolio_management_agent)
    workflow.add_node("trading_strategist_agent", trading_strategist_agent)

    # Connect selected analysts to risk management
    for analyst_key in selected_analysts:
        node_name = analyst_nodes[analyst_key][0]
        workflow.add_edge(node_name, "risk_management_agent")

    workflow.add_edge("risk_management_agent", "portfolio_management_agent")
    workflow.add_edge("portfolio_management_agent", "trading_strategist_agent")
    workflow.add_edge("trading_strategist_agent", END)

    workflow.set_entry_point("start_node")
    return workflow
