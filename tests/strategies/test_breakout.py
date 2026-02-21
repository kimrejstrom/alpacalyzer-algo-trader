"""
Unit tests for BreakoutStrategy.

Tests breakout detection, consolidation patterns, volume confirmation,
and exit conditions for both long and short positions.
"""

import pandas as pd

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.strategies.base import MarketContext
from alpacalyzer.strategies.breakout import BreakoutConfig, BreakoutPositionData, BreakoutStrategy


def create_mock_data(
    prices: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[int] | None = None,
) -> pd.DataFrame:
    """Create mock OHLCV DataFrame for testing."""
    if highs is None:
        highs = prices
    if lows is None:
        lows = prices
    if volumes is None:
        volumes = [1_000_000] * len(prices)

    return pd.DataFrame(
        {
            "open": prices,
            "close": prices,
            "high": highs,
            "low": lows,
            "volume": volumes,
        }
    )


def create_trading_signals(
    symbol: str,
    price: float,
    raw_data: pd.DataFrame,
    momentum: float = 0.0,
    score: float = 0.5,
    atr: float = 1.0,
    rvol: float = 1.0,
) -> TradingSignals:
    """Create mock TradingSignals for testing."""
    daily_df = raw_data.copy()
    intraday_df = raw_data.copy()

    return TradingSignals(
        symbol=symbol,
        signals=[],
        raw_score=int(score * 100),
        price=price,
        atr=atr,
        rvol=rvol,
        score=score,
        momentum=momentum,
        raw_data_daily=daily_df,
        raw_data_intraday=intraday_df,
    )


