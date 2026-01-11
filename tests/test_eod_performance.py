"""Tests for EOD Performance Analyzer JSON event parsing."""

from zoneinfo import ZoneInfo

import pytest

from alpacalyzer.analysis.eod_performance import EODPerformanceAnalyzer

EET = ZoneInfo("Europe/Helsinki")


@pytest.fixture
def analyzer():
    """Create EOD analyzer instance."""
    return EODPerformanceAnalyzer()


def test_parse_event_line_valid_json(analyzer):
    """Test parsing valid JSON event line."""
    event_json = '{"event_type": "ORDER_FILLED", "timestamp": "2024-01-05T10:30:00Z", "ticker": "NVDA", "side": "buy", "quantity": 27, "filled_qty": 27, "avg_price": 179.87, "strategy": "momentum"}'

    result = analyzer.parse_event_line(event_json)

    assert result is not None
    assert result["event_type"] == "ORDER_FILLED"
    assert result["ticker"] == "NVDA"
    assert result["side"] == "buy"


def test_parse_event_line_non_json(analyzer):
    """Test parsing non-JSON line returns None."""
    line = "This is not a JSON line"

    result = analyzer.parse_event_line(line)

    assert result is None


def test_parse_event_line_empty_line(analyzer):
    """Test parsing empty line returns None."""
    result = analyzer.parse_event_line("")

    assert result is None


def test_parse_event_line_invalid_json(analyzer):
    """Test parsing invalid JSON line returns None."""
    line = '{"event_type": "ORDER_FILLED", invalid json'

    result = analyzer.parse_event_line(line)

    assert result is None


def test_parse_event_line_missing_event_type(analyzer):
    """Test parsing JSON without event_type returns None."""
    line = '{"ticker": "NVDA", "side": "buy"}'

    result = analyzer.parse_event_line(line)

    assert result is None


def test_parse_event_line_not_dict(analyzer):
    """Test parsing JSON array returns None."""
    line = '["event_type", "ORDER_FILLED"]'

    result = analyzer.parse_event_line(line)

    assert result is None


def test_load_events_from_file(tmp_path, analyzer):
    """Test loading events from a JSONL file."""
    log_file = tmp_path / "events.jsonl"

    event1_json = '{"event_type": "ORDER_FILLED", "timestamp": "2024-01-05T10:30:00Z", "ticker": "NVDA", "side": "buy", "quantity": 27, "filled_qty": 27, "avg_price": 179.87, "strategy": "momentum"}'
    event2_json = (
        '{"event_type": "ENTRY_TRIGGERED", "timestamp": "2024-01-05T10:35:00Z", '
        '"ticker": "AAPL", "strategy": "momentum", "side": "long", '
        '"quantity": 100, "entry_price": 150.00, "stop_loss": 145.50, '
        '"target": 163.50, "reason": "Golden cross"}'
    )

    with open(log_file, "w") as f:
        f.write(event1_json + "\n")
        f.write(event2_json + "\n")

    events = analyzer.load_events(str(log_file))

    assert len(events) == 2
    assert events[0]["event_type"] == "ORDER_FILLED"
    assert events[0]["ticker"] == "NVDA"
    assert events[1]["event_type"] == "ENTRY_TRIGGERED"
    assert events[1]["ticker"] == "AAPL"


def test_load_events_filters_non_json(tmp_path, analyzer):
    """Test that load_events filters out non-JSON lines."""
    log_file = tmp_path / "events.jsonl"

    event_json = '{"event_type": "ORDER_FILLED", "timestamp": "2024-01-05T10:30:00Z", "ticker": "NVDA", "side": "buy", "quantity": 27, "filled_qty": 27, "avg_price": 179.87, "strategy": "momentum"}'

    with open(log_file, "w") as f:
        f.write("Some non-JSON line\n")
        f.write(event_json + "\n")
        f.write("Another non-JSON line\n")

    events = analyzer.load_events(str(log_file))

    assert len(events) == 1
    assert events[0]["event_type"] == "ORDER_FILLED"


def test_load_events_nonexistent_file(analyzer):
    """Test loading from non-existent file returns empty list."""
    events = analyzer.load_events("/nonexistent/path/events.jsonl")

    assert events == []


