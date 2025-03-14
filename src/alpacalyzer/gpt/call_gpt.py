import json
import os
from typing import TypeVar, cast

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from pandas import DataFrame

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.gpt.response_models import TopTickersResponse, TradingStrategyResponse
from alpacalyzer.scanners.reddit_scanner import fetch_reddit_posts, fetch_user_posts
from alpacalyzer.utils.logger import logger

T = TypeVar("T")

load_dotenv()
client = OpenAI()
api_key = os.getenv("OPENAI_API_KEY")
if api_key is None:
    raise ValueError("Missing OpenAI API Key")
client.api_key = api_key


def dataframe_to_compact_csv(df: pd.DataFrame, max_rows: int) -> str:
    """Convert DataFrame to a compact CSV format with rounding and row limits."""

    # Keep only the most recent `max_rows`
    df = df.tail(max_rows)

    # Rename "symbol" to "ticker" if present
    if "symbol" in df.columns:
        df = df.rename(columns={"symbol": "ticker"})

    # Round all float values to 3 decimal places
    df = df.map(lambda x: round(x, 3) if isinstance(x, float) else x)

    # Convert timestamp columns to string (ISO format)
    if "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].astype(str)

    csv = df.to_csv(index=False)
    return cast(str, csv)
    # return df.to_csv(index=False)


def serialize_trading_signals(signals: TradingSignals, recommendations: list[str]) -> str:
    """Convert TradingSignals object into a JSON-compatible format with CSV data."""

    json_ready_signals = {
        "ticker": signals["symbol"],  # Rename at the top level
        "current_price": signals["price"],
        "ta_score_from_0_to_1": signals["score"],
        "atr": signals["atr"],
        "rvol": signals["rvol"],
        "momentum": signals["momentum"],
        # TODO: trim to open, close, volume, high, low and format dates
        "3_months_daily_candles_csv": dataframe_to_compact_csv(
            signals["raw_data_daily"], max_rows=90
        ),  # Daily candles 3 months
        # TODO: trim to open, close, volume, high, low and format dates
        "10_hours_5min_candles_csv": dataframe_to_compact_csv(
            signals["raw_data_intraday"], max_rows=120
        ),  # 5-min candles 10 hours
        "recommendations": recommendations,
    }

    return json.dumps(json_ready_signals)  # Convert to JSON string


def call_gpt_structured(messages, function_schema: type[T]) -> T | None:
    response = client.beta.chat.completions.parse(
        model="o3-mini",
        reasoning_effort="medium",
        messages=messages,
        response_format=function_schema,
    )
    return cast(T, response.choices[0].message.parsed)


def get_reddit_insights() -> TopTickersResponse | None:
    messages = [
        {
            "role": "system",
            "content": """
You are a Swing trader expert analyst, an AI that analyzes trading data to identify top opportunities.
Your goal is to provide a list of the top 5 swing trade tickers
based on the latest market insights from select reddit posts.
Focus on high-potential stocks with strong momentum and technical setups or great short-selling opportunities.
""",
        },
        {
            "role": "user",
            "content": "Analyze current and relevant insights from reddit",
        },
    ]
    trading_edge_ideas = fetch_reddit_posts("TradingEdge")
    winning_watch_list_ideas = fetch_user_posts("WinningWatchlist")
    combined_ideas = trading_edge_ideas + winning_watch_list_ideas
    formatted_reddit_ideas = "\n\n".join([f"Title: {post['title']}\nBody: {post['body']}" for post in combined_ideas])
    logger.debug(f"Reddit insights input: {formatted_reddit_ideas}")
    messages.append(
        {
            "role": "user",
            "content": formatted_reddit_ideas,
        }
    )
    top_tickers_response = call_gpt_structured(messages, TopTickersResponse)
    logger.debug(f"Reddit insights output: {top_tickers_response}")
    return top_tickers_response


