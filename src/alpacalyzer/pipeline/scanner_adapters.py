"""Scanner adapters for existing scanner implementations."""


import pandas as pd

from alpacalyzer.pipeline.scanner_protocol import BaseScanner, TopTicker


class WSBScannerAdapter(BaseScanner):
    """Adapter for WSB/ApeWisdom scanner."""

    def __init__(self):
        super().__init__(name="wsb_scanner", enabled=True)
        from alpacalyzer.scanners.wsb_scanner import WSBScanner

        self._scanner = WSBScanner()

    def _execute_scan(self) -> list[TopTicker]:
        df = self._scanner.get_trending_stocks(limit=50)
        if df.empty:
            return []
        return self._df_to_tickers(df)

    def _df_to_tickers(self, df: pd.DataFrame) -> list[TopTicker]:
        tickers = []
        for _, row in df.iterrows():
            ticker = row.get("ticker")
            if not ticker:
                continue

            mentions = row.get("mentions", 0)
            rank = row.get("rank", 0)
            score = row.get("score", 0.5)

            tickers.append(
                TopTicker(
                    ticker=ticker,
                    signal="bullish" if mentions > 10 else "neutral",
                    confidence=min(float(score), 1.0),
                    reasoning=f"Rank {rank} with {mentions} mentions (score: {score:.2f})",
                )
            )
        return tickers


class StocktwitsScannerAdapter(BaseScanner):
    """Adapter for Stocktwits scanner."""

    def __init__(self):
        super().__init__(name="stocktwits_scanner", enabled=True)
        from alpacalyzer.scanners.stocktwits_scanner import StocktwitsScanner

        self._scanner = StocktwitsScanner()

    def _execute_scan(self) -> list[TopTicker]:
        df = self._scanner.get_trending_stocks()
        if df.empty:
            return []
        return self._df_to_tickers(df)

    def _df_to_tickers(self, df: pd.DataFrame) -> list[TopTicker]:
        tickers = []
        for _, row in df.iterrows():
            ticker = row.get("ticker")
            if not ticker:
                continue

            watchers = row.get("watchlist_count", 0)
            title = row.get("title", "")

            tickers.append(
                TopTicker(
                    ticker=ticker,
                    signal="neutral",
                    confidence=min(0.7, 1.0),
                    reasoning=f"Watchers: {watchers} - {title[:50] if title else 'No description'}",
                )
            )
        return tickers


class FinvizScannerAdapter(BaseScanner):
    """Adapter for Finviz scanner."""

    def __init__(self):
        super().__init__(name="finviz_scanner", enabled=True)
        from alpacalyzer.scanners.finviz_scanner import FinvizScanner

        self._scanner = FinvizScanner()

    def _execute_scan(self) -> list[TopTicker]:
        df = self._scanner.get_trending_stocks(limit=20)
        if df.empty:
            return []
        return self._df_to_tickers(df)

    def _df_to_tickers(self, df: pd.DataFrame) -> list[TopTicker]:
        tickers = []
        for idx, row in df.iterrows():
            ticker = row.get("Ticker") or row.get("ticker")
            if not ticker:
                continue

            rel_vol = row.get("Relative Volume") or row.get("rel_volume", 0)
            rsi = row.get("RSI", 50)
            score = (float(rel_vol) / 10.0 + (100 - abs(float(rsi) - 50)) / 100.0) / 2.0

            tickers.append(
                TopTicker(
                    ticker=ticker,
                    signal="bullish" if float(rsi) < 70 else "neutral",
                    confidence=min(max(float(score), 0.5), 1.0),
                    reasoning=f"Rel Vol: {rel_vol}, RSI: {rsi:.1f}, Score: {score:.2f}",
                )
            )
        return tickers


class SocialScannerAdapter(BaseScanner):
    """Adapter for Social scanner (combined WSB + Stocktwits + Finviz)."""

    def __init__(self):
        super().__init__(name="social_scanner", enabled=True)
        from alpacalyzer.scanners.social_scanner import SocialScanner

        self._scanner = SocialScanner()

    def _execute_scan(self) -> list[TopTicker]:
        df = self._scanner.get_trending_stocks(limit=20)
        if df.empty:
            return []
        return self._df_to_tickers(df)

    def _df_to_tickers(self, df: pd.DataFrame) -> list[TopTicker]:
        tickers = []
        for _, row in df.iterrows():
            ticker = row.get("ticker")
            if not ticker:
                continue

            final_rank = row.get("final_rank", 0)
            final_score = row.get("final_score", 0)
            sentiment_score = row.get("sentiment_score", 0.5)
            technical_score = row.get("technical_score", 0.5)

            signal = "bullish" if sentiment_score > 0.5 else "neutral"
            confidence = min(float(final_score), 1.0)

            reasoning = f"Final Rank: {final_rank:.1f}, Sentiment: {sentiment_score:.2f}, TA: {technical_score:.2f}"

            tickers.append(
                TopTicker(
                    ticker=ticker,
                    signal=signal,
                    confidence=confidence,
                    reasoning=reasoning,
                )
            )
        return tickers
