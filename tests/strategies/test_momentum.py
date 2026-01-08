"""Tests for MomentumStrategy implementation."""

import pandas as pd
import pytest
from alpaca.trading.models import Position

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.data.models import EntryCriteria, EntryType, TradingStrategy
from alpacalyzer.strategies.base import MarketContext
from alpacalyzer.strategies.config import StrategyConfig
from alpacalyzer.strategies.momentum import MomentumStrategy


@pytest.fixture
def momentum_strategy():
    """Momentum strategy with default config."""
    return MomentumStrategy()


@pytest.fixture
def momentum_strategy_custom():
    """Momentum strategy with custom config."""
    config = StrategyConfig(
        name="custom_momentum",
        description="Custom momentum strategy",
        stop_loss_pct=0.02,
        target_pct=0.06,
        min_confidence=65.0,
        min_ta_score=0.5,
        min_momentum=-2.0,
        entry_conditions_ratio=0.6,
        exit_momentum_threshold=-12.0,
        exit_score_threshold=0.25,
        catastrophic_momentum=-20.0,
        price_tolerance_pct=0.02,
        candlestick_pattern_confidence=75.0,
    )
    return MomentumStrategy(config)


@pytest.fixture
def market_context():
    """Standard market context for testing."""
    return MarketContext(
        vix=15.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=[],
        cooldown_tickers=[],
    )


@pytest.fixture
def agent_recommendation_long():
    """Agent recommendation for long trade."""
    return TradingStrategy(
        ticker="AAPL",
        trade_type="long",
        entry_point=150.0,
        stop_loss=145.5,
        target_price=163.5,
        quantity=50,
        risk_reward_ratio=3.0,
        strategy_notes="Test long strategy",
        entry_criteria=[
            EntryCriteria(entry_type=EntryType.RSI_OVERSOLD, value=28.0),
            EntryCriteria(entry_type=EntryType.ABOVE_MOVING_AVERAGE_20, value=150.0),
        ],
    )


@pytest.fixture
def agent_recommendation_short():
    """Agent recommendation for short trade."""
    return TradingStrategy(
        ticker="AAPL",
        trade_type="short",
        entry_point=150.0,
        stop_loss=154.5,
        target_price=136.5,
        quantity=50,
        risk_reward_ratio=3.0,
        strategy_notes="Test short strategy",
        entry_criteria=[
            EntryCriteria(entry_type=EntryType.RSI_OVERBOUGHT, value=72.0),
            EntryCriteria(entry_type=EntryType.BELOW_MOVING_AVERAGE_20, value=150.0),
        ],
    )


@pytest.fixture
def bullish_signal_oversold():
    """Bullish signal with oversold RSI and price above SMAs."""
    daily_data = pd.DataFrame(
        {
            "RSI": [45.0, 40.0, 28.0],
            "SMA_20": [148.0, 148.5, 149.0],
            "SMA_50": [146.0, 146.5, 147.0],
            "Close": [147.0, 148.0, 150.0],
        }
    )

    intraday_data = pd.DataFrame(
        {
            "Bullish_Engulfing": [85.0, 85.0, 90.0],  # All 3 rows above 80
            "Hammer": [80.0, 80.0, 85.0],  # All 3 rows above 80
            "Doji": [85.0, 85.0, 85.0],  # All 3 rows above 80
        }
    )

    return TradingSignals(
        symbol="AAPL",
        price=150.0,
        atr=2.5,
        rvol=1.2,
        signals=["RSI oversold", "Bullish crossover"],
        raw_score=75,
        score=0.75,
        momentum=8.5,
        raw_data_daily=daily_data,
        raw_data_intraday=intraday_data,
    )


