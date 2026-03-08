# Alpacalyzer Documentation

## Quick Links

- [AGENTS.md](../AGENTS.md) - AI Agent instructions (start here for agents)
- [README.md](../README.md) - Project overview and setup

## Architecture

- [Architecture Overview](architecture/overview.md) - Domain map, layering, import rules
- [ADRs](architecture/decisions/) - Architecture decision records

## Development Procedures

- [TDD Workflow](dev/tdd-flow.md) - Test-driven development process
- [Commit Conventions](dev/commit-conventions.md) - Commit format, branch naming
- [Debugging](dev/debugging.md) - Debugging procedures
- [Debugging Guide](dev/debugging-guide.md) - Hypothesis-driven debugging for complex bugs
- [GitHub Operations](dev/github-operations.md) - `gh` CLI usage
- [Testing](dev/testing.md) - Test structure and patterns
- [Common Mistakes](dev/common-mistakes.md) - Recurring agent errors and fixes
- [Parallel Exploration](dev/parallel-exploration.md) - Running multiple agents on the same problem

## Orchestrator

- [Parallel Issue Orchestrator](dev/tdd-flow.md#parallel-issue-orchestrator) - Batch issue execution with dependency resolution
- `scripts/orchestrate.sh` - Main orchestrator script (discovery → waves → dispatch → monitor → merge)
- `scripts/issue-preflight.sh` - Single-issue validation and Agent Metadata parsing
- `scripts/wti.sh` - Portable worktree issue start (extracted from zshrc)
- `scripts/wtr.sh` - Portable worktree issue remove (extracted from zshrc)
- `.github/ISSUE_TEMPLATE/feature-task.md` - Issue template with Agent Metadata table
- `.agents/orchestrator-log.jsonl` - Orchestrator event log (gitignored)

## Plans

- [Plans Index](plans/INDEX.md) - Active, completed, and backlog plans
- [Plan Template](templates/plan-template.md) - Template for new issue plans

## Commands

- `/plan-feature <description>` — Decompose a feature into agent-sized issues with dependency ordering ([source](../.agents/commands/plan-feature.md))
- `/start-issue <number>` — Start work on a GitHub issue ([source](../.agents/commands/start-issue.md))
- `/create-pr` — Create a pull request after completing work ([source](../.agents/commands/create-pr.md))
- `/fix-issue <number>` — Quick-fix an issue with TDD ([source](../.agents/commands/fix-issue.md))

## Enforcement & Automation

- [Golden Principles](principles.md) - Code invariants that must be upheld
- `scripts/lint_architecture.py` - Architecture boundary linter (import rules, stop_loss enforcement)
- `scripts/validate_docs.py` - Doc cross-reference validation
- `scripts/audit_principles.py` - Golden principles audit (raw HTTP, typed events, boundary validation)
- `.agents/config.yaml` - Shared grind loop config (max iterations, stall/idle timeouts)
- `.agents/hooks/check-completion.sh` - Grind loop completion checker with structured JSON output, idle/stuck detection, session logging
- `.agents/hooks/check-plan-exists.sh` - Plan-first workflow enforcement (Claude PreToolUse hook)
- `.agents/hooks/opencode-grind-loop.sh` - Bash grind loop wrapper with stall timeout (headless/CI)
- `.opencode/plugins/grind-loop.ts` - OpenCode grind loop plugin (session.idle → re-prompt, stall timer)
- `.opencode/plugins/plan-first.ts` - OpenCode plan-first plugin (tool.execute.before → block writes)
- `.agents/scratchpad.md` - Structured agent state tracking (STATUS, CURRENT_FOCUS, COMPLETED items)
- `.agents/session-log.jsonl` - Per-iteration session log for post-hoc observability (gitignored)

## Skills

See `.agents/skills/` for specialized skills:

| Task                        | Skill File                     |
| --------------------------- | ------------------------------ |
| Decompose feature           | `issue-decomposition/SKILL.md` |
| Create new hedge fund agent | `new-agent/SKILL.md`           |
| Create new data scanner     | `new-scanner/SKILL.md`         |
| Create trading strategy     | `new-strategy/SKILL.md`        |
| Add technical indicator     | `technical-indicator/SKILL.md` |
| Work with GPT/prompts       | `gpt-integration/SKILL.md`     |
| Create Pydantic models      | `pydantic-model/SKILL.md`      |
| Modify execution engine     | `execution/SKILL.md`           |
| Observability               | `observability/SKILL.md`       |
| Validate end-to-end         | `validate-e2e/SKILL.md`        |
