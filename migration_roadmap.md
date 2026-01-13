# Alpacalyzer Migration Plan: Strategy-First Architecture

> **Status**: 90% Complete → Final Cutover In Progress
> **Created**: January 2026
> **Last Assessment**: January 13, 2026
> **Target Completion**: Phase 6 (Clean Break) - See issues #60-#66

## Executive Summary

This document outlines a strategic refactoring of the Alpacalyzer Algo Trader to address architectural issues in the trading loop, entry/exit logic, and strategy management. The goal is to create a robust, flexible system that preserves existing strengths (agents, technical analysis, scanners) while fixing fundamental design problems.

---

## Migration Assessment (January 13, 2026)

### Current State

All five original migration phases have been implemented with working code and comprehensive test coverage (~125+ tests). The new architecture currently runs **in parallel** with the old `Trader` class via the `--new-engine` CLI flag.

**Decision**: Proceed with **clean break** - full cutover to `ExecutionEngine` with `trader.py` removal.

### Phase Completion Status

| Phase       | Description              | Status         | Issues           | Notes                                  |
| ----------- | ------------------------ | -------------- | ---------------- | -------------------------------------- |
| **Phase 1** | Strategy Abstraction     | ✅ Complete    | #4-#8 (closed)   | `strategies/` module with 3 strategies |
| **Phase 2** | Execution Engine         | ✅ Complete    | #9-#15 (closed)  | `execution/` module ready              |
| **Phase 3** | Structured Logging       | ✅ Complete    | #17-#20 (closed) | 15 event types, `emit_event()` wired   |
| **Phase 4** | Pipeline                 | ✅ Complete    | #21-#24 (closed) | `pipeline/` module ready               |
| **Phase 5** | Backtesting & Strategies | ✅ Complete    | #25-#28 (closed) | Backtester + 3 strategies              |
| **Phase 6** | Clean Break Cutover      | 🔄 In Progress | #60-#66 (open)   | Remove `trader.py`, full integration   |

### Phase 6: Clean Break Migration (NEW)

**Goal**: Remove `trader.py` entirely and make `ExecutionEngine` + `TradingOrchestrator` the only execution path.

