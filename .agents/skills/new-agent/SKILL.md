---
name: "new-agent"
description: "Use this skill ONLY when creating a new hedge fund agent (e.g., Ray Dalio, Peter Lynch). Do not use for scanners or other components."
---

# Scope Constraint

- Agent files go in `src/alpacalyzer/agents/{name}_agent.py`
- Tests go in `tests/test_{name}_agent.py`
- Agents are LangGraph nodes in the hedge fund workflow

# Placeholders

- `<agent>` — lowercase with underscores (e.g., `ray_dalio`)
- `<Agent>` — PascalCase (e.g., `RayDalio`)

# Steps

## 1. Study the reference implementation

Read `src/alpacalyzer/agents/warren_buffet_agent.py` — it's the canonical example. Also glance at `src/alpacalyzer/agents/cathie_wood_agent.py` for a second style.

Key patterns: each agent has a system prompt defining its investment philosophy, calls GPT via `src/alpacalyzer/llm/`, and returns structured output that updates LangGraph state.

## 2. Create agent file

Copy `src/alpacalyzer/agents/warren_buffet_agent.py` → `src/alpacalyzer/agents/<agent>_agent.py` and modify:

- `SYSTEM_PROMPT` — define the agent's unique investment philosophy
- Function name — `<agent>_agent(state: AgentState)`
- Signal model — reuse or extend `WarrenBuffettSignal` pattern
- Return key — `<agent>_signal`

## 3. Register in hedge fund workflow

Edit `src/alpacalyzer/hedge_fund.py`:

- Import the new agent function
- Add as a LangGraph node
- Wire edges (typically after other agents, before risk manager)

## 4. Write tests

Follow the pattern in `tests/test_investor_agents.py`:

- Test bullish/bearish/neutral signal generation
- Test error handling when LLM fails
- Mock the LLM client (auto-mocked via `conftest.py`)

## 5. Run and verify

```bash
uv run pytest tests/test_<agent>_agent.py -v
uv run pytest tests/test_hedge_fund.py -v  # integration
```

# Reference files

| Purpose         | File                                            |
| --------------- | ----------------------------------------------- |
| Reference agent | `src/alpacalyzer/agents/warren_buffet_agent.py` |
| Second example  | `src/alpacalyzer/agents/cathie_wood_agent.py`   |
| LLM integration | `src/alpacalyzer/llm/`                          |
| Workflow        | `src/alpacalyzer/hedge_fund.py`                 |
| Graph state     | `src/alpacalyzer/graph/state.py`                |
| Prompts         | `src/alpacalyzer/prompts/`                      |
| Test pattern    | `tests/test_investor_agents.py`                 |
