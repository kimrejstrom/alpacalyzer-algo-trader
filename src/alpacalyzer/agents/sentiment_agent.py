from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage

from alpacalyzer.data.models import SentimentAnalysisResponse
from alpacalyzer.gpt.call_gpt import call_gpt_structured
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.trading.yfinance_client import YFinanceClient
from alpacalyzer.utils.logger import get_logger
from alpacalyzer.utils.progress import progress

logger = get_logger()


##### Technical Analyst #####
def sentiment_agent(state: AgentState):
    """
    Sophisticated sentiment analysis system that evaluates sentiment of most recent news articles and social media posts

    It uses advanced NLP techniques to extract sentiment scores and trends.
    """
    data = state["data"]
    tickers = data["tickers"]

    # Initialize analysis for each ticker
    sentiment_analysis = {}

    # Get Ownership data
    ownership_df = FinvizScanner().get_ownership_stocks(tickers=tickers)

    for ticker in tickers:
        progress.update_status("sentiment_agent", ticker, "Analyzing sentiment of news data")

        # Get news signals
        news = YFinanceClient().get_news(ticker)
        if not news or news is None:
            progress.update_status("sentiment_agent", ticker, "Failed: No news data found")
            # Still create an entry with neutral sentiment when no news is found
            sentiment_analysis[ticker] = {"signal": "neutral", "confidence": 0, "reasoning": "No news data available"}
            continue

        # Get insider ownership signals
        ownership_data = ownership_df.loc[ownership_df["Ticker"] == ticker]

        # Determine insider signals based on transaction shares which is a percentage string
        transaction_shares = ownership_data["Insider Trans"].values[0] if not ownership_data.empty else "0%"
        try:
            transaction_shares_float = float(transaction_shares.strip("%")) / 100
        except ValueError:
            transaction_shares_float = 0.0
        insider_signal = "bearish" if transaction_shares_float < 0 else "bullish"

        logger.debug(f"Insider signals for {ticker}: {insider_signal} {transaction_shares}")

        progress.update_status("sentiment_agent", ticker, "Calculating sentiment signals")

        news_items = [
            {
                "title": item["content"]["title"],
                "summary": item["content"]["summary"],
                "description": item["content"]["description"],
                "pubDate": item["content"]["pubDate"],
            }
            for item in news
        ]
        sentiment_signals = calculate_sentiment_signals(news_items)

        if sentiment_signals is None or len(sentiment_signals.sentiment_analysis) == 0:
            progress.update_status("sentiment_agent", ticker, "Failed: No sentiment data found")
            # Still create an entry with neutral sentiment when no sentiment data
            sentiment_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "Sentiment analysis failed or returned no data",
            }
            continue

        logger.debug(f"Sentiment signals for {ticker}: {sentiment_signals}")

        # Calculate weighted signal counts
        insider_weight = 0.3
        news_weight = 0.7

        # Simplified bullish/bearish signal calculations
        insider_bullish = insider_weight if insider_signal == "bullish" else 0
        insider_bearish = insider_weight if insider_signal == "bearish" else 0

        news_bullish = news_weight * sum(entry.sentiment == "Bullish" for entry in sentiment_signals.sentiment_analysis)
        news_bearish = news_weight * sum(entry.sentiment == "Bearish" for entry in sentiment_signals.sentiment_analysis)

        bullish_signals = insider_bullish + news_bullish
        bearish_signals = insider_bearish + news_bearish

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        # Calculate confidence level based on the weighted proportion
        total_weighted_signals = 1 * insider_weight + len(sentiment_signals.sentiment_analysis) * news_weight
        confidence: float = 0  # Default confidence when there are no signals
        if total_weighted_signals > 0:
            confidence = round(max(bullish_signals, bearish_signals) / total_weighted_signals, 2) * 100
        reasoning = f"Weighted Bullish signals: {bullish_signals:.1f}, Weighted Bearish signals: {bearish_signals:.1f}"

        sentiment_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "reasoning": reasoning,
        }

        progress.update_status("sentiment_agent", ticker, "Done")

    # Create the technical analyst message
    message = HumanMessage(
        content=json.dumps(sentiment_analysis),
        name="sentiment_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(sentiment_analysis, "Sentiment Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["sentiment_agent"] = sentiment_analysis

    return {
        "messages": list(state["messages"]) + [message],
        "data": data,
    }


def calculate_sentiment_signals(news_items: list[dict[str, Any]]) -> SentimentAnalysisResponse | None:
    system_message = {
        "role": "system",
        "content": """
        You are Sentinel, an expert-level financial-news sentiment analyzer.
        Your job is to read any given financial news article and classify its overall tone as Bullish, Bearish
        or Neutral, providing both a concise label and a supporting rationale.

        Formatting Requirements
        Every response must be valid JSON with exactly these top-level keys:
            1.	"sentiment" – one of "Bullish", "Bearish", or "Neutral".
            2.	"score" – a floating-point number in [–1.0, +1.0], where +1.0 is extremely bullish,
            –1.0 is extremely bearish, and 0.0 is neutral.
            3.	"highlights" – an array of up to five excerpted phrases or sentences
            from the text that drove your classification.
            4.	"rationale" – a 1–2-sentence human-readable summary explaining why you chose that label and score.

        Analysis Guidelines
            •	Look for forward-looking language (e.g. “expects,” “will,” “forecast”)
            and judge the direction of the prediction (up or down).
            •	Watch for valuation cues: “undervalued,” “overheated,” “correction,” “record highs,” etc.
            •	Capture sentiment toward key entities: companies, sectors, indices, commodities.
            •	Treat balanced coverage of positives and negatives as Neutral (score near 0.0).
            •	Extreme language (“skyrockets,” “plunges,” “crippled”) should push score toward –1.0 or +1.0.

        Edge Cases
            •	If the article is purely factual or descriptive (e.g. earnings release with no commentary),
            label Neutral with "score": 0.0.
            •	If conflicting signals are equally strong, average them: e.g. two bullish statements
            and two bearish statements → a "score" near 0.0.
            •	For very short articles (<50 words), still extract highlights but allow up to three.
        """,
    }

    # Define a template for the user (human) message
    human_template = "Here are the news items:\n{news_items}\n\n"

    # Prepare dynamic input values (assumes these variables are defined)
    news_items_str = json.dumps(news_items, indent=2)

    # Format the human message using the template
    human_message = {
        "role": "user",
        "content": human_template.format(
            news_items=news_items_str,
        ),
    }

    # Combine the messages into a list that you can send to your API
    messages = [system_message, human_message]

    return call_gpt_structured(messages=messages, function_schema=SentimentAnalysisResponse)
