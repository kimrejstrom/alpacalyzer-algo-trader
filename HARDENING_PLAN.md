# Alpacalyzer Hardening & Improvement Plan

**Created**: January 20, 2026
**Status**: ✅ COMPLETE
**Last Updated**: January 29, 2026

---

## Executive Summary

All hardening issues have been successfully implemented and merged. The system is now production-ready with proper risk management, state persistence, and performance optimizations.

### Issue Summary

| Priority | Issue | Title | Status | Actual GitHub Issue |
|----------|-------|-------|--------|---------------------|
| P0 | #67 | Fix short position margin calculation | ✅ Closed | #77 |
| P0 | #68 | Implement position sizing in BreakoutStrategy | ✅ Closed | #78 |
| P0 | #69 | Clarify agent vs. strategy entry authority | ✅ Closed | Documented |
| P1 | #70 | Fetch real VIX in ExecutionEngine | ✅ Closed | #80 |
| P1 | #71 | Add ExecutionEngine state persistence | ✅ Closed | #81 |
| P1 | #72 | Optimize ExecutionEngine cycle performance | ✅ Closed | #82 |
| P2 | #73 | Resolve bracket order vs. dynamic exit conflict | ✅ Closed | Documented |
| P2 | #74 | Implement dynamic position sizing | ✅ Closed | Already implemented |
| P2 | #75 | Clean up unused code | ✅ Closed | Committed |

---

## Implemented Features

### P0-Critical: Short Position Margin Calculation (Issue #77)

**File**: `src/alpacalyzer/trading/risk_manager.py`

Fixed the margin calculation for short positions. Now correctly **divides** by margin requirement instead of multiplying:

```python
# CORRECT: Division gives proper short capacity
adjusted_buying_power = day_trading_buying_power / short_margin_requirement * safety_factor
```

**Test**: `tests/test_risk_manager.py::TestShortPositionMarginCalculation`

---

### P0-High: BreakoutStrategy Position Sizing (Issue #78)

**File**: `src/alpacalyzer/strategies/breakout.py`

BreakoutStrategy now properly calculates position size using `BaseStrategy.calculate_position_size()`:

```python
size = self.calculate_position_size(signal, context, context.buying_power)
```

**Tests**: `tests/strategies/test_breakout.py::TestBreakoutStrategyPositionSizing`

---

### P0-High: Agent vs. Strategy Entry Authority (Issue #69)

**Files**: All strategies, `src/alpacalyzer/strategies/base.py`

Documented the two authority models:

1. **MODE 1: AGENT-DRIVEN** (MomentumStrategy)
   - Agent provides: entry_point, stop_loss, target_price, quantity
   - Strategy validates: Technical conditions (momentum, score)
   - Strategy uses agent values directly, never recalculates

2. **MODE 2: STRATEGY-DRIVEN** (BreakoutStrategy, MeanReversionStrategy)
   - Strategy detects opportunities independently
   - Strategy calculates its own entry/stop/target/size
   - Agent integration reserved for future enhancement

---

### P1-Medium: Real VIX Fetching (Issue #80)

**Files**: `src/alpacalyzer/data/api.py`, `src/alpacalyzer/execution/engine.py`

VIX is now fetched from Yahoo Finance with caching:

```python
def get_vix(use_cache: bool = True) -> float | None:
    # Fetches ^VIX from yfinance
    # 1-hour cache TTL
    # Returns None on error (caller handles fallback)
```

**Tests**: `tests/test_data_api.py::TestGetVix`, `tests/test_execution_engine.py`

---

### P1-Medium: State Persistence (Issue #81)

**Files**: `src/alpacalyzer/execution/engine.py`, `src/alpacalyzer/execution/state.py`

ExecutionEngine now persists state to `.alpacalyzer-state.json`:

- `save_state()` - Called after each cycle
- `load_state()` - Called on startup
- `--reset-state` CLI flag to start fresh
- Version checking for state format migrations

**Tests**: `tests/test_execution/test_state_persistence*.py`

---

### P1-Medium: Signal Caching (Issue #82)

**File**: `src/alpacalyzer/execution/engine.py`

Technical signals are now cached with configurable TTL:

```python
@dataclass
class CachedSignal:
    signal: TradingSignals
    timestamp: float
    ttl: float  # Default 300 seconds

# Single TechnicalAnalyzer instance reused
self._ta = TechnicalAnalyzer()
```

**Tests**: `tests/execution/test_signal_cache.py` (20 tests)

---

### P2-Low: Bracket Order vs. Dynamic Exit Precedence (Issue #73)

**Files**: `src/alpacalyzer/execution/engine.py`, `src/alpacalyzer/execution/order_manager.py`

Documented the two-tier exit system:

1. **BRACKET ORDERS (Primary)**: OCO orders managed by Alpaca broker
2. **DYNAMIC EXITS (Secondary)**: `strategy.evaluate_exit()` for emergencies

**Precedence Rule**: When `has_bracket_order=True`, dynamic exits are SKIPPED.

---

### P2-Low: Dynamic Position Sizing (Issue #74)

**File**: `src/alpacalyzer/trading/risk_manager.py`

Already implemented via `calculate_dynamic_position_size()`:

- ATR-based risk calculation
- VIX adjustment (reduces size when VIX > 20)
- Max position cap (5% default)
- Fallback to fixed sizing when ATR unavailable

**Tests**: `tests/test_risk_manager.py::TestDynamicPositionSizing`

---

### P2-Low: Code Cleanup (Issue #75)

Removed commented-out code from:
- `src/alpacalyzer/agents/quant_agent.py`
- `src/alpacalyzer/trading/trading_strategist.py`

---

## Test Coverage

All hardening features have comprehensive test coverage:

| Feature | Test File | Tests |
|---------|-----------|-------|
| Margin Calculation | `test_risk_manager.py` | 14 |
| Position Sizing | `test_breakout.py` | 30 |
| VIX Fetching | `test_data_api.py`, `test_execution_engine.py` | 9 |
| State Persistence | `test_state_persistence*.py` | 10 |
| Signal Caching | `test_signal_cache.py` | 20 |

---

## Maintenance Notes

### Regular Tasks
1. Review financial calculations quarterly for accuracy
2. Validate P&L calculations against broker statements
3. Monitor order execution quality metrics
4. Run regression tests before major releases

### CLI Flags
- `--reset-state`: Clear persisted state and start fresh
- `--analyze`: Run in analyze mode (no real trades)

### State File
- Location: `.alpacalyzer-state.json` (git-ignored)
- Contains: signal_queue, positions, cooldowns, orders
- Version: `1.0.0`

---

## Conclusion

The hardening plan has been fully implemented, significantly improving the accuracy and reliability of the Alpacalyzer trading system. All 9 issues across 3 priority levels have been completed and merged.

**End of Implementation Plan**
