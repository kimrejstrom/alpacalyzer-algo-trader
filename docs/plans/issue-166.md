# Plan: Issue #166 — Add TradeDecisionRecord and DecisionContext Pydantic models for journal sync

## Goal

Create Pydantic models that aggregate data from multiple events into a single structured record per trade for syncing to the journal app.

## Acceptance Criteria

- [x] Models defined in `src/alpacalyzer/sync/models.py`
- [x] All fields use types compatible with JSON serialization
- [x] Prices are decimal strings (matching journal's `Decimal.js` format)
- [x] Dates are ISO 8601 strings
- [x] Tests pass

## Files to Modify

| File                               | Change                       |
| ---------------------------------- | ---------------------------- |
| `src/alpacalyzer/sync/__init__.py` | Create empty init file       |
| `src/alpacalyzer/sync/models.py`   | Create three Pydantic models |
| `tests/sync/test_models.py`        | Create tests for the models  |

## Test Scenarios

| Scenario                                     | Expected                                   |
| -------------------------------------------- | ------------------------------------------ |
| Create AgentSignalRecord with all fields     | Valid model with all fields                |
| Create AgentSignalRecord with minimal fields | Valid model with optional fields as None   |
| Create DecisionContext with agent_signals    | Valid model with list of AgentSignalRecord |
| Create TradeDecisionRecord with all fields   | Valid model with complete trade data       |
| Serialize to JSON                            | Valid JSON with string prices/dates        |
| Deserialize from JSON                        | Valid model restored                       |
| Default values for optional fields           | None for optional fields                   |

## Risks

- None identified - this is a pure data modeling task with straightforward requirements.
