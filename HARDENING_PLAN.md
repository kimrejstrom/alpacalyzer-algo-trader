# Alpacalyzer Hardening & Improvement Plan

**Created**: January 20, 2026
**Status**: Ready for Implementation
**Priority**: Critical - Financial logic bugs must be fixed before production use

---

## Executive Summary

This plan addresses critical financial logic bugs, architectural improvements, and code quality issues identified during post-migration analysis. The migration to modular architecture is complete, but production readiness requires fixing risk management bugs, clarifying decision flow, and adding missing features.

### Issue Breakdown

| Priority | Issue | Scope | Risk |
|----------|-------|-------|------|
| P0 | #67: Fix short position margin calculation | Risk Manager | **CRITICAL** - Incorrect position sizing |
| P0 | #68: Implement position sizing in BreakoutStrategy | Breakout Strategy | **HIGH** - Can't execute trades |
| P0 | #69: Clarify agent vs. strategy entry authority | All strategies | **HIGH** - Decision confusion |
| P1 | #70: Fetch real VIX in ExecutionEngine | ExecutionEngine | Medium - Hardcoded value |
| P1 | #71: Add ExecutionEngine state persistence | ExecutionEngine | Medium - Data loss on restart |
| P1 | #72: Optimize ExecutionEngine cycle performance | ExecutionEngine | Medium - API inefficiency |
| P2 | #73: Resolve bracket order vs. dynamic exit conflict | All strategies | Low - Dual exit paths |
| P2 | #74: Implement dynamic position sizing | Risk Manager | Low - Improvement |
| P2 | #75: Clean up unused code | Multiple | Low - Code hygiene |

---

## Context for Engineers

### What is Alpacalyzer?

Alpacalyzer is an AI-powered algorithmic trading platform that:
1. **Scans** multiple sources (Reddit, Stocktwits, Finviz) for trading opportunities
2. **Analyzes** using AI agents (technical, sentiment, value investors via GPT-4)
3. **Executes** trades through Alpaca Markets API with configurable strategies

### Key Architecture Concepts

```
┌─────────────────────────────────────────────────────────────┐
│ 1. OPPORTUNITY PIPELINE (pipeline/)                        │
│    ScannerRegistry → OpportunityAggregator                 │
│    - Aggregates opportunities from Reddit, social, Finviz │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. HEDGE FUND AGENTS (hedge_fund.py, agents/)             │
│    Technical → Sentiment → Quant → Value Investors         │
│    → Risk Manager → Portfolio Manager → Trading Strategist │
│    - LangGraph workflow with GPT-4                         │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. EXECUTION ENGINE (execution/engine.py)                 │
│    - Single loop: exits first, then entries                │
│    - Uses Strategy for entry/exit decisions                │
│    - Manages positions, cooldowns, orders                  │
└─────────────────────────────────────────────────────────────┘
```

### Critical Design Principle

**Agents provide trade setup (entry, stop, target, size) → Strategies validate technical filters → ExecutionEngine executes**

