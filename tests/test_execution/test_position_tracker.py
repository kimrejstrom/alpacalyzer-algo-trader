"""Tests for PositionTracker module."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from alpaca.trading.models import Position


class TestTrackedPosition:
    """Tests for TrackedPosition dataclass."""

    def test_tracked_position_creation(self):
        """Test creating a TrackedPosition."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=100,
            avg_entry_price=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            unrealized_pnl_pct=0.0333,
            strategy_name="momentum",
            opened_at=datetime.now(UTC),
            entry_order_id="order_123",
            stop_loss=145.0,
            target=165.0,
        )

        assert position.ticker == "AAPL"
        assert position.side == "long"
        assert position.quantity == 100
        assert position.avg_entry_price == 150.0
        assert position.current_price == 155.0
        assert position.market_value == 15500.0
        assert position.unrealized_pnl == 500.0
        assert position.strategy_name == "momentum"
        assert position.stop_loss == 145.0
        assert position.target == 165.0

    def test_tracked_position_defaults(self):
        """Test TrackedPosition default values."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=100,
            avg_entry_price=150.0,
            current_price=150.0,
            market_value=15000.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            strategy_name="momentum",
            opened_at=datetime.now(UTC),
        )

        assert position.entry_order_id is None
        assert position.stop_loss is None
        assert position.target is None
        assert position.exit_attempts == 0
        assert position.last_exit_attempt is None
        assert position.notes == []

    def test_from_alpaca_position_long(self):
        """Test creating TrackedPosition from Alpaca Position (long)."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.market_value = "15500.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"

        tracked = TrackedPosition.from_alpaca_position(
            mock_position,
            strategy_name="momentum",
            opened_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            stop_loss=145.0,
            target=165.0,
        )

        assert tracked.ticker == "AAPL"
        assert tracked.side == "long"
        assert tracked.quantity == 100
        assert tracked.avg_entry_price == 150.0
        assert tracked.current_price == 155.0
        assert tracked.market_value == 15500.0
        assert tracked.unrealized_pnl == 500.0
        assert tracked.unrealized_pnl_pct == 0.0333
        assert tracked.strategy_name == "momentum"
        assert tracked.opened_at == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        assert tracked.stop_loss == 145.0
        assert tracked.target == 165.0

    def test_from_alpaca_position_short(self):
        """Test creating TrackedPosition from Alpaca Position (short)."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "TSLA"
        mock_position.side = "short"
        mock_position.qty = "50"
        mock_position.avg_entry_price = "200.0"
        mock_position.current_price = "195.0"
        mock_position.market_value = "9750.0"
        mock_position.unrealized_pl = "250.0"
        mock_position.unrealized_plpc = "0.025"

        tracked = TrackedPosition.from_alpaca_position(
            mock_position,
            strategy_name="momentum",
        )

        assert tracked.ticker == "TSLA"
        assert tracked.side == "short"
        assert tracked.quantity == 50
        assert tracked.avg_entry_price == 200.0
        assert tracked.current_price == 195.0

    def test_from_alpaca_position_missing_optional_fields(self):
        """Test from_alpaca_position handles missing optional fields."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = None
        mock_position.market_value = None
        mock_position.unrealized_pl = None
        mock_position.unrealized_plpc = None

        tracked = TrackedPosition.from_alpaca_position(mock_position)

        assert tracked.current_price == 150.0
        assert tracked.market_value == 15000.0
        assert tracked.unrealized_pnl == 0.0
        assert tracked.unrealized_pnl_pct == 0.0

    def test_update_price_long(self):
        """Test update_price for long position."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=100,
            avg_entry_price=150.0,
            current_price=150.0,
            market_value=15000.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            strategy_name="momentum",
            opened_at=datetime.now(UTC),
        )

        position.update_price(160.0)

        assert position.current_price == 160.0
        assert position.market_value == 16000.0
        assert position.unrealized_pnl == 1000.0
        assert abs(position.unrealized_pnl_pct - 0.0667) < 0.0001

    def test_update_price_short(self):
        """Test update_price for short position."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        position = TrackedPosition(
            ticker="TSLA",
            side="short",
            quantity=50,
            avg_entry_price=200.0,
            current_price=200.0,
            market_value=10000.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            strategy_name="momentum",
            opened_at=datetime.now(UTC),
        )

        position.update_price(190.0)

        assert position.current_price == 190.0
        assert position.market_value == 9500.0
        assert position.unrealized_pnl == 500.0

    def test_update_price_zero_entry(self):
        """Test update_price handles zero entry price."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=100,
            avg_entry_price=0.0,
            current_price=0.0,
            market_value=0.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            strategy_name="momentum",
            opened_at=datetime.now(UTC),
        )

        position.update_price(150.0)

        assert position.current_price == 150.0
        assert position.unrealized_pnl_pct == 0.0

    def test_record_exit_attempt(self):
        """Test record_exit_attempt increments counter and adds note."""
        from alpacalyzer.execution.position_tracker import TrackedPosition

        position = TrackedPosition(
            ticker="AAPL",
            side="long",
            quantity=100,
            avg_entry_price=150.0,
            current_price=150.0,
            market_value=15000.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            strategy_name="momentum",
            opened_at=datetime.now(UTC),
        )

        position.record_exit_attempt("Stop loss hit")

        assert position.exit_attempts == 1
        assert position.last_exit_attempt is not None
        assert len(position.notes) == 1
        assert "Exit attempt 1: Stop loss hit" in position.notes[0]

        position.record_exit_attempt("Target reached")

        assert position.exit_attempts == 2
        assert len(position.notes) == 2
        assert "Exit attempt 2: Target reached" in position.notes[1]


class TestPositionTracker:
    """Tests for PositionTracker class."""

    def test_position_tracker_creation(self):
        """Test creating a PositionTracker."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        assert tracker.count() == 0
        assert tracker.total_value() == 0.0
        assert tracker.total_pnl() == 0.0
        assert tracker.get_all() == []
        assert tracker._last_sync is None

    def test_add_position(self):
        """Test adding a new position."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        opened_at = datetime.now(UTC)

        position = tracker.add_position(
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            strategy_name="momentum",
            order_id="order_123",
            stop_loss=145.0,
            target=165.0,
        )

        assert position.ticker == "AAPL"
        assert position.side == "long"
        assert position.quantity == 100
        assert position.avg_entry_price == 150.0
        assert position.strategy_name == "momentum"
        assert position.entry_order_id == "order_123"
        assert position.stop_loss == 145.0
        assert position.target == 165.0
        assert position.opened_at >= opened_at

        assert tracker.count() == 1
        assert tracker.has_position("AAPL") is True

    def test_add_position_minimal(self):
        """Test adding position with minimal parameters."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        position = tracker.add_position(
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            strategy_name="momentum",
        )

        assert position.entry_order_id is None
        assert position.stop_loss is None
        assert position.target is None

    def test_remove_position(self):
        """Test removing a position."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")

        removed = tracker.remove_position("AAPL")

        assert removed is not None
        assert removed.ticker == "AAPL"
        assert tracker.count() == 0
        assert tracker.has_position("AAPL") is False

    def test_remove_nonexistent_position(self):
        """Test removing a position that doesn't exist."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        removed = tracker.remove_position("AAPL")

        assert removed is None
        assert tracker.count() == 0

    def test_remove_position_moves_to_history(self):
        """Test that removed positions are moved to history."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="momentum")

        tracker.remove_position("AAPL")

        assert tracker.count() == 1
        closed = tracker.get_closed_positions()
        assert len(closed) == 1
        assert closed[0].ticker == "AAPL"

    def test_get_position(self):
        """Test getting a position by ticker."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")

        position = tracker.get("AAPL")

        assert position is not None
        assert position.ticker == "AAPL"

    def test_get_nonexistent_position(self):
        """Test getting a position that doesn't exist."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()

        position = tracker.get("AAPL")

        assert position is None

    def test_get_all_positions(self):
        """Test getting all positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")
        tracker.add_position(ticker="TSLA", side="short", quantity=25, entry_price=200.0, strategy_name="momentum")

        positions = tracker.get_all()

        assert len(positions) == 3
        tickers = {p.ticker for p in positions}
        assert tickers == {"AAPL", "MSFT", "TSLA"}

    def test_get_by_strategy(self):
        """Test filtering positions by strategy."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")
        tracker.add_position(ticker="TSLA", side="short", quantity=25, entry_price=200.0, strategy_name="momentum")

        momentum_positions = tracker.get_by_strategy("momentum")

        assert len(momentum_positions) == 2
        tickers = {p.ticker for p in momentum_positions}
        assert tickers == {"AAPL", "TSLA"}

    def test_has_position(self):
        """Test checking if a ticker has a position."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")

        assert tracker.has_position("AAPL") is True
        assert tracker.has_position("MSFT") is False

    def test_count(self):
        """Test counting open positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        assert tracker.count() == 0

        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        assert tracker.count() == 1

        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")
        assert tracker.count() == 2

    def test_total_value(self):
        """Test calculating total market value."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")

        total = tracker.total_value()

        assert total == 15000.0 + 15000.0

    def test_total_pnl(self):
        """Test calculating total unrealized P&L."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        pos1 = tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        pos2 = tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")

        pos1.update_price(160.0)
        pos2.update_price(290.0)

        total = tracker.total_pnl()

        assert total == 1000.0 + (-500.0)

    def test_get_closed_positions(self):
        """Test getting closed positions history."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")
        tracker.add_position(ticker="TSLA", side="short", quantity=25, entry_price=200.0, strategy_name="hedge")

        tracker.remove_position("AAPL")
        tracker.remove_position("TSLA")

        closed = tracker.get_closed_positions()

        assert len(closed) == 2
        tickers = [p.ticker for p in closed]
        assert tickers == ["AAPL", "TSLA"]

    def test_get_closed_positions_with_limit(self):
        """Test get_closed_positions with limit parameter."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        for i in range(5):
            tracker.add_position(ticker=f"STK{i}", side="long", quantity=100, entry_price=100.0, strategy_name="test")
            tracker.remove_position(f"STK{i}")

        closed = tracker.get_closed_positions(limit=3)

        assert len(closed) == 3

    def test_sync_from_broker_new_positions(self):
        """Test sync_from_broker adds new positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        mock_position1 = MagicMock(spec=Position)
        mock_position1.symbol = "AAPL"
        mock_position1.side = "long"
        mock_position1.qty = "100"
        mock_position1.avg_entry_price = "150.0"
        mock_position1.current_price = "155.0"
        mock_position1.market_value = "15500.0"
        mock_position1.unrealized_pl = "500.0"
        mock_position1.unrealized_plpc = "0.0333"

        tracker = PositionTracker()

        with patch("alpacalyzer.trading.alpaca_client.get_positions", return_value=[mock_position1]):
            changes = tracker.sync_from_broker()

        assert len(changes) == 1
        assert "AAPL" in changes
        assert tracker.count() == 1
        assert tracker.has_position("AAPL") is True
        assert tracker._last_sync is not None

    def test_sync_from_broker_update_existing(self):
        """Test sync_from_broker updates existing positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "160.0"
        mock_position.market_value = "16000.0"
        mock_position.unrealized_pl = "1000.0"
        mock_position.unrealized_plpc = "0.0667"

        with patch("alpacalyzer.trading.alpaca_client.get_positions", return_value=[mock_position]):
            changes = tracker.sync_from_broker()

        assert len(changes) == 0
        assert tracker.count() == 1
        position = tracker.get("AAPL")
        assert position is not None
        assert position.current_price == 160.0
        assert position.market_value == 16000.0
        assert position.unrealized_pnl == 1000.0

    def test_sync_from_broker_remove_closed(self):
        """Test sync_from_broker removes closed positions."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")

        with patch("alpacalyzer.trading.alpaca_client.get_positions", return_value=[]):
            changes = tracker.sync_from_broker()

        assert len(changes) == 2
        assert "AAPL" in changes
        assert "MSFT" in changes
        assert tracker.count() == 0
        closed = tracker.get_closed_positions()
        assert len(closed) == 2

    def test_sync_from_broker_mixed_changes(self):
        """Test sync_from_broker with mixed adds/updates/removes."""
        from alpacalyzer.execution.position_tracker import PositionTracker

        tracker = PositionTracker()
        tracker.add_position(ticker="AAPL", side="long", quantity=100, entry_price=150.0, strategy_name="momentum")
        tracker.add_position(ticker="MSFT", side="long", quantity=50, entry_price=300.0, strategy_name="swing")

        mock_position = MagicMock(spec=Position)
        mock_position.symbol = "AAPL"
        mock_position.side = "long"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "160.0"
        mock_position.market_value = "16000.0"
        mock_position.unrealized_pl = "1000.0"
        mock_position.unrealized_plpc = "0.0667"

        with patch("alpacalyzer.trading.alpaca_client.get_positions", return_value=[mock_position]):
            changes = tracker.sync_from_broker()

        assert len(changes) == 1
        assert "MSFT" in changes
        assert tracker.count() == 1
        assert tracker.has_position("AAPL") is True
        assert tracker.has_position("MSFT") is False
