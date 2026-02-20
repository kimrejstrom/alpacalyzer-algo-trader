"""Event models for structured logging."""

from datetime import datetime

from pydantic import BaseModel, Field


class ScanCompleteEvent(BaseModel):
    """Emitted when a scanner finishes."""

    event_type: str = "SCAN_COMPLETE"
    timestamp: datetime = Field(description="When the scan completed")
    source: str = Field(description="Scanner source (reddit, social, technical, finviz)")
    tickers_found: list[str] = Field(description="List of tickers discovered")
    duration_seconds: float = Field(description="Scan duration in seconds")


class SignalGeneratedEvent(BaseModel):
    """Emitted when analysis generates a trading signal."""

    event_type: str = "SIGNAL_GENERATED"
    timestamp: datetime = Field(description="When the signal was generated")
    ticker: str = Field(description="Stock ticker symbol")
    action: str = Field(description="Trading action (buy, sell, short, cover, hold)")
    confidence: float = Field(description="Confidence score (0.0-1.0)")
    source: str = Field(description="Signal source (hedge_fund, manual)")
    strategy: str = Field(description="Strategy that generated the signal")
    reasoning: str | None = Field(default=None, description="Reasoning for the signal")


class SignalExpiredEvent(BaseModel):
    """Emitted when a signal expires without execution."""

    event_type: str = "SIGNAL_EXPIRED"
    timestamp: datetime = Field(description="When the signal expired")
    ticker: str = Field(description="Stock ticker symbol")
    created_at: datetime = Field(description="When the signal was created")
    reason: str = Field(description="Reason for expiration")


class EntryTriggeredEvent(BaseModel):
    """Emitted when entry conditions are met."""

    event_type: str = "ENTRY_TRIGGERED"
    timestamp: datetime = Field(description="When entry was triggered")
    ticker: str = Field(description="Stock ticker symbol")
    strategy: str = Field(description="Strategy that triggered entry")
    side: str = Field(description="Position side (long, short)")
    quantity: int = Field(description="Number of shares")
    entry_price: float = Field(description="Entry price per share")
    stop_loss: float = Field(description="Stop loss price")
    target: float = Field(description="Target price")
    reason: str = Field(description="Reason for entry")


class EntryBlockedEvent(BaseModel):
    """Emitted when entry is blocked."""

    event_type: str = "ENTRY_BLOCKED"
    timestamp: datetime = Field(description="When entry was blocked")
    ticker: str = Field(description="Stock ticker symbol")
    strategy: str = Field(description="Strategy that attempted entry")
    reason: str = Field(description="Reason for blocking")
    conditions_met: int = Field(description="Number of conditions met")
    conditions_total: int = Field(description="Total number of conditions")


class ExitTriggeredEvent(BaseModel):
    """Emitted when exit conditions are met."""

    event_type: str = "EXIT_TRIGGERED"
    timestamp: datetime = Field(description="When exit was triggered")
    ticker: str = Field(description="Stock ticker symbol")
    strategy: str = Field(description="Strategy that triggered exit")
    side: str = Field(description="Position side (long, short)")
    quantity: int = Field(description="Number of shares")
    entry_price: float = Field(description="Original entry price")
    exit_price: float = Field(description="Exit price per share")
    pnl: float = Field(description="Profit/loss in dollars")
    pnl_pct: float = Field(description="Profit/loss as percentage")
    hold_duration_hours: float = Field(description="How long position was held")
    reason: str = Field(description="Reason for exit")
    urgency: str = Field(description="Exit urgency (normal, urgent, immediate)")
    exit_mechanism: str = Field(
        default="dynamic_exit",
        description="Exit mechanism that triggered (dynamic_exit, bracket_order)",
    )


class OrderSubmittedEvent(BaseModel):
    """Emitted when an order is submitted."""

    event_type: str = "ORDER_SUBMITTED"
    timestamp: datetime = Field(description="When order was submitted")
    ticker: str = Field(description="Stock ticker symbol")
    order_id: str = Field(description="Alpaca order ID")
    client_order_id: str = Field(description="Client order ID")
    side: str = Field(description="Order side (buy, sell)")
    quantity: int = Field(description="Number of shares")
    order_type: str = Field(description="Order type (market, limit, stop, stop_limit)")
    limit_price: float | None = Field(default=None, description="Limit price (if applicable)")
    stop_price: float | None = Field(default=None, description="Stop price (if applicable)")
    strategy: str = Field(description="Strategy that placed the order")


class OrderFilledEvent(BaseModel):
    """Emitted when an order is filled."""

    event_type: str = "ORDER_FILLED"
    timestamp: datetime = Field(description="When order was filled")
    ticker: str = Field(description="Stock ticker symbol")
    order_id: str = Field(description="Alpaca order ID")
    client_order_id: str = Field(description="Client order ID")
    side: str = Field(description="Order side (buy, sell)")
    quantity: int = Field(description="Order quantity")
    filled_qty: int = Field(description="Filled quantity")
    avg_price: float = Field(description="Average fill price")
    strategy: str = Field(description="Strategy that placed the order")


