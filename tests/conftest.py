from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_openai_client(monkeypatch):
    """Mock the OpenAI client for all tests automatically."""
    mock_client = MagicMock()

    def mock_get_client():
        return mock_client

    monkeypatch.setattr("alpacalyzer.gpt.call_gpt.get_openai_client", mock_get_client)

    return mock_client