class TestBreakoutConfig:
    """Tests for BreakoutConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BreakoutConfig()

        assert config.name == "breakout"
        assert config.consolidation_periods == 20
        assert config.consolidation_range_pct == 0.05
        assert config.min_volume_ratio == 1.5
        assert config.breakout_buffer_pct == 0.002
        assert config.risk_pct_per_trade == 0.02
        assert config.target_multiple == 2.0
        assert config.min_atr == 0.5
        assert config.max_false_breakouts == 2

    def test_custom_config(self):
        """Test custom configuration values."""
        config = BreakoutConfig(
            name="custom_breakout",
            consolidation_periods=30,
            consolidation_range_pct=0.03,
            min_volume_ratio=2.0,
            target_multiple=3.0,
        )

        assert config.name == "custom_breakout"
        assert config.consolidation_periods == 30
        assert config.consolidation_range_pct == 0.03
        assert config.min_volume_ratio == 2.0
        assert config.target_multiple == 3.0


class TestBreakoutStrategyEntry:
    """Tests for BreakoutStrategy evaluate_entry method."""

    def test_bullish_breakout_detection(self):
        """Test detection of bullish breakout above resistance."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        pre_breakout_prices = [100.0] * 1
        pre_breakout_highs = [100.5] * 1
        pre_breakout_lows = [99.5] * 1
        pre_breakout_volumes = [1_000_000] * 1

        breakout_prices = [101.5]
        breakout_highs = [102.0]
        breakout_lows = [100.8]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + pre_breakout_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + pre_breakout_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + pre_breakout_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + pre_breakout_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is True
        assert decision.entry_price == 101.5
        assert decision.stop_loss < 101.5
        assert decision.target > 101.5
        assert "Bullish breakout" in decision.reason

    def test_bearish_breakout_detection(self):
        """Test detection of bearish breakout below support."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        breakout_prices = [98.5]
        breakout_highs = [99.0]
        breakout_lows = [97.0]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 98.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is True
        assert decision.entry_price == 98.5
        assert decision.stop_loss > 98.5
        assert decision.target < 98.5
        assert "Bearish breakout" in decision.reason

    def test_no_entry_without_consolidation(self):
        """Test no entry when price is not in consolidation."""
        config = BreakoutConfig(consolidation_periods=10, consolidation_range_pct=0.05)
        strategy = BreakoutStrategy(config)

        prices = [100.0, 105.0, 102.0, 108.0, 101.0, 110.0, 103.0, 112.0, 100.0, 115.0, 116.0, 118.0, 117.0, 119.0, 116.0, 120.0, 118.0, 121.0, 117.0, 122.0, 123.0, 125.0]
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 125.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "consolidation" in decision.reason.lower() or "range" in decision.reason.lower()

    def test_no_entry_without_volume_confirmation(self):
        """Test no entry when volume is too low."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 25 + [101.5]
        highs = [100.5] * 25 + [102.0]
        lows = [99.5] * 25 + [100.8]
        volumes = [1_000_000] * 25 + [1_200_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "volume" in decision.reason.lower()

    def test_no_entry_market_closed(self):
        """Test no entry when market is closed."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="closed",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "market" in decision.reason.lower()

    def test_no_entry_ticker_in_cooldown(self):
        """Test no entry when ticker is in cooldown."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=["TEST"],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "cooldown" in decision.reason.lower()

    def test_no_entry_existing_position(self):
        """Test no entry when already holding position in ticker."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "position" in decision.reason.lower()

    def test_no_entry_insufficient_data(self):
        """Test no entry when insufficient data for analysis."""
        config = BreakoutConfig(consolidation_periods=20)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 25
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 100.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False


class TestBreakoutStrategyExit:
    """Tests for BreakoutStrategy evaluate_exit method."""

    def create_alpaca_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        current_price: float,
        unrealized_plpc: float = 0.0,
    ):
        """Create mock Position using Alpaca's Position model."""
        from alpaca.trading.models import Position

        return Position.model_construct(
            symbol=symbol,
            side=side,
            avg_entry_price=str(entry_price),
            qty="100",
            current_price=str(current_price),
            unrealized_pl=str((current_price - entry_price) * 100),
            unrealized_plpc=str(unrealized_plpc),
            market_value=str(current_price * 100),
            cost_basis=str(entry_price * 100),
        )

    def test_exit_on_stop_loss_hit_long(self):
        """Test exit when stop loss is hit for long position."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.0]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 95.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=101.5,
            stop_loss=99.5,
            target=104.5,
            side="long",
        )

        position = self.create_alpaca_position("TEST", "long", entry_price=101.5, current_price=95.0)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is True
        assert decision.reason == "stop_loss"
        assert decision.urgency == "immediate"

    def test_exit_on_stop_loss_hit_short(self):
        """Test exit when stop loss is hit for short position."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [98.5]
        highs = [100.5] * 30 + [99.0]
        lows = [99.5] * 30 + [97.0]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 105.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=98.5,
            stop_loss=100.5,
            target=95.5,
            side="short",
        )

        position = self.create_alpaca_position("TEST", "short", entry_price=98.5, current_price=105.0)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is True
        assert decision.reason == "stop_loss"
        assert decision.urgency == "immediate"

    def test_exit_on_target_reached_long(self):
        """Test exit when target is reached for long position."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.8]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 110.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=101.5,
            stop_loss=99.5,
            target=104.5,
            side="long",
        )

        position = self.create_alpaca_position("TEST", "long", entry_price=101.5, current_price=110.0, unrealized_plpc=0.10)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is True
        assert decision.reason == "target_reached"
        assert decision.urgency == "normal"

    def test_exit_on_target_reached_short(self):
        """Test exit when target is reached for short position."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [98.5]
        highs = [100.5] * 30 + [99.0]
        lows = [99.5] * 30 + [97.0]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 90.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=98.5,
            stop_loss=100.5,
            target=95.5,
            side="short",
        )

        position = self.create_alpaca_position("TEST", "short", entry_price=98.5, current_price=90.0, unrealized_plpc=0.10)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is True
        assert decision.reason == "target_reached"
        assert decision.urgency == "normal"

    def test_exit_on_failed_breakout_long(self):
        """Test exit when bullish breakout fails (price returns to range)."""
        config = BreakoutConfig(consolidation_periods=10)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 20 + [102.0, 102.0] * 5 + [102.0, 101.0]
        highs = [100.5] * 20 + [102.5, 102.5] * 5 + [102.5, 101.5]
        lows = [99.5] * 20 + [101.0, 101.0] * 5 + [101.0, 100.0]
        df = create_mock_data(prices, highs, lows)
        signal = create_trading_signals("TEST", 101.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=102.0,
            stop_loss=99.5,
            target=107.0,
            side="long",
        )

        position = self.create_alpaca_position("TEST", "long", entry_price=102.0, current_price=101.0)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is True
        assert decision.reason == "breakout_failed"
        assert decision.urgency == "urgent"

    def test_exit_on_failed_breakout_short(self):
        """Test exit when bearish breakout fails (price returns to range)."""
        config = BreakoutConfig(consolidation_periods=10)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 20 + [98.0, 98.0] * 5 + [98.0, 99.5]
        highs = [100.5] * 20 + [99.0, 99.0] * 5 + [99.0, 100.0]
        lows = [99.5] * 20 + [97.0, 97.0] * 5 + [97.0, 98.5]
        df = create_mock_data(prices, highs, lows)
        signal = create_trading_signals("TEST", 99.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=98.0,
            stop_loss=100.5,
            target=93.0,
            side="short",
        )

        position = self.create_alpaca_position("TEST", "short", entry_price=98.0, current_price=99.5)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is True
        assert decision.reason == "breakout_failed"
        assert decision.urgency == "urgent"

    def test_no_exit_when_conditions_not_met(self):
        """Test no exit when all conditions are still valid."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.8]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=101.5,
            stop_loss=99.5,
            target=104.5,
            side="long",
        )

        position = self.create_alpaca_position("TEST", "long", entry_price=101.5, current_price=101.0, unrealized_plpc=0.01)

        decision = strategy.evaluate_exit(position, signal, context)

        assert decision.should_exit is False


class TestBreakoutStrategyFalseBreakouts:
    """Tests for false breakout tracking."""

    def test_false_breakout_counting(self):
        """Test that false breakouts are tracked per ticker."""
        config = BreakoutConfig(max_false_breakouts=2)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.0]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 95.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=101.5,
            stop_loss=99.5,
            target=104.5,
            side="long",
        )

        from alpaca.trading.models import Position

        position = Position.model_construct(
            symbol="TEST",
            side="long",
            avg_entry_price="101.5",
            qty="100",
            current_price="95.0",
            unrealized_pl="-650.0",
            unrealized_plpc="-0.02",
            market_value="9500.0",
            cost_basis="10150.0",
        )

        strategy.evaluate_exit(position, signal, context)

        assert strategy._false_breakout_count.get("TEST", 0) == 1

    def test_false_breakout_block_entry(self):
        """Test that entries are blocked after max false breakouts."""
        config = BreakoutConfig(max_false_breakouts=1)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.0]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 95.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        strategy._false_breakout_count["TEST"] = 1

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "false breakout" in decision.reason.lower()

    def test_successful_trade_clears_false_breakouts(self):
        """Test that successful trade clears false breakout count."""
        config = BreakoutConfig(max_false_breakouts=2)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.8]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 110.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=["TEST"],
            cooldown_tickers=[],
        )

        strategy._position_data["TEST"] = BreakoutPositionData(
            entry_price=101.5,
            stop_loss=99.5,
            target=104.5,
            side="long",
        )

        from alpaca.trading.models import Position

        position = Position.model_construct(
            symbol="TEST",
            side="long",
            avg_entry_price="101.5",
            qty="100",
            current_price="110.0",
            unrealized_pl="850.0",
            unrealized_plpc="0.10",
            market_value="11000.0",
            cost_basis="10150.0",
        )

        strategy.evaluate_exit(position, signal, context)

        assert strategy._false_breakout_count.get("TEST", 0) == 0


class TestBreakoutStrategyConfidence:
    """Tests for confidence calculation."""

    def test_confidence_increases_with_volume(self):
        """Test that confidence increases with higher volume."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        low_volume_df = create_mock_data([100.0] * 20 + [101.5], volumes=[1_000_000] * 20 + [1_600_000])
        high_volume_df = create_mock_data([100.0] * 20 + [101.5], volumes=[1_000_000] * 20 + [2_500_000])

        low_confidence = strategy._calculate_confidence(low_volume_df, "bullish")
        high_confidence = strategy._calculate_confidence(high_volume_df, "bullish")

        assert high_confidence > low_confidence

    def test_confidence_alignment_with_trend(self):
        """Test that confidence increases when price aligns with trend."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        aligned_df = create_mock_data([95.0, 97.0, 98.0, 99.0, 100.0] * 4 + [101.5])
        misaligned_df = create_mock_data([105.0, 103.0, 102.0, 101.0, 100.0] * 4 + [101.5])

        aligned_confidence = strategy._calculate_confidence(aligned_df, "bullish")
        misaligned_confidence = strategy._calculate_confidence(misaligned_df, "bullish")

        assert aligned_confidence > misaligned_confidence

    def test_confidence_with_tight_range(self):
        """Test that confidence increases with tighter consolidation range."""
        config = BreakoutConfig(consolidation_periods=10)
        strategy = BreakoutStrategy(config)

        tight_range_df = create_mock_data([100.0, 100.2, 100.1, 100.3, 100.0] * 4 + [101.5])
        loose_range_df = create_mock_data([98.0, 102.0, 99.0, 101.0, 100.0] * 4 + [101.5])

        tight_confidence = strategy._calculate_confidence(tight_range_df, "bullish")
        loose_confidence = strategy._calculate_confidence(loose_range_df, "bullish")

        assert tight_confidence > loose_confidence

    def test_confidence_maximum(self):
        """Test that confidence doesn't exceed 95%."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        df = create_mock_data([95.0, 97.0, 98.0, 99.0, 100.0] * 4 + [105.0], volumes=[1_000_000] * 20 + [5_000_000])

        confidence = strategy._calculate_confidence(df, "bullish")

        assert confidence <= 95.0


