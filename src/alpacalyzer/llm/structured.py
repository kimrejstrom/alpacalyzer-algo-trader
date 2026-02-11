from __future__ import annotations

from pydantic import BaseModel


def structured_output[T: BaseModel](client, messages: list[dict], format_cls: type[T]) -> T:
    raise NotImplementedError("Structured output support planned for Issue #3")
