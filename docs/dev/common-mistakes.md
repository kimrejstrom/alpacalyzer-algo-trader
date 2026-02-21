# Common Agent Mistakes

Recurring errors observed during agent-driven development. Add new entries when an agent makes the same mistake twice.

## Trading Safety

- **Missing stop_loss on entry**: Every `EntryDecision(should_enter=True)` must include `stop_loss`. The architecture linter (`scripts/lint_architecture.py`) enforces this.
- **Real orders in tests**: Always use `analyze_mode=True` and mock the Alpaca API. Never submit real orders during testing.

## Architecture

- **Cross-layer imports**: Strategies must not import from agents, scanners, or orchestrator. See `docs/architecture/overview.md` for allowed import directions. The architecture linter catches these.
- **Inline templates in skills**: Reference existing files instead of copying code into skill files. Skills should be <100 lines.

## Testing

- **Running full test suite repeatedly**: Run the specific test file, save output, analyze. Don't re-run the full suite to debug.
- **Not mocking external APIs**: All external calls (Alpaca, OpenAI, Reddit) must be mocked in tests.

## Git / Workflow

- **Hardcoding repo owner/name**: Always derive from `git remote get-url origin`.
- **Starting a new issue in the same session**: One worktree = one issue = one session.
