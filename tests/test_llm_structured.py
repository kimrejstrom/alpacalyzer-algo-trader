import json
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field


class SampleSchema(BaseModel):
    name: str = Field(..., description="Test name field")
    value: int = Field(..., description="Test value field")


class TestCompleteStructured:
    """Tests for the instructor-based complete_structured function."""

    def test_valid_response_parses_successfully(self):
        """Valid JSON response is parsed into the response model."""
        from alpacalyzer.llm.structured import complete_structured

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "test", "value": 42}'
        mock_client.chat.completions.create.return_value = mock_response

        result, response = complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
        )

        assert result.name == "test"
        assert result.value == 42

    def test_instructor_retry_on_validation_error(self):
        """When instructor path succeeds with retry, returns valid model."""
        from alpacalyzer.llm.structured import complete_structured

        mock_client = MagicMock()
        mock_instructor_client = MagicMock()

        expected = SampleSchema(name="retry_ok", value=200)
        mock_raw = MagicMock()
        mock_instructor_client.chat.completions.create_with_completion.return_value = (expected, mock_raw)

        with patch("alpacalyzer.llm.structured.instructor") as mock_instructor:
            mock_instructor.from_openai.return_value = mock_instructor_client
            mock_instructor.Mode.JSON = "json"

            result, response = complete_structured(
                mock_client,
                [{"role": "user", "content": "test"}],
                SampleSchema,
                "test-model",
            )

        assert result.name == "retry_ok"
        assert result.value == 200
        mock_instructor.from_openai.assert_called_once_with(mock_client, mode="json")

    def test_instructor_passes_max_retries(self):
        """Instructor is called with max_retries for automatic retry-with-feedback."""
        from alpacalyzer.llm.structured import MAX_RETRIES, complete_structured

        mock_client = MagicMock()
        mock_instructor_client = MagicMock()

        expected = SampleSchema(name="test", value=42)
        mock_instructor_client.chat.completions.create_with_completion.return_value = (expected, MagicMock())

        with patch("alpacalyzer.llm.structured.instructor") as mock_instructor:
            mock_instructor.from_openai.return_value = mock_instructor_client
            mock_instructor.Mode.JSON = "json"

            complete_structured(
                mock_client,
                [{"role": "user", "content": "test"}],
                SampleSchema,
                "test-model",
            )

        call_kwargs = mock_instructor_client.chat.completions.create_with_completion.call_args.kwargs
        assert call_kwargs["max_retries"] == MAX_RETRIES

    def test_fallback_on_instructor_failure(self):
        """When instructor exhausts retries, falls back to manual JSON parse."""
        from alpacalyzer.llm.structured import complete_structured

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "fallback_ok", "value": 999}'
        mock_client.chat.completions.create.return_value = mock_response

        mock_instructor_client = MagicMock()
        mock_instructor_client.chat.completions.create_with_completion.side_effect = Exception("retries exhausted")

        with patch("alpacalyzer.llm.structured.instructor") as mock_instructor:
            mock_instructor.from_openai.return_value = mock_instructor_client
            mock_instructor.Mode.JSON = "json"

            result, response = complete_structured(
                mock_client,
                [{"role": "user", "content": "test"}],
                SampleSchema,
                "test-model",
            )

        assert result.name == "fallback_ok"
        assert result.value == 999

    def test_fallback_includes_schema_in_system_message(self):
        """Manual fallback injects schema instruction as system message."""
        from alpacalyzer.llm.structured import _fallback_manual_parse

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "schema_test", "value": 500}'
        mock_client.chat.completions.create.return_value = mock_response

        _fallback_manual_parse(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "json" in messages[0]["content"].lower()
        assert call_kwargs["response_format"]["type"] == "json_object"


class DecisionItem(BaseModel):
    ticker: str
    action: str
    quantity: int = 0
    confidence: float = 50.0
    reasoning: str = ""


class DecisionList(BaseModel):
    decisions: list[DecisionItem]


class TestCoerceDictLists:
    def test_converts_dict_to_list(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"decisions": {"NVDA": {"action": "hold", "quantity": 0, "reasoning": "test"}, "AAPL": {"action": "buy", "quantity": 10, "reasoning": "test2"}}}'
        result = _coerce_dict_lists(raw)
        parsed = json.loads(result)
        assert isinstance(parsed["decisions"], list)
        assert len(parsed["decisions"]) == 2
        tickers = {d["ticker"] for d in parsed["decisions"]}
        assert tickers == {"NVDA", "AAPL"}

    def test_leaves_list_unchanged(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"decisions": [{"ticker": "NVDA", "action": "hold"}]}'
        assert _coerce_dict_lists(raw) == raw

    def test_leaves_invalid_json_unchanged(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = "not json"
        assert _coerce_dict_lists(raw) == raw

    def test_coerced_dict_validates_as_pydantic_model(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"decisions": {"NVDA": {"action": "hold", "quantity": 0, "confidence": 80.0, "reasoning": "strong"}}}'
        coerced = _coerce_dict_lists(raw)
        result = DecisionList.model_validate_json(coerced)
        assert len(result.decisions) == 1
        assert result.decisions[0].ticker == "NVDA"
        assert result.decisions[0].action == "hold"


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


class StrategyItem(BaseModel):
    ticker: str
    quantity: int = 0
    strategy_notes: str = ""


class StrategyList(BaseModel):
    strategies: list[StrategyItem]


class TestCoerceMissingWrapper:
    def test_wraps_flat_object_in_list_field(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"ticker": "GILD", "quantity": 10, "strategy_notes": "test"}'
        result = _coerce_dict_lists(raw, StrategyList)

        parsed = json.loads(result)
        assert "strategies" in parsed
        assert isinstance(parsed["strategies"], list)
        assert len(parsed["strategies"]) == 1
        assert parsed["strategies"][0]["ticker"] == "GILD"

    def test_wrapped_result_validates_as_pydantic(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"ticker": "GILD", "quantity": 10, "strategy_notes": "buy dip"}'
        coerced = _coerce_dict_lists(raw, StrategyList)
        result = StrategyList.model_validate_json(coerced)
        assert len(result.strategies) == 1
        assert result.strategies[0].ticker == "GILD"

    def test_no_wrap_when_key_already_present(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"strategies": [{"ticker": "GILD", "quantity": 10, "strategy_notes": "ok"}]}'
        result = _coerce_dict_lists(raw, StrategyList)
        assert result == raw

    def test_no_wrap_without_response_model(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"ticker": "GILD", "quantity": 10}'
        result = _coerce_dict_lists(raw)
        assert result == raw

    def test_dict_coercion_still_works_with_response_model(self):
        from alpacalyzer.llm.structured import _coerce_dict_lists

        raw = '{"decisions": {"NVDA": {"action": "hold", "quantity": 0, "reasoning": "test"}}}'
        result = _coerce_dict_lists(raw, DecisionList)

        parsed = json.loads(result)
        assert isinstance(parsed["decisions"], list)
        assert parsed["decisions"][0]["ticker"] == "NVDA"


class TestStripCodeFences:
    def test_strips_json_code_fence(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = '```json\n{"name": "test", "value": 42}\n```'
        assert _strip_code_fences(raw) == '{"name": "test", "value": 42}'

    def test_strips_plain_code_fence(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = '```\n{"name": "test", "value": 42}\n```'
        assert _strip_code_fences(raw) == '{"name": "test", "value": 42}'

    def test_leaves_plain_json_unchanged(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = '{"name": "test", "value": 42}'
        assert _strip_code_fences(raw) == raw

    def test_handles_whitespace_around_fences(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = '  ```json\n{"name": "test", "value": 42}\n```  '
        assert _strip_code_fences(raw) == '{"name": "test", "value": 42}'

    def test_handles_multiline_json_in_fences(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = '```json\n{\n  "top_tickers": [\n    {"ticker": "AAPL", "score": 5}\n  ]\n}\n```'
        result = _strip_code_fences(raw)
        parsed = json.loads(result)
        assert parsed["top_tickers"][0]["ticker"] == "AAPL"

    def test_strips_prose_preamble_before_json(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = 'Looking at AAOI, I need to analyze the data carefully.\n\n{"strategies": [{"ticker": "AAOI", "quantity": 10}]}'
        result = _strip_code_fences(raw)
        parsed = json.loads(result)
        assert parsed["strategies"][0]["ticker"] == "AAOI"

    def test_leaves_invalid_non_json_unchanged(self):
        from alpacalyzer.llm.structured import _strip_code_fences

        raw = "This is just plain text with no JSON at all."
        assert _strip_code_fences(raw) == raw


class TestSanitizeJsonControlChars:
    """Tests for _sanitize_json_control_chars — handles LLMs that emit unescaped control chars."""

    def test_valid_json_returned_unchanged(self):
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        raw = '{"name": "test", "value": 42}'
        assert _sanitize_json_control_chars(raw) == raw

    def test_literal_newlines_in_string_values_escaped(self):
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        # Simulate LLM returning literal newlines inside a JSON string value
        raw = '{"highlights": ["line one",\n"line two"]}'
        result = _sanitize_json_control_chars(raw)
        parsed = json.loads(result)
        assert parsed["highlights"] == ["line one", "line two"]

    def test_literal_tabs_escaped(self):
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        raw = '{"text": "hello\tworld"}'
        result = _sanitize_json_control_chars(raw)
        parsed = json.loads(result)
        assert "hello" in parsed["text"]

    def test_carriage_return_escaped(self):
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        raw = '{"text": "hello\r\nworld"}'
        result = _sanitize_json_control_chars(raw)
        parsed = json.loads(result)
        assert "hello" in parsed["text"]

    def test_null_bytes_stripped(self):
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        raw = '{"text": "hello\x00world"}'
        result = _sanitize_json_control_chars(raw)
        parsed = json.loads(result)
        assert parsed["text"] == "helloworld"

    def test_sentiment_response_with_control_chars(self):
        """Regression: exact pattern from mimo-v2-flash that caused the original error."""
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        # This mimics the actual failing response — literal newlines inside JSON string values
        raw = (
            '{\n  "sentiment_analysis": [\n    {\n'
            '      "sentiment": "Bullish",\n      "score": 0.7,\n'
            '      "highlights": [\n        "semiconductor ETFs rally",\n'
            '        "bull 3X ETF up 11.6%",\n'
            '        "US equity indexes rebound",\n'
            '        "S&P 500 closing up .83%"\n'
            "      ],\n"
            '      "rationale": "Strong positive momentum across'
            ' semiconductor and equity sectors."\n'
            "    }\n  ]\n}"
        )
        result = _sanitize_json_control_chars(raw)
        parsed = json.loads(result)
        assert parsed["sentiment_analysis"][0]["sentiment"] == "Bullish"
        assert len(parsed["sentiment_analysis"][0]["highlights"]) == 4

    def test_non_json_content_returned_as_is(self):
        from alpacalyzer.llm.structured import _sanitize_json_control_chars

        raw = "not json at all"
        assert _sanitize_json_control_chars(raw) == raw


class TestCompleteStructuredWithCodeFences:
    def test_handles_fenced_json_response(self):
        """Regression test: LLM returns JSON wrapped in markdown code fences."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"name": "fenced", "value": 99}\n```'
        mock_client.chat.completions.create.return_value = mock_response

        from alpacalyzer.llm.structured import complete_structured

        result, response = complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
        )

        assert result.name == "fenced"
        assert result.value == 99


class TestEntryCriteriaNormalization:
    """Regression tests: LLM generates near-miss EntryType enum values."""

    def test_exact_value_passes(self):
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="above_ma50", value=100.0)
        assert ec.entry_type == "above_ma50"

    def test_price_prefix_stripped(self):
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="price_above_ma50", value=100.0)
        assert ec.entry_type == "above_ma50"

    def test_price_near_support_exact(self):
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="price_near_support", value=370.0)
        assert ec.entry_type == "price_near_support"

    def test_price_below_ma20_normalized(self):
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="price_below_ma20", value=50.0)
        assert ec.entry_type == "below_ma20"


class TestTradingStrategyHardening:
    """Tests for TradingStrategy model resilience to common LLM output mistakes."""

    def test_risk_reward_ratio_colon_format(self):
        """LLM returns risk_reward_ratio as '1:1.47' instead of float."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio="1:1.47",  # type: ignore[arg-type]
        )
        assert ts.risk_reward_ratio == 1.47

    def test_risk_reward_ratio_plain_float(self):
        """Normal float still works."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio=2.5,
        )
        assert ts.risk_reward_ratio == 2.5

    def test_risk_reward_ratio_string_float(self):
        """LLM returns risk_reward_ratio as string '2.5'."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio="2.5",  # type: ignore[arg-type]
        )
        assert ts.risk_reward_ratio == 2.5

    def test_missing_optional_fields_use_defaults(self):
        """LLM omits quantity, entry_point, strategy_notes — defaults used."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio=1.5,
        )
        assert ts.quantity == 0
        assert ts.entry_point == 0.0
        assert ts.strategy_notes == ""

    def test_entry_criteria_string_coerced_to_list(self):
        """LLM returns entry_criteria as a plain string instead of list."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio=1.5,
            entry_criteria="Price closes above $101 with volume > 1.5x average",
        )
        assert isinstance(ts.entry_criteria, list)
        assert len(ts.entry_criteria) == 1

    def test_entry_criteria_list_of_strings(self):
        """LLM returns entry_criteria as list of plain strings."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio=1.5,
            entry_criteria=["Price above $101", "RSI > 50"],
        )
        assert isinstance(ts.entry_criteria, list)
        assert len(ts.entry_criteria) == 2

    def test_entry_criteria_dict_list_still_works(self):
        """Original EntryCriteria dict format still works."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio=1.5,
            entry_criteria=[{"entry_type": "above_ma50", "value": 101.0}],
        )
        assert isinstance(ts.entry_criteria, list)
        assert len(ts.entry_criteria) == 1

    def test_entry_criteria_defaults_to_empty(self):
        """entry_criteria defaults to empty list when omitted."""
        from alpacalyzer.data.models import TradingStrategy

        ts = TradingStrategy(
            ticker="AKAM",
            trade_type="long",
            stop_loss=95.0,
            target_price=110.0,
            risk_reward_ratio=1.5,
        )
        assert ts.entry_criteria == []

    def test_full_llm_response_json_parses(self):
        """Simulate the exact failing LLM response from production."""
        from alpacalyzer.data.models import TradingStrategyResponse

        raw = json.dumps(
            {
                "strategies": [
                    {
                        "ticker": "AKAM",
                        "trade_type": "long",
                        "stop_loss": 95.0,
                        "target_price": 110.0,
                        "risk_reward_ratio": "1:1.47",
                        "entry_criteria": "Price closes above $101.50 with volume exceeding 1.5M (1.5x average volume)",
                    }
                ]
            }
        )
        result = TradingStrategyResponse.model_validate_json(raw)
        assert len(result.strategies) == 1
        assert result.strategies[0].risk_reward_ratio == 1.47
        assert result.strategies[0].quantity == 0
        assert result.strategies[0].entry_point == 0.0
        assert result.strategies[0].strategy_notes == ""


class TestEntryCriteriaNullValue:
    """Regression: LLM returns pattern-based entry criteria with value=None."""

    def test_pattern_entry_with_null_value(self):
        """bullish_engulfing has no numeric value — LLM sends null."""
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="bullish_engulfing", value=None)
        assert ec.entry_type == "bullish_engulfing"
        assert ec.value is None

    def test_pattern_entry_with_missing_value(self):
        """LLM omits value entirely for pattern-based entries."""
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="doji")
        assert ec.entry_type == "doji"
        assert ec.value is None

    def test_numeric_entry_still_requires_value(self):
        """Numeric entries like above_ma50 still work with a value."""
        from alpacalyzer.data.models import EntryCriteria

        ec = EntryCriteria(entry_type="above_ma50", value=100.0)
        assert ec.value == 100.0

    def test_strategy_with_mixed_entry_criteria(self):
        """Regression: exact pattern from minimax-m2.5 that caused the original error."""
        from alpacalyzer.data.models import TradingStrategyResponse

        raw = json.dumps(
            {
                "strategies": [
                    {
                        "ticker": "AMPX",
                        "quantity": 263,
                        "entry_point": 17.71,
                        "stop_loss": 16.33,
                        "target_price": 18.50,
                        "risk_reward_ratio": 0.79,
                        "trade_type": "long",
                        "entry_criteria": [
                            {"entry_type": "price_near_support", "value": 17.60},
                            {"entry_type": "bullish_engulfing", "value": None},
                        ],
                    }
                ]
            }
        )
        result = TradingStrategyResponse.model_validate_json(raw)
        assert len(result.strategies) == 1
        assert len(result.strategies[0].entry_criteria) == 2
