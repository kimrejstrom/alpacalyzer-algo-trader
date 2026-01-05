import numpy as np
import pandas as pd
import requests

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


class StocktwitsScanner:
    def __init__(self):
        self.headers = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")}

    def get_trending_stocks(self):
        """Get trending stocks from Stocktwits."""
        try:
            url = "https://api.stocktwits.com/api/2/trending/symbols.json"
            response = requests.get(url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                return pd.DataFrame()

            try:
                data = response.json()
                symbols = data.get("symbols", [])

                # Convert to DataFrame
                df = pd.DataFrame(symbols)
                if df.empty:
                    return df

                # Rename columns
                df = df.rename(columns={"symbol": "ticker"})

                # Filter to only stocks
                return df[df["instrument_class"] == "Stock"]

            except Exception as e:
                logger.error(f"Error parsing Stocktwits data: {str(e)}", exc_info=True)
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching trending stocks: {str(e)}", exc_info=True)
            return pd.DataFrame()

    # Get sentiment from messages
    @timed_lru_cache(seconds=60, maxsize=128)
    def get_message_sentiment(self, ticker):
        """Fetch sentiment and mentions from Stocktwits API for a given ticker."""
        try:
            messages_url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
            response = requests.get(messages_url, headers=self.headers, timeout=15)
            if response.status_code == 200:
                data = response.json()

                # Extract mentions
                mentions = data.get("symbol", {}).get("watchlist_count", 0)

                # Extract sentiment from messages
                messages = data.get("messages", [])
                if messages:
                    bullish = 0
                    bearish = 0
                    total = 0

                    for message in messages[:100]:
                        if "entities" in message:
                            sentiment = message["entities"].get("sentiment", {})
                            if sentiment and "basic" in sentiment:
                                total += 1
                                if sentiment["basic"] == "Bullish":
                                    bullish += 1
                                elif sentiment["basic"] == "Bearish":
                                    bearish += 1

                    # Calculate bullish ratio
                    bullish_ratio = bullish / total if total > 0 else 0.5
                    return bullish_ratio, mentions

            return 0.5, 0
        except Exception as e:
            logger.error(f"Error fetching sentiment for {ticker}: {str(e)}", exc_info=True)
            return 0.5, 0

    def get_stock_ranks(self, df: pd.DataFrame) -> pd.DataFrame:
        if "ticker" not in df:
            logger.warning("DataFrame must contain 'ticker' column")
            return pd.DataFrame()

        # Add bullish ratio and mentions if missing
        results = df["ticker"].apply(self.get_message_sentiment)
        df["bullish_ratio"], df["mentions"] = zip(*results)

        # Filter for minimum watchers and bullish ratio
        # df = df[df["mentions"] >= 1000]
        # df = df[df["bullish_ratio"] > 0.6]

        if df.empty:
            return df

        # Calculate score as log10(watchers) * bullish_ratio
        df["mentions"] = df["mentions"].replace(0, 1e-10)
        df["log_mentions"] = np.log10(df["mentions"])
        df["score"] = df["log_mentions"] * df["bullish_ratio"]

        # Sort by score
        df = df.sort_values("score", ascending=False)
        df["rank"] = range(1, len(df) + 1)

        # Get top N stocks
        return df
