from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def complete_structured[T: BaseModel](
    client,
    messages: list[dict],
    response_model: type[T],
    model: str,
) -> tuple[T, object]:
    """
    Complete a structured LLM call using OpenRouter's native json_schema response_format.

    Returns:
        Tuple of (parsed_result, raw_response).
    """
    schema = response_model.model_json_schema()

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
    )

    content = response.choices[0].message.content
    result = response_model.model_validate_json(content)
    return result, response
