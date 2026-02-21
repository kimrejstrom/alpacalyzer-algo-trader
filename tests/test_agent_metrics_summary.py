"""Tests for agent-metrics-summary script reading structured events.jsonl."""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from agent_metrics_summary import summarize_events


@pytest.fixture
def events_dir(tmp_path):
    """Create a temporary logs directory with events.jsonl."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir


def write_events(events_dir: Path, events: list[dict]) -> Path:
    """Write events to a JSONL file."""
    jsonl_path = events_dir / "events.jsonl"
    with open(jsonl_path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
    return jsonl_path


def test_empty_events_file(events_dir):
    """Metrics summary handles empty events file gracefully."""
    write_events(events_dir, [])
    result = summarize_events(events_dir.parent)
    assert result["llm_metrics"] == {}
    assert result["trade_metrics"]["fills"] == 0
    assert result["error_metrics"]["total_errors"] == 0


def test_llm_call_metrics(events_dir):
    """LLM call events are aggregated correctly."""
    events = [
        {
            "event_type": "LLM_CALL",
            "timestamp": "2026-02-20T10:00:00Z",
            "agent": "TechnicalsAgent",
            "model": "claude-3.5-sonnet",
            "tier": "standard",
            "latency_ms": 1200.0,
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
            "cost_usd": 0.015,
        },
        {
            "event_type": "LLM_CALL",
            "timestamp": "2026-02-20T10:05:00Z",
            "agent": "SentimentAgent",
            "model": "llama-3.2-3b-instruct",
            "tier": "fast",
            "latency_ms": 300.0,
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
            "cost_usd": 0.002,
        },
        {
            "event_type": "LLM_CALL",
            "timestamp": "2026-02-20T10:10:00Z",
            "agent": "TechnicalsAgent",
            "model": "claude-3.5-sonnet",
            "tier": "standard",
            "latency_ms": 800.0,
            "prompt_tokens": 400,
            "completion_tokens": 150,
            "total_tokens": 550,
            "cost_usd": 0.012,
        },
    ]
    write_events(events_dir, events)
    result = summarize_events(events_dir.parent)

    llm = result["llm_metrics"]
    assert llm["call_count"] == 3
    assert llm["total_tokens"] == 1550
    assert llm["avg_latency_ms"] == pytest.approx(766.67, rel=0.01)
    assert llm["total_cost_usd"] == pytest.approx(0.029)
    assert llm["by_agent"]["TechnicalsAgent"] == 2
    assert llm["by_agent"]["SentimentAgent"] == 1


def test_trade_metrics(events_dir):
    """Trade events are aggregated correctly."""
    events = [
        {
            "event_type": "ORDER_FILLED",
            "timestamp": "2026-02-20T10:00:00Z",
            "ticker": "AAPL",
            "order_id": "o1",
            "client_order_id": "c1",
            "side": "buy",
            "quantity": 10,
            "filled_qty": 10,
            "avg_price": 150.0,
            "strategy": "momentum",
        },
        {
            "event_type": "ORDER_REJECTED",
            "timestamp": "2026-02-20T10:05:00Z",
            "ticker": "TSLA",
            "client_order_id": "c2",
            "reason": "Insufficient buying power",
        },
        {
            "event_type": "POSITION_OPENED",
            "timestamp": "2026-02-20T10:00:00Z",
            "ticker": "AAPL",
            "side": "long",
            "quantity": 10,
            "entry_price": 150.0,
            "strategy": "momentum",
            "order_id": "o1",
        },
        {
            "event_type": "POSITION_CLOSED",
            "timestamp": "2026-02-20T14:00:00Z",
            "ticker": "AAPL",
            "side": "long",
            "quantity": 10,
            "entry_price": 150.0,
            "exit_price": 155.0,
            "pnl": 50.0,
            "pnl_pct": 0.033,
            "hold_duration_hours": 4.0,
            "strategy": "momentum",
            "exit_reason": "target_hit",
        },
    ]
    write_events(events_dir, events)
    result = summarize_events(events_dir.parent)

    trade = result["trade_metrics"]
    assert trade["fills"] == 1
    assert trade["rejects"] == 1
    assert trade["entries"] == 1
    assert trade["exits"] == 1
    assert trade["total_pnl"] == pytest.approx(50.0)
    assert "Insufficient buying power" in trade["reject_reasons"]


def test_error_metrics(events_dir):
    """Error events are aggregated correctly."""
    events = [
        {
            "event_type": "ERROR",
            "timestamp": "2026-02-20T10:00:00Z",
            "error_type": "rate_limit",
            "component": "order_manager",
            "message": "Rate limit exceeded",
        },
        {
            "event_type": "ERROR",
            "timestamp": "2026-02-20T10:01:00Z",
            "error_type": "api_error",
            "component": "order_manager",
            "message": "API timeout",
        },
        {
            "event_type": "ERROR",
            "timestamp": "2026-02-20T10:02:00Z",
            "error_type": "rate_limit",
            "component": "emitter",
            "message": "Rate limit exceeded",
        },
    ]
    write_events(events_dir, events)
    result = summarize_events(events_dir.parent)

    errors = result["error_metrics"]
    assert errors["total_errors"] == 3
    assert errors["by_type"]["rate_limit"] == 2
    assert errors["by_type"]["api_error"] == 1
    assert errors["by_component"]["order_manager"] == 2
    assert errors["by_component"]["emitter"] == 1


def test_cycle_metrics(events_dir):
    """Cycle complete events provide last run info."""
    events = [
        {
            "event_type": "CYCLE_COMPLETE",
            "timestamp": "2026-02-20T10:00:00Z",
            "entries_evaluated": 5,
            "entries_triggered": 2,
            "exits_evaluated": 3,
            "exits_triggered": 1,
            "signals_pending": 4,
            "positions_open": 3,
            "duration_seconds": 12.5,
        },
        {
            "event_type": "CYCLE_COMPLETE",
            "timestamp": "2026-02-20T10:05:00Z",
            "entries_evaluated": 3,
            "entries_triggered": 1,
            "exits_evaluated": 2,
            "exits_triggered": 0,
            "signals_pending": 3,
            "positions_open": 4,
            "duration_seconds": 8.2,
        },
    ]
    write_events(events_dir, events)
    result = summarize_events(events_dir.parent)

    last_run = result["last_run"]
    assert last_run["last_timestamp"] == "2026-02-20T10:05:00Z"
    assert last_run["last_duration_seconds"] == 8.2
    assert last_run["total_cycles"] == 2


def test_mixed_events(events_dir):
    """All event types are handled together correctly."""
    events = [
        {
            "event_type": "LLM_CALL",
            "timestamp": "2026-02-20T10:00:00Z",
            "agent": "QuantAgent",
            "model": "claude-3.5-sonnet",
            "tier": "deep",
            "latency_ms": 2000.0,
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
            "cost_usd": 0.05,
        },
        {
            "event_type": "ORDER_FILLED",
            "timestamp": "2026-02-20T10:01:00Z",
            "ticker": "NVDA",
            "order_id": "o1",
            "client_order_id": "c1",
            "side": "buy",
            "quantity": 5,
            "filled_qty": 5,
            "avg_price": 800.0,
            "strategy": "breakout",
        },
        {
            "event_type": "SCAN_COMPLETE",
            "timestamp": "2026-02-20T10:00:00Z",
            "source": "reddit",
            "tickers_found": ["NVDA", "AAPL"],
            "duration_seconds": 3.5,
        },
    ]
    write_events(events_dir, events)
    result = summarize_events(events_dir.parent)

    assert result["llm_metrics"]["call_count"] == 1
    assert result["trade_metrics"]["fills"] == 1
    assert result["scan_metrics"]["total_scans"] == 1


def test_nonexistent_events_file(tmp_path):
    """Handles missing events.jsonl gracefully."""
    result = summarize_events(tmp_path)
    assert result["llm_metrics"] == {}
    assert result["trade_metrics"]["fills"] == 0


def test_malformed_json_lines_skipped(events_dir):
    """Malformed JSON lines are skipped without crashing."""
    jsonl_path = events_dir / "events.jsonl"
    with open(jsonl_path, "w") as f:
        f.write("not valid json\n")
        f.write(
            json.dumps(
                {
                    "event_type": "ORDER_FILLED",
                    "timestamp": "2026-02-20T10:00:00Z",
                    "ticker": "AAPL",
                    "order_id": "o1",
                    "client_order_id": "c1",
                    "side": "buy",
                    "quantity": 10,
                    "filled_qty": 10,
                    "avg_price": 150.0,
                    "strategy": "momentum",
                }
            )
            + "\n"
        )

    result = summarize_events(events_dir.parent)
    assert result["trade_metrics"]["fills"] == 1
