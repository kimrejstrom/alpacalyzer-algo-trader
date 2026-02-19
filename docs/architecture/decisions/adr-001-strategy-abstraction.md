# ADR-001: Strategy Abstraction

## Status

Accepted

## Context

The trading system needed a way to support multiple trading strategies (Momentum, Breakout, MeanReversion) with a common interface. Each strategy has different entry/exit criteria but should integrate with a unified execution engine.

## Decision

We implemented a Protocol-based strategy abstraction:

```python
from typing import Protocol

class TradingStrategy(Protocol):
    def analyze(self, ticker: str, data: pd.DataFrame) -> StrategySignal | None: ...
    def validate(self, signal: TradeSignal) -> ValidationResult: ...
```

## Rationale

1. **Protocol over ABC**: Python Protocols provide structural subtyping, allowing strategies to define their own base classes without forcing inheritance
2. **Single Responsibility**: Each strategy handles only its logic, not order execution
3. **Validation Flow**: Agent proposes → Strategy validates → Execution follows (never recalculates)
4. **Testability**: Strategies can be tested in isolation with mocked market data

## Consequences

- New strategies can be added by implementing the Protocol
- Strategies cannot modify agent-proposed values (only validate/reject)
- Each strategy maintains its own state and configuration
