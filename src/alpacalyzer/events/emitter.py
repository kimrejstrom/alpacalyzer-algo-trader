"""Event emitter for structured logging."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from alpacalyzer.events.models import TradingEvent
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


class EventHandler(ABC):
    """Base class for event handlers."""

    @abstractmethod
    def handle(self, event: TradingEvent) -> None:
        """Handle an event."""
        pass


class ConsoleEventHandler(EventHandler):
    """Logs events to console in human-readable format."""

    def __init__(self, event_types: list[str] | None = None):
        # If None, handle all events
        self.event_types = event_types

    def handle(self, event: TradingEvent) -> None:
        if self.event_types and event.event_type not in self.event_types:
            return

        message = self._format_event(event)
        logger.info(message)

    def _format_event(self, event: TradingEvent) -> str:
        """Format event for console output."""
        event_type = event.event_type

        if event_type == "ENTRY_TRIGGERED":
            return f"📈 ENTRY: {event.ticker} {event.side.upper()} x{event.quantity} @ ${event.entry_price:.2f} (SL: ${event.stop_loss:.2f}, TP: ${event.target:.2f})"
        if event_type == "EXIT_TRIGGERED":
            emoji = "✅" if event.pnl >= 0 else "❌"
            return f"{emoji} EXIT: {event.ticker} P/L: ${event.pnl:.2f} ({event.pnl_pct:.2%}) - {event.reason}"
        if event_type == "SCAN_COMPLETE":
            return f"🔍 Scan complete ({event.source}): {len(event.tickers_found)} tickers found"
        if event_type == "SIGNAL_GENERATED":
            return f"📊 Signal: {event.ticker} {event.action.upper()} (confidence: {event.confidence * 100:.0f}%)"
        if event_type == "ORDER_FILLED":
            return f"💰 Filled: {event.ticker} {event.side.upper()} {event.filled_qty}x @ ${event.avg_price:.2f}"
        if event_type == "CYCLE_COMPLETE":
            return f"🔄 Cycle: {event.entries_triggered} entries, {event.exits_triggered} exits, {event.positions_open} positions"
        return f"[{event_type}] {event.ticker if hasattr(event, 'ticker') else 'system'}"


class FileEventHandler(EventHandler):
    """Writes events as JSON lines to a file."""

    def __init__(self, file_path: str | None = None):
        from pathlib import Path

        self.file_path = file_path or "logs/events.jsonl"
        # Ensure directory exists
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)

    def handle(self, event: TradingEvent) -> None:
        json_line = event.model_dump_json()

        with open(self.file_path, "a") as f:
            f.write(json_line + "\n")


class AnalyticsEventHandler(EventHandler):
    """Writes events to analytics log for EOD analysis."""

    ANALYTICS_EVENTS = [
        "ENTRY_TRIGGERED",
        "EXIT_TRIGGERED",
        "ORDER_FILLED",
        "ORDER_CANCELED",
        "POSITION_OPENED",
        "POSITION_CLOSED",
    ]

    def handle(self, event: TradingEvent) -> None:
        if event.event_type not in self.ANALYTICS_EVENTS:
            return

        line = self._format_analytics_line(event)
        logger.analyze(line)

    def _format_analytics_line(self, event: TradingEvent) -> str:
        """Format event for analytics log (backwards compatible)."""
        if event.event_type == "ORDER_FILLED":
            return (
                f"[EXECUTION] Ticker: {event.ticker}, Side: {event.side.upper()}, "
                f"Cum: {event.filled_qty}/{event.quantity} @ {event.avg_price}, "
                f"OrderType: limit, OrderId: {event.order_id}, "
                f"ClientOrderId: {event.client_order_id}, Status: fill"
            )
        if event.event_type == "POSITION_CLOSED":
            return f"[EXIT] Ticker: {event.ticker}, Side: {event.side}, Entry: {event.entry_price}, Exit: {event.exit_price}, P/L: {event.pnl_pct:.2%}, Reason: {event.exit_reason}"
        return event.model_dump_json()


class CallbackEventHandler(EventHandler):
    """Calls a callback function for each event."""

    def __init__(self, callback: Callable[[TradingEvent], None]):
        self.callback = callback

    def handle(self, event: TradingEvent) -> None:
        self.callback(event)


class EventEmitter:
    """
    Central event emission system.

    Usage:
        emitter = EventEmitter()
        emitter.add_handler(ConsoleEventHandler())
        emitter.add_handler(FileEventHandler())

        emitter.emit(EntryTriggeredEvent(...))
    """

    _instance: "EventEmitter | None" = None
    _lock = threading.Lock()

    def __init__(self):
        self._handlers: list[EventHandler] = []

    @classmethod
    def get_instance(cls) -> "EventEmitter":
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance.add_handler(ConsoleEventHandler())
                    cls._instance.add_handler(AnalyticsEventHandler())
        return cls._instance

    def add_handler(self, handler: EventHandler) -> None:
        """Add an event handler."""
        self._handlers.append(handler)

    def remove_handler(self, handler: EventHandler) -> None:
        """Remove an event handler."""
        self._handlers.remove(handler)

    def emit(self, event: TradingEvent) -> None:
        """Emit an event to all handlers."""
        for handler in self._handlers:
            try:
                handler.handle(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}", exc_info=True)

    def clear_handlers(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()


def emit_event(event: TradingEvent) -> None:
    """Emit an event using the global emitter."""
    EventEmitter.get_instance().emit(event)
