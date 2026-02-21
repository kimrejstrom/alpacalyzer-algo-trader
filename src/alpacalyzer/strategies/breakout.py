"""
Breakout trading strategy implementation.

Identifies consolidation patterns and enters positions when price breaks
out with volume confirmation. Supports both long and short positions.
"""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision, MarketContext
from alpacalyzer.strategies.config import StrategyConfig
from alpacalyzer.utils.logger import get_logger

if TYPE_CHECKING:
    from alpaca.trading.models import Position

    from alpacalyzer.data.models import TradingStrategy

logger = get_logger(__name__)


@dataclass
class BreakoutConfig(StrategyConfig):
    """Configuration for breakout strategy."""

    name: str = "breakout"
    description: str = "Breakout trading strategy with consolidation detection"

    consolidation_periods: int = 20
    consolidation_range_pct: float = 0.05

    min_volume_ratio: float = 1.5
    breakout_buffer_pct: float = 0.002

    risk_pct_per_trade: float = 0.02
    target_multiple: float = 2.0

    min_atr: float = 0.5
    max_false_breakouts: int = 2

    def validate(self) -> list[str]:
        errors = super().validate()

        if self.consolidation_periods < 5:
            errors.append("consolidation_periods must be at least 5")

        if not 0.0 < self.consolidation_range_pct < 1.0:
            errors.append("consolidation_range_pct must be between 0 and 1")

        if self.min_volume_ratio < 1.0:
            errors.append("min_volume_ratio must be at least 1.0")

        if not 0.0 < self.breakout_buffer_pct < 1.0:
            errors.append("breakout_buffer_pct must be between 0 and 1")

        if self.target_multiple < 1.0:
            errors.append("target_multiple must be at least 1.0")

        if self.min_atr < 0.0:
            errors.append("min_atr must be non-negative")

        if self.max_false_breakouts < 0:
            errors.append("max_false_breakouts must be non-negative")

        return errors


@dataclass
class BreakoutPositionData:
    """Stored data for a breakout position."""

    entry_price: float
    stop_loss: float
    target: float
    side: str


