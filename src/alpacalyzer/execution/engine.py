"""Execution engine for trade management."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from alpacalyzer.execution.cooldown import CooldownManager
from alpacalyzer.execution.order_manager import OrderManager, OrderParams
from alpacalyzer.execution.position_tracker import PositionTracker, TrackedPosition
from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue
from alpacalyzer.strategies.base import EntryDecision, ExitDecision, MarketContext

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
    ):
        self.strategy = strategy
        self.config = config or ExecutionConfig()
        self.signal_queue = signal_queue or SignalQueue()
        self.positions = position_tracker or PositionTracker()
        self.cooldowns = cooldown_manager or CooldownManager()
        self.orders = order_manager or OrderManager(analyze_mode=self.config.analyze_mode)

        self._running = False

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
        self.orders.close_position(position.ticker)
        self.positions.remove_position(position.ticker)

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

        self.orders.submit_bracket_order(params)
        self.cooldowns.add_cooldown(signal.ticker, "entry_filled", "execution_engine")

    def _build_market_context(self) -> MarketContext:
        """Build market and account context."""
        from alpacalyzer.trading.alpaca_client import get_account_info, get_market_status

        account_info = get_account_info()
        vix = 20.0  # TODO: Fetch VIX from market data API
        market_status = get_market_status()

        return MarketContext(
            vix=vix,
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

    def _emit_cycle_complete(self) -> None:
        """Emit cycle complete event (would go to event logger)."""
        # Placeholder for event emission
        pass

    def add_signal(self, signal: PendingSignal) -> None:
        """Add a signal to the queue for processing."""
        self.signal_queue.add(signal)

    def start(self) -> None:
        """Start the execution loop."""
        self._running = True

    def stop(self) -> None:
        """Stop the execution loop."""
        self._running = False
