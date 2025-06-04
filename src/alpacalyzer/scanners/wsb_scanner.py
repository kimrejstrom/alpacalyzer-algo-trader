import pandas as pd
import requests
from colorama import Fore, Style
from tabulate import tabulate

from alpacalyzer.utils.logger import logger


class WSBScanner:
    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }

    def get_trending_stocks(self, limit=50):
        """
        Get trending stocks from ApeWisdom.

        Returns DataFrame with columns: ticker, mentions, rank
        """
        try:
            url = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
            response = requests.get(url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                logger.error(f"Error: ApeWisdom API returned status code {response.status_code}")
                return pd.DataFrame()

            data = response.json()
            results = data.get("results", [])

            # Convert to DataFrame
            df = pd.DataFrame(results)
            if df.empty:
                return df

            # Rename and calculate columns
            df = df.rename(columns={"ticker": "ticker", "mentions": "mentions"})

            # Add score and sentiment (normalized rank)
            df["score"] = df["rank"].rank(pct=True)  # Percentile rank (0-1)
            df["sentiment"] = df["score"]  # Same as score since ApeWisdom already factors in sentiment

            # Get top N stocks (already ranked by ApeWisdom)
            return df.head(limit)

        except Exception as e:
            logger.error(f"Error fetching ApeWisdom data: {str(e)}", exc_info=True)
            return pd.DataFrame()


def main():
    scanner = WSBScanner()
    df = scanner.get_trending_stocks()

    if not df.empty:
        logger.info(f"\n{Fore.MAGENTA}Top Trending Stocks from ApeWisdom:{Style.RESET_ALL}")

        headers = [
            f"{Fore.YELLOW}Ticker{Style.RESET_ALL}",
            f"{Fore.YELLOW}Mentions{Style.RESET_ALL}",
            f"{Fore.YELLOW}Rank{Style.RESET_ALL}"
        ]

        table_data = []
        for _, row in df.iterrows():
            table_data.append([
                f"{Fore.CYAN}{row['ticker']}{Style.RESET_ALL}",
                f"{Fore.GREEN}{row['mentions']}{Style.RESET_ALL}",
                f"{Fore.BLUE}{row['rank']}{Style.RESET_ALL}"
            ])

        logger.info(tabulate(table_data, headers=headers, tablefmt="psql"))
    else:
        logger.info(f"{Fore.YELLOW}No trending stocks found from ApeWisdom.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
