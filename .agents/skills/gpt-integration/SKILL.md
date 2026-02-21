---
name: "gpt-integration"
description: "Use this skill ONLY when modifying GPT/LLM calls, agent prompts, or structured output. Do not use for other AI/ML tasks."
---

# Scope Constraint

- LLM abstraction layer: `src/alpacalyzer/llm/`
- Agent prompts: `src/alpacalyzer/prompts/` and inline in agent files
- GPT calls: `src/alpacalyzer/gpt/call_gpt.py` (legacy) or `src/alpacalyzer/llm/` (new)
- Tests must mock the LLM client (auto-mocked via `conftest.py`)

# Steps

## 1. Study the LLM integration

Read these files:

1. `src/alpacalyzer/llm/` — new abstraction layer (preferred)
2. `src/alpacalyzer/gpt/call_gpt.py` — legacy GPT calling logic
3. `src/alpacalyzer/agents/warren_buffet_agent.py` — example agent using LLM
4. `src/alpacalyzer/prompts/` — prompt templates
5. `tests/conftest.py` — auto-mocking setup

Key patterns: agents define a system prompt (investment philosophy), call LLM with structured output via Pydantic models, and return results that update LangGraph state.

## 2. Modify or create prompts

System prompts should have: clear identity, investment philosophy/principles, analysis framework, and output expectations. Keep prompts concise — GPT-4 has token limits.

Use Pydantic models with `Field(description=...)` to guide structured output. See `src/alpacalyzer/data/models.py` for existing response models.

## 3. Use the LLM abstraction

Prefer `src/alpacalyzer/llm/` over direct `call_gpt.py`. The new layer supports multiple providers via `LLM_API_KEY` env var.

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

| Purpose         | File                                            |
| --------------- | ----------------------------------------------- |
| LLM layer (new) | `src/alpacalyzer/llm/`                          |
| Legacy GPT      | `src/alpacalyzer/gpt/call_gpt.py`               |
| Example agent   | `src/alpacalyzer/agents/warren_buffet_agent.py` |
| Prompts         | `src/alpacalyzer/prompts/`                      |
| Response models | `src/alpacalyzer/data/models.py`                |
| Test mocking    | `tests/conftest.py`                             |
