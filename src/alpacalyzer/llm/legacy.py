from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from alpacalyzer.gpt.call_gpt import call_gpt_structured as _legacy_call

T = TypeVar("T", bound=BaseModel)


def legacy_complete_structured(
    messages: list[dict],
    response_model: type[BaseModel],
) -> BaseModel | None:
    """Wrapper around legacy call_gpt.py for rollback support."""
    return _legacy_call(messages, response_model)
