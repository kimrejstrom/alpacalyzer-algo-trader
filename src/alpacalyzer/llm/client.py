from __future__ import annotations

import os
from typing import Any

from openai import OpenAI


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
