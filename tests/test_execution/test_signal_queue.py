"""Tests for SignalQueue module."""

from datetime import UTC, datetime, timedelta

from alpacalyzer.data.models import EntryCriteria, EntryType, TradingStrategy


class TestPendingSignal:
    """Tests for PendingSignal dataclass."""

    def test_pending_signal_creation(self):
        """Test creating a PendingSignal."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        signal = PendingSignal(
            priority=50,
            ticker="AAPL",
            action="buy",
            confidence=75.0,
            source="agent",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=4),
        )

        assert signal.priority == 50
        assert signal.ticker == "AAPL"
        assert signal.action == "buy"
        assert signal.confidence == 75.0
        assert signal.source == "agent"

    def test_pending_signal_ordering(self):
        """Test that PendingSignal is ordered by priority."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        low_priority = PendingSignal(priority=100, ticker="LOW", action="buy", confidence=50.0, source="test")
        high_priority = PendingSignal(priority=10, ticker="HIGH", action="buy", confidence=90.0, source="test")

        assert high_priority < low_priority

    def test_pending_signal_from_strategy_long(self):
        """Test creating PendingSignal from TradingStrategy (long)."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        strategy = TradingStrategy(
            ticker="AAPL",
            quantity=100,
            entry_point=150.0,
            stop_loss=140.0,
            target_price=170.0,
            risk_reward_ratio=2.0,
            strategy_notes="Good setup",
            trade_type="long",
            entry_criteria=[EntryCriteria(entry_type=EntryType.BREAKOUT_ABOVE, value=150.0)],
        )

        signal = PendingSignal.from_strategy(strategy, source="agent")

        assert signal.ticker == "AAPL"
        assert signal.action == "buy"
        assert signal.confidence == 75.0
        assert signal.source == "agent"
        assert signal.agent_recommendation == strategy
        assert signal.expires_at is not None
        # Priority: 100 - (2.0 * 10) = 80
        assert signal.priority == 80

    def test_pending_signal_from_strategy_short(self):
        """Test creating PendingSignal from TradingStrategy (short)."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        strategy = TradingStrategy(
            ticker="TSLA",
            quantity=50,
            entry_point=200.0,
            stop_loss=220.0,
            target_price=170.0,
            risk_reward_ratio=2.0,
            strategy_notes="Short setup",
            trade_type="short",
            entry_criteria=[EntryCriteria(entry_type=EntryType.BREAKDOWN_BELOW, value=200.0)],
        )

        signal = PendingSignal.from_strategy(strategy, source="agent")

        assert signal.ticker == "TSLA"
        assert signal.action == "short"

    def test_pending_signal_is_expired_true(self):
        """Test is_expired returns True for expired signals."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        signal = PendingSignal(
            priority=50,
            ticker="AAPL",
            action="buy",
            confidence=75.0,
            source="test",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )

        assert signal.is_expired() is True

    def test_pending_signal_is_expired_false(self):
        """Test is_expired returns False for non-expired signals."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        signal = PendingSignal(
            priority=50,
            ticker="AAPL",
            action="buy",
            confidence=75.0,
            source="test",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

        assert signal.is_expired() is False

    def test_pending_signal_is_expired_no_expiration(self):
        """Test is_expired returns False when no expiration is set."""
        from alpacalyzer.execution.signal_queue import PendingSignal

        signal = PendingSignal(
            priority=50,
            ticker="AAPL",
            action="buy",
            confidence=75.0,
            source="test",
            expires_at=None,
        )

        assert signal.is_expired() is False


