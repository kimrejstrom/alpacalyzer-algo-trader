"""PositionTracker for enriched local position state with broker synchronization."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from alpaca.trading.models import Position

if TYPE_CHECKING:
    pass


@dataclass
class TrackedPosition:
    """
    Enriched position data beyond broker-provided information.

    Tracks positions with strategy association, entry timestamps,
    stop loss/target tracking, and exit attempt history.
    """

    # Core position data
    ticker: str
    side: str
    quantity: int
    avg_entry_price: float
    current_price: float

    # Computed values
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

    # Enriched metadata
    strategy_name: str
    opened_at: datetime
    entry_order_id: str | None = None
    stop_loss: float | None = None
    target: float | None = None

    # State tracking
    exit_attempts: int = 0
    last_exit_attempt: datetime | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_alpaca_position(
        cls,
        position: Position,
        strategy_name: str = "unknown",
        opened_at: datetime | None = None,
        stop_loss: float | None = None,
        target: float | None = None,
    ) -> "TrackedPosition":
        """
        Create a TrackedPosition from an Alpaca Position.

        Args:
            position: Alpaca Position object
            strategy_name: Strategy that opened this position
            opened_at: When position was opened (defaults to now)
            stop_loss: Stop loss price
            target: Target price

        Returns:
            TrackedPosition with enriched metadata
        """
        qty = int(float(position.qty))
        entry = float(position.avg_entry_price)
        current = float(position.current_price) if position.current_price else entry
        mkt_value = float(position.market_value) if position.market_value else qty * current
        pnl = float(position.unrealized_pl) if position.unrealized_pl else 0.0
        pnl_pct = float(position.unrealized_plpc) if position.unrealized_plpc else 0.0

        return cls(
            ticker=position.symbol,
            side=position.side,
            quantity=qty,
            avg_entry_price=entry,
            current_price=current,
            market_value=mkt_value,
            unrealized_pnl=pnl,
            unrealized_pnl_pct=pnl_pct,
            strategy_name=strategy_name,
            opened_at=opened_at or datetime.now(UTC),
            stop_loss=stop_loss,
            target=target,
        )

    def update_price(self, new_price: float) -> None:
        """
        Update current price and recalculate P&L.

        Args:
            new_price: New current price
        """
        self.current_price = new_price
        self.market_value = self.quantity * new_price

        if self.side == "long":
            self.unrealized_pnl = (new_price - self.avg_entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.avg_entry_price - new_price) * self.quantity

        if self.avg_entry_price > 0:
            self.unrealized_pnl_pct = self.unrealized_pnl / (self.avg_entry_price * self.quantity)
        else:
            self.unrealized_pnl_pct = 0.0

    def record_exit_attempt(self, reason: str) -> None:
        """
        Record an exit attempt.

        Args:
            reason: Reason for exit attempt
        """
        self.exit_attempts += 1
        self.last_exit_attempt = datetime.now(UTC)
        self.notes.append(f"Exit attempt {self.exit_attempts}: {reason}")

    def to_dict(self) -> dict[str, Any]:
        """Serialize position to dictionary."""
        return {
            "ticker": self.ticker,
            "side": self.side,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "strategy_name": self.strategy_name,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "entry_order_id": self.entry_order_id,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "exit_attempts": self.exit_attempts,
            "last_exit_attempt": self.last_exit_attempt.isoformat() if self.last_exit_attempt else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrackedPosition":
        """Deserialize position from dictionary."""
        opened_at = None
        if data.get("opened_at"):
            opened_at = datetime.fromisoformat(data["opened_at"])

        last_exit_attempt = None
        if data.get("last_exit_attempt"):
            last_exit_attempt = datetime.fromisoformat(data["last_exit_attempt"])

        return cls(
            ticker=data["ticker"],
            side=data["side"],
            quantity=data["quantity"],
            avg_entry_price=data["avg_entry_price"],
            current_price=data["current_price"],
            market_value=data["market_value"],
            unrealized_pnl=data["unrealized_pnl"],
            unrealized_pnl_pct=data["unrealized_pnl_pct"],
            strategy_name=data["strategy_name"],
            opened_at=opened_at or datetime.now(UTC),
            entry_order_id=data.get("entry_order_id"),
            stop_loss=data.get("stop_loss"),
            target=data.get("target"),
            exit_attempts=data.get("exit_attempts", 0),
            last_exit_attempt=last_exit_attempt,
            notes=data.get("notes", []),
        )


class PositionTracker:
    """
    Manages local position state with broker synchronization.

    Features:
    - Rich position metadata (strategy, entry time, stop/target)
    - Broker synchronization (detects adds/updates/removes)
    - Position history for analytics
    - Query interface for filtering
    """

    def __init__(self):
        """Initialize PositionTracker."""
        self._positions: dict[str, TrackedPosition] = {}
        self._closed_positions: list[TrackedPosition] = []
        self._last_sync: datetime | None = None

    def sync_from_broker(self) -> list[str]:
        """
        Sync positions from Alpaca broker.

        Updates existing positions, adds new ones, and moves closed
        positions to history.

        Returns:
            List of tickers that changed (added or removed)
        """
        from alpacalyzer.trading.alpaca_client import get_positions

        broker_positions = get_positions()
        broker_tickers = {p.symbol for p in broker_positions}
        local_tickers = set(self._positions.keys())

        changes = []

        # Update existing / add new positions
        for pos in broker_positions:
            ticker = pos.symbol

            if ticker in self._positions:
                # Update existing position
                tracked = self._positions[ticker]
                new_price = float(pos.current_price) if pos.current_price else tracked.current_price
                tracked.update_price(new_price)
            else:
                # New position (opened outside our system or missed)
                self._positions[ticker] = TrackedPosition.from_alpaca_position(pos)
                changes.append(ticker)

        # Handle closed positions
        for ticker in local_tickers - broker_tickers:
            closed = self._positions.pop(ticker)
            self._closed_positions.append(closed)
            changes.append(ticker)

        self._last_sync = datetime.now(UTC)
        return changes

    def add_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float,
        strategy_name: str,
        order_id: str | None = None,
        stop_loss: float | None = None,
        target: float | None = None,
    ) -> TrackedPosition:
        """
        Add a new position (called after order fill).

        Args:
            ticker: Stock ticker symbol
            side: Position side ("long" or "short")
            quantity: Number of shares
            entry_price: Average entry price
            strategy_name: Strategy that opened this position
            order_id: Entry order ID
            stop_loss: Stop loss price
            target: Target price

        Returns:
            Created TrackedPosition
        """
        position = TrackedPosition(
            ticker=ticker,
            side=side,
            quantity=quantity,
            avg_entry_price=entry_price,
            current_price=entry_price,
            market_value=quantity * entry_price,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            strategy_name=strategy_name,
            opened_at=datetime.now(UTC),
            entry_order_id=order_id,
            stop_loss=stop_loss,
            target=target,
        )
        self._positions[ticker] = position
        return position

    def remove_position(self, ticker: str) -> TrackedPosition | None:
        """
        Remove a position (called after exit).

        Moves position to history.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Removed TrackedPosition or None if not found
        """
        if ticker in self._positions:
            position = self._positions.pop(ticker)
            self._closed_positions.append(position)
            return position
        return None

    def get(self, ticker: str) -> TrackedPosition | None:
        """
        Get a position by ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            TrackedPosition or None if not found
        """
        return self._positions.get(ticker)

    def get_all(self) -> list[TrackedPosition]:
        """
        Get all current positions.

        Returns:
            List of all open positions
        """
        return list(self._positions.values())

    def get_by_strategy(self, strategy_name: str) -> list[TrackedPosition]:
        """
        Get positions opened by a specific strategy.

        Args:
            strategy_name: Strategy name to filter by

        Returns:
            List of positions for the strategy
        """
        return [p for p in self._positions.values() if p.strategy_name == strategy_name]

    def has_position(self, ticker: str) -> bool:
        """
        Check if we have a position in a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if position exists
        """
        return ticker in self._positions

    def count(self) -> int:
        """
        Get number of open positions.

        Returns:
            Number of open positions
        """
        return len(self._positions)

    def total_value(self) -> float:
        """
        Get total market value of all positions.

        Returns:
            Total market value
        """
        return sum(p.market_value for p in self._positions.values())

    def total_pnl(self) -> float:
        """
        Get total unrealized P&L.

        Returns:
            Total unrealized profit/loss
        """
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_closed_positions(self, limit: int = 100) -> list[TrackedPosition]:
        """
        Get recently closed positions.

        Args:
            limit: Maximum number of positions to return

        Returns:
            List of recently closed positions
        """
        return self._closed_positions[-limit:]

    def to_dict(self) -> dict[str, Any]:
        """Serialize positions to dictionary."""
        return {
            "positions": {ticker: pos.to_dict() for ticker, pos in self._positions.items()},
            "closed_positions": [pos.to_dict() for pos in self._closed_positions],
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PositionTracker":
        """Deserialize positions from dictionary."""
        tracker = cls()

        for ticker, pos_data in data.get("positions", {}).items():
            tracker._positions[ticker] = TrackedPosition.from_dict(pos_data)

        for pos_data in data.get("closed_positions", []):
            tracker._closed_positions.append(TrackedPosition.from_dict(pos_data))

        if data.get("last_sync"):
            tracker._last_sync = datetime.fromisoformat(data["last_sync"])

        return tracker
