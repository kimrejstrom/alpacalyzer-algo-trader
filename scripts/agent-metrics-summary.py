#!/usr/bin/env python3
"""
Agent Metrics Summary Script

Parses recent log files and outputs structured JSON with:
- LLM call count, latency, token usage, cost per agent
- Trade execution metrics (fills, rejects, slippage)
- Error rates by component
- Last run timestamp and duration
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MetricsSummary:
    """Aggregated metrics from log files."""

    llm_metrics: dict[str, Any] = field(default_factory=dict)
    trade_metrics: dict[str, Any] = field(default_factory=dict)
    error_metrics: dict[str, Any] = field(default_factory=dict)
    last_run: dict[str, Any] = field(default_factory=dict)


def parse_log_file(file_path: Path, metrics: MetricsSummary) -> None:
    """Parse a single log file and extract metrics."""

    if not file_path.exists():
        return

    try:
        content = file_path.read_text()
    except Exception:
        return

    lines = content.split("\n")

    for line in lines:
        parse_llm_metrics(line, metrics)
        parse_trade_metrics(line, metrics)
        parse_error_metrics(line, metrics)
        parse_run_info(line, metrics)


def parse_llm_metrics(line: str, metrics: MetricsSummary) -> None:
    """Parse LLM-related metrics from log line."""

    llm_metrics = metrics.llm_metrics

    if "LLM" in line or "GPT" in line or "API" in line:
        llm_metrics.setdefault("call_count", 0)
        llm_metrics["call_count"] += 1

        latency_match = re.search(r"latency[=:]?\s*(\d+\.?\d*)\s*ms", line, re.IGNORECASE)
        if latency_match:
            llm_metrics.setdefault("total_latency_ms", 0)
            llm_metrics["total_latency_ms"] += float(latency_match.group(1))

        tokens_match = re.search(r"tokens[=:]?\s*(\d+)", line, re.IGNORECASE)
        if tokens_match:
            llm_metrics.setdefault("total_tokens", 0)
            llm_metrics["total_tokens"] += int(tokens_match.group(1))

        cost_match = re.search(r"cost[=:]?\s*\$?(\d+\.?\d*)", line, re.IGNORECASE)
        if cost_match:
            llm_metrics.setdefault("total_cost", 0.0)
            llm_metrics["total_cost"] += float(cost_match.group(1))

    if "agent" in line.lower() and "call" in line.lower():
        agent_match = re.search(r"(\w+Agent)", line)
        if agent_match:
            agent_name = agent_match.group(1)
            llm_metrics.setdefault("by_agent", {}).setdefault(agent_name, 0)
            llm_metrics["by_agent"][agent_name] += 1


def parse_trade_metrics(line: str, metrics: MetricsSummary) -> None:
    """Parse trade execution metrics from log line."""

    trade_metrics = metrics.trade_metrics

    if "ORDER_FILLED" in line or "Filled" in line:
        trade_metrics.setdefault("fills", 0)
        trade_metrics["fills"] += 1

        qty_match = re.search(r"qty[=:]?\s*(\d+)", line, re.IGNORECASE)
        if qty_match:
            trade_metrics.setdefault("total_filled_qty", 0)
            trade_metrics["total_filled_qty"] += int(qty_match.group(1))

    if "ORDER_REJECTED" in line or "Rejected" in line:
        trade_metrics.setdefault("rejects", 0)
        trade_metrics["rejects"] += 1

        reason_match = re.search(r"reason[=:]?\s*['\"]?([^'\"\\n]+)", line, re.IGNORECASE)
        if reason_match:
            trade_metrics.setdefault("reject_reasons", []).append(reason_match.group(1).strip())

    if "POSITION_OPENED" in line or "Entry" in line:
        trade_metrics.setdefault("entries", 0)
        trade_metrics["entries"] += 1

    if "POSITION_CLOSED" in line or "Exit" in line:
        trade_metrics.setdefault("exits", 0)
        trade_metrics["exits"] += 1

        pnl_match = re.search(r"pnl[=:]?\s*\$?(-?\d+\.?\d*)", line, re.IGNORECASE)
        if pnl_match:
            trade_metrics.setdefault("total_pnl", 0.0)
            trade_metrics["total_pnl"] += float(pnl_match.group(1))

    if "slippage" in line.lower():
        slippage_match = re.search(r"slippage[=:]?\s*\$?(\d+\.?\d*)", line, re.IGNORECASE)
        if slippage_match:
            trade_metrics.setdefault("slippage_total", 0.0)
            trade_metrics["slippage_total"] += float(slippage_match.group(1))


def parse_error_metrics(line: str, metrics: MetricsSummary) -> None:
    """Parse error metrics from log line."""

    error_metrics = metrics.error_metrics

    if "ERROR" in line or "Error" in line or "Exception" in line:
        error_metrics.setdefault("total_errors", 0)
        error_metrics["total_errors"] += 1

        if "Rate limit" in line:
            error_metrics.setdefault("by_type", {}).setdefault("rate_limit", 0)
            error_metrics["by_type"]["rate_limit"] += 1

        if "API" in line:
            error_metrics.setdefault("by_type", {}).setdefault("api_error", 0)
            error_metrics["by_type"]["api_error"] += 1

        if "Order" in line:
            error_metrics.setdefault("by_type", {}).setdefault("order_error", 0)
            error_metrics["by_type"]["order_error"] += 1

        if "LLM" in line or "GPT" in line:
            error_metrics.setdefault("by_type", {}).setdefault("llm_error", 0)
            error_metrics["by_type"]["llm_error"] += 1

        component_match = re.search(r"(emitter|order_manager|position_tracker|cooldown_manager|strategy|scanner|agent)", line, re.IGNORECASE)
        if component_match:
            component = component_match.group(1).lower()
            error_metrics.setdefault("by_component", {}).setdefault(component, 0)
            error_metrics["by_component"][component] += 1


def parse_run_info(line: str, metrics: MetricsSummary) -> None:
    """Parse run information from log line."""

    run_info = metrics.last_run

    timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
    if timestamp_match and not run_info.get("last_timestamp"):
        run_info["last_timestamp"] = timestamp_match.group(1)

    duration_match = re.search(r"duration[=:]?\s*(\d+\.?\d*)\s*seconds?", line, re.IGNORECASE)
    if duration_match:
        run_info["last_duration_seconds"] = float(duration_match.group(1))

    cycle_match = re.search(r"Cycle.*complete", line, re.IGNORECASE)
    if cycle_match:
        run_info["last_cycle"] = timestamp_match.group(1) if timestamp_match else None


def calculate_summary_metrics(metrics: MetricsSummary) -> dict[str, Any]:
    """Calculate derived metrics and format output."""

    result = {
        "llm_metrics": {},
        "trade_metrics": {},
        "error_metrics": {},
        "last_run": {},
    }

    llm = metrics.llm_metrics
    if llm.get("call_count", 0) > 0:
        result["llm_metrics"] = {
            "call_count": llm.get("call_count", 0),
            "total_latency_ms": round(llm.get("total_latency_ms", 0), 2),
            "avg_latency_ms": round(llm.get("total_latency_ms", 0) / llm.get("call_count", 1), 2),
            "total_tokens": llm.get("total_tokens", 0),
            "total_cost_usd": round(llm.get("total_cost", 0), 4),
            "by_agent": llm.get("by_agent", {}),
        }

    trade = metrics.trade_metrics
    if trade:
        result["trade_metrics"] = {
            "fills": trade.get("fills", 0),
            "total_filled_qty": trade.get("total_filled_qty", 0),
            "rejects": trade.get("rejects", 0),
            "entries": trade.get("entries", 0),
            "exits": trade.get("exits", 0),
            "total_pnl": round(trade.get("total_pnl", 0), 2),
            "slippage_total": round(trade.get("slippage_total", 0), 2),
            "reject_reasons": trade.get("reject_reasons", [])[:10],
        }

    error = metrics.error_metrics
    if error:
        result["error_metrics"] = {
            "total_errors": error.get("total_errors", 0),
            "by_type": error.get("by_type", {}),
            "by_component": error.get("by_component", {}),
        }

    result["last_run"] = {
        "last_timestamp": metrics.last_run.get("last_timestamp"),
        "last_duration_seconds": metrics.last_run.get("last_duration_seconds"),
        "last_cycle": metrics.last_run.get("last_cycle"),
    }

    return result


def main() -> int:
    """Main entry point."""

    log_dir = Path("logs")
    metrics = MetricsSummary()

    log_files = [
        log_dir / "trading_logs.log",
        log_dir / "analytics_log.log",
    ]

    for log_file in log_files:
        parse_log_file(log_file, metrics)

    result = calculate_summary_metrics(metrics)

    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
