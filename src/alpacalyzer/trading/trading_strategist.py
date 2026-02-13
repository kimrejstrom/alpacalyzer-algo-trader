import json

from langchain_core.messages import HumanMessage

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.data.models import PortfolioDecision, TradingStrategyResponse
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.llm import LLMTier, get_llm_client
from alpacalyzer.prompts import load_prompt
from alpacalyzer.utils.candles_formatter import format_candles_to_markdown
from alpacalyzer.utils.progress import progress


##### Trading Strategist Agent #####
def trading_strategist_agent(state: AgentState):
    """Makes trading strategies and entry criterias for selected tickers"""

    # Get the analyst signals
    analyst_signals = state["data"]["analyst_signals"]
    data = analyst_signals["portfolio_management_agent"]

    technical_analyzer = TechnicalAnalyzer()
    # Initialize analysis for each ticker
    trading_strategies: dict[str, TradingStrategyResponse] = {}

    progress.update_status("trading_strategist_agent", None, "Analyzing portoflio manager output")

    # Get position limits, current prices, and signals for every ticker
    for ticker, details in data.items():
        progress.update_status("trading_strategist_agent", ticker, "Processing ticker signals")
        decision = PortfolioDecision.model_validate(details)

        if decision.action == "hold":
            progress.update_status("trading_strategist_agent", ticker, "Hold signal, skipping")
            continue

        signals = technical_analyzer.analyze_stock(decision.ticker)
        if signals is None:
            continue

        progress.update_status("trading_strategist_agent", decision.ticker, "Generating trading strategy")
        trading_strategies_response = get_trading_strategies(signals, decision)

        if trading_strategies_response is None:
            progress.update_status("trading_strategist_agent", decision.ticker, "Failed to generate trading strategy")
            continue

        trading_strategies[decision.ticker] = trading_strategies_response
        progress.update_status("trading_strategist_agent", decision.ticker, "Done")

    # Create the portfolio management message
    message = HumanMessage(
        content=json.dumps({ticker: strategy.model_dump() for ticker, strategy in trading_strategies.items()}),
        name="trading_strategist_agent",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(
            {ticker: strategy.model_dump() for ticker, strategy in trading_strategies.items()},
            "Trading Strategist Agent",
        )

    progress.update_status("trading_strategist_agent", None, "Done")

    return {
        "messages": list(state["messages"]) + [message],
        "data": state["data"],
    }



def serialize_trading_signals(signals: TradingSignals) -> str:
    """Convert TradingSignals object into a JSON-compatible format with explicit units."""

    json_ready_signals = {
        "ticker": signals["symbol"],
        "current_price": f"${signals['price']:.2f}",
        "technical_analysis_score_from_0_to_1": f"{signals['score']:.2f}/1.00 ({signals['score'] * 100:.1f}%)",
        "atr": f"${signals['atr']:.2f}",
        "rvol": f"{signals['rvol']:.2f}x",
        "momentum": f"{signals['momentum']:.2f}%",
    }

    return json.dumps(json_ready_signals, indent=2)


def get_trading_strategies(trading_signals: TradingSignals, decision: PortfolioDecision) -> TradingStrategyResponse | None:
    """Generate trading strategies based on the given signals and recommendations."""
    system_message = {
        "role": "system",
        "content": load_prompt("trading_strategist"),
    }

    human_template = (
        "Based on the provided data, make an optimal trading strategy for the ticker.\n\n"
        "Here are the signals for the ticker:\n{signals}\n\n"
        "Here is the decision from the Portfolio Manager:\n{decision}\n\n"
        "Candlestick Data (3 months):\n{candles_3_months}\n\n"
        "Candlestick Data (10 hours):\n{candles_5_min}\n\n"
    )

    signals_str = serialize_trading_signals(trading_signals)
    decision_str = json.dumps(decision.model_dump(), indent=2)
    candles_3_months_str = format_candles_to_markdown(trading_signals["raw_data_daily"], max_rows=90, granularity="day")
    candles_5_min_str = format_candles_to_markdown(trading_signals["raw_data_intraday"], max_rows=120, granularity="minute")

    human_message = {
        "role": "user",
        "content": human_template.format(
            signals=signals_str,
            decision=decision_str,
            candles_3_months=candles_3_months_str,
            candles_5_min=candles_5_min_str,
        ),
    }

    # Combine the messages into a list that you can send to your API
    messages = [system_message, human_message]

    client = get_llm_client()
    return client.complete_structured(messages, TradingStrategyResponse, tier=LLMTier.DEEP)
