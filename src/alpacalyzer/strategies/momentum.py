"""
Momentum trading strategy implementation.

Extracted from check_entry_conditions() and check_exit_conditions()
in trader.py, implements fuzzy logic entry evaluation with
technical confirmation.
"""

from typing import TYPE_CHECKING, cast

import pandas as pd
from alpaca.trading.enums import OrderSide

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.data.models import TradingStrategy
from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision, MarketContext
from alpacalyzer.strategies.config import StrategyConfig
from alpacalyzer.utils.logger import get_logger

if TYPE_CHECKING:
    from alpaca.trading.models import Position

logger = get_logger()


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based swing trading strategy.

    Uses fuzzy logic (70% threshold) to evaluate entry conditions
    from technical signals. Agent recommendations control trade setup
    (entry, stop loss, target, quantity), while this strategy
    evaluates technical suitability.
    """

    def __init__(self, config: StrategyConfig | None = None):
        if config is None:
            config = self._default_config()
        self.config = config
        self.ta = TechnicalAnalyzer()

    @staticmethod
    def _default_config() -> StrategyConfig:
        """Default configuration matching current trader.py behavior."""
        return StrategyConfig(
            name="momentum",
            description="Momentum-based swing trading with TA confirmation",
            stop_loss_pct=0.03,
            target_pct=0.09,
            min_confidence=70.0,
            min_ta_score=0.6,
            min_momentum=-3.0,
            entry_conditions_ratio=0.7,
            exit_momentum_threshold=-15.0,
            exit_score_threshold=0.3,
            catastrophic_momentum=-25.0,
            price_tolerance_pct=0.015,
            candlestick_pattern_confidence=80.0,
        )

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: TradingStrategy | None = None,
    ) -> EntryDecision:
        """
        Evaluate entry using fuzzy logic on technical conditions.

        Entry criteria are generated dynamically from TradingSignals
        based on trade_type (long/short). Agent recommendation
        provides trade setup (entry, stop loss, target, quantity).
        """
        # Check basic filters (market open, cooldown, existing position)
        passed, reason = self._check_basic_filters(signal, context)
        if not passed:
            return EntryDecision(should_enter=False, reason=reason)

        # Require agent recommendation for trade setup
        if agent_recommendation is None:
            return EntryDecision(
                should_enter=False,
                reason="No agent recommendation provided for trade setup",
            )

        trade_type = agent_recommendation.trade_type
        is_long = trade_type == "long"

        # Generate and evaluate entry criteria based on trade_type
        conditions_met_count, total_conditions, failed_conditions = self._evaluate_entry_criteria(signal, is_long)

        # Apply fuzzy logic threshold
        conditions_ratio = conditions_met_count / total_conditions if total_conditions > 0 else 0
        conditions_met = conditions_ratio >= self.config.entry_conditions_ratio

        logger.info(f"Entry conditions for {signal['symbol']}: {conditions_met_count}/{total_conditions} met ({conditions_ratio:.1%})")
        if failed_conditions:
            logger.debug(f"Failed conditions: {', '.join(failed_conditions)}")
        logger.info(f"Entry conditions met for {signal['symbol']}: {conditions_met}")

        if not conditions_met:
            return EntryDecision(
                should_enter=False,
                reason=f"Entry conditions not met ({conditions_met_count}/{total_conditions} conditions satisfied)",
            )

        # Use agent recommendation values directly for trade setup
        # Strategy's role: Validate technical conditions, not recalculate prices
        # Agent provides: entry_point, stop_loss, target_price, quantity
        # Strategy validates: Momentum trend, technical signals
        return EntryDecision(
            should_enter=True,
            reason=f"Entry conditions met ({conditions_met_count}/{total_conditions}), trade_type={trade_type}",
            suggested_size=agent_recommendation.quantity,
            entry_price=agent_recommendation.entry_point,
            stop_loss=agent_recommendation.stop_loss,
            target=agent_recommendation.target_price,
        )

    def _evaluate_entry_criteria(self, signal: TradingSignals, is_long: bool) -> tuple[int, int, list[str]]:
        """
        Generate and evaluate entry criteria based on trade type.

        Returns:
            Tuple of (conditions_met_count, total_conditions, failed_conditions_list)
        """
        # Get 3-candle averages for consistency
        daily_data = signal["raw_data_daily"]
        intraday_data = signal["raw_data_intraday"]

        daily_3candle = cast(pd.Series, daily_data.iloc[-3:].mean())
        intraday_3candle = cast(pd.Series, intraday_data.iloc[-3:].mean())

        price = signal["price"]
        rsi = daily_3candle["RSI"]
        sma20 = daily_3candle["SMA_20"]
        sma50 = daily_3candle["SMA_50"]

        # Generate applicable conditions based on trade type
        conditions_met_count = 0
        failed_conditions = []

        # Define which conditions to check based on trade type
        if is_long:
            # Long entry conditions
            conditions_to_check = self._get_long_entry_conditions(price, rsi, sma20, sma50, intraday_3candle)
        else:
            # Short entry conditions
            conditions_to_check = self._get_short_entry_conditions(price, rsi, sma20, sma50, intraday_3candle)

        # Evaluate each condition
        for condition_name, condition_met in conditions_to_check.items():
            if condition_met:
                conditions_met_count += 1
            else:
                failed_conditions.append(condition_name)

        return conditions_met_count, len(conditions_to_check), failed_conditions

    def _get_long_entry_conditions(self, price: float, rsi: float, sma20: float, sma50: float, intraday_3candle: pd.Series) -> dict[str, bool]:
        """Get and evaluate long entry conditions."""
        conditions = {}

        # RSI oversold check (RSI < 30)
        conditions["RSI_OVERSOLD"] = rsi < 30
        if not conditions["RSI_OVERSOLD"]:
            logger.debug(f"RSI oversold: {rsi} > 30")

        # Price above SMA20
        conditions["ABOVE_MOVING_AVERAGE_20"] = price >= sma20
        if not conditions["ABOVE_MOVING_AVERAGE_20"]:
            logger.debug(f"Price above SMA20: {price} < {sma20}")

        # Price above SMA50
        conditions["ABOVE_MOVING_AVERAGE_50"] = price >= sma50
        if not conditions["ABOVE_MOVING_AVERAGE_50"]:
            logger.debug(f"Price above SMA50: {price} < {sma50}")

        # Bullish Engulfing pattern
        bullish_engulfing_conf = intraday_3candle["Bullish_Engulfing"]
        conditions["BULLISH_ENGULFING"] = bullish_engulfing_conf >= self.config.candlestick_pattern_confidence
        if not conditions["BULLISH_ENGULFING"]:
            logger.debug(f"Bullish Engulfing not detected (confidence: {bullish_engulfing_conf:.1f})")

        # Hammer pattern
        hammer_conf = intraday_3candle["Hammer"]
        conditions["HAMMER"] = hammer_conf >= self.config.candlestick_pattern_confidence
        if not conditions["HAMMER"]:
            logger.debug(f"Hammer not detected (confidence: {hammer_conf:.1f})")

        # Doji pattern
        doji_conf = intraday_3candle["Doji"]
        conditions["DOJI"] = doji_conf >= self.config.candlestick_pattern_confidence
        if not conditions["DOJI"]:
            logger.debug(f"Doji not detected (confidence: {doji_conf:.1f})")

        return conditions

    def _get_short_entry_conditions(self, price: float, rsi: float, sma20: float, sma50: float, intraday_3candle: pd.Series) -> dict[str, bool]:
        """Get and evaluate short entry conditions."""
        conditions = {}

        # RSI overbought check (RSI > 70)
        conditions["RSI_OVERBOUGHT"] = rsi > 70
        if not conditions["RSI_OVERBOUGHT"]:
            logger.debug(f"RSI overbought: {rsi} < 70")

        # Price below SMA20
        conditions["BELOW_MOVING_AVERAGE_20"] = price <= sma20
        if not conditions["BELOW_MOVING_AVERAGE_20"]:
            logger.debug(f"Price below SMA20: {price} > {sma20}")

        # Price below SMA50
        conditions["BELOW_MOVING_AVERAGE_50"] = price <= sma50
        if not conditions["BELOW_MOVING_AVERAGE_50"]:
            logger.debug(f"Price below SMA50: {price} > {sma50}")

        # Bearish Engulfing pattern
        bearish_engulfing_conf = intraday_3candle["Bearish_Engulfing"]
        conditions["BEARISH_ENGULFING"] = bearish_engulfing_conf <= -self.config.candlestick_pattern_confidence
        if not conditions["BEARISH_ENGULFING"]:
            logger.debug(f"Bearish Engulfing not detected (confidence: {bearish_engulfing_conf:.1f})")

        # Shooting Star pattern
        shooting_star_conf = intraday_3candle["Shooting_Star"]
        conditions["SHOOTING_STAR"] = shooting_star_conf >= self.config.candlestick_pattern_confidence
        if not conditions["SHOOTING_STAR"]:
            logger.debug(f"Shooting Star not detected (confidence: {shooting_star_conf:.1f})")

        # Doji pattern (also works for shorts)
        doji_conf = intraday_3candle["Doji"]
        conditions["DOJI"] = doji_conf >= self.config.candlestick_pattern_confidence
        if not conditions["DOJI"]:
            logger.debug(f"Doji not detected (confidence: {doji_conf:.1f})")

        return conditions

    def evaluate_exit(
        self,
        position: "Position",
        signal: TradingSignals,
        context: MarketContext,
    ) -> ExitDecision:
        """
        Evaluate exit conditions using logic from trader.py check_exit_conditions().

        Serves as safeguard against extreme conditions. Primary exit is handled
        by bracket order's take_profit and stop_loss.
        """
        momentum = signal["momentum"]
        score = signal["score"]
        is_long = position.side == "long"
        unrealized_plpc = float(position.unrealized_plpc or 0.0)
        is_profitable = unrealized_plpc > 0

        exit_signals = []

        if is_profitable:
            # Let Winners Run - only exit on major reversal
            if is_long:
                if momentum < self.config.exit_momentum_threshold:
                    exit_signals.append(f"Major momentum reversal: {momentum:.1f}% drop")
                if score < self.config.exit_score_threshold:
                    exit_signals.append(f"Technical score collapse: {score:.2f}")
            else:  # is_short
                if momentum > -self.config.exit_momentum_threshold:
                    exit_signals.append(f"Major momentum reversal: {momentum:.1f}% rise")
                if score > 0.8:
                    exit_signals.append(f"Technical score collapse for short: {score:.2f}")

        else:
            # Cut Losses on Clear Signals
            if is_long:
                weak_tech_signals = self.ta.weak_technicals(signal["signals"], OrderSide.BUY)

                # Require BOTH momentum degradation AND technical weakness
                if momentum < self.config.exit_momentum_threshold and weak_tech_signals:
                    exit_signals.append(f"Strong momentum drop: {momentum:.1f}% with weak technicals")
                # OR severe technical collapse alone
                elif score < self.config.exit_score_threshold and weak_tech_signals:
                    exit_signals.append(f"Technical score collapse: {score:.2f} with weak technicals")
                # OR catastrophic momentum without needing technical confirmation
                elif momentum < self.config.catastrophic_momentum:
                    exit_signals.append(f"Catastrophic momentum drop: {momentum:.1f}%")

            else:  # is_short
                weak_tech_signals = self.ta.weak_technicals(signal["signals"], OrderSide.SELL)

                if momentum > -self.config.exit_momentum_threshold and weak_tech_signals:
                    exit_signals.append(f"Strong momentum rise: {momentum:.1f}% with weak technicals")
                elif score > 0.7 and weak_tech_signals:
                    exit_signals.append(f"Technical score strength: {score:.2f} with weak technicals")
                elif momentum > -self.config.catastrophic_momentum:
                    exit_signals.append(f"Catastrophic momentum rise: {momentum:.1f}%")

        if exit_signals:
            reason_str = ", ".join(exit_signals)
            urgency = self._determine_exit_urgency(exit_signals)
            logger.info(f"\nDYNAMIC EXIT FOR {position.symbol} due to: {reason_str}")
            logger.debug(f"Position details: {position}")
            if unrealized_plpc < 0:
                logger.info(f"LOSS: {unrealized_plpc:.2%} P&L on trade")
            else:
                logger.info(f"WIN: {unrealized_plpc:.2%} P&L on trade")
            return ExitDecision(should_exit=True, reason=reason_str, urgency=urgency)

        return ExitDecision(should_exit=False, reason="Exit conditions not met")

    def _determine_exit_urgency(self, exit_signals: list[str]) -> str:
        """Determine exit urgency based on exit reasons."""
        for signal in exit_signals:
            if "Catastrophic" in signal:
                return "immediate"
            if "momentum" in signal.lower():
                return "urgent"
        return "normal"
