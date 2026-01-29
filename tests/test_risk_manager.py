"""Tests for Risk Management Agent."""

from unittest.mock import MagicMock, patch

from alpacalyzer.graph.state import AgentState
from alpacalyzer.trading.risk_manager import (
    calculate_dynamic_position_size,
    get_stock_atr,
    risk_management_agent,
)


class TestShortPositionMarginCalculation:
    """Test that short positions use correct margin calculation (divide, not multiply)."""

    def test_short_position_margin_calculation(self, monkeypatch):
        """Test that short positions use division for margin calculation."""
        state = AgentState(
            messages=[],
            data={
                "tickers": ["AAPL"],
                "portfolio": {},
                "AAPL": {"signal": "bearish"},
                "analyst_signals": {
                    "potential_candidates_agent": {
                        "AAPL": {
                            "signal": "bearish",
                            "confidence": 80.0,
                            "reasoning": "Test bearish signal",
                        }
                    }
                },
            },
            metadata={"show_reasoning": False},
        )

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.qty = "0"
        mock_position.cost_basis = "0"
        mock_position.current_price = "150.00"
        mock_position.side = "long"
        mock_position.unrealized_pl = "0"

        mock_account = {
            "equity": 100000.0,
            "buying_power": 50000.0,
            "daytrading_buying_power": 200000.0,
            "maintenance_margin": 2500.0,
        }

        def mock_get_all_positions():
            return [mock_position]

        def mock_get_account_info():
            return mock_account

        def mock_get_current_price(ticker):
            return 150.0

        monkeypatch.setattr(
            "alpacalyzer.trading.risk_manager.trading_client.get_all_positions",
            mock_get_all_positions,
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.risk_manager.get_account_info",
            mock_get_account_info,
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.risk_manager.get_current_price",
            mock_get_current_price,
        )

        result = risk_management_agent(state)

        risk_data = result["data"]["analyst_signals"]["risk_management_agent"]["AAPL"]

        expected_adjusted_buying_power = mock_account["daytrading_buying_power"] / 0.5 * 0.9

        actual_adjusted_buying_power = risk_data["reasoning"]["adjusted_buying_power"]

        assert actual_adjusted_buying_power == expected_adjusted_buying_power, (
            f"Expected adjusted_buying_power {expected_adjusted_buying_power}, got {actual_adjusted_buying_power}. Short positions should DIVIDE by margin requirement, not multiply."
        )


class TestDynamicPositionSizing:
    """Tests for dynamic position sizing based on ATR and VIX."""

    def test_dynamic_sizing_with_atr(self):
        """Test that position size scales with ATR."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=2.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=None,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
        risk_amount = 10000.0 * 0.002  # $20
        risk_per_share = 2 * 2.0  # $4
        expected_shares = int(risk_amount / risk_per_share)
        expected_size = expected_shares * 100.0
        assert size == expected_size

    def test_dynamic_sizing_with_high_atr(self):
        """Test that high ATR reduces position size."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=5.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=None,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
        assert size < 500.0
        assert size > 0

    def test_dynamic_sizing_with_low_atr(self):
        """Test that low ATR increases position size, but capped at max."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=0.5):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=None,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
        risk_amount = 10000.0 * 0.002  # $20
        risk_per_share = 2 * 0.5  # $1
        expected_shares = int(risk_amount / risk_per_share)
        uncapped_size = expected_shares * 100.0
        max_size = 10000.0 * 0.05
        expected_size = min(uncapped_size, max_size)
        assert size == expected_size

    def test_dynamic_sizing_with_vix(self):
        """Test that VIX reduces position size."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=2.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size_no_vix = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=None,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
                size_with_vix = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=30.0,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
        assert size_with_vix < size_no_vix

    def test_dynamic_sizing_atr_unavailable(self):
        """Test fallback to fixed sizing when ATR unavailable."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=None):
            size = calculate_dynamic_position_size(
                ticker="AAPL",
                portfolio_equity=10000.0,
                vix=None,
                base_risk_pct=0.002,
                max_position_pct=0.05,
            )
        assert size == 500.0

    def test_dynamic_sizing_zero_atr(self):
        """Test fallback when ATR is zero."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=0.0):
            size = calculate_dynamic_position_size(
                ticker="AAPL",
                portfolio_equity=10000.0,
                vix=None,
                base_risk_pct=0.002,
                max_position_pct=0.05,
            )
        assert size == 500.0


class TestGetStockAtr:
    """Tests for get_stock_atr function."""

    def test_get_stock_atr_returns_value(self):
        """Test that ATR is returned when available."""
        mock_signals = {"atr": 2.5}
        with patch("alpacalyzer.analysis.technical_analysis.TechnicalAnalyzer") as mock_ta_class:
            mock_ta = MagicMock()
            mock_ta.analyze_stock.return_value = mock_signals
            mock_ta_class.return_value = mock_ta
            result = get_stock_atr("AAPL")
        assert result == 2.5

    def test_get_stock_atr_returns_none_when_unavailable(self):
        """Test that None is returned when ATR unavailable."""
        with patch("alpacalyzer.analysis.technical_analysis.TechnicalAnalyzer") as mock_ta_class:
            mock_ta = MagicMock()
            mock_ta.analyze_stock.return_value = None
            mock_ta_class.return_value = mock_ta
            result = get_stock_atr("AAPL")
        assert result is None

    def test_get_stock_atr_returns_none_when_key_missing(self):
        """Test that None is returned when atr key missing."""
        with patch("alpacalyzer.analysis.technical_analysis.TechnicalAnalyzer") as mock_ta_class:
            mock_ta = MagicMock()
            mock_ta.analyze_stock.return_value = {"price": 150.0}
            mock_ta_class.return_value = mock_ta
            result = get_stock_atr("AAPL")
        assert result is None


class TestDynamicPositionSizingEdgeCases:
    """Edge case tests for dynamic position sizing."""

    def test_dynamic_sizing_zero_portfolio(self):
        """Test handling of zero portfolio equity."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=2.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=0.0,
                    vix=None,
                    base_risk_pct=0.02,
                    max_position_pct=0.05,
                )
        assert size == 0.0

    def test_dynamic_sizing_price_unavailable(self):
        """Test fallback when price is unavailable."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=2.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=None):
                size = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=None,
                    base_risk_pct=0.02,
                    max_position_pct=0.05,
                )
        assert size == 500.0

    def test_dynamic_sizing_small_risk_amount(self):
        """Test minimum share when risk amount is very small."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=10.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=100.0,
                    vix=None,
                    base_risk_pct=0.02,
                    max_position_pct=0.05,
                )
        assert size == 5.0  # 1 share * $100, but capped at 5% of $100 = $5

    def test_dynamic_sizing_negative_vix(self):
        """Test handling of negative VIX (should behave like no VIX)."""
        with patch("alpacalyzer.trading.risk_manager.get_stock_atr", return_value=2.0):
            with patch("alpacalyzer.trading.risk_manager.get_current_price", return_value=100.0):
                size_with_neg_vix = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=-5.0,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
                size_no_vix = calculate_dynamic_position_size(
                    ticker="AAPL",
                    portfolio_equity=10000.0,
                    vix=None,
                    base_risk_pct=0.002,
                    max_position_pct=0.05,
                )
        assert size_with_neg_vix == size_no_vix
