"""Tests for BaseStrategy functionality."""

import pandas as pd
import pytest
from alpaca.trading.models import Position

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.data.models import TradingStrategy
from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision, MarketContext


class MockStrategy(BaseStrategy):
    """Mock strategy for testing BaseStrategy methods."""

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: TradingStrategy | None = None,
    ) -> EntryDecision:
        return EntryDecision(should_enter=False, reason="Mock")

    def evaluate_exit(
        self,
        position: Position,
        signal: TradingSignals,
        context: MarketContext,
    ) -> ExitDecision:
        return ExitDecision(should_exit=False, reason="Mock")


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
def bullish_signal():
    """Bullish trading signal."""
    empty_df = pd.DataFrame()
    return TradingSignals(
        symbol="AAPL",
        price=150.00,
        atr=2.5,
        rvol=1.2,
        signals=["RSI oversold", "Bullish crossover"],
        raw_score=75,
        score=0.75,
        momentum=8.5,
        raw_data_daily=empty_df,
        raw_data_intraday=empty_df,
    )


def test_base_strategy_default_position_sizing(bullish_signal, market_context):
    """Test default calculate_position_size implementation."""
    strategy = MockStrategy()

    # Calculate position size for $5000 max amount
    size = strategy.calculate_position_size(bullish_signal, market_context, 5000.0)

    # Expected: 5000 / 150 = 33.33 -> 33 shares
    assert size == 33


def test_base_strategy_position_sizing_zero_price():
    """Test calculate_position_size with zero price."""
    strategy = MockStrategy()

    empty_df = pd.DataFrame()
    signal = TradingSignals(
        symbol="AAPL",
        price=0.0,
        atr=0.0,
        rvol=1.0,
        signals=[],
        raw_score=0,
        score=0.0,
        momentum=0.0,
        raw_data_daily=empty_df,
        raw_data_intraday=empty_df,
    )
    context = MarketContext(
        vix=15.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=[],
        cooldown_tickers=[],
    )

    size = strategy.calculate_position_size(signal, context, 5000.0)
    assert size == 0


def test_base_strategy_position_sizing_missing_price():
    """Test calculate_position_size when price is missing."""
    strategy = MockStrategy()

    signal = {"symbol": "AAPL"}
    context = MarketContext(
        vix=15.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=[],
        cooldown_tickers=[],
    )

    size = strategy.calculate_position_size(signal, context, 5000.0)
    assert size == 0


def test_base_strategy_check_basic_filters_market_open(bullish_signal, market_context):
    """Test _check_basic_filters passes when market is open."""
    strategy = MockStrategy()

    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)

    assert passed
    assert reason == "Basic filters passed"


def test_base_strategy_check_basic_filters_market_closed(bullish_signal, market_context):
    """Test _check_basic_filters fails when market is closed."""
    strategy = MockStrategy()
    market_context.market_status = "closed"

    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)

    assert not passed
    assert "closed" in reason.lower()


def test_base_strategy_check_basic_filters_in_cooldown(bullish_signal, market_context):
    """Test _check_basic_filters fails when ticker is in cooldown."""
    strategy = MockStrategy()
    market_context.cooldown_tickers = ["AAPL"]

    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)

    assert not passed
    assert "cooldown" in reason.lower()


def test_base_strategy_check_basic_filters_existing_position(bullish_signal, market_context):
    """Test _check_basic_filters fails when position already exists."""
    strategy = MockStrategy()
    market_context.existing_positions = ["AAPL"]

    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)

    assert not passed
    assert "position" in reason.lower()


def test_base_strategy_check_basic_filters_case_insensitive(bullish_signal, market_context):
    """Test _check_basic_filters is case-insensitive for market status."""
    strategy = MockStrategy()

    # Test uppercase
    market_context.market_status = "OPEN"
    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)
    assert passed

    # Test lowercase
    market_context.market_status = "open"
    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)
    assert passed

    # Test mixed case
    market_context.market_status = "Open"
    passed, reason = strategy._check_basic_filters(bullish_signal, market_context)
    assert passed


# =============================================================================
# ATR/VIX-Aware Position Sizing Tests (Issue #95)
# =============================================================================