class TestSignalQueue:
    """Tests for SignalQueue class."""

    def test_signal_queue_creation(self):
        """Test creating a SignalQueue."""
        from alpacalyzer.execution.signal_queue import SignalQueue

        queue = SignalQueue()

        assert queue.max_signals == 50
        assert queue.default_ttl == timedelta(hours=4)
        assert queue.size() == 0
        assert queue.is_empty() is True

    def test_signal_queue_custom_config(self):
        """Test creating a SignalQueue with custom configuration."""
        from alpacalyzer.execution.signal_queue import SignalQueue

        queue = SignalQueue(max_signals=100, default_ttl_hours=8)

        assert queue.max_signals == 100
        assert queue.default_ttl == timedelta(hours=8)

    def test_add_signal(self):
        """Test adding a signal to the queue."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        signal = PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test")

        result = queue.add(signal)

        assert result is True
        assert queue.size() == 1
        assert queue.contains("AAPL") is True

    def test_add_duplicate_ticker(self):
        """Test that duplicate tickers are rejected."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        signal1 = PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test")
        signal2 = PendingSignal(priority=40, ticker="AAPL", action="sell", confidence=80.0, source="test")

        queue.add(signal1)
        result = queue.add(signal2)

        assert result is False
        assert queue.size() == 1

    def test_add_queue_full(self):
        """Test that adding to a full queue fails."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue(max_signals=2)

        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))
        queue.add(PendingSignal(priority=60, ticker="MSFT", action="buy", confidence=70.0, source="test"))
        result = queue.add(PendingSignal(priority=70, ticker="GOOGL", action="buy", confidence=65.0, source="test"))

        assert result is False
        assert queue.size() == 2

    def test_add_default_expiration(self):
        """Test that default TTL is applied when no expiration is set."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue(default_ttl_hours=4)
        signal = PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test", expires_at=None)

        queue.add(signal)

        assert signal.expires_at is not None

    def test_peek_signal(self):
        """Test peeking at the highest priority signal."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=100, ticker="LOW", action="buy", confidence=50.0, source="test"))
        queue.add(PendingSignal(priority=10, ticker="HIGH", action="buy", confidence=90.0, source="test"))
        queue.add(PendingSignal(priority=50, ticker="MED", action="buy", confidence=70.0, source="test"))

        signal = queue.peek()

        assert signal is not None
        assert signal.ticker == "HIGH"
        assert signal.priority == 10
        assert queue.size() == 3  # Signal should not be removed

    def test_peek_empty_queue(self):
        """Test peeking at an empty queue."""
        from alpacalyzer.execution.signal_queue import SignalQueue

        queue = SignalQueue()

        assert queue.peek() is None

    def test_pop_signal(self):
        """Test popping the highest priority signal."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=100, ticker="LOW", action="buy", confidence=50.0, source="test"))
        queue.add(PendingSignal(priority=10, ticker="HIGH", action="buy", confidence=90.0, source="test"))
        queue.add(PendingSignal(priority=50, ticker="MED", action="buy", confidence=70.0, source="test"))

        signal = queue.pop()

        assert signal is not None
        assert signal.ticker == "HIGH"
        assert signal.priority == 10
        assert queue.size() == 2  # Signal should be removed
        assert queue.contains("HIGH") is False

    def test_pop_empty_queue(self):
        """Test popping from an empty queue."""
        from alpacalyzer.execution.signal_queue import SignalQueue

        queue = SignalQueue()

        assert queue.pop() is None

    def test_remove_signal(self):
        """Test removing a signal by ticker."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))
        queue.add(PendingSignal(priority=60, ticker="MSFT", action="buy", confidence=70.0, source="test"))

        result = queue.remove("AAPL")

        assert result is True
        assert queue.size() == 1
        assert queue.contains("AAPL") is False

    def test_remove_nonexistent_signal(self):
        """Test removing a non-existent signal."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))

        result = queue.remove("MSFT")

        assert result is False
        assert queue.size() == 1

    def test_contains_signal(self):
        """Test checking if a ticker is in the queue."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))

        assert queue.contains("AAPL") is True
        assert queue.contains("MSFT") is False

    def test_is_empty(self):
        """Test checking if the queue is empty."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()

        assert queue.is_empty() is True

        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))

        assert queue.is_empty() is False

    def test_size(self):
        """Test getting the queue size."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()

        assert queue.size() == 0

        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))
        assert queue.size() == 1

        queue.add(PendingSignal(priority=60, ticker="MSFT", action="buy", confidence=70.0, source="test"))
        assert queue.size() == 2

    def test_clear(self):
        """Test clearing the queue."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))
        queue.add(PendingSignal(priority=60, ticker="MSFT", action="buy", confidence=70.0, source="test"))

        queue.clear()

        assert queue.size() == 0
        assert queue.is_empty() is True

    def test_iteration(self):
        """Test iterating over the queue."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=100, ticker="LOW", action="buy", confidence=50.0, source="test"))
        queue.add(PendingSignal(priority=10, ticker="HIGH", action="buy", confidence=90.0, source="test"))
        queue.add(PendingSignal(priority=50, ticker="MED", action="buy", confidence=70.0, source="test"))

        tickers = [signal.ticker for signal in queue]

        assert tickers == ["HIGH", "MED", "LOW"]
        assert queue.size() == 3  # Signals should not be removed

    def test_len_dunder(self):
        """Test __len__ method."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=50, ticker="AAPL", action="buy", confidence=75.0, source="test"))
        queue.add(PendingSignal(priority=60, ticker="MSFT", action="buy", confidence=70.0, source="test"))

        assert len(queue) == 2

    def test_cleanup_expired_signals(self):
        """Test that expired signals are cleaned up."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(
            PendingSignal(
                priority=50,
                ticker="AAPL",
                action="buy",
                confidence=75.0,
                source="test",
                expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired
            )
        )
        queue.add(
            PendingSignal(
                priority=60,
                ticker="MSFT",
                action="buy",
                confidence=70.0,
                source="test",
                expires_at=datetime.now(UTC) + timedelta(hours=1),  # Not expired
            )
        )

        # Check that expired signals are removed when accessing queue
        assert queue.size() == 1
        assert queue.contains("AAPL") is False
        assert queue.contains("MSFT") is True

    def test_priority_ordering(self):
        """Test that signals are popped in priority order."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()
        queue.add(PendingSignal(priority=90, ticker="A", action="buy", confidence=10.0, source="test"))
        queue.add(PendingSignal(priority=30, ticker="B", action="buy", confidence=70.0, source="test"))
        queue.add(PendingSignal(priority=50, ticker="C", action="buy", confidence=50.0, source="test"))
        queue.add(PendingSignal(priority=10, ticker="D", action="buy", confidence=90.0, source="test"))
        queue.add(PendingSignal(priority=70, ticker="E", action="buy", confidence=30.0, source="test"))

        tickers = []
        while not queue.is_empty():
            signal = queue.pop()
            assert signal is not None
            tickers.append(signal.ticker)

        assert tickers == ["D", "B", "C", "E", "A"]

    def test_integration_with_trading_strategy(self):
        """Test integration with TradingStrategy model."""
        from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue

        queue = SignalQueue()

        strategies = [
            TradingStrategy(
                ticker="AAPL",
                quantity=100,
                entry_point=150.0,
                stop_loss=140.0,
                target_price=170.0,
                risk_reward_ratio=2.0,
                strategy_notes="Good setup",
                trade_type="long",
                entry_criteria=[EntryCriteria(entry_type=EntryType.BREAKOUT_ABOVE, value=150.0)],
            ),
            TradingStrategy(
                ticker="MSFT",
                quantity=50,
                entry_point=300.0,
                stop_loss=280.0,
                target_price=350.0,
                risk_reward_ratio=2.5,
                strategy_notes="Better setup",
                trade_type="long",
                entry_criteria=[EntryCriteria(entry_type=EntryType.BREAKOUT_ABOVE, value=300.0)],
            ),
        ]

        for strategy in strategies:
            signal = PendingSignal.from_strategy(strategy, source="agent")
            queue.add(signal)

        assert queue.size() == 2
        assert queue.contains("AAPL") is True
        assert queue.contains("MSFT") is True

        # MSFT has higher RRR (2.5) -> lower priority number (75) -> processed first
        # AAPL has lower RRR (2.0) -> higher priority number (80) -> processed second
        # So MSFT should be popped first
        signal = queue.pop()
        assert signal is not None
        assert signal.ticker == "MSFT"
