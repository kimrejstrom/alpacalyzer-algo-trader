# Fix Issue Command

Fetch issue details, find relevant code, implement fix, and open PR.

## Usage

```
/fix-issue <issue_number>
```

**Arguments:**

- `issue_number`: The GitHub issue number to fix

## Argument Indexing

- **Claude Code**: Use `$1` for the first argument (issue number)
- **OpenCode**: Use `$ARGUMENTS` to get all arguments

## Steps

### 1. Get Repo Info

```bash
git remote get-url origin
```

Parse owner and repo name.

### 2. Fetch Issue

Use GitHub MCP tools to fetch the issue:

```
mcp_io_github_git_issue_read(owner, repo, issue_number, method="get")
```

### 3. Analyze Issue

Read the issue description:

- What needs to be fixed?
- What are the acceptance criteria?
- Are there any hints about where the code lives?

### 4. Find Relevant Code

Search for relevant code:

```bash
# Search for keywords
rg "keyword" src/

# Find test files
ls tests/test_*.py
```

### 5. Create Branch

```bash
git checkout -b fix/issue-<issue_number>-<short-description>
```

### 6. Write Test First

Create test that reproduces the issue:

```python
def test_bug_fix():
    """Test for issue #XX"""
    # Test that demonstrates the bug
    pass
```

Run test to confirm it fails.

### 7. Implement Fix

Implement the fix to make the test pass.

### 8. Run Tests

```bash
uv run pytest tests -x -q
```

### 9. Run Linting

```bash
uv run ruff check .
uv run ruff format .
```

### 10. Run Type Checking

```bash
uv run ty check src
```

### 11. Commit

```bash
git add -A
git commit -m "fix(scope): description for #XX"
```

### 12. Push and Create PR

```bash
git push -u origin fix/issue-XX-description
```

```
mcp_io_github_git_create_pull_request(
    owner="<owner>",
    repo="<repo>",
    title="fix(scope): description for #XX",
    body="## Summary\n<description>\n\n## Issue\nFixes #XX",
    head="fix/issue-XX-description",
    base="main"
)
```

### 13. Trigger Code Review

```
@code-reviewer Please review:
- ISSUE_NUMBER: <issue_number>
- PR_NUMBER: <pr_number>
- OWNER: <owner>
- REPO: <repo>
- FEATURE_DESCRIPTION: <brief description>
```

## Notes

- Use `fix/` prefix for bug fix branches
- Always write test first (TDD)
- Include issue number in commit and PR
