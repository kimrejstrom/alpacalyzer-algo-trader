"""Tests for MeanReversionStrategy implementation."""

from unittest.mock import MagicMock

import pandas as pd
import pytest
from alpaca.trading.models import Position

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.strategies.base import MarketContext
from alpacalyzer.strategies.mean_reversion import MeanReversionConfig, MeanReversionStrategy


@pytest.fixture
def mean_reversion_strategy():
    """Mean reversion strategy with default config."""
    return MeanReversionStrategy()


@pytest.fixture
def mean_reversion_strategy_custom():
    """Mean reversion strategy with custom config."""
    config = MeanReversionConfig(
        name="custom_mean_reversion",
        description="Custom mean reversion strategy",
        rsi_period=12,
        rsi_oversold=25.0,
        rsi_overbought=75.0,
        bb_period=18,
        bb_std=1.8,
        deviation_threshold=1.8,
        risk_pct_per_trade=0.02,
        max_hold_hours=36,
        stop_loss_std=2.8,
        min_volume_ratio=1.3,
        trend_filter_period=40,
    )
    return MeanReversionStrategy(config)


@pytest.fixture
def market_context():
    """Standard market context for testing."""
    return MarketContext(
        vix=20.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=[],
        cooldown_tickers=[],
    )


@pytest.fixture
def long_position():
    """Sample long position."""
    mock_pos = MagicMock(spec=Position)
    mock_pos.symbol = "AAPL"
    mock_pos.qty = 10
    mock_pos.side = "long"
    mock_pos.avg_entry_price = 140.0
    mock_pos.current_price = 140.0
    mock_pos.unrealized_pl = 0.0
    return mock_pos


@pytest.fixture
def short_position():
    """Sample short position."""
    mock_pos = MagicMock(spec=Position)
    mock_pos.symbol = "AAPL"
    mock_pos.qty = -10
    mock_pos.side = "short"
    mock_pos.avg_entry_price = 148.0
    mock_pos.current_price = 148.0
    mock_pos.unrealized_pl = 0.0
    return mock_pos


@pytest.fixture
def oversold_signal():
    """Oversold signal with RSI < 30, price below BB_lower."""
    daily_data = pd.DataFrame(
        {
            "close": [152.0 - i * 0.5 for i in range(60)],
            "volume": [1000000] * 60,
        }
    )
    daily_data["RSI"] = 28.0
    return TradingSignals(
        symbol="AAPL",
        price=140.0,
        atr=2.0,
        rvol=1.2,
        signals=["RSI oversold", "Price below BB"],
        raw_score=30,
        score=0.30,
        momentum=-12.0,
        raw_data_daily=daily_data,
        raw_data_intraday=pd.DataFrame({"Bullish_Engulfing": [0, 0, 0]}),
    )


@pytest.fixture
def overbought_signal():
    """Overbought signal with RSI > 70, price above BB_upper."""
    daily_data = pd.DataFrame(
        {
            "close": [120.0 + i * 0.5 for i in range(60)],
            "volume": [1000000] * 60,
        }
    )
    daily_data["RSI"] = 72.0
    return TradingSignals(
        symbol="AAPL",
        price=148.0,
        atr=2.0,
        rvol=1.2,
        signals=["RSI overbought", "Price above BB"],
        raw_score=25,
        score=0.25,
        momentum=12.0,
        raw_data_daily=daily_data,
        raw_data_intraday=pd.DataFrame({"Bearish_Engulfing": [0, 0, 0]}),
    )


@pytest.fixture
def neutral_signal():
    """Neutral signal with RSI in normal range."""
    daily_data = pd.DataFrame(
        {
            "close": [145.0 + (i % 10 - 5) * 0.5 for i in range(60)],
            "volume": [int(1500000 + 100000 * i) for i in range(60)],
        }
    )
    daily_data["RSI"] = 50.0
    return TradingSignals(
        symbol="AAPL",
        price=146.0,
        atr=2.0,
        rvol=1.2,
        signals=["Neutral"],
        raw_score=50,
        score=0.50,
        momentum=2.0,
        raw_data_daily=daily_data,
        raw_data_intraday=pd.DataFrame({"Doji": [0, 0, 0]}),
    )


class TestMeanReversionConfigDefault:
    """Test default configuration values."""

    def test_default_config_values(self, mean_reversion_strategy):
        """Test default configuration matches expected values."""
        config = mean_reversion_strategy.config

        assert config.name == "mean_reversion"
        assert config.rsi_period == 14
        assert config.rsi_oversold == 30.0
        assert config.rsi_overbought == 70.0
        assert config.rsi_exit_threshold == 50.0
        assert config.bb_period == 20
        assert config.bb_std == 2.0
        assert config.mean_period == 20
        assert config.deviation_threshold == 2.0
        assert config.risk_pct_per_trade == 0.015
        assert config.max_hold_hours == 48
        assert config.stop_loss_std == 3.0
        assert config.min_volume_ratio == 1.2
        assert config.trend_filter_period == 50