def get_top_candidates(finviz_df: DataFrame) -> TopTickersResponse | None:
    messages = [
        {
            "role": "system",
            "content": """
You are Momentum Market Analyst GPT, an AI specialized in spotting swing trading opportunities
before they become mainstream.

## **Role & Expertise**
1. You analyze tickers using technical analysis, volume-based momentum, and risk management best practices.
2. You leverage **technical data** (price action, volume, relative volume, short interest, etc.)
to identify high-upside, early-stage plays.
3. Your primary goal is to **identify three tickers** (1, 2, 3) with a concise rationale for each.

## **Key Objectives**
- Assess **momentum** by analyzing **relative volume (RVOL), ATR, performance, RSI etc**.
- Maintain **disciplined risk management**, considering **position sizing, stop-loss placement,
and risk/reward assessment**.

## **Trading Principles & Rules**
- **No Gap-Ups:** Avoid chasing stocks that have significantly gapped overnight.
- **Low Market Cap, High Volume:** Prioritize **liquid stocks under $50** with notable volume surges.
- **Avoid Holding Overnight News Plays:** If **news causes a large gap**, treat it **strictly**
as an **intraday scalp** or **skip entirely**.
- **High Short Interest = Bonus:** If volume increases, potential for a **short squeeze** exists.

## **Premarket & Intraday Checklist**
- **Unusual Premarket Volume:** At least **1M shares traded in premarket**. Compare this with the stock’s
**daily highest volume**.
- **Mark Key Levels:**
  - **Premarket High:** Serves as a **breakout trigger**.
  - **Consolidation Bottom:** Serves as **support/stop-loss consideration**.

## **Expected Output**
- List **exactly 3 tickers** (1, 2, 3) that meet the above conditions.
- Provide a **short rationale** for each selection.
""",
        },
        {
            "role": "user",
            "content": "Analyze the following stocks for swing trading opportunities:",
        },
    ]
    formatted_finviz_data = finviz_df.to_json(orient="records")
    logger.debug(f"Top candidates input: {formatted_finviz_data}")
    logger.debug(formatted_finviz_data)
    messages.append(
        {
            "role": "user",
            "content": formatted_finviz_data,
        }
    )
    top_tickers_response = call_gpt_structured(messages, TopTickersResponse)
    logger.debug(f"Top candidates output: {top_tickers_response}")
    return top_tickers_response


def get_trading_strategies(ticker_data: TradingSignals, recommendations: list[str]) -> TradingStrategyResponse | None:
    messages = [
        {
            "role": "system",
            "content": """
You are Chart Pattern Analyst GPT, a financial analysis expert specializing in candlestick chart interpretation and
swing trading strategies.

## Role & Expertise
- Your goal is to analyze candlestick data, identify notable patterns, highlight support/resistance levels, and propose
potential swing trading scenarios with an emphasis on risk management.
- You apply technical analysis (candlesticks, trendlines, support/resistance, indicators, volume)
and propose exactly one optimal trading strategy for the given ticker.

## Key Objectives
1. Identify & utilize Candlestick Patterns (hammer, shooting star, doji, engulfing, etc.).
1. Note Support & Resistance areas to guide entry/exit levels.
1. Incorporate Technical Indicators (moving averages, RSI, MACD, Bollinger Bands) as needed.
1. Analyze Volume for confirmation or divergence.
1. Use Multi-Timeframe Analysis (data has both intraday 5 min candles as well as 3month daily candles).
1. Suggest Risk Management steps (stop-loss, position sizing, risk/reward).
1. Communicate your analysis in a concise, structured way.
1. Responds with a JSON output that matches the provided schema.

## Reference / Core Principles

### Candlestick Basics
- **Body** (open-close), **Wicks** (high-low), Bullish vs. Bearish.

### Key Candlestick Patterns
- **Single-Candle:** Hammer, Inverted Hammer, Shooting Star, Doji (including Dragonfly), Marubozu, Spinning Top.
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

## **Targets**
1. **Percentage Gain:** Aim for **3%+**.
2. **Risk:Reward:** Target is **1:3**.

## Response Style & Format
- **Concise & Structured:** Provide analysis in short paragraphs or bullet points, covering each key aspect in order
(trend, patterns, support/resistance, indicators, volume, strategy).
- **Actionable Insights:** Suggest potential trading scenarios (long or short) and approximate stop/target zones.
- **Risk-Focused:** Always highlight possible downsides or failure points for each setup.
- **Mandatory JSON Output:** Conclude with a valid JSON object that adheres to the JSON schema.
- **Indicate trade type:** Long or short depending on the setup.
- **Give a clear entry criteria:** Give one condition that must be met for the trade to be valid.
- **Relevant entries:** Input data includes latest price, and candles have the same information,
    make sure your suggestions are relevant with respect to current price.

## TIPS & BEST PRACTICES
1. **Always Keep It Clear & Actionable**
   - Focus on the data (candles, volume, indicators) and connect them to possible trading decisions.
2. **Highlight Both Bullish & Bearish Scenarios**
   - Show where the setup might fail, so the user understands downside risks.
3. **Stay Consistent**
   - Use the same structure for each ticker, making it easy for users to compare.
4. **No “Sure Bets”**
   - Remain objective, acknowledging that any trade has risk.
""",
        },
        {
            "role": "user",
            "content": f"Analyze the candle stick data and indicators of the stock and generate trading strategies for {ticker_data['symbol']}, make sure to use up to date price data."  # noqa: E501
            f"",
        },
    ]
    formatted_ticker_data = serialize_trading_signals(ticker_data, recommendations)
    logger.debug(f"Trading strategies input: {formatted_ticker_data}")
    messages.append(
        {
            "role": "user",
            "content": formatted_ticker_data,
        }
    )
    response = call_gpt_structured(messages, TradingStrategyResponse)
    logger.debug(f"Trading strategies output: {response}")
    return response
