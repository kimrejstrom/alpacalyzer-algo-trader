"""Tests for the StrategyDashboard class."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from alpacalyzer.analysis.dashboard import (
    StrategyDashboard,
    dashboard_command,
    print_header,
    print_success,
    print_table,
)


@pytest.fixture
def mock_strategies():
    """Create mock strategies for testing."""
    from alpacalyzer.strategies.config import StrategyConfig
    from alpacalyzer.strategies.momentum import MomentumStrategy

    config1 = StrategyConfig(name="momentum", risk_pct_per_trade=0.02)
    config2 = StrategyConfig(name="breakout", risk_pct_per_trade=0.02)
    strategy1 = MomentumStrategy(config1)
    strategy2 = MagicMock()
    strategy2.config = config2
    strategy2.enabled = True
    strategy2.name = "breakout"
    return [strategy1, strategy2]


@pytest.fixture
def dashboard():
    """Create a StrategyDashboard instance."""
    return StrategyDashboard()


@pytest.fixture
def mock_price_data():
    """Create mock price data."""
    dates = pd.date_range(start="2024-01-01", periods=50, freq="D")
    data = {
        "open": [150.0 + i for i in range(50)],
        "close": [150.5 + i for i in range(50)],
        "high": [151.0 + i for i in range(50)],
        "low": [149.5 + i for i in range(50)],
        "volume": [1000000] * 50,
    }
    return pd.DataFrame(data, index=dates)


class TestPrintFunctions:
    """Test helper print functions."""

    def test_print_header(self, capsys):
        """Test print_header function."""
        print_header("Test Header")
        captured = capsys.readouterr()
        assert "Test Header" in captured.out

    def test_print_success(self, capsys):
        """Test print_success function."""
        print_success("Success message")
        captured = capsys.readouterr()
        assert "Success message" in captured.out

    def test_print_table(self, capsys):
        """Test print_table function."""
        headers = ["Name", "Value"]
        rows = [["Test1", "100"], ["Test2", "200"]]
        print_table("Test Table", headers, rows)
        captured = capsys.readouterr()
        assert "Test Table" in captured.out
        assert "Test1" in captured.out

    def test_print_table_empty(self, capsys):
        """Test print_table with empty rows."""
        print_table("Empty Table", ["Col1"], [])
        captured = capsys.readouterr()
        assert "No data" in captured.out


class TestStrategyDashboard:
    """Test StrategyDashboard class."""

    def test_init(self, dashboard):
        """Test dashboard initialization."""
        assert dashboard is not None
        assert hasattr(dashboard, "registry")

    def test_show_overview(self, dashboard, capsys):
        """Test showing strategy overview."""
        dashboard.show_overview()
        captured = capsys.readouterr()
        output = captured.out
        # Check that output contains strategy names or table
        assert "Strategy" in output or "breakout" in output or "momentum" in output

    @patch("alpacalyzer.analysis.dashboard.compare_strategies")
    @patch("alpacalyzer.analysis.dashboard.get_price_data")
    def test_compare_on_ticker(self, mock_get_price, mock_compare, dashboard, mock_price_data, capsys):
        """Test comparing strategies on a ticker."""
        # Setup mocks
        mock_get_price.return_value = mock_price_data
        mock_compare.return_value = pd.DataFrame(
            {
                "Strategy": ["momentum", "breakout"],
                "Win Rate": ["60.0%", "70.0%"],
                "Total P/L": ["$100.00", "$200.00"],
            }
        )

        # Run comparison
        dashboard.compare_on_ticker("AAPL", days=30)

        # Verify output
        captured = capsys.readouterr()
        output = captured.out
        assert "AAPL" in output or "Strategy Performance" in output

    @patch("alpacalyzer.analysis.dashboard.get_price_data")
    def test_compare_on_ticker_no_strategies(self, mock_get_price, capsys):
        """Test comparison when no strategies are registered."""
        from alpacalyzer.analysis.dashboard import StrategyRegistry

        # Temporarily patch the registry to return empty
        with patch.object(StrategyRegistry, "list_strategies", return_value=[]):
            dashboard = StrategyDashboard()
            dashboard.compare_on_ticker("AAPL", days=30)

        captured = capsys.readouterr()
        assert "No strategies" in captured.out or "registered" in captured.out

    @patch("alpacalyzer.analysis.dashboard.Backtester")
    @patch("alpacalyzer.analysis.dashboard.get_price_data")
    def test_show_backtest_detail(self, mock_get_price, mock_backtester_class, dashboard, mock_price_data, capsys):
        """Test showing detailed backtest results."""
        # Setup mocks
        mock_get_price.return_value = mock_price_data

        mock_result = MagicMock()
        mock_result.closed_trades = [
            MagicMock(
                entry_time=datetime(2024, 1, 1, 10, 0),
                exit_time=datetime(2024, 1, 2, 10, 0),
                side="long",
                entry_price=150.0,
                exit_price=155.0,
                pnl=5.0,
                pnl_pct=0.033,
            )
        ]
        mock_result.summary.return_value = "Test Summary"

        mock_backtester = MagicMock()
        mock_backtester.run.return_value = mock_result
        mock_backtester_class.return_value = mock_backtester

        # Run detail view
        dashboard.show_backtest_detail("momentum", "AAPL", days=30)

        # Verify output
        captured = capsys.readouterr()
        output = captured.out
        assert "momentum" in output or "Backtest" in output or "Trade History" in output

    @patch("alpacalyzer.data.api.get_price_data")
    def test_show_market_conditions(self, mock_get_price, dashboard, capsys):
        """Test showing market conditions analysis."""
        # Create mock data for SPY
        dates = pd.date_range(start="2024-01-01", periods=50, freq="D")
        data = {
            "close": [400.0 + i * 0.5 for i in range(50)],
            "volume": [1000000] * 50,
        }
        mock_df = pd.DataFrame(data, index=dates)
        mock_get_price.return_value = mock_df

        # Run market conditions
        dashboard.show_market_conditions()

        # Verify output
        captured = capsys.readouterr()
        output = captured.out
        assert "Market Conditions" in output or "Market Regime" in output or "SPY" in output

    def test_show_backtest_detail_strategy_not_found(self, dashboard, capsys):
        """Test showing backtest detail for non-existent strategy."""
        from alpacalyzer.analysis.dashboard import StrategyRegistry

        # Temporarily patch to raise error
        with patch.object(StrategyRegistry, "get", side_effect=ValueError("Not found")):
            dashboard.show_backtest_detail("nonexistent", "AAPL", days=30)

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "Strategy not found" in captured.out


class TestDashboardCommand:
    """Test dashboard CLI command."""

    @patch("alpacalyzer.analysis.dashboard.StrategyDashboard")
    def test_dashboard_command_overview(self, mock_dashboard_class):
        """Test dashboard command with no arguments (overview)."""
        mock_dashboard = MagicMock()
        mock_dashboard_class.return_value = mock_dashboard

        # Call with no arguments - should show overview
        dashboard_command(ticker=None, strategy=None, days=30, conditions=False)

        # Verify overview was called
        mock_dashboard.show_overview.assert_called_once()

    @patch("alpacalyzer.analysis.dashboard.StrategyDashboard")
    def test_dashboard_command_conditions(self, mock_dashboard_class):
        """Test dashboard command with conditions flag."""
        mock_dashboard = MagicMock()
        mock_dashboard_class.return_value = mock_dashboard

        # Call with conditions flag
        dashboard_command(ticker=None, strategy=None, days=30, conditions=True)

        # Verify market conditions was called
        mock_dashboard.show_market_conditions.assert_called_once()

    @patch("alpacalyzer.analysis.dashboard.StrategyDashboard")
    def test_dashboard_command_ticker_comparison(self, mock_dashboard_class):
        """Test dashboard command with ticker only (comparison)."""
        mock_dashboard = MagicMock()
        mock_dashboard_class.return_value = mock_dashboard

        # Call with ticker only
        dashboard_command(ticker="AAPL", strategy=None, days=30, conditions=False)

        # Verify compare was called
        mock_dashboard.compare_on_ticker.assert_called_once_with("AAPL", 30)

    @patch("alpacalyzer.analysis.dashboard.StrategyDashboard")
    def test_dashboard_command_detailed_backtest(self, mock_dashboard_class):
        """Test dashboard command with both ticker and strategy."""
        mock_dashboard = MagicMock()
        mock_dashboard_class.return_value = mock_dashboard

        # Call with both ticker and strategy
        dashboard_command(ticker="AAPL", strategy="momentum", days=30, conditions=False)

        # Verify backtest detail was called
        mock_dashboard.show_backtest_detail.assert_called_once_with("momentum", "AAPL", 30)

    @patch("alpacalyzer.analysis.dashboard.StrategyDashboard")
    def test_dashboard_command_priority(self, mock_dashboard_class):
        """Test that conditions takes priority over other options."""
        mock_dashboard = MagicMock()
        mock_dashboard_class.return_value = mock_dashboard

        # Call with conditions and other args - conditions should win
        dashboard_command(ticker="AAPL", strategy="momentum", days=30, conditions=True)

        mock_dashboard.show_market_conditions.assert_called_once()
        mock_dashboard.compare_on_ticker.assert_not_called()
        mock_dashboard.show_backtest_detail.assert_not_called()
        mock_dashboard.show_overview.assert_not_called()
