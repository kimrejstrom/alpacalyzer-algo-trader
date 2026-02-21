"""Event emitter for structured logging."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from alpacalyzer.events.models import TradingEvent
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


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

        # AGENT_REASONING is rendered via the progress display, not the logger
        if event.event_type == "AGENT_REASONING":
            return

        message = self._format_event(event)
        if event.event_type in ("LLM_CALL",):
            logger.debug(message)
        else:
            logger.info(message)

    def _format_event(self, event: TradingEvent) -> str:
        """Format event for console output."""
        event_type = event.event_type

        if event_type == "ENTRY_TRIGGERED":
            ticker = getattr(event, "ticker", "?")
            side = getattr(event, "side", "?").upper()
            qty = getattr(event, "quantity", 0)
            entry = getattr(event, "entry_price", 0)
            sl = getattr(event, "stop_loss", 0)
            tp = getattr(event, "target", 0)
            return f"📈 ENTRY: {ticker} {side} x{qty} @ ${entry:.2f} (SL: ${sl:.2f}, TP: ${tp:.2f})"
        if event_type == "EXIT_TRIGGERED":
            pnl = getattr(event, "pnl", 0)
            emoji = "✅" if pnl >= 0 else "❌"
            return f"{emoji} EXIT: {getattr(event, 'ticker', '?')} P/L: ${pnl:.2f} ({getattr(event, 'pnl_pct', 0):.2%}) - {getattr(event, 'reason', '?')}"
        if event_type == "SCAN_COMPLETE":
            return f"🔍 Scan complete ({getattr(event, 'source', '?')}): {len(getattr(event, 'tickers_found', []))} tickers found"
        if event_type == "SIGNAL_GENERATED":
            return f"📊 Signal: {getattr(event, 'ticker', '?')} {getattr(event, 'action', '?').upper()} (confidence: {getattr(event, 'confidence', 0) * 100:.0f}%)"
        if event_type == "ORDER_FILLED":
            return f"💰 Filled: {getattr(event, 'ticker', '?')} {getattr(event, 'side', '?').upper()} {getattr(event, 'filled_qty', 0)}x @ ${getattr(event, 'avg_price', 0):.2f}"
        if event_type == "CYCLE_COMPLETE":
            return f"🔄 Cycle: {getattr(event, 'entries_triggered', 0)} entries, {getattr(event, 'exits_triggered', 0)} exits, {getattr(event, 'positions_open', 0)} positions"
        if event_type == "LLM_CALL":
            agent = getattr(event, "agent", "unknown")
            model = getattr(event, "model", "?")
            latency = getattr(event, "latency_ms", 0)
            tokens = getattr(event, "total_tokens", 0)
            return f"🤖 LLM: {agent} | model={model} latency={latency:.0f}ms tokens={tokens}"
        if event_type == "ERROR":
            component = getattr(event, "component", "?")
            error_type = getattr(event, "error_type", "?")
            return f"⚠️ Error: {component} | type={error_type} msg={getattr(event, 'message', '?')}"
        if event_type == "AGENT_REASONING":
            agent = getattr(event, "agent", "unknown")
            tickers = getattr(event, "tickers", [])
            tickers_str = ", ".join(tickers) if tickers else "N/A"
            return f"[{agent}] tickers={tickers_str}"
        return f"[{event_type}] {getattr(event, 'ticker', getattr(event, 'agent', 'system'))}"


class FileEventHandler(EventHandler):
    """
    Writes events as JSON lines to a file with size-based rotation.

    Rotates when the file exceeds max_bytes. Keeps up to backup_count
    rotated files (events.jsonl.1, events.jsonl.2, etc.).
    """

    def __init__(
        self,
        file_path: str | None = None,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 3,
    ):
        from pathlib import Path

        self.file_path = file_path or "logs/events.jsonl"
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._lock = threading.Lock()
        # Ensure directory exists
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)

    def handle(self, event: TradingEvent) -> None:
        json_line = event.model_dump_json()

        with self._lock:
            self._rotate_if_needed()
            with open(self.file_path, "a") as f:
                f.write(json_line + "\n")

    def _rotate_if_needed(self) -> None:
        """Rotate the log file if it exceeds max_bytes."""
        from pathlib import Path

        path = Path(self.file_path)
        if not path.exists():
            return

        try:
            if path.stat().st_size < self.max_bytes:
                return
        except OSError:
            return

        # Rotate: events.jsonl.3 → deleted, .2 → .3, .1 → .2, current → .1
        for i in range(self.backup_count, 0, -1):
            src = Path(f"{self.file_path}.{i}")
            if i == self.backup_count:
                src.unlink(missing_ok=True)
            else:
                dst = Path(f"{self.file_path}.{i + 1}")
                if src.exists():
                    src.rename(dst)

        # Move current to .1
        backup_1 = Path(f"{self.file_path}.1")
        if path.exists():
            path.rename(backup_1)


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
                    cls._instance.add_handler(FileEventHandler())
        assert cls._instance is not None
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
                logger.error(f"event handler error | error={e}", exc_info=True)

    def clear_handlers(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()


def emit_event(event: TradingEvent) -> None:
    """Emit an event using the global emitter."""
    EventEmitter.get_instance().emit(event)
