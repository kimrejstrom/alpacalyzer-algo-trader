from __future__ import annotations

import os


def get_model_for_task(task: str) -> str:
    return os.getenv("LLM_MODEL_STANDARD", "anthropic/claude-3.5-sonnet")
