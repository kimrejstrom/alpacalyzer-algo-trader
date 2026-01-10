"""Events module for structured logging."""

from alpacalyzer.events.emitter import (
    AnalyticsEventHandler,
    CallbackEventHandler,
    ConsoleEventHandler,
    EventEmitter,
    EventHandler,
    FileEventHandler,
    emit_event,
)
from alpacalyzer.events.models import (
    CooldownEndedEvent,
    CooldownStartedEvent,
    CycleCompleteEvent,
    EntryBlockedEvent,
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    OrderCanceledEvent,
    OrderFilledEvent,
    OrderRejectedEvent,
    OrderSubmittedEvent,
    PositionClosedEvent,
    PositionOpenedEvent,
    ScanCompleteEvent,
    SignalExpiredEvent,
    SignalGeneratedEvent,
    TradingEvent,
)

__all__ = [
    # Event models
    "ScanCompleteEvent",
    "SignalGeneratedEvent",
    "SignalExpiredEvent",
    "EntryTriggeredEvent",
    "EntryBlockedEvent",
    "ExitTriggeredEvent",
    "OrderSubmittedEvent",
    "OrderFilledEvent",
    "OrderCanceledEvent",
    "OrderRejectedEvent",
    "PositionOpenedEvent",
    "PositionClosedEvent",
    "CooldownStartedEvent",
    "CooldownEndedEvent",
    "CycleCompleteEvent",
    "TradingEvent",
    # Event emitter
    "EventEmitter",
    "EventHandler",
    "ConsoleEventHandler",
    "FileEventHandler",
    "AnalyticsEventHandler",
    "CallbackEventHandler",
    "emit_event",
]
