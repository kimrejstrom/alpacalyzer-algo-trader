"""Tests for EventEmitter module."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest

from alpacalyzer.events.emitter import (
    CallbackEventHandler,
    ConsoleEventHandler,
    EventEmitter,
    EventHandler,
    FileEventHandler,
    emit_event,
)
from alpacalyzer.events.models import (
    AgentReasoningEvent,
    EntryBlockedEvent,
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    OrderCanceledEvent,
    OrderFilledEvent,
    OrderRejectedEvent,
    ScanCompleteEvent,
    SignalGeneratedEvent,
)


@pytest.fixture(autouse=True)
def reset_emitter_singleton():
    """Reset EventEmitter singleton before and after each test."""
    EventEmitter._instance = None
    yield
    EventEmitter._instance = None


# =============================================================================
# EventHandler Tests
# =============================================================================


def test_event_handler_abstract():
    """Test EventHandler is abstract and requires handle method."""
    from alpacalyzer.events.emitter import EventHandler

    with pytest.raises(TypeError):
        EventHandler()


def test_console_handler_formats_entry_event():
    """Test ConsoleEventHandler formats EntryTriggeredEvent correctly."""
    handler = ConsoleEventHandler()

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.00,
        stop_loss=145.50,
        target=163.50,
        reason="Golden cross",
    )

    formatted = handler._format_event(event)

    assert "ENTRY" in formatted
    assert "AAPL" in formatted
    assert "LONG" in formatted
    assert "150.00" in formatted


def test_console_handler_formats_exit_event_profit():
    """Test ConsoleEventHandler formats ExitTriggeredEvent with profit."""
    handler = ConsoleEventHandler()

    event = ExitTriggeredEvent(
        timestamp=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        exit_price=162.0,
        pnl=1200.0,
        pnl_pct=0.08,
        hold_duration_hours=24.0,
        reason="Target price reached",
        urgency="normal",
    )

    formatted = handler._format_event(event)

    assert "EXIT" in formatted
    assert "AAPL" in formatted
    assert "1200.00" in formatted


def test_console_handler_formats_scan_event():
    """Test ConsoleEventHandler formats ScanCompleteEvent."""
    handler = ConsoleEventHandler()

    event = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        source="reddit",
        tickers_found=["AAPL", "TSLA", "NVDA"],
        duration_seconds=15.5,
    )

    formatted = handler._format_event(event)

    assert "Scan complete" in formatted
    assert "reddit" in formatted
    assert "3 tickers" in formatted


def test_console_handler_filters_by_event_type():
    """Test ConsoleEventHandler filters events by type."""
    mock_logger = Mock()
    handler = ConsoleEventHandler(event_types=["ENTRY_TRIGGERED"])

    with patch("alpacalyzer.events.emitter.logger", mock_logger):
        entry_event = EntryTriggeredEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=165.0,
            reason="Entry",
        )

        scan_event = ScanCompleteEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            source="reddit",
            tickers_found=["AAPL"],
            duration_seconds=10.0,
        )

        handler.handle(entry_event)
        handler.handle(scan_event)

        # Should only log entry event
        assert mock_logger.info.call_count == 1


def test_file_handler_writes_to_file(tmp_path):
    """Test FileEventHandler writes JSON lines to file."""
    file_path = tmp_path / "events.jsonl"
    handler = FileEventHandler(file_path=str(file_path))

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Entry triggered",
    )

    handler.handle(event)

    with open(file_path) as f:
        content = f.read()

    assert "ENTRY_TRIGGERED" in content
    assert "AAPL" in content


def test_file_handler_append_mode(tmp_path):
    """Test FileEventHandler appends to file."""
    file_path = tmp_path / "events.jsonl"
    handler = FileEventHandler(file_path=str(file_path))

    event1 = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="First entry",
    )

    event2 = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 1, 0, tzinfo=UTC),
        source="reddit",
        tickers_found=["TSLA"],
        duration_seconds=5.0,
    )

    handler.handle(event1)
    handler.handle(event2)

    with open(file_path) as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert "ENTRY_TRIGGERED" in lines[0]
    assert "SCAN_COMPLETE" in lines[1]


def test_file_handler_rotates_when_exceeding_max_bytes(tmp_path):
    """Test FileEventHandler rotates file when it exceeds max_bytes."""
    file_path = tmp_path / "events.jsonl"
    # Set tiny max_bytes so rotation triggers quickly
    handler = FileEventHandler(file_path=str(file_path), max_bytes=100, backup_count=2)

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Entry triggered",
    )

    # Write enough events to trigger rotation
    for _ in range(5):
        handler.handle(event)

    # Should have rotated — backup files should exist
    backup_1 = tmp_path / "events.jsonl.1"
    assert backup_1.exists(), "Backup .1 should exist after rotation"
    # Current file should still be writable and small
    assert file_path.exists()


def test_file_handler_respects_backup_count(tmp_path):
    """Test FileEventHandler deletes oldest backup beyond backup_count."""
    file_path = tmp_path / "events.jsonl"
    handler = FileEventHandler(file_path=str(file_path), max_bytes=50, backup_count=2)

    event = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        source="reddit",
        tickers_found=["TSLA"],
        duration_seconds=5.0,
    )

    # Write many events to trigger multiple rotations
    for _ in range(20):
        handler.handle(event)

    # Should have at most backup_count backups
    assert file_path.exists()
    assert (tmp_path / "events.jsonl.1").exists()
    assert (tmp_path / "events.jsonl.2").exists()
    assert not (tmp_path / "events.jsonl.3").exists(), "Should not exceed backup_count"


def test_file_handler_no_rotation_under_limit(tmp_path):
    """Test FileEventHandler does not rotate when under max_bytes."""
    file_path = tmp_path / "events.jsonl"
    handler = FileEventHandler(file_path=str(file_path), max_bytes=10 * 1024 * 1024, backup_count=3)

    event = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        source="reddit",
        tickers_found=["TSLA"],
        duration_seconds=5.0,
    )

    handler.handle(event)

    assert file_path.exists()
    assert not (tmp_path / "events.jsonl.1").exists(), "Should not rotate under limit"


def test_callback_handler():
    """Test CallbackEventHandler calls callback function."""
    received_events = []

    def callback(event):
        received_events.append(event)

    handler = CallbackEventHandler(callback)

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Entry triggered",
    )

    handler.handle(event)

    assert len(received_events) == 1
    assert received_events[0].ticker == "AAPL"


# =============================================================================
# EventEmitter Tests
# =============================================================================


def test_event_emitter_singleton():
    """Test EventEmitter is a singleton."""
    emitter1 = EventEmitter.get_instance()
    emitter2 = EventEmitter.get_instance()

    assert emitter1 is emitter2


def test_event_emitter_add_remove_handler():
    """Test adding and removing handlers."""
    emitter = EventEmitter()

    handler1 = ConsoleEventHandler()
    handler2 = FileEventHandler()

    emitter.add_handler(handler1)
    emitter.add_handler(handler2)

    assert len(emitter._handlers) == 2

    emitter.remove_handler(handler1)

    assert len(emitter._handlers) == 1
    assert handler2 in emitter._handlers


def test_event_emitter_clear_handlers():
    """Test clearing all handlers."""
    emitter = EventEmitter()

    emitter.add_handler(ConsoleEventHandler())
    emitter.add_handler(FileEventHandler())

    assert len(emitter._handlers) > 0

    emitter.clear_handlers()

    assert len(emitter._handlers) == 0


def test_event_emitter_emit_to_multiple_handlers():
    """Test EventEmitter emits to all handlers."""
    emitter = EventEmitter()
    emitter.clear_handlers()

    received1 = []
    received2 = []

    emitter.add_handler(CallbackEventHandler(lambda e: received1.append(e)))
    emitter.add_handler(CallbackEventHandler(lambda e: received2.append(e)))

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Entry triggered",
    )

    emitter.emit(event)

    assert len(received1) == 1
    assert len(received2) == 1


def test_event_emitter_error_handling():
    """Test EventEmitter handles handler errors gracefully."""
    emitter = EventEmitter()
    emitter.clear_handlers()

    class BrokenHandler(EventHandler):
        def handle(self, event):
            raise RuntimeError("Handler error")

    received = []

    emitter.add_handler(BrokenHandler())
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Entry triggered",
    )

    # Should not raise, should continue to next handler
    emitter.emit(event)

    assert len(received) == 1


def test_emit_event_convenience_function():
    """Test emit_event convenience function."""
    received = []

    EventEmitter._instance = None  # Reset singleton
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Entry triggered",
    )

    emit_event(event)

    assert len(received) == 1


# =============================================================================
# Event-Specific Emission Tests (Integration)
# =============================================================================


def test_emit_event_entry_blocked():
    """Test that EntryBlockedEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = EntryBlockedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        ticker="MSFT",
        strategy="momentum",
        reason="Insufficient conditions",
        conditions_met=2,
        conditions_total=5,
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].ticker == "MSFT"
    assert received[0].event_type == "ENTRY_BLOCKED"


