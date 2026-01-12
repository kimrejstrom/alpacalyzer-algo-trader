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