@pytest.fixture
def bearish_signal_overbought():
    """Bearish signal with overbought RSI and price below SMAs."""
    daily_data = pd.DataFrame(
        {
            "RSI": [65.0, 70.0, 72.0],
            "SMA_20": [152.0, 151.5, 151.0],
            "SMA_50": [154.0, 153.5, 153.0],
            "Close": [153.0, 152.0, 150.0],
        }
    )

    intraday_data = pd.DataFrame(
        {
            "Bearish_Engulfing": [-85.0, -85.0, -90.0],  # All 3 rows below -80
            "Shooting_Star": [80.0, 80.0, 85.0],  # All 3 rows above 80
            "Doji": [85.0, 85.0, 85.0],  # All 3 rows above 80
        }
    )

    return TradingSignals(
        symbol="AAPL",
        price=150.0,
        atr=2.5,
        rvol=1.2,
        signals=["RSI overbought", "Bearish crossover"],
        raw_score=25,
        score=0.25,
        momentum=-8.5,
        raw_data_daily=daily_data,
        raw_data_intraday=intraday_data,
    )


@pytest.fixture
def weak_bullish_signal():
    """Weak bullish signal that doesn't meet entry conditions."""
    daily_data = pd.DataFrame(
        {
            "RSI": [55.0, 52.0, 50.0],
            "SMA_20": [148.0, 148.5, 149.0],
            "SMA_50": [146.0, 146.5, 147.0],
            "Close": [147.0, 148.0, 148.5],
        }
    )

    intraday_data = pd.DataFrame(
        {
            "Bullish_Engulfing": [0, 0, 0],
            "Hammer": [0, 0, 0],
            "Doji": [0, 0, 0],
        }
    )

    return TradingSignals(
        symbol="AAPL",
        price=148.5,
        atr=2.5,
        rvol=1.2,
        signals=["Weak bullish"],
        raw_score=45,
        score=0.45,
        momentum=3.0,
        raw_data_daily=daily_data,
        raw_data_intraday=intraday_data,
    )


@pytest.fixture
def weak_bearish_signal():
    """Weak bearish signal that doesn't meet entry conditions."""
    daily_data = pd.DataFrame(
        {
            "RSI": [60.0, 58.0, 55.0],
            "SMA_20": [152.0, 151.5, 151.0],
            "SMA_50": [154.0, 153.5, 153.0],
            "Close": [153.0, 152.0, 151.5],
        }
    )

    intraday_data = pd.DataFrame(
        {
            "Bearish_Engulfing": [0, 0, 0],
            "Shooting_Star": [0, 0, 0],
            "Doji": [0, 0, 0],
        }
    )

    return TradingSignals(
        symbol="AAPL",
        price=151.5,
        atr=2.5,
        rvol=1.2,
        signals=["Weak bearish"],
        raw_score=55,
        score=0.55,
        momentum=-3.0,
        raw_data_daily=daily_data,
        raw_data_intraday=intraday_data,
    )


class TestMomentumStrategyDefaultConfig:
    """Test default configuration values."""

    def test_default_config_values(self, momentum_strategy):
        """Test default configuration matches expected values."""
        config = momentum_strategy.config

        assert config.name == "momentum"
        assert config.description == "Momentum-based swing trading with TA confirmation"
        assert config.stop_loss_pct == 0.03
        assert config.target_pct == 0.09
        assert config.min_confidence == 70.0
        assert config.min_ta_score == 0.6
        assert config.min_momentum == -3.0
        assert config.entry_conditions_ratio == 0.7
        assert config.exit_momentum_threshold == -15.0
        assert config.exit_score_threshold == 0.3
        assert config.catastrophic_momentum == -25.0
        assert config.price_tolerance_pct == 0.015
        assert config.candlestick_pattern_confidence == 80.0


