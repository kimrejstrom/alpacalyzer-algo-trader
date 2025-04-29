import time

import requests
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import logger


class YFinanceClient:
    """
    A reusable client for fetching data from Yahoo Finance with built-in.

    rate limit handling and retry logic.
    """

    def __init__(self, max_retries=2, retry_wait=5):
        """
        Initialize the YFinanceClient with a session to reduce request overhead.

        Args:
            max_retries (int): Number of times to retry after hitting a rate limit.
            retry_wait (int): Wait time (in seconds) before retrying a failed request.
        """
        self.session = requests.Session()
        self.max_retries = max_retries
        self.retry_wait = retry_wait

    def _yf_ticker(self, ticker_symbol: str):
        """
        Fetch a YFinance Ticker object with rate-limit handling.

        Args:
            ticker_symbol (str): The stock ticker symbol (e.g., "^VIX").

        Returns:
            yf.Ticker: The YFinance Ticker object.
        """
        for attempt in range(self.max_retries):
            try:
                return yf.Ticker(ticker_symbol, session=self.session)
            except YFRateLimitError:
                logger.warning(
                    f"Rate limited. Retrying in {self.retry_wait} seconds... (Attempt {attempt + 1}/{self.max_retries})"
                )
                time.sleep(self.retry_wait)
            except Exception as e:
                logger.error(f"Failed to fetch ticker for {ticker_symbol}: {e}")
                break

        logger.error(f"Failed to retrieve ticker for {ticker_symbol} after {self.max_retries} attempts.")
        return None

    @timed_lru_cache(seconds=3600, maxsize=128)
    def get_vix(self, period: str = "1d"):
        """
        Fetch the latest historical data for the VIX volatility index.

        Args:
            period (str): The time period to fetch (default is "1d").

        Returns:
            float: The latest VIX closing value or default value of 25.0 if unavailable.
        """
        ticker = self._yf_ticker("^VIX")
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
        ticker = self._yf_ticker(ticker_symbol)
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
