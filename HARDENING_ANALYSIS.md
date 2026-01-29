# Hardening Implementation Analysis

**Date**: January 29, 2026
**Purpose**: Deep analysis of hardening implementations - gaps, shortcomings, and future work

---

## Executive Summary

All 9 hardening issues are implemented, but several have **quality gaps** or **incomplete edge cases**. This document identifies specific shortcomings and recommends follow-up work.

---

## Issue-by-Issue Analysis

### Issue #67/#77: Short Position Margin Calculation ⚠️

**Implementation Quality**: 7/10

**What's Done**:

- Fixed division vs multiplication bug
- Test verifies correct calculation

**Gaps & Shortcomings**:

1. **Hardcoded margin requirement (0.5)**

   ```python
   short_margin_requirement = 0.5  # Line 189
   ```

   - Different brokers/account types have different requirements
   - Reg-T margin is 50%, but portfolio margin can be 15-25%
   - Should fetch from Alpaca API or make configurable

2. **No margin warning threshold**

   - Code logs when position usage > 80%, but no margin-specific warning
   - Should warn when approaching maintenance margin

3. **Missing overnight margin handling**
   - Day trading buying power vs overnight buying power not distinguished
   - Short positions held overnight have different requirements

**Recommended Follow-up**:

- [ ] Fetch margin requirement from Alpaca account info
- [ ] Add configurable margin safety thresholds
- [ ] Distinguish day vs overnight margin requirements

---

### Issue #68/#78: BreakoutStrategy Position Sizing ⚠️

**Implementation Quality**: 6/10

**What's Done**:

- Calls `calculate_position_size()` correctly
- Returns non-zero size

**Gaps & Shortcomings**:

1. **Position sizing ignores agent recommendation**

   ```python
   # Line 225 - Always calculates own size
   size = self.calculate_position_size(signal, context, context.buying_power)
   ```

   - Unlike MomentumStrategy, doesn't use `agent_recommendation.quantity`
   - Inconsistent with "agents propose, strategies validate" principle

2. **No ATR-based sizing**

   - Uses fixed risk percentage, not volatility-adjusted
   - `calculate_dynamic_position_size()` exists but isn't used

3. **`_position_data` stored in memory only**

   - Position data (stop_loss, target) lost on restart
   - Not integrated with state persistence

4. **False breakout tracking not persisted**
   - `_false_breakout_count` resets on restart
   - Could re-enter bad tickers immediately after restart

**Recommended Follow-up**:

- [ ] Add agent integration path (when agent_recommendation provided)
- [ ] Use ATR-based dynamic sizing
- [ ] Persist `_position_data` and `_false_breakout_count` in state

---

### Issue #69: Agent vs. Strategy Entry Authority ⚠️

**Implementation Quality**: 5/10

**What's Done**:

- MomentumStrategy correctly uses agent values
- Documentation added to Strategy protocol

**Gaps & Shortcomings**:

1. **BreakoutStrategy and MeanReversionStrategy don't integrate with agents**

   ```python
   # BreakoutStrategy - agent_recommendation is ignored
   agent_recommendation: "TradingStrategy | None" = None,  # Reserved for future
   ```

   - These strategies operate independently
   - No path to use agent recommendations even if provided

2. **No validation that agent values are used**

   - No test asserting strategies don't recalculate entry/stop/target
   - Could regress without detection

3. **Inconsistent behavior across strategies**

   - MomentumStrategy: Requires agent, uses agent values
   - BreakoutStrategy: Ignores agent, calculates own values
   - MeanReversionStrategy: Ignores agent, calculates own values
   - Confusing for users/operators

4. **Documentation says "reserved for future" but no tracking**
   - No GitHub issue tracking agent integration for Breakout/MeanReversion

**Recommended Follow-up**:

- [ ] Create issues for agent integration in Breakout/MeanReversion
- [ ] Add tests verifying agent values are used (not recalculated)
- [ ] Document the two modes clearly in AGENTS.md
- [ ] Consider a `requires_agent` property on Strategy protocol

---

### Issue #70/#80: Fetch Real VIX ✅

**Implementation Quality**: 9/10

**What's Done**:

- Fetches from yfinance
- 1-hour cache TTL
- Fallback to 25.0 on error
- Warning logged when VIX > 30

**Minor Gaps**:

1. **Fallback value (25.0) is arbitrary**

   - 25.0 is "elevated but not extreme"
   - Could use historical average (~19) or last known value

2. **No VIX regime classification**

   - Just a number, no interpretation
   - Could add: "low" (<15), "normal" (15-20), "elevated" (20-30), "high" (>30)

3. **Cache not shared across processes**
   - If running multiple instances, each fetches independently

**Recommended Follow-up**:

- [ ] Consider using last known value as fallback instead of 25.0
- [ ] Add VIX regime classification for logging/decisions

---

### Issue #71/#81: State Persistence ✅

**Implementation Quality**: 8/10

**What's Done**:

- Saves/loads signal_queue, positions, cooldowns, orders
- Version checking for migrations
- `--reset-state` CLI flag
- Comprehensive tests

**Minor Gaps**:

1. **No automatic backup before overwrite**

   - If save fails mid-write, state file could be corrupted
   - Should write to temp file then rename

2. **No state file rotation**

   - Single file, no history
   - Can't recover from bad state without manual intervention

