---
name: "pydantic-model"
description: "Use this skill ONLY when creating Pydantic data models, configs, or event types. Do not use for database models or other schemas."
---

# Scope Constraint

| Model Purpose                     | Location                               |
| --------------------------------- | -------------------------------------- |
| Trading data (signals, positions) | `src/alpacalyzer/data/models.py`       |
| Strategy configuration            | `src/alpacalyzer/strategies/config.py` |
| Event types (logging)             | `src/alpacalyzer/events/models.py`     |
| Execution state                   | `src/alpacalyzer/execution/state.py`   |
| Agent responses                   | `src/alpacalyzer/data/models.py`       |

# Steps

## 1. Study existing models

Read `src/alpacalyzer/data/models.py` for the established patterns. Also check `src/alpacalyzer/strategies/config.py` and `src/alpacalyzer/events/models.py`.

Key patterns: Pydantic v2 syntax (`model_dump()`, `ConfigDict`, `field_validator` with `@classmethod`), `Field()` with descriptions for GPT guidance, validators for business logic.

### LLM output resilience

Models that receive LLM output need extra hardening because LLMs frequently return wrong types, missing fields, or invented enum values. Patterns used in `TradingStrategy`:

- **Defaults for commonly-omitted fields**: `quantity: int = 0`, `entry_point: float = 0.0`, `strategy_notes: str = ""`
- **Type coercion validators**: `field_validator("risk_reward_ratio", mode="before")` parses `"1:1.47"` → `1.47`
- **Flexible input types**: `entry_criteria: list[EntryCriteria | str]` accepts both structured dicts and plain strings
- **Enum normalization**: `EntryCriteria.entry_type` validator maps near-miss values like `"price_above_ma50"` → `"above_ma50"`
- **Default collections**: `entry_criteria: list[...] = Field(default_factory=list)` instead of required list

## 2. Create model

Follow these conventions:

- Inherit from `pydantic.BaseModel`
- Use `Field(description=...)` for all fields (helps GPT structured output)
- Add `@field_validator` for business constraints (e.g., `stop_loss_pct < target_pct`)
- Add `@model_validator(mode='after')` for cross-field validation
- Use `Literal` for constrained string choices

## 3. Write tests

Test: valid creation, required field enforcement, field validation, cross-field validation, serialization round-trip (`model_dump()` → `model_validate()`).

## 4. Run and verify

```bash
uv run pytest tests/test_<module>_models.py -v
```

# Pydantic v2 quick reference

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class MyModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    name: str = Field(..., min_length=1)
    value: float = Field(..., gt=0)

    @field_validator('name')
    @classmethod
    def name_uppercase(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode='after')
    def check_consistency(self) -> 'MyModel':
        # cross-field validation
        return self
```

# Reference files

| Purpose         | File                                   |
| --------------- | -------------------------------------- |
| Trading models  | `src/alpacalyzer/data/models.py`       |
| Strategy config | `src/alpacalyzer/strategies/config.py` |
| Event models    | `src/alpacalyzer/events/models.py`     |
| Execution state | `src/alpacalyzer/execution/state.py`   |
