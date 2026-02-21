from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_openai_client(monkeypatch):
    """Mock OpenAI client for all tests automatically."""
    mock_client = MagicMock()

    def mock_get_client():
        return mock_client

    monkeypatch.setattr("alpacalyzer.gpt.call_gpt.get_openai_client", mock_get_client)

    return mock_client


@pytest.fixture(autouse=True)
def _suppress_event_emitter():
    """Prevent EventEmitter singleton from registering Console/File handlers during tests."""
    from alpacalyzer.events.emitter import EventEmitter

    EventEmitter._instance = None
    # Create a bare emitter with no handlers so events are silently dropped
    instance = EventEmitter()
    EventEmitter._instance = instance
    yield
    EventEmitter._instance = None


pytest_plugins = ["tests.execution.fixtures"]