class TestMeanReversionConfigCustom:
    """Test custom configuration."""

    def test_custom_config_values(self, mean_reversion_strategy_custom):
        """Test custom configuration values are applied."""
        config = mean_reversion_strategy_custom.config

        assert config.name == "custom_mean_reversion"
        assert config.rsi_period == 12
        assert config.rsi_oversold == 25.0
        assert config.rsi_overbought == 75.0
        assert config.bb_period == 18
        assert config.bb_std == 1.8
        assert config.deviation_threshold == 1.8
        assert config.risk_pct_per_trade == 0.02
        assert config.max_hold_hours == 36
        assert config.stop_loss_std == 2.8
        assert config.min_volume_ratio == 1.3
        assert config.trend_filter_period == 40


class TestMeanReversionStrategyEvaluateEntry:
    """Test entry evaluation logic."""

    def test_entry_market_closed(self, mean_reversion_strategy, oversold_signal, market_context):
        """Test entry fails when market is closed."""
        market_context.market_status = "closed"
        decision = mean_reversion_strategy.evaluate_entry(oversold_signal, market_context)

        assert not decision.should_enter
        assert "closed" in decision.reason.lower()

    def test_entry_cooldown_ticker(self, mean_reversion_strategy, oversold_signal, market_context):
        """Test entry fails when ticker is in cooldown."""
        market_context.cooldown_tickers = ["AAPL"]
        decision = mean_reversion_strategy.evaluate_entry(oversold_signal, market_context)

        assert not decision.should_enter
        assert "cooldown" in decision.reason.lower()

    def test_entry_existing_position(self, mean_reversion_strategy, oversold_signal, market_context):
        """Test entry fails when position already exists."""
        market_context.existing_positions = ["AAPL"]
        decision = mean_reversion_strategy.evaluate_entry(oversold_signal, market_context)

        assert not decision.should_enter
        assert "position" in decision.reason.lower()

    def test_long_entry_insufficient_volume(self, mean_reversion_strategy, oversold_signal, market_context):
        """Test entry fails with insufficient volume."""
        oversold_signal["raw_data_daily"]["volume"] = [500000] * 60
        decision = mean_reversion_strategy.evaluate_entry(oversold_signal, market_context)

        assert not decision.should_enter
        assert "volume" in decision.reason.lower()

    def test_long_entry_strong_downtrend(self, mean_reversion_strategy, oversold_signal, market_context):
        """Test entry fails when in strong downtrend."""
        oversold_signal["raw_data_daily"]["close"] = [160.0 - i * 1.5 for i in range(60)]
        oversold_signal["raw_data_daily"]["volume"] = [1000000 + 500000 * i for i in range(60)]
        decision = mean_reversion_strategy.evaluate_entry(oversold_signal, market_context)

        assert not decision.should_enter
        assert "downtrend" in decision.reason.lower()

    def test_long_entry_rsi_not_oversold(self, mean_reversion_strategy, neutral_signal, market_context):
        """Test entry fails when RSI is not oversold."""
        decision = mean_reversion_strategy.evaluate_entry(neutral_signal, market_context)

        assert not decision.should_enter
        assert "rsi" in decision.reason.lower()

    def test_short_entry_rsi_not_overbought(self, mean_reversion_strategy, neutral_signal, market_context):
        """Test entry fails when RSI is not overbought."""
        decision = mean_reversion_strategy.evaluate_entry(neutral_signal, market_context)

        assert not decision.should_enter
        assert "rsi" in decision.reason.lower()

    def test_short_entry_strong_uptrend(self, mean_reversion_strategy, overbought_signal, market_context):
        """Test entry fails when in strong uptrend."""
        overbought_signal["raw_data_daily"]["close"] = [120.0 + i * 1.5 for i in range(60)]
        overbought_signal["raw_data_daily"]["volume"] = [1000000 + 500000 * i for i in range(60)]
        decision = mean_reversion_strategy.evaluate_entry(overbought_signal, market_context)

        assert not decision.should_enter
        assert "uptrend" in decision.reason.lower()


