from __future__ import annotations

from unittest.mock import MagicMock, patch

from alpacalyzer.llm.client import LLMClient


class TestLLMClient:
    def test_init_with_custom_base_url(self):
        client = LLMClient(base_url="https://custom.api.com/v1", api_key="test-key")
        assert str(client.client.base_url) == "https://custom.api.com/v1/"

    def test_init_fallback_to_openai_api_key(self):
        with patch.dict("os.environ", {"LLM_API_KEY": ""}, clear=False):
            with patch.dict("os.environ", {"OPENAI_API_KEY": "fallback-key"}, clear=False):
                client = LLMClient()
                assert client.client.api_key == "fallback-key"

    def test_complete_returns_content(self):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hello, World!"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("alpacalyzer.llm.client.OpenAI", return_value=mock_client):
            client = LLMClient()
            result = client.complete(messages=[{"role": "user", "content": "Say hello"}])

            assert result == "Hello, World!"
            mock_client.chat.completions.create.assert_called_once()

    def test_complete_with_model_param(self):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("alpacalyzer.llm.client.OpenAI", return_value=mock_client):
            client = LLMClient()
            client.complete(messages=[{"role": "user", "content": "Test"}], model="gpt-4")

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "gpt-4"

    def test_default_headers(self):
        client = LLMClient()
        assert client.client.default_headers.get("X-Title") == "Alpacalyzer"

    def test_init_with_custom_headers(self):
        client = LLMClient(default_headers={"X-Custom": "Value"})
        assert client.client.default_headers.get("X-Custom") == "Value"
