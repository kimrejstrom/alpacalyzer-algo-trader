from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field


class SampleSchema(BaseModel):
    name: str = Field(..., description="Test name field")
    value: int = Field(..., description="Test value field")


class TestCompleteStructured:
    def test_strict_json_schema_mode(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "test", "value": 42}'
        mock_client.chat.completions.create.return_value = mock_response

        from alpacalyzer.llm.structured import complete_structured

        result = complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
            use_response_healing=False,
        )

        assert result.name == "test"
        assert result.value == 42
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["strict"] is True

    def test_response_healing_fallback(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "fallback", "value": 100}'
        mock_client.chat.completions.create.return_value = mock_response

        from alpacalyzer.llm.structured import complete_structured

        result = complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
            use_response_healing=True,
        )

        assert result.name == "fallback"
        assert result.value == 100
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "plugins" in call_kwargs

    def test_json_mode_fallback_on_invalid_first_response(self):
        mock_client = MagicMock()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            if call_count == 1:
                mock_response.choices[0].message.content = '{"wrong": "field"}'
            else:
                mock_response.choices[0].message.content = '{"name": "json_mode", "value": 200}'
            return mock_response

        mock_client.chat.completions.create.side_effect = side_effect

        from alpacalyzer.llm.structured import complete_structured

        result = complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
            use_response_healing=False,
        )

        assert result.name == "json_mode"
        assert result.value == 200
        assert mock_client.chat.completions.create.call_count == 2
        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        assert second_call_kwargs["response_format"]["type"] == "json_object"

    def test_schema_instruction_in_fallback(self):
        mock_client = MagicMock()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            if call_count == 1:
                mock_response.choices[0].message.content = '{"wrong": "field"}'
            else:
                mock_response.choices[0].message.content = '{"name": "schema_test", "value": 500}'
            return mock_response

        mock_client.chat.completions.create.side_effect = side_effect

        from alpacalyzer.llm.structured import complete_structured

        complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
            use_response_healing=False,
        )

        assert mock_client.chat.completions.create.call_count == 2
        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "json" in messages[0]["content"].lower()
        assert messages[1]["role"] == "user"


class TestLLMClientStructured:
    def test_complete_structured_uses_tier_routing(self):
        from alpacalyzer.llm.client import LLMClient
        from alpacalyzer.llm.config import LLMTier

        mock_inner_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "client_test", "value": 999}'
        mock_inner_client.chat.completions.create.return_value = mock_response

        with patch("alpacalyzer.llm.client.OpenAI", return_value=mock_inner_client):
            client = LLMClient()

        with patch("alpacalyzer.llm.client.get_model_for_tier") as mock_get_model:
            mock_get_model.return_value = "anthropic/claude-3.5-sonnet"

            client.complete_structured(
                [{"role": "user", "content": "test"}],
                SampleSchema,
                tier=LLMTier.STANDARD,
            )

            mock_get_model.assert_called_once_with(LLMTier.STANDARD)

    def test_complete_structured_with_default_tier(self):
        from alpacalyzer.llm.client import LLMClient

        mock_inner_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "default_tier", "value": 777}'
        mock_inner_client.chat.completions.create.return_value = mock_response

        with patch("alpacalyzer.llm.client.OpenAI", return_value=mock_inner_client):
            client = LLMClient()

        with patch("alpacalyzer.llm.client.get_model_for_tier", return_value="test-model"):
            client.complete_structured(
                [{"role": "user", "content": "test"}],
                SampleSchema,
            )

        call_kwargs = mock_inner_client.chat.completions.create.call_args.kwargs
        assert "response_format" in call_kwargs


class TestLLMTierConfig:
    def test_get_model_for_tier_fast(self):
        from alpacalyzer.llm.config import LLMTier, get_model_for_tier

        with patch.dict("os.environ", {"LLM_MODEL_FAST": "test-fast-model"}):
            result = get_model_for_tier(LLMTier.FAST)
            assert result == "test-fast-model"

    def test_get_model_for_tier_standard(self):
        from alpacalyzer.llm.config import LLMTier, get_model_for_tier

        with patch.dict("os.environ", {"LLM_MODEL_STANDARD": "test-standard-model"}):
            result = get_model_for_tier(LLMTier.STANDARD)
            assert result == "test-standard-model"

    def test_get_model_for_tier_deep(self):
        from alpacalyzer.llm.config import LLMTier, get_model_for_tier

        with patch.dict("os.environ", {"LLM_MODEL_DEEP": "test-deep-model"}):
            result = get_model_for_tier(LLMTier.DEEP)
            assert result == "test-deep-model"

    def test_get_model_for_tier_uses_defaults(self):
        import os

        from alpacalyzer.llm.config import LLMTier, get_model_for_tier

        original_env = {k: v for k, v in os.environ.items() if k.startswith("LLM_MODEL")}
        for k in original_env:
            del os.environ[k]

        try:
            fast = get_model_for_tier(LLMTier.FAST)
            standard = get_model_for_tier(LLMTier.STANDARD)
            deep = get_model_for_tier(LLMTier.DEEP)

            assert "llama" in fast.lower() or "3.2" in fast
            assert "claude" in standard.lower()
            assert "claude" in deep.lower()
        finally:
            for k, v in original_env.items():
                os.environ[k] = v
