#!/usr/bin/env python3
"""
Agent Metrics Summary Script

Reads structured events from logs/events.jsonl and outputs aggregated JSON with:
- LLM metrics: call count, latency, token usage, cost per agent
- Trade metrics: fills, rejects, entries, exits, PnL
- Error metrics: error rates by type and component
- Scan metrics: scanner activity
- Last run info: timestamp and duration
"""

import json
import sys
from pathlib import Path
from typing import Any


def load_events(base_dir: Path) -> list[dict]:
    """Load events from events.jsonl, skipping malformed lines."""
    events_path = base_dir / "logs" / "events.jsonl"
    if not events_path.exists():
        return []

    events = []
    for line in events_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def summarize_events(base_dir: Path) -> dict[str, Any]:
    """Aggregate events into a structured metrics summary."""
    events = load_events(base_dir)

    llm_metrics: dict[str, Any] = {}
    trade_metrics: dict[str, Any] = {
        "fills": 0,
        "rejects": 0,
        "entries": 0,
        "exits": 0,
        "total_pnl": 0.0,
        "reject_reasons": [],
    }
    error_metrics: dict[str, Any] = {
        "total_errors": 0,
        "by_type": {},
        "by_component": {},
    }
    scan_metrics: dict[str, Any] = {"total_scans": 0, "by_source": {}}
    last_run: dict[str, Any] = {
        "last_timestamp": None,
        "last_duration_seconds": None,
        "total_cycles": 0,
    }

    for event in events:
        event_type = event.get("event_type")

        if event_type == "LLM_CALL":
            _aggregate_llm(event, llm_metrics)
        elif event_type == "ORDER_FILLED":
            trade_metrics["fills"] += 1
        elif event_type == "ORDER_REJECTED":
            trade_metrics["rejects"] += 1
            reason = event.get("reason")
            if reason:
                trade_metrics["reject_reasons"].append(reason)
        elif event_type == "POSITION_OPENED":
            trade_metrics["entries"] += 1
        elif event_type == "POSITION_CLOSED":
            trade_metrics["exits"] += 1
            trade_metrics["total_pnl"] += event.get("pnl", 0.0)
        elif event_type == "ERROR":
            _aggregate_error(event, error_metrics)
        elif event_type == "SCAN_COMPLETE":
            scan_metrics["total_scans"] += 1
            source = event.get("source", "unknown")
            scan_metrics["by_source"][source] = scan_metrics["by_source"].get(source, 0) + 1
        elif event_type == "CYCLE_COMPLETE":
            last_run["total_cycles"] += 1
            last_run["last_timestamp"] = event.get("timestamp")
            last_run["last_duration_seconds"] = event.get("duration_seconds")

    # Finalize LLM metrics
    if llm_metrics.get("call_count", 0) > 0:
        llm_metrics["avg_latency_ms"] = round(llm_metrics["_total_latency"] / llm_metrics["call_count"], 2)
        llm_metrics["total_cost_usd"] = round(llm_metrics.pop("_total_cost", 0.0), 4)
        del llm_metrics["_total_latency"]

    trade_metrics["total_pnl"] = round(trade_metrics["total_pnl"], 2)
    trade_metrics["reject_reasons"] = trade_metrics["reject_reasons"][:10]

    return {
        "llm_metrics": llm_metrics if llm_metrics.get("call_count") else {},
        "trade_metrics": trade_metrics,
        "error_metrics": error_metrics,
        "scan_metrics": scan_metrics,
        "last_run": last_run,
    }


def _aggregate_llm(event: dict, metrics: dict) -> None:
    """Aggregate a single LLM_CALL event."""
    metrics.setdefault("call_count", 0)
    metrics.setdefault("total_tokens", 0)
    metrics.setdefault("_total_latency", 0.0)
    metrics.setdefault("_total_cost", 0.0)
    metrics.setdefault("by_agent", {})

    metrics["call_count"] += 1
    metrics["total_tokens"] += event.get("total_tokens", 0)
    metrics["_total_latency"] += event.get("latency_ms", 0.0)
    metrics["_total_cost"] += event.get("cost_usd", 0.0) or 0.0

    agent = event.get("agent", "unknown")
    metrics["by_agent"][agent] = metrics["by_agent"].get(agent, 0) + 1


def _aggregate_error(event: dict, metrics: dict) -> None:
    """Aggregate a single ERROR event."""
    metrics["total_errors"] += 1

    error_type = event.get("error_type", "unknown")
    metrics["by_type"][error_type] = metrics["by_type"].get(error_type, 0) + 1

    component = event.get("component", "unknown")
    metrics["by_component"][component] = metrics["by_component"].get(component, 0) + 1


def main() -> int:
    """Main entry point."""
    base_dir = Path(".")
    result = summarize_events(base_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
