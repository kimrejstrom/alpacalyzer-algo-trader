---
name: "new-strategy"
description: "Use this skill ONLY when creating a new trading strategy (e.g., MeanReversion, Breakout). Do not use for agents or scanners."
---

# Scope Constraint

- Strategy files go in `src/alpacalyzer/strategies/{name}.py`
- Tests go in `tests/strategies/test_{name}.py`
- Strategies evaluate entry/exit conditions based on signals

# Placeholders

- `<strategy>` — lowercase (e.g., `mean_reversion`)
- `<Strategy>` — PascalCase (e.g., `MeanReversion`)

# Steps

## 1. Study the reference implementation

Read these files in order:

1. `src/alpacalyzer/strategies/base.py` — `Strategy` protocol, `BaseStrategy`, `EntryDecision`, `ExitDecision`
2. `src/alpacalyzer/strategies/config.py` — `StrategyConfig` dataclass
3. `src/alpacalyzer/strategies/momentum.py` — canonical implementation

Key concepts: strategies implement `evaluate_entry()` and `evaluate_exit()`. They receive `TradingSignals` + `MarketContext` and return decision objects. Agent recommendations are optional inputs.

## 2. Create strategy file

Copy `src/alpacalyzer/strategies/momentum.py` → `src/alpacalyzer/strategies/<strategy>.py` and modify:

- Config: create `DEFAULT_<STRATEGY>_CONFIG` with strategy-specific params
- `evaluate_entry()` — implement your entry logic. MUST include `stop_loss` in every `EntryDecision(should_enter=True)`
- `evaluate_exit()` — implement exit logic with urgency levels (`normal`, `urgent`, `immediate`)
- Use `self._check_basic_filters()` for standard guards (market open, cooldown, existing position)

## 3. Register strategy

Edit `src/alpacalyzer/strategies/registry.py` — add to `_register_builtins()`.

## 4. Write tests

Follow the pattern in `tests/strategies/test_momentum.py`:

- Test entry with bullish/bearish signals
- Test market closed, existing position, cooldown rejection
- Test position sizing stays within limits
- Test exit for profitable and losing positions
- Test catastrophic drop triggers immediate exit
- Test agent recommendation integration

## 5. Run and verify

```bash
uv run pytest tests/test_<strategy>_strategy.py -vv
uv run pytest tests/test_*_strategy.py  # regression
```

# Safety invariants

- Every `EntryDecision(should_enter=True)` MUST include `stop_loss`
- Exits are always processed before entries (engine invariant)
- Position size must not exceed `config.max_position_pct` of equity

# Reference files

| Purpose        | File                                     |
| -------------- | ---------------------------------------- |
| Base classes   | `src/alpacalyzer/strategies/base.py`     |
| Config         | `src/alpacalyzer/strategies/config.py`   |
| Reference impl | `src/alpacalyzer/strategies/momentum.py` |
| Registry       | `src/alpacalyzer/strategies/registry.py` |
| Test pattern   | `tests/strategies/test_momentum.py`      |
| Architecture   | `docs/architecture/overview.md`          |
