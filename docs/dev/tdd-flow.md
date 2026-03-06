# TDD Workflow

## Standard TDD Flow

```bash
# 1. Write test in tests/
# Example: tests/test_momentum_strategy.py

# 2. Verify test fails
uv run pytest tests/test_momentum_strategy.py -v

# 3. Implement minimal code to pass
# Example: src/alpacalyzer/strategies/momentum.py

# 4. Verify test passes
uv run pytest tests/test_momentum_strategy.py -v

# 5. Commit
git add tests/test_momentum_strategy.py src/alpacalyzer/strategies/momentum.py
git commit -m "feat(strategies): implement momentum strategy for #XX"

# 6. Create PR using gh CLI
```

## Completing a Feature

Run `/create-pr` — it handles tests, lint, typecheck, commit, push, PR creation, and code review trigger in one shot.

See [`.agents/commands/create-pr.md`](../../.agents/commands/create-pr.md) for the full step-by-step breakdown.

## Grind Loop (Iterate-Until-Done)

Both Claude Code and OpenCode support automated iteration loops that re-prompt the agent until all completion criteria are met.

### Configuration

All grind loop settings live in `.agents/config.yaml`:

```yaml
grind_loop:
  max_iterations: 5
  stall_timeout_seconds: 300 # 5 min — kills hung agents
  idle_timeout_seconds: 120 # 2 min — re-prompts stopped agents
  session_log: .agents/session-log.jsonl
```

All three implementations (Claude hook, OpenCode plugin, bash wrapper) read from this file.

### Claude Code

Enforcement is automatic via hooks in `.claude/settings.local.json`:

- `Stop` hook runs `.agents/hooks/check-completion.sh` after each agent turn
- `PreToolUse` hook runs `.agents/hooks/check-plan-exists.sh` before any Write/Edit

No manual setup needed — hooks fire automatically.

### OpenCode

Enforcement is automatic via plugins in `.opencode/plugins/`:

- `grind-loop.ts` — listens to `session.idle` events, runs `check-completion.sh`, re-prompts if incomplete, and runs a stall timer that fires if the agent goes silent for `stall_timeout_seconds`
- `plan-first.ts` — intercepts `tool.execute.before` on write/edit tools and blocks code writes until a plan file exists in `docs/plans/`

Plugins are loaded automatically by OpenCode at startup. No manual setup needed.

Fallback: `.agents/hooks/opencode-grind-loop.sh` wraps `opencode --prompt` in a bash loop with `timeout` for stall protection. Used for headless/CI.

### Completion Criteria (shared)

Both tools use `.agents/hooks/check-completion.sh` which checks:

1. Tests pass (`uv run pytest tests`)
2. No Critical/High findings in `CODE_REVIEW_*.md`
3. Blind review requested if PR exists but no review file (non-trivial PRs only)
4. Scratchpad signals DONE (`.agents/scratchpad.md`)
5. Agent idle detection — if scratchpad says IN_PROGRESS with unchecked items, re-prompts the agent
6. Stuck detection — if the same CURRENT_FOCUS appears across 2+ iterations, suggests a different approach
7. Iteration cap (configurable, default 5) prevents infinite loops

Output is structured JSON with `followup_prompt`, `checks`, and `context` fields. Each iteration is logged to `.agents/session-log.jsonl` for post-hoc observability.

### Scratchpad

The agent should maintain `.agents/scratchpad.md` during work:

```markdown
## STATUS: IN_PROGRESS

## ITERATION: 2/5

## STARTED_AT: 2026-03-05T14:30:00Z

## COMPLETED

- [x] Plan file created
- [x] Tests written
- [ ] Implementation done
- [ ] Code review passed

## CURRENT_FOCUS

Implementing the FooBar component per test_foo.py

## PREVIOUS_ATTEMPTS

- Iteration 1: Wrote tests, started implementation. Stopped due to LLM timeout.

## BLOCKERS

None
```

The grind loop reads this to build context-aware re-prompts and detect stuck loops.

### Stall & Idle Protection

| Scenario                          | Detection                                                                   | Action                                            |
| --------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------- |
| Agent stuck (no output for 5 min) | Bash: `timeout` command. OpenCode: stall timer in plugin.                   | Kill/re-prompt with "try a different approach"    |
| Agent stopped but not done        | `check-completion.sh` idle check (scratchpad IN_PROGRESS + unchecked items) | Re-prompt with scratchpad context                 |
| Same task stuck across iterations | Session log analysis (same CURRENT_FOCUS 2+ times)                          | Escalated re-prompt suggesting different approach |
| Max iterations reached            | Iteration counter in all implementations                                    | Stop gracefully                                   |

## Parallel Issue Orchestrator

For batch execution of multiple issues, use `scripts/orchestrate.sh`. It replaces the human-in-the-loop for starting worktrees, monitoring agent progress, and handling auto-merge.

### Quick Start

```bash
# Run all issues with the orchestrator-ready label
scripts/orchestrate.sh --label orchestrator-ready

# Run specific issues
scripts/orchestrate.sh --issues 101,102,103

# Dry run — show wave plan without launching agents
scripts/orchestrate.sh --dry-run --label orchestrator-ready

# Limit parallelism
scripts/orchestrate.sh --max-parallel 2 --issues 101,102
```

### How It Works

1. Fetches open issues (by label or explicit list)
2. Runs `scripts/issue-preflight.sh` on each to parse Agent Metadata and check dependencies
3. Topological sort → groups issues into waves (respects `Depends on` and `Parallel safe`)
4. Per wave: creates worktrees via `wti.sh --setup-only`, launches agents, monitors via polling
5. Auto-merge eligible PRs (`Auto-merge: yes` in issue metadata) once CI is green and PR is mergeable
6. Updates local main between waves so the next wave branches from latest

### Issue Metadata

Every issue should have an Agent Metadata table (enforced by the GitHub issue template):

```markdown
| Field                | Value    |
| -------------------- | -------- |
| Depends on           | #none    |
| Parallel safe        | yes      |
| Auto-merge           | no       |
| Agent tool           | opencode |
| Estimated complexity | small    |
```

The orchestrator parses this to decide ordering, parallelism, and merge behavior. Missing metadata defaults to safe values (`parallel_safe: true, auto_merge: false, agent_tool: opencode`).

### What the Orchestrator Does NOT Do

- Own the grind loop (that's `grind-loop.ts` / `check-completion.sh`)
- Resolve merge conflicts (that's the agent's job within its worktree)
- Run code review (that's the code-reviewer subagent, triggered by the agent)
- Retry failed sessions (flags for human intervention)

Config lives in `.agents/config.yaml` under the `orchestrator:` section. Logs go to `.agents/orchestrator-log.jsonl`.

See [plan-parallel-orchestrator.md](../plans/plan-parallel-orchestrator.md) for full design details.

## Closing a Pull Request

When the feature is approved and ready to merge:

1. **Review docs impact**: Update README.md or AGENTS.md if the change affects setup or architecture
2. **Merge PR**: Use `gh pr merge <pr_number> --repo <owner>/<repo> --squash` (auto-closes linked issue)
3. **Highlight future work**: Call out any follow-ups or ideas discovered during implementation, ask user whether each should be tracked as a new GitHub issue
4. **Notify user**: Tell the user the PR is merged and they can remove the worktree:
   ```
   PR merged! You can now close this IDE window and run `wt remove` from the main worktree.
   ```
