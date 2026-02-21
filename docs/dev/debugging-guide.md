# Hypothesis-Driven Debugging Guide

For complex bugs — especially trading logic issues where the wrong fix can cause financial loss — use this structured approach instead of trial-and-error.

## The Process

### Step 1: Read the Error, Form Hypotheses

Read the full error output. Don't jump to code. Form 2–3 hypotheses about what could cause this behavior.

Example: "Position opened without stop loss"

- H1: Strategy's `evaluate_entry()` returned `should_enter=True` without setting `stop_loss`
- H2: Agent proposed a stop loss but it was lost during `PendingSignal.from_strategy()` conversion
- H3: Stop loss was set but `OrderManager` didn't submit the stop order

### Step 2: Identify Evidence for Each Hypothesis

For each hypothesis, determine what evidence would confirm or deny it.

| Hypothesis | Confirming Evidence                                                     | Denying Evidence         |
| ---------- | ----------------------------------------------------------------------- | ------------------------ |
| H1         | `EntryDecision.stop_loss` is None in strategy output                    | `stop_loss` has a value  |
| H2         | `PendingSignal.stop_loss` is None but `EntryDecision.stop_loss` was set | Both have values         |
| H3         | `OrderManager` logs show no stop order submission                       | Stop order was submitted |

### Step 3: Add Targeted Instrumentation

Add logging or assertions at the specific points that distinguish hypotheses. Don't scatter print statements everywhere.

```python
# Targeted: log at the decision boundary
logger.info(f"entry decision | ticker={ticker} stop_loss={decision.stop_loss}")
```

### Step 4: Run Once, Analyze

Run the failing test or scenario exactly once. Save the output.

```bash
uv run pytest tests/test_specific.py -vv > debug-output.txt 2>&1
```

Read the output. Which hypotheses survived? Which were eliminated?

### Step 5: Fix the Confirmed Root Cause

Fix only the confirmed issue. Remove all instrumentation. Run the test again to verify.

## Trading-Specific Examples

### Position Sizing Bug

Symptoms: Positions are too large or too small.

Hypotheses:

1. `calculate_position_size()` receives wrong account balance
2. Risk percentage config is wrong
3. Price data is stale (yesterday's close instead of current)

Evidence to gather:

- Log `account.buying_power` at entry to `calculate_position_size()`
- Log the risk config values being used
- Compare `current_price` in the calculation vs actual market price

### Stop Loss Calculation Error

Symptoms: Stop loss triggers too early or too late.

Hypotheses:

1. Stop loss percentage applied to wrong base price
2. ATR calculation uses wrong period
3. Stop loss price not adjusted for bid/ask spread

Evidence to gather:

- Log `entry_price`, `stop_loss_pct`, and calculated `stop_loss` together
- Compare ATR period in config vs what's passed to the indicator
- Check if stop order uses limit vs market

### Signal Queue Starvation

Symptoms: Signals are added but never executed.

Hypotheses:

1. Signals expire before execution cycle runs
2. `SignalQueue.pop()` filters them out (wrong priority, duplicate ticker)
3. Execution cycle skips entries (exits-before-entries logic blocks them)

Evidence to gather:

- Log signal TTL and cycle timing
- Log `SignalQueue` size before and after `pop()`
- Log which phase of `run_cycle()` is reached

## Key Rule

Never guess. Instrument, observe, then fix. One run with targeted logging beats ten runs with random changes.
