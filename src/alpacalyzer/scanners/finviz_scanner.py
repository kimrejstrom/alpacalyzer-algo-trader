import pandas as pd
from finviz.screener import Screener

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


class FinvizScanner:
    def __init__(self):
        """Initializes the FinvizScanner class with filters for the custom screener."""
        # Filters based on the provided URL
        self.filters = [
            "geo_usa",  # U.S.-based stocks
            "ind_stocksonly",  # Stocks only (no ETFs, etc.)
            "sh_curvol_o100000",  # Current volume over 100,000
            "sh_price_u50",  # Price under $50
            "sh_relvol_o1.5",  # Relative volume over 1.5
        ]
        # Specify table as "Custom"
        self.table = "Custom"
        # Define custom columns from your URL settings
        self.columns = [
            "1",
            "4",
            "6",
            "30",
            "42",
            "43",
            "48",
            "49",
            "50",
            "52",
            "53",
            "56",
            "59",
            "60",
            "61",
            "64",
            "67",
            "86",
            "65",
            "66",
        ]

    def get_trending_stocks(self, limit=20):
        """
        Fetches stocks from the custom Finviz screener.

        Returns a DataFrame with relevant data.
        """
        try:
            # Initialize the screener
            stock_list = Screener(
                filters=self.filters,
                table=self.table,
                custom=self.columns,
                order="-relativevolume",
                rows=limit,
            )
            return pd.DataFrame(stock_list.data)

        except Exception as e:
            logger.error(f"Error fetching data from Finviz: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def get_ownership_stocks(self, tickers: tuple[str, ...]) -> pd.DataFrame:
        """
        Fetches stocks from the custom Finviz screener.

        Returns a DataFrame with relevant data.
        """
        try:
            # Initialize the screener
            stock_list = Screener(
                tickers=list(tickers),
                table="Ownership",
            )
            return pd.DataFrame(stock_list.data)

        except Exception as e:
            logger.error(f"Error fetching data from Finviz: {str(e)}", exc_info=True)
            return pd.DataFrame()

    @timed_lru_cache(seconds=60, maxsize=128)
    def fetch_stock_data(self, tickers: tuple[str, ...]) -> pd.DataFrame:
        """
        Fetches stocks from the custom Finviz screener.

        Returns a DataFrame with relevant data.
        """
        try:
            # Initialize the screener
            stock_list = Screener(
                tickers=list(tickers),
                table=self.table,
                custom=self.columns,
                order="-relativevolume",
            )
            return pd.DataFrame(stock_list.data)

        except Exception as e:
            logger.error(f"Error fetching data from Finviz: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def get_stock_ranks(self, df: pd.DataFrame):
        """
        Get stock ranks based on the Finviz data.

        Returns a DataFrame with columns: ticker, mentions, rank
        """

        stocks_df = self.fetch_stock_data(tuple(df["ticker"].tolist()))

        if stocks_df.empty:
            return stocks_df

        stocks_df.columns = stocks_df.columns.str.lower()

        # Remove commas and percentage signs, and convert to numeric
        for col in stocks_df.columns:
            if col not in ["ticker", "industry", "market cap"]:
                stocks_df[col] = (
                    stocks_df[col]
                    .replace(r"^-$", None, regex=True)  # Replace only standalone '-' with None
                    .replace({",": "", "%": ""}, regex=True)  # Remove commas and percentage signs
                    .astype(float)  # Convert to float
                )

        # Apply scoring function to each row
        stocks_df["score"] = stocks_df.apply(self.score_stock, axis=1)

        # Rank stocks by score, descending
        stocks_df = stocks_df.sort_values(by="score", ascending=False)
        stocks_df["rank"] = range(1, len(stocks_df) + 1)
        # Get top N stocks
        return stocks_df

    def score_stock(self, row, target_side: str = "long"):
        score = 0
        if abs(row["gap"]) > 5.0:
            score -= 10

        if row["rel volume"] > 10:
            score += 15
        elif row["rel volume"] > 5:
            score += 10
        elif row["rel volume"] > 2:
            score += 5
        else:
            score -= 5

        if target_side == "long":
            if row["rsi"] > 80:
                score -= 10
            elif 70 < row["rsi"] <= 80:
                score -= 5
            elif 30 <= row["rsi"] <= 70:
                score += 10
            elif row["rsi"] < 30:
                score += 5
        else:
            if row["rsi"] > 80:
                score += 10
            elif 70 < row["rsi"] <= 80:
                score += 5
            elif 30 <= row["rsi"] <= 70:
                score += 10
            elif row["rsi"] < 30:
                score -= 5

        if target_side == "long":
            if row["sma20"] > 0:
                score += 10
            if row["sma50"] > 0:
                score += 20
        else:
            if row["sma20"] < 0:
                score += 10
            if row["sma50"] < 0:
                score += 20

        if target_side == "long":
            if abs(row["perf week"]) > 50:
                score -= 10
            elif 10 < abs(row["perf week"]) <= 50:
                score += 5
            elif -10 <= row["perf week"] <= 10:
                score += 10
        else:
            if abs(row["perf week"]) > 50:
                score += 5
            elif 10 < abs(row["perf week"]) <= 50:
                score += 10
            elif -10 <= row["perf week"] <= 10:
                score += 5

        return (score + 100) / 200


def main():
    scanner = FinvizScanner()
    stocks = scanner.get_trending_stocks()
    logger.info(stocks)


if __name__ == "__main__":
    main()
