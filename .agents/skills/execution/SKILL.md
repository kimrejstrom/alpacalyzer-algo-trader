---
name: "execution"
description: "Use this skill ONLY when modifying the execution engine, signal queue, position tracker, cooldown manager, or order manager. Do not use for strategies or agents."
---

# Scope Constraint

- Execution files: `src/alpacalyzer/execution/`
- Tests: `tests/test_execution*.py`

# Architecture

```
ExecutionEngine
├── SignalQueue      — priority queue of pending signals
├── PositionTracker  — tracks open positions with P&L
├── CooldownManager  — rate limiting per ticker
└── OrderManager     — bracket orders (entry + stop + target)
```

# Key invariant

Exits are ALWAYS processed before entries. This protects capital.

# Steps

## 1. Study the execution cycle

Read `src/alpacalyzer/execution/engine.py`, focusing on `run_cycle()`:

1. Sync positions from broker
2. Process exits (capital protection first)
3. Process entries (new positions)
4. Update cooldowns
5. Emit summary event

## 2. Understand each component

| Component | File                                            | Key class                            |
| --------- | ----------------------------------------------- | ------------------------------------ |
| Engine    | `src/alpacalyzer/execution/engine.py`           | `ExecutionEngine`, `ExecutionConfig` |
| Signals   | `src/alpacalyzer/execution/signal_queue.py`     | `SignalQueue`, `PendingSignal`       |
| Positions | `src/alpacalyzer/execution/position_tracker.py` | `PositionTracker`, `TrackedPosition` |
| Cooldowns | `src/alpacalyzer/execution/cooldown.py`         | `CooldownManager`                    |
| Orders    | `src/alpacalyzer/execution/order_manager.py`    | `OrderManager`, `OrderParams`        |
| State     | `src/alpacalyzer/execution/state.py`            | Shared state models                  |

## 3. Make changes

Read the specific component file before modifying. Key patterns:

- `SignalQueue` uses heapq (lower priority number = processed first)
- `PositionTracker` uses dict for O(1) lookups, syncs from Alpaca each cycle
- `OrderManager` submits bracket orders (entry + stop loss + target)
- `analyze_mode=True` skips real order submission

## 4. Write tests

Follow patterns in existing execution tests. Always:

- Mock Alpaca API (never submit real orders in tests)
- Test with `analyze_mode=True`
- Test exit-before-entry invariant
- Test max_positions limit
- Test cooldown enforcement

## 5. Run and verify

```bash
uv run pytest tests/test_execution*.py -v
```

# Safety rules

- Always test with `analyze_mode=True` first
- Mock Alpaca API in all tests
- `config.max_positions` prevents over-trading
- Every entry must have stop_loss and target (bracket order)

# Reference files

| Purpose          | File                                            |
| ---------------- | ----------------------------------------------- |
| Engine           | `src/alpacalyzer/execution/engine.py`           |
| Signal queue     | `src/alpacalyzer/execution/signal_queue.py`     |
| Position tracker | `src/alpacalyzer/execution/position_tracker.py` |
| Cooldowns        | `src/alpacalyzer/execution/cooldown.py`         |
| Order manager    | `src/alpacalyzer/execution/order_manager.py`    |
| Architecture     | `docs/architecture/overview.md`                 |
