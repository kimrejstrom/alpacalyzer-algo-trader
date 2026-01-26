"""Tests for data API functions including VIX fetching."""

from unittest.mock import MagicMock, patch


class TestGetVix:
    """Tests for VIX fetching function."""

    def test_get_vix_fresh_returns_value(self):
        """Test that get_vix returns a value from yfinance."""
        from alpacalyzer.data.api import get_vix

        with patch("alpacalyzer.trading.yfinance_client.YFinanceClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_vix.return_value = 25.5
            mock_client_class.return_value = mock_client

            vix = get_vix()

            assert vix is not None
            assert vix == 25.5

    def test_get_vix_uses_cache(self):
        """Test that get_vix uses cached value when available."""

        from alpacalyzer.data.api import _vix_cache, get_vix

        _vix_cache.clear()

        with patch("alpacalyzer.trading.yfinance_client.YFinanceClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_vix.return_value = 25.0
            mock_client_class.return_value = mock_client

            vix1 = get_vix(use_cache=True)
            vix2 = get_vix(use_cache=True)

            assert vix1 == 25.0
            assert vix2 == 25.0
            assert mock_client.get_vix.call_count == 1

    def test_get_vix_respects_cache_expiration(self):
        """Test that get_vix fetches fresh value when cache expires."""
        import time

        from alpacalyzer.data.api import VIX_TTL, _vix_cache, get_vix

        _vix_cache.clear()

        with patch("alpacalyzer.trading.yfinance_client.YFinanceClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_vix.side_effect = [25.0, 30.0]
            mock_client_class.return_value = mock_client

            vix1 = get_vix(use_cache=True)
            assert vix1 == 25.0

            _vix_cache["vix"] = (25.0, time.time() - VIX_TTL - 100)

            vix2 = get_vix(use_cache=True)
            assert vix2 == 30.0
            assert mock_client.get_vix.call_count == 2

    def test_get_vix_no_cache_flag(self):
        """Test that use_cache=False always fetches fresh value."""
        import time

        from alpacalyzer.data.api import _vix_cache, get_vix

        _vix_cache["vix"] = (20.0, time.time())

        with patch("alpacalyzer.trading.yfinance_client.YFinanceClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_vix.return_value = 25.0
            mock_client_class.return_value = mock_client

            vix = get_vix(use_cache=False)

            assert vix == 25.0
            assert mock_client.get_vix.call_count == 1

    def test_get_vix_returns_default_on_error(self):
        """Test that get_vix returns default value (25.0) on error."""
        from alpacalyzer.data.api import get_vix

        with patch("alpacalyzer.trading.yfinance_client.YFinanceClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get_vix.return_value = 25.0
            mock_client_class.return_value = mock_client

            vix = get_vix()

            assert vix == 25.0


class TestPricesToDf:
    """Tests for price data conversion."""

    def test_prices_to_df_conversion(self):
        """Test converting Price objects to DataFrame."""
        from alpacalyzer.data.api import prices_to_df
        from alpacalyzer.data.models import Price

        prices = [
            Price(
                open=100.0,
                close=101.0,
                high=102.0,
                low=99.0,
                volume=1000000,
                time="2024-01-01",
            ),
            Price(
                open=101.0,
                close=102.0,
                high=103.0,
                low=100.0,
                volume=1100000,
                time="2024-01-02",
            ),
        ]

        df = prices_to_df(prices)

        assert len(df) == 2
        assert "close" in df.columns
        assert df.iloc[0]["close"] == 101.0
        assert df.iloc[1]["close"] == 102.0
