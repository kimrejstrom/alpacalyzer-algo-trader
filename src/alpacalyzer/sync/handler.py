from alpacalyzer.events.emitter import EventHandler
from alpacalyzer.events.models import (
    AgentReasoningEvent,
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    LLMCallEvent,
    PositionClosedEvent,
    SignalGeneratedEvent,
    TradingEvent,
)
from alpacalyzer.sync.client import JournalSyncClient
from alpacalyzer.sync.models import (
    AgentSignalRecord,
    DecisionContext,
    TradeDecisionRecord,
)
from alpacalyzer.utils.logger import get_logger

logger = get_logger("sync.handler")


class JournalSyncHandler(EventHandler):
    """Event handler that syncs trade decisions to my-stock-journal."""

    def __init__(self, client: JournalSyncClient) -> None:
        self._client = client
        self._pending_context: dict[str, DecisionContext] = {}
        self._synced_trades: dict[str, str] = {}
        self._entry_times: dict[str, str] = {}
        self._llm_costs: list[dict] = []

    def handle(self, event: TradingEvent) -> None:
        """Handle an event by accumulating context or syncing trades."""
        try:
            if isinstance(event, AgentReasoningEvent):
                self._handle_agent_reasoning(event)
            elif isinstance(event, SignalGeneratedEvent):
                self._handle_signal_generated(event)
            elif isinstance(event, LLMCallEvent):
                self._handle_llm_call(event)
            elif isinstance(event, EntryTriggeredEvent):
                self._handle_entry_triggered(event)
            elif isinstance(event, ExitTriggeredEvent):
                self._handle_exit_triggered(event)
            elif isinstance(event, PositionClosedEvent):
                self._handle_position_closed(event)
        except Exception as e:
            logger.warning(f"Error handling event {getattr(event, 'event_type', 'unknown')}: {e}")

    def _ensure_context(self, ticker: str) -> DecisionContext:
        """Ensure pending context exists for a ticker."""
        if ticker not in self._pending_context:
            self._pending_context[ticker] = DecisionContext()
        return self._pending_context[ticker]

    def _handle_agent_reasoning(self, event: AgentReasoningEvent) -> None:
        """Handle AgentReasoningEvent by extracting signals from reasoning."""
        for ticker in event.tickers:
            ctx = self._ensure_context(ticker)
            reasoning = event.reasoning
            if isinstance(reasoning, dict):
                signal = reasoning.get("signal")
                confidence = reasoning.get("confidence")
            else:
                signal = None
                confidence = None

            ctx.agent_signals.append(
                AgentSignalRecord(
                    agent=event.agent,
                    signal=signal,
                    confidence=confidence,
                    reasoning=event.reasoning,
                )
            )

    def _handle_signal_generated(self, event: SignalGeneratedEvent) -> None:
        """Handle SignalGeneratedEvent by storing strategy params and scanner source."""
        ctx = self._ensure_context(event.ticker)
        ctx.strategy_params = {
            "strategy": event.strategy,
            "confidence": event.confidence,
            "reasoning": event.reasoning,
        }
        if event.source and event.source != "hedge_fund":
            ctx.scanner_source = event.source

    def _handle_llm_call(self, event: LLMCallEvent) -> None:
        """Handle LLMCallEvent by storing cost data globally, to attach at entry."""
        self._llm_costs.append(
            {
                "agent": event.agent,
                "model": event.model,
                "latency_ms": event.latency_ms,
                "total_tokens": event.total_tokens,
                "cost_usd": event.cost_usd,
            }
        )

    def _handle_entry_triggered(self, event: EntryTriggeredEvent) -> None:
        """Handle EntryTriggeredEvent by syncing trade record."""
        ctx = self._pending_context.get(event.ticker, DecisionContext())

        if self._llm_costs:
            ctx.llm_costs = self._llm_costs.copy()
            self._llm_costs.clear()

        side_upper = event.side.upper()
        if side_upper not in ("LONG", "SHORT"):
            logger.warning(f"Invalid side '{event.side}' for {event.ticker}, defaulting to LONG")
            side_upper = "LONG"

        entry_time = event.timestamp.isoformat()
        self._entry_times[event.ticker] = entry_time

        record = TradeDecisionRecord(
            ticker=event.ticker,
            side=side_upper,
            shares=event.quantity,
            entry_price=str(event.entry_price),
            target_price=str(event.target) if event.target else None,
            stop_price=str(event.stop_loss) if event.stop_loss else None,
            entry_date=entry_time,
            status="OPEN",
            decision_context=ctx,
            strategy_name=event.strategy,
            exit_reason=event.reason,
        )

        response = self._client.sync_trade(record)
        if response and "id" in response:
            self._synced_trades[event.ticker] = response["id"]

        if event.ticker in self._pending_context:
            del self._pending_context[event.ticker]

    def _handle_exit_triggered(self, event: ExitTriggeredEvent) -> None:
        """Handle ExitTriggeredEvent by syncing updated trade record."""
        ctx = self._pending_context.get(event.ticker, DecisionContext())

        if self._llm_costs:
            ctx.llm_costs = self._llm_costs.copy()
            self._llm_costs.clear()

        entry_time = self._entry_times.get(event.ticker)
        status = "WIN" if event.pnl >= 0 else "LOSS"

        side_upper = event.side.upper()
        if side_upper not in ("LONG", "SHORT"):
            logger.warning(f"Invalid side '{event.side}' for {event.ticker}, defaulting to LONG")
            side_upper = "LONG"

        record = TradeDecisionRecord(
            ticker=event.ticker,
            side=side_upper,
            shares=event.quantity,
            entry_price=str(event.entry_price),
            exit_price=str(event.exit_price),
            entry_date=entry_time or event.timestamp.isoformat(),
            exit_date=event.timestamp.isoformat(),
            status=status,
            realized_pnl=event.pnl,
            realized_pnl_pct=event.pnl_pct,
            hold_duration_hours=event.hold_duration_hours,
            exit_reason=event.reason,
            exit_mechanism=event.exit_mechanism,
            decision_context=ctx,
            strategy_name=event.strategy,
        )

        self._client.sync_trade(record)

        if event.ticker in self._synced_trades:
            del self._synced_trades[event.ticker]
        if event.ticker in self._entry_times:
            del self._entry_times[event.ticker]
        if event.ticker in self._pending_context:
            del self._pending_context[event.ticker]

    def _handle_position_closed(self, event: PositionClosedEvent) -> None:
        """Handle PositionClosedEvent by syncing updated trade record."""
        ctx = self._pending_context.get(event.ticker, DecisionContext())

        if self._llm_costs:
            ctx.llm_costs = self._llm_costs.copy()
            self._llm_costs.clear()

        entry_time = self._entry_times.get(event.ticker)
        status = "WIN" if event.pnl >= 0 else "LOSS"

        side_upper = event.side.upper()
        if side_upper not in ("LONG", "SHORT"):
            logger.warning(f"Invalid side '{event.side}' for {event.ticker}, defaulting to LONG")
            side_upper = "LONG"

        record = TradeDecisionRecord(
            ticker=event.ticker,
            side=side_upper,
            shares=event.quantity,
            entry_price=str(event.entry_price),
            exit_price=str(event.exit_price),
            entry_date=entry_time or event.timestamp.isoformat(),
            exit_date=event.timestamp.isoformat(),
            status=status,
            realized_pnl=event.pnl,
            realized_pnl_pct=event.pnl_pct,
            hold_duration_hours=event.hold_duration_hours,
            exit_reason=event.exit_reason,
            decision_context=ctx,
            strategy_name=event.strategy,
        )

        self._client.sync_trade(record)

        if event.ticker in self._synced_trades:
            del self._synced_trades[event.ticker]
        if event.ticker in self._entry_times:
            del self._entry_times[event.ticker]
        if event.ticker in self._pending_context:
            del self._pending_context[event.ticker]
