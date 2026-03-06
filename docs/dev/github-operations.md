# GitHub Operations

Use `gh` CLI for all GitHub operations. For long body text, use `--body-file -` to pipe via stdin (avoids ARG_MAX issues with custom shell prompts like Starship).

## Getting Repo Info

Always get repo info first:

```bash
git remote get-url origin
# Parse: owner = "kimrejstrom", repo = "alpacalyzer-algo-trader"
```

**Never hardcode** owner/repo values. Always parse from git remote.

## Issue Management

### Read Issue

```bash
gh issue view <issue_number> --repo <owner>/<repo>
```

### Create Issue

```bash
gh issue create --repo <owner>/<repo> --title "title" --body-file - <<'EOF'
Issue body here (supports markdown)
EOF
```

### Close Issue

```bash
gh issue close <issue_number> --repo <owner>/<repo>
```

## Pull Requests

### Create PR

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

### Update PR

```bash
gh pr edit <pr_number> --repo <owner>/<repo> --title "new title" --body-file - <<'EOF'
Updated body
EOF
```

### Merge PR

```bash
gh pr merge <pr_number> --repo <owner>/<repo> --squash
```

### View PR

```bash
gh pr view <pr_number> --repo <owner>/<repo>
gh pr diff <pr_number> --repo <owner>/<repo>
gh pr view <pr_number> --repo <owner>/<repo> --json files
```

## Branch Management

### Create Branch

```bash
git checkout -b <branch_name>
# or from a specific base
git checkout -b <branch_name> <from_branch>
```

## Repository Operations

### Fork Repository

```bash
gh repo fork <owner>/<repo>
```

### Get Latest Release

```bash
gh release view --repo <owner>/<repo>
```

## Search

### Search Issues

```bash
gh issue list --repo <owner>/<repo> --search "query"
```

### Search PRs

```bash
gh pr list --repo <owner>/<repo> --search "query"
```

### Search Code

```bash
gh search code "query" --repo <owner>/<repo>
```
