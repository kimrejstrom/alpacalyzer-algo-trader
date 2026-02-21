from pandas import DataFrame

from alpacalyzer.data.models import TopTicker, TopTickersResponse
from alpacalyzer.llm import LLMTier, get_llm_client
from alpacalyzer.prompts import load_prompt
from alpacalyzer.scanners.reddit_scanner import fetch_reddit_posts, fetch_user_posts
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


def get_reddit_insights() -> TopTickersResponse | None:
    system_message = {
        "role": "system",
        "content": load_prompt("opportunity_finder_reddit"),
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

    client = get_llm_client()
    return client.complete_structured(messages, TopTickersResponse, tier=LLMTier.FAST, caller="opportunity_finder_reddit")


def format_top_tickers(tickers: list[TopTicker]) -> str:
    """Format list of TopTicker objects into a readable string for API consumption."""
    formatted = [f"Symbol: {ticker.ticker}\nSignal: {ticker.signal}\nConfidence: {ticker.confidence}%\nReasoning: {ticker.reasoning}\n" for ticker in tickers]
    return "\n".join(formatted)


def get_top_candidates(top_tickers: list[TopTicker], finviz_df: DataFrame) -> TopTickersResponse | None:
    system_message = {
        "role": "system",
        "content": load_prompt("opportunity_finder_candidates"),
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
    client = get_llm_client()
    return client.complete_structured(messages, TopTickersResponse, tier=LLMTier.FAST, caller="opportunity_finder_candidates")
