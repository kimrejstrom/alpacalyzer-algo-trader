"""
Execution engine for trade management.

EXIT MECHANISM PRECEDENCE (Issue #73):
=====================================

This module implements a two-tier exit system with clear precedence rules
to avoid conflicts between automatic and manual exit mechanisms.

1. BRACKET ORDERS (Primary Exit Mechanism)
   ----------------------------------------
   - Created via OrderManager.submit_bracket_order() at entry time
   - Contains stop_loss and take_profit legs as OCO (One-Cancels-Other)
   - Managed entirely by Alpaca broker infrastructure
   - Triggered automatically by price movement
   - Advantages:
     * Fastest execution (broker-side, no polling delay)
     * Most reliable (works even if our system is offline)
     * No race conditions with other exit mechanisms
   - Used for: Normal profit-taking and stop-loss scenarios

2. DYNAMIC EXITS (Secondary Exit Mechanism)
   -----------------------------------------
   - Evaluated via strategy.evaluate_exit() each execution cycle
   - Manually closes position via OrderManager.close_position()
   - Cancels any remaining bracket order legs before closing
   - Used for: Emergency conditions that bracket orders can't detect
   - Examples:
     * Catastrophic momentum collapse (e.g., -25% momentum)
     * Technical score collapse below threshold
     * Strategy-specific exit signals not based on price alone

PRECEDENCE RULE:
----------------
If a position has an active bracket order (has_bracket_order=True),
dynamic exit evaluation is SKIPPED entirely. This prevents:
  - Race conditions between broker and our system
  - Redundant close attempts on already-closing positions
  - Order rejection errors from Alpaca API

When dynamic exit IS triggered (has_bracket_order=False):
  1. All open orders for the ticker are canceled first
  2. Position is closed via market order
  3. Cooldown is applied to prevent immediate re-entry

LOGGING:
--------
- Bracket order skips are logged at DEBUG level
- Dynamic exit triggers are logged at INFO level with reason
- Exit mechanism type is recorded in ExitTriggeredEvent.exit_mechanism

See also:
- OrderManager.submit_bracket_order() for bracket order creation
- OrderManager.close_position() for dynamic exit execution
- TrackedPosition.has_bracket_order for bracket order tracking
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import time as time_func
from typing import TYPE_CHECKING

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.events import CycleCompleteEvent, EntryTriggeredEvent, ExitTriggeredEvent, emit_event
from alpacalyzer.execution.cooldown import CooldownManager
from alpacalyzer.execution.order_manager import OrderManager, OrderParams
from alpacalyzer.execution.position_tracker import PositionTracker, TrackedPosition
from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue
from alpacalyzer.execution.state import STATE_VERSION, EngineState
from alpacalyzer.strategies.base import EntryDecision, ExitDecision, MarketContext
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)

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
        signal_cache_ttl: TTL for technical signal cache in seconds
    """

    check_interval_seconds: int = 120
    max_positions: int = 10
    daily_loss_limit_pct: float = 0.05
    analyze_mode: bool = False
    signal_cache_ttl: float = 300.0


