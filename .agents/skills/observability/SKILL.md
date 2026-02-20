---
name: "observability"
description: "Use this skill when you need to inspect runtime behavior, query LLM costs, trade execution metrics, or error rates"
---

# Observability Skill

## How It Works

All runtime metrics flow through the structured event system (`events.jsonl`). Every trading event, LLM call, and error is emitted as a typed Pydantic model via `emit_event()` and written as JSON lines to `logs/events.jsonl` by the `FileEventHandler`.

The metrics summary script reads this structured data directly — no regex parsing of free-text logs.

## Running the Metrics Summary

```bash
python scripts/agent_metrics_summary.py
```

This outputs structured JSON with:

- **LLM metrics**: Call count, latency, token usage, cost per agent
- **Trade metrics**: Fills, rejects, entries, exits, PnL
- **Error metrics**: Error rates by type and component
- **Scan metrics**: Scanner activity by source
- **Last run info**: Timestamp, duration, cycle count

## Event Types

| Event             | Source                            | Key Fields                                   |
| ----------------- | --------------------------------- | -------------------------------------------- |
| `LLM_CALL`        | `LLMClient.complete_structured()` | agent, model, tier, latency_ms, tokens, cost |
| `ORDER_FILLED`    | Trade update handler              | ticker, side, filled_qty, avg_price          |
| `ORDER_REJECTED`  | Trade update handler              | ticker, reason                               |
| `POSITION_OPENED` | Execution engine                  | ticker, side, entry_price, strategy          |
| `POSITION_CLOSED` | Execution engine                  | ticker, pnl, pnl_pct, exit_reason            |
| `ERROR`           | Any component                     | error_type, component, message               |
| `SCAN_COMPLETE`   | Scanners                          | source, tickers_found, duration              |
| `CYCLE_COMPLETE`  | Execution engine                  | entries/exits triggered, duration            |

## Interpreting Output

### LLM Metrics

```json
{
  "llm_metrics": {
    "call_count": 42,
    "total_tokens": 15000,
    "avg_latency_ms": 1250.5,
    "total_cost_usd": 0.45,
    "by_agent": {
      "TechnicalsAgent": 15,
      "SentimentAgent": 12
    }
  }
}
```

- High `call_count` with low tokens → inefficient prompting
- High `avg_latency_ms` → LLM provider issues
- `by_agent` → identify heavy consumers

### Trade Metrics

```json
{
  "trade_metrics": {
    "fills": 5,
    "rejects": 3,
    "entries": 8,
    "exits": 3,
    "total_pnl": 125.5,
    "reject_reasons": ["Insufficient buying power"]
  }
}
```

- High rejects/entries ratio → strategy misalignment
- Check `reject_reasons` for actionable feedback

### Error Metrics

```json
{
  "error_metrics": {
    "total_errors": 10,
    "by_type": { "rate_limit": 5, "api_error": 3 },
    "by_component": { "order_manager": 4, "emitter": 2 }
  }
}
```

## Emitting New Events

To add observability to a new component:

```python
from alpacalyzer.events import emit_event, ErrorEvent
from datetime import datetime, timezone

# Emit an error event
emit_event(ErrorEvent(
    timestamp=datetime.now(tz=timezone.utc),
    error_type="api_error",
    component="my_component",
    message="Something went wrong",
))
```

For LLM calls, pass `caller=` to `complete_structured()`:

```python
client.complete_structured(messages, MyModel, tier=LLMTier.STANDARD, caller="MyAgent")
```

## Log Files

- `logs/events.jsonl` - Structured event log (machine-readable, source of truth)
- `logs/trading_logs.log` - Human-readable trading activity