| Issue                                                                   | Title                      | Status  | Depends On    |
| ----------------------------------------------------------------------- | -------------------------- | ------- | ------------- |
| [#60](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/60) | Create TradingOrchestrator | 🔲 Open | -             |
| [#61](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/61) | Create Scanner Adapters    | 🔲 Open | -             |
| [#62](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/62) | Enhance ExecutionEngine    | 🔲 Open | -             |
| [#63](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/63) | Rewrite CLI                | 🔲 Open | #60, #61, #62 |
| [#64](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/64) | Delete trader.py           | 🔲 Open | #63           |
| [#65](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/65) | Update Tests               | 🔲 Open | #64           |
| [#66](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/66) | Update Documentation       | 🔲 Open | #65           |

### Target Architecture (Post-Phase 6)

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPPORTUNITY PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│  ScannerRegistry                                                 │
│  ├── RedditScannerAdapter (wraps existing scanner)              │
│  └── SocialScannerAdapter (wraps existing scanner)              │
│              │                                                   │
│              ▼                                                   │
│  OpportunityAggregator                                           │
│  ├── Deduplication + scoring                                    │
│  └── Rate limiting                                               │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRADING ORCHESTRATOR (NEW)                     │
├─────────────────────────────────────────────────────────────────┤
│  TradingOrchestrator                                             │
│  ├── scan() → OpportunityAggregator                             │
│  ├── analyze() → Hedge Fund Agents (LangGraph)                  │
│  └── execute() → ExecutionEngine                                │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION ENGINE                             │
├─────────────────────────────────────────────────────────────────┤
│  ExecutionEngine (single loop, clear state)                      │
│  ├── SignalQueue: Pending signals from analysis                  │
│  ├── PositionTracker: Current positions + metadata              │
│  ├── CooldownManager: Per-ticker cooldowns                      │
│  └── OrderManager: Order submission + cancellation              │
│                                                                  │
│  Strategy (via StrategyRegistry)                                │
│  ├── MomentumStrategy                                            │
│  ├── BreakoutStrategy                                            │
│  └── MeanReversionStrategy                                       │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EVENT SYSTEM                                 │
├─────────────────────────────────────────────────────────────────┤
│  15 Structured JSON event types via EventEmitter                │
│  Handlers: Console, File (JSONL), Analytics                     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Changes in Phase 6

1. **New `TradingOrchestrator`** (`src/alpacalyzer/orchestrator.py`)

   - Replaces `Trader` class for pipeline coordination
   - Delegates all execution to `ExecutionEngine`
   - Clean separation: scanning → analysis → execution

2. **Scanner Adapters** (`src/alpacalyzer/scanners/adapters.py`)

   - Wrap existing scanners to implement `BaseScanner` protocol
   - Enable use with `ScannerRegistry` and `OpportunityAggregator`

3. **Enhanced `OrderManager`**

   - Full order cancellation logic (from `trader.py`)
   - Position closing with bracket order handling
   - Cooldown integration

4. **CLI Rewrite**

   - Remove `--new-engine` flag (new engine becomes default)
   - Remove `Trader` import entirely
   - Use `TradingOrchestrator` + `ExecutionEngine`

5. **Delete `trader.py`**
   - 686-line monolith removed
   - All functionality migrated to new modules

### Files to Delete

- `src/alpacalyzer/trading/trader.py` (686 lines)

### Files to Create

- `src/alpacalyzer/orchestrator.py` (~150 lines)
- `src/alpacalyzer/scanners/adapters.py` (~200 lines)

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Architecture Vision](#architecture-vision)
3. [Migration Phases](#migration-phases)
4. [Detailed Implementation Plan](#detailed-implementation-plan)
5. [Risk Mitigation](#risk-mitigation)
6. [Success Metrics](#success-metrics)
7. [GitHub Issues](#github-issues)

---

## Current State Analysis

### ✅ Components to Preserve

| Component           | Location                                         | Reason to Keep                   |
| ------------------- | ------------------------------------------------ | -------------------------------- |
| Agent Architecture  | `src/alpacalyzer/agents/`                        | Well-designed LangGraph workflow |
| Technical Analysis  | `src/alpacalyzer/analysis/technical_analysis.py` | Solid TA-Lib implementation      |
| Data Models         | `src/alpacalyzer/data/models.py`                 | Good Pydantic models             |
| Scanners            | `src/alpacalyzer/scanners/`                      | Functional multi-source scanning |
| Alpaca Client       | `src/alpacalyzer/trading/alpaca_client.py`       | Clean API integration            |
| Hedge Fund Workflow | `src/alpacalyzer/hedge_fund.py`                  | Good DAG structure               |

### ❌ Components to Refactor

| Component    | Location                             | Problem                                       |
| ------------ | ------------------------------------ | --------------------------------------------- |
| Trading Loop | `src/alpacalyzer/trading/trader.py`  | 576-line monolith with mixed responsibilities |
| Entry Logic  | `trader.py:check_entry_conditions()` | Hardcoded thresholds, not configurable        |
| Exit Logic   | `trader.py:check_exit_conditions()`  | Rigid rules, no strategy customization        |
| Scheduler    | `src/alpacalyzer/cli.py`             | Multiple overlapping loops                    |
| Logging      | `src/alpacalyzer/utils/logger.py`    | Scattered, inconsistent format                |

### Key Problems Identified

1. **Monolithic Trader Class**: The `Trader` class handles scanning, analysis, execution, and monitoring in one place
2. **Hardcoded Strategy Logic**: Entry/exit conditions use fixed thresholds (0.7 ratio, 1.5% tolerance, etc.)
3. **No Strategy Abstraction**: Cannot easily test or compare different trading strategies
4. **Competing Scan Loops**: 4-hour, 4-minute, 5-minute, and 2-minute loops with unclear interaction
5. **Inconsistent Logging**: Mix of console logs, file logs, and analytics logs without structure

---

## Architecture Vision

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPPORTUNITY PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│  ScannerRegistry                                                 │
│  ├── RedditScanner                                               │
│  ├── SocialScanner (WSB + Stocktwits + Finviz)                  │
│  └── TechnicalScanner                                            │
│              │                                                   │
│              ▼                                                   │
│  OpportunityAggregator                                           │
│  ├── Deduplication                                               │
│  ├── Priority scoring                                            │
│  └── Rate limiting                                               │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ANALYSIS PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│  AgentWorkflow (LangGraph) ← EXISTING, PRESERVED                │
│  ├── Technical Analyst                                           │
│  ├── Sentiment Agent                                             │
│  ├── Quant Agent                                                 │
│  ├── Value Investors (Graham, Buffett, Munger, etc.)            │
│  │           │                                                   │
│  │           ▼                                                   │
│  ├── Risk Manager                                                │
│  ├── Portfolio Manager                                           │
│  └── Signal Generator (replaces Trading Strategist)             │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     STRATEGY ENGINE (NEW)                        │
├─────────────────────────────────────────────────────────────────┤
│  StrategyRegistry                                                │
│  ├── MomentumStrategy                                            │
│  ├── BreakoutStrategy                                            │
│  ├── MeanReversionStrategy                                       │
│  └── [Custom strategies via config]                              │
│                                                                  │
│  Each Strategy implements:                                       │
│  • should_enter(signal, context) -> bool                        │
│  • should_exit(position, signal) -> bool                        │
│  • calculate_size(signal, available) -> int                     │
│  • get_order_params() -> OrderParams                            │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION ENGINE (NEW)                       │
├─────────────────────────────────────────────────────────────────┤
│  ExecutionEngine (single loop, clear state)                      │
│  ├── SignalQueue: Pending signals from analysis                  │
│  ├── PositionTracker: Current positions + metadata              │
│  ├── CooldownManager: Per-ticker cooldowns                      │
│  └── OrderManager: Order submission + tracking                   │
│                                                                  │
│  Loop cycle:                                                     │
│  1. Process exits (protect capital first)                       │
│  2. Process entries (new positions)                             │
│  3. Update state                                                 │
│  4. Emit events                                                  │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EVENT SYSTEM (NEW)                           │
├─────────────────────────────────────────────────────────────────┤
│  Structured JSON events for all actions:                         │
│  • SCAN_COMPLETE: {tickers: [...], source: "reddit"}            │
│  • SIGNAL_GENERATED: {ticker, action, strategy, confidence}     │
│  • ENTRY_TRIGGERED: {ticker, strategy, price, quantity}         │
│  • EXIT_TRIGGERED: {ticker, reason, pnl}                        │
│  • ORDER_FILLED: {ticker, side, quantity, price}                │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
src/alpacalyzer/
├── __init__.py
├── cli.py                    # Simplified CLI entry point
├── config.py                 # Centralized configuration
│
├── scanners/                 # ✅ PRESERVE (minor refactor)
│   ├── __init__.py
│   ├── base.py              # Scanner protocol (NEW)
│   ├── registry.py          # Scanner registration (NEW)
│   ├── reddit_scanner.py
│   ├── social_scanner.py
│   ├── finviz_scanner.py
│   ├── stocktwits_scanner.py
│   └── wsb_scanner.py
│
├── agents/                   # ✅ PRESERVE
│   ├── __init__.py
│   ├── agents.py
│   ├── technicals_agent.py
│   ├── sentiment_agent.py
│   ├── quant_agent.py
│   ├── fundamentals_agent.py
│   ├── ben_graham_agent.py
│   ├── bill_ackman_agent.py
│   ├── cathie_wood_agent.py
│   ├── charlie_munger.py
│   └── warren_buffet_agent.py
│
├── analysis/                 # ✅ PRESERVE
│   ├── __init__.py
│   ├── technical_analysis.py
│   └── eod_performance.py
│
├── strategies/              # 🆕 NEW MODULE
│   ├── __init__.py
│   ├── base.py              # Strategy protocol + base class
│   ├── config.py            # Strategy configuration models
│   ├── registry.py          # Strategy registration
│   ├── momentum.py          # Momentum strategy implementation
│   ├── breakout.py          # Breakout strategy implementation
│   └── mean_reversion.py    # Mean reversion strategy
│
├── execution/               # 🆕 NEW MODULE (replaces trader.py)
│   ├── __init__.py
│   ├── engine.py            # Main execution loop
│   ├── signal_queue.py      # Signal queue management
│   ├── position_tracker.py  # Position state management
│   ├── cooldown.py          # Cooldown management
│   └── order_manager.py     # Order submission + tracking
│
├── pipeline/                # 🆕 NEW MODULE
│   ├── __init__.py
│   ├── aggregator.py        # Opportunity aggregation
│   └── scheduler.py         # Unified scheduling
│
├── events/                  # 🆕 NEW MODULE
│   ├── __init__.py
│   ├── models.py            # Event type definitions
│   ├── emitter.py           # Event emission
│   └── handlers.py          # Event handlers (logging, etc.)
│
├── data/                    # ✅ PRESERVE
│   ├── __init__.py
│   ├── api.py
│   ├── cache.py
│   └── models.py
│
├── trading/                 # ✅ PRESERVE (simplified)
│   ├── __init__.py
│   ├── alpaca_client.py
│   ├── risk_manager.py
│   ├── portfolio_manager.py
│   └── yfinance_client.py
│
├── graph/                   # ✅ PRESERVE
│   ├── __init__.py
│   └── state.py
│
├── gpt/                     # ✅ PRESERVE
│   ├── __init__.py
│   └── call_gpt.py
│
└── utils/                   # ✅ PRESERVE (enhance logging)
    ├── __init__.py
    ├── logger.py            # Enhanced with structured logging
    ├── cache_utils.py
    ├── display.py
    ├── progress.py
    └── scheduler.py
```

---

## Migration Phases

### Phase 1: Strategy Abstraction (Foundation)

**Effort**: Medium | **Impact**: High | **Risk**: Low

Create the strategy abstraction layer without changing existing behavior.

**Deliverables**:

- `Strategy` protocol/base class
- `StrategyConfig` dataclass
- `StrategyRegistry` for registration
- `MomentumStrategy` (extracted from current logic)
- Unit tests for strategy evaluation

### Phase 2: Execution Engine (Core)

**Effort**: High | **Impact**: High | **Risk**: Medium

Replace the monolithic `Trader` class with a clean execution engine.

**Deliverables**:

- `ExecutionEngine` with single loop
- `SignalQueue` for pending signals
- `PositionTracker` for state management
- `CooldownManager` for rate limiting
- `OrderManager` for order handling
- Integration tests

### Phase 3: Structured Event Logging

**Effort**: Low | **Impact**: Medium | **Risk**: Low

Unify logging with structured JSON events.

**Deliverables**:

- Event type models (Pydantic)
- `EventEmitter` class
- Migration of existing log calls
- EOD analyzer compatibility

### Phase 4: Opportunity Pipeline

**Effort**: Medium | **Impact**: Medium | **Risk**: Low

Create unified opportunity aggregation from scanners.

**Deliverables**:

- `Scanner` protocol
- `ScannerRegistry`
- `OpportunityAggregator`
- Unified scheduling

### Phase 5: Additional Strategies & Backtesting

**Effort**: High | **Impact**: High | **Risk**: Medium

Add new strategies and backtesting capability.

**Deliverables**:

- `BreakoutStrategy`
- `MeanReversionStrategy`
- Backtesting framework
- Strategy performance comparison

---

## Detailed Implementation Plan

### Phase 1: Strategy Abstraction

#### 1.1 Create Strategy Base Classes

```python
# src/alpacalyzer/strategies/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.data.models import TradingStrategy


@dataclass
class StrategyConfig:
    """Configuration for a trading strategy."""
    name: str
    description: str = ""

    # Position sizing
    max_position_pct: float = 0.05  # Max 5% of portfolio per position

    # Risk management
    stop_loss_pct: float = 0.03     # 3% stop loss
    target_pct: float = 0.09        # 9% target (3:1 R:R)
    trailing_stop: bool = False
    trailing_stop_pct: float = 0.02

    # Entry filters
    min_confidence: float = 70.0
    min_ta_score: float = 0.6
    min_momentum: float = -5.0

    # Exit filters
    exit_momentum_threshold: float = -15.0
    exit_score_threshold: float = 0.3

    # Cooldown
    cooldown_hours: int = 3

    # Additional parameters
    params: dict = field(default_factory=dict)


@dataclass
class MarketContext:
    """Current market conditions for strategy evaluation."""
    vix: float
    market_status: str  # "open", "pre-market", "after-hours", "closed"
    account_equity: float
    buying_power: float
    existing_positions: list[str]
    cooldown_tickers: list[str]


@dataclass
class EntryDecision:
    """Result of entry evaluation."""
    should_enter: bool
    reason: str
    suggested_size: int = 0
    entry_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0


@dataclass
class ExitDecision:
    """Result of exit evaluation."""
    should_exit: bool
    reason: str
    urgency: str = "normal"  # "normal", "urgent", "immediate"


@runtime_checkable
class Strategy(Protocol):
    """Protocol defining the strategy interface."""

    config: StrategyConfig

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: TradingStrategy | None = None
    ) -> EntryDecision:
        """Evaluate if entry conditions are met."""
        ...

    def evaluate_exit(
        self,
        position: "TrackedPosition",
        signal: TradingSignals,
        context: MarketContext
    ) -> ExitDecision:
        """Evaluate if exit conditions are met."""
        ...

    def calculate_position_size(
        self,
        signal: TradingSignals,
        context: MarketContext,
        max_amount: float
    ) -> int:
        """Calculate the number of shares to trade."""
        ...


class BaseStrategy(ABC):
    """Base class with common strategy logic."""

    def __init__(self, config: StrategyConfig):
        self.config = config

    @abstractmethod
    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: TradingStrategy | None = None
    ) -> EntryDecision:
        pass

    @abstractmethod
    def evaluate_exit(
        self,
        position: "TrackedPosition",
        signal: TradingSignals,
        context: MarketContext
    ) -> ExitDecision:
        pass

    def calculate_position_size(
        self,
        signal: TradingSignals,
        context: MarketContext,
        max_amount: float
    ) -> int:
        """Default position sizing based on config."""
        price = signal["price"]
        if price <= 0:
            return 0

        # Max position value based on portfolio percentage
        max_position_value = context.account_equity * self.config.max_position_pct

        # Use the smaller of position limit and available funds
        available = min(max_position_value, max_amount)

        return int(available / price)

    def _check_basic_filters(
        self,
        signal: TradingSignals,
        context: MarketContext
    ) -> tuple[bool, str]:
        """Check basic entry filters common to all strategies."""

        # Market must be open
        if context.market_status != "open":
            return False, f"Market is {context.market_status}"

        # Check minimum TA score
        if signal["score"] < self.config.min_ta_score:
            return False, f"TA score {signal['score']:.2f} below minimum {self.config.min_ta_score}"

        # Check momentum
        if signal["momentum"] < self.config.min_momentum:
            return False, f"Momentum {signal['momentum']:.1f}% below minimum {self.config.min_momentum}%"

        # Check if already in position
        if signal["symbol"] in context.existing_positions:
            return False, f"Already have position in {signal['symbol']}"

        # Check cooldown
        if signal["symbol"] in context.cooldown_tickers:
            return False, f"{signal['symbol']} is in cooldown"

        return True, "Basic filters passed"
```

#### 1.2 Implement Momentum Strategy

```python
# src/alpacalyzer/strategies/momentum.py
from alpacalyzer.strategies.base import (
    BaseStrategy, StrategyConfig, MarketContext,
    EntryDecision, ExitDecision
)
from alpacalyzer.analysis.technical_analysis import TradingSignals, TechnicalAnalyzer
from alpacalyzer.data.models import TradingStrategy


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based trading strategy.

    Enters on strong momentum with technical confirmation.
    Exits on momentum reversal or technical breakdown.
    """

    def __init__(self, config: StrategyConfig | None = None):
        if config is None:
            config = StrategyConfig(
                name="momentum",
                description="Momentum-based swing trading",
                stop_loss_pct=0.03,
                target_pct=0.09,
                min_confidence=70.0,
                min_ta_score=0.6,
                min_momentum=-3.0,
                exit_momentum_threshold=-15.0,
                exit_score_threshold=0.3,
            )
        super().__init__(config)
        self.ta = TechnicalAnalyzer()

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: TradingStrategy | None = None
    ) -> EntryDecision:
        """Evaluate momentum entry conditions."""

        # Check basic filters
        passed, reason = self._check_basic_filters(signal, context)
        if not passed:
            return EntryDecision(should_enter=False, reason=reason)

        # Momentum-specific checks
        momentum = signal["momentum"]
        score = signal["score"]
        price = signal["price"]

        # Need positive momentum for long entries
        if momentum < 0:
            return EntryDecision(
                should_enter=False,
                reason=f"Negative momentum {momentum:.1f}% not suitable for momentum strategy"
            )

        # Check for breakout signals
        signals_list = signal["signals"]
        has_breakout = any("Breakout" in s for s in signals_list)

        # Higher score threshold if no breakout pattern
        required_score = 0.7 if not has_breakout else 0.6
        if score < required_score:
            return EntryDecision(
                should_enter=False,
                reason=f"Score {score:.2f} below required {required_score} (breakout: {has_breakout})"
            )

        # Check for weak technical signals
        weak_signals = self.ta.weak_technicals(signals_list, "buy")
        if weak_signals:
            return EntryDecision(
                should_enter=False,
                reason=f"Weak technical signals: {weak_signals}"
            )

        # Calculate entry parameters
        atr = signal["atr"]
        stop_loss = price - (atr * 1.5)  # 1.5 ATR stop
        target = price + (atr * 4.5)     # 3:1 R:R

        # Use agent recommendation if available
        if agent_recommendation:
            stop_loss = agent_recommendation.stop_loss
            target = agent_recommendation.target_price

        size = self.calculate_position_size(signal, context, context.buying_power)

        return EntryDecision(
            should_enter=True,
            reason=f"Momentum entry: score={score:.2f}, momentum={momentum:.1f}%",
            suggested_size=size,
            entry_price=price,
            stop_loss=stop_loss,
            target=target
        )

    def evaluate_exit(
        self,
        position: "TrackedPosition",
        signal: TradingSignals,
        context: MarketContext
    ) -> ExitDecision:
        """Evaluate momentum exit conditions."""

        momentum = signal["momentum"]
        score = signal["score"]
        is_profitable = position.unrealized_pnl_pct > 0

        # Profitable position - let it run unless major reversal
        if is_profitable:
            if momentum < -15:
                return ExitDecision(
                    should_exit=True,
                    reason=f"Major momentum reversal: {momentum:.1f}%",
                    urgency="urgent"
                )
            if score < 0.3:
                return ExitDecision(
                    should_exit=True,
                    reason=f"Technical score collapse: {score:.2f}",
                    urgency="normal"
                )
            return ExitDecision(should_exit=False, reason="Profitable, holding")

        # Losing position - cut losses on confirmation
        weak_signals = self.ta.weak_technicals(signal["signals"], "buy")

        if momentum < -15 and weak_signals:
            return ExitDecision(
                should_exit=True,
                reason=f"Momentum drop {momentum:.1f}% with weak technicals",
                urgency="urgent"
            )

        if momentum < -25:
            return ExitDecision(
                should_exit=True,
                reason=f"Catastrophic momentum drop: {momentum:.1f}%",
                urgency="immediate"
            )

        if score < 0.3 and weak_signals:
            return ExitDecision(
                should_exit=True,
                reason=f"Score collapse {score:.2f} with weak technicals",
                urgency="normal"
            )

        return ExitDecision(should_exit=False, reason="Exit conditions not met")
```

#### 1.3 Strategy Registry

```python
# src/alpacalyzer/strategies/registry.py
from typing import Type
from alpacalyzer.strategies.base import Strategy, StrategyConfig


class StrategyRegistry:
    """Registry for available trading strategies."""

    _strategies: dict[str, Type[Strategy]] = {}
    _instances: dict[str, Strategy] = {}

    @classmethod
    def register(cls, name: str, strategy_class: Type[Strategy]) -> None:
        """Register a strategy class."""
        cls._strategies[name] = strategy_class

    @classmethod
    def get(cls, name: str, config: StrategyConfig | None = None) -> Strategy:
        """Get or create a strategy instance."""
        if name not in cls._strategies:
            raise ValueError(f"Unknown strategy: {name}")

        # Return cached instance if no custom config
        if config is None and name in cls._instances:
            return cls._instances[name]

        # Create new instance
        instance = cls._strategies[name](config)
        if config is None:
            cls._instances[name] = instance

        return instance

    @classmethod
    def list_strategies(cls) -> list[str]:
        """List all registered strategy names."""
        return list(cls._strategies.keys())


# Auto-register built-in strategies
def _register_builtins():
    from alpacalyzer.strategies.momentum import MomentumStrategy
    StrategyRegistry.register("momentum", MomentumStrategy)
    # Future strategies will be registered here

_register_builtins()
```

### Phase 2: Execution Engine

See GitHub issues for detailed implementation specs.

### Phase 3: Structured Event Logging

See GitHub issues for detailed implementation specs.

### Phase 4: Opportunity Pipeline

See GitHub issues for detailed implementation specs.

### Phase 5: Backtesting

See GitHub issues for detailed implementation specs.

---

## Risk Mitigation

### Technical Risks

| Risk                            | Likelihood | Impact | Mitigation                                 |
| ------------------------------- | ---------- | ------ | ------------------------------------------ |
| Breaking existing functionality | Medium     | High   | Comprehensive test suite, parallel running |
| Performance regression          | Low        | Medium | Benchmark before/after, profiling          |
| Data loss during migration      | Low        | High   | Git branches, no data migration required   |

### Process Risks

| Risk                 | Likelihood | Impact | Mitigation                              |
| -------------------- | ---------- | ------ | --------------------------------------- |
| Scope creep          | Medium     | Medium | Well-defined issues, phase gates        |
| Incomplete migration | Medium     | High   | Modular approach, each phase adds value |

### Mitigation Strategies

1. **Parallel Running**: Run old and new systems side-by-side in analyze mode
2. **Feature Flags**: Toggle between old/new execution paths
3. **Incremental Rollout**: Deploy strategies one at a time
4. **Automated Testing**: Unit tests for all strategy logic
5. **Manual Testing**: Paper trading validation before live

---

## Success Metrics

### Phase 1 Success Criteria

- [ ] Strategy protocol defined and documented
- [ ] MomentumStrategy extracts current behavior
- [ ] All existing entry/exit tests pass
- [ ] Strategy can be swapped via configuration

### Phase 2 Success Criteria

- [ ] ExecutionEngine runs single loop
- [ ] Position state correctly tracked
- [ ] Orders submitted correctly
- [ ] No regression in trade execution

### Phase 3 Success Criteria

- [ ] All log output in structured JSON
- [ ] EOD analyzer works with new format
- [ ] Log parsing is simpler
- [ ] No loss of information

### Phase 4 Success Criteria

- [ ] Single OpportunityAggregator
- [ ] Scanners conform to protocol
- [ ] Deduplication working
- [ ] Scheduling simplified

### Phase 5 Success Criteria

- [ ] Backtesting framework operational
- [ ] Strategy comparison possible
- [ ] Historical performance metrics
- [ ] New strategies tested

---

## Phase 6: Final Cutover (Proposed)

The migration architecture is complete. This phase covers the final transition from parallel systems to new-engine-only operation.

### 6.1 Production Validation (Weeks 1-3)

**Week 1: Analyze Mode Comparison**

- [ ] Run both engines in analyze mode simultaneously
- [ ] Compare entry/exit decisions between old and new
- [ ] Document any behavioral differences
- [ ] Fix critical discrepancies

**Week 2-3: Paper Trading Validation**

- [ ] Run new engine in paper trading mode
- [ ] Monitor for edge cases and errors
- [ ] Validate P&L calculations match expectations
- [ ] Test emergency rollback procedure

### 6.2 Cutover Execution

- [ ] Make `--new-engine` the default behavior
- [ ] Add `--legacy-engine` flag for rollback
- [ ] Update documentation and README.md
- [ ] Announce deprecation timeline for legacy code

### 6.3 Legacy Code Removal

After 30 days of successful new-engine operation:

- [ ] Remove `Trader.monitor_and_trade()` method
- [ ] Remove `Trader.check_entry_conditions()`
- [ ] Remove `Trader.check_exit_conditions()`
- [ ] Rename `Trader` class to `Orchestrator` (scanning only)
- [ ] Remove `--legacy-engine` flag
- [ ] Archive migration documentation

### 6.4 Documentation Updates

- [ ] Update README.md with current architecture
- [ ] Refresh docs/ folder with new module documentation
- [ ] Add strategy customization guide
- [ ] Document event schema for external integrations
- [ ] Update AGENTS.md with new workflow

---

## GitHub Issues

All migration issues are **CLOSED**. Issues are organized by phase and tracked in the repository: [View all migration issues](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues)

### Phase 1: Strategy Abstraction ✅ COMPLETE

- [x] [#4: Implement StrategyConfig Dataclass](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/4)
- [x] [#5: Create Strategy Protocol and Base Class](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/5)
- [x] [#7: Create Strategy Registry](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/7)
- [x] [#8: Extract MomentumStrategy from Current Logic](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/8)
- [x] [#6: Add Strategy Unit Tests](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/6)

### Phase 2: Execution Engine ✅ COMPLETE

- [x] [#13: Create ExecutionEngine Core](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/13)
- [x] [#9: Implement SignalQueue](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/9)
- [x] [#11: Implement PositionTracker](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/11)
- [x] [#12: Implement CooldownManager](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/12)
- [x] [#10: Implement OrderManager](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/10)
- [x] [#15: Migrate from Trader to ExecutionEngine](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/15)
- [x] [#14: Add Execution Integration Tests](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/14)

### Phase 3: Structured Logging ✅ COMPLETE

- [x] [#17: Define Event Models](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/17)
- [x] [#18: Migrate Existing Log Calls](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/18) (partial - hybrid approach)
- [x] [#19: Create EventEmitter](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/19)
- [x] [#20: Update EOD Analyzer](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/20)

### Phase 4: Opportunity Pipeline ✅ COMPLETE

- [x] [#21: Implement ScannerRegistry](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/21)
- [x] [#22: Unify Scheduling with PipelineScheduler](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/22)
- [x] [#23: Create OpportunityAggregator](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/23)
- [x] [#24: Create Scanner Protocol](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/24)

### Phase 5: Backtesting & New Strategies ✅ COMPLETE

- [x] [#25: Implement MeanReversionStrategy](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/25)
- [x] [#26: Implement BreakoutStrategy](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/26)
- [x] [#27: Create Backtesting Framework](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/27)
- [x] [#28: Add Strategy Performance Dashboard](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/28)

---

## Appendix

### A. Current Code Statistics (Updated January 13, 2026)

```
src/alpacalyzer/
├── trading/trader.py        685 lines (hybrid - uses new events + old logic)
├── hedge_fund.py            165 lines (preserved ✅)
├── cli.py                   206 lines (expanded with --new-engine flag)
├── analysis/technical_analysis.py  446 lines (preserved ✅)
├── agents/                  ~1500 lines total (preserved ✅)
├── scanners/                ~800 lines total (preserved + events ✅)
└── data/models.py           247 lines (preserved ✅)

NEW MODULES:
├── strategies/
│   ├── base.py              254 lines ✅
│   ├── config.py            219 lines ✅
│   ├── registry.py          153 lines ✅
│   ├── momentum.py          314 lines ✅
│   ├── breakout.py          393 lines ✅
│   └── mean_reversion.py    367 lines ✅
├── execution/
│   ├── engine.py            ~210 lines ✅
│   ├── signal_queue.py      154 lines ✅
│   ├── position_tracker.py  326 lines ✅
│   ├── cooldown.py          ~130 lines ✅
│   └── order_manager.py     244 lines ✅
├── events/
│   ├── models.py            220 lines ✅
│   └── emitter.py           178 lines ✅
├── pipeline/
│   ├── scanner_protocol.py  106 lines ✅
│   ├── registry.py          ~100 lines ✅
│   ├── aggregator.py        195 lines ✅
│   └── scheduler.py         167 lines ✅
└── backtesting/
    └── backtester.py        462 lines ✅

TOTAL NEW CODE: ~3,592 lines
TEST COVERAGE: ~125+ tests across 16 files
```

### B. Dependencies

Current dependencies that support the migration:

- `pydantic` - For data models and validation
- `langgraph` - For agent workflow (preserved)
- `alpaca-py` - For trading API (preserved)
- `pandas` - For data manipulation (preserved)
- `talib` - For technical analysis (preserved)

### C. Testing Strategy

1. **Unit Tests**: All strategy logic, event emission, position tracking
2. **Integration Tests**: Full execution cycle, order submission
3. **Paper Trading**: Validation in Alpaca paper trading environment
4. **A/B Testing**: Compare new vs old system performance

---

_This document will be updated as the migration progresses._
