"""Tests for backtesting framework."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from alpacalyzer.backtesting.backtester import (
    Backtester,
    BacktestResult,
    BacktestTrade,
    compare_strategies,
)
from alpacalyzer.strategies.base import EntryDecision, ExitDecision


class TestBacktestTrade:
    """Tests for BacktestTrade dataclass."""

    def test_closed_property(self):
        """Test closed property returns True when exit_time is set."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="long",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 15),
            exit_price=110.0,
        )
        assert trade.closed is True

        trade_open = BacktestTrade(
            ticker="AAPL",
            side="long",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
        )
        assert trade_open.closed is False

    def test_pnl_long(self):
        """Test PnL calculation for long position."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="long",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 15),
            exit_price=110.0,
            quantity=10,
        )
        assert trade.pnl == 100.0

    def test_pnl_short(self):
        """Test PnL calculation for short position."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="short",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 15),
            exit_price=90.0,
            quantity=10,
        )
        assert trade.pnl == 100.0

    def test_pnl_open_position(self):
        """Test PnL is 0 for open position."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="long",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
        )
        assert trade.pnl == 0.0

    def test_pnl_pct_long(self):
        """Test PnL percentage for long position."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="long",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 15),
            exit_price=110.0,
        )
        assert trade.pnl_pct == pytest.approx(0.10)

    def test_pnl_pct_short(self):
        """Test PnL percentage for short position."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="short",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 15),
            exit_price=90.0,
        )
        assert trade.pnl_pct == pytest.approx(0.10)

    def test_hold_duration(self):
        """Test hold duration calculation."""
        trade = BacktestTrade(
            ticker="AAPL",
            side="long",
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            exit_time=datetime(2024, 1, 15),
            exit_price=110.0,
        )
        assert trade.hold_duration == timedelta(days=14)


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    def test_total_trades(self):
        """Test total_trades property."""
        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[
                BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0),
                BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0),
            ],
        )
        assert result.total_trades == 2

    def test_closed_trades(self):
        """Test closed_trades filters correctly."""
        open_trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0)
        closed_trade = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 110.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[open_trade, closed_trade],
        )

        assert len(result.closed_trades) == 1
        assert result.closed_trades[0] == closed_trade

    def test_winning_trades(self):
        """Test winning_trades property."""
        winning_trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        losing_trade = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[winning_trade, losing_trade],
        )

        assert len(result.winning_trades) == 1
        assert result.winning_trades[0] == winning_trade

    def test_losing_trades(self):
        """Test losing_trades property."""
        winning_trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        losing_trade = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[winning_trade, losing_trade],
        )

        assert len(result.losing_trades) == 1
        assert result.losing_trades[0] == losing_trade

    def test_win_rate(self):
        """Test win_rate calculation."""
        winning_trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        losing_trade = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[winning_trade, losing_trade],
        )

        assert result.win_rate == pytest.approx(0.50)

    def test_win_rate_no_trades(self):
        """Test win_rate is 0 when no closed trades."""
        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[],
        )
        assert result.win_rate == 0.0

    def test_total_pnl(self):
        """Test total_pnl calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0, quantity=10)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0, quantity=10)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2],
        )

        assert result.total_pnl == 0.0

    def test_average_pnl(self):
        """Test average_pnl calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 120.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2],
        )

        assert result.average_pnl == 15.0

    def test_average_win(self):
        """Test average_win calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 120.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2],
        )

        assert result.average_win == 15.0

    def test_average_loss(self):
        """Test average_loss calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 90.0)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 80.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2],
        )

        assert result.average_loss == -15.0

    def test_profit_factor(self):
        """Test profit_factor calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2],
        )

        assert result.profit_factor == 1.0

    def test_profit_factor_no_losses(self):
        """Test profit_factor with only winning trades."""
        trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade],
        )

        assert result.profit_factor == float("inf")

    def test_sharpe_ratio(self):
        """Test sharpe_ratio calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 120.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2],
        )

        assert result.sharpe_ratio > 0

    def test_sharpe_ratio_insufficient_trades(self):
        """Test sharpe_ratio is 0 with fewer than 2 trades."""
        trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade],
        )

        assert result.sharpe_ratio == 0.0

    def test_max_drawdown(self):
        """Test max_drawdown calculation."""
        trade1 = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)
        trade2 = BacktestTrade("AAPL", "long", datetime(2024, 2, 1), 100.0, datetime(2024, 2, 15), 90.0)
        trade3 = BacktestTrade("AAPL", "long", datetime(2024, 3, 1), 100.0, datetime(2024, 3, 15), 120.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade1, trade2, trade3],
        )

        assert result.max_drawdown > 0

    def test_summary(self):
        """Test summary method output."""
        trade = BacktestTrade("AAPL", "long", datetime(2024, 1, 1), 100.0, datetime(2024, 1, 15), 110.0)

        result = BacktestResult(
            strategy="momentum",
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            trades=[trade],
        )

        summary = result.summary()
        assert "Backtest Results" in summary
        assert "momentum" in summary
        assert "AAPL" in summary
        assert "Total Trades: 1" in summary


class TestBacktester:
    """Tests for Backtester class."""

    def test_init(self):
        """Test Backtester initialization."""
        mock_strategy = MagicMock()
        backtester = Backtester(mock_strategy)
        assert backtester.strategy == mock_strategy

    @patch("alpacalyzer.backtesting.backtester.get_price_data")
    @patch("alpacalyzer.backtesting.backtester.TechnicalAnalyzer")
    def test_run_no_data(self, mock_ta_class, mock_get_price_data):
        """Test run method with no data available."""
        mock_get_price_data.return_value = pd.DataFrame()

        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"
        backtester = Backtester(mock_strategy)

        result = backtester.run(
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        assert result.total_trades == 0
        assert result.ticker == "AAPL"

    @patch("alpacalyzer.backtesting.backtester.get_price_data")
    @patch("alpacalyzer.backtesting.backtester.TechnicalAnalyzer")
    def test_run_with_data_always_enter(self, mock_ta_class, mock_get_price_data):
        """Test run method with a strategy that always enters."""
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [101, 102, 103],
                "volume": [1000000, 1000000, 1000000],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        mock_get_price_data.return_value = df

        mock_ta_instance = MagicMock()
        mock_ta_instance.calculate_daily_indicators.return_value = df
        mock_ta_class.return_value = mock_ta_instance

        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"
        mock_strategy.evaluate_entry.return_value = EntryDecision(
            should_enter=True,
            reason="Test entry",
            suggested_size=10,
        )
        mock_strategy.evaluate_exit.return_value = ExitDecision(
            should_exit=False,
            reason="No exit",
        )

        backtester = Backtester(mock_strategy)

        result = backtester.run(
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 3),
            initial_capital=10000.0,
        )

        assert result.total_trades >= 1

    @patch("alpacalyzer.backtesting.backtester.get_price_data")
    @patch("alpacalyzer.backtesting.backtester.TechnicalAnalyzer")
    def test_run_with_data_never_enter(self, mock_ta_class, mock_get_price_data):
        """Test run method with a strategy that never enters."""
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [101, 102, 103],
                "volume": [1000000, 1000000, 1000000],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        mock_get_price_data.return_value = df

        mock_ta_instance = MagicMock()
        mock_ta_instance.calculate_daily_indicators.return_value = df
        mock_ta_class.return_value = mock_ta_instance

        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"
        mock_strategy.evaluate_entry.return_value = EntryDecision(
            should_enter=False,
            reason="No entry signal",
        )

        backtester = Backtester(mock_strategy)

        result = backtester.run(
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 3),
        )

        assert result.total_trades == 0

    @patch("alpacalyzer.backtesting.backtester.get_price_data")
    @patch("alpacalyzer.backtesting.backtester.TechnicalAnalyzer")
    def test_run_multi(self, mock_ta_class, mock_get_price_data):
        """Test run_multi method."""
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [101, 102, 103],
                "volume": [1000000, 1000000, 1000000],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        mock_get_price_data.return_value = df

        mock_ta_instance = MagicMock()
        mock_ta_instance.calculate_daily_indicators.return_value = df
        mock_ta_class.return_value = mock_ta_instance

        mock_strategy = MagicMock()
        mock_strategy.name = "test_strategy"
        mock_strategy.evaluate_entry.return_value = EntryDecision(
            should_enter=False,
            reason="No entry",
        )

        backtester = Backtester(mock_strategy)

        results = backtester.run_multi(
            tickers=["AAPL", "MSFT"],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 3),
        )

        assert "AAPL" in results
        assert "MSFT" in results


class TestCompareStrategies:
    """Tests for compare_strategies function."""

    @patch("alpacalyzer.backtesting.backtester.get_price_data")
    @patch("alpacalyzer.backtesting.backtester.TechnicalAnalyzer")
    def test_compare_strategies(self, mock_ta_class, mock_get_price_data):
        """Test compare_strategies function."""
        df = pd.DataFrame(
            {
                "open": [100, 101, 102],
                "high": [105, 106, 107],
                "low": [99, 100, 101],
                "close": [101, 102, 103],
                "volume": [1000000, 1000000, 1000000],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        mock_get_price_data.return_value = df

        mock_ta_instance = MagicMock()
        mock_ta_instance.calculate_daily_indicators.return_value = df
        mock_ta_class.return_value = mock_ta_instance

        strategy1 = MagicMock()
        strategy1.name = "strategy1"
        strategy1.evaluate_entry.return_value = EntryDecision(
            should_enter=False,
            reason="No entry",
        )

        strategy2 = MagicMock()
        strategy2.name = "strategy2"
        strategy2.evaluate_entry.return_value = EntryDecision(
            should_enter=False,
            reason="No entry",
        )

        comparison = compare_strategies(
            strategies=[strategy1, strategy2],
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 3),
        )

        assert len(comparison) == 2
        assert "Strategy" in comparison.columns
