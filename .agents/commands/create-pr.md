# Create PR Command

Create a pull request after completing feature work.

## Usage

```
/create-pr
```

## Argument Indexing

- **Claude Code**: No arguments needed
- **OpenCode**: No arguments needed

## Steps

### 1. Run Tests

```bash
uv run pytest tests -x -q
```

### 2. Run Linting

```bash
uv run ruff check .
uv run ruff format .
```

### 3. Run Type Checking

```bash
uv run ty check src
```

### 4. Get Repo Info

```bash
git remote get-url origin
```

Parse owner and repo name.

### 5. Check Changes

```bash
git status
git diff --cached
```

### 6. Commit if Needed

If there are uncommitted changes:

```bash
git add -A
git commit -m "feat(scope): description for #XX"
```

### 7. Push Branch

```bash
git push -u origin feature/issue-XX-description
```

### 8. Create PR

Use `gh` CLI:

```bash
gh pr create --repo <owner>/<repo> \
  --title "feat(scope): description for #XX" \
  --head feature/issue-XX-description \
  --base main \
  --body-file - <<'EOF'
## Summary
<description>

## Issue
Closes #XX
EOF
```

### 9. Trigger Code Review

```
@code-reviewer Please review:
- ISSUE_NUMBER: <issue_number>
- PR_NUMBER: <pr_number>
- OWNER: <owner>
- REPO: <repo>
- FEATURE_DESCRIPTION: <brief description>
```

### 10. Report Completion

Reply to user:

```
Feature #XX ready for review. PR url: {PR_URL}, also see docs/plans/_PLAN_issue-XX.md for details
```

## Notes

- Ensure all tests pass before creating PR
- Include issue number in commit message and PR title
- Always trigger code review (mandatory)
