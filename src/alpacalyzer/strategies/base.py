"""
Base strategy protocol and dataclasses.

This module defines Strategy protocol, BaseStrategy abstract class,
and supporting dataclasses for entry/exit decisions and market context.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from alpaca.trading.models import Position as AlpacaPosition

    from alpacalyzer.analysis.technical_analysis import TradingSignals
    from alpacalyzer.data.models import TradingStrategy

    # Type alias for Position - at runtime this is alpaca.trading.models.Position
    # but we use any type in protocol to allow flexibility
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
    """

    should_enter: bool
    reason: str
    suggested_size: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0


@dataclass
class ExitDecision:
    """
    Decision result from evaluate_exit method.

    Attributes:
        should_exit: Whether to exit the position
        reason: Human-readable explanation of decision
        urgency: Exit urgency level - affects execution priority
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
        Calculate the number of shares to trade.

        Args:
            signal: Technical analysis signals for the ticker
            context: Market and account context
            max_amount: Maximum dollar amount to allocate

        Returns:
            Number of shares (rounded down to integer)
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
        Calculate position size based on price and max allocation.

        Default implementation uses max_amount / signal["price"].

        Args:
            signal: Trading signals with current price
            context: Market context (unused in default implementation)
            max_amount: Maximum dollar amount to allocate

        Returns:
            Number of shares (rounded down to integer)
        """
        price = signal.get("price", 0.0)
        if price <= 0:
            return 0

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
