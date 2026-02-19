# Observability Skill

Use this skill when you need to inspect runtime behavior, query LLM costs, trade execution metrics, or error rates.

## Running the Metrics Summary

To get a summary of recent runtime metrics:

```bash
python scripts/agent-metrics-summary.py
```

This outputs structured JSON with:

- **LLM metrics**: Call count, latency, token usage, cost per agent
- **Trade metrics**: Fills, rejects, slippage, entries, exits, PnL
- **Error metrics**: Error rates by type and component
- **Last run info**: Timestamp and duration

## Interpreting Output

### LLM Metrics

```json
{
  "llm_metrics": {
    "call_count": 42,
    "avg_latency_ms": 1250.5,
    "total_tokens": 15000,
    "total_cost_usd": 0.45,
    "by_agent": {
      "TechnicalsAgent": 15,
      "SentimentAgent": 12
    }
  }
}
```

Key indicators:

- High `call_count` with low tokens may indicate inefficient prompting
- High `avg_latency_ms` may indicate LLM provider issues
- `total_cost_usd` helps track API spend

### Trade Metrics

```json
{
  "trade_metrics": {
    "fills": 5,
    "rejects": 3,
    "entries": 8,
    "exits": 3,
    "total_pnl": 125.5,
    "reject_reasons": ["Rate limit", "Insufficient buying power"]
  }
}
```

Key indicators:

- High `rejects` / `entries` ratio may indicate strategy misalignment
- Check `reject_reasons` for actionable feedback
- `total_pnl` shows overall profitability

### Error Metrics

```json
{
  "error_metrics": {
    "total_errors": 10,
    "by_type": {
      "rate_limit": 5,
      "api_error": 3
    },
    "by_component": {
      "order_manager": 4,
      "emitter": 2
    }
  }
}
```

Key indicators:

- High `rate_limit` errors: Check API rate limits
- High `api_error` by component: Investigate that component
- Persistent errors require investigation

## Common Diagnostics

### High Error Rate

1. Run metrics summary: `python scripts/agent-metrics-summary.py`
2. Check `error_metrics.by_type` for patterns
3. Check `error_metrics.by_component` for affected components
4. Review recent log files in `logs/`

### High Reject Rate

1. Check `trade_metrics.reject_reasons`
2. Review strategy configuration in `.env`
3. Verify Alpaca account status and buying power

### LLM Cost Issues

1. Check `llm_metrics.total_cost_usd`
2. Review `llm_metrics.by_agent` for heavy users
3. Consider optimizing prompts for token efficiency

## Log Files

- `logs/trading_logs.log` - Main trading activity
- `logs/analytics_log.log` - Analytics and metrics
- `logs/eod/` - End-of-day reports

For detailed debugging, inspect raw log files directly.
