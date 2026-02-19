# Start Issue Command

Start work on a GitHub issue.

## Usage

```
/start-issue <issue_number>
```

**Arguments:**

- `issue_number`: The GitHub issue number to work on

## Argument Indexing

- **Claude Code**: Use `$1` for the first argument (issue number)
- **OpenCode**: Use `$ARGUMENTS` to get all arguments

## Steps

### 1. Get Repo Info

```bash
git remote get-url origin
```

Parse owner and repo name from the output.

### 2. Fetch Issue

Use GitHub MCP tools to fetch the issue:

```
mcp_io_github_git_issue_read(owner, repo, issue_number, method="get")
```

### 3. Verify/Create Branch

Check current branch:

```bash
git branch --show-current
```

If not on correct branch, create one:

```bash
git checkout -b feature/issue-<issue_number>-<short-description>
```

Branch naming: `feature/issue-{issue_number}-{short-description}`

### 4. Create Plan File

Create `docs/plans/_PLAN_issue-{issue_number}.md` with:

```
# Plan: {issue_title}

## Issue
#{issue_number}

## Acceptance Criteria
- [ ]

## Tasks
- [ ]

## Notes
```

### 5. Scaffold Test File

Create test file in `tests/`:

```
tests/test_issue_{issue_number}.py
```

With basic test structure:

```python
import pytest

def test_placeholder():
    """Placeholder test for issue #{issue_number}"""
    assert True
```

### 6. Verify Tests Run

```bash
uv run pytest tests/test_issue_{issue_number}.py -v
```

## Notes

- This command is for starting NEW work on an issue
- If work is already in progress, skip this command
- Ensure you're on the correct branch before starting
