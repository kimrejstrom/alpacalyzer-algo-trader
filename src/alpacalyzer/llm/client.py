from __future__ import annotations

import os
from typing import Any, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from alpacalyzer.llm.config import LLMTier, get_model_for_tier
from alpacalyzer.llm.structured import complete_structured

T = TypeVar("T", bound="BaseModel")

_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_headers: dict[str, str] | None = None,
    ):
        self.client = OpenAI(
            base_url=base_url or os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            default_headers=default_headers or {"X-Title": "Alpacalyzer"},
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> str:
        response = self.client.chat.completions.create(
            model=model or os.getenv("LLM_MODEL_STANDARD", "gpt-4o"),
            messages=messages,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""

    def complete_structured(
        self,
        messages: list[dict],
        response_model: type[T],
        tier: LLMTier = LLMTier.STANDARD,
        use_response_healing: bool = True,
    ) -> T:
        model = get_model_for_tier(tier)
        return complete_structured(self.client, messages, response_model, model, use_response_healing)