This is the **intended** flow (see issue #69 for current broken state).

### Testing Philosophy

- **Test-first**: Write test BEFORE implementation
- **Mock external APIs**: Alpaca, OpenAI must always be mocked
- **Use fixtures**: `conftest.py` has automatic OpenAI mocking
- **Save test output**: Run once, save to file, analyze - never run full suite repeatedly

### Toolset

- **uv**: Package manager (`uv sync`, `uv run pytest`)
- **pytest**: Test framework
- **ruff**: Linting and formatting (`uv run ruff check .`, `uv run ruff format .`)
- **ty**: Type checking (`uv run ty check src`)

---

## Issue Details

### P0-Critical: Fix Short Position Margin Calculation

**GitHub Issue**: #67
**File**: `src/alpacalyzer/trading/risk_manager.py`
**Lines**: 96
**Risk**: CRITICAL - Incorrect position sizing for shorts, potential margin violations

#### Problem

```python
# Line 96 - WRONG
adjusted_buying_power = day_trading_buying_power * short_margin_requirement * safety_factor
```

This **multiplies** by margin requirement (0.5), which reduces buying power. It should **divide** to calculate actual short capacity.

#### Correct Logic

For short positions:
- Margin requirement = 50% (typical)
- If you have $10,000 buying power
- You can short up to $10,000 / 0.5 = $20,000 position value

#### Implementation Tasks

1. **Write test for margin calculation**
2. **Fix calculation**
3. **Add warning when approaching limits**
4. **Update documentation**

---

### P0-High: Implement Position Sizing in BreakoutStrategy

**GitHub Issue**: #68
**File**: `src/alpacalyzer/strategies/breakout.py`
**Lines**: 217, 222
**Risk**: HIGH - BreakoutStrategy can't execute trades (size=0)

#### Problem

```python
# Line 217 (long breakout)
return EntryDecision(
    suggested_size=0,  # ❌ NEVER SET
    ...
)

# Line 222 (short breakout)
return EntryDecision(
    suggested_size=0,  # ❌ NEVER SET
    ...
)
```

#### Solution

Call `self.calculate_position_size()` from `BaseStrategy` (already implemented).

---

### P0-High: Clarify Agent vs. Strategy Entry Authority

**GitHub Issue**: #69
**Files**: All strategies, `trading/trading_strategist.py`, `execution/engine.py`
**Risk**: HIGH - Decision confusion, double validation

#### Problem

Current state is **confused**:

1. TradingStrategist agent (GPT-4) generates: entry, stop_loss, target, quantity
2. MomentumStrategy.evaluate_entry() **re-validates** technical conditions
3. If strategy rejects, agent's setup is discarded
4. **BUT**: MomentumStrategy also calculates its own stop/target in some paths!

#### Intended Behavior (Per User Decision)

**"Agents decide, strategies must be clear what strategy is the trigger"**

This means:
- **Agents** provide trade setup (entry, stop, target, size)
- **Strategies** validate technical filters for their specific approach
- **Strategies MUST NOT** re-calculate entry/stop/target
- **Strategies** can reject if technical conditions don't match their style

Example:
- MomentumStrategy: Rejects if momentum is negative
- BreakoutStrategy: Rejects if no consolidation pattern detected
- MeanReversionStrategy: Rejects if RSI not oversold

#### Implementation Tasks

1. Document the authority flow
2. Remove redundant calculations from strategies
3. Update all strategies to use agent values
4. Add tests clarifying the flow

---

### P1: Fetch Real VIX in ExecutionEngine

**GitHub Issue**: #70
**File**: `src/alpacalyzer/execution/engine.py`
**Line**: 209
**Risk**: Medium - Hardcoded value affects market context

#### Problem

```python
# Line 209
vix = 20.0  # TODO: Fetch VIX from market data API
```

VIX is always 20.0, which means:
- Market always appears "calm"
- Strategies can't adjust for volatility regimes
- No correlation between VIX and actual market fear

#### Solution Options

1. Use existing `data/api.py` to fetch VIX (^VIX ticker)
2. Add VIX to `MarketContext` and update daily
3. Cache value to avoid repeated API calls

---

### P1: Add ExecutionEngine State Persistence

**GitHub Issue**: #71
**File**: `src/alpacalyzer/execution/engine.py`
**Risk**: Medium - Data loss on restart

#### Problem

ExecutionEngine stores all state in memory:
- `signal_queue`: Pending signals
- `positions`: Current positions
- `cooldowns`: Per-ticker cooldowns

On restart: **ALL LOST**

#### Solution

Add state persistence:
1. Serialize state to JSON file on each cycle
2. Load state on startup
3. Add `--reset-state` CLI flag to clear
4. Handle version mismatches

---

### P1: Optimize ExecutionEngine Cycle Performance

**GitHub Issue**: #72
**File**: `src/alpacalyzer/execution/engine.py`
**Lines**: 108-112, 122-126
**Risk**: Medium - API inefficiency

#### Problem

```python
# Creates NEW TechnicalAnalyzer for EVERY position on EVERY cycle
signals = TechnicalAnalyzer().analyze_stock(position.ticker)
```

This is expensive:
- API call for each position
- No caching
- Redundant calculations

#### Solution

1. Batch fetch technical signals
2. Cache signals with TTL
3. Reuse existing TechnicalAnalyzer instance
4. Consider parallel fetching for multiple tickers

---

### P2: Resolve Bracket Order vs. Dynamic Exit Conflict

**GitHub Issue**: #73
**Files**: All strategies, `execution/order_manager.py`
**Risk**: Low - Dual exit paths

#### Problem

Two exit mechanisms:
1. **Bracket orders**: Automatic stop/target via Alpaca
2. **Dynamic exits**: Strategy.evaluate_exit() in ExecutionEngine

**Conflict**: Which takes precedence?

Current state: Both can close positions. Unclear.

#### Solution

Define precedence:
1. Bracket orders are PRIMARY (automatic)
2. Dynamic exits are SECONDARY (manual override)
3. Document when each is used
4. Add logging for both paths

---

### P2: Implement Dynamic Position Sizing

**GitHub Issue**: #74
**File**: `src/alpacalyzer/trading/risk_manager.py`
**Line**: 72
**Risk**: Low - Improvement

#### Problem

```python
# Fixed 5% per position, regardless of volatility
position_limit = total_portfolio_value * 0.05
```

This doesn't account for:
- High volatility stocks (should size smaller)
- Low volatility stocks (could size larger)
- ATR-based risk
- Portfolio correlation

#### Solution

Implement dynamic sizing:
1. Use ATR to calculate risk per share
2. Size based on risk % of portfolio
3. Adjust for volatility regime (VIX)
4. Consider correlation with existing positions

---

### P2: Clean Up Unused Code

**GitHub Issue**: #75
**Files**: Multiple
**Risk**: Low - Code hygiene

#### Tasks

1. Remove commented code in `trading/trading_strategist.py:104-106`
2. Clean up unused imports
3. Remove dead code paths
4. Run linter to identify

---

## Implementation Order

### Week 1: Critical Fixes
1. **Issue #67**: Fix short margin calculation (P0)
2. **Issue #68**: BreakoutStrategy position sizing (P0)
3. **Issue #69**: Clarify agent vs. strategy authority (P0)

### Week 2: ExecutionEngine Improvements
4. **Issue #70**: Fetch real VIX (P1)
5. **Issue #71**: State persistence (P1)
6. **Issue #72**: Cycle optimization (P1)

### Week 3: Improvements & Cleanup
7. **Issue #73**: Bracket order conflict (P2)
8. **Issue #74**: Dynamic position sizing (P2)
9. **Issue #75**: Code cleanup (P2)

---

## Testing Strategy

### For Each Issue

1. **Write failing test FIRST**
   - Test the bug exists (for fixes)
   - Test the new behavior (for features)

2. **Implement minimal code**
   - Just enough to pass the test
   - No extra features

3. **Verify test passes**
   - `uv run pytest tests/test_xxx.py -v`

4. **Commit**
   - Single atomic change
   - Conventional commit message

5. **Run lint/typecheck**
   - `uv run ruff check .`
   - `uv run ruff format .`
   - `uv run ty check src`

### Integration Testing

After all P0/P1 issues complete:
- Run full test suite
- Manual paper trading validation
- Compare agent → strategy → execution flow

---

## Success Criteria

### P0 Issues (Must Have)
- [ ] Short positions calculate margin correctly
- [ ] BreakoutStrategy can execute trades
- [ ] Agent vs. strategy authority is clear and documented

### P1 Issues (Should Have)
- [ ] VIX reflects actual market conditions
- [ ] Engine state persists across restarts
- [ ] API calls are batched/cached

### P2 Issues (Nice to Have)
- [ ] Exit precedence is documented
- [ ] Position sizing adapts to volatility
- [ ] Code is clean and linted

---

## Rollback Plan

Each issue will be in a separate branch. If any issue causes problems:

1. Revert the specific commit
2. Document the issue
3. Create follow-up issue with findings

---

## Documentation Updates

After implementation:
1. Update `AGENTS.md` with clarified decision flow
2. Update `README.md` with new CLI flags (if any)
3. Update this file with completion status
4. Create "Architecture Decision Records" for major changes

---

**End of Implementation Plan**

**Next Step**: Create GitHub issues one by one following this plan.
