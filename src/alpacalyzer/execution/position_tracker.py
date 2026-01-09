"""Position tracking for trade management."""

from dataclasses import dataclass
from datetime import UTC, datetime

from alpacalyzer.trading.alpaca_client import trading_client

if False:
    from alpaca.trading.models import Position


@dataclass
class TrackedPosition:
    """
    A tracked position with P&L tracking.

    Attributes:
        ticker: Stock ticker symbol
        quantity: Number of shares (negative for short)
        entry_price: Average entry price
        current_price: Current market price
        unrealized_pl: Unrealized profit/loss in USD
        unrealized_plpc: Unrealized profit/loss as percentage
        side: Position side ("long" or "short")
        entry_time: When position was added to tracker
    """

    ticker: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pl: float
    unrealized_plpc: float
    side: str
    entry_time: datetime

    @classmethod
    def from_alpaca_position(cls, position: "Position") -> "TrackedPosition":
        """
        Create TrackedPosition from Alpaca Position.

        Alpaca Position uses strings for numeric fields, so we convert them.
        """
        side_str = position.side.value if hasattr(position.side, "value") else str(position.side)

        return cls(
            ticker=position.symbol,
            quantity=int(float(position.qty)),
            entry_price=float(position.avg_entry_price),
            current_price=float(position.current_price) if position.current_price else 0.0,
            unrealized_pl=float(position.unrealized_pl) if position.unrealized_pl else 0.0,
            unrealized_plpc=float(position.unrealized_plpc) if position.unrealized_plpc else 0.0,
            side=side_str,
            entry_time=datetime.now(UTC),
        )


class PositionTracker:
    """
    Track and manage open positions.

    Features:
    - Add/remove positions
    - Query by ticker
    - Sync with broker
    - Track P&L over time
    """

    def __init__(self):
        self._positions: dict[str, TrackedPosition] = {}

    def add(self, position: "Position") -> None:
        """Add a position to the tracker."""
        tracked = TrackedPosition.from_alpaca_position(position)
        self._positions[tracked.ticker] = tracked

    def get(self, ticker: str) -> TrackedPosition | None:
        """Get a tracked position by ticker."""
        return self._positions.get(ticker)

    def get_all(self) -> list[TrackedPosition]:
        """Get all tracked positions."""
        return list(self._positions.values())

    def remove(self, ticker: str) -> bool:
        """
        Remove a position from tracker.

        Returns True if position was found and removed.
        """
        if ticker in self._positions:
            del self._positions[ticker]
            return True
        return False

    def clear(self) -> None:
        """Clear all positions."""
        self._positions.clear()

    def count(self) -> int:
        """Get number of tracked positions."""
        return len(self._positions)

    def get_tickers(self) -> list[str]:
        """Get list of ticker symbols."""
        return list(self._positions.keys())

    def has(self, ticker: str) -> bool:
        """Check if tracker has a position for the ticker."""
        return ticker in self._positions

    def update_pnl(self, ticker: str, unrealized_pl: float, unrealized_plpc: float) -> None:
        """Update P&L for a tracked position."""
        if ticker in self._positions:
            self._positions[ticker].unrealized_pl = unrealized_pl
            self._positions[ticker].unrealized_plpc = unrealized_plpc

    def sync_from_broker(self) -> None:
        """
        Sync positions from broker (Alpaca).

        This replaces all existing positions with fresh data from the broker.
        """
        positions = trading_client.get_all_positions()
        self._positions.clear()

        for position in positions:
            tracked = TrackedPosition.from_alpaca_position(position)
            self._positions[tracked.ticker] = tracked
