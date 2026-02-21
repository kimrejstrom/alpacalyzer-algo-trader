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
- [GitHub Operations](dev/github-operations.md) - GitHub MCP tools usage
- [Testing](dev/testing.md) - Test structure and patterns
- [Common Mistakes](dev/common-mistakes.md) - Recurring agent errors and fixes

## Plans

- [Plans Index](plans/INDEX.md) - Active, completed, and backlog plans
- [Plan Template](templates/plan-template.md) - Template for new issue plans

## Enforcement & Automation

- `scripts/lint_architecture.py` - Architecture boundary linter (import rules, stop_loss enforcement)
- `scripts/validate_docs.py` - Doc cross-reference validation
- `.agents/hooks/check-completion.sh` - Grind loop completion checker (shared by Claude + OpenCode)
- `.agents/hooks/check-plan-exists.sh` - Plan-first workflow enforcement (Claude PreToolUse hook)
- `.opencode/plugins/grind-loop.ts` - OpenCode grind loop plugin (session.idle → re-prompt)
- `.opencode/plugins/plan-first.ts` - OpenCode plan-first plugin (tool.execute.before → block writes)

## Skills

See `.agents/skills/` for specialized skills:

| Task                        | Skill File                     |
| --------------------------- | ------------------------------ |
| Create new hedge fund agent | `new-agent/SKILL.md`           |
| Create new data scanner     | `new-scanner/SKILL.md`         |
| Create trading strategy     | `new-strategy/SKILL.md`        |
| Add technical indicator     | `technical-indicator/SKILL.md` |
| Work with GPT/prompts       | `gpt-integration/SKILL.md`     |
| Create Pydantic models      | `pydantic-model/SKILL.md`      |
| Modify execution engine     | `execution/SKILL.md`           |
| Observability               | `observability/SKILL.md`       |