class TestBreakoutStrategyATR:
    """Tests for ATR calculation."""

    def test_atr_calculation(self):
        """Test that ATR is calculated correctly."""
        config = BreakoutConfig()
        strategy = BreakoutStrategy(config)

        df = pd.DataFrame(
            {
                "open": [100, 101, 102, 101, 103],
                "close": [101, 102, 101, 103, 104],
                "high": [102, 103, 102, 104, 105],
                "low": [99, 100, 100, 101, 102],
                "volume": [1_000_000] * 5,
            }
        )

        atr = strategy._calculate_atr(df, period=5)

        assert atr >= 0

    def test_low_atr_prevents_entry(self):
        """Test that entry is prevented when ATR is below minimum."""
        config = BreakoutConfig(min_atr=5.0)
        strategy = BreakoutStrategy(config)

        df = pd.DataFrame(
            {
                "open": [
                    100,
                    100.1,
                    100.2,
                    100.1,
                    100.3,
                    100.4,
                    100.3,
                    100.5,
                    100.4,
                    100.6,
                    100.5,
                    100.7,
                    100.6,
                    100.8,
                    100.7,
                    100.9,
                    100.8,
                    101.0,
                    100.9,
                    101.1,
                    101.0,
                    101.2,
                    101.1,
                    101.3,
                    101.2,
                    101.4,
                    101.3,
                    101.5,
                    101.4,
                    101.6,
                    101.5,
                    101.7,
                    101.6,
                    101.8,
                    101.7,
                    101.9,
                    101.8,
                    102.0,
                    101.9,
                    102.1,
                ],
                "close": [
                    100.1,
                    100.2,
                    100.1,
                    100.3,
                    100.4,
                    100.3,
                    100.5,
                    100.4,
                    100.6,
                    100.5,
                    100.7,
                    100.6,
                    100.8,
                    100.7,
                    100.9,
                    100.8,
                    101.0,
                    100.9,
                    101.1,
                    101.0,
                    101.2,
                    101.1,
                    101.3,
                    101.2,
                    101.4,
                    101.3,
                    101.5,
                    101.4,
                    101.6,
                    101.5,
                    101.7,
                    101.6,
                    101.8,
                    101.7,
                    101.9,
                    101.8,
                    102.0,
                    101.9,
                    102.1,
                    102.0,
                ],
                "high": [
                    100.2,
                    100.3,
                    100.2,
                    100.4,
                    100.5,
                    100.4,
                    100.6,
                    100.5,
                    100.7,
                    100.6,
                    100.8,
                    100.7,
                    100.9,
                    100.8,
                    101.0,
                    100.9,
                    101.1,
                    101.0,
                    101.2,
                    101.1,
                    101.3,
                    101.2,
                    101.4,
                    101.3,
                    101.5,
                    101.4,
                    101.6,
                    101.5,
                    101.7,
                    101.6,
                    101.8,
                    101.7,
                    101.9,
                    101.8,
                    102.0,
                    101.9,
                    102.1,
                    102.0,
                    102.2,
                    102.1,
                ],
                "low": [
                    99.9,
                    100.0,
                    100.0,
                    100.1,
                    100.2,
                    100.1,
                    100.3,
                    100.2,
                    100.4,
                    100.3,
                    100.5,
                    100.4,
                    100.6,
                    100.5,
                    100.7,
                    100.6,
                    100.8,
                    100.7,
                    100.9,
                    100.8,
                    101.0,
                    100.9,
                    101.1,
                    101.0,
                    101.2,
                    101.1,
                    101.3,
                    101.2,
                    101.4,
                    101.3,
                    101.5,
                    101.4,
                    101.6,
                    101.5,
                    101.7,
                    101.6,
                    101.8,
                    101.7,
                    101.9,
                    101.8,
                ],
                "volume": [2_000_000] * 39 + [4_000_000],  # 2.0x volume to pass volume check
            }
        )

        signal = create_trading_signals("TEST", 102.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is False
        assert "atr" in decision.reason.lower() or "volatility" in decision.reason.lower()


class TestBreakoutStrategyProperties:
    """Tests for BreakoutStrategy properties."""

    def test_name_property(self):
        """Test that name property returns config name."""
        config = BreakoutConfig(name="test_breakout")
        strategy = BreakoutStrategy(config)

        assert strategy.name == "test_breakout"

    def test_default_name(self):
        """Test that default name is 'breakout'."""
        strategy = BreakoutStrategy()

        assert strategy.name == "breakout"


class TestBreakoutStrategyPositionSizing:
    """Tests for BreakoutStrategy position sizing."""

    def test_bullish_breakout_position_sizing(self):
        """Test that bullish breakout calculates non-zero position size."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        pre_breakout_prices = [100.0] * 1
        pre_breakout_highs = [100.5] * 1
        pre_breakout_lows = [99.5] * 1
        pre_breakout_volumes = [1_000_000] * 1

        breakout_prices = [101.5]
        breakout_highs = [102.0]
        breakout_lows = [100.8]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + pre_breakout_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + pre_breakout_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + pre_breakout_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + pre_breakout_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is True
        assert decision.suggested_size > 0, f"Position size should be > 0, got {decision.suggested_size}"
        assert decision.entry_price == 101.5
        assert decision.stop_loss < 101.5
        assert decision.target > 101.5

    def test_bearish_breakout_position_sizing(self):
        """Test that bearish breakout calculates non-zero position size."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        breakout_prices = [98.5]
        breakout_highs = [99.0]
        breakout_lows = [97.0]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 98.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        decision = strategy.evaluate_entry(signal, context)

        assert decision.should_enter is True
        assert decision.suggested_size > 0, f"Position size should be > 0, got {decision.suggested_size}"
        assert decision.entry_price == 98.5
        assert decision.stop_loss > 98.5
        assert decision.target < 98.5


class TestBreakoutStrategyAgentIntegration:
    """
    Tests for agent recommendation integration (Issue #96).

    Verifies the "agents propose, strategies validate" pattern:
    - When agent_recommendation provided: use agent's values if conditions valid
    - When agent_recommendation is None: calculate own values (current behavior)
    """

    def create_agent_recommendation(
        self,
        ticker: str = "TEST",
        quantity: int = 50,
        entry_point: float = 101.5,
        stop_loss: float = 98.0,
        target_price: float = 108.0,
        trade_type: str = "long",
    ):
        """Create mock TradingStrategy (agent recommendation)."""
        from alpacalyzer.data.models import TradingStrategy

        return TradingStrategy(
            ticker=ticker,
            quantity=quantity,
            entry_point=entry_point,
            stop_loss=stop_loss,
            target_price=target_price,
            risk_reward_ratio=2.0,
            strategy_notes="Agent recommendation for breakout",
            trade_type=trade_type,
            entry_criteria=[],
        )

    def test_entry_with_agent_recommendation_uses_agent_values(self):
        """Test that agent's values are used when conditions are valid."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        # Create valid breakout setup
        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        pre_breakout_prices = [100.0] * 1
        pre_breakout_highs = [100.5] * 1
        pre_breakout_lows = [99.5] * 1
        pre_breakout_volumes = [1_000_000] * 1

        breakout_prices = [101.5]
        breakout_highs = [102.0]
        breakout_lows = [100.8]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + pre_breakout_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + pre_breakout_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + pre_breakout_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + pre_breakout_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        # Agent provides specific values
        agent_rec = self.create_agent_recommendation(
            ticker="TEST",
            quantity=75,  # Agent's quantity
            entry_point=101.5,
            stop_loss=97.5,  # Agent's stop loss (different from strategy's calculation)
            target_price=110.0,  # Agent's target (different from strategy's calculation)
            trade_type="long",
        )

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        assert decision.should_enter is True
        # Verify agent's values are used, not strategy's calculations
        assert decision.suggested_size == 75, f"Expected agent's quantity 75, got {decision.suggested_size}"
        assert decision.entry_price == 101.5, f"Expected agent's entry 101.5, got {decision.entry_price}"
        assert decision.stop_loss == 97.5, f"Expected agent's stop_loss 97.5, got {decision.stop_loss}"
        assert decision.target == 110.0, f"Expected agent's target 110.0, got {decision.target}"

    def test_entry_with_agent_recommendation_short_uses_agent_values(self):
        """Test that agent's values are used for short breakout when conditions valid."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        # Create valid bearish breakout setup
        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        breakout_prices = [98.5]
        breakout_highs = [99.0]
        breakout_lows = [97.0]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 98.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        # Agent provides specific values for short
        agent_rec = self.create_agent_recommendation(
            ticker="TEST",
            quantity=60,
            entry_point=98.5,
            stop_loss=102.0,  # Agent's stop loss for short
            target_price=92.0,  # Agent's target for short
            trade_type="short",
        )

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        assert decision.should_enter is True
        assert decision.suggested_size == 60
        assert decision.entry_price == 98.5
        assert decision.stop_loss == 102.0
        assert decision.target == 92.0

    def test_entry_with_agent_recommendation_rejects_no_consolidation(self):
        """Test that entry is rejected when no consolidation pattern exists."""
        config = BreakoutConfig(consolidation_periods=10, consolidation_range_pct=0.05)
        strategy = BreakoutStrategy(config)

        # Create non-consolidation data (wide range)
        prices = [100.0, 105.0, 102.0, 108.0, 101.0, 110.0, 103.0, 112.0, 100.0, 115.0, 116.0, 118.0, 117.0, 119.0, 116.0, 120.0, 118.0, 121.0, 117.0, 122.0, 123.0, 125.0]
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 125.0, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        agent_rec = self.create_agent_recommendation(
            ticker="TEST",
            quantity=50,
            entry_point=125.0,
            stop_loss=120.0,
            target_price=135.0,
            trade_type="long",
        )

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        # Should reject even with agent recommendation
        assert decision.should_enter is False
        assert "consolidation" in decision.reason.lower() or "range" in decision.reason.lower()

    def test_entry_with_agent_recommendation_rejects_low_volume(self):
        """Test that entry is rejected when volume confirmation is missing."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        # Create consolidation with low volume breakout
        prices = [100.0] * 25 + [101.5]
        highs = [100.5] * 25 + [102.0]
        lows = [99.5] * 25 + [100.8]
        volumes = [1_000_000] * 25 + [1_200_000]  # Only 1.2x volume, below 1.5x threshold

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        agent_rec = self.create_agent_recommendation(
            ticker="TEST",
            quantity=50,
            entry_point=101.5,
            stop_loss=98.0,
            target_price=108.0,
            trade_type="long",
        )

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        # Should reject even with agent recommendation
        assert decision.should_enter is False
        assert "volume" in decision.reason.lower()

    def test_entry_without_agent_recommendation_calculates_own_values(self):
        """Test that strategy calculates own values when no agent recommendation."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        # Create valid breakout setup
        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        pre_breakout_prices = [100.0] * 1
        pre_breakout_highs = [100.5] * 1
        pre_breakout_lows = [99.5] * 1
        pre_breakout_volumes = [1_000_000] * 1

        breakout_prices = [101.5]
        breakout_highs = [102.0]
        breakout_lows = [100.8]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + pre_breakout_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + pre_breakout_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + pre_breakout_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + pre_breakout_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        # No agent recommendation - strategy should calculate own values
        decision = strategy.evaluate_entry(signal, context, agent_recommendation=None)

        assert decision.should_enter is True
        # Strategy calculates its own values
        assert decision.suggested_size > 0
        assert decision.entry_price == 101.5
        # Stop loss and target are calculated by strategy, not agent
        assert decision.stop_loss < 101.5  # Below entry for long
        assert decision.target > 101.5  # Above entry for long

    def test_entry_with_agent_recommendation_rejects_basic_filters(self):
        """Test that basic filters still apply with agent recommendation."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        prices = [100.0] * 30 + [101.5]
        df = create_mock_data(prices)
        signal = create_trading_signals("TEST", 101.5, df)

        # Market closed
        context = MarketContext(
            vix=15.0,
            market_status="closed",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        agent_rec = self.create_agent_recommendation()

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        assert decision.should_enter is False
        assert "market" in decision.reason.lower()

    def test_entry_with_agent_recommendation_rejects_false_breakouts(self):
        """Test that false breakout limit still applies with agent recommendation."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5, max_false_breakouts=1)
        strategy = BreakoutStrategy(config)

        # Create valid breakout setup
        prices = [100.0] * 30 + [101.5]
        highs = [100.5] * 30 + [102.0]
        lows = [99.5] * 30 + [100.0]
        volumes = [1_000_000] * 30 + [2_000_000]

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        # Set false breakout count at limit
        strategy._false_breakout_count["TEST"] = 1

        agent_rec = self.create_agent_recommendation()

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        assert decision.should_enter is False
        assert "false breakout" in decision.reason.lower()

    def test_entry_with_agent_recommendation_rejects_bullish_breakout_short(self):
        """Test that breakout rejects when agent proposes short but breakout is bullish."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        # Create valid bullish breakout setup
        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        breakout_prices = [101.5]
        breakout_highs = [102.0]
        breakout_lows = [100.8]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 101.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        # Agent provides SHORT recommendation but breakout is BULLISH
        agent_rec = self.create_agent_recommendation(
            ticker="TEST",
            quantity=50,
            entry_point=101.5,
            stop_loss=103.0,
            target_price=98.0,
            trade_type="short",  # Mismatch: breakout is bullish
        )

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        assert decision.should_enter is False
        assert "trade_type mismatch" in decision.reason.lower()
        assert "bullish" in decision.reason.lower()

    def test_entry_with_agent_recommendation_rejects_bearish_breakout_long(self):
        """Test that breakout rejects when agent proposes long but breakout is bearish."""
        config = BreakoutConfig(consolidation_periods=10, min_volume_ratio=1.5)
        strategy = BreakoutStrategy(config)

        # Create valid bearish breakout setup
        pre_consolidation_prices = [100.0] * 20
        pre_consolidation_highs = [100.5] * 20
        pre_consolidation_lows = [99.5] * 20
        pre_consolidation_volumes = [1_000_000] * 20

        consolidation_prices = [100.0] * 10
        consolidation_highs = [100.5] * 10
        consolidation_lows = [99.5] * 10
        consolidation_volumes = [1_000_000] * 10

        breakout_prices = [98.5]
        breakout_highs = [99.0]
        breakout_lows = [97.0]
        breakout_volumes = [2_000_000]

        prices = pre_consolidation_prices + consolidation_prices + breakout_prices
        highs = pre_consolidation_highs + consolidation_highs + breakout_highs
        lows = pre_consolidation_lows + consolidation_lows + breakout_lows
        volumes = pre_consolidation_volumes + consolidation_volumes + breakout_volumes

        df = create_mock_data(prices, highs, lows, volumes)
        signal = create_trading_signals("TEST", 98.5, df)

        context = MarketContext(
            vix=15.0,
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        # Agent provides LONG recommendation but breakout is BEARISH
        agent_rec = self.create_agent_recommendation(
            ticker="TEST",
            quantity=50,
            entry_point=98.5,
            stop_loss=96.0,
            target_price=103.0,
            trade_type="long",  # Mismatch: breakout is bearish
        )

        decision = strategy.evaluate_entry(signal, context, agent_recommendation=agent_rec)

        assert decision.should_enter is False
        assert "trade_type mismatch" in decision.reason.lower()
        assert "bearish" in decision.reason.lower()