class OrderCanceledEvent(BaseModel):
    """Emitted when an order is canceled."""

    event_type: str = "ORDER_CANCELED"
    timestamp: datetime = Field(description="When order was canceled")
    ticker: str = Field(description="Stock ticker symbol")
    order_id: str = Field(description="Alpaca order ID")
    client_order_id: str = Field(description="Client order ID")
    reason: str | None = Field(default=None, description="Reason for cancellation")


class OrderRejectedEvent(BaseModel):
    """Emitted when an order is rejected."""

    event_type: str = "ORDER_REJECTED"
    timestamp: datetime = Field(description="When order was rejected")
    ticker: str = Field(description="Stock ticker symbol")
    order_id: str | None = Field(default=None, description="Alpaca order ID (if assigned)")
    client_order_id: str = Field(description="Client order ID")
    reason: str = Field(description="Reason for rejection")


class PositionOpenedEvent(BaseModel):
    """Emitted when a new position is opened."""

    event_type: str = "POSITION_OPENED"
    timestamp: datetime = Field(description="When position was opened")
    ticker: str = Field(description="Stock ticker symbol")
    side: str = Field(description="Position side (long, short)")
    quantity: int = Field(description="Number of shares")
    entry_price: float = Field(description="Entry price per share")
    strategy: str = Field(description="Strategy that opened position")
    order_id: str = Field(description="Order ID that opened position")


class PositionClosedEvent(BaseModel):
    """Emitted when a position is closed."""

    event_type: str = "POSITION_CLOSED"
    timestamp: datetime = Field(description="When position was closed")
    ticker: str = Field(description="Stock ticker symbol")
    side: str = Field(description="Position side (long, short)")
    quantity: int = Field(description="Number of shares")
    entry_price: float = Field(description="Original entry price")
    exit_price: float = Field(description="Exit price per share")
    pnl: float = Field(description="Profit/loss in dollars")
    pnl_pct: float = Field(description="Profit/loss as percentage")
    hold_duration_hours: float = Field(description="How long position was held")
    strategy: str = Field(description="Strategy that closed position")
    exit_reason: str = Field(description="Reason for closing position")


class CooldownStartedEvent(BaseModel):
    """Emitted when a ticker enters cooldown."""

    event_type: str = "COOLDOWN_STARTED"
    timestamp: datetime = Field(description="When cooldown started")
    ticker: str = Field(description="Stock ticker symbol")
    duration_hours: int = Field(description="Cooldown duration in hours")
    reason: str = Field(description="Reason for cooldown")
    strategy: str = Field(description="Strategy that triggered cooldown")


class CooldownEndedEvent(BaseModel):
    """Emitted when a cooldown expires."""

    event_type: str = "COOLDOWN_ENDED"
    timestamp: datetime = Field(description="When cooldown ended")
    ticker: str = Field(description="Stock ticker symbol")


class CycleCompleteEvent(BaseModel):
    """Emitted at the end of each execution cycle."""

    event_type: str = "CYCLE_COMPLETE"
    timestamp: datetime = Field(description="When cycle completed")
    entries_evaluated: int = Field(description="Number of entries evaluated")
    entries_triggered: int = Field(description="Number of entries triggered")
    exits_evaluated: int = Field(description="Number of exits evaluated")
    exits_triggered: int = Field(description="Number of exits triggered")
    signals_pending: int = Field(description="Number of signals pending execution")
    positions_open: int = Field(description="Number of open positions")
    duration_seconds: float = Field(description="Cycle duration in seconds")


class LLMCallEvent(BaseModel):
    """Emitted when an LLM call completes."""

    event_type: str = "LLM_CALL"
    timestamp: datetime = Field(description="When the call completed")
    agent: str = Field(description="Agent/caller that made the LLM call")
    model: str = Field(description="Model name used")
    tier: str = Field(description="LLM tier (fast, standard, deep)")
    latency_ms: float = Field(description="Call latency in milliseconds")
    prompt_tokens: int = Field(default=0, description="Prompt token count")
    completion_tokens: int = Field(default=0, description="Completion token count")
    total_tokens: int = Field(default=0, description="Total token count")
    cost_usd: float | None = Field(default=None, description="Estimated cost in USD")


class ErrorEvent(BaseModel):
    """Emitted when a notable error occurs."""

    event_type: str = "ERROR"
    timestamp: datetime = Field(description="When the error occurred")
    error_type: str = Field(description="Error category (rate_limit, api_error, llm_error, order_error)")
    component: str = Field(description="Component that raised the error")
    message: str = Field(description="Error message")
    ticker: str | None = Field(default=None, description="Related ticker if applicable")


# Union type for all events
TradingEvent = (
    ScanCompleteEvent
    | SignalGeneratedEvent
    | SignalExpiredEvent
    | EntryTriggeredEvent
    | EntryBlockedEvent
    | ExitTriggeredEvent
    | OrderSubmittedEvent
    | OrderFilledEvent
    | OrderCanceledEvent
    | OrderRejectedEvent
    | PositionOpenedEvent
    | PositionClosedEvent
    | CooldownStartedEvent
    | CooldownEndedEvent
    | CycleCompleteEvent
    | LLMCallEvent
    | ErrorEvent
)
