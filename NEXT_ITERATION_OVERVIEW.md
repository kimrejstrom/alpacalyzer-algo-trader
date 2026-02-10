# Alpacalyzer Next Iteration: LLM Provider Migration & Model Tuning

**Created**: February 9, 2026
**Status**: � ISSUES CREATED
**Goal**: Move from OpenAI to an OpenAI-compatible provider, tune models per task

---

## Problem Statement

We're locked into OpenAI's Responses API (`client.responses.parse()`) with `gpt-5-mini` for everything. This creates three issues:

1. **Vendor lock-in** — The Responses API with `reasoning` and `text_format` parameters is OpenAI-specific. Can't switch providers.
2. **Cost inefficiency** — Sentiment classification uses the same model/config as complex trade setup generation.
3. **No model tuning** — All tasks use `reasoning.effort = "medium"` regardless of complexity.

### Current LLM Usage

| Agent                      | Task Type                 | Complexity | Current Config               |
| -------------------------- | ------------------------- | ---------- | ---------------------------- |
| `sentiment_agent.py`       | News classification       | Low        | gpt-5-mini, medium reasoning |
| `quant_agent.py`           | Chart pattern analysis    | High       | gpt-5-mini, medium reasoning |
| `trading_strategist.py`    | Trade setup generation    | High       | gpt-5-mini, medium reasoning |
| `portfolio_manager.py`     | Portfolio allocation      | Medium     | gpt-5-mini, medium reasoning |
| `opportunity_finder.py`    | Reddit/stock screening    | Low-Medium | gpt-5-mini, medium reasoning |
| `ben_graham_agent.py`      | Value investing synthesis | Medium     | gpt-5-mini, medium reasoning |
| (+ 3 more investor agents) | Investment synthesis      | Medium     | gpt-5-mini, medium reasoning |

---

## Migration Challenge

**Current code uses OpenAI's Responses API:**

```python
response = client.responses.parse(
    model="gpt-5-mini",
    reasoning={"effort": "medium"},
    input=messages,
    text_format=function_schema,  # Pydantic model
)
return response.output_parsed
```

**This is NOT the standard Chat Completions API.** The Responses API:

- Has built-in structured output via `text_format`
- Supports `reasoning` parameter for o-series models
- Returns `output_parsed` directly as the Pydantic type

**Target: Standard Chat Completions API** (OpenAI-compatible):

```python
response = client.chat.completions.create(
    model=config.model,
    messages=messages,
    response_format={"type": "json_schema", "json_schema": schema},
)
return function_schema.model_validate_json(response.choices[0].message.content)
```

This is a **breaking change** in how we call the API and parse responses.

---

## OpenRouter Research Findings

**Confirmed**: OpenRouter fully supports our migration path. Key findings:

### 1. OpenAI Python SDK Works Directly

OpenRouter is designed to work with the standard OpenAI SDK — just change `base_url`:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("LLM_API_KEY"),
    default_headers={
        "HTTP-Referer": "https://github.com/kimrejstrom/alpacalyzer-algo-trader",
        "X-Title": "Alpacalyzer",
    },
)

response = client.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    messages=[{"role": "user", "content": "Hello"}],
)
```

### 2. Structured Outputs Supported

OpenRouter supports `response_format` with `json_schema` type:

```python
response = client.chat.completions.create(
    model="anthropic/claude-3.5-sonnet",
    messages=messages,
    response_format={
        "type": "json_schema",
        "json_schema": {
            "name": "TradingSignal",
            "strict": True,
            "schema": TradingSignal.model_json_schema(),  # Pydantic → JSON Schema
        },
    },
)
result = TradingSignal.model_validate_json(response.choices[0].message.content)
```

**Models with structured output support**: OpenAI GPT-4o+, Anthropic Claude 3.5+, Google Gemini, most open-source models via Fireworks.

### 3. Response Healing Plugin

For models with imperfect JSON formatting, OpenRouter offers automatic repair:

```python
response = client.chat.completions.create(
    model="meta-llama/llama-3.3-70b-instruct",
    messages=messages,
    response_format={"type": "json_schema", "json_schema": schema},
    extra_body={"plugins": [{"id": "response-healing"}]},  # Auto-repair malformed JSON
)
```

This is our fallback for models that don't natively support strict JSON schema.

### 4. Migration Path Summary

| Current (Responses API)          | Target (Chat Completions)                                                |
| -------------------------------- | ------------------------------------------------------------------------ |
| `client.responses.parse()`       | `client.chat.completions.create()`                                       |
| `text_format=PydanticModel`      | `response_format={"type": "json_schema", ...}`                           |
| `response.output_parsed`         | `PydanticModel.model_validate_json(response.choices[0].message.content)` |
| `reasoning={"effort": "medium"}` | Not supported (use reasoning models directly)                            |
| OpenAI-only                      | Any OpenAI-compatible provider                                           |

### 5. Pydantic → JSON Schema Conversion

Pydantic v2 has built-in JSON Schema export:

```python
from pydantic import BaseModel

