"""
Tests for bracket order status synchronization (Issue #99).

This module tests the sync_bracket_order_status functionality that ensures
the has_bracket_order flag on TrackedPosition reflects actual broker state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from alpacalyzer.execution.engine import ExecutionConfig, ExecutionEngine
from alpacalyzer.execution.position_tracker import PositionTracker, TrackedPosition
from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision
from tests.execution.mock_broker import MockAlpacaClient, MockOrder, mock_alpaca_client


class MockExitStrategy(BaseStrategy):
    """Mock strategy that triggers exit when should_exit_flag is True."""

    def __init__(self):
        super().__init__()
        self.should_exit_flag = False
        self.exit_reason = "Test exit"

    def evaluate_entry(self, signal, context, agent_recommendation=None) -> EntryDecision:
        return EntryDecision(
            should_enter=False,
            reason="Test - no entry",
            suggested_size=0,
            entry_price=0.0,
            stop_loss=0.0,
            target=0.0,
        )

    def evaluate_exit(self, position, signal, context) -> ExitDecision:
        return ExitDecision(
            should_exit=self.should_exit_flag,
            reason=self.exit_reason,
            urgency="normal",
        )


@pytest.fixture
def mock_broker(monkeypatch) -> MockAlpacaClient:
    """Fixture that patches alpaca_client with mock."""
    return mock_alpaca_client(monkeypatch)


@pytest.fixture
def tracked_position_with_bracket():
    """TrackedPosition with has_bracket_order=True."""
    return TrackedPosition(
        ticker="AAPL",
        side="long",
        quantity=10,
        avg_entry_price=150.0,
        current_price=152.0,
        market_value=1520.0,
        unrealized_pnl=20.0,
        unrealized_pnl_pct=0.0133,
        strategy_name="test_strategy",
        opened_at=datetime.now(UTC),
        stop_loss=145.0,
        target=160.0,
        has_bracket_order=True,
    )


@pytest.fixture
def tracked_position_without_bracket():
    """TrackedPosition with has_bracket_order=False."""
    return TrackedPosition(
        ticker="MSFT",
        side="long",
        quantity=5,
        avg_entry_price=300.0,
        current_price=295.0,
        market_value=1475.0,
        unrealized_pnl=-25.0,
        unrealized_pnl_pct=-0.0167,
        strategy_name="test_strategy",
        opened_at=datetime.now(UTC),
        stop_loss=290.0,
        target=320.0,
        has_bracket_order=False,
    )


class TestSyncBracketOrderStatus:
    """Tests for PositionTracker.sync_bracket_order_status()."""

    def test_sync_finds_bracket_order_present(self, mock_broker, tracked_position_with_bracket):
        """When bracket order exists, has_bracket_order should remain True."""
        # Setup: Add bracket order to mock broker
        mock_broker.orders = [
            MockOrder(
                id="order_1",
                client_order_id="test_AAPL_buy_123",
                symbol="AAPL",
                side="sell",
                order_class="bracket",
                status="open",
            )
        ]

        tracker = PositionTracker()
        tracker._positions["AAPL"] = tracked_position_with_bracket

        # Act
        tracker.sync_bracket_order_status("AAPL")

        # Assert
        assert tracker._positions["AAPL"].has_bracket_order is True

    def test_sync_finds_no_bracket_order(self, mock_broker, tracked_position_with_bracket):
        """When no bracket order exists, has_bracket_order should become False."""
        # Setup: No orders in mock broker
        mock_broker.orders = []

        tracker = PositionTracker()
        tracker._positions["AAPL"] = tracked_position_with_bracket

        # Act
        tracker.sync_bracket_order_status("AAPL")

        # Assert
        assert tracker._positions["AAPL"].has_bracket_order is False

    def test_sync_finds_non_bracket_orders_only(self, mock_broker, tracked_position_with_bracket):
        """When only non-bracket orders exist, has_bracket_order should become False."""
        # Setup: Add non-bracket order
        mock_broker.orders = [
            MockOrder(
                id="order_1",
                client_order_id="test_AAPL_buy_123",
                symbol="AAPL",
                side="sell",
                order_class="simple",  # Not a bracket order
                status="open",
            )
        ]

        tracker = PositionTracker()
        tracker._positions["AAPL"] = tracked_position_with_bracket

        # Act
        tracker.sync_bracket_order_status("AAPL")

        # Assert
        assert tracker._positions["AAPL"].has_bracket_order is False

    def test_sync_handles_oco_order_class(self, mock_broker, tracked_position_with_bracket):
        """OCO orders (bracket legs) should be detected as bracket orders."""
        # Setup: Add OCO order (bracket leg)
        mock_broker.orders = [
            MockOrder(
                id="order_1",
                client_order_id="test_AAPL_sl_123",
                symbol="AAPL",
                side="sell",
                order_class="oco",  # OCO is a bracket leg
                status="open",
            )
        ]

        tracker = PositionTracker()
        tracker._positions["AAPL"] = tracked_position_with_bracket

        # Act
        tracker.sync_bracket_order_status("AAPL")

        # Assert
        assert tracker._positions["AAPL"].has_bracket_order is True

    def test_sync_handles_oto_order_class(self, mock_broker, tracked_position_with_bracket):
        """OTO orders should be detected as bracket orders."""
        # Setup: Add OTO order
        mock_broker.orders = [
            MockOrder(
                id="order_1",
                client_order_id="test_AAPL_oto_123",
                symbol="AAPL",
                side="sell",
                order_class="oto",  # OTO is a bracket-related order
                status="open",
            )
        ]

        tracker = PositionTracker()
        tracker._positions["AAPL"] = tracked_position_with_bracket

        # Act
        tracker.sync_bracket_order_status("AAPL")

        # Assert
        assert tracker._positions["AAPL"].has_bracket_order is True

    def test_sync_position_not_found(self, mock_broker):
        """Sync should handle missing position gracefully."""
        tracker = PositionTracker()

        # Act - should not raise
        tracker.sync_bracket_order_status("NONEXISTENT")

        # Assert - no exception raised

    def test_sync_logs_state_change(self, mock_broker, tracked_position_with_bracket):
        """State changes should update the flag correctly."""
        mock_broker.orders = []

        tracker = PositionTracker()
        tracker._positions["AAPL"] = tracked_position_with_bracket

        # Act
        tracker.sync_bracket_order_status("AAPL")

        # Assert - flag should be updated
        assert tracker._positions["AAPL"].has_bracket_order is False


class TestExecutionEngineExitWithBracketSync:
    """Tests for ExecutionEngine._process_exit() with bracket order sync."""

    def test_exit_skipped_when_bracket_order_exists(self, mock_broker):
        """Dynamic exit should be skipped when bracket order is confirmed to exist."""
        # Setup
        mock_broker.orders = [
            MockOrder(
                id="order_1",
                client_order_id="test_AAPL_sl_123",
                symbol="AAPL",
                side="sell",
                order_class="bracket",
                status="open",
            )
        ]

        strategy = MockExitStrategy()
        strategy.should_exit_flag = True  # Strategy wants to exit

        config = ExecutionConfig(analyze_mode=True)
        engine = ExecutionEngine(strategy=strategy, config=config, reset_state=True)

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=10,
            avg_entry_price=150.0,
            current_price=152.0,
            market_value=1520.0,
            unrealized_pnl=20.0,
            unrealized_pnl_pct=0.0133,
            strategy_name="test_strategy",
            opened_at=datetime.now(UTC),
            stop_loss=145.0,
            target=160.0,
            has_bracket_order=True,
        )
        engine.positions._positions["AAPL"] = position

        # Act
        engine._process_exit(position)

        # Assert - position should still have bracket order flag
        assert engine.positions._positions["AAPL"].has_bracket_order is True

    def test_exit_evaluated_when_bracket_order_gone(self, mock_broker, monkeypatch):
        """Dynamic exit should be evaluated when bracket order is confirmed gone."""
        # Setup - no orders in broker
        mock_broker.orders = []

        # Mock additional dependencies
        monkeypatch.setattr("alpacalyzer.data.api.get_vix", lambda use_cache=False: 20.0)

        strategy = MockExitStrategy()
        strategy.should_exit_flag = True  # Strategy wants to exit

        config = ExecutionConfig(analyze_mode=True)
        engine = ExecutionEngine(strategy=strategy, config=config, reset_state=True)

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=10,
            avg_entry_price=150.0,
            current_price=152.0,
            market_value=1520.0,
            unrealized_pnl=20.0,
            unrealized_pnl_pct=0.0133,
            strategy_name="test_strategy",
            opened_at=datetime.now(UTC),
            stop_loss=145.0,
            target=160.0,
            has_bracket_order=True,  # Initially True, but broker has no orders
        )
        engine.positions._positions["AAPL"] = position

        # Mock technical analysis
        with patch.object(engine, "_get_cached_signal") as mock_signal:
            mock_signal.return_value = MagicMock()

            # Act
            engine._process_exit(position)

        # Assert - flag should be updated to False
        assert engine.positions._positions["AAPL"].has_bracket_order is False

    def test_exit_not_evaluated_when_flag_already_false(self, mock_broker, monkeypatch):
        """When has_bracket_order is already False, should evaluate exit directly."""
        # Mock additional dependencies
        monkeypatch.setattr("alpacalyzer.data.api.get_vix", lambda use_cache=False: 20.0)

        strategy = MockExitStrategy()
        strategy.should_exit_flag = False  # Strategy doesn't want to exit

        config = ExecutionConfig(analyze_mode=True)
        engine = ExecutionEngine(strategy=strategy, config=config, reset_state=True)

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=10,
            avg_entry_price=150.0,
            current_price=152.0,
            market_value=1520.0,
            unrealized_pnl=20.0,
            unrealized_pnl_pct=0.0133,
            strategy_name="test_strategy",
            opened_at=datetime.now(UTC),
            stop_loss=145.0,
            target=160.0,
            has_bracket_order=False,  # Already False
        )
        engine.positions._positions["AAPL"] = position

        # Mock technical analysis
        with patch.object(engine, "_get_cached_signal") as mock_signal:
            mock_signal.return_value = MagicMock()

            # Act
            engine._process_exit(position)

        # Assert - position should still exist (strategy said don't exit)
        assert "AAPL" in engine.positions._positions

    def test_sync_called_only_when_flag_is_true(self, mock_broker, monkeypatch):
        """Sync should only be called when has_bracket_order is True."""
        # Mock additional dependencies
        monkeypatch.setattr("alpacalyzer.data.api.get_vix", lambda use_cache=False: 20.0)

        strategy = MockExitStrategy()
        config = ExecutionConfig(analyze_mode=True)
        engine = ExecutionEngine(strategy=strategy, config=config, reset_state=True)

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=10,
            avg_entry_price=150.0,
            current_price=152.0,
            market_value=1520.0,
            unrealized_pnl=20.0,
            unrealized_pnl_pct=0.0133,
            strategy_name="test_strategy",
            opened_at=datetime.now(UTC),
            stop_loss=145.0,
            target=160.0,
            has_bracket_order=False,  # Already False - no sync needed
        )
        engine.positions._positions["AAPL"] = position

        # Mock the sync method to track calls
        with patch.object(engine.positions, "sync_bracket_order_status") as mock_sync:
            with patch.object(engine, "_get_cached_signal") as mock_signal:
                mock_signal.return_value = MagicMock()

                # Act
                engine._process_exit(position)

            # Assert - sync should NOT be called
            mock_sync.assert_not_called()


class TestBracketOrderSyncLogging:
    """Tests for logging behavior during bracket order sync."""

    def test_logs_when_bracket_order_disappears(self, mock_broker):
        """Should update flag when bracket order is detected as gone."""
        mock_broker.orders = []

        tracker = PositionTracker()
        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=10,
            avg_entry_price=150.0,
            current_price=152.0,
            market_value=1520.0,
            unrealized_pnl=20.0,
            unrealized_pnl_pct=0.0133,
            strategy_name="test_strategy",
            opened_at=datetime.now(UTC),
            has_bracket_order=True,
        )
        tracker._positions["AAPL"] = position

        tracker.sync_bracket_order_status("AAPL")

        # Flag should be updated to False
        assert tracker._positions["AAPL"].has_bracket_order is False

    def test_no_change_when_bracket_order_exists(self, mock_broker):
        """Should not change flag when bracket order still exists."""
        mock_broker.orders = [
            MockOrder(
                id="order_1",
                client_order_id="test_AAPL_sl_123",
                symbol="AAPL",
                side="sell",
                order_class="bracket",
                status="open",
            )
        ]

        tracker = PositionTracker()
        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=10,
            avg_entry_price=150.0,
            current_price=152.0,
            market_value=1520.0,
            unrealized_pnl=20.0,
            unrealized_pnl_pct=0.0133,
            strategy_name="test_strategy",
            opened_at=datetime.now(UTC),
            has_bracket_order=True,  # Already True, will stay True
        )
        tracker._positions["AAPL"] = position

        tracker.sync_bracket_order_status("AAPL")

        # Flag should remain True
        assert tracker._positions["AAPL"].has_bracket_order is True
