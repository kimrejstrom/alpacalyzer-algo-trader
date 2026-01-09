"""Tests for PositionTracker."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from alpaca.trading.enums import AssetClass, AssetExchange, PositionSide

from alpacalyzer.execution.position_tracker import PositionTracker, TrackedPosition


@pytest.fixture
def sample_position():
    """Create a sample Alpaca Position."""
    pos = MagicMock()
    pos.asset_id = "test_asset_id"
    pos.symbol = "AAPL"
    pos.exchange = AssetExchange.NASDAQ
    pos.asset_class = AssetClass.US_EQUITY
    pos.avg_entry_price = "150.0"
    pos.qty = "10"
    pos.side = PositionSide.LONG
    pos.market_value = "1500.0"
    pos.cost_basis = "1500.0"
    pos.unrealized_pl = "0.0"
    pos.unrealized_plpc = "0.0"
    pos.unrealized_intraday_pl = "0.0"
    pos.unrealized_intraday_plpc = "0.0"
    pos.current_price = "150.0"
    pos.lastday_price = "150.0"
    pos.change_today = "0.0"
    return pos


class TestPositionTracker:
    def test_initial_state_empty(self):
        """Tracker starts with no positions."""
        tracker = PositionTracker()
        assert tracker.get_all() == []
        assert tracker.get("AAPL") is None
        assert tracker.count() == 0

    def test_add_position(self, sample_position):
        """Can add a position to tracker."""
        tracker = PositionTracker()
        tracker.add(sample_position)

        tracked = tracker.get("AAPL")
        assert tracked is not None
        assert tracked.ticker == "AAPL"
        assert tracked.quantity == 10
        assert tracked.entry_price == 150.0

    def test_add_multiple_positions(self, sample_position):
        """Can add multiple positions."""
        tracker = PositionTracker()

        aapl_pos = sample_position
        msft_pos = MagicMock()
        msft_pos.asset_id = "test_asset_id_2"
        msft_pos.symbol = "MSFT"
        msft_pos.exchange = AssetExchange.NASDAQ
        msft_pos.asset_class = AssetClass.US_EQUITY
        msft_pos.avg_entry_price = "300.0"
        msft_pos.qty = "5"
        msft_pos.side = PositionSide.LONG
        msft_pos.market_value = "1500.0"
        msft_pos.cost_basis = "1500.0"
        msft_pos.unrealized_pl = "0.0"
        msft_pos.unrealized_plpc = "0.0"
        msft_pos.unrealized_intraday_pl = "0.0"
        msft_pos.unrealized_intraday_plpc = "0.0"
        msft_pos.current_price = "300.0"
        msft_pos.lastday_price = "300.0"
        msft_pos.change_today = "0.0"

        tracker.add(aapl_pos)
        tracker.add(msft_pos)

        assert tracker.count() == 2
        assert tracker.get("AAPL") is not None
        assert tracker.get("MSFT") is not None

    def test_remove_position(self, sample_position):
        """Can remove a position."""
        tracker = PositionTracker()
        tracker.add(sample_position)
        assert tracker.count() == 1

        removed = tracker.remove("AAPL")
        assert removed is True
        assert tracker.count() == 0
        assert tracker.get("AAPL") is None

    def test_remove_nonexistent_position(self):
        """Removing nonexistent position returns False."""
        tracker = PositionTracker()
        removed = tracker.remove("NONEXISTENT")
        assert removed is False

    def test_clear_all_positions(self, sample_position):
        """Can clear all positions."""
        tracker = PositionTracker()
        tracker.add(sample_position)
        assert tracker.count() == 1

        tracker.clear()
        assert tracker.count() == 0
        assert tracker.get_all() == []

    def test_get_existing_tickers(self, sample_position):
        """Get list of ticker symbols."""
        tracker = PositionTracker()
        tracker.add(sample_position)

        tickers = tracker.get_tickers()
        assert tickers == ["AAPL"]

    def test_has_position(self, sample_position):
        """Check if tracker has position for ticker."""
        tracker = PositionTracker()
        assert tracker.has("AAPL") is False

        tracker.add(sample_position)
        assert tracker.has("AAPL") is True
        assert tracker.has("MSFT") is False

    def test_update_position_pnl(self, sample_position):
        """Can update P&L for a position."""
        tracker = PositionTracker()
        tracker.add(sample_position)

        tracker.update_pnl("AAPL", unrealized_pl=50.0, unrealized_plpc=3.33)

        tracked = tracker.get("AAPL")
        assert tracked is not None
        assert tracked.unrealized_pl == 50.0
        assert tracked.unrealized_plpc == 3.33

    def test_sync_from_broker_empty(self, monkeypatch):
        """Sync with empty broker positions."""

        def mock_get_all_positions():
            return []

        monkeypatch.setattr(
            "alpacalyzer.execution.position_tracker.trading_client.get_all_positions",
            mock_get_all_positions,
        )

        tracker = PositionTracker()
        tracker.sync_from_broker()

        assert tracker.count() == 0

    def test_sync_from_broker_with_positions(self, monkeypatch, sample_position):
        """Sync positions from broker."""

        def mock_get_all_positions():
            return [sample_position]

        monkeypatch.setattr(
            "alpacalyzer.execution.position_tracker.trading_client.get_all_positions",
            mock_get_all_positions,
        )

        tracker = PositionTracker()
        tracker.sync_from_broker()

        assert tracker.count() == 1
        tracked = tracker.get("AAPL")
        assert tracked is not None
        assert tracked.ticker == "AAPL"


def test_sync_replaces_existing_positions(monkeypatch, sample_position):
    """Sync replaces existing positions with fresh data."""

    def mock_get_all_positions():
        return [sample_position]

    def mock_get_all_positions_v2():
        updated_pos = MagicMock()
        updated_pos.asset_id = "test_asset_id"
        updated_pos.symbol = "AAPL"
        updated_pos.exchange = AssetExchange.NASDAQ
        updated_pos.asset_class = AssetClass.US_EQUITY
        updated_pos.avg_entry_price = "150.0"
        updated_pos.qty = "8"  # Changed from 10
        updated_pos.side = PositionSide.LONG
        updated_pos.market_value = "1200.0"
        updated_pos.cost_basis = "1200.0"
        updated_pos.unrealized_pl = "-100.0"  # Loss
        updated_pos.unrealized_plpc = "-7.69"
        updated_pos.unrealized_intraday_pl = "-50.0"
        updated_pos.unrealized_intraday_plpc = "-4.0"
        updated_pos.current_price = "149.0"
        updated_pos.lastday_price = "150.0"
        updated_pos.change_today = "-1.0"
        return [updated_pos]

    monkeypatch.setattr(
        "alpacalyzer.execution.position_tracker.trading_client.get_all_positions",
        mock_get_all_positions,
    )

    tracker = PositionTracker()
    tracker.sync_from_broker()
    assert tracker.get("AAPL").quantity == 10

    # Update mock to return different data
    monkeypatch.setattr(
        "alpacalyzer.execution.position_tracker.trading_client.get_all_positions",
        mock_get_all_positions_v2,
    )

    tracker.sync_from_broker()
    assert tracker.get("AAPL").quantity == 8
    assert tracker.get("AAPL").unrealized_pl == -100.0


class TestTrackedPosition:
    def test_creation_from_alpaca_position(self, sample_position):
        """Create TrackedPosition from Alpaca Position."""
        tracked = TrackedPosition.from_alpaca_position(sample_position)

        assert tracked.ticker == "AAPL"
        assert tracked.quantity == 10
        assert tracked.entry_price == 150.0
        assert tracked.current_price == 150.0
        assert tracked.unrealized_pl == 0.0
        assert tracked.side == "long"

    def test_creation_short_position(self):
        """Create TrackedPosition for short position."""
        short_pos = MagicMock()
        short_pos.asset_id = "test_asset_id"
        short_pos.symbol = "TSLA"
        short_pos.exchange = AssetExchange.NASDAQ
        short_pos.asset_class = AssetClass.US_EQUITY
        short_pos.avg_entry_price = "200.0"
        short_pos.qty = "-5"  # Negative for short
        short_pos.side = PositionSide.SHORT
        short_pos.market_value = "-1000.0"
        short_pos.cost_basis = "-1000.0"
        short_pos.unrealized_pl = "0.0"
        short_pos.unrealized_plpc = "0.0"
        short_pos.unrealized_intraday_pl = "0.0"
        short_pos.unrealized_intraday_plpc = "0.0"
        short_pos.current_price = "200.0"
        short_pos.lastday_price = "200.0"
        short_pos.change_today = "0.0"

        tracked = TrackedPosition.from_alpaca_position(short_pos)

        assert tracked.ticker == "TSLA"
        assert tracked.quantity == -5
        assert tracked.side == "short"

    def test_tracked_position_has_entry_time(self):
        """TrackedPosition records when it was added."""
        before = datetime.now(UTC)
        tracked = TrackedPosition(
            ticker="AAPL",
            quantity=10,
            entry_price=150.0,
            current_price=150.0,
            unrealized_pl=0.0,
            unrealized_plpc=0.0,
            side="long",
            entry_time=datetime.now(UTC),
        )
        after = datetime.now(UTC)

        assert before <= tracked.entry_time <= after
