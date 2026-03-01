# Plan: Issue #168 — Add JournalSyncHandler and wire into EventEmitter

## Goal

Implement an `EventHandler` that listens to the trading event stream, accumulates context per-ticker during analysis, and syncs `TradeDecisionRecord` payloads to my-stock-journal on entry/exit events.

## Acceptance Criteria

- [ ] Handler accumulates `AgentReasoningEvent`, `SignalGeneratedEvent`, `LLMCallEvent` per-ticker
- [ ] Entry events trigger sync with full `DecisionContext`
- [ ] Exit events trigger sync with exit data and WIN/LOSS status
- [ ] Context buffer cleared after successful sync
- [ ] Handler never crashes — all exceptions caught
- [ ] Handler registered only when `JOURNAL_API_URL` is set
- [ ] `.env.example` updated with new env vars
- [ ] Tests pass

## Files to Modify

| File                               | Change                                |
| ---------------------------------- | ------------------------------------- |
| `src/alpacalyzer/sync/handler.py`  | New file - JournalSyncHandler         |
| `src/alpacalyzer/sync/__init__.py` | Export JournalSyncHandler             |
| `src/alpacalyzer/cli.py`           | Wire handler when JOURNAL_API_URL set |
| `.env.example`                     | Already present (added in #167)       |

## Test Scenarios

| Scenario                          | Expected                                         |
| --------------------------------- | ------------------------------------------------ |
| AgentReasoningEvent accumulation  | `_pending_context[ticker].agent_signals` updated |
| SignalGeneratedEvent accumulation | Strategy, confidence, reasoning stored           |
| LLMCallEvent accumulation         | LLM cost data appended to ticker context         |
| EntryTriggeredEvent               | TradeDecisionRecord synced, context cleared      |
| ExitTriggeredEvent                | Update record with exit data, WIN/LOSS status    |
| PositionClosedEvent               | Same as ExitTriggeredEvent                       |
| Client error                      | Handler logs warning, doesn't crash              |
| Empty context on entry            | Syncs with empty DecisionContext                 |
| No JOURNAL_API_URL                | Handler NOT registered                           |

## Risks

- None identified - this is an opt-in feature with error resilience built in
