# Plan: Issue #162 — Wire BreakoutStrategy and MeanReversionStrategy into agent-propose/validate model

## Goal

Update BreakoutStrategy and MeanReversionStrategy to properly validate agent-proposed trade parameters by rejecting setups where the agent's `trade_type` doesn't match the strategy's detected conditions.

## Acceptance Criteria

- [ ] `BreakoutStrategy.evaluate_entry()` validates that agent's trade_type matches breakout direction
- [ ] `BreakoutStrategy` rejects agent setups that don't match breakout criteria (no consolidation, no volume surge)
- [ ] `BreakoutStrategy` MUST USE agent values for entry/stop/target/size when accepting (no recalculation)
- [ ] `MeanReversionStrategy.evaluate_entry()` validates that agent's trade_type matches mean reversion direction
- [ ] `MeanReversionStrategy` rejects agent setups that don't match mean reversion criteria
- [ ] `MeanReversionStrategy` MUST USE agent values for entry/stop/target/size when accepting (no recalculation)
- [ ] Both strategies still work independently (without agent input) as fallback
- [ ] All existing tests pass
- [ ] New tests cover agent-propose/validate flow for both strategies

## Files to Modify

| File                                           | Change                                                                       |
| ---------------------------------------------- | ---------------------------------------------------------------------------- |
| `src/alpacalyzer/strategies/breakout.py`       | Add validation: reject agent trade_type mismatching breakout direction       |
| `src/alpacalyzer/strategies/mean_reversion.py` | Add validation: reject agent trade_type mismatching mean reversion direction |
| `tests/strategies/test_breakout.py`            | Add tests: agent trade_type mismatch rejection                               |
| `tests/strategies/test_mean_reversion.py`      | Add tests: agent trade_type mismatch rejection                               |

## Test Scenarios

| Scenario                                          | Expected                    |
| ------------------------------------------------- | --------------------------- |
| Breakout: agent says long, breakout is bullish    | Accept, use agent values    |
| Breakout: agent says short, breakout is bullish   | REJECT - direction mismatch |
| Breakout: agent says long, breakout is bearish    | REJECT - direction mismatch |
| MeanReversion: agent says long, signal oversold   | Accept, use agent values    |
| MeanReversion: agent says short, signal oversold  | REJECT - direction mismatch |
| MeanReversion: agent says long, signal overbought | REJECT - direction mismatch |

## Implementation Details

### BreakoutStrategy

- After detecting bullish breakout (price > resistance), validate `agent_recommendation.trade_type == "long"`
- After detecting bearish breakout (price < support), validate `agent_recommendation.trade_type == "short"`
- If mismatch: return `EntryDecision(should_enter=False, reason="Agent trade_type mismatch: agent proposed {type} but breakout is {direction}")`

### MeanReversionStrategy

- After detecting long conditions (RSI oversold, price below BB), validate `agent_recommendation.trade_type == "long"`
- After detecting short conditions (RSI overbought, price above BB), validate `agent_recommendation.trade_type == "short"`
- If mismatch: return `EntryDecision(should_enter=False, reason="Agent trade_type mismatch: agent proposed {type} but mean reversion signal is {direction}")`

## Risks

- None identified - this is a validation addition, not changing existing logic
