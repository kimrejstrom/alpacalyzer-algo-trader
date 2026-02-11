from __future__ import annotations

import os
from unittest.mock import patch

from alpacalyzer.gpt.config import AGENT_TIERS, LLMTier, get_model_for_tier


class TestLLMTier:
    def test_enum_values(self):
        assert LLMTier.FAST.value == "fast"
        assert LLMTier.STANDARD.value == "standard"
        assert LLMTier.DEEP.value == "deep"

    def test_enum_member_names(self):
        assert LLMTier.FAST.name == "FAST"
        assert LLMTier.STANDARD.name == "STANDARD"
        assert LLMTier.DEEP.name == "DEEP"


class TestGetModelForTier:
    def test_fast_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            model = get_model_for_tier(LLMTier.FAST)
            assert model == "meta-llama/llama-3.2-3b-instruct"

    def test_standard_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            model = get_model_for_tier(LLMTier.STANDARD)
            assert model == "anthropic/claude-3.5-sonnet"

    def test_deep_default_model(self):
        with patch.dict(os.environ, {}, clear=True):
            model = get_model_for_tier(LLMTier.DEEP)
            assert model == "anthropic/claude-3.5-sonnet"

    def test_fast_env_override(self):
        with patch.dict(os.environ, {"LLM_MODEL_FAST": "custom-fast-model"}):
            model = get_model_for_tier(LLMTier.FAST)
            assert model == "custom-fast-model"

    def test_standard_env_override(self):
        with patch.dict(os.environ, {"LLM_MODEL_STANDARD": "custom-standard-model"}):
            model = get_model_for_tier(LLMTier.STANDARD)
            assert model == "custom-standard-model"

    def test_deep_env_override(self):
        with patch.dict(os.environ, {"LLM_MODEL_DEEP": "custom-deep-model"}):
            model = get_model_for_tier(LLMTier.DEEP)
            assert model == "custom-deep-model"

    def test_multiple_env_overrides(self):
        env = {
            "LLM_MODEL_FAST": "fast-override",
            "LLM_MODEL_STANDARD": "standard-override",
            "LLM_MODEL_DEEP": "deep-override",
        }
        with patch.dict(os.environ, env, clear=True):
            assert get_model_for_tier(LLMTier.FAST) == "fast-override"
            assert get_model_for_tier(LLMTier.STANDARD) == "standard-override"
            assert get_model_for_tier(LLMTier.DEEP) == "deep-override"


class TestAgentTiers:
    def test_fast_tier_agents(self):
        assert AGENT_TIERS["sentiment_agent"] == LLMTier.FAST
        assert AGENT_TIERS["technical_analyst"] == LLMTier.FAST
        assert AGENT_TIERS["opportunity_finder"] == LLMTier.FAST

    def test_standard_tier_agents(self):
        assert AGENT_TIERS["fundamental_analyst"] == LLMTier.STANDARD
        assert AGENT_TIERS["ben_graham"] == LLMTier.STANDARD
        assert AGENT_TIERS["bill_ackman"] == LLMTier.STANDARD
        assert AGENT_TIERS["cathie_wood"] == LLMTier.STANDARD
        assert AGENT_TIERS["charlie_munger"] == LLMTier.STANDARD
        assert AGENT_TIERS["warren_buffett"] == LLMTier.STANDARD
        assert AGENT_TIERS["portfolio_management_agent"] == LLMTier.STANDARD
        assert AGENT_TIERS["risk_management_agent"] == LLMTier.STANDARD

    def test_deep_tier_agents(self):
        assert AGENT_TIERS["quant_agent"] == LLMTier.DEEP
        assert AGENT_TIERS["trading_strategist_agent"] == LLMTier.DEEP

    def test_all_agents_mapped(self):
        expected_agent_count = 13
        assert len(AGENT_TIERS) == expected_agent_count

    def test_agent_tiers_returns_correct_enum(self):
        for tier in AGENT_TIERS.values():
            assert isinstance(tier, LLMTier)
