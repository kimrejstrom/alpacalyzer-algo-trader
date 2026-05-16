from __future__ import annotations

import os
from enum import Enum


class LLMTier(Enum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


def get_model_for_tier(tier: LLMTier) -> str:
    return {
        LLMTier.FAST: os.getenv("LLM_MODEL_FAST", "deepseek/deepseek-v4-flash"),
        LLMTier.STANDARD: os.getenv("LLM_MODEL_STANDARD", "deepseek/deepseek-v4-flash"),
        LLMTier.DEEP: os.getenv("LLM_MODEL_DEEP", "deepseek/deepseek-v4-pro"),
    }[tier]
