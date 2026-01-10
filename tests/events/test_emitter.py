"""Tests for EventEmitter module."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from alpacalyzer.events.emitter import (
    AnalyticsEventHandler,
    CallbackEventHandler,
    ConsoleEventHandler,
    EventEmitter,
    FileEventHandler,
    emit_event,
)
from alpacalyzer.events.models import (
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    OrderFilledEvent,
    PositionClosedEvent,
    ScanCompleteEvent,
)


@pytest.fixture(autouse=True)
def reset_emitter_singleton():
    """Reset EventEmitter singleton before and after each test."""
    EventEmitter._instance = None
    yield
    EventEmitter._instance = None


def test_event_handler_abstract():
    """Test EventHandler is abstract and requires handle method."""
    from alpacalyzer.events.emitter import EventHandler

    with pytest.raises(TypeError):
        EventHandler()


def test_console_handler_formats_entry_event():
    """Test ConsoleEventHandler formats EntryTriggeredEvent correctly."""
    handler = ConsoleEventHandler()

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 2, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 1, 12, 1, 0),
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


def test_analytics_handler_filters_events():
    """Test AnalyticsEventHandler filters by event type."""
    mock_logger = Mock()
    handler = AnalyticsEventHandler()

    with patch("alpacalyzer.events.emitter.logger", mock_logger):
        analytics_event = OrderFilledEvent(
            timestamp=datetime(2024, 1, 1, 12, 1, 0),
            ticker="AAPL",
            order_id="12345",
            client_order_id="client_123",
            side="buy",
            quantity=100,
            filled_qty=100,
            avg_price=150.25,
            strategy="momentum",
        )

        non_analytics_event = ScanCompleteEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            source="reddit",
            tickers_found=["AAPL"],
            duration_seconds=10.0,
        )

        handler.handle(analytics_event)
        handler.handle(non_analytics_event)

        # Only analytics event should be logged
        assert mock_logger.analyze.call_count == 1


def test_analytics_handler_formats_order_filled():
    """Test AnalyticsEventHandler formats OrderFilledEvent."""
    handler = AnalyticsEventHandler()

    event = OrderFilledEvent(
        timestamp=datetime(2024, 1, 1, 12, 1, 0),
        ticker="AAPL",
        order_id="12345",
        client_order_id="client_123",
        side="buy",
        quantity=100,
        filled_qty=100,
        avg_price=150.25,
        strategy="momentum",
    )

    formatted = handler._format_analytics_line(event)

    assert "[EXECUTION]" in formatted
    assert "AAPL" in formatted
    assert "BUY" in formatted


def test_analytics_handler_formats_position_closed():
    """Test AnalyticsEventHandler formats PositionClosedEvent."""
    handler = AnalyticsEventHandler()

    event = PositionClosedEvent(
        timestamp=datetime(2024, 1, 2, 12, 0, 0),
        ticker="AAPL",
        side="long",
        quantity=100,
        entry_price=150.25,
        exit_price=162.50,
        pnl=1225.0,
        pnl_pct=0.0815,
        hold_duration_hours=24.0,
        strategy="momentum",
        exit_reason="Target price reached",
    )

    formatted = handler._format_analytics_line(event)

    assert "[EXIT]" in formatted
    assert "AAPL" in formatted
    assert "8.15%" in formatted


def test_callback_handler():
    """Test CallbackEventHandler calls callback function."""
    received_events = []

    def callback(event):
        received_events.append(event)

    handler = CallbackEventHandler(callback)

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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

    class BrokenHandler:
        def handle(self, event):
            raise RuntimeError("Handler error")

    received = []

    emitter.add_handler(BrokenHandler())
    emitter.add_handler(CallbackEventHandler(lambda e: received.append(e)))

    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
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
