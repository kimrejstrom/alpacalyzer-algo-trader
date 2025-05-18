import yfinance as yf

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import logger


class YFinanceClient:
    """
    A reusable client for fetching data from Yahoo Finance with built-in.

    rate limit handling and retry logic.
    """

    def __init__(self):
        """
        Initialize the YFinanceClient with a session to reduce request overhead.

        Args:
            max_retries (int): Number of times to retry after hitting a rate limit.
            retry_wait (int): Wait time (in seconds) before retrying a failed request.
        """

    @timed_lru_cache(seconds=3600, maxsize=128)
    def get_vix(self, period: str = "1d"):
        """
        Fetch the latest historical data for the VIX volatility index.

        Args:
            period (str): The time period to fetch (default is "1d").

        Returns:
            float: The latest VIX closing value or default value of 25.0 if unavailable.
        """
        ticker = yf.Ticker("^VIX")
        if ticker is None:
            logger.warning("Failed to retrieve VIX ticker.")
            return 25.0

        try:
            vix_data = ticker.history(period=period)
            if vix_data.empty:
                logger.warning("VIX data is empty.")
                return 25.0
            return vix_data["Close"].iloc[-1]
        except Exception as e:
            logger.error(f"Error retrieving VIX history: {e}")
            return 25.0

    @timed_lru_cache(seconds=1800, maxsize=128)
    def get_news(self, ticker_symbol: str, limit: int = 5):
        """
        Fetch the latest news articles for a given ticker.

        Args:
            ticker_symbol (str): The stock ticker symbol (e.g., "AAPL").
            limit (int): Maximum number of news articles to return (default is 5).

        Returns:
            list: A list of news article dictionaries containing title, publisher, link, etc.
        """
        ticker = yf.Ticker(ticker_symbol)
        if ticker is None:
            logger.warning(f"Failed to retrieve ticker for {ticker_symbol}.")
            return []

        try:
            news = ticker.news
            if not news:
                logger.warning(f"No news found for {ticker_symbol}.")
                return []

            # Limit the number of articles returned
            return news[:limit]
        except Exception as e:
            logger.error(f"Error retrieving news for {ticker_symbol}: {e}")
            return []