def test_emit_event_exit_triggered():
    """Test that ExitTriggeredEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = ExitTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        ticker="TSLA",
        strategy="momentum",
        side="short",
        quantity=50,
        entry_price=250.0,
        exit_price=200.0,
        pnl=-2500.0,
        pnl_pct=-0.10,
        hold_duration_hours=4.5,
        reason="Stop loss hit",
        urgency="normal",
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].ticker == "TSLA"
    assert received[0].event_type == "EXIT_TRIGGERED"


def test_emit_event_order_filled():
    """Test that OrderFilledEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = OrderFilledEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        ticker="NVDA",
        order_id="12345",
        client_order_id="client_123",
        side="buy",
        quantity=100,
        filled_qty=100,
        avg_price=500.0,
        strategy="momentum",
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].ticker == "NVDA"
    assert received[0].event_type == "ORDER_FILLED"


def test_emit_event_order_canceled():
    """Test that OrderCanceledEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = OrderCanceledEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        ticker="AMD",
        order_id="67890",
        client_order_id="client_678",
        reason="User requested",
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].ticker == "AMD"
    assert received[0].event_type == "ORDER_CANCELED"


def test_emit_event_order_rejected():
    """Test that OrderRejectedEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = OrderRejectedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        ticker="NFLX",
        order_id=None,
        client_order_id="client_nflx",
        reason="Insufficient buying power",
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].ticker == "NFLX"
    assert received[0].event_type == "ORDER_REJECTED"


