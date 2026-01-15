"""Tests for scanner adapters."""

from unittest.mock import patch

import pandas as pd

from alpacalyzer.data.models import TopTicker, TopTickersResponse
from alpacalyzer.pipeline.registry import ScannerRegistry, _register_scanner_adapters
from alpacalyzer.scanners.adapters import RedditScannerAdapter, SocialScannerAdapter


class TestRedditScannerAdapter:
    def setup_method(self):
        ScannerRegistry.reset()
        _register_scanner_adapters()

    def test_reddit_scanner_adapter_name(self):
        adapter = RedditScannerAdapter()
        assert adapter.name == "reddit"
        assert adapter.enabled is True

    def test_reddit_scanner_returns_empty_when_no_insights(self):
        with patch("alpacalyzer.scanners.adapters.get_reddit_insights", return_value=None):
            adapter = RedditScannerAdapter()
            result = adapter.scan()
            assert result.success is True
            assert result.count == 0
            assert result.symbols() == []

    def test_reddit_scanner_returns_empty_when_no_top_tickers(self):
        with patch("alpacalyzer.scanners.adapters.get_reddit_insights", return_value=TopTickersResponse(top_tickers=[])):
            adapter = RedditScannerAdapter()
            result = adapter.scan()
            assert result.success is True
            assert result.count == 0

    def test_reddit_scanner_returns_tickers_when_data_available(self):
        top_tickers = [
            TopTicker(ticker="AAPL", signal="bullish", confidence=80, reasoning="Test"),
            TopTicker(ticker="GOOGL", signal="neutral", confidence=60, reasoning="Test"),
        ]
        ta_df = pd.DataFrame({"ticker": ["AAPL", "GOOGL"], "close": [150.0, 2800.0]})

        with (
            patch("alpacalyzer.scanners.adapters.get_reddit_insights", return_value=TopTickersResponse(top_tickers=top_tickers)),
            patch("alpacalyzer.scanners.adapters.FinvizScanner.fetch_stock_data", return_value=ta_df),
            patch("alpacalyzer.scanners.adapters.get_top_candidates", return_value=TopTickersResponse(top_tickers=top_tickers)),
        ):
            adapter = RedditScannerAdapter()
            result = adapter.scan()

            assert result.success is True
            assert result.count == 2
            assert "AAPL" in result.symbols()
            assert "GOOGL" in result.symbols()

    def test_reddit_scanner_returns_empty_when_finviz_empty(self):
        top_tickers = [
            TopTicker(ticker="AAPL", signal="bullish", confidence=80, reasoning="Test"),
        ]

        with (
            patch("alpacalyzer.scanners.adapters.get_reddit_insights", return_value=TopTickersResponse(top_tickers=top_tickers)),
            patch("alpacalyzer.scanners.adapters.FinvizScanner.fetch_stock_data", return_value=pd.DataFrame()),
        ):
            adapter = RedditScannerAdapter()
            result = adapter.scan()

            assert result.success is True
            assert result.count == 0


class TestSocialScannerAdapter:
    def setup_method(self):
        ScannerRegistry.reset()
        _register_scanner_adapters()

    def test_social_scanner_adapter_name(self):
        adapter = SocialScannerAdapter()
        assert adapter.name == "social"
        assert adapter.enabled is True

    def test_social_scanner_returns_empty_when_no_trending_stocks(self):
        with patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=pd.DataFrame()):
            adapter = SocialScannerAdapter()
            result = adapter.scan()
            assert result.success is True
            assert result.count == 0

    def test_social_scanner_filters_by_ta_threshold(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.3,
                        "momentum": 5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 10,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.5),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()
            assert result.count == 0

    def test_social_scanner_passes_valid_tickers(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.6,
                        "momentum": 5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 10,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.5),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.weak_technicals", return_value=None),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()

            assert result.success is True
            assert result.count == 1
            assert "AAPL" in result.symbols()

    def test_social_scanner_returns_bullish_for_high_score(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.9,
                        "momentum": 5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 10,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.5),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.weak_technicals", return_value=None),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()

            assert result.success is True
            assert result.count == 1
            assert result.tickers[0].signal == "bullish"

    def test_social_scanner_returns_neutral_for_medium_score(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.5,
                        "momentum": 5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 10,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.4),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.weak_technicals", return_value=None),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()

            assert result.success is True
            assert result.count == 1
            assert result.tickers[0].signal == "neutral"

    def test_social_scanner_filters_negative_momentum_with_high_sentiment(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.6,
                        "momentum": -5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 25,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.5),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()

            assert result.count == 0

    def test_social_scanner_filters_weak_momentum(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.6,
                        "momentum": -5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 10,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.5),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()

            assert result.count == 0

    def test_social_scanner_filters_weak_technicals(self):
        df = pd.DataFrame(
            {
                "ticker": ["AAPL"],
                "trading_signals": [
                    {
                        "score": 0.6,
                        "momentum": 5.0,
                        "atr": 2.0,
                        "price": 100.0,
                        "rvol": 2.0,
                        "signals": ["TA: Breakout"],
                    }
                ],
                "sentiment_rank": 10,
            }
        )

        with (
            patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=df),
            patch("alpacalyzer.scanners.adapters.YFinanceClient.get_vix", return_value=15.0),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.calculate_ta_threshold", return_value=0.5),
            patch("alpacalyzer.scanners.adapters.TechnicalAnalyzer.weak_technicals", return_value="Unfavorable technicals"),
        ):
            adapter = SocialScannerAdapter()
            result = adapter.scan()

            assert result.count == 0


class TestScannerRegistryAutoRegistration:
    def setup_method(self):
        ScannerRegistry.reset()
        _register_scanner_adapters()

    def test_scanner_registry_has_reddit_adapter(self):
        from alpacalyzer.pipeline.registry import get_scanner_registry

        registry = get_scanner_registry()
        assert "reddit" in registry.list_scanners()

    def test_scanner_registry_has_social_adapter(self):
        from alpacalyzer.pipeline.registry import get_scanner_registry

        registry = get_scanner_registry()
        assert "social" in registry.list_scanners()

    def test_scanner_registry_run_all_returns_results(self):
        from alpacalyzer.pipeline.registry import get_scanner_registry

        with patch("alpacalyzer.scanners.adapters.get_reddit_insights", return_value=None), patch("alpacalyzer.scanners.adapters.SocialScanner.get_trending_stocks", return_value=pd.DataFrame()):
            registry = get_scanner_registry()
            results = list(registry.run_all())

            assert len(results) == 2
            source_names = [r.source for r in results]
            assert "reddit" in source_names
            assert "social" in source_names
