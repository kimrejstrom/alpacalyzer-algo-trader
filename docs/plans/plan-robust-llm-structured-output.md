# Plan: Robust LLM Structured Output (instructor + model hardening)

## Goal

Replace brittle hand-rolled JSON schema enforcement with `instructor` library for automatic retry-with-validation-feedback, and harden Pydantic models to tolerate common LLM output mistakes.

## Problem

LLMs via OpenRouter (especially Claude via proxy) frequently return:

- Missing fields (`quantity`, `entry_point`, `strategy_notes`)
- Wrong types (`risk_reward_ratio: "1:1.47"` instead of float)
- Strings instead of lists (`entry_criteria`)
- Invented enum values

Current `structured.py` uses `json_schema` strict mode (not supported by all OpenRouter providers) with a fallback to `json_object` mode + manual coercion helpers. This is whack-a-mole.

## Approach: Two-pronged

1. **Adopt `instructor`** — wraps existing OpenAI client, adds retry-with-validation-feedback loop. Uses `Mode.JSON` for OpenRouter compatibility.
2. **Harden Pydantic models** — add defaults, validators, and coercion so that _most_ LLM mistakes parse on first try without needing retries.

## Acceptance Criteria

- [x] `instructor` added as dependency
- [x] `structured.py` refactored to use `instructor.from_openai()` with `Mode.JSON` and `max_retries=2`
- [x] `TradingStrategy` model hardened: `quantity`/`entry_point`/`strategy_notes` have defaults, `risk_reward_ratio` has validator for "1:X" format, `entry_criteria` accepts string input
- [x] `EntryCriteria` simplified — accept plain strings as fallback
- [x] Existing tests updated, new tests for model validators
- [x] All tests pass, lint clean

## Files to Modify

| File                                | Change                                |
| ----------------------------------- | ------------------------------------- |
| `pyproject.toml`                    | Add `instructor` dependency           |
| `src/alpacalyzer/llm/structured.py` | Rewrite to use instructor             |
| `src/alpacalyzer/llm/client.py`     | Pass instructor-wrapped client        |
| `src/alpacalyzer/data/models.py`    | Harden TradingStrategy, EntryCriteria |
| `tests/test_llm_structured.py`      | Update tests for new implementation   |

## Test Scenarios

| Scenario                                            | Expected                                                  |
| --------------------------------------------------- | --------------------------------------------------------- |
| LLM returns valid JSON                              | Parses on first try                                       |
| LLM returns `risk_reward_ratio: "1:1.47"`           | Validator coerces to 1.47                                 |
| LLM returns `entry_criteria` as string              | Validator wraps in list                                   |
| LLM omits `quantity`/`entry_point`/`strategy_notes` | Defaults used                                             |
| LLM returns completely wrong schema                 | instructor retries with error feedback, succeeds on retry |
| LLM fails all retries                               | Raises clear error                                        |

## Risks

- `instructor` adds a dependency — mitigated: it's the industry standard (1M+ monthly downloads), already depends on `openai` and `pydantic` which we have
- Mode.JSON may not work with all providers — mitigated: it's the most widely supported mode, and we keep the code-fence stripping as safety net
