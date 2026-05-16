import json
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field


class SampleSchema(BaseModel):
    name: str = Field(..., description="Test name field")
    value: int = Field(..., description="Test value field")


class TestCompleteStructured:
    """Tests for the OpenRouter json_schema complete_structured function."""

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

    def test_passes_json_schema_response_format(self):
        """Verifies the correct response_format is sent to OpenRouter."""
        from alpacalyzer.llm.structured import complete_structured

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"name": "test", "value": 1}'
        mock_client.chat.completions.create.return_value = mock_response

        complete_structured(
            mock_client,
            [{"role": "user", "content": "test"}],
            SampleSchema,
            "test-model",
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        rf = call_kwargs["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["name"] == "SampleSchema"
        assert rf["json_schema"]["strict"] is True
        assert "properties" in rf["json_schema"]["schema"]


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

            assert "deepseek" in fast.lower()
            assert "deepseek" in standard.lower()
            assert "deepseek" in deep.lower() and "pro" in deep.lower()
        finally:
            for k, v in original_env.items():
                os.environ[k] = v


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