def test_emit_event_scan_complete():
    """Test that ScanCompleteEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        source="social_scanner",
        tickers_found=["AAPL", "MSFT", "GOOG"],
        duration_seconds=5.2,
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].source == "social_scanner"
    assert received[0].event_type == "SCAN_COMPLETE"


def test_emit_event_signal_generated():
    """Test that SignalGeneratedEvent is emitted correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = SignalGeneratedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        ticker="TSLA",
        action="buy",
        confidence=0.80,
        source="hedge_fund",
        strategy="momentum",
        reasoning="Strong bullish momentum",
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].ticker == "TSLA"
    assert received[0].event_type == "SIGNAL_GENERATED"


# =============================================================================
# Agent Reasoning Event Tests
# =============================================================================


def test_console_handler_formats_agent_reasoning_event():
    """Test ConsoleEventHandler formats AgentReasoningEvent correctly."""
    handler = ConsoleEventHandler()

    event = AgentReasoningEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        agent="Technical Analyst",
        tickers=["AAPL", "TSLA"],
        reasoning={"AAPL": {"signal": "bullish"}, "TSLA": {"signal": "bearish"}},
    )

    formatted = handler._format_event(event)

    assert "Technical Analyst" in formatted
    assert "AAPL" in formatted
    assert "TSLA" in formatted


def test_console_handler_formats_agent_reasoning_no_tickers():
    """Test ConsoleEventHandler formats AgentReasoningEvent with no tickers."""
    handler = ConsoleEventHandler()

    event = AgentReasoningEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        agent="Risk Manager",
        tickers=[],
        reasoning={"risk_level": "low"},
    )

    formatted = handler._format_event(event)

    assert "Risk Manager" in formatted
    assert "N/A" in formatted


def test_emit_agent_reasoning_event():
    """Test that AgentReasoningEvent is emitted and received correctly."""
    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = AgentReasoningEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        agent="Portfolio Management Agent",
        tickers=["NVDA", "AMD"],
        reasoning={"NVDA": {"action": "buy", "confidence": 0.85}},
    )

    emit_event(event)

    assert len(received) == 1
    assert received[0].event_type == "AGENT_REASONING"
    assert received[0].agent == "Portfolio Management Agent"
    assert received[0].tickers == ["NVDA", "AMD"]


def test_show_agent_reasoning_emits_event():
    """Test that show_agent_reasoning() emits an AgentReasoningEvent."""
    from alpacalyzer.graph.state import show_agent_reasoning

    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    reasoning = {"AAPL": {"signal": "bullish", "confidence": 0.9}}
    show_agent_reasoning(reasoning, "Technical Analyst")

    # The event handler receives the AgentReasoningEvent (not the console log)
    assert len(received) == 1
    assert received[0].event_type == "AGENT_REASONING"
    assert received[0].agent == "Technical Analyst"
    assert "AAPL" in received[0].tickers
    assert received[0].reasoning == reasoning


def test_show_agent_reasoning_emits_event_with_string_input():
    """Test show_agent_reasoning() handles string JSON input."""
    from alpacalyzer.graph.state import show_agent_reasoning

    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    reasoning_str = '{"TSLA": {"action": "sell"}}'
    show_agent_reasoning(reasoning_str, "Risk Manager")

    assert len(received) == 1
    assert received[0].event_type == "AGENT_REASONING"
    assert received[0].agent == "Risk Manager"
    assert "TSLA" in received[0].tickers


def test_show_agent_reasoning_emits_event_with_plain_string():
    """Test show_agent_reasoning() handles non-JSON string input."""
    from alpacalyzer.graph.state import show_agent_reasoning

    received = []
    emitter = EventEmitter.get_instance()
    emitter.clear_handlers()
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    show_agent_reasoning("Some plain text reasoning", "Portfolio Manager")

    assert len(received) == 1
    assert received[0].event_type == "AGENT_REASONING"
    assert received[0].agent == "Portfolio Manager"
    assert received[0].reasoning == {"raw": "Some plain text reasoning"}
