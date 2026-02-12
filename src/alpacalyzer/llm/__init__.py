from __future__ import annotations

import logging
import os
from typing import cast

from pydantic import BaseModel

from alpacalyzer.llm.client import LLMClient
from alpacalyzer.llm.config import LLMTier
from alpacalyzer.llm.legacy import legacy_complete_structured

logger = logging.getLogger(__name__)

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def use_new_llm() -> bool:
    """Check if new LLM client is enabled."""
    return os.getenv("USE_NEW_LLM", "true").lower() == "true"


def complete_structured[T: BaseModel](
    messages: list[dict],
    response_model: type[T],
    tier: LLMTier = LLMTier.STANDARD,
) -> T:
    """
    Unified interface that routes to new or legacy implementation.

    When USE_NEW_LLM=true (default): Uses new LLMClient with tier routing
    When USE_NEW_LLM=false: Uses legacy call_gpt_structured

    Raises:
        ValueError: If legacy implementation returns None.
    """
    if use_new_llm():
        client = get_llm_client()
        result = client.complete_structured(messages, response_model, tier)
        logger.info(f"LLM call via new client (tier={tier.value})")
        return result
    result = legacy_complete_structured(messages, response_model)
    if result is None:
        raise ValueError("Legacy LLM implementation returned None")
    logger.info("LLM call via legacy call_gpt.py")
    return cast(T, result)


__all__ = [
    "LLMClient",
    "get_llm_client",
    "LLMTier",
    "use_new_llm",
    "complete_structured",
    "legacy_complete_structured",
]
