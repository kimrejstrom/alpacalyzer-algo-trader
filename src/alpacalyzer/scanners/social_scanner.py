import time
from datetime import UTC, datetime

import pandas as pd

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer
from alpacalyzer.events import ScanCompleteEvent, emit_event
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.scanners.stocktwits_scanner import StocktwitsScanner
from alpacalyzer.scanners.wsb_scanner import WSBScanner
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


class SocialScanner:
    def __init__(self):
        self.wsb_scanner = WSBScanner()
        self.finviz_scanner = FinvizScanner()
        self.stocktwits_scanner = StocktwitsScanner()
        self.technical_analyzer = TechnicalAnalyzer()

    def display_top_stocks(self, df, top_n=10):
        """Display the top N ranked stocks."""
        if not df.empty:
            logger.debug(f"top {top_n} ranked stocks")
            for index, row in df.head(top_n).iterrows():
                logger.debug(
                    f"#{index + 1}: {row['ticker']} |"
                    f" sentiment_score={row['sentiment_score']:.2f} sentiment_rank={row['sentiment_rank']:.2f}"
                    f" technical_score={row['technical_score']:.2f} ta_rank={row['ta_rank']:.2f}"
                    f" final_score={row['final_score']:.2f} final_rank={row['final_rank']:.2f}"
                )
        else:
            logger.info("no stocks found")

    def get_trending_stocks(self, limit: int = 20) -> pd.DataFrame:
        """
        Fetch trending stocks from Reddit, Stocktwits, and Finviz, combine them, rank
        them.
        """  # noqa: D205

        start_time = time.time()

        # Initialize empty sets to store tickers
        tickers_set = set()

        # Fetch trending stocks from ApeWisdom (Reddit)
        try:
            wsb_df = self.wsb_scanner.get_trending_stocks(limit)
            if not wsb_df.empty:
                tickers_set.update(wsb_df["ticker"].tolist())
                logger.info(f"fetched tickers from apewisdom | count={len(wsb_df)}")
            else:
                logger.info("no trending stocks from apewisdom")
        except Exception as e:
            logger.error(f"apewisdom fetch failed | error={e}", exc_info=True)

        # Fetch trending stocks from Stocktwits
        try:
            stocktwits_df = self.stocktwits_scanner.get_trending_stocks()
            if not stocktwits_df.empty:
                tickers_set.update(stocktwits_df["ticker"].tolist())
                logger.info(f"fetched tickers from stocktwits | count={len(stocktwits_df)}")
            else:
                logger.info("no trending stocks from stocktwits")
        except Exception as e:
            logger.error(f"stocktwits fetch failed | error={e}", exc_info=True)

        # Fetch trending stocks from Finviz
        try:
            finviz_df = self.finviz_scanner.get_trending_stocks(limit)
            if not finviz_df.empty:
                if "Ticker" in finviz_df.columns:
                    finviz_df = finviz_df.rename(columns={"Ticker": "ticker"})
                tickers_set.update(finviz_df["ticker"].tolist())
                logger.info(f"fetched tickers from finviz | count={len(finviz_df)}")
            else:
                logger.info("no trending stocks from finviz")
        except Exception as e:
            logger.error(f"finviz fetch failed | error={e}", exc_info=True)

        # Combine all unique tickers into a list and filter VOO SPY and QQQ
        tickers_list = list(filter(lambda x: x not in ["VOO", "SPY", "QQQ"], tickers_set))

        logger.info(f"unique tickers combined | count={len(tickers_list)}")

        if not tickers_list:
            logger.info("no tickers found from sources")
            return pd.DataFrame()

        # Fetch ranks for the combined tickers
        return self.rank_stocks(tickers_list, limit, start_time)

    def rank_stocks(self, tickers_list: list[str], limit: int, start_time: float | None = None) -> pd.DataFrame:
        """Rank stocks based on the combined data."""

        # Fetch ranks for tickers from Stocktwits
        try:
            st_ranked = self.stocktwits_scanner.get_stock_ranks(pd.DataFrame({"ticker": tickers_list}))

        except Exception as e:
            logger.error(f"stocktwits ranks fetch failed | error={e}", exc_info=True)
            st_ranked = pd.DataFrame()

        # Fetch ranks for tickers from Finviz
        try:
            finviz_ranked = self.finviz_scanner.get_stock_ranks(pd.DataFrame({"ticker": tickers_list}))

        except Exception as e:
            logger.error(f"finviz ranks fetch failed | error={e}", exc_info=True)
            finviz_ranked = pd.DataFrame()

        # Combine the ranked results
        combined_df = pd.DataFrame({"ticker": tickers_list})

        if not st_ranked.empty:
            combined_df = pd.merge(
                combined_df,
                st_ranked[["ticker", "rank", "score"]],
                on="ticker",
                how="left",
            ).rename(columns={"rank": "st_rank", "score": "st_score"})

        if not finviz_ranked.empty:
            combined_df = pd.merge(
                combined_df,
                finviz_ranked[["ticker", "rank", "score"]],
                on="ticker",
                how="left",
            ).rename(columns={"rank": "finviz_rank", "score": "finviz_score"})

        combined_df = combined_df.dropna(subset=["st_rank", "finviz_rank", "st_score", "finviz_score"])

        if combined_df.empty:
            logger.info("no stocks to combine from sources")
            return pd.DataFrame()

        # Calculate sentiment rank
        combined_df["sentiment_rank"] = combined_df.apply(
            lambda row: ((row["st_rank"] + row["finviz_rank"]) / 2),
            axis=1,
        )

        # Calculate sentiment score
        combined_df["sentiment_score"] = combined_df.apply(
            lambda row: ((row["st_score"] + row["finviz_score"]) / 2),
            axis=1,
        )

        # Run technical analysis silently
        logger.info("running technical analysis")
        ta_results = []
        for _, row in combined_df.iterrows():
            ta_data = self.technical_analyzer.analyze_stock(row["ticker"])
            if ta_data:
                ta_results.append({"ticker": ta_data["symbol"], "technical_score": ta_data["score"], "trading_signals": ta_data})

        # Add technical ranks
        ta_df = pd.DataFrame(ta_results)

        # Ensure ta_df contains required columns and data
        if not ta_df.empty and "ticker" in ta_df.columns:
            ta_df = ta_df.sort_values("technical_score", ascending=False)
            ta_df["ta_rank"] = range(1, len(ta_df) + 1)

            # Merge technical ranks
            combined_df = pd.merge(
                combined_df,
                ta_df[["ticker", "ta_rank", "technical_score", "trading_signals"]],
                on="ticker",
                how="left",
            )
            combined_df["final_rank"] = combined_df["sentiment_rank"] + combined_df["ta_rank"]
            combined_df["final_score"] = combined_df["sentiment_score"] + combined_df["technical_score"]

            if start_time is not None:
                duration = time.time() - start_time
                emit_event(
                    ScanCompleteEvent(
                        timestamp=datetime.now(UTC),
                        source="social_scanner",
                        tickers_found=combined_df["ticker"].tolist(),
                        duration_seconds=duration,
                    )
                )

            return combined_df.sort_values("final_rank").reset_index(drop=True)
        logger.warning("technical analysis data empty or invalid")

        if combined_df.empty:
            logger.info("no stocks found or no technical data available")
        return pd.DataFrame()


def main():
    scanner = SocialScanner()
    df = scanner.get_trending_stocks()
    scanner.display_top_stocks(df)


if __name__ == "__main__":
    main()
