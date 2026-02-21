# Plan: Issues #150–#155 — Wave 3 Harness Engineering Upgrade

## Goal

Implement all 6 Wave 3 tasks: structured JSON CLI output, golden principles + audit script, plans restructuring, doc-gardening workflow, parallel exploration docs, and hypothesis-driven debugging guide.

## Acceptance Criteria

See individual issues #150–#155.

## Files to Modify

| File                                   | Change                                        |
| -------------------------------------- | --------------------------------------------- |
| `src/alpacalyzer/cli.py`               | Add `--dry-run` and `--json` flags (#150)     |
| `.agents/skills/validate-e2e/SKILL.md` | New validate-e2e skill (#150)                 |
| `docs/principles.md`                   | New golden principles doc (#151)              |
| `scripts/audit_principles.py`          | New audit script (#151)                       |
| `.github/workflows/doc-gardening.yml`  | New scheduled workflow (#153)                 |
| `docs/dev/parallel-exploration.md`     | New parallel exploration guide (#154)         |
| `docs/dev/debugging.md`                | Expand with hypothesis-driven approach (#155) |
| `docs/plans/INDEX.md`                  | Update with tech-debt tracking (#152)         |
| `.gitignore`                           | Ensure docs/plans/ not ignored (#152)         |
| `docs/INDEX.md`                        | Add pointers to new docs                      |
| `AGENTS.md`                            | Add pointers to new docs                      |

## Risks

- CLI `--dry-run --json` touches production code path — keep changes minimal and behind flag
