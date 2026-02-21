"""Tests for LLMCallEvent and ErrorEvent models."""

from datetime import UTC, datetime

from alpacalyzer.events.models import ErrorEvent, LLMCallEvent


def test_llm_call_event_creation():
    """LLMCallEvent can be created with all fields."""
    event = LLMCallEvent(
        timestamp=datetime.now(tz=UTC),
        agent="TechnicalsAgent",
        model="claude-3.5-sonnet",
        tier="standard",
        latency_ms=1200.0,
        prompt_tokens=500,
        completion_tokens=200,
        total_tokens=700,
        cost_usd=0.015,
    )
    assert event.event_type == "LLM_CALL"
    assert event.agent == "TechnicalsAgent"
    assert event.total_tokens == 700


def test_llm_call_event_serialization():
    """LLMCallEvent serializes to JSON correctly."""
    event = LLMCallEvent(
        timestamp=datetime.now(tz=UTC),
        agent="SentimentAgent",
        model="llama-3.2-3b-instruct",
        tier="fast",
        latency_ms=300.0,
        prompt_tokens=200,
        completion_tokens=100,
        total_tokens=300,
    )
    data = event.model_dump()
    assert data["event_type"] == "LLM_CALL"
    assert data["cost_usd"] is None

    json_str = event.model_dump_json()
    assert "LLM_CALL" in json_str


def test_llm_call_event_optional_cost():
    """cost_usd is optional and defaults to None."""
    event = LLMCallEvent(
        timestamp=datetime.now(tz=UTC),
        agent="TestAgent",
        model="test-model",
        tier="fast",
        latency_ms=100.0,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )
    assert event.cost_usd is None


def test_error_event_creation():
    """ErrorEvent can be created with all fields."""
    event = ErrorEvent(
        timestamp=datetime.now(tz=UTC),
        error_type="rate_limit",
        component="order_manager",
        message="Rate limit exceeded",
        ticker="AAPL",
    )
    assert event.event_type == "ERROR"
    assert event.error_type == "rate_limit"
    assert event.component == "order_manager"
    assert event.ticker == "AAPL"


def test_error_event_optional_ticker():
    """ErrorEvent ticker is optional."""
    event = ErrorEvent(
        timestamp=datetime.now(tz=UTC),
        error_type="api_error",
        component="emitter",
        message="Connection timeout",
    )
    assert event.ticker is None


def test_error_event_serialization():
    """ErrorEvent serializes to JSON correctly."""
    event = ErrorEvent(
        timestamp=datetime.now(tz=UTC),
        error_type="llm_error",
        component="llm_client",
        message="Model not available",
    )
    json_str = event.model_dump_json()
    assert "ERROR" in json_str
    assert "llm_error" in json_str