def test_parse_log_with_json_events(tmp_path, analyzer):
    """Test parse_log with JSON event format."""
    log_file = tmp_path / "events.jsonl"

    entry_json = (
        '{"event_type": "ENTRY_TRIGGERED", "timestamp": "2024-01-05T10:30:00Z", '
        '"ticker": "AAPL", "strategy": "momentum", "side": "long", '
        '"quantity": 100, "entry_price": 150.00, "stop_loss": 145.50, '
        '"target": 163.50, "reason": "Golden cross"}'
    )
    exit_json = (
        '{"event_type": "EXIT_TRIGGERED", "timestamp": "2024-01-05T14:30:00Z", '
        '"ticker": "AAPL", "strategy": "momentum", "side": "long", '
        '"quantity": 100, "entry_price": 150.00, "exit_price": 162.00, '
        '"pnl": 1200.0, "pnl_pct": 0.08, "hold_duration_hours": 4.0, '
        '"reason": "Target reached", "urgency": "normal"}'
    )
    order_json = (
        '{"event_type": "ORDER_FILLED", "timestamp": "2024-01-05T10:35:00Z", '
        '"ticker": "AAPL", "order_id": "12345", "client_order_id": "client_123", '
        '"side": "buy", "quantity": 100, "filled_qty": 100, '
        '"avg_price": 150.25, "strategy": "momentum"}'
    )

    with open(log_file, "w") as f:
        f.write(entry_json + "\n")
        f.write(exit_json + "\n")
        f.write(order_json + "\n")

    analyzer.log_path = str(log_file)
    decisions = analyzer.parse_log()

    assert len(decisions) == 2  # ENTRY and EXIT events
    assert decisions[0].ticker == "AAPL"
    assert decisions[0].action == "BUY"
    assert decisions[1].action == "EXIT_LONG"


def test_parse_log_filters_by_date_with_json(tmp_path, analyzer):
    """Test parse_log filters by target date with JSON events."""
    log_file = tmp_path / "events.jsonl"

    today_json = (
        '{"event_type": "ENTRY_TRIGGERED", "timestamp": "2024-01-05T10:30:00Z", '
        '"ticker": "AAPL", "strategy": "momentum", "side": "long", '
        '"quantity": 100, "entry_price": 150.00, "stop_loss": 145.50, '
        '"target": 163.50, "reason": "Entry"}'
    )
    yesterday_json = (
        '{"event_type": "ENTRY_TRIGGERED", "timestamp": "2024-01-04T10:30:00Z", '
        '"ticker": "TSLA", "strategy": "momentum", "side": "long", '
        '"quantity": 50, "entry_price": 200.00, "stop_loss": 190.00, '
        '"target": 220.00, "reason": "Entry"}'
    )

    with open(log_file, "w") as f:
        f.write(today_json + "\n")
        f.write(yesterday_json + "\n")

    analyzer.log_path = str(log_file)
    from datetime import date

    decisions = analyzer.parse_log(target_date_eet=date(2024, 1, 5))

    assert len(decisions) == 1
    assert decisions[0].ticker == "AAPL"


def test_detect_log_format_json(tmp_path, analyzer):
    """Test log format detection for JSON events."""
    log_file = tmp_path / "events.jsonl"

    with open(log_file, "w") as f:
        f.write('{"event_type": "ORDER_FILLED", "ticker": "AAPL"}\n')

    fmt = analyzer._detect_log_format(str(log_file))
    assert fmt == "json"


def test_detect_log_format_legacy(tmp_path, analyzer):
    """Test log format detection for legacy format."""
    log_file = tmp_path / "analytics.log"

    with open(log_file, "w") as f:
        f.write("[EXECUTION] Ticker: AAPL, Side: BUY (DEBUG - 2024-01-05 10:30:00,000)\n")

    fmt = analyzer._detect_log_format(str(log_file))
    assert fmt == "legacy"


def test_parse_events_to_decision_records_converts_entry(analyzer):
    """Test conversion of ENTRY_TRIGGERED events."""
    events = [
        {
            "event_type": "ENTRY_TRIGGERED",
            "timestamp": "2024-01-05T10:30:00Z",
            "ticker": "AAPL",
            "strategy": "momentum",
            "side": "long",
            "quantity": 100,
            "entry_price": 150.00,
            "stop_loss": 145.50,
            "target": 163.50,
            "reason": "Golden cross",
        }
    ]

    decisions, exec_events = analyzer._parse_events_to_decision_records(events)

    assert len(decisions) == 1
    assert decisions[0].ticker == "AAPL"
    assert decisions[0].action == "BUY"
    assert decisions[0].quantity == 100


def test_parse_events_to_decision_records_converts_exit(analyzer):
    """Test conversion of EXIT_TRIGGERED events."""
    events = [
        {
            "event_type": "EXIT_TRIGGERED",
            "timestamp": "2024-01-05T14:30:00Z",
            "ticker": "AAPL",
            "strategy": "momentum",
            "side": "long",
            "quantity": 100,
            "entry_price": 150.00,
            "exit_price": 162.00,
            "pnl": 1200.0,
            "pnl_pct": 0.08,
            "hold_duration_hours": 4.0,
            "reason": "Target reached",
            "urgency": "normal",
        }
    ]

    decisions, exec_events = analyzer._parse_events_to_decision_records(events)

    assert len(decisions) == 1
    assert decisions[0].ticker == "AAPL"
    assert decisions[0].action == "EXIT_LONG"
    assert decisions[0].exit_pl_pct == 0.08