class TestATRVIXAwarePositionSizing:
    """Tests for consolidated ATR/VIX-aware position sizing in BaseStrategy."""

    @pytest.fixture
    def signal_with_atr(self):
        """Trading signal with ATR data."""
        empty_df = pd.DataFrame()
        return TradingSignals(
            symbol="AAPL",
            price=100.0,
            atr=2.0,  # ATR of $2
            rvol=1.2,
            signals=["RSI oversold"],
            raw_score=75,
            score=0.75,
            momentum=8.5,
            raw_data_daily=empty_df,
            raw_data_intraday=empty_df,
        )

    @pytest.fixture
    def signal_without_atr(self):
        """Trading signal without ATR data."""
        empty_df = pd.DataFrame()
        return TradingSignals(
            symbol="AAPL",
            price=100.0,
            atr=0.0,  # No ATR
            rvol=1.2,
            signals=[],
            raw_score=50,
            score=0.5,
            momentum=0.0,
            raw_data_daily=empty_df,
            raw_data_intraday=empty_df,
        )

    @pytest.fixture
    def context_normal_vix(self):
        """Market context with normal VIX."""
        return MarketContext(
            vix=20.0,  # Normal VIX
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

    @pytest.fixture
    def context_high_vix(self):
        """Market context with high VIX."""
        return MarketContext(
            vix=40.0,  # High VIX
            market_status="open",
            account_equity=100000.0,
            buying_power=50000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

    def test_position_sizing_uses_atr_when_available(self, signal_with_atr, context_normal_vix):
        """Test that position sizing uses ATR for risk calculation when available."""
        strategy = MockStrategy()

        # With ATR=2.0, risk_per_share = 2 * ATR = $4
        # base_risk = 2% of account_equity = $2000
        # shares = risk_amount / (2 * ATR) = 2000 / 4 = 500 shares
        # position_value = 500 * 100 = $50,000
        # But capped at 5% of equity = $5000, so 50 shares
        # Also capped at max_amount = $5000, so 50 shares
        size = strategy.calculate_position_size(signal_with_atr, context_normal_vix, 5000.0)

        # ATR-based sizing should give us shares based on risk calculation
        # Simple sizing would give: 5000 / 100 = 50 shares
        # ATR sizing with these params should also give ~50 (capped by max_amount)
        assert size > 0
        assert isinstance(size, int)
        # Verify it doesn't exceed max_amount
        assert size * signal_with_atr["price"] <= 5000.0

    def test_position_sizing_reduces_with_high_vix(self, signal_with_atr, context_normal_vix, context_high_vix):
        """Test that high VIX reduces position size."""
        strategy = MockStrategy()

        size_normal_vix = strategy.calculate_position_size(signal_with_atr, context_normal_vix, 5000.0)
        size_high_vix = strategy.calculate_position_size(signal_with_atr, context_high_vix, 5000.0)

        # High VIX should result in smaller position
        assert size_high_vix <= size_normal_vix

    def test_position_sizing_fallback_without_atr(self, signal_without_atr, context_normal_vix):
        """Test fallback to simple sizing when ATR is unavailable."""
        strategy = MockStrategy()

        # Without ATR, should fall back to max_amount / price
        size = strategy.calculate_position_size(signal_without_atr, context_normal_vix, 5000.0)

        # Fallback: 5000 / 100 = 50 shares
        assert size == 50

    def test_position_sizing_respects_max_amount(self, signal_with_atr, context_normal_vix):
        """Test that position size never exceeds max_amount."""
        strategy = MockStrategy()

        max_amount = 1000.0
        size = strategy.calculate_position_size(signal_with_atr, context_normal_vix, max_amount)

        # Position value should not exceed max_amount
        position_value = size * signal_with_atr["price"]
        assert position_value <= max_amount

    def test_position_sizing_with_high_atr_reduces_size(self, context_normal_vix):
        """Test that high ATR (volatile stock) reduces position size."""
        strategy = MockStrategy()
        empty_df = pd.DataFrame()

        # Low ATR signal
        low_atr_signal = TradingSignals(
            symbol="AAPL",
            price=100.0,
            atr=1.0,  # Low volatility
            rvol=1.0,
            signals=[],
            raw_score=50,
            score=0.5,
            momentum=0.0,
            raw_data_daily=empty_df,
            raw_data_intraday=empty_df,
        )

        # High ATR signal
        high_atr_signal = TradingSignals(
            symbol="AAPL",
            price=100.0,
            atr=5.0,  # High volatility
            rvol=1.0,
            signals=[],
            raw_score=50,
            score=0.5,
            momentum=0.0,
            raw_data_daily=empty_df,
            raw_data_intraday=empty_df,
        )

        size_low_atr = strategy.calculate_position_size(low_atr_signal, context_normal_vix, 5000.0)
        size_high_atr = strategy.calculate_position_size(high_atr_signal, context_normal_vix, 5000.0)

        # Higher ATR should result in smaller position (more risk per share)
        assert size_high_atr <= size_low_atr

    def test_position_sizing_minimum_one_share(self, context_normal_vix):
        """Test that position sizing returns at least 1 share when conditions allow."""
        strategy = MockStrategy()
        empty_df = pd.DataFrame()

        # Very high ATR relative to max_amount
        signal = TradingSignals(
            symbol="AAPL",
            price=100.0,
            atr=50.0,  # Very high ATR
            rvol=1.0,
            signals=[],
            raw_score=50,
            score=0.5,
            momentum=0.0,
            raw_data_daily=empty_df,
            raw_data_intraday=empty_df,
        )

        # Small max_amount but enough for at least 1 share
        size = strategy.calculate_position_size(signal, context_normal_vix, 150.0)

        # Should return at least 1 share if max_amount >= price
        assert size >= 1

    def test_position_sizing_zero_when_insufficient_funds(self, context_normal_vix):
        """Test that position sizing returns 0 when max_amount < price."""
        strategy = MockStrategy()
        empty_df = pd.DataFrame()

        signal = TradingSignals(
            symbol="AAPL",
            price=100.0,
            atr=2.0,
            rvol=1.0,
            signals=[],
            raw_score=50,
            score=0.5,
            momentum=0.0,
            raw_data_daily=empty_df,
            raw_data_intraday=empty_df,
        )

        # max_amount less than price of 1 share
        size = strategy.calculate_position_size(signal, context_normal_vix, 50.0)

        assert size == 0
