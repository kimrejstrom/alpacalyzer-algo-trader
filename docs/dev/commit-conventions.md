# Commit Conventions

## Commit Message Format

Follow conventional commits with **single-line format only** (avoids terminal issues):

```bash
# ✅ GOOD - single line
git commit -m "feat(strategies): implement momentum strategy for #XX"

# ❌ BAD - multi-line causes issues
git commit -m "feat(strategies): implement momentum strategy

This adds..."
```

## Commit Types

- `feat(scope): add momentum strategy for #XX`
- `fix(agents): correct sentiment analysis bug for #XX`
- `docs(readme): update architecture diagram for #XX`
- `test(strategies): add breakout strategy tests for #XX`
- `refactor(execution): simplify signal queue logic for #XX`
- `chore(deps): update alpaca-py to latest for #XX`

## Branch Naming

Format: `feature/issue-XX-short-description`

Examples:

- `feature/issue-4-strategy-config`
- `feature/issue-17-event-models`
- `fix/issue-42-memory-leak`

## Pre-Commit Checklist

Before every commit:

- [ ] GitHub issue exists and referenced (`#XX`)
- [ ] Test written BEFORE implementation
- [ ] All tests pass (`uv run pytest tests`)
- [ ] Linting clean (`uv run ruff check .`)
- [ ] Formatting applied (`uv run ruff format .`)
- [ ] Type checking passes (`uv run ty check src`)
- [ ] Commit follows conventional format
- [ ] No hardcoded secrets (check for API keys, tokens)
- [ ] Single focused change only
