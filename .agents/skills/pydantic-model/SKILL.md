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
