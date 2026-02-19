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

# 6. Create PR using GitHub MCP tools
```

## Completing a Feature

1. **Ensure all tests pass**

   ```bash
   uv run pytest tests
   ```

2. **Run linting and type checking**

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run ty check src
   ```

3. **Push changes and create PR** using GitHub MCP tools

4. **Run automated code review** (MANDATORY):

   ```
   @code-reviewer Please review:
   - ISSUE_NUMBER: <issue_number>
   - PR_NUMBER: <pr_number>
   - OWNER: <repo_owner>
   - REPO: <repo_name>
   - FEATURE_DESCRIPTION: <brief description>
   ```

5. **Address any Critical/High issues** found in `CODE_REVIEW_<ISSUE>.md`

6. **Reply with completion message**:
   ```
   Feature #XX ready for review. PR url: {PR_URL}, also see _PLAN_issue-XX.md for details
   ```

## Closing a Pull Request

When the feature is approved and ready to merge:

1. **Review docs impact**: Update README.md or AGENTS.md if the change affects setup or architecture
2. **Merge PR**: Use GitHub MCP tools to squash merge (auto-closes linked issue)
3. **Highlight future work**: Call out any follow-ups or ideas discovered during implementation, ask user whether each should be tracked as a new GitHub issue
4. **Notify user**: Tell the user the PR is merged and they can remove the worktree:
   ```
   PR merged! You can now close this IDE window and run `wt remove` from the main worktree.
   ```
