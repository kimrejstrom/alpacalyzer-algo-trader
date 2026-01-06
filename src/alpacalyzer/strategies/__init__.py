"""
Trading strategies module.

This module provides a pluggable strategy abstraction layer for Alpacalyzer.
Strategies implement the Strategy protocol and can be used for entry/exit decisions.

Example:
    from alpacalyzer.strategies.momentum import MomentumStrategy
    from alpacalyzer.strategies.registry import StrategyRegistry

    # Get a strategy
    strategy = StrategyRegistry.get("momentum")

    # Use strategy for decisions
    entry_decision = strategy.evaluate_entry(signal, context)
"""

from alpacalyzer.strategies.base import (
    BaseStrategy,
    EntryDecision,
    ExitDecision,
    MarketContext,
    Strategy,
)

__all__ = [
    "BaseStrategy",
    "Strategy",
    "EntryDecision",
    "ExitDecision",
    "MarketContext",
]
