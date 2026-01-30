"""
Mean reversion trading strategy implementation.

Identifies overbought/oversold conditions and trades the expected
reversion to the mean using RSI, Bollinger Bands, and Z-score.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision, MarketContext
from alpacalyzer.strategies.config import StrategyConfig
from alpacalyzer.utils.logger import get_logger

if TYPE_CHECKING:
    from alpaca.trading.models import Position

    from alpacalyzer.data.models import TradingStrategy

logger = get_logger()


@dataclass
class MeanReversionConfig(StrategyConfig):
    """
    Configuration for mean reversion strategy.

    Attributes:
        rsi_period: RSI calculation period
        rsi_oversold: RSI threshold for oversold (long entry)
        rsi_overbought: RSI threshold for overbought (short entry)
        rsi_exit_threshold: RSI level to consider normalization
        bb_period: Bollinger Band period
        bb_std: Standard deviation multiplier for Bollinger Bands
        mean_period: Moving average period for mean calculation
        deviation_threshold: Standard deviations from mean to trigger entry
        risk_pct_per_trade: Risk percentage per trade
        max_hold_hours: Maximum hours to hold position
        stop_loss_std: Stop loss distance in standard deviations
        min_volume_ratio: Minimum volume ratio (current / average)
        trend_filter_period: Period for trend strength calculation
    """

    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    rsi_exit_threshold: float = 50.0
    bb_period: int = 20
    bb_std: float = 2.0
    mean_period: int = 20
    deviation_threshold: float = 2.0
    risk_pct_per_trade: float = 0.015
    max_hold_hours: int = 48
    stop_loss_std: float = 3.0
    min_volume_ratio: float = 1.2
    trend_filter_period: int = 50


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion trading strategy.

    Identifies extreme deviations from the mean and trades
    the expected reversion using RSI, Bollinger Bands, and Z-score.
    """

    def __init__(self, config: MeanReversionConfig | None = None):
        if config is None:
            config = self._default_config()
        self.config = config
        self._entry_times: dict[str, datetime] = {}

    @staticmethod
    def _default_config() -> MeanReversionConfig:
        """Default configuration for mean reversion strategy."""
        return MeanReversionConfig(
            name="mean_reversion",
            description="Mean reversion strategy with RSI and Bollinger Bands",
        )

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: "TradingStrategy | None" = None,
    ) -> EntryDecision:
        """
        Evaluate whether to enter a mean reversion position.

        NOTE: MeanReversionStrategy currently detects opportunities independently.
        If agent_recommendation is provided, strategy should validate conditions
        and use agent's entry/stop/target/quantity values.

        Decision Flow:
        - Strategy validates RSI oversold/overbought + Bollinger Band conditions
        - If agent_recommendation provided: validate mean reversion fit, use agent values
        - Reject if not in mean reversion range (RSI neutral, price within bands)

        Entry conditions (Long):
        - RSI below oversold threshold (< 30)
        - Price below lower Bollinger Band
        - Volume spike indicating capitulation
        - Not in strong downtrend

        Entry conditions (Short):
        - RSI above overbought threshold (> 70)
        - Price above upper Bollinger Band
        - Volume spike indicating exhaustion
        - Not in strong uptrend
        """
        from dataclasses import dataclass

        @dataclass
        class MeanReversionSignal:
            ticker: str
            side: str
            price: float
            stop_loss: float
            target: float
            confidence: float
            reason: str

        @dataclass
        class MeanReversionPosition:
            symbol: str
            side: str
            avg_entry_price: float
            current_price: float
            entry_time: datetime | None = None
            stop_loss: float = 0.0
            target: float = 0.0

        passed, reason = self._check_basic_filters(signal, context)
        if not passed:
            return EntryDecision(should_enter=False, reason=reason)

        df = signal["raw_data_daily"]
        required_periods = (
            max(
                self.config.rsi_period,
                self.config.bb_period,
                self.config.trend_filter_period,
            )
            + 10
        )

        if len(df) < required_periods:
            return EntryDecision(
                should_enter=False,
                reason=f"Insufficient data: need {required_periods} bars, have {len(df)}",
            )

        price = signal["price"]

        rsi = self._calculate_rsi(df)
        current_rsi = rsi.iloc[-1]

        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df)
        z_score = self._calculate_z_score(df)

        latest = df.iloc[-1]
        avg_volume = df["volume"].tail(50).mean()
        current_volume = latest["volume"]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

        if volume_ratio < self.config.min_volume_ratio:
            return EntryDecision(
                should_enter=False,
                reason=f"Insufficient volume: ratio={volume_ratio:.2f} < {self.config.min_volume_ratio}",
            )

        sma_long = df["close"].tail(self.config.trend_filter_period).mean()
        sma_short = df["close"].tail(20).mean()
        trend_strength = (sma_short - sma_long) / sma_long

        should_enter = False
        mr_signal = None

        if current_rsi < self.config.rsi_oversold and price < bb_lower.iloc[-1] and z_score < -self.config.deviation_threshold and trend_strength > -0.10:
            std = (bb_upper.iloc[-1] - bb_middle.iloc[-1]) / self.config.bb_std
            stop_loss = price - (std * self.config.stop_loss_std)
            target = bb_middle.iloc[-1]
            confidence = self._calculate_confidence(current_rsi, z_score, "oversold")

            should_enter = True
            mr_signal = MeanReversionSignal(
                ticker=signal["symbol"],
                side="long",
                price=price,
                stop_loss=stop_loss,
                target=target,
                confidence=confidence,
                reason=f"Oversold: RSI={current_rsi:.1f}, Z-score={z_score:.2f}, below BB",
            )

        elif current_rsi > self.config.rsi_overbought and price > bb_upper.iloc[-1] and z_score > self.config.deviation_threshold and trend_strength < 0.10:
            std = (bb_upper.iloc[-1] - bb_middle.iloc[-1]) / self.config.bb_std
            stop_loss = price + (std * self.config.stop_loss_std)
            target = bb_middle.iloc[-1]
            confidence = self._calculate_confidence(current_rsi, z_score, "overbought")

            should_enter = True
            mr_signal = MeanReversionSignal(
                ticker=signal["symbol"],
                side="short",
                price=price,
                stop_loss=stop_loss,
                target=target,
                confidence=confidence,
                reason=f"Overbought: RSI={current_rsi:.1f}, Z-score={z_score:.2f}, above BB",
            )

        if not should_enter:
            reasons = []
            if current_rsi >= self.config.rsi_oversold and current_rsi <= self.config.rsi_overbought:
                reasons.append(f"RSI neutral ({current_rsi:.1f})")
            if not (price < bb_lower.iloc[-1] or price > bb_upper.iloc[-1]):
                reasons.append("Price within Bollinger Bands")
            if not (z_score < -self.config.deviation_threshold or z_score > self.config.deviation_threshold):
                reasons.append(f"Z-score within threshold ({z_score:.2f})")
            if trend_strength <= -0.10:
                reasons.append(f"Strong downtrend ({trend_strength:.1%})")
            if trend_strength >= 0.10:
                reasons.append(f"Strong uptrend ({trend_strength:.1%})")
            return EntryDecision(should_enter=False, reason="; ".join(reasons))

        suggested_size = self.calculate_position_size(signal, context, context.buying_power * self.config.risk_pct_per_trade)

        assert mr_signal is not None, "mr_signal must be set when should_enter is True"

        return EntryDecision(
            should_enter=True,
            reason=mr_signal.reason,
            suggested_size=suggested_size,
            entry_price=mr_signal.price,
            stop_loss=mr_signal.stop_loss,
            target=mr_signal.target,
        )

    def evaluate_exit(
        self,
        position: "Position",
        signal: TradingSignals,
        context: MarketContext,
    ) -> ExitDecision:
        """
        Evaluate whether to exit a mean reversion position.

        Exit conditions:
        - Stop loss hit
        - Target reached (reversion to mean)
        - RSI normalized
        - Maximum hold time exceeded
        """
        df = signal["raw_data_daily"]
        price = signal["price"]

        position_side = getattr(position, "side", "long")
        avg_entry_price = float(getattr(position, "avg_entry_price", 0))

        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(df)
        rsi = self._calculate_rsi(df)
        current_rsi = rsi.iloc[-1]

        bb_std = (bb_upper.iloc[-1] - bb_middle.iloc[-1]) / self.config.bb_std

        stop_loss_long = avg_entry_price - (bb_std * self.config.stop_loss_std)
        stop_loss_short = avg_entry_price + (bb_std * self.config.stop_loss_std)

        if position_side == "long" and price <= stop_loss_long:
            return ExitDecision(
                should_exit=True,
                reason="stop_loss",
                urgency="immediate",
            )

        if position_side == "short" and price >= stop_loss_short:
            return ExitDecision(
                should_exit=True,
                reason="stop_loss",
                urgency="immediate",
            )

        target = bb_middle.iloc[-1]

        if position_side == "long" and price >= target:
            return ExitDecision(
                should_exit=True,
                reason="target_reached",
                urgency="normal",
            )

        if position_side == "short" and price <= target:
            return ExitDecision(
                should_exit=True,
                reason="target_reached",
                urgency="normal",
            )

        rsi_normalized = self.config.rsi_oversold < current_rsi < self.config.rsi_overbought
        crossed_middle = abs(current_rsi - self.config.rsi_exit_threshold) < 5

        if rsi_normalized and crossed_middle:
            return ExitDecision(
                should_exit=True,
                reason="rsi_normalized",
                urgency="normal",
            )

        return ExitDecision(should_exit=False, reason="Exit conditions not met")

    def _calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=self.config.rsi_period).mean()
        avg_loss = loss.rolling(window=self.config.rsi_period).mean()

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calculate_bollinger_bands(self, df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        middle = df["close"].rolling(window=self.config.bb_period).mean()
        std = df["close"].rolling(window=self.config.bb_period).std()

        upper = middle + (std * self.config.bb_std)
        lower = middle - (std * self.config.bb_std)

        return upper, middle, lower

    def _calculate_z_score(self, df: pd.DataFrame) -> float:
        """Calculate Z-score of current price from mean."""
        mean = df["close"].tail(self.config.mean_period).mean()
        std = df["close"].tail(self.config.mean_period).std()

        if std == 0:
            return 0.0

        return (df.iloc[-1]["close"] - mean) / std

    def _calculate_confidence(self, rsi: float, z_score: float, condition: str) -> float:
        """Calculate confidence score."""
        confidence = 50.0

        if condition == "oversold":
            if rsi < 20:
                confidence += 20
            elif rsi < 25:
                confidence += 15
            elif rsi < 30:
                confidence += 10

            if z_score < -3:
                confidence += 15
            elif z_score < -2.5:
                confidence += 10

        else:
            if rsi > 80:
                confidence += 20
            elif rsi > 75:
                confidence += 15
            elif rsi > 70:
                confidence += 10

            if z_score > 3:
                confidence += 15
            elif z_score > 2.5:
                confidence += 10

        return min(confidence, 95.0)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize strategy state for persistence.

        Persists:
        - _entry_times: Entry timestamps for max_hold_hours calculation

        Returns:
            Dictionary containing strategy state.
        """
        return {"entry_times": {ticker: dt.isoformat() for ticker, dt in self._entry_times.items()}}

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Restore strategy state from persisted data.

        Args:
            data: Dictionary containing strategy state from to_dict()
        """
        # Clear existing state
        self._entry_times = {}

        if not data:
            return

        # Restore entry times
        entry_times = data.get("entry_times", {})
        for ticker, iso_str in entry_times.items():
            self._entry_times[ticker] = datetime.fromisoformat(iso_str)