class TradingSignal(BaseModel):
    ticker: str
    action: str
    confidence: float
    reasoning: str

# Get JSON Schema for OpenRouter
schema = TradingSignal.model_json_schema()
# Returns: {"type": "object", "properties": {...}, "required": [...]}
```

This is exactly what OpenRouter's `json_schema.schema` field expects.

---

## Iteration 1: LLM Abstraction Layer

**Scope**: Replace the OpenAI-specific Responses API with a provider-agnostic layer. Ship and validate before changing prompts.

### Issues

| #                                                                         | Title                                                    | Priority | Depends On       | Effort |
| ------------------------------------------------------------------------- | -------------------------------------------------------- | -------- | ---------------- | ------ |
| [#106](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/106) | Create `llm/` module with provider-agnostic client       | P0       | -                | M      |
| [#107](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/107) | Add model routing config (fast/standard/deep tiers)      | P0       | #106             | S      |
| [#108](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/108) | Implement structured output with fallback chain          | P0       | #106             | M      |
| [#109](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/109) | Migrate all agents to new LLM client                     | P0       | #106, #107, #108 | M      |
| [#110](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/110) | Add feature flag for rollback (`USE_NEW_LLM=true/false`) | P0       | #106             | S      |
| [#111](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/111) | Update `.env.example` and docs                           | P1       | #109             | S      |

### Acceptance Criteria

**Issue #108 (Structured Output)** must pass:

- [ ] All 10 agent response schemas parse correctly with OpenRouter
- [ ] Tested against at least 2 model backends (e.g., Claude, Llama)
- [ ] Fallback chain: native JSON schema → JSON mode → prompt-based extraction
- [ ] No regression in agent output quality (manual spot-check)

**Issue #110 (Feature Flag)** enables:

- [ ] `USE_NEW_LLM=false` reverts to original `call_gpt.py` behavior
- [ ] Can A/B test in production before full cutover
- [ ] Clear logging of which path is active

### New Module Structure

```
src/alpacalyzer/llm/
├── __init__.py
├── client.py          # Provider-agnostic client with base_url support
├── config.py          # LLMConfig, ModelConfig, tier definitions
├── structured.py      # Structured output with fallback chain
└── legacy.py          # Wrapper around old call_gpt.py for rollback
```

### Implementation Sketch

**`client.py`** — Provider-agnostic wrapper:

```python
from openai import OpenAI
from pydantic import BaseModel
from alpacalyzer.llm.config import get_model_for_tier, LLMTier

class LLMClient:
    def __init__(self):
        self.client = OpenAI(
            base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"),
            default_headers={"X-Title": "Alpacalyzer"},
        )

    def complete_structured[T: BaseModel](
        self,
        messages: list[dict],
        response_model: type[T],
        tier: LLMTier = LLMTier.STANDARD,
    ) -> T:
        model = get_model_for_tier(tier)
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
            extra_body={"plugins": [{"id": "response-healing"}]},
        )
        return response_model.model_validate_json(
            response.choices[0].message.content
        )
```

**`config.py`** — Model routing:

```python
from enum import Enum

class LLMTier(Enum):
    FAST = "fast"        # Classification, simple extraction
    STANDARD = "standard"  # Synthesis, investor agents
    DEEP = "deep"        # Complex analysis, trade setup

def get_model_for_tier(tier: LLMTier) -> str:
    return {
        LLMTier.FAST: os.getenv("LLM_MODEL_FAST", "meta-llama/llama-3.2-3b-instruct"),
        LLMTier.STANDARD: os.getenv("LLM_MODEL_STANDARD", "anthropic/claude-3.5-sonnet"),
        LLMTier.DEEP: os.getenv("LLM_MODEL_DEEP", "anthropic/claude-3.5-sonnet"),
    }[tier]
```

### Environment Variables

```bash
# New LLM configuration
USE_NEW_LLM=true                                    # Feature flag for rollback
LLM_BASE_URL=https://openrouter.ai/api/v1          # OpenAI-compatible endpoint
LLM_API_KEY=your_openrouter_key                    # Falls back to OPENAI_API_KEY

