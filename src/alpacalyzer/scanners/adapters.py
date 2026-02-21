"""Scanner adapters implementing BaseScanner protocol."""

import pandas as pd
from alpaca.trading.enums import OrderSide

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer
from alpacalyzer.data.models import TopTicker
from alpacalyzer.pipeline.scanner_protocol import BaseScanner
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.scanners.social_scanner import SocialScanner
from alpacalyzer.trading.opportunity_finder import get_reddit_insights, get_top_candidates
from alpacalyzer.trading.yfinance_client import YFinanceClient
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


class RedditScannerAdapter(BaseScanner):
    """Adapter for Reddit/insight scanning."""

    def __init__(self):
        super().__init__(name="reddit", enabled=True)
        self._finviz = FinvizScanner()

    def _execute_scan(self) -> list[TopTicker]:
        insights = get_reddit_insights()
        if not insights or not insights.top_tickers:
            logger.info("reddit scan found no insights from LLM")
            return []

        tickers = [x.ticker for x in insights.top_tickers]
        logger.info(f"reddit LLM extracted tickers | count={len(tickers)} tickers={', '.join(tickers)}")

        ta_df = self._finviz.fetch_stock_data(tuple(tickers))
        if ta_df.empty:
            logger.info("reddit finviz data empty for extracted tickers")
            return []

        candidates = get_top_candidates(insights.top_tickers, ta_df)
        if not candidates or not candidates.top_tickers:
            logger.info("reddit candidate filtering returned no tickers")
            return []

        logger.info(f"reddit scan complete | candidates={len(candidates.top_tickers)}")
        return candidates.top_tickers


class SocialScannerAdapter(BaseScanner):
    """Adapter for social/technical scanning with TA filtering."""

    def __init__(self):
        super().__init__(name="social", enabled=True)
        self._scanner = SocialScanner()
        self._ta = TechnicalAnalyzer()
        self._yfinance = YFinanceClient()

    def _execute_scan(self) -> list[TopTicker]:
        df = self._scanner.get_trending_stocks(10)
        if df.empty:
            return []

        vix = self._yfinance.get_vix()
        opportunities = []

        for _, stock in df.iterrows():
            signals = stock.get("trading_signals")
            if not isinstance(signals, dict):
                continue

            if not self._passes_filters(signals, stock, vix):
                continue

            signal = "bullish" if signals["score"] > 0.8 else "neutral"
            opportunities.append(
                TopTicker(
                    ticker=stock["ticker"],
                    confidence=75,
                    signal=signal,
                    reasoning=f"Technical Score: {signals['score']:.2f}",
                )
            )

        return opportunities

    def _passes_filters(self, signals: dict, stock: pd.Series, vix: float) -> bool:
        momentum = signals["momentum"]
        score = signals["score"]
        signal_list = signals["signals"]

        atr_pct = signals["atr"] / signals["price"]
        threshold = self._ta.calculate_ta_threshold(vix, signals["rvol"], atr_pct)

        if score < threshold:
            return False
        if momentum < 0 and stock.get("sentiment_rank", 0) > 20:
            return False
        if momentum < -3:
            return False
        if 15 < vix < 30 and score < 0.8 and not any("Breakout" in s for s in signal_list):
            return False
        if self._ta.weak_technicals(signal_list, OrderSide.BUY):
            return False

        return True