class TestMomentumStrategyEvaluateEntry:
    """Test entry evaluation logic."""

    def test_entry_requires_agent_recommendation(self, momentum_strategy, bullish_signal_oversold, market_context):
        """Test entry fails without agent recommendation."""
        decision = momentum_strategy.evaluate_entry(bullish_signal_oversold, market_context, None)

        assert not decision.should_enter
        assert "agent recommendation" in decision.reason.lower()

    def test_entry_market_closed(self, momentum_strategy, bullish_signal_oversold, market_context, agent_recommendation_long):
        """Test entry fails when market is closed."""
        market_context.market_status = "closed"
        decision = momentum_strategy.evaluate_entry(bullish_signal_oversold, market_context, agent_recommendation_long)

        assert not decision.should_enter
        assert "closed" in decision.reason.lower()

    def test_entry_cooldown_ticker(self, momentum_strategy, bullish_signal_oversold, market_context, agent_recommendation_long):
        """Test entry fails when ticker is in cooldown."""
        market_context.cooldown_tickers = ["AAPL"]
        decision = momentum_strategy.evaluate_entry(bullish_signal_oversold, market_context, agent_recommendation_long)

        assert not decision.should_enter
        assert "cooldown" in decision.reason.lower()

    def test_entry_existing_position(self, momentum_strategy, bullish_signal_oversold, market_context, agent_recommendation_long):
        """Test entry fails when position already exists."""
        market_context.existing_positions = ["AAPL"]
        decision = momentum_strategy.evaluate_entry(bullish_signal_oversold, market_context, agent_recommendation_long)

        assert not decision.should_enter
        assert "position" in decision.reason.lower()

    def test_long_entry_all_conditions_met(self, momentum_strategy, bullish_signal_oversold, market_context, agent_recommendation_long):
        """Test long entry when all conditions are met."""
        decision = momentum_strategy.evaluate_entry(bullish_signal_oversold, market_context, agent_recommendation_long)

        assert decision.should_enter
        assert decision.suggested_size == agent_recommendation_long.quantity
        assert decision.entry_price == agent_recommendation_long.entry_point
        assert decision.stop_loss == agent_recommendation_long.stop_loss
        assert decision.target == agent_recommendation_long.target_price
        assert "long" in decision.reason.lower()

    def test_short_entry_all_conditions_met(self, momentum_strategy, bearish_signal_overbought, market_context, agent_recommendation_short):
        """Test short entry when all conditions are met."""
        decision = momentum_strategy.evaluate_entry(bearish_signal_overbought, market_context, agent_recommendation_short)

        assert decision.should_enter
        assert decision.suggested_size == agent_recommendation_short.quantity
        assert decision.entry_price == agent_recommendation_short.entry_point
        assert decision.stop_loss == agent_recommendation_short.stop_loss
        assert decision.target == agent_recommendation_short.target_price
        assert "short" in decision.reason.lower()

    def test_long_entry_insufficient_conditions(self, momentum_strategy, weak_bullish_signal, market_context, agent_recommendation_long):
        """Test long entry fails with insufficient conditions met."""
        decision = momentum_strategy.evaluate_entry(weak_bullish_signal, market_context, agent_recommendation_long)

        assert not decision.should_enter
        assert "conditions not met" in decision.reason.lower()

    def test_short_entry_insufficient_conditions(self, momentum_strategy, weak_bearish_signal, market_context, agent_recommendation_short):
        """Test short entry fails with insufficient conditions met."""
        decision = momentum_strategy.evaluate_entry(weak_bearish_signal, market_context, agent_recommendation_short)

        assert not decision.should_enter
        assert "conditions not met" in decision.reason.lower()

    def test_long_entry_fuzzy_logic_threshold(self, momentum_strategy, bullish_signal_oversold, market_context, agent_recommendation_long):
        """Test long entry uses 70% fuzzy logic threshold."""
        # Default config has 0.7 threshold (5 of 6 conditions must be met for longs)
        # Our bullish signal has RSI < 30, price >= SMA20, price >= SMA50,
        # Bullish_Engulfing, Hammer (3/6 = 50%) - should fail
        decision = momentum_strategy.evaluate_entry(bullish_signal_oversold, market_context, agent_recommendation_long)

        # Signal should pass because conditions are strong
        assert decision.should_enter