def test_build_event_summary(analyzer):
    """Test building event type summary."""
    events = [
        {"event_type": "ENTRY_TRIGGERED", "ticker": "AAPL", "timestamp": "2024-01-05T10:00:00Z"},
        {"event_type": "ENTRY_TRIGGERED", "ticker": "NVDA", "timestamp": "2024-01-05T11:00:00Z"},
        {"event_type": "EXIT_TRIGGERED", "ticker": "AAPL", "timestamp": "2024-01-05T14:00:00Z"},
        {"event_type": "ORDER_FILLED", "ticker": "AAPL", "timestamp": "2024-01-05T10:05:00Z"},
        {"event_type": "ORDER_FILLED", "ticker": "NVDA", "timestamp": "2024-01-05T11:05:00Z"},
        {"event_type": "POSITION_CLOSED", "ticker": "NVDA", "timestamp": "2024-01-05T15:00:00Z"},
    ]

    summary = analyzer._build_event_summary(events)

    assert summary["ENTRY_TRIGGERED"] == 2
    assert summary["EXIT_TRIGGERED"] == 1
    assert summary["ORDER_FILLED"] == 2
    assert summary["POSITION_CLOSED"] == 1


def test_build_position_timeline(analyzer):
    """Test building position timeline from events."""
    events = [
        {
            "event_type": "ENTRY_TRIGGERED",
            "ticker": "AAPL",
            "timestamp": "2024-01-05T10:00:00Z",
            "strategy": "momentum",
            "side": "long",
            "quantity": 100,
            "entry_price": 150.00,
            "reason": "Golden cross",
        },
        {"event_type": "ORDER_FILLED", "ticker": "AAPL", "timestamp": "2024-01-05T10:05:00Z", "quantity": 100, "avg_price": 150.25},
        {"event_type": "EXIT_TRIGGERED", "ticker": "AAPL", "timestamp": "2024-01-05T14:00:00Z", "quantity": 100, "exit_price": 160.00, "pnl": 1000.0, "pnl_pct": 0.067, "reason": "Target reached"},
    ]

    timeline = analyzer._build_position_timeline(events)

    assert len(timeline) == 1
    ticker, lines = timeline[0]
    assert ticker == "AAPL"
    assert len(lines) == 3
    assert "ENTRY_TRIGGERED" in lines[0]
    assert "ORDER_FILLED" in lines[1]
    assert "EXIT_TRIGGERED" in lines[2]


def test_build_strategy_performance(analyzer):
    """Test building strategy performance metrics."""
    events = [
        {"event_type": "ENTRY_TRIGGERED", "ticker": "AAPL", "timestamp": "2024-01-05T10:00:00Z", "strategy": "momentum"},
        {"event_type": "EXIT_TRIGGERED", "ticker": "AAPL", "timestamp": "2024-01-05T14:00:00Z", "strategy": "momentum", "pnl": 1000.0, "pnl_pct": 0.067, "hold_duration_hours": 4.0},
        {"event_type": "ENTRY_TRIGGERED", "ticker": "NVDA", "timestamp": "2024-01-05T11:00:00Z", "strategy": "mean_reversion"},
        {"event_type": "EXIT_TRIGGERED", "ticker": "NVDA", "timestamp": "2024-01-05T15:00:00Z", "strategy": "mean_reversion", "pnl": -500.0, "hold_duration_hours": 4.0},
        {"event_type": "ENTRY_TRIGGERED", "ticker": "TSLA", "timestamp": "2024-01-05T12:00:00Z", "strategy": "momentum"},
        {"event_type": "EXIT_TRIGGERED", "ticker": "TSLA", "timestamp": "2024-01-05T16:00:00Z", "strategy": "momentum", "pnl": 1500.0, "hold_duration_hours": 4.0},
    ]

    strategy_perf = analyzer._build_strategy_performance(events)

    assert "momentum" in strategy_perf
    assert "mean_reversion" in strategy_perf
    assert strategy_perf["momentum"]["entries"] == 2
    assert strategy_perf["momentum"]["exits"] == 2
    assert strategy_perf["momentum"]["wins"] == 2
    assert strategy_perf["momentum"]["total_pnl"] == 2500.0
    assert len(strategy_perf["momentum"]["hold_times"]) == 2
    assert strategy_perf["mean_reversion"]["entries"] == 1
    assert strategy_perf["mean_reversion"]["exits"] == 1
    assert strategy_perf["mean_reversion"]["wins"] == 0
    assert strategy_perf["mean_reversion"]["total_pnl"] == -500.0
