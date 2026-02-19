# Architecture Overview

## Domain Map

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPPORTUNITY PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│  ScannerRegistry                                                 │
│  ├── RedditScannerAdapter                                        │
│  └── SocialScannerAdapter                                        │
│              │                                                   │
│              ▼                                                   │
│  OpportunityAggregator                                           │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRADING ORCHESTRATOR                           │
├─────────────────────────────────────────────────────────────────┤
│  TradingOrchestrator                                             │
│  ├── scan() → OpportunityAggregator                             │
│  ├── analyze() → Hedge Fund Agents                              │
│  └── execute() → ExecutionEngine                                │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION ENGINE                             │
├─────────────────────────────────────────────────────────────────┤
│  ExecutionEngine                                                 │
│  ├── SignalQueue                                                 │
│  ├── PositionTracker                                            │
│  ├── CooldownManager                                            │
│  └── OrderManager                                                │
│                                                                  │
│  Strategy (via StrategyRegistry)                                │
│  ├── MomentumStrategy                                            │
│  ├── BreakoutStrategy                                            │
│  └── MeanReversionStrategy                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Package Layering

```
┌─────────────────────────────────────────┐
│           CLI (cli.py)                  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      Orchestrator (orchestrator.py)     │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌───────────────┐   ┌───────────────┐
│   Pipeline    │   │    Hedge      │
│   (scanners)  │   │    Fund       │
└───────────────┘   │  (agents)     │
        │           └───────────────┘
        ▼
┌───────────────┐   ┌───────────────┐
│  Execution    │   │   Strategies  │
│   Engine      │   │               │
└───────────────┘   └───────────────┘
        │                   │
        └─────────┬─────────┘
                  ▼
┌─────────────────────────────────────────┐
│          Trading (Alpaca Client)        │
└─────────────────────────────────────────┘
```

## Import Direction Rules

```
┌─────────────────────────────────────────────────────────────┐
│                      ALLOWED IMPORTS                        │
├─────────────────────────────────────────────────────────────┤
│  CLI → Orchestrator                                         │
│  Orchestrator → Pipeline, HedgeFund, Execution, Strategies │
│  Pipeline → Scanners, Events                               │
│  HedgeFund → Agents, LLM, Events                           │
│  Execution → Strategies, Trading, Events                   │
│  Strategies → Analysis, Events                             │
│  Agents → LLM, Prompts, Events                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     FORBIDDEN IMPORTS                       │
├─────────────────────────────────────────────────────────────┤
│  ✗ Lower layers cannot import upper layers                 │
│  ✗ Execution cannot import CLI                              │
│  ✗ Strategies cannot import Orchestrator                  │
│  ✗ Scanners cannot import Execution                        │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

| Component    | Location                          | Key Pattern           |
| ------------ | --------------------------------- | --------------------- |
| CLI Entry    | `src/alpacalyzer/cli.py`          | Command + scheduling  |
| Orchestrator | `src/alpacalyzer/orchestrator.py` | Pipeline coordination |
| Execution    | `src/alpacalyzer/execution/`      | Single loop engine    |
| Strategies   | `src/alpacalyzer/strategies/`     | Pluggable strategies  |
| Pipeline     | `src/alpacalyzer/pipeline/`       | Scanner aggregation   |
| Events       | `src/alpacalyzer/events/`         | Structured logging    |
| Hedge Fund   | `src/alpacalyzer/hedge_fund.py`   | DAG workflow          |
| Agents       | `src/alpacalyzer/agents/`         | Agent pattern         |
| Scanners     | `src/alpacalyzer/scanners/`       | Data collectors       |
| LLM          | `src/alpacalyzer/llm/`            | Abstraction layer     |

## Agent vs. Strategy Decision Authority

The trading system uses a two-tier decision model:

**Tier 1: Agent (GPT-4 via TradingStrategist)**

- Analyzes ticker from multiple perspectives
- Proposes optimal trade setup:
  - Entry point (price)
  - Stop loss
  - Take profit target
  - Position size (quantity)
  - Trade direction (long/short)
- Provides reasoning

**Tier 2: Trading Strategy**

- Validates that agent's setup fits strategy's philosophy
- Can REJECT if conditions don't match:
  - MomentumStrategy: Rejects negative momentum, weak technicals
  - BreakoutStrategy: Rejects no consolidation pattern
  - MeanReversionStrategy: Rejects not-oversold/overbought conditions
- MUST USE agent values for entry/stop/target/size (no recalculation)

> **Note**: Not all strategies currently accept agent recommendations. BreakoutStrategy and MeanReversionStrategy currently detect opportunities independently through technical analysis. Agent integration for these strategies is planned for a future enhancement. MomentumStrategy is the primary strategy that follows the agent-propose/validate model.

**Key Principle**

> Agents propose, strategies validate. Strategies never override agent's calculated trade parameters.

## Migration Context

All phases of the architecture migration are now complete:

- **Phase 1**: `strategies/` module with 3 strategies
- **Phase 2**: `execution/` module (ExecutionEngine, SignalQueue, PositionTracker, CooldownManager, OrderManager)
- **Phase 3**: `events/` module with structured JSON logging
- **Phase 4**: `pipeline/` module (ScannerRegistry, OpportunityAggregator)
- **Phase 5**: Backtesting framework and performance dashboard
- **Phase 6**: Clean break - `Trader` class removed, `TradingOrchestrator` is the entry point