class TestMeanReversionStrategyEvaluateExit:
    """Test exit evaluation logic."""

    def test_exit_no_conditions(self, mean_reversion_strategy, long_position, market_context):
        """Test no exit when conditions not met."""
        daily_data = pd.DataFrame(
            {
                "close": [140.0 + (i % 10 - 5) * 0.5 for i in range(60)],
                "volume": [1000000 + i * 10000 for i in range(60)],
            }
        )
        daily_data["RSI"] = 55.0
        signal = TradingSignals(
            symbol="AAPL",
            price=138.0,
            atr=2.0,
            rvol=1.2,
            signals=["No conditions met"],
            raw_score=50,
            score=0.50,
            momentum=0.0,
            raw_data_daily=daily_data,
            raw_data_intraday=pd.DataFrame({}),
        )
        decision = mean_reversion_strategy.evaluate_exit(long_position, signal, market_context)

        assert not decision.should_exit

    def test_exit_stop_loss_long(self, mean_reversion_strategy, long_position, market_context):
        """Test exit on stop loss for long position."""
        daily_data = pd.DataFrame(
            {
                "close": [140.0] * 30,
                "volume": [1000000] * 30,
            }
        )
        signal = TradingSignals(
            symbol="AAPL",
            price=135.0,
            atr=2.0,
            rvol=1.2,
            signals=["Stop loss"],
            raw_score=30,
            score=0.30,
            momentum=-15.0,
            raw_data_daily=daily_data,
            raw_data_intraday=pd.DataFrame({}),
        )
        decision = mean_reversion_strategy.evaluate_exit(long_position, signal, market_context)

        assert decision.should_exit
        assert "stop_loss" in decision.reason.lower()
        assert decision.urgency == "immediate"

    def test_exit_stop_loss_short(self, mean_reversion_strategy, short_position, market_context):
        """Test exit on stop loss for short position."""
        daily_data = pd.DataFrame(
            {
                "close": [148.0] * 30,
                "volume": [1000000] * 30,
            }
        )
        signal = TradingSignals(
            symbol="AAPL",
            price=152.0,
            atr=2.0,
            rvol=1.2,
            signals=["Stop loss"],
            raw_score=30,
            score=0.30,
            momentum=15.0,
            raw_data_daily=daily_data,
            raw_data_intraday=pd.DataFrame({}),
        )
        decision = mean_reversion_strategy.evaluate_exit(short_position, signal, market_context)

        assert decision.should_exit
        assert "stop_loss" in decision.reason.lower()
        assert decision.urgency == "immediate"


class TestMeanReversionStrategyIndicators:
    """Test indicator calculations."""

    def test_calculate_rsi(self, mean_reversion_strategy):
        """Test RSI calculation."""
        df = pd.DataFrame(
            {
                "close": [100, 101, 102, 101, 100, 99, 98, 99, 100, 101, 102, 103, 104, 103, 102, 101, 100, 99, 98, 99],
            }
        )
        rsi = mean_reversion_strategy._calculate_rsi(df)

        assert len(rsi) == len(df)
        assert not pd.isna(rsi.iloc[-1])
        assert rsi.iloc[-1] > 0
        assert rsi.iloc[-1] < 100

    def test_calculate_bollinger_bands(self, mean_reversion_strategy):
        """Test Bollinger Bands calculation."""
        df = pd.DataFrame(
            {
                "close": [100.0 + i * 0.5 + (i % 3 - 1) * 0.2 for i in range(30)],
            }
        )
        upper, middle, lower = mean_reversion_strategy._calculate_bollinger_bands(df)

        assert len(upper) == len(df)
        assert len(middle) == len(df)
        assert len(lower) == len(df)
        valid_upper = upper.dropna()
        valid_middle = middle.dropna()
        valid_lower = lower.dropna()
        assert (valid_upper >= valid_middle).all()
        assert (valid_middle >= valid_lower).all()

    def test_calculate_z_score(self, mean_reversion_strategy):
        """Test Z-score calculation."""
        df = pd.DataFrame(
            {
                "close": [100.0 + i * 0.5 for i in range(30)],
            }
        )
        z_score = mean_reversion_strategy._calculate_z_score(df)

        assert isinstance(z_score, float)

    def test_calculate_confidence_oversold(self, mean_reversion_strategy):
        """Test confidence calculation for oversold condition."""
        confidence = mean_reversion_strategy._calculate_confidence(20.0, -3.0, "oversold")

        assert confidence > 50
        assert confidence <= 95

    def test_calculate_confidence_overbought(self, mean_reversion_strategy):
        """Test confidence calculation for overbought condition."""
        confidence = mean_reversion_strategy._calculate_confidence(80.0, 3.0, "overbought")

        assert confidence > 50
        assert confidence <= 95

    def test_calculate_confidence_moderate(self, mean_reversion_strategy):
        """Test confidence calculation for moderate conditions."""
        confidence = mean_reversion_strategy._calculate_confidence(32.0, -2.1, "oversold")

        assert confidence >= 50
        assert confidence < 80
