from __future__ import annotations

import os
from enum import Enum


class LLMTier(Enum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


def get_model_for_tier(tier: LLMTier) -> str:
    return {
        LLMTier.FAST: os.getenv("LLM_MODEL_FAST", "meta-llama/llama-3.2-3b-instruct"),
        LLMTier.STANDARD: os.getenv("LLM_MODEL_STANDARD", "anthropic/claude-3.5-sonnet"),
        LLMTier.DEEP: os.getenv("LLM_MODEL_DEEP", "anthropic/claude-3.5-sonnet"),
    }[tier]
