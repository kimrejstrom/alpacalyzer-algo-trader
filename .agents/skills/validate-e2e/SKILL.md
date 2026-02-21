---
name: "validate-e2e"
description: "Use this skill to validate changes end-to-end by running the app in dry-run mode and inspecting structured JSON output"
---

# Validate End-to-End Skill

## When to Use

After making changes to the trading pipeline (scanners, agents, strategies, execution), validate that the full flow still works by running a dry-run cycle.

## How to Validate

```bash
uv run alpacalyzer --analyze --dry-run --json 2>/dev/null
```

This runs one analysis cycle and outputs structured JSON to stdout:

```json
{
  "status": "ok",
  "mode": "dry_run",
  "tickers_scanned": ["AAPL", "TSLA", "NVDA"],
  "opportunities": 3,
  "strategies_generated": 2,
  "signals_queued": 2,
  "errors": []
}
```

## What to Check

1. `status` should be `"ok"` — any other value means something broke
2. `errors` should be empty — non-empty means a component failed
3. `opportunities` > 0 — if zero, scanners may be broken
4. `strategies_generated` > 0 — if zero, agents may be broken

## With Specific Tickers

```bash
uv run alpacalyzer --analyze --dry-run --json --tickers AAPL,MSFT 2>/dev/null
```

## Interpreting Failures

- `"status": "error"` with `"errors": ["scanner timeout"]` → Scanner issue
- `opportunities: 0` → Check scanner adapters and API keys
- `strategies_generated: 0` with `opportunities > 0` → Agent/LLM issue
- Any Python traceback on stderr → Code error (the `2>/dev/null` hides stderr; remove it to debug)

## Integration with CI

This is not wired into CI (it requires API keys). Use it locally after making pipeline changes.
