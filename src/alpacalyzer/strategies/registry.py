"""
Strategy registry for managing available trading strategies.

This module provides a centralized registry for registering and retrieving
strategy implementations. It supports:
- Registration of strategy classes with optional default configs
- Strategy instantiation with custom or default configs
- Instance caching for singleton access (when no custom config)
- Listing available strategies
- Auto-registration of built-in strategies
"""

from typing import TYPE_CHECKING

from alpacalyzer.strategies.base import Strategy

if TYPE_CHECKING:
    from alpacalyzer.strategies.config import StrategyConfig
else:
    # Avoid circular import at runtime
    from alpacalyzer.strategies.config import StrategyConfig as _Config

    StrategyConfig = _Config


class StrategyRegistry:
    """
    Registry for available trading strategies.

    The registry maintains three class-level dictionaries:
    - _strategies: Maps strategy names to their classes
    - _instances: Caches singleton instances for strategies without custom configs
    - _default_configs: Stores default configs for each strategy

    Example:
        >>> StrategyRegistry.register("momentum", MomentumStrategy)
        >>> strategy = StrategyRegistry.get("momentum")
        >>> entry_decision = strategy.evaluate_entry(signal, context)
    """

    _strategies: dict[str, type[Strategy]] = {}
    _instances: dict[str, Strategy] = {}
    _default_configs: dict[str, StrategyConfig] = {}

    @classmethod
    def register(
        cls,
        name: str,
        strategy_class: type[Strategy],
        default_config: StrategyConfig | None = None,
    ) -> None:
        """
        Register a strategy class with optional default config.

        Args:
            name: Unique name for the strategy
            strategy_class: Strategy class implementing Strategy protocol
            default_config: Optional default configuration for this strategy

        Example:
            >>> config = StrategyConfig(name="momentum", stop_loss_pct=0.05)
            >>> StrategyRegistry.register("momentum", MomentumStrategy, config)
        """
        cls._strategies[name] = strategy_class
        if default_config:
            cls._default_configs[name] = default_config

    @classmethod
    def get(cls, name: str, config: StrategyConfig | None = None) -> Strategy:
        """
        Get or create a strategy instance.

        If no custom config is provided, returns a cached singleton instance.
        Otherwise, creates a new instance with the provided config.

        Args:
            name: Name of the registered strategy
            config: Optional custom configuration (uses default if None)

        Returns:
            Strategy instance

        Raises:
            ValueError: If strategy name is not registered

        Example:
            >>> # Get with default config (cached)
            >>> strategy = StrategyRegistry.get("momentum")
            >>>
            >>> # Get with custom config (new instance)
            >>> custom_config = StrategyConfig(stop_loss_pct=0.10)
            >>> strategy = StrategyRegistry.get("momentum", config=custom_config)
        """
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}. Available: {cls.list_strategies()}")

        # Return cached instance if no custom config
        if config is None and name in cls._instances:
            return cls._instances[name]

        # Create new instance
        use_config = config or cls._default_configs.get(name)
        instance = cls._strategies[name](use_config)

        # Cache instance if no custom config was provided
        if config is None:
            cls._instances[name] = instance

        return instance

    @classmethod
    def list_strategies(cls) -> list[str]:
        """
        List all registered strategy names.

        Returns:
            List of strategy names in registration order (sorted for consistency)
        """
        return sorted(cls._strategies.keys())

    @classmethod
    def get_default_config(cls, name: str) -> StrategyConfig | None:
        """
        Get the default config for a registered strategy.

        Args:
            name: Name of the registered strategy

        Returns:
            Default StrategyConfig if set, None otherwise
        """
        return cls._default_configs.get(name)


def _register_builtins() -> None:
    """
    Auto-register built-in strategies on module import.

    This function is called when the registry module is imported.
    It imports and registers all built-in strategies.

    Note: MomentumStrategy will be registered in issue #8.
    Additional strategies (breakout, mean_reversion, etc.) will be added later.
    """
    # Import and register built-in strategies here
    # from alpacalyzer.strategies.momentum import MomentumStrategy
    # StrategyRegistry.register("momentum", MomentumStrategy)

    # Future: breakout, mean_reversion, scalping, etc.
    pass


# Auto-register built-in strategies on import
_register_builtins()
