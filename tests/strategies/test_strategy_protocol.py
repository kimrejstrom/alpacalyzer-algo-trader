"""Tests for Strategy protocol compliance."""

import pytest
from alpaca.trading.models import Position

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.data.models import TradingStrategy
from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision, MarketContext, Strategy


class MockStrategy(BaseStrategy):
    """Mock strategy for testing protocol compliance."""

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


def test_strategy_protocol_is_checkable():
    """Test that Strategy protocol is runtime_checkable."""
    # This should not raise an error - protocol must be @runtime_checkable
    mock = MockStrategy()
    assert isinstance(mock, Strategy)


def test_strategy_protocol_requires_methods():
    """Test that Strategy protocol requires all three methods."""
    # MockStrategy implements all methods, so it should be valid
    mock = MockStrategy()

    # Check that all required methods exist
    assert hasattr(mock, "evaluate_entry")
    assert hasattr(mock, "evaluate_exit")
    assert hasattr(mock, "calculate_position_size")


def test_incomplete_strategy_not_protocol_compliant():
    """Test that incomplete strategies fail isinstance check."""

    class IncompleteStrategy:
        """Strategy missing required methods."""

        def evaluate_entry(self, signal, context):
            pass

        # Missing evaluate_exit
        # Missing calculate_position_size

    incomplete = IncompleteStrategy()

    # Should not be considered a Strategy
    assert not isinstance(incomplete, Strategy)


def test_base_strategy_is_abstract():
    """Test that BaseStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseStrategy()
