# Technical Debt Tracker

Items tracked here are known issues that don't warrant their own GitHub issue yet but should be addressed when touching nearby code.

## Active

| Area       | Debt                                                                                                                                                   | Impact                                                       | Added      |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------ | ---------- |
| Strategies | BreakoutStrategy and MeanReversionStrategy don't use agent recommendations ([#162](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/162)) | Limits agent-propose/validate model to MomentumStrategy only | 2026-02-21 |

## Resolved

| Area   | Debt                                                                                   | Resolution                                                                               | Resolved   |
| ------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------- |
| Audit  | `audit_principles.py` flagged data/scanners as violations — they ARE the typed clients | Whitelisted `data/`, `scanners/`, `trading/` dirs in audit checks                        | 2026-02-21 |
| CLI    | `main()` is `pragma: no cover` — no structured test path for CLI flags                 | Extracted `_run_dry_run()` as testable function, added 4 tests in `test_cli_dry_run.py`  | 2026-02-21 |
| CLI    | `--tickers` flag caused double analysis run (scan+analyze ran twice)                   | Guarded second `safe_execute(analyze(scan()))` behind `if not direct_tickers`            | 2026-02-21 |
| Events | `events.jsonl` grows unbounded — no rotation or archival                               | Added size-based rotation to `FileEventHandler` (10MB default, 3 backups), added 3 tests | 2026-02-21 |
| UI     | `AgentProgress._refresh_display` appended rows without clearing (Rich Table bug)       | Create fresh `Table` per refresh, use `live.update(table)` instead of mutating in-place  | 2026-02-21 |
