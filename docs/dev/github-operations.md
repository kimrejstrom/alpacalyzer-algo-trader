# GitHub Operations

Use GitHub MCP tools instead of `gh` CLI for all GitHub operations.

## Getting Repo Info

Always get repo info first:

```bash
git remote get-url origin
# Parse: owner = "kimrejstrom", repo = "alpacalyzer-algo-trader"
```

**Never hardcode** owner/repo values. Always parse from git remote.

## Issue Management

### Read Issue

```
mcp_io_github_git_issue_read(owner, repo, issue_number, method="get")
```

Parameters:

- `owner`: Repository owner (from git remote)
- `repo`: Repository name (from git remote)
- `issue_number`: Issue number
- `method`: "get"

### Create Issue

```
mcp_io_github_git_issue_write(method="create", owner, repo, title, body)
```

### Update Issue

```
mcp_io_github_git_issue_write(method="update", owner, repo, issue_number, state="closed")
```

## Pull Requests

### Create PR

```
mcp_io_github_git_create_pull_request(owner, repo, title, body, head, base)
```

### Update PR

```
mcp_io_github_git_update_pull_request(owner, repo, pullNumber, ...)
```

### Merge PR

```
mcp_io_github_git_merge_pull_request(owner, repo, pullNumber, merge_method="squash")
```

## Branch Management

### Create Branch

```
mcp_io_github_git_create_branch(branch, owner, repo, from_branch)
```

## Repository Operations

### Fork Repository

```
mcp_io_github_git_fork_repository(owner, repo)
```

### Get Latest Release

```
mcp_io_github_git_get_latest_release(owner, repo)
```

## Search

### Search Issues

```
mcp_io_github_git_search_issues(query, owner, repo)
```

### Search PRs

```
mcp_io_github_git_search_pull_requests(query, owner, repo)
```

### Search Code

```
mcp_io_github_git_search_code(query)
```
