"""Tests for PositionTracker module."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from alpaca.trading.models import Position


class TestTrackedPosition:
    """Tests for TrackedPosition dataclass."""

    def test_tracked_position_creation(self):
        """Test creating a TrackedPosition."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        entry_time = datetime(2026, 1, 9, 18, 38, 36, 382349, tzinfo=UTC)
        position = TrackedPosition(
            ticker="AAPL",
            quantity=100,
            entry_price=150.0,
            current_price=155.0,
            unrealized_pl=500.0,
            unrealized_plpc=0.0333,
            side="long",
            entry_time=entry_time,
        )

        assert position.ticker == "AAPL"
        assert position.quantity == 100
        assert position.entry_price == 150.0
        assert position.current_price == 155.0
        assert position.unrealized_pl == 500.0
        assert position.unrealized_plpc == 0.0333
        assert position.side == "long"
        assert position.entry_time == entry_time

    def test_from_alpaca_position_long(self):
        """Test creating TrackedPosition from Alpaca Position (long)."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"

        tracked = TrackedPosition.from_alpaca_position(mock_position)

        assert tracked.ticker == "AAPL"
        assert tracked.side == "long"
        assert tracked.quantity == 100
        assert tracked.entry_price == 150.0
        assert tracked.current_price == 155.0
        assert tracked.unrealized_pl == 500.0
        assert tracked.unrealized_plpc == 0.0333

    def test_from_alpaca_position_short(self):
        """Test creating TrackedPosition from Alpaca Position (short)."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "short"
        mock_position.qty = "50"
        mock_position.avg_entry_price = "200.0"
        mock_position.current_price = "195.0"
        mock_position.unrealized_pl = "250.0"
        mock_position.unrealized_plpc = "0.025"

        tracked = TrackedPosition.from_alpaca_position(mock_position)

        assert tracked.ticker == "AAPL"
        assert tracked.side == "short"
        assert tracked.quantity == 50
        assert tracked.entry_price == 200.0
        assert tracked.current_price == 195.0
        assert tracked.unrealized_pl == 250.0
        assert tracked.unrealized_plpc == 0.025

    def test_from_alpaca_position_missing_fields(self):
        """Test handling missing fields from Alpaca Position."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = None
        mock_position.unrealized_pl = None
        mock_position.unrealized_plpc = None

        tracked = TrackedPosition.from_alpaca_position(mock_position)

        assert tracked.ticker == "AAPL"
        assert tracked.quantity == 100
        assert tracked.entry_price == 150.0
        assert tracked.current_price == 0.0
        assert tracked.unrealized_pl == 0.0
        assert tracked.unrealized_plpc == 0.0


class TestPositionTracker:
    """Tests for PositionTracker class."""

    def test_position_tracker_creation(self):
        """Test PositionTracker initialization."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        assert tracker.count() == 0
        assert tracker.get_all() == []
        assert not tracker.has("AAPL")

    def test_add_position(self):
        """Test adding a position to tracker."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"

        tracker = PositionTracker()
        tracker.add(mock_position)

        assert tracker.count() == 1
        assert tracker.has("AAPL")

        position = tracker.get("AAPL")
        assert position is not None
        assert position.ticker == "AAPL"

    def test_get_position(self):
        """Test getting a position by ticker."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "MSFT"
        mock_position.side = "long"
        mock_position.qty = "50"
        mock_position.avg_entry_price = "250.0"
        mock_position.current_price = "255.0"
        mock_position.unrealized_pl = "250.0"
        mock_position.unrealized_plpc = "0.02"

        tracker = PositionTracker()
        tracker.add(mock_position)

        position = tracker.get("MSFT")
        assert position is not None
        assert position.ticker == "MSFT"

        nonexistent = tracker.get("NONEXISTENT")
        assert nonexistent is None

    def test_get_all_positions(self):
        """Test getting all positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            mock_position = MagicMock(spec=Position)
            mock_position.symbol = ticker
            mock_position.side = "long"
            mock_position.qty = "100"
            mock_position.avg_entry_price = "150.0"
            mock_position.current_price = "155.0"
            mock_position.unrealized_pl = "500.0"
            mock_position.unrealized_plpc = "0.0333"
            tracker.add(mock_position)

        positions = tracker.get_all()
        assert len(positions) == 3
        assert {p.ticker for p in positions} == {"AAPL", "MSFT", "GOOGL"}

    def test_remove_position(self):
        """Test removing a position."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"

        tracker = PositionTracker()
        tracker.add(mock_position)

        assert tracker.count() == 1
        assert tracker.has("AAPL")

        removed = tracker.remove("AAPL")
        assert removed is True
        assert tracker.count() == 0
        assert not tracker.has("AAPL")

    def test_remove_nonexistent_position(self):
        """Test removing a nonexistent position."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        removed = tracker.remove("NONEXISTENT")
        assert removed is False

    def test_clear(self):
        """Test clearing all positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"
        tracker.add(mock_position)

        assert tracker.count() == 1

        tracker.clear()

        assert tracker.count() == 0
        assert tracker.get_all() == []

    def test_count(self):
        """Test counting positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        assert tracker.count() == 0

        for i in range(3):
            mock_position = MagicMock(spec=Position)
            mock_position.symbol = f"TICKER{i}"
            mock_position.side = "long"
            mock_position.qty = "100"
            mock_position.avg_entry_price = "150.0"
            mock_position.current_price = "155.0"
            mock_position.unrealized_pl = "500.0"
            mock_position.unrealized_plpc = "0.0333"
            tracker.add(mock_position)

        assert tracker.count() == 3

    def test_get_tickers(self):
        """Test getting list of tickers."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"
        tracker.add(mock_position)

        tickers = tracker.get_tickers()
        assert tickers == ["AAPL"]

    def test_has(self):
        """Test checking if tracker has a position."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        assert not tracker.has("AAPL")

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"
        tracker.add(mock_position)

        assert tracker.has("AAPL")
        assert not tracker.has("NONEXISTENT")

    def test_sync_from_broker(self):
        """Test syncing positions from broker."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        mock_positions = [
            MagicMock(spec=Position),
            MagicMock(spec=Position),
        ]
        mock_positions[0].symbol = "AAPL"
        mock_positions[0].side = "long"
        mock_positions[0].qty = "100"
        mock_positions[0].avg_entry_price = "150.0"
        mock_positions[0].current_price = "155.0"
        mock_positions[0].unrealized_pl = "500.0"
        mock_positions[0].unrealized_plpc = "0.0333"

        mock_positions[1].symbol = "MSFT"
        mock_positions[1].side = "long"
        mock_positions[1].qty = "50"
        mock_positions[1].avg_entry_price = "250.0"
        mock_positions[1].current_price = "255.0"
        mock_positions[1].unrealized_pl = "250.0"
        mock_positions[1].unrealized_plpc = "0.02"

        with patch(
            "alpacalyzer.execution.position_tracker.trading_client.get_all_positions",
            return_value=mock_positions,
        ):
            tracker = PositionTracker()
            tracker.sync_from_broker()

            assert tracker.count() == 2
            assert tracker.has("AAPL")
            assert tracker.has("MSFT")

    def test_get_active_tickers(self):
        """Test getting active tickers."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        for ticker in ["AAPL", "MSFT"]:
            mock_position = MagicMock(spec=Position)
            mock_position.symbol = ticker
            mock_position.side = "long"
            mock_position.qty = "100"
            mock_position.avg_entry_price = "150.0"
            mock_position.current_price = "155.0"
            mock_position.unrealized_pl = "500.0"
            mock_position.unrealized_plpc = "0.0333"
            tracker.add(mock_position)

        tickers = tracker.get_tickers()
        assert sorted(tickers) == ["AAPL", "MSFT"]