@dataclass
class CachedSignal:
    """Cached technical signal with timestamp."""

    signal: TradingSignals
    timestamp: float
    ttl: float


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

        self._signal_cache: dict[str, CachedSignal] = {}
        self._cache_ttl = self.config.signal_cache_ttl
        self._ta = TechnicalAnalyzer()

        self.load_state(reset=reset_state)

    def _get_cached_signal(self, ticker: str) -> TradingSignals | None:
        """Get cached signal if within TTL."""
        if ticker not in self._signal_cache:
            return None

        cached = self._signal_cache[ticker]
        age = time_func() - cached.timestamp

        if age < cached.ttl:
            return cached.signal
        del self._signal_cache[ticker]
        return None

    def _cache_signal(self, ticker: str, signal: TradingSignals, ttl: float | None = None) -> None:
        """Cache a technical signal."""
        if ttl is None:
            ttl = self._cache_ttl

        self._signal_cache[ticker] = CachedSignal(
            signal=signal,
            timestamp=time_func(),
            ttl=ttl,
        )

    def _clear_expired_cache(self) -> None:
        """Remove expired entries from cache."""
        current_time = time_func()
        expired = [ticker for ticker, cached in self._signal_cache.items() if current_time - cached.timestamp > cached.ttl]
        for ticker in expired:
            del self._signal_cache[ticker]

    def run_cycle(self) -> None:
        """
        Execute one cycle of the trading loop.

        Order of operations:
        1. Sync positions from broker
        2. Clear expired cache
        3. Process exits (capital protection first)
        4. Process entries (new positions)
        5. Update cooldowns
        6. Emit summary event
        """
        if self.config.analyze_mode:
            self._run_analyze_cycle()
            return

        self._clear_expired_cache()

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
        """
        Evaluate and execute exit for a position.

        Exit Mechanism Precedence:
        --------------------------
        1. If position has active bracket order → SKIP dynamic exit
           (Bracket order handles stop_loss/take_profit automatically)
        2. If no bracket order → Evaluate strategy.evaluate_exit()
           (Used for emergency conditions like momentum collapse)

        Bracket Order Sync (Issue #99):
        --------------------------------
        Before skipping dynamic exit, we verify the bracket order still exists
        by querying the broker. This handles cases where bracket orders are
        canceled externally (via Alpaca dashboard, API, or fills).

        See module docstring for full precedence documentation.
        """
        if position.has_bracket_order:
            # Verify bracket order still exists before skipping (Issue #99)
            self.positions.sync_bracket_order_status(position.ticker)

            # Re-check after sync - bracket order may have been canceled
            if position.has_bracket_order:
                logger.debug(f"exit skipped, bracket active | ticker={position.ticker} stop={position.stop_loss} target={position.target}")
                return
            # If bracket order is gone, fall through to dynamic exit evaluation

        signals = self._get_cached_signal(position.ticker)

        if signals is None:
            signals = self._ta.analyze_stock(position.ticker)
            if signals is not None:
                self._cache_signal(position.ticker, signals)
                logger.debug(f"signal cache miss | ticker={position.ticker}")
            else:
                logger.warning(f"technical analysis failed | ticker={position.ticker}")
                return

        logger.debug(f"signal cache hit | ticker={position.ticker}")

        context = self._build_market_context()
        decision = self.strategy.evaluate_exit(position, signals, context)

        if decision.should_exit:
            self._execute_exit(position, decision)

    def _process_entry(self, signal: PendingSignal, context: MarketContext) -> None:
        """Evaluate and execute entry for a signal."""
        ta_signals = self._get_cached_signal(signal.ticker)

        if ta_signals is None:
            ta_signals = self._ta.analyze_stock(signal.ticker)
            if ta_signals is not None:
                self._cache_signal(signal.ticker, ta_signals)
                logger.debug(f"signal cache miss | ticker={signal.ticker}")
            else:
                logger.warning(f"technical analysis failed | ticker={signal.ticker}")
                return

        logger.debug(f"signal cache hit | ticker={signal.ticker}")

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
        """
        Execute exit order for a position via dynamic exit mechanism.

        This is the SECONDARY exit path, used only when:
        - Position has no active bracket order (has_bracket_order=False)
        - Strategy.evaluate_exit() returned should_exit=True

        The dynamic exit will:
        1. Cancel any remaining open orders for the ticker
        2. Close the position via market order
        3. Apply cooldown to prevent immediate re-entry
        """
        logger.info(f"dynamic exit triggered | ticker={position.ticker} reason={decision.reason} urgency={decision.urgency}")

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
                    exit_mechanism="dynamic_exit",
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
            logger.warning(f"elevated VIX detected | vix={vix:.2f}")

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
        self._clear_expired_cache()
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
                strategy_state=self.strategy.to_dict(),
            )

            STATE_FILE.write_text(state.to_json(), encoding="utf-8")
            logger.debug(f"state saved | path={STATE_FILE}")
        except Exception as e:
            logger.error(f"state save failed | error={e}")

    def load_state(self, reset: bool = False) -> None:
        """
        Load engine state from disk.

        Args:
            reset: If True, ignore saved state and start fresh
        """
        if reset or not STATE_FILE.exists():
            logger.info("starting with fresh state")
            return

        try:
            state_json = STATE_FILE.read_text(encoding="utf-8")
            state = EngineState.from_json(state_json)

            # Handle version migration: v1.0.0 -> v1.1.0
            # v1.0.0 states don't have strategy_state, from_json defaults it to {}
            if state.version == "1.0.0":
                logger.info("migrating state | from=v1.0.0 to=v1.1.0")
                # Continue loading - strategy_state will be empty dict
            elif state.version != STATE_VERSION:
                logger.warning(f"state version mismatch | saved={state.version} expected={STATE_VERSION}")
                return

            logger.info(f"loading state | timestamp={state.timestamp}")

            self.signal_queue = SignalQueue.from_dict(state.signal_queue)
            self.positions = PositionTracker.from_dict(state.positions)
            self.cooldowns = CooldownManager.from_dict(state.cooldowns)
            self.orders = OrderManager.from_dict(state.orders)

            # Restore strategy state (Issue #98)
            self.strategy.from_dict(state.strategy_state)

            logger.info(f"state loaded | signals={len(self.signal_queue._heap)} positions={len(self.positions._positions)} cooldowns={len(self.cooldowns._cooldowns)}")
        except Exception as e:
            logger.error(f"state load failed, starting fresh | error={e}")
