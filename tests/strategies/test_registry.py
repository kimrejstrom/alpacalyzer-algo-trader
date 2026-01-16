"""
Tests for StrategyRegistry.

Tests cover:
- Registering strategies
- Retrieving strategies by name
- Instance caching for singleton access
- Custom config handling
- Error handling for unknown strategies
- Listing available strategies
"""

from typing import TYPE_CHECKING

import pytest

from alpacalyzer.strategies.base import BaseStrategy, EntryDecision, ExitDecision, MarketContext
from alpacalyzer.strategies.config import StrategyConfig

if TYPE_CHECKING:
    from alpacalyzer.analysis.technical_analysis import TradingSignals
else:
    # Runtime: use dict as fallback
    TradingSignals = dict

from alpacalyzer.strategies.registry import StrategyRegistry


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""

    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: object = None,
    ) -> EntryDecision:
        return EntryDecision(should_enter=False, reason="Mock strategy")

    def evaluate_exit(
        self,
        position: object,
        signal: TradingSignals,
        context: MarketContext,
    ) -> ExitDecision:
        return ExitDecision(should_exit=False, reason="Mock strategy")


class TestStrategyRegistry:
    """Test suite for StrategyRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        StrategyRegistry._strategies.clear()
        StrategyRegistry._instances.clear()
        StrategyRegistry._default_configs.clear()

    def teardown_method(self):
        """Restore built-in strategies after each test."""
        from alpacalyzer.strategies.breakout import BreakoutStrategy
        from alpacalyzer.strategies.mean_reversion import MeanReversionStrategy
        from alpacalyzer.strategies.momentum import MomentumStrategy

        StrategyRegistry.register("breakout", BreakoutStrategy, BreakoutStrategy._default_config())
        StrategyRegistry.register("mean_reversion", MeanReversionStrategy, MeanReversionStrategy._default_config())
        StrategyRegistry.register("momentum", MomentumStrategy, MomentumStrategy._default_config())

    def test_register_strategy(self):
        """Test registering a strategy class."""
        StrategyRegistry.register("test", MockStrategy)

        assert "test" in StrategyRegistry._strategies
        assert StrategyRegistry._strategies["test"] is MockStrategy

    def test_register_strategy_with_default_config(self):
        """Test registering a strategy with default config."""
        config = StrategyConfig(name="test_default", stop_loss_pct=0.05)
        StrategyRegistry.register("test", MockStrategy, default_config=config)

        assert "test" in StrategyRegistry._strategies
        assert "test" in StrategyRegistry._default_configs
        assert StrategyRegistry._default_configs["test"] is config

    def test_get_strategy_without_config(self):
        """Test getting a strategy instance without custom config."""
        StrategyRegistry.register("test", MockStrategy)
        strategy = StrategyRegistry.get("test")

        assert isinstance(strategy, MockStrategy)
        assert isinstance(strategy.config, StrategyConfig)

    def test_get_strategy_returns_singleton_without_custom_config(self):
        """Test that get() returns same instance when no custom config."""
        StrategyRegistry.register("test", MockStrategy)
        strategy1 = StrategyRegistry.get("test")
        strategy2 = StrategyRegistry.get("test")

        assert strategy1 is strategy2

    def test_get_strategy_with_custom_config(self):
        """Test getting a strategy with custom config."""
        default_config = StrategyConfig(name="default", stop_loss_pct=0.05)
        custom_config = StrategyConfig(name="custom", stop_loss_pct=0.10)

        StrategyRegistry.register("test", MockStrategy, default_config=default_config)

        strategy_default = StrategyRegistry.get("test")
        strategy_custom = StrategyRegistry.get("test", config=custom_config)

        # Cast to access config attribute safely
        assert strategy_default.config.stop_loss_pct == 0.05  # type: ignore[attr-defined]
        assert strategy_custom.config.stop_loss_pct == 0.10  # type: ignore[attr-defined]

    def test_get_strategy_custom_config_not_cached(self):
        """Test that custom config creates new instance, not cached."""
        default_config = StrategyConfig(name="default", stop_loss_pct=0.05)
        custom_config = StrategyConfig(name="custom", stop_loss_pct=0.10)

        StrategyRegistry.register("test", MockStrategy, default_config=default_config)

        strategy_default = StrategyRegistry.get("test")
        strategy_custom = StrategyRegistry.get("test", config=custom_config)

        assert strategy_default is not strategy_custom
        assert strategy_default is StrategyRegistry.get("test")  # Cached instance

    def test_get_unknown_strategy_raises_error(self):
        """Test that getting unknown strategy raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            StrategyRegistry.get("unknown")

        assert "Unknown strategy: unknown" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)

    def test_get_strategy_with_no_default_config(self):
        """Test getting strategy when no default config is registered."""
        StrategyRegistry.register("test", MockStrategy)
        strategy = StrategyRegistry.get("test")

        # Should create strategy with None config (or default dataclass)
        assert isinstance(strategy, MockStrategy)

    def test_list_strategies(self):
        """Test listing all registered strategies."""
        StrategyRegistry.register("momentum", MockStrategy)
        StrategyRegistry.register("breakout", MockStrategy)
        StrategyRegistry.register("mean_reversion", MockStrategy)

        strategies = StrategyRegistry.list_strategies()

        assert len(strategies) == 3
        assert "momentum" in strategies
        assert "breakout" in strategies
        assert "mean_reversion" in strategies

    def test_list_strategies_empty(self):
        """Test listing strategies when none registered."""
        strategies = StrategyRegistry.list_strategies()

        assert strategies == []

    def test_get_default_config(self):
        """Test getting default config for a strategy."""
        config = StrategyConfig(name="test", stop_loss_pct=0.05)
        StrategyRegistry.register("test", MockStrategy, default_config=config)

        default_config = StrategyRegistry.get_default_config("test")

        assert default_config is config
        assert default_config.stop_loss_pct == 0.05

    def test_get_default_config_none_when_not_set(self):
        """Test getting default config when none was registered."""
        StrategyRegistry.register("test", MockStrategy)

        default_config = StrategyRegistry.get_default_config("test")

        assert default_config is None

    def test_multiple_registrations_override(self):
        """Test that re-registering a strategy overwrites previous."""

        class StrategyA(BaseStrategy):
            def __init__(self, config=None):
                self.config = config or StrategyConfig()

            def evaluate_entry(self, signal, context, agent_recommendation=None):
                return EntryDecision(should_enter=False, reason="A")

            def evaluate_exit(self, position, signal, context):
                return ExitDecision(should_exit=False, reason="A")

        class StrategyB(BaseStrategy):
            def __init__(self, config=None):
                self.config = config or StrategyConfig()

            def evaluate_entry(self, signal, context, agent_recommendation=None):
                return EntryDecision(should_enter=False, reason="B")

            def evaluate_exit(self, position, signal, context):
                return ExitDecision(should_exit=False, reason="B")

        StrategyRegistry.register("test", StrategyA)
        StrategyRegistry.register("test", StrategyB)

        strategy = StrategyRegistry.get("test")
        entry_decision = strategy.evaluate_entry(
            {},
            MarketContext(
                vix=20.0,
                market_status="open",
                account_equity=100000.0,
                buying_power=100000.0,
                existing_positions=[],
                cooldown_tickers=[],
            ),
        )

        assert entry_decision.reason == "B"
