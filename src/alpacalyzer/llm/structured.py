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
        extra_body: dict = {}
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
            extra_body=extra_body if extra_body else None,
        )
        content = response.choices[0].message.content
        content = _strip_code_fences(content)
        content = _coerce_dict_lists(content, response_model)
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
    content = _strip_code_fences(content)
    content = _coerce_dict_lists(content, response_model)
    return response_model.model_validate_json(content), response


def _coerce_dict_lists(content: str, response_model: type | None = None) -> str:
    """
    Coerce LLM output to match the expected schema structure.

    Handles two common LLM mistakes:
    1. Dict-valued fields instead of lists:
       ``{"decisions": {"TICKER": {...}}}`` → ``{"decisions": [{"ticker": "TICKER", ...}]}``
    2. Missing wrapper key — LLM returns a flat object or list that should be
       nested under the model's single list field:
       ``{"ticker": "GILD", ...}`` → ``{"strategies": [{"ticker": "GILD", ...}]}``
    """
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content

    changed = False

    # Case 1: dict-valued fields → lists
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
                data[key] = [{**v, "ticker": k} if "ticker" not in v else v for k, v in value.items()]
                changed = True

    # Case 2: missing wrapper key — LLM returned a flat object or bare list
    if response_model is not None and isinstance(data, dict) and hasattr(response_model, "model_fields"):
        model_fields: dict = response_model.model_fields  # type: ignore[union-attr]
        # Find the single list field on the response model (e.g. "strategies", "decisions")
        list_fields = [name for name, field_info in model_fields.items() if hasattr(field_info.annotation, "__origin__") and field_info.annotation.__origin__ is list]
        if len(list_fields) == 1:
            wrapper_key = list_fields[0]
            if wrapper_key not in data:
                # LLM returned the inner object directly — wrap it
                data = {wrapper_key: [data]}
                changed = True

    # Case 3: list items missing "ticker" — drop invalid items rather than
    # letting Pydantic reject the entire response.
    # Only apply to fields whose list item type actually has a "ticker" field.
    if isinstance(data, dict):
        ticker_list_fields: set[str] = set()
        if response_model is not None and hasattr(response_model, "model_fields"):
            model_fields_map: dict = response_model.model_fields  # type: ignore[union-attr]
            for name, field_info in model_fields_map.items():
                annotation = field_info.annotation
                if hasattr(annotation, "__origin__") and annotation.__origin__ is list:
                    args = getattr(annotation, "__args__", ())
                    if args and hasattr(args[0], "model_fields") and "ticker" in args[0].model_fields:
                        ticker_list_fields.add(name)

        for key, value in data.items():
            if isinstance(value, list) and (key in ticker_list_fields or response_model is None):
                original_len = len(value)
                data[key] = [item for item in value if not isinstance(item, dict) or "ticker" in item]
                if len(data[key]) < original_len:
                    dropped = original_len - len(data[key])
                    logger.warning(f"Dropped {dropped} list item(s) from '{key}' missing required 'ticker' field")
                    changed = True

    return json.dumps(data) if changed else content


def _strip_code_fences(content: str) -> str:
    """
    Strip markdown code fences and extract JSON from mixed text/JSON responses.

    Handles three LLM output patterns:
    1. ```json\n{...}\n``` — markdown code fences
    2. "Some reasoning text... {json}" — prose preamble before JSON
    3. Clean JSON — returned as-is
    """
    stripped = content.strip()

    # Pattern 1: markdown code fences
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline == -1:
            return stripped
        stripped = stripped[first_newline + 1 :]
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3].rstrip()
        return stripped

    # Pattern 2: prose preamble before JSON — find the first { or [
    # that starts a valid JSON structure
    if stripped and stripped[0] not in ("{", "["):
        # Try to find JSON object
        brace_idx = stripped.find("{")
        bracket_idx = stripped.find("[")

        # Pick the earliest valid JSON start
        candidates = []
        if brace_idx != -1:
            candidates.append(brace_idx)
        if bracket_idx != -1:
            candidates.append(bracket_idx)

        if candidates:
            start = min(candidates)
            candidate = stripped[start:]
            # Verify it's actually valid JSON before returning
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, ValueError):
                pass

    return stripped
