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


AGENT_TIERS: dict[str, LLMTier] = {
    "sentiment_agent": LLMTier.FAST,
    "technical_analyst": LLMTier.FAST,
    "opportunity_finder": LLMTier.FAST,
    "fundamental_analyst": LLMTier.STANDARD,
    "ben_graham": LLMTier.STANDARD,
    "bill_ackman": LLMTier.STANDARD,
    "cathie_wood": LLMTier.STANDARD,
    "charlie_munger": LLMTier.STANDARD,
    "warren_buffett": LLMTier.STANDARD,
    "portfolio_management_agent": LLMTier.STANDARD,
    "risk_management_agent": LLMTier.STANDARD,
    "quant_agent": LLMTier.DEEP,
    "trading_strategist_agent": LLMTier.DEEP,
}
