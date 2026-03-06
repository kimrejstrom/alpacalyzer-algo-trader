---
name: "gpt-integration"
description: "Use this skill ONLY when modifying LLM calls, agent prompts, or structured output. Do not use for other AI/ML tasks."
---

# Scope Constraint

- LLM abstraction layer: `src/alpacalyzer/llm/` (primary — use this)
- Agent prompts: `src/alpacalyzer/prompts/` (Markdown files) and inline in agent files
- Legacy GPT calls: `src/alpacalyzer/gpt/call_gpt.py` (deprecated — do not use for new code)
- Tests must mock the LLM client (auto-mocked via `conftest.py`)

# Steps

## 1. Study the LLM integration

Read these files:

1. `src/alpacalyzer/llm/client.py` — `LLMClient` class (OpenAI-compatible, supports OpenRouter)
2. `src/alpacalyzer/llm/config.py` — `LLMTier` enum (FAST/STANDARD/DEEP) and model mapping
3. `src/alpacalyzer/llm/structured.py` — `instructor`-based structured output with automatic retry-with-validation-feedback and manual fallback
4. `src/alpacalyzer/agents/warren_buffet_agent.py` — example agent using LLM
5. `src/alpacalyzer/prompts/` — prompt templates (Markdown)
6. `tests/conftest.py` — auto-mocking setup

Key patterns: agents define a system prompt (investment philosophy), call `LLMClient.complete_structured()` with a Pydantic response model and an `LLMTier`, and return results that update LangGraph state. Every call emits an `LLMCallEvent` for observability.

### Structured output pipeline

`complete_structured()` uses a three-layer approach:

1. **instructor** (`Mode.JSON`, `max_retries=2`) — wraps the OpenAI client, validates the response against the Pydantic model, and if validation fails, feeds the error back to the LLM and retries automatically.
2. **Manual fallback** — if instructor exhausts retries, falls back to raw `json_object` mode with schema injected as a system message, plus coercion helpers (`_coerce_dict_lists`, `_strip_code_fences`).
3. **Model-level hardening** — Pydantic models themselves have `field_validator`s that tolerate common LLM mistakes (e.g. `risk_reward_ratio: "1:1.47"` → `1.47`, `entry_criteria` as string → list). This means most LLM output parses on the first try without needing retries.

## 2. Modify or create prompts

System prompts should have: clear identity, investment philosophy/principles, analysis framework, and output expectations. Keep prompts concise — token limits vary by model tier.

Use Pydantic models with `Field(description=...)` to guide structured output. See `src/alpacalyzer/data/models.py` for existing response models.

When creating response models for LLM output, make them resilient:

- Use defaults for fields LLMs commonly omit (e.g. `quantity: int = 0`)
- Add `field_validator(mode="before")` for type coercion (e.g. `"1:1.47"` → `1.47`)
- Accept union types where LLMs vary (e.g. `entry_criteria: list[EntryCriteria | str]`)
- See `TradingStrategy` in `models.py` for the canonical example

## 3. Use the LLM abstraction

Always use `src/alpacalyzer/llm/` for new code. Do not use `src/alpacalyzer/gpt/call_gpt.py` — it is deprecated.

The LLM layer supports multiple providers via `LLM_API_KEY` env var (OpenRouter by default). Choose the appropriate tier:

| Tier               | Use Case                           | Default Model     |
| ------------------ | ---------------------------------- | ----------------- |
| `LLMTier.FAST`     | Sentiment, opportunity finding     | Llama 3.2 3B      |
| `LLMTier.STANDARD` | Investor agents, portfolio manager | Claude 3.5 Sonnet |
| `LLMTier.DEEP`     | Quant agent, trading strategist    | Claude 3.5 Sonnet |

## 4. Write tests

All tests auto-mock the LLM client via `conftest.py`. Test:

- Correct parameters passed to LLM
- Response structure matches expected model
- Error handling when LLM fails

## 5. Run and verify

```bash
uv run pytest tests/test_<agent>_agent.py -v
```

# Reference files

| Purpose             | File                                            |
| ------------------- | ----------------------------------------------- |
| LLM client          | `src/alpacalyzer/llm/client.py`                 |
| LLM config/tiers    | `src/alpacalyzer/llm/config.py`                 |
| Structured output   | `src/alpacalyzer/llm/structured.py`             |
| Example agent       | `src/alpacalyzer/agents/warren_buffet_agent.py` |
| Prompts             | `src/alpacalyzer/prompts/`                      |
| Response models     | `src/alpacalyzer/data/models.py`                |
| Structured tests    | `tests/test_llm_structured.py`                  |
| Test mocking        | `tests/conftest.py`                             |
| Legacy (deprecated) | `src/alpacalyzer/gpt/call_gpt.py`               |
