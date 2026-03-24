from __future__ import annotations

import json
from typing import TypeVar

import instructor
from pydantic import BaseModel, ValidationError

from alpacalyzer.utils.logger import get_logger

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)

# Default retry count — instructor feeds validation errors back to the LLM
MAX_RETRIES = 2


def complete_structured[T: BaseModel](
    client,
    messages: list[dict],
    response_model: type[T],
    model: str,
    use_response_healing: bool = True,
) -> tuple[T, object]:
    """
    Complete a structured LLM call using instructor for retry-with-feedback.

    Returns:
        Tuple of (parsed_result, raw_response).
    """
    # Wrap the raw OpenAI client with instructor in JSON mode
    # (most compatible with OpenRouter — doesn't require tool-calling support)
    instructor_client = instructor.from_openai(client, mode=instructor.Mode.JSON)

    try:
        result, raw_response = instructor_client.chat.completions.create_with_completion(
            model=model,
            messages=messages,
            response_model=response_model,
            max_retries=MAX_RETRIES,
        )
        return result, raw_response
    except (ValidationError, Exception) as e:
        # If instructor exhausts retries, fall back to manual JSON mode parse
        logger.warning(f"instructor retries exhausted for {response_model.__name__}: {e}")
        return _fallback_manual_parse(client, messages, response_model, model)


def _fallback_manual_parse[T: BaseModel](
    client,
    messages: list[dict],
    response_model: type[T],
    model: str,
) -> tuple[T, object]:
    """Last-resort fallback: raw JSON mode + coercion helpers."""
    schema = response_model.model_json_schema()
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
    content = _sanitize_json_control_chars(content)
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
        list_fields = [name for name, field_info in model_fields.items() if hasattr(field_info.annotation, "__origin__") and field_info.annotation.__origin__ is list]
        if len(list_fields) == 1:
            wrapper_key = list_fields[0]
            if wrapper_key not in data:
                data = {wrapper_key: [data]}
                changed = True

    # Case 3: list items missing "ticker" — drop invalid items
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
    """Strip markdown code fences and extract JSON from mixed text/JSON responses."""
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

    # Pattern 2: prose preamble before JSON
    if stripped and stripped[0] not in ("{", "["):
        brace_idx = stripped.find("{")
        bracket_idx = stripped.find("[")

        candidates = []
        if brace_idx != -1:
            candidates.append(brace_idx)
        if bracket_idx != -1:
            candidates.append(bracket_idx)

        if candidates:
            start = min(candidates)
            candidate = stripped[start:]
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, ValueError):
                pass

    return stripped


def _sanitize_json_control_chars(content: str) -> str:
    """
    Remove unescaped control characters (U+0000–U+001F) that break JSON parsing.

    Many cheap/fast LLMs emit literal newlines, tabs, or other control chars
    inside JSON string values.  ``json.loads`` (and Pydantic's
    ``model_validate_json``) reject these per the JSON spec.

    Strategy: replace common control chars with their escaped equivalents,
    and strip the rest.
    """
    # Replace common control characters with their JSON escape sequences
    replacements = {
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
    }

    # We need to operate only inside JSON string values to avoid breaking
    # the structural whitespace.  A pragmatic approach: first try json.loads;
    # if it works, the content is fine.  If not, do a brute-force replacement
    # of control chars that appear between quotes.
    try:
        json.loads(content)
        return content  # already valid
    except (json.JSONDecodeError, ValueError):
        pass

    # Brute-force: replace control chars everywhere, then re-add structural
    # newlines by re-formatting.  This works because JSON structural whitespace
    # is optional.
    cleaned = []
    for ch in content:
        if ch in replacements:
            cleaned.append(replacements[ch])
        elif ord(ch) < 0x20:
            # Drop other control characters (NUL, BEL, etc.)
            continue
        else:
            cleaned.append(ch)
    result = "".join(cleaned)

    # Verify the result is now valid JSON; if not, return as-is and let
    # downstream error handling deal with it.
    try:
        json.loads(result)
        return result
    except (json.JSONDecodeError, ValueError):
        return result
