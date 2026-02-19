import json
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.llm import LLMTier, get_llm_client
from alpacalyzer.prompts import load_prompt
from alpacalyzer.utils.candles_formatter import format_candles_to_markdown
from alpacalyzer.utils.progress import progress


class QuantSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


##### Quant Agent #####
def quant_agent(state: AgentState):
    """Quantitative analysis for selected tickers"""

    # Get the tickers
    data = state["data"]
    tickers = data["tickers"]

    quant_analysis = {}

    technical_analyzer = TechnicalAnalyzer()

    # Get position limits, current prices, and signals for every ticker
    for ticker in tickers:
        progress.update_status("quant_agent", ticker, "Analyzing quantitative signals")

        signals = technical_analyzer.analyze_stock(ticker)
        if signals is None:
            progress.update_status("quant_agent", ticker, "Failed to generate quantitative analysis")
            progress.update_status("quant_agent", ticker, "Done")
            quant_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "Quantitative analysis failed or returned no data",
            }
            continue

        quant_output = get_quant_analysis(signals)

        if quant_output is None:
            progress.update_status("quant_agent", ticker, "Failed to generate quantitative analysis")
            quant_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "Quantitative analysis failed or returned no data",
            }
            continue

        quant_analysis[ticker] = {
            "signal": quant_output.signal,
            "confidence": quant_output.confidence,
            "reasoning": quant_output.reasoning,
        }

        progress.update_status("quant_agent", ticker, "Done")

    # Create the quant agent message
    message = HumanMessage(
        content=json.dumps(quant_analysis),
        name="quant_agent",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(quant_analysis, "Quant Agent")

    # Add signals to the overall state
    state["data"]["analyst_signals"]["quant_agent"] = quant_analysis

    return {"messages": [message], "data": state["data"]}


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


def get_quant_analysis(
    trading_signals: TradingSignals,
) -> QuantSignal | None:
    """Generate trading strategies based on the given signals and recommendations."""
    system_message = {
        "role": "system",
        "content": load_prompt("quant_agent"),
    }

    human_template = (
        "Based on the provided data, give a recommendation for the ticker.\n\n"
        "Here are the signals for the ticker:\n{signals}\n\n"
        "Candlestick Data (3 months):\n{candles_3_months}\n\n"
        "Candlestick Data (10 hours):\n{candles_5_min}\n\n"
    )

    signals_str = serialize_trading_signals(trading_signals)
    candles_3_months_str = format_candles_to_markdown(trading_signals["raw_data_daily"], max_rows=90, granularity="day")
    candles_5_min_str = format_candles_to_markdown(trading_signals["raw_data_intraday"], max_rows=120, granularity="minute")

    human_message = {
        "role": "user",
        "content": human_template.format(
            signals=signals_str,
            candles_3_months=candles_3_months_str,
            candles_5_min=candles_5_min_str,
        ),
    }

    # Combine the messages into a list that you can send to your API
    messages = [system_message, human_message]
    client = get_llm_client()
    return client.complete_structured(messages, QuantSignal, tier=LLMTier.DEEP)
