"""Tests for LLM client emitting LLMCallEvent on completions."""

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from alpacalyzer.events.models import LLMCallEvent
from alpacalyzer.llm.client import LLMClient
from alpacalyzer.llm.config import LLMTier


class MockResponse(BaseModel):
    answer: str


def _make_mock_openai_response(content: str, usage=None):
    """Create a mock OpenAI response."""
    choice = MagicMock()
    choice.message.content = content

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_mock_usage(prompt_tokens=100, completion_tokens=50, total_tokens=150):
    """Create a mock usage object."""
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    usage.total_tokens = total_tokens
    return usage


def test_complete_structured_emits_llm_call_event():
    """complete_structured emits an LLMCallEvent via emit_event."""
    client = LLMClient(api_key="test-key", base_url="http://fake")

    usage = _make_mock_usage(prompt_tokens=200, completion_tokens=80, total_tokens=280)
    mock_response = _make_mock_openai_response('{"answer": "42"}', usage=usage)

    with (
        patch.object(client.client.chat.completions, "create", return_value=mock_response),
        patch("alpacalyzer.llm.client.emit_event") as mock_emit,
    ):
        result = client.complete_structured(
            messages=[{"role": "user", "content": "test"}],
            response_model=MockResponse,
            tier=LLMTier.STANDARD,
            caller="TestAgent",
        )

    assert result.answer == "42"
    mock_emit.assert_called_once()
    event = mock_emit.call_args[0][0]
    assert isinstance(event, LLMCallEvent)
    assert event.agent == "TestAgent"
    assert event.total_tokens == 280
    assert event.latency_ms > 0


def test_complete_structured_default_caller():
    """complete_structured uses 'unknown' as default caller."""
    client = LLMClient(api_key="test-key", base_url="http://fake")

    usage = _make_mock_usage()
    mock_response = _make_mock_openai_response('{"answer": "ok"}', usage=usage)

    with (
        patch.object(client.client.chat.completions, "create", return_value=mock_response),
        patch("alpacalyzer.llm.client.emit_event") as mock_emit,
    ):
        client.complete_structured(
            messages=[{"role": "user", "content": "test"}],
            response_model=MockResponse,
            tier=LLMTier.FAST,
        )

    event = mock_emit.call_args[0][0]
    assert event.agent == "unknown"
    assert event.tier == "fast"


def test_complete_structured_handles_missing_usage():
    """LLMCallEvent is emitted even when usage data is missing."""
    client = LLMClient(api_key="test-key", base_url="http://fake")

    mock_response = _make_mock_openai_response('{"answer": "ok"}', usage=None)

    with (
        patch.object(client.client.chat.completions, "create", return_value=mock_response),
        patch("alpacalyzer.llm.client.emit_event") as mock_emit,
    ):
        client.complete_structured(
            messages=[{"role": "user", "content": "test"}],
            response_model=MockResponse,
            tier=LLMTier.STANDARD,
        )

    event = mock_emit.call_args[0][0]
    assert event.prompt_tokens == 0
    assert event.completion_tokens == 0
    assert event.total_tokens == 0
