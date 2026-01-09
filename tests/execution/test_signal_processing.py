"""Signal processing tests."""

from datetime import UTC, datetime, timedelta

from alpacalyzer.execution.signal_queue import PendingSignal


def test_signal_queue_to_entry(mock_broker, mock_strategy, sample_trading_strategy):
    """Signal in queue leads to entry evaluation."""
    from alpacalyzer.execution.engine import ExecutionEngine

    signal = PendingSignal.from_strategy(sample_trading_strategy, source="agent")

    engine = ExecutionEngine(strategy=mock_strategy)
    engine.signal_queue.add(signal)

    assert engine.signal_queue.contains("AAPL")
    assert engine.signal_queue.size() == 1


def test_duplicate_signal_rejected(signal_queue, sample_trading_strategy):
    """Duplicate ticker signals rejected."""
    signal = PendingSignal.from_strategy(sample_trading_strategy, source="agent")

    result1 = signal_queue.add(signal)
    result2 = signal_queue.add(signal)

    assert result1 is True
    assert result2 is False
    assert signal_queue.size() == 1


def test_expired_signal_skipped(signal_queue):
    """Expired signals not processed."""
    expired_signal = PendingSignal(
        priority=50,
        ticker="AAPL",
        action="buy",
        confidence=80.0,
        source="test",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )

    signal_queue.add(expired_signal)

    assert signal_queue.is_empty()