class BreakoutStrategy(BaseStrategy):
    """
    Breakout trading strategy.

    Identifies consolidation patterns and enters when price breaks
    out with volume confirmation. Supports both long and short positions.

    Entry conditions:
    1. Price is in consolidation (tight range)
    2. Price breaks above resistance or below support
    3. Volume spike confirms breakout (> 1.5x average)
    4. ATR indicates sufficient volatility
    5. No recent false breakouts

    Exit conditions:
    1. Target reached (based on pattern height * target_multiple)
    2. Stop loss triggered
    3. Breakout fails (price returns to consolidation range)
    """

    def __init__(self, config: BreakoutConfig | None = None):
        if config is None:
            config = self._default_config()
        self.config = config
        self._false_breakout_count: dict[str, int] = {}
        self._position_data: dict[str, BreakoutPositionData] = {}

    @staticmethod
    def _default_config() -> BreakoutConfig:
        """Default configuration for breakout strategy."""
        return BreakoutConfig(
            name="breakout",
            description="Breakout trading strategy with consolidation detection",
            consolidation_periods=20,
            consolidation_range_pct=0.05,
            min_volume_ratio=1.5,
            breakout_buffer_pct=0.002,
            risk_pct_per_trade=0.02,
            target_multiple=2.0,
            min_atr=0.5,
            max_false_breakouts=2,
        )

    @property
    def name(self) -> str:
        return self.config.name

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: "TradingStrategy | None" = None,
    ) -> EntryDecision:
        """
        Evaluate entry conditions for breakout.

        Decision Flow (Issue #96 - Agent Integration):
        1. Check basic filters (market open, cooldown, existing position)
        2. Validate breakout conditions (consolidation pattern, volume spike)
        3. If agent_recommendation provided and conditions valid: use agent's values
        4. If agent_recommendation is None and conditions valid: calculate own values

        Agent vs Strategy Authority:
        - Agent proposes: entry_point, stop_loss, target_price, quantity
        - Strategy validates: consolidation pattern exists, volume confirms breakout
        - Strategy MUST NOT override agent's calculated values when provided

        Args:
            signal: TradingSignals with technical analysis data
            context: Market and account context
            agent_recommendation: Optional AI agent recommendation with trade setup

        Returns:
            EntryDecision with entry details or rejection reason
        """
        passed, reason = self._check_basic_filters(signal, context)
        if not passed:
            return EntryDecision(should_enter=False, reason=reason)

        symbol = signal["symbol"]
        price = signal["price"]

        if price <= 0:
            return EntryDecision(should_enter=False, reason="Invalid price")

        raw_data = signal["raw_data_daily"] if "raw_data_daily" in signal else signal.get("raw_data_intraday")
        if raw_data is None or not isinstance(raw_data, pd.DataFrame):
            return EntryDecision(should_enter=False, reason="No price data available")

        if len(raw_data) < self.config.consolidation_periods + 10:
            return EntryDecision(should_enter=False, reason="Insufficient data for analysis")

        # Exclude current bar from consolidation calculation to detect breakout
        recent = raw_data.iloc[-(self.config.consolidation_periods + 1) : -1]
        latest = raw_data.iloc[-1]

        resistance = recent["high"].max()
        support = recent["low"].min()
        range_pct = (resistance - support) / support if support > 0 else 1.0

        if range_pct > self.config.consolidation_range_pct:
            return EntryDecision(
                should_enter=False,
                reason=f"Price not in consolidation (range: {range_pct:.1%}, max: {self.config.consolidation_range_pct:.1%})",
            )

        avg_volume = raw_data["volume"].tail(50).mean()
        current_volume = latest.get("volume", 0)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0.0

        if volume_ratio < self.config.min_volume_ratio:
            return EntryDecision(
                should_enter=False,
                reason=f"Volume too low ({volume_ratio:.1f}x vs {self.config.min_volume_ratio:.1f}x required)",
            )

        atr = self._calculate_atr(raw_data)
        if atr < self.config.min_atr:
            return EntryDecision(
                should_enter=False,
                reason=f"ATR too low ({atr:.2f} vs {self.config.min_atr:.2f} minimum)",
            )

        if self._false_breakout_count.get(symbol, 0) >= self.config.max_false_breakouts:
            return EntryDecision(
                should_enter=False,
                reason=f"Too many recent false breakouts ({self._false_breakout_count[symbol]})",
            )

        buffer = price * self.config.breakout_buffer_pct
        current_high = latest.get("high", price)
        current_low = latest.get("low", price)

        # Check for bullish breakout
        if current_high > resistance + buffer:
            # Validate agent recommendation direction matches breakout
            if agent_recommendation is not None and agent_recommendation.trade_type != "long":
                return EntryDecision(
                    should_enter=False,
                    reason=f"Agent trade_type mismatch: agent proposed {agent_recommendation.trade_type} but breakout is bullish",
                )

            # Determine trade values based on agent recommendation
            if agent_recommendation is not None:
                # Use agent's values (agents propose, strategies validate)
                entry_price = agent_recommendation.entry_point
                stop_loss = agent_recommendation.stop_loss
                target = agent_recommendation.target_price
                size = agent_recommendation.quantity
                side = agent_recommendation.trade_type
            else:
                # Calculate own values (independent operation)
                entry_price = price
                stop_loss = support - atr
                pattern_height = price - support
                target = price + pattern_height * self.config.target_multiple
                size = self.calculate_position_size(signal, context, context.buying_power)
                side = "long"

            self._position_data[symbol] = BreakoutPositionData(
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                side=side,
            )

            return EntryDecision(
                should_enter=True,
                reason=f"Bullish breakout above {resistance:.2f} with {volume_ratio:.1f}x volume",
                suggested_size=size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
            )

        # Check for bearish breakout
        if current_low < support - buffer:
            # Validate agent recommendation direction matches breakout
            if agent_recommendation is not None and agent_recommendation.trade_type != "short":
                return EntryDecision(
                    should_enter=False,
                    reason=f"Agent trade_type mismatch: agent proposed {agent_recommendation.trade_type} but breakout is bearish",
                )

            # Determine trade values based on agent recommendation
            if agent_recommendation is not None:
                # Use agent's values (agents propose, strategies validate)
                entry_price = agent_recommendation.entry_point
                stop_loss = agent_recommendation.stop_loss
                target = agent_recommendation.target_price
                size = agent_recommendation.quantity
                side = agent_recommendation.trade_type
            else:
                # Calculate own values (independent operation)
                entry_price = price
                stop_loss = resistance + atr
                pattern_height = resistance - price
                target = price - pattern_height * self.config.target_multiple
                size = self.calculate_position_size(signal, context, context.buying_power)
                side = "short"

            self._position_data[symbol] = BreakoutPositionData(
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
                side=side,
            )

            return EntryDecision(
                should_enter=True,
                reason=f"Bearish breakout below {support:.2f} with {volume_ratio:.1f}x volume",
                suggested_size=size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target,
            )

        return EntryDecision(should_enter=False, reason="No breakout detected")

    def evaluate_exit(
        self,
        position: "Position",
        signal: TradingSignals,
        context: MarketContext,
    ) -> ExitDecision:
        """
        Evaluate exit conditions for breakout position.

        Args:
            position: Current position with entry price and P&L
            signal: TradingSignals with technical analysis data
            context: Market and account context

        Returns:
            ExitDecision with exit details or rejection reason
        """
        symbol = position.symbol
        current_price = signal.get("price", 0.0)

        if current_price <= 0:
            return ExitDecision(should_exit=False, reason="Invalid price")

        pos_data = self._position_data.get(symbol)
        if pos_data is None:
            return ExitDecision(should_exit=False, reason="No position data found")

        stop_loss = pos_data.stop_loss
        target = pos_data.target

        is_long = pos_data.side == "long"

        if is_long and current_price <= stop_loss and stop_loss > 0:
            self._record_false_breakout(symbol)
            del self._position_data[symbol]
            return ExitDecision(
                should_exit=True,
                reason="stop_loss",
                urgency="immediate",
            )

        if not is_long and current_price >= stop_loss and stop_loss > 0:
            self._record_false_breakout(symbol)
            del self._position_data[symbol]
            return ExitDecision(
                should_exit=True,
                reason="stop_loss",
                urgency="immediate",
            )

        if is_long and current_price >= target and target > 0:
            self._clear_false_breakouts(symbol)
            del self._position_data[symbol]
            return ExitDecision(
                should_exit=True,
                reason="target_reached",
                urgency="normal",
            )

        if not is_long and current_price <= target and target > 0:
            self._clear_false_breakouts(symbol)
            del self._position_data[symbol]
            return ExitDecision(
                should_exit=True,
                reason="target_reached",
                urgency="normal",
            )

        raw_data = signal.get("raw_data_daily")
        if raw_data is None or not isinstance(raw_data, pd.DataFrame):
            raw_data = signal.get("raw_data_intraday")
        if raw_data is not None and isinstance(raw_data, pd.DataFrame) and len(raw_data) >= self.config.consolidation_periods + 1:
            # Exclude current bar from consolidation calculation (same as entry logic)
            recent = raw_data.iloc[-(self.config.consolidation_periods + 1) : -1]
            resistance = recent["high"].max()
            support = recent["low"].min()

            if is_long and current_price < resistance:
                del self._position_data[symbol]
                return ExitDecision(
                    should_exit=True,
                    reason="breakout_failed",
                    urgency="urgent",
                )

            if not is_long and current_price > support:
                del self._position_data[symbol]
                return ExitDecision(
                    should_exit=True,
                    reason="breakout_failed",
                    urgency="urgent",
                )

        return ExitDecision(should_exit=False, reason="Exit conditions not met")

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(df) < period + 1:
            return 0.0

        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        tr = tr.dropna()
        return tr.tail(period).mean() if len(tr) >= period else tr.mean()

    def _calculate_confidence(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate confidence score for the breakout."""
        confidence = 50.0

        avg_volume = df["volume"].tail(50).mean()
        current_volume = df.iloc[-1]["volume"]
        if current_volume > avg_volume * 2:
            confidence += 15
        elif current_volume > avg_volume * 1.5:
            confidence += 10

        close = df["close"]
        sma_50 = close.tail(50).mean()
        sma_20 = close.tail(20).mean()
        price = df.iloc[-1]["close"]

        if direction == "bullish" and price > sma_20 > sma_50:
            confidence += 15
        elif direction == "bearish" and price < sma_20 < sma_50:
            confidence += 15

        recent = df.tail(self.config.consolidation_periods)
        range_pct = (recent["high"].max() - recent["low"].min()) / recent["low"].min()
        if range_pct < 0.03:
            confidence += 10

        return min(confidence, 95.0)

    def _record_false_breakout(self, ticker: str) -> None:
        """Record a false breakout for a ticker."""
        self._false_breakout_count[ticker] = self._false_breakout_count.get(ticker, 0) + 1

    def _clear_false_breakouts(self, ticker: str) -> None:
        """Clear false breakout count after successful trade."""
        self._false_breakout_count[ticker] = 0

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize strategy state for persistence.

        Persists:
        - _position_data: Entry price, stop loss, target for each position
        - _false_breakout_count: Failed breakout count per ticker

        Returns:
            Dictionary containing strategy state.
        """
        return {
            "position_data": {ticker: asdict(data) for ticker, data in self._position_data.items()},
            "false_breakout_count": dict(self._false_breakout_count),
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Restore strategy state from persisted data.

        Args:
            data: Dictionary containing strategy state from to_dict()
        """
        # Clear existing state
        self._position_data = {}
        self._false_breakout_count = {}

        if not data:
            return

        # Restore position data
        position_data = data.get("position_data", {})
        for ticker, pos_dict in position_data.items():
            self._position_data[ticker] = BreakoutPositionData(
                entry_price=pos_dict["entry_price"],
                stop_loss=pos_dict["stop_loss"],
                target=pos_dict["target"],
                side=pos_dict["side"],
            )

        # Restore false breakout counts
        self._false_breakout_count = dict(data.get("false_breakout_count", {}))
