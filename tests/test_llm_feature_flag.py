from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from alpacalyzer.llm import complete_structured, use_new_llm


class TestModel(BaseModel):
    name: str
    value: int


class TestUseNewLLM:
    def test_default_true(self, monkeypatch):
        monkeypatch.delenv("USE_NEW_LLM", raising=False)
        assert use_new_llm() is True

    def test_explicit_true(self, monkeypatch):
        monkeypatch.setenv("USE_NEW_LLM", "true")
        assert use_new_llm() is True

    def test_explicit_false(self, monkeypatch):
        monkeypatch.setenv("USE_NEW_LLM", "false")
        assert use_new_llm() is False

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("USE_NEW_LLM", "FALSE")
        assert use_new_llm() is False

        monkeypatch.setenv("USE_NEW_LLM", "True")
        assert use_new_llm() is True


class TestCompleteStructured:
    def test_routes_to_new_client_when_flag_true(self, monkeypatch):
        monkeypatch.setenv("USE_NEW_LLM", "true")

        mock_client = MagicMock()
        mock_response = TestModel(name="test", value=42)
        mock_client.complete_structured.return_value = mock_response

        with patch("alpacalyzer.llm.get_llm_client", return_value=mock_client):
            result = complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_model=TestModel,
            )

            assert result == mock_response
            mock_client.complete_structured.assert_called_once()

    def test_routes_to_legacy_when_flag_false(self, monkeypatch):
        monkeypatch.setenv("USE_NEW_LLM", "false")

        mock_response = TestModel(name="legacy", value=99)

        with patch("alpacalyzer.llm.legacy_complete_structured", return_value=mock_response) as mock_legacy:
            result = complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_model=TestModel,
            )

            assert result == mock_response
            mock_legacy.assert_called_once()
