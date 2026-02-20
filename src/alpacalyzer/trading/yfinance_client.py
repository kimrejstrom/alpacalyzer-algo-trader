import pandas as pd
import yfinance as yf

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


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
            logger.warning("VIX ticker retrieval failed")
            return 25.0

        try:
            vix_data = ticker.history(period=period)
            if vix_data.empty:
                logger.warning("VIX data empty")
                return 25.0
            return vix_data["Close"].iloc[-1]
        except Exception as e:
            logger.error(f"VIX history retrieval failed | error={e}")
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
            logger.warning(f"ticker retrieval failed | ticker={ticker_symbol}")
            return []

        try:
            news = ticker.news
            if not news:
                logger.warning(f"no news found | ticker={ticker_symbol}")
                return []

            # Limit the number of articles returned
            return news[:limit]
        except Exception as e:
            logger.error(f"news retrieval failed | ticker={ticker_symbol} error={e}")
            return []

    @timed_lru_cache(seconds=1800, maxsize=128)
    def get_intraday_data(self, ticker_symbol: str, period: str = "1d", interval: str = "1m"):
        """
        Fetch intraday historical data for a given ticker.

        Args:
            ticker_symbol (str): The stock ticker symbol (e.g., "AAPL").
            period (str): The time period to fetch (default is "1d").
            interval (str): The data interval
            (e.g., "1m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo").

        Returns:
            pd.DataFrame: A pandas DataFrame containing the intraday data, or an empty DataFrame if an error occurs.
        """
        ticker = yf.Ticker(ticker_symbol)
        if ticker is None:
            logger.warning(f"ticker retrieval failed | ticker={ticker_symbol}")
            return pd.DataFrame()

        try:
            data = ticker.history(period=period, interval=interval)
            if data.empty:
                logger.warning(f"no intraday data found | ticker={ticker_symbol} period={period} interval={interval}")
            return data
        except Exception as e:
            logger.error(f"intraday data retrieval failed | ticker={ticker_symbol} error={e}")
            return pd.DataFrame()
