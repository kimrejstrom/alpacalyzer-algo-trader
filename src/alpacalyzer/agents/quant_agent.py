import json
from typing import Literal

import pandas as pd
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.gpt.call_gpt import call_gpt_structured
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
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


def candles_to_csv(df: pd.DataFrame, max_rows: int, granularity: Literal["day", "minute"] = "minute") -> str:
    """Convert a DataFrame of candle data to a compact CSV format with rounding."""

    # Keep only the most recent `max_rows`
    df = df.tail(max_rows)

    # Rename "symbol" to "ticker" if present
    if "symbol" in df.columns:
        df = df.rename(columns={"symbol": "ticker"})

    # Define required columns, include ticker if available
    required_cols = ["timestamp", "open", "high", "low", "close", "volume"]
    if "ticker" in df.columns:
        required_cols.append("ticker")

    # Filter columns (only if they exist)
    df = df[[col for col in required_cols if col in df.columns]]

    # Round all float values to 3 decimal places
    df = df.map(lambda x: round(x, 3) if isinstance(x, float) else x)

    # Adjust timestamp based on granularity
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if granularity == "day":
            # Keep only the date part
            df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d")
        elif granularity == "minute":
            # Keep full ISO format for minute granularity
            df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return str(df.to_csv(index=False))


def serialize_trading_signals(signals: TradingSignals) -> str:
    """Convert TradingSignals object into a JSON-compatible format with CSV data."""

    json_ready_signals = {
        "ticker": signals["symbol"],  # Rename at the top level
        "current_price": signals["price"],
        "technical_analysis_score_from_0_to_1": signals["score"],
        "atr": signals["atr"],
        "rvol": signals["rvol"],
        "momentum": signals["momentum"],
    }

    return json.dumps(json_ready_signals, indent=2)  # Convert to JSON string


def get_quant_analysis(
    trading_signals: TradingSignals,
) -> QuantSignal | None:
    """Generate trading strategies based on the given signals and recommendations."""
    system_message = {
        "role": "system",
        "content": """
        You are Chart Pattern Analyst GPT, a financial analysis expert and trading strategist specializing in
        candlestick chart interpretation and quantitative analysis and technical analysis.

        ## Role & Expertise
        - Your goal is to analyze candlestick data, identify notable patterns, account for support/resistance
        levels, and indicate a bullish, bearish, or neutral signal.
        - You apply technical analysis (candlesticks, trendlines, support/resistance, indicators, volume)
        and propose a confidence level between 0-100 and a concise reasoning for your analysis.

        ## Key Objectives
        1. Identify & utilize Candlestick Patterns (hammer, shooting star, doji, engulfing, etc.).
        1. Note Support & Resistance areas to guide entry/exit levels.
        1. Incorporate Technical Indicators (moving averages, RSI, MACD, Bollinger Bands) as needed.
        1. Analyze Volume for confirmation or divergence.
        1. Use Multi-Timeframe Analysis (data has both intraday 5 min candles as well as 3month daily candles).
        1. Communicate your analysis in a concise, structured way.
        1. Responds with a JSON output that matches the provided schema.

        ## Reference / Core Principles

        ### Candlestick Basics
        - **Body** (open-close), **Wicks** (high-low), Bullish vs. Bearish.

        ### Key Candlestick Patterns
        - **Single-Candle:** Hammer, Inverted Hammer, Shooting Star, Doji (including Dragonfly),
        Marubozu, Spinning Top.
        - **Dual-Candle:** Engulfing (bullish/bearish).
        - **Triple-Candle:** Morning Star / Evening Star.

        ### Trend Analysis
        - **Uptrend:** Higher highs/lows
        - **Downtrend:** Lower highs/lows
        - **Sideways:** Range-bound

        ### Support & Resistance
        - Identify prior swing highs/lows or pivot zones.

        ### Technical Indicators
        - MAs (SMA, EMA), RSI, MACD, Bollinger Bands, etc.

        ### Volume Analysis
        - **High volume** during breakouts = stronger validity.
        - **Divergence** between price and volume can signal reversals.

        ### Multi-Timeframe Approach
        - Start from higher time frames (daily/weekly) for context, then narrow down to lower (1h, 5m).

        ## Response Style & Format
        - **Mandatory JSON Output:** Conclude with a valid JSON object that adheres to the JSON schema.
        - **Relevant entries:** Input data includes latest price, and candles have the same information,
            make sure your suggestions are relevant with respect to current price.

        ## TIPS & BEST PRACTICES
        1. **Always Keep It Clear & Actionable**
        - Focus on the data (candles, volume, indicators) and connect them to possible trading decisions.
        2. **Highlight Both Bullish & Bearish Scenarios**
        - Show where the setup might fail, so the user understands downside risks.
        3. **Stay Consistent**
        - Use the same structure for each ticker, making it easy for users to compare.
        """,
    }

    human_template = (
        "Based on the provided data, give a recommendation for the ticker.\n\n"
        "Here are the signals for the ticker:\n{signals}\n\n"
        "Candlestick Data (3 months):\n{candles_3_months}\n\n"
        "Candlestick Data (10 hours):\n{candles_5_min}\n\n"
    )

    signals_str = serialize_trading_signals(trading_signals)
    candles_3_months_str = candles_to_csv(trading_signals["raw_data_daily"], max_rows=90, granularity="day")
    candles_5_min_str = candles_to_csv(trading_signals["raw_data_intraday"], max_rows=120, granularity="minute")

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

    return call_gpt_structured(messages=messages, function_schema=QuantSignal)
