"""SignalQueue for managing pending trading signals."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from heapq import heapify, heappop, heappush

from alpacalyzer.data.models import TradingStrategy
from alpacalyzer.events import SignalExpiredEvent, emit_event


@dataclass(order=True)
class PendingSignal:
    """A signal waiting to be executed."""

    # Priority field for heap (lower = higher priority)
    priority: int = field(compare=True)

    # Signal data (not used for comparison)
    ticker: str = field(compare=False)
    action: str = field(compare=False)  # "buy", "sell", "short", "cover"
    confidence: float = field(compare=False)
    source: str = field(compare=False)  # "reddit", "technical", "manual"
    created_at: datetime = field(compare=False, default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = field(compare=False, default=None)
    agent_recommendation: TradingStrategy | None = field(compare=False, default=None)

    @classmethod
    def from_strategy(cls, strategy: TradingStrategy, source: str = "agent") -> "PendingSignal":
        """Create a PendingSignal from a TradingStrategy."""
        # Higher confidence = lower priority number = processed first
        priority = 100 - int(strategy.risk_reward_ratio * 10)

        return cls(
            priority=priority,
            ticker=strategy.ticker,
            action="buy" if strategy.trade_type == "long" else "short",
            confidence=75.0,  # Default from agent
            source=source,
            expires_at=datetime.now(UTC) + timedelta(hours=4),
            agent_recommendation=strategy,
        )

    def is_expired(self) -> bool:
        """Check if the signal has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at


class SignalQueue:
    """
    Priority queue for pending trading signals.

    Features:
    - Priority-based ordering (higher confidence first)
    - Automatic expiration
    - Deduplication by ticker
    - Safe for single-threaded use (no explicit locking)

    Note: For multi-threaded scenarios, add threading.Lock or use queue.PriorityQueue.
    """

    def __init__(self, max_signals: int = 50, default_ttl_hours: int = 4):
        self._heap: list[PendingSignal] = []
        self._tickers: set[str] = set()
        self.max_signals = max_signals
        self.default_ttl = timedelta(hours=default_ttl_hours)

    def add(self, signal: PendingSignal) -> bool:
        """
        Add a signal to the queue.

        Returns True if added, False if duplicate or queue full.
        """
        # Check for duplicate ticker
        if signal.ticker in self._tickers:
            return False

        # Check queue capacity
        if len(self._heap) >= self.max_signals:
            return False

        # Set default expiration if not set
        if signal.expires_at is None:
            signal.expires_at = datetime.now(UTC) + self.default_ttl

        heappush(self._heap, signal)
        self._tickers.add(signal.ticker)
        return True

    def peek(self) -> PendingSignal | None:
        """Get the highest priority signal without removing it."""
        self._cleanup_expired()
        return self._heap[0] if self._heap else None

    def pop(self) -> PendingSignal | None:
        """Remove and return the highest priority signal."""
        self._cleanup_expired()
        if not self._heap:
            return None

        signal = heappop(self._heap)
        self._tickers.discard(signal.ticker)
        return signal

    def remove(self, ticker: str) -> bool:
        """Remove a signal by ticker."""
        if ticker not in self._tickers:
            return False

        self._heap = [s for s in self._heap if s.ticker != ticker]
        self._tickers.discard(ticker)
        # Re-heapify after removal
        heapify(self._heap)
        return True

    def contains(self, ticker: str) -> bool:
        """Check if a ticker has a pending signal."""
        return ticker in self._tickers

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        self._cleanup_expired()
        return len(self._heap) == 0

    def size(self) -> int:
        """Get number of pending signals."""
        self._cleanup_expired()
        return len(self._heap)

    def clear(self) -> None:
        """Remove all signals."""
        self._heap.clear()
        self._tickers.clear()

    def _cleanup_expired(self) -> None:
        """Remove expired signals."""
        now = datetime.now(UTC)
        expired = [s for s in self._heap if s.expires_at and s.expires_at < now]

        for signal in expired:
            self._tickers.discard(signal.ticker)
            emit_event(
                SignalExpiredEvent(
                    timestamp=now,
                    ticker=signal.ticker,
                    created_at=signal.created_at,
                    reason="signal_expired",
                )
            )

        self._heap = [s for s in self._heap if s not in expired]
        heapify(self._heap)

    def __iter__(self) -> Iterator[PendingSignal]:
        """Iterate over signals without removing them."""
        self._cleanup_expired()
        return iter(sorted(self._heap))

    def __len__(self) -> int:
        return self.size()