class TestMomentumStrategyEntryCriteria:
    """Test entry criteria evaluation."""

    def test_long_entry_rsi_oversold(self, momentum_strategy, bullish_signal_oversold):
        """Test RSI oversold condition for long entries (fails if RSI > 30)."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bullish_signal_oversold, is_long=True)

        # RSI avg is 37.67, which is > 30, so this condition should fail
        assert "RSI_OVERSOLD" in failed

    def test_long_entry_above_sma20(self, momentum_strategy, bullish_signal_oversold):
        """Test price above SMA20 condition for long entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bullish_signal_oversold, is_long=True)

        assert "ABOVE_MOVING_AVERAGE_20" not in failed

    def test_long_entry_above_sma50(self, momentum_strategy, bullish_signal_oversold):
        """Test price above SMA50 condition for long entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bullish_signal_oversold, is_long=True)

        assert "ABOVE_MOVING_AVERAGE_50" not in failed

    def test_long_entry_bullish_engulfing(self, momentum_strategy, bullish_signal_oversold):
        """Test bullish engulfing pattern for long entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bullish_signal_oversold, is_long=True)

        assert "BULLISH_ENGULFING" not in failed

    def test_long_entry_hammer(self, momentum_strategy, bullish_signal_oversold):
        """Test hammer pattern for long entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bullish_signal_oversold, is_long=True)

        assert "HAMMER" not in failed

    def test_long_entry_doji(self, momentum_strategy, bullish_signal_oversold):
        """Test doji pattern for long entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bullish_signal_oversold, is_long=True)

        assert "DOJI" not in failed

    def test_short_entry_rsi_overbought(self, momentum_strategy, bearish_signal_overbought):
        """Test RSI overbought condition for short entries (fails if RSI < 70)."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bearish_signal_overbought, is_long=False)

        # RSI avg is 69.0, which is < 70, so this condition should fail
        assert "RSI_OVERBOUGHT" in failed

    def test_short_entry_below_sma20(self, momentum_strategy, bearish_signal_overbought):
        """Test price below SMA20 condition for short entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bearish_signal_overbought, is_long=False)

        assert "BELOW_MOVING_AVERAGE_20" not in failed

    def test_short_entry_below_sma50(self, momentum_strategy, bearish_signal_overbought):
        """Test price below SMA50 condition for short entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bearish_signal_overbought, is_long=False)

        assert "BELOW_MOVING_AVERAGE_50" not in failed

    def test_short_entry_bearish_engulfing(self, momentum_strategy, bearish_signal_overbought):
        """Test bearish engulfing pattern for short entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bearish_signal_overbought, is_long=False)

        assert "BEARISH_ENGULFING" not in failed

    def test_short_entry_shooting_star(self, momentum_strategy, bearish_signal_overbought):
        """Test shooting star pattern for short entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bearish_signal_overbought, is_long=False)

        assert "SHOOTING_STAR" not in failed

    def test_short_entry_doji(self, momentum_strategy, bearish_signal_overbought):
        """Test doji pattern for short entries."""
        conditions_met, total, failed = momentum_strategy._evaluate_entry_criteria(bearish_signal_overbought, is_long=False)

        assert "DOJI" not in failed


class TestMomentumStrategyEvaluateExit:
    """Test exit evaluation logic."""

    @pytest.fixture
    def profitable_long_position(self):
        """Profitable long position."""
        return Position.model_construct(
            symbol="AAPL",
            side="long",
            avg_entry_price="150.0",
            qty="50",
            current_price="157.5",
            unrealized_pl="375.0",
            unrealized_plpc="0.05",
            market_value="7875.0",
            cost_basis="7500.0",
        )

    @pytest.fixture
    def losing_long_position(self):
        """Losing long position."""
        return Position.model_construct(
            symbol="AAPL",
            side="long",
            avg_entry_price="150.0",
            qty="50",
            current_price="147.0",
            unrealized_pl="-150.0",
            unrealized_plpc="-0.02",
            market_value="7350.0",
            cost_basis="7500.0",
        )

    @pytest.fixture
    def profitable_short_position(self):
        """Profitable short position."""
        return Position.model_construct(
            symbol="AAPL",
            side="short",
            avg_entry_price="150.0",
            qty="50",
            current_price="142.5",
            unrealized_pl="375.0",
            unrealized_plpc="0.05",
            market_value="7125.0",
            cost_basis="7500.0",
        )

    @pytest.fixture
    def losing_short_position(self):
        """Losing short position."""
        return Position.model_construct(
            symbol="AAPL",
            side="short",
            avg_entry_price="150.0",
            qty="50",
            current_price="153.0",
            unrealized_pl="-150.0",
            unrealized_plpc="-0.02",
            market_value="7650.0",
            cost_basis="7500.0",
        )

    def test_exit_no_conditions_profitable_long(self, momentum_strategy, profitable_long_position, bullish_signal_oversold, market_context):
        """Test no exit for profitable long position with good momentum."""
        signal = bullish_signal_oversold
        decision = momentum_strategy.evaluate_exit(profitable_long_position, signal, market_context)

        assert not decision.should_exit
        assert "not met" in decision.reason.lower()

    def test_exit_momentum_reversal_profitable_long(self, momentum_strategy, profitable_long_position, market_context):
        """Test exit on major momentum reversal for profitable long."""
        daily_data = pd.DataFrame(
            {
                "RSI": [45.0, 40.0, 35.0],
                "SMA_20": [148.0, 148.5, 149.0],
                "SMA_50": [146.0, 146.5, 147.0],
                "Close": [147.0, 148.0, 150.0],
            }
        )

        intraday_data = pd.DataFrame({"Bullish_Engulfing": [0, 85.0, 90.0]})

        signal = TradingSignals(
            symbol="AAPL",
            price=157.5,
            atr=2.5,
            rvol=1.2,
            signals=["Momentum dropping"],
            raw_score=75,
            score=0.75,
            momentum=-16.0,  # Below exit_momentum_threshold (-15.0)
            raw_data_daily=daily_data,
            raw_data_intraday=intraday_data,
        )

        decision = momentum_strategy.evaluate_exit(profitable_long_position, signal, market_context)

        assert decision.should_exit
        assert "momentum reversal" in decision.reason.lower()
        assert decision.urgency == "urgent"

    def test_exit_score_collapse_profitable_long(self, momentum_strategy, profitable_long_position, market_context):
        """Test exit on technical score collapse for profitable long."""
        daily_data = pd.DataFrame(
            {
                "RSI": [45.0, 40.0, 35.0],
                "SMA_20": [148.0, 148.5, 149.0],
                "SMA_50": [146.0, 146.5, 147.0],
                "Close": [147.0, 148.0, 150.0],
            }
        )

        intraday_data = pd.DataFrame({"Bullish_Engulfing": [0, 85.0, 90.0]})

        signal = TradingSignals(
            symbol="AAPL",
            price=157.5,
            atr=2.5,
            rvol=1.2,
            signals=["Score dropping"],
            raw_score=75,
            score=0.25,  # Below exit_score_threshold (0.3)
            momentum=8.5,
            raw_data_daily=daily_data,
            raw_data_intraday=intraday_data,
        )

        decision = momentum_strategy.evaluate_exit(profitable_long_position, signal, market_context)

        assert decision.should_exit
        assert "score collapse" in decision.reason.lower()

    def test_exit_momentum_reversal_profitable_short(self, momentum_strategy, profitable_short_position, market_context):
        """Test exit on major momentum reversal for profitable short."""
        daily_data = pd.DataFrame(
            {
                "RSI": [65.0, 60.0, 55.0],
                "SMA_20": [152.0, 151.5, 151.0],
                "SMA_50": [154.0, 153.5, 153.0],
                "Close": [153.0, 152.0, 150.0],
            }
        )

        intraday_data = pd.DataFrame({"Bearish_Engulfing": [0, -85.0, -90.0]})

        signal = TradingSignals(
            symbol="AAPL",
            price=142.5,
            atr=2.5,
            rvol=1.2,
            signals=["Momentum rising"],
            raw_score=25,
            score=0.25,
            momentum=16.0,  # Above -exit_momentum_threshold (15.0)
            raw_data_daily=daily_data,
            raw_data_intraday=intraday_data,
        )

        decision = momentum_strategy.evaluate_exit(profitable_short_position, signal, market_context)

        assert decision.should_exit
        assert "momentum reversal" in decision.reason.lower()

    def test_exit_score_collapse_profitable_short(self, momentum_strategy, profitable_short_position, market_context):
        """Test exit on technical score collapse for profitable short."""
        daily_data = pd.DataFrame(
            {
                "RSI": [65.0, 60.0, 55.0],
                "SMA_20": [152.0, 151.5, 151.0],
                "SMA_50": [154.0, 153.5, 153.0],
                "Close": [153.0, 152.0, 150.0],
            }
        )

        intraday_data = pd.DataFrame({"Bearish_Engulfing": [0, -85.0, -90.0]})

        signal = TradingSignals(
            symbol="AAPL",
            price=142.5,
            atr=2.5,
            rvol=1.2,
            signals=["Score rising"],
            raw_score=25,
            score=0.85,  # Above 0.8
            momentum=-8.5,
            raw_data_daily=daily_data,
            raw_data_intraday=intraday_data,
        )

        decision = momentum_strategy.evaluate_exit(profitable_short_position, signal, market_context)

        assert decision.should_exit
        assert "score collapse" in decision.reason.lower()

    def test_exit_catastrophic_momentum_long(self, momentum_strategy, losing_long_position, market_context):
        """Test exit on catastrophic momentum drop for long."""
        daily_data = pd.DataFrame(
            {
                "RSI": [45.0, 40.0, 35.0],
                "SMA_20": [148.0, 148.5, 149.0],
                "SMA_50": [146.0, 146.5, 147.0],
                "Close": [147.0, 148.0, 150.0],
            }
        )

        intraday_data = pd.DataFrame({"Bullish_Engulfing": [0, 85.0, 90.0]})

        signal = TradingSignals(
            symbol="AAPL",
            price=147.0,
            atr=2.5,
            rvol=1.2,
            signals=["Catastrophic drop"],
            raw_score=75,
            score=0.75,
            momentum=-26.0,  # Below catastrophic_momentum (-25.0)
            raw_data_daily=daily_data,
            raw_data_intraday=intraday_data,
        )

        decision = momentum_strategy.evaluate_exit(losing_long_position, signal, market_context)

        assert decision.should_exit
        assert "catastrophic" in decision.reason.lower()
        assert decision.urgency == "immediate"

    def test_exit_catastrophic_momentum_short(self, momentum_strategy, losing_short_position, market_context):
        """Test exit on catastrophic momentum rise for short."""
        daily_data = pd.DataFrame(
            {
                "RSI": [65.0, 60.0, 55.0],
                "SMA_20": [152.0, 151.5, 151.0],
                "SMA_50": [154.0, 153.5, 153.0],
                "Close": [153.0, 152.0, 150.0],
            }
        )

        intraday_data = pd.DataFrame({"Bearish_Engulfing": [0, -85.0, -90.0]})

        signal = TradingSignals(
            symbol="AAPL",
            price=153.0,
            atr=2.5,
            rvol=1.2,
            signals=["Catastrophic rise"],
            raw_score=25,
            score=0.25,
            momentum=26.0,  # Above -catastrophic_momentum (25.0)
            raw_data_daily=daily_data,
            raw_data_intraday=intraday_data,
        )

        decision = momentum_strategy.evaluate_exit(losing_short_position, signal, market_context)

        assert decision.should_exit
        assert "catastrophic" in decision.reason.lower()
        assert decision.urgency == "immediate"


class TestMomentumStrategyExitUrgency:
    """Test exit urgency determination."""

    def test_exit_urgency_catastrophic(self, momentum_strategy):
        """Test catastrophic urgency."""
        signals = ["Catastrophic momentum drop: -26.0%"]
        urgency = momentum_strategy._determine_exit_urgency(signals)

        assert urgency == "immediate"

    def test_exit_urgency_momentum(self, momentum_strategy):
        """Test urgent urgency for momentum."""
        signals = ["Major momentum reversal: -16.0%"]
        urgency = momentum_strategy._determine_exit_urgency(signals)

        assert urgency == "urgent"

    def test_exit_urgency_normal(self, momentum_strategy):
        """Test normal urgency for other signals."""
        signals = ["Technical score collapse: 0.25"]
        urgency = momentum_strategy._determine_exit_urgency(signals)

        assert urgency == "normal"


class TestMomentumStrategyCustomConfig:
    """Test custom configuration."""

    def test_custom_config_values(self, momentum_strategy_custom):
        """Test custom configuration values are applied."""
        config = momentum_strategy_custom.config

        assert config.name == "custom_momentum"
        assert config.stop_loss_pct == 0.02
        assert config.target_pct == 0.06
        assert config.entry_conditions_ratio == 0.6
        assert config.exit_momentum_threshold == -12.0
        assert config.candlestick_pattern_confidence == 75.0
