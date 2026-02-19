# ADR-002: Execution Engine Design

## Status

Accepted

## Context

The trading system needed a unified execution engine that could:

1. Process signals from multiple strategies
2. Manage position tracking across strategies
3. Handle order submission to Alpaca
4. Enforce cooldowns and risk limits

## Decision

We implemented a single-loop execution engine with dedicated components:

```
ExecutionEngine
├── SignalQueue      # Buffer incoming signals, deduplicate
├── PositionTracker # Track open positions across strategies
├── CooldownManager # Prevent rapid re-trading same ticker
└── OrderManager    # Submit/cancel orders, handle fills
```

The engine runs a single event loop that:

1. Processes incoming signals from the orchestrator
2. Checks cooldowns and existing positions
3. Validates against the appropriate strategy
4. Submits orders via OrderManager
5. Updates PositionTracker with results

## Rationale

1. **Single Loop**: Simpler mental model than async event-driven approaches
2. **Component Isolation**: Each component has a single responsibility
3. **Backpressure**: SignalQueue buffers to prevent overwhelming the execution
4. **Auditability**: All actions logged via the events system

## Consequences

- All execution flows through one loop (easy to trace)
- Cooldowns apply globally (prevents rapid trading)
- PositionTracker is source of truth for all positions
- OrderManager handles all Alpaca API interactions (easy to mock in tests)
