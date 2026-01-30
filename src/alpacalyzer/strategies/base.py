"""
Base strategy protocol and dataclasses.

This module defines Strategy protocol, BaseStrategy abstract class,
and supporting dataclasses for entry/exit decisions and market context.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from alpaca.trading.models import Position as AlpacaPosition

    from alpacalyzer.analysis.technical_analysis import TradingSignals
    from alpacalyzer.data.models import TradingStrategy

    # Type alias for Position - at runtime this is alpaca.trading.models.Position
    # but we use any type in protocol to allow flexibility for backtesting
    Position = AlpacaPosition


@dataclass
class EntryDecision:
    """
    Decision result from evaluate_entry method.

    Attributes:
        should_enter: Whether to enter the position
        reason: Human-readable explanation of decision
        suggested_size: Number of shares to trade (0 if not entering)
        entry_price: Suggested entry price (0 if not entering)
        stop_loss: Stop loss price level (0 if not entering)
        target: Target/profit-taking price level (0 if not entering)
        side: Position side ("long" or "short")
    """

    should_enter: bool
    reason: str
    suggested_size: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    side: str = "long"


@dataclass
class ExitDecision:
    """
    Decision result from evaluate_exit method.

    Exit Mechanism Context (Issue #73):
    -----------------------------------
    This decision is used by the SECONDARY exit mechanism (dynamic exits).
    It is only evaluated when a position does NOT have an active bracket order.

    Primary exits (bracket orders) are handled automatically by the broker
    and do not use this decision class.

    Attributes:
        should_exit: Whether to exit the position via dynamic exit.
                     Only set True for emergency conditions that bracket
                     orders cannot detect (e.g., momentum collapse).
        reason: Human-readable explanation of decision. Logged and stored
                in exit events for debugging and analytics.
        urgency: Exit urgency level - affects execution priority:
                 - "normal": Standard exit, no special handling
                 - "urgent": Prioritize this exit in the queue
                 - "immediate": Execute as soon as possible (e.g., catastrophic loss)
    """

    should_exit: bool
    reason: str
    urgency: str = "normal"  # Options: "normal", "urgent", "immediate"


@dataclass
class MarketContext:
    """
    Market and account context for trading decisions.

    Attributes:
        vix: Current VIX (volatility index) value
        market_status: Current market status ("open", "closed", etc.)
        account_equity: Total account equity in USD
        buying_power: Available buying power in USD
        existing_positions: List of tickers currently held
        cooldown_tickers: List of tickers in cooldown period
    """

    vix: float
    market_status: str
    account_equity: float
    buying_power: float
    existing_positions: list[str]
    cooldown_tickers: list[str]


@runtime_checkable
class Strategy(Protocol):
    """
    Protocol defining the interface for trading strategies.

    All strategies must implement these three methods to make
    entry and exit decisions, and calculate position sizes.

    The @runtime_checkable decorator allows isinstance() checks
    to verify protocol compliance at runtime.

    DECISION FLOW:

    1. Agent (GPT-4 via TradingStrategist) provides:
       - entry_point: Suggested entry price
       - stop_loss: Suggested stop loss price
       - target_price: Suggested take profit price
       - quantity: Suggested number of shares
       - trade_type: 'long' or 'short'

    2. Strategy validates setup against its philosophy:
       - MomentumStrategy: Checks positive momentum trend
       - BreakoutStrategy: Checks for consolidation pattern
       - MeanReversionStrategy: Checks oversold/overbought conditions

    3. If conditions don't match, STRATEGY REJECTS:
       - Return EntryDecision(should_enter=False, reason="...")
       - Agent's setup is discarded

    4. If conditions match, STRATEGY USES AGENT VALUES:
       - Use agent's entry_point, stop_loss, target_price, quantity
       - DO NOT recalculate these values
       - Return EntryDecision(should_enter=True, ...)

    AUTHORITY:
    - Agents have authority to propose trade setups
    - Strategies have authority to reject if setup doesn't fit their style
    - Strategies MUST NOT override agent's calculated values

    STATE PERSISTENCE (Issue #98):
    - Strategies can persist state via to_dict() and from_dict()
    - ExecutionEngine calls these during save_state/load_state
    - Default implementation returns empty dict / no-op
    """

    def evaluate_entry(
        self,
        signal: "TradingSignals",
        context: MarketContext,
        agent_recommendation: "TradingStrategy | None" = None,
    ) -> EntryDecision:
        """
        Evaluate whether to enter a new position.

        Args:
            signal: Technical analysis signals for the ticker
            context: Market and account context
            agent_recommendation: Optional AI agent recommendation

        Returns:
            EntryDecision with should_enter flag and order parameters
        """
        ...

    def evaluate_exit(
        self,
        position: "Position",
        signal: "TradingSignals",
        context: MarketContext,
    ) -> ExitDecision:
        """
        Evaluate whether to exit an existing position.

        IMPORTANT - Exit Mechanism Precedence (Issue #73):
        --------------------------------------------------
        This method is part of the SECONDARY exit mechanism (dynamic exits).
        It is only called when the position does NOT have an active bracket order.

        Primary Exit (Bracket Orders):
        - Stop loss and take profit are set at entry time
        - Managed automatically by Alpaca broker
        - Fastest and most reliable

        Secondary Exit (This Method):
        - Called each execution cycle by ExecutionEngine
        - Used for emergency conditions bracket orders can't detect
        - Examples: Momentum collapse, technical score degradation

        When to return should_exit=True:
        - Catastrophic momentum drop (e.g., -25%)
        - Technical score collapse below threshold
        - Strategy-specific emergency conditions

        When to return should_exit=False:
        - Normal market conditions (let bracket order handle it)
        - Minor fluctuations within acceptable range

        Args:
            position: Current position with P&L info
            signal: Technical analysis signals for the ticker
            context: Market and account context

        Returns:
            ExitDecision with should_exit flag and urgency level
        """
        ...

    def calculate_position_size(
        self,
        signal: "TradingSignals",
        context: MarketContext,
        max_amount: float,
    ) -> int:
        """
        Calculate the number of shares to trade using ATR/VIX-aware sizing.

        Position Sizing Logic (Issue #95 - Consolidated):
        1. If ATR available in signal: Calculate shares based on risk per share (2 * ATR)
        2. Apply VIX adjustment from context: Reduce risk in high volatility environments
        3. Cap at max_amount to respect allocation limits
        4. Fall back to simple sizing (max_amount / price) if ATR unavailable

        Args:
            signal: Technical analysis signals for the ticker (includes ATR)
            context: Market and account context (includes VIX, account_equity)
            max_amount: Maximum dollar amount to allocate

        Returns:
            Number of shares (rounded down to integer)
        """
        ...

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize strategy-specific state for persistence.

        Override in subclasses that maintain state (e.g., position data,
        false breakout counts, entry times).

        Returns:
            Dictionary containing strategy state, empty dict by default.
        """
        ...

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Restore strategy-specific state from persisted data.

        Override in subclasses that maintain state.

        Args:
            data: Dictionary containing strategy state from to_dict()
        """
        ...


class BaseStrategy(ABC):
    """
    Abstract base class providing common strategy functionality.

    Subclasses must implement evaluate_entry and evaluate_exit.
    This class provides:
    - Common validation logic (_check_basic_filters)
    - Default position sizing implementation
    - Shared utility methods
    """

    @abstractmethod
    def evaluate_entry(
        self,
        signal: "TradingSignals",
        context: MarketContext,
        agent_recommendation: "TradingStrategy | None" = None,
    ) -> EntryDecision:
        """
        Evaluate whether to enter a new position.

        Must be implemented by subclasses.
        """
        ...

    @abstractmethod
    def evaluate_exit(
        self,
        position: "Position",
        signal: "TradingSignals",
        context: MarketContext,
    ) -> ExitDecision:
        """
        Evaluate whether to exit an existing position.

        Must be implemented by subclasses.
        """
        ...

    def calculate_position_size(
        self,
        signal: "TradingSignals",
        context: MarketContext,
        max_amount: float,
    ) -> int:
        """
        Calculate position size based on ATR, VIX, and max allocation.

        Uses ATR-based risk calculation when available, with VIX adjustment
        for market volatility. Falls back to simple max_amount / price when
        ATR is unavailable.

        Position Sizing Logic (Issue #95 - Consolidated):
        1. If ATR available: Calculate shares based on risk per share (2 * ATR)
        2. Apply VIX adjustment: Reduce risk in high volatility environments
        3. Cap at max_amount to respect allocation limits
        4. Fall back to simple sizing if ATR unavailable

        Args:
            signal: Trading signals with current price and ATR
            context: Market context with VIX and account info
            max_amount: Maximum dollar amount to allocate

        Returns:
            Number of shares (rounded down to integer)
        """
        price = signal.get("price", 0.0)
        if price <= 0:
            return 0

        atr = signal.get("atr", 0.0)

        # If ATR unavailable, fall back to simple sizing
        if atr is None or atr <= 0:
            shares = int(max_amount / price)
            return max(0, shares)

        # ATR-based position sizing
        # Base risk: 2% of account equity (configurable via context)
        base_risk_pct = 0.02
        risk_amount = context.account_equity * base_risk_pct

        # VIX adjustment: reduce position size in high volatility
        # VIX=20 is baseline (no adjustment), VIX=40 reduces by 50%
        vix = context.vix
        if vix is not None and vix > 20:
            vix_factor = max(0, (vix - 20) / 20)
            risk_amount = risk_amount / (1 + vix_factor)

        # Calculate shares based on risk per share (2 * ATR as stop distance)
        risk_per_share = 2 * atr
        if risk_amount < risk_per_share:
            # Minimum 1 share if we can afford it
            shares = 1 if max_amount >= price else 0
        else:
            shares = int(risk_amount / risk_per_share)

        # Cap position value at max_amount
        position_value = shares * price
        if position_value > max_amount:
            shares = int(max_amount / price)

        return max(0, shares)

    def _check_basic_filters(
        self,
        signal: "TradingSignals",
        context: MarketContext,
    ) -> tuple[bool, str]:
        """
        Check common entry filters before strategy-specific logic.

        These filters apply to all strategies:
        - Market must be open
        - Ticker must not be in cooldown
        - Must not have existing position in same ticker

        Args:
            signal: Trading signals (must contain 'symbol' key)
            context: Market context with market status and positions

        Returns:
            Tuple of (passed, reason) where passed is True if filters pass
        """
        # Check if market is open
        if context.market_status.lower() != "open":
            return False, f"Market is {context.market_status}"

        # Check if ticker is in cooldown
        symbol = signal.get("symbol", "")
        if symbol in context.cooldown_tickers:
            return False, f"Ticker {symbol} is in cooldown"

        # Check if we already have a position
        if symbol in context.existing_positions:
            return False, f"Already have position in {symbol}"

        return True, "Basic filters passed"

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize strategy-specific state for persistence.

        Default implementation returns empty dict. Override in subclasses
        that maintain state (e.g., BreakoutStrategy, MeanReversionStrategy).

        Returns:
            Dictionary containing strategy state.
        """
        return {}

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Restore strategy-specific state from persisted data.

        Default implementation is a no-op. Override in subclasses
        that maintain state.

        Args:
            data: Dictionary containing strategy state from to_dict()
        """
        pass
