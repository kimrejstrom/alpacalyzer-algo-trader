"""Execution engine for trade management."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from alpacalyzer.events import CycleCompleteEvent, EntryTriggeredEvent, ExitTriggeredEvent, emit_event
from alpacalyzer.execution.cooldown import CooldownManager
from alpacalyzer.execution.order_manager import OrderManager, OrderParams
from alpacalyzer.execution.position_tracker import PositionTracker, TrackedPosition
from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue
from alpacalyzer.execution.state import STATE_VERSION, EngineState
from alpacalyzer.strategies.base import EntryDecision, ExitDecision, MarketContext
from alpacalyzer.utils.logger import get_logger

logger = get_logger()

STATE_FILE = Path(".alpacalyzer-state.json")

if TYPE_CHECKING:
    from alpacalyzer.strategies.base import Strategy


@dataclass
class ExecutionConfig:
    """
    Configuration for the execution engine.

    Attributes:
        check_interval_seconds: How often to run the cycle (in seconds)
        max_positions: Maximum number of concurrent positions
        daily_loss_limit_pct: Maximum daily loss percentage
        analyze_mode: If True, skip order submission
    """

    check_interval_seconds: int = 120
    max_positions: int = 10
    daily_loss_limit_pct: float = 0.05
    analyze_mode: bool = False


class ExecutionEngine:
    """
    Single execution loop for trade management.

    Responsibilities:
    - Process exit conditions (protect capital first)
    - Process entry conditions
    - Manage order lifecycle
    - Emit events for logging
    """

    def __init__(
        self,
        strategy: "Strategy",
        config: ExecutionConfig | None = None,
        signal_queue: SignalQueue | None = None,
        position_tracker: PositionTracker | None = None,
        cooldown_manager: CooldownManager | None = None,
        order_manager: OrderManager | None = None,
        reset_state: bool = False,
    ):
        self.strategy = strategy
        self.config = config or ExecutionConfig()
        self.signal_queue = signal_queue or SignalQueue()
        self.positions = position_tracker or PositionTracker()
        self.cooldowns = cooldown_manager or CooldownManager()
        self.orders = order_manager or OrderManager(analyze_mode=self.config.analyze_mode)

        self._running = False

        self.load_state(reset=reset_state)

    def run_cycle(self) -> None:
        """
        Execute one cycle of the trading loop.

        Order of operations:
        1. Sync positions from broker
        2. Process exits (capital protection first)
        3. Process entries (new positions)
        4. Update cooldowns
        5. Emit summary event
        """
        if self.config.analyze_mode:
            self._run_analyze_cycle()
            return

        # 1. Sync positions
        self.positions.sync_from_broker()

        # 2. Process exits FIRST (protect capital)
        for position in self.positions.get_all():
            self._process_exit(position)

        # 3. Process entries
        context = self._build_market_context()
        while not self.signal_queue.is_empty():
            signal = self.signal_queue.peek()
            if signal is None:
                break

            if self._can_take_position(signal, context):
                self._process_entry(signal, context)
                self.signal_queue.pop()
            else:
                break  # Stop if we can't take more positions

        # 4. Update cooldowns
        self.cooldowns.cleanup_expired()

        # 5. Emit cycle complete event
        self._emit_cycle_complete()

        # 6. Save state
        self.save_state()

    def _process_exit(self, position: TrackedPosition) -> None:
        """Evaluate and execute exit for a position."""
        from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer

        signals = TechnicalAnalyzer().analyze_stock(position.ticker)
        if signals is None:
            return

        context = self._build_market_context()
        decision = self.strategy.evaluate_exit(position, signals, context)

        if decision.should_exit:
            self._execute_exit(position, decision)

    def _process_entry(self, signal: PendingSignal, context: MarketContext) -> None:
        """Evaluate and execute entry for a signal."""
        from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer

        ta_signals = TechnicalAnalyzer().analyze_stock(signal.ticker)
        if ta_signals is None:
            return

        decision = self.strategy.evaluate_entry(
            ta_signals,
            context,
            signal.agent_recommendation,
        )

        if decision.should_enter:
            self._execute_entry(signal, decision)

    def _can_take_position(self, signal: PendingSignal, context: MarketContext) -> bool:
        """Check if we can take a new position."""
        if self.positions.count() >= self.config.max_positions:
            return False

        if signal.ticker in context.existing_positions:
            return False

        if signal.ticker in context.cooldown_tickers:
            return False

        return True

    def _execute_exit(self, position: TrackedPosition, decision: ExitDecision) -> None:
        """Execute exit order for a position."""
        result = self.orders.close_position(position.ticker)
        if result:
            exit_price = float(result.filled_avg_price) if result.filled_avg_price else 0.0

            emit_event(
                ExitTriggeredEvent(
                    timestamp=datetime.now(UTC),
                    ticker=position.ticker,
                    strategy="execution_engine",
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.avg_entry_price,
                    exit_price=exit_price,
                    pnl=position.unrealized_pnl,
                    pnl_pct=position.unrealized_pnl_pct,
                    hold_duration_hours=0.0,
                    reason=decision.reason,
                    urgency=decision.urgency,
                )
            )
            self.positions.remove_position(position.ticker)
            self.cooldowns.add_cooldown(position.ticker, decision.reason, "execution_engine")

    def _execute_entry(self, signal: PendingSignal, decision: EntryDecision) -> None:
        """Execute entry order for a signal."""
        params = OrderParams(
            ticker=signal.ticker,
            side=signal.action,
            quantity=decision.suggested_size,
            entry_price=decision.entry_price,
            stop_loss=decision.stop_loss,
            target=decision.target,
            strategy_name="execution_engine",
        )

        emit_event(
            EntryTriggeredEvent(
                timestamp=datetime.now(UTC),
                ticker=signal.ticker,
                strategy="execution_engine",
                side=signal.action,
                quantity=decision.suggested_size,
                entry_price=decision.entry_price,
                stop_loss=decision.stop_loss,
                target=decision.target,
                reason=decision.reason,
            )
        )

        self.orders.submit_bracket_order(params)
        self.cooldowns.add_cooldown(signal.ticker, "entry_filled", "execution_engine")

    def _build_market_context(self) -> MarketContext:
        """Build market and account context."""
        from alpacalyzer.data.api import get_vix
        from alpacalyzer.trading.alpaca_client import get_account_info, get_market_status

        account_info = get_account_info()
        vix = get_vix(use_cache=True)
        market_status = get_market_status()

        if vix and vix > 30.0:
            logger.warning(f"Elevated VIX detected: {vix:.2f}")

        return MarketContext(
            vix=vix if vix is not None else 20.0,
            market_status=market_status,
            account_equity=account_info["equity"],
            buying_power=account_info["buying_power"],
            existing_positions=list(self.positions._positions.keys()),
            cooldown_tickers=self.cooldowns.get_all_tickers(),
        )

    def _run_analyze_cycle(self) -> None:
        """Run cycle in analyze mode (no order submission)."""
        # In analyze mode, we still sync and evaluate, but don't submit orders
        self.positions.sync_from_broker()

        for position in self.positions.get_all():
            self._process_exit(position)

        context = self._build_market_context()
        while not self.signal_queue.is_empty():
            signal = self.signal_queue.peek()
            if signal is None:
                break

            if self._can_take_position(signal, context):
                self._process_entry(signal, context)
                self.signal_queue.pop()
            else:
                break

        self.cooldowns.cleanup_expired()
        self._emit_cycle_complete()

        # Save state after cycle completes
        self.save_state()

    def _emit_cycle_complete(self) -> None:
        """Emit cycle complete event."""
        entries_evaluated = len(self.signal_queue)
        entries_triggered = sum(1 for pos in self.positions.get_all())
        exits_evaluated = len(self.positions.get_all())
        exits_triggered = exits_evaluated
        signals_pending = self.signal_queue.size()
        positions_open = self.positions.count()

        emit_event(
            CycleCompleteEvent(
                timestamp=datetime.now(UTC),
                entries_evaluated=entries_evaluated,
                entries_triggered=entries_triggered,
                exits_evaluated=exits_evaluated,
                exits_triggered=exits_triggered,
                signals_pending=signals_pending,
                positions_open=positions_open,
                duration_seconds=0.0,
            )
        )

    def add_signal(self, signal: PendingSignal) -> None:
        """Add a signal to the queue for processing."""
        self.signal_queue.add(signal)

    def start(self) -> None:
        """Start the execution loop."""
        self._running = True

    def stop(self) -> None:
        """Stop the execution loop."""
        self._running = False

    def save_state(self) -> None:
        """Save current engine state to disk."""
        try:
            state = EngineState(
                version=STATE_VERSION,
                timestamp=datetime.now(UTC),
                signal_queue=self.signal_queue.to_dict(),
                positions=self.positions.to_dict(),
                cooldowns=self.cooldowns.to_dict(),
                orders=self.orders.to_dict(),
            )

            STATE_FILE.write_text(state.to_json(), encoding="utf-8")
            logger.debug(f"State saved to {STATE_FILE}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state(self, reset: bool = False) -> None:
        """
        Load engine state from disk.

        Args:
            reset: If True, ignore saved state and start fresh
        """
        if reset or not STATE_FILE.exists():
            logger.info("Starting with fresh state")
            return

        try:
            state_json = STATE_FILE.read_text(encoding="utf-8")
            state = EngineState.from_json(state_json)

            if state.version != STATE_VERSION:
                logger.warning(f"State version mismatch: {state.version} != {STATE_VERSION}. Starting with fresh state.")
                return

            logger.info(f"Loading state from {state.timestamp}")

            self.signal_queue = SignalQueue.from_dict(state.signal_queue)
            self.positions = PositionTracker.from_dict(state.positions)
            self.cooldowns = CooldownManager.from_dict(state.cooldowns)
            self.orders = OrderManager.from_dict(state.orders)

            logger.info(f"State loaded: {len(self.signal_queue._heap)} signals, {len(self.positions._positions)} positions, {len(self.cooldowns._cooldowns)} cooldowns")
        except Exception as e:
            logger.error(f"Failed to load state: {e}. Starting fresh.")
