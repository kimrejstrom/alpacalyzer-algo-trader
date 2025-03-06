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

    def _fetch_data(self, ticker_symbol: str, period: str = "1d"):
        """
        Fetch historical data for a given ticker, with rate-limit handling.

        Args:
            ticker_symbol (str): The stock ticker symbol (e.g., "^VIX").
            period (str): The time period to fetch (default is "1d").

        Returns:
            pd.DataFrame: The historical data for the given ticker.
        """
        for attempt in range(self.max_retries):
            try:
                ticker = yf.Ticker(ticker_symbol, session=self.session)
                data = ticker.history(period=period)
                if data.empty:
                    logger.warning(f"No data found for {ticker_symbol}.")
                return data
            except YFRateLimitError:
                logger.warning(
                    f"Rate limited. Retrying in {self.retry_wait} seconds... (Attempt {attempt + 1}/{self.max_retries})"
                )
                time.sleep(self.retry_wait)
            except Exception as e:
                logger.error(f"Failed to fetch data for {ticker_symbol}: {e}")
                break

        logger.error(f"Failed to retrieve data for {ticker_symbol} after {self.max_retries} attempts.")
        return None

    @timed_lru_cache(seconds=3600, maxsize=128)
    def get_vix(self, period: str = "1d"):
        """
        Fetch the latest historical data for the VIX volatility index.

        Args:
            period (str): The time period to fetch (default is "1d").

        Returns:
            pd.DataFrame: The historical VIX data.
        """
        vix_data = self._fetch_data("^VIX", period=period)
        if vix_data is None or vix_data.empty:
            logger.warning("VIX data is empty.")
            return 25.0
        return vix_data["Close"].iloc[-1]
