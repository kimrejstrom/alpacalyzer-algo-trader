from pandas import DataFrame

from alpacalyzer.data.models import TopTicker, TopTickersResponse
from alpacalyzer.gpt.call_gpt import call_gpt_structured
from alpacalyzer.scanners.reddit_scanner import fetch_reddit_posts, fetch_user_posts
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


def get_reddit_insights() -> TopTickersResponse | None:
    system_message = {
        "role": "system",
        "content": """
        You are a Swing trader expert analyst, an AI that analyzes trading data to identify top opportunities.
        Your goal is to provide a list of the top 5 swing trade tickers
        based on the latest market insights from select reddit posts.
        Focus on high-potential stocks with strong momentum and technical setups or great short-selling opportunities.

        ## **Expected Output**
        - List **3-5 great tickers** that meet the above conditions.
        - Provide a **short reasoning** for each selection, including a Short/Long bias.
        - Also include the main reason you chose this stock based on the reddit posts you receive.
        - Give a confidence score on a scale from 0-100 for each ticker.
        """,
    }

    human_template = """Analyze current and relevant insights from reddit.

        Here are the relevant reddit posts for consideration:

        {ideas}

        "Return the trading signal in this JSON format:"
            {{
              "signal": "bullish/bearish/neutral",
              "confidence": float (0-100),
              "reasoning": "string"
            }}
        """

    trading_edge_ideas = fetch_reddit_posts("TradingEdge")
    winning_watch_list_ideas = fetch_user_posts("WinningWatchlist")
    combined_ideas = trading_edge_ideas + winning_watch_list_ideas
    formatted_reddit_ideas = "\n\n".join([f"Title: {post['title']}\nBody: {post['body']}" for post in combined_ideas])
    logger.debug(f"Reddit insights input: {formatted_reddit_ideas}")

    human_message = {
        "role": "user",
        "content": human_template.format(
            ideas=formatted_reddit_ideas,
        ),
    }

    # Combine the messages into a list that you can send to your API
    messages = [system_message, human_message]

    top_tickers_response = call_gpt_structured(messages, TopTickersResponse)
    logger.debug(f"Reddit insights output: {top_tickers_response}")
    return top_tickers_response


def format_top_tickers(tickers: list[TopTicker]) -> str:
    """Format list of TopTicker objects into a readable string for API consumption."""
    formatted = [f"Symbol: {ticker.ticker}\nSignal: {ticker.signal}\nConfidence: {ticker.confidence}\nReasoning: {ticker.reasoning}\n" for ticker in tickers]
    return "\n".join(formatted)


def get_top_candidates(top_tickers: list[TopTicker], finviz_df: DataFrame) -> TopTickersResponse | None:
    system_message = {
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
        - **Unusual Premarket Volume:** At least **1M shares traded in premarket**. Compare this with the stock's
        **daily highest volume**.
        - **Mark Key Levels:**
        - **Premarket High:** Serves as a **breakout trigger**.
        - **Consolidation Bottom:** Serves as **support/stop-loss consideration**.

        ## **Expected Output**
        - List **3-5 great tickers** that meet the above conditions.
        - Provide a **short recommendation** for each selection, including a Short/Long bias.
        - Give a confidence score on a scale from 0-100 for each ticker.
        """,
    }

    human_template = """Analyze the following stocks for swing trading opportunities.

        Top candidates:
        {top_candidates}

        "Stock data: {stock_data}"

        "Return the trading signal in this JSON format:"
            {{
              "signal": "bullish/bearish/neutral",
              "confidence": float (0-100),
              "reasoning": "string"
            }}
        """

    formatted_finviz_data = finviz_df.to_json(orient="records")
    formatted_top_tickers = format_top_tickers(top_tickers)

    human_message = {
        "role": "user",
        "content": human_template.format(top_candidates=formatted_top_tickers, stock_data=formatted_finviz_data),
    }

    messages = [system_message, human_message]
    top_tickers_response = call_gpt_structured(messages, TopTickersResponse)
    logger.debug(f"Top candidates output: {top_tickers_response}")
    return top_tickers_response