3. **Strategy-specific data not persisted**

   - BreakoutStrategy's `_position_data` and `_false_breakout_count`
   - MeanReversionStrategy's entry times (for max_hold_hours)

4. **No compression**
   - State file could grow large with many signals/positions
   - JSON is verbose

**Recommended Follow-up**:

- [ ] Add atomic write (temp file + rename)
- [ ] Add state file backup/rotation
- [ ] Extend state persistence to strategy-specific data

---

### Issue #72/#82: Signal Caching ✅

**Implementation Quality**: 9/10

**What's Done**:

- TTL-based caching
- Single TechnicalAnalyzer instance
- Cache cleared at cycle start
- 20 comprehensive tests

**Minor Gaps**:

1. **No batch fetching**

   - Original issue mentioned "batch fetch for all tickers"
   - Still fetches one ticker at a time (just cached)

2. **No parallel fetching**

   - Original issue mentioned "parallel fetching"
   - Sequential fetching, just with caching

3. **Cache not shared across entry/exit processing**
   - Cache is cleared at cycle start
   - If same ticker in both entry and exit, fetched twice

**Recommended Follow-up**:

- [ ] Consider batch API calls if TechnicalAnalyzer supports it
- [ ] Don't clear cache at cycle start, let TTL handle expiration

---

### Issue #73: Bracket Order vs. Dynamic Exit ✅

**Implementation Quality**: 9/10

**What's Done**:

- Comprehensive documentation in engine.py
- Clear precedence rule: bracket orders primary, dynamic exits secondary
- `has_bracket_order` flag on TrackedPosition
- Logging for both paths

**Minor Gaps**:

1. **`has_bracket_order` not synced from broker**

   - Set to True by default
   - If bracket order is canceled externally, flag not updated
   - Could miss dynamic exit opportunities

2. **No event for bracket order fills**
   - Dynamic exits emit ExitTriggeredEvent
   - Bracket order fills don't emit events (broker handles)
   - Incomplete audit trail

**Recommended Follow-up**:

- [ ] Sync `has_bracket_order` from broker order status
- [ ] Consider webhook/polling for bracket order fill events

---

### Issue #74: Dynamic Position Sizing ✅

**Implementation Quality**: 8/10

**What's Done**:

- ATR-based sizing
- VIX adjustment
- Max position cap
- Fallback to fixed sizing

**Gaps**:

1. **Not used by all strategies**

   - `calculate_dynamic_position_size()` exists in risk_manager.py
   - MomentumStrategy uses agent's quantity (doesn't call it)
   - BreakoutStrategy uses `calculate_position_size()` from BaseStrategy (different function!)
   - MeanReversionStrategy uses `calculate_position_size()` from BaseStrategy

2. **Two different sizing functions**

   ```python
   # risk_manager.py
   def calculate_dynamic_position_size(ticker, portfolio_equity, vix, ...)

   # strategies/base.py
   def calculate_position_size(self, signal, context, max_amount)
   ```

   - Confusing which to use
   - BaseStrategy's version is simpler (no ATR/VIX)

3. **No correlation adjustment**
   - Original issue mentioned "consider correlation with existing positions"
   - Not implemented

**Recommended Follow-up**:

- [ ] Consolidate sizing functions (one source of truth)
- [ ] Have strategies use dynamic sizing from risk_manager
- [ ] Add correlation-based position limit reduction

---

### Issue #75: Code Cleanup ✅

**Implementation Quality**: 10/10

**What's Done**:

- Removed commented code
- Linter passes
- No unused imports

**No gaps identified.**

---

## Summary: Priority Follow-up Work

### High Priority (Should Fix)

| Issue | Gap                                             | Impact                  |
| ----- | ----------------------------------------------- | ----------------------- |
| #68   | BreakoutStrategy ignores agent recommendation   | Inconsistent behavior   |
| #69   | No agent integration for Breakout/MeanReversion | Feature incomplete      |
| #74   | Two different sizing functions                  | Confusing, inconsistent |
| #71   | Strategy-specific data not persisted            | Data loss on restart    |

### Medium Priority (Should Consider)

| Issue | Gap                                        | Impact          |
| ----- | ------------------------------------------ | --------------- |
| #67   | Hardcoded margin requirement               | Inflexible      |
| #73   | `has_bracket_order` not synced from broker | Stale state     |
| #71   | No atomic write for state file             | Corruption risk |
| #72   | No batch/parallel fetching                 | Performance     |

### Low Priority (Nice to Have)

| Issue | Gap                       | Impact                 |
| ----- | ------------------------- | ---------------------- |
| #70   | VIX regime classification | Better logging         |
| #71   | State file rotation       | Recovery options       |
| #74   | Correlation adjustment    | Better risk management |

---

## New GitHub Issues Created

| Issue                                                                     | Title                                          | Priority |
| ------------------------------------------------------------------------- | ---------------------------------------------- | -------- |
| [#95](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/95)   | Consolidate position sizing functions          | P1       |
| [#96](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/96)   | Add agent integration to BreakoutStrategy      | P1       |
| [#97](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/97)   | Add agent integration to MeanReversionStrategy | P1       |
| [#98](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/98)   | Persist strategy-specific state                | P1       |
| [#99](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/99)   | Sync bracket order status from broker          | P2       |
| [#100](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/100) | Fetch margin requirement from Alpaca           | P2       |

---

**End of Analysis**
