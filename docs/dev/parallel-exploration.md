# Parallel Exploration Pattern

When facing hard problems or architectural decisions, run multiple agents on the same issue simultaneously and compare results.

## When to Use

- Architectural decisions with multiple valid approaches
- Complex bugs where the root cause is unclear
- Performance optimization with competing strategies
- Any problem where you want to compare agent reasoning

## Setup

The existing worktree infrastructure supports this natively. Create multiple worktrees for the same issue:

```bash
# Terminal 1: Claude Code
wti 66 -c

# Terminal 2: OpenCode
wti 66 -o
```

Both agents work independently on the same issue in isolated worktrees.

## Comparing Results

After both agents finish:

1. Review each worktree's changes: `git diff main` in each
2. Compare test coverage and passing rates
3. Read each agent's plan file in `docs/plans/`
4. Check code review findings (`CODE_REVIEW_*.md`)
5. Pick the better approach — or cherry-pick the best parts from each

## Cleanup

Keep the winning worktree, remove the rest:

```bash
# Remove the losing worktree
wtr 66  # removes the worktree for issue 66
```

## Tips

- Give both agents the same prompt for a fair comparison
- Don't let one agent see the other's work — that defeats the purpose
- For truly hard problems, try 3 worktrees: Claude Code, OpenCode, and a manual approach
- Document which approach won and why in the issue comments — this builds institutional knowledge
