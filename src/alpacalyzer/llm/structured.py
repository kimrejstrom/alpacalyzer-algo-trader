from __future__ import annotations

from pydantic import BaseModel


def structured_output(client, messages: list[dict], format_cls: type[BaseModel]) -> BaseModel:
    raise NotImplementedError("Structured output support planned for Issue #3")
