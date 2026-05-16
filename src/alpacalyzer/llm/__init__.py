from __future__ import annotations

from pydantic import BaseModel

from alpacalyzer.llm.client import LLMClient
from alpacalyzer.llm.config import LLMTier

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def complete_structured[T: BaseModel](
    messages: list[dict],
    response_model: type[T],
    tier: LLMTier = LLMTier.STANDARD,
) -> T:
    """Complete a structured LLM call via OpenRouter with json_schema response_format."""
    client = get_llm_client()
    return client.complete_structured(messages, response_model, tier)


__all__ = [
    "LLMClient",
    "LLMTier",
    "complete_structured",
    "get_llm_client",
]
