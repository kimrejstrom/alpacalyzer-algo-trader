"""
Backtesting framework for strategy validation and performance testing.

This module provides:
- Backtester: Core engine for running backtests against historical data
- BacktestResult: Results container with comprehensive metrics
- BacktestTrade: Individual trade tracking
- compare_strategies: Utility for comparing multiple strategies

Example:
    from datetime import datetime
    from alpacalyzer.backtesting import Backtester, compare_strategies
    from alpacalyzer.strategies.momentum import MomentumStrategy

    # Single strategy backtest
    strategy = MomentumStrategy()
    backtester = Backtester(strategy)

    result = backtester.run(
        ticker="AAPL",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
    )

    print(result.summary())

    # Compare strategies
    comparison = compare_strategies(
        strategies=[MomentumStrategy(), BreakoutStrategy()],
        ticker="AAPL",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
    )
    print(comparison)
"""

from alpacalyzer.backtesting.backtester import (
    Backtester,
    BacktestResult,
    BacktestTrade,
    compare_strategies,
)

__all__ = [
    "BacktestResult",
    "BacktestTrade",
    "Backtester",
    "compare_strategies",
]