# Model routing (verify actual model IDs on OpenRouter before use)
LLM_MODEL_FAST=meta-llama/llama-3.2-3b-instruct    # Tier 1: classification
LLM_MODEL_STANDARD=anthropic/claude-3.5-sonnet     # Tier 2: synthesis
LLM_MODEL_DEEP=anthropic/claude-3.5-sonnet         # Tier 3: complex analysis

# Legacy (still works when USE_NEW_LLM=false)
OPENAI_API_KEY=your_openai_api_key
```

**Note**: Model IDs are placeholders. Verify actual identifiers on OpenRouter before implementation.

---

## Iteration 2: Prompt Optimization (Future)

**Scope**: After Iteration 1 is stable, optimize prompts per model tier.

| #   | Title                                                      | Priority |
| --- | ---------------------------------------------------------- | -------- |
| 7   | Externalize agent prompts to markdown skill files          | P1       |
| 8   | Optimize fast-tier prompts (sentiment, opportunity finder) | P1       |
| 9   | Optimize standard-tier prompts (investor agents)           | P1       |
| 10  | Optimize deep-tier prompts (quant, trading strategist)     | P1       |
| 11  | Add explicit units to all numeric data in prompts          | P2       |
| 12  | Convert candle data to markdown tables                     | P2       |

---

## Iteration 3: Trading Improvements (Future)

**Scope**: Orthogonal to LLM migration. Separate iteration.

| #   | Title                                                | Priority | Notes                              |
| --- | ---------------------------------------------------- | -------- | ---------------------------------- |
| 13  | Add chop/regime filter (VIX + ATR Z-score)           | P1       | Prevents trading in bad conditions |
| 14  | Consume unused Alpaca bar fields (VWAP, trade count) | P2       | No subscription upgrade needed     |
| 15  | Add halt checks before order placement               | P2       | Via trading API, not market data   |
| 16  | Volume profile / VPOC analysis                       | P2       | New signal source                  |
| 17  | Risk-adjusted metrics in perf dashboard              | P2       | Sharpe, Sortino, Calmar            |

---

## Iteration 4: Observability (Future)

| #   | Title                                             | Priority |
| --- | ------------------------------------------------- | -------- |
| 18  | LLM call metrics (latency, tokens, cost)          | P2       |
| 19  | Domain-specific eval test suite for agent outputs | P2       |
| 20  | Remove `call_gpt_web` / dead code cleanup         | P2       |

---

## Risk Assessment

| Risk                                         | Likelihood | Impact | Mitigation                                          |
| -------------------------------------------- | ---------- | ------ | --------------------------------------------------- |
| Structured output breaks with new provider   | High       | High   | Fallback chain (#3), extensive schema testing       |
| Cheaper model produces worse trade decisions | Medium     | High   | Feature flag (#5), A/B test before full cutover     |
| Model IDs change on OpenRouter               | Medium     | Low    | Verify IDs before implementation, make configurable |
| Prompt changes degrade performance           | Medium     | Medium | Deferred to Iteration 2, after LLM layer is stable  |

---

## Open Questions (Resolved)

- [x] ~~Which specific models to use for each tier?~~ → Start with Claude 3.5 Sonnet for standard/deep, Llama 3.2 3B for fast. Benchmark after migration.
- [x] ~~Does OpenRouter support `response_format` JSON schema mode?~~ → **Yes**, for OpenAI, Anthropic, Google, and most open-source models. Use `response-healing` plugin as fallback.
- [x] ~~Keep `reasoning` parameter for o-series?~~ → **No**. The `reasoning` parameter is Responses API-specific. For reasoning models, just use them directly (e.g., `openai/o1-mini`). No special handling needed.

---

## Research Notes

Detailed analysis of external sources (r/Daytrading order flow post, r/algotrading metrics post, Fintool AI agents article) moved to separate document: `docs/llm_research_notes.md`

Key takeaways incorporated:

- Model routing by complexity is production-proven (Fintool)
- Skills/prompts as markdown files > hardcoded strings (Fintool)
- Chop filter using VIX + ATR Z-score (Daytrader) — deferred to Iteration 3
- VWAP/trade count from Alpaca bars (Daytrader) — deferred to Iteration 3
- Tick-level delta analysis not viable on free Alpaca tier (IEX = 2.5% volume)

---

_Issues created for Iteration 1. Work can begin._

### Execution Order

**Wave 1** (parallel):

- #106 — LLM client module (foundation)
- #110 — Feature flag (can start skeleton)

**Wave 2** (parallel, after #106):

- #107 — Model routing config
- #108 — Structured output

**Wave 3** (after #106, #107, #108):

- #109 — Migrate all agents

**Wave 4** (after #109):

- #111 — Documentation
