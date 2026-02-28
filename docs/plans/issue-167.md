# Plan: Issue #167 — Add JournalSyncClient HTTP Client

## Goal

Create an HTTP client (`JournalSyncClient`) that sends `TradeDecisionRecord` payloads to the my-stock-journal app's sync endpoint with retry logic, timeout handling, and failure logging.

## Acceptance Criteria

- [x] Client POSTs `TradeDecisionRecord` JSON to journal API
- [x] `X-API-Key` header set on all requests
- [x] Retry with exponential backoff (3 attempts) on 5xx/connection errors
- [x] 10s request timeout
- [x] Failed syncs logged to `logs/sync_failures.jsonl`
- [x] Never raises exceptions — all errors caught and logged
- [x] Tests pass with mocked HTTP

## Files to Create

| File                             | Change                        |
| -------------------------------- | ----------------------------- |
| `src/alpacalyzer/sync/client.py` | New `JournalSyncClient` class |
| `tests/sync/test_client.py`      | Tests for the client          |

## Files to Modify

| File                               | Change                                           |
| ---------------------------------- | ------------------------------------------------ |
| `src/alpacalyzer/sync/__init__.py` | Export `JournalSyncClient`                       |
| `.env.example`                     | Add `JOURNAL_API_URL` and `JOURNAL_SYNC_API_KEY` |

## Test Scenarios

| Scenario         | Expected                                                              |
| ---------------- | --------------------------------------------------------------------- |
| Successful sync  | Returns parsed response JSON                                          |
| 5xx error        | Retries 3 times with exponential backoff                              |
| 4xx error        | No retry, returns None                                                |
| Timeout          | Returns None, logs failure                                            |
| Connection error | Retries 3 times, logs failure on final attempt                        |
| Failure logged   | `logs/sync_failures.jsonl` contains timestamp, ticker, error, payload |

## Risks

- Network failures don't impact trading loop — mitigated by catching all exceptions
- Log file may grow unbounded — mitigated by JSONL format (append-only)
