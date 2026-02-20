from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from alpacalyzer.utils.logger import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


def complete_structured[T: BaseModel](
    client,
    messages: list[dict],
    response_model: type[T],
    model: str,
    use_response_healing: bool = True,
) -> tuple[T, object]:
    """
    Complete a structured LLM call.

    Returns:
        Tuple of (parsed_result, raw_response).
    """
    schema = response_model.model_json_schema()

    try:
        extra_body = {}
        if use_response_healing:
            extra_body["plugins"] = [{"id": "response-healing"}]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": schema,
                },
            },
            **extra_body,
        )
        content = response.choices[0].message.content
        return response_model.model_validate_json(content), response
    except (ValidationError, json.JSONDecodeError) as e:
        logger.debug(f"Strict JSON schema failed for {response_model.__name__}: {e}")
        return _fallback_json_mode(client, messages, response_model, model, schema)


def _fallback_json_mode[T: BaseModel](
    client,
    messages: list[dict],
    response_model: type[T],
    model: str,
    schema: dict,
) -> tuple[T, object]:
    schema_instruction = f"Respond with valid JSON matching this schema:\n```json\n{json.dumps(schema, indent=2)}\n```"

    augmented_messages = [
        {"role": "system", "content": schema_instruction},
        *messages,
    ]

    response = client.chat.completions.create(
        model=model,
        messages=augmented_messages,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return response_model.model_validate_json(content), response
