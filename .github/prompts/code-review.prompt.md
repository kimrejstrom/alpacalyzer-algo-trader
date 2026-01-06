# Code Review Prompt Template

Use this template to generate structured code reviews for Alpacalyzer PRs.

## Purpose

This prompt guides structured code reviews for agent-generated pull requests, ensuring consistency, safety, and alignment with project goals.

## Input Requirements

Before running this prompt, gather:

1. **PR Details**:

   - PR number and title
   - Issue reference (`#XX`)
   - Changed files list
   - Diff summary

2. **Test Results**:

   - CI status (lint, typecheck, tests)
   - Coverage report (if available)
   - Test output for new tests

3. **Context**:
   - Related migration phase (if applicable)
   - Dependencies or breaking changes
   - Performance implications

## Review Prompt

```markdown
You are conducting a code review for Alpacalyzer Algo Trader, an algorithmic trading platform.

## PR Information

- **PR**: #[NUMBER] - [TITLE]
- **Issue**: #[ISSUE_NUMBER]
- **Author**: [AUTHOR]
- **Branch**: [BRANCH_NAME]
- **Changed Files**: [FILE_COUNT] files, [LINE_CHANGES] lines

## Files Changed

[LIST_FILES_WITH_CHANGES]

## CI Status

- Lint: [PASS/FAIL]
- Typecheck: [PASS/FAIL]
- Tests: [PASS/FAIL - X/Y passing]

## Review Focus

Conduct a thorough code review following `.github/instructions/code-review.instructions.md`.

Pay special attention to:

1. **Trading Logic Safety**: Verify entry/exit conditions, position sizing, stop loss
2. **Test Coverage**: Ensure all code paths tested, mocks used for APIs
3. **Type Safety**: Check for proper type hints, no loose `Any` types
4. **Security**: No hardcoded secrets, proper validation
5. **Migration Alignment**: Changes align with migration_roadmap.md phases

## Automated Checks

Run through:

- [ ] Issue reference present?
- [ ] Tests added for new code?
- [ ] CI passing?
- [ ] One focused change?
- [ ] No hardcoded secrets?
- [ ] Trading logic has stop loss?
- [ ] External APIs mocked?

## Deep Dive

For each changed file:

1. **Purpose**: What does this change accomplish?
2. **Correctness**: Does it achieve the goal correctly?
3. **Tests**: Are tests sufficient and correct?
4. **Safety**: Any trading/security risks?
5. **Quality**: Code clarity, naming, structure?

## Trading Logic Validation

If trading logic changed:

- [ ] Entry conditions prevent duplicate positions?
- [ ] Position sizing respects limits?
- [ ] Stop loss ALWAYS set?
- [ ] Market hours respected?
- [ ] Risk limits enforced?
- [ ] Order parameters validated?
- [ ] Analyze mode prevents trades?

## Output Format

Generate: `CODE_REVIEW_[feature-name].md` with:

---

# Code Review: [PR Title]

**PR**: #[NUMBER]
**Issue**: #[ISSUE]
**Reviewer**: AI Assistant
**Date**: [DATE]
**Status**: ⛔ BLOCK | 🛑 REQUEST CHANGES | ✅ APPROVE

## Summary

[2-3 sentence overview of changes and recommendation]

## Automated Checks

| Check           | Status | Notes |
| --------------- | ------ | ----- |
| Issue Reference | ✅/❌  |       |
| Tests Present   | ✅/❌  |       |
| CI Passing      | ✅/❌  |       |
| Lint            | ✅/❌  |       |
| Typecheck       | ✅/❌  |       |
| Single Change   | ✅/❌  |       |

## Critical Issues (⛔ MUST FIX)

[List blocking issues that prevent merge]

- ⛔ **File**: [file.py:line]
  - **Issue**: [description]
  - **Risk**: [impact]
  - **Fix**: [specific action]

## High Priority Issues (🛑 SHOULD FIX)

[List important issues to address before merge]

- 🛑 **File**: [file.py:line]
  - **Issue**: [description]
  - **Suggestion**: [how to improve]

## Medium/Low Issues (🟡 CONSIDER)

[List nice-to-haves and minor improvements]

- 🟡 **File**: [file.py:line]
  - **Note**: [observation]
  - **Optional**: [suggestion]

## Positive Observations (👍 GOOD WORK)

[Acknowledge good practices]

- 👍 [Good thing observed]
- 👍 [Another good thing]

## Trading Logic Review

[Only if trading logic changed]

### Entry Logic

- **Assessment**: [safe/unsafe]
- **Notes**: [observations]

### Exit Logic

- **Assessment**: [safe/unsafe]
- **Notes**: [observations]

### Risk Management

- **Assessment**: [safe/unsafe]
- **Notes**: [position sizing, stop loss, limits]

### Test Coverage

- **Entry scenarios**: ✅/❌
- **Exit scenarios**: ✅/❌
- **Edge cases**: ✅/❌
- **API mocking**: ✅/❌

## Test Review

### Coverage

- **New tests added**: [count]
- **Test quality**: [assessment]
- **Mocking**: ✅/❌ (Alpaca, OpenAI mocked)
- **Deterministic**: ✅/❌ (no random data)

### Test Cases Reviewed

- [Test 1]: [assessment]
- [Test 2]: [assessment]

## Code Quality Assessment

### Structure

- **Readability**: [1-5 score]
- **Modularity**: [1-5 score]
- **Naming**: [1-5 score]

### Concerns

- [Any code quality issues]

## Migration Alignment

[Only if part of migration]

- **Phase**: [Phase X from migration_roadmap.md]
- **Alignment**: ✅/❌
- **Notes**: [how it fits into migration]

## Security Review

- **Secrets**: ✅ None found / ❌ Found [location]
- **Validation**: ✅ Proper / 🟡 Could improve
- **Auth**: ✅ N/A / ✅ Proper / ❌ Missing

## Performance Considerations

- [Any performance notes or concerns]

## Documentation

- **Docstrings**: ✅/❌
- **Comments**: [sufficient/sparse/too many]
- **AGENTS.md updated**: ✅/❌/N/A

## Final Recommendation

**Decision**: ⛔ BLOCK | 🛑 REQUEST CHANGES | ✅ APPROVE

**Reasoning**: [Brief explanation of decision]

**Next Steps**:

1. [Action item 1]
2. [Action item 2]

## Review Notes

[Any additional context or observations]

---

**Reviewed using**: `.github/instructions/code-review.instructions.md`
**Prompt version**: 1.0
```

## How to Use This Prompt

1. **Gather Context**: Collect PR details, CI results, changed files
2. **Fill Template**: Replace [PLACEHOLDERS] with actual values
3. **Run Review**: Process through review instructions
4. **Generate Output**: Create `CODE_REVIEW_[feature].md` file
5. **Post Findings**: Add review comments to PR on GitHub
6. **Track Resolution**: Monitor fixes and re-review if needed

## Output File Location

Save review to: `/Users/kim.rejstrom/Development/personal/alpacalyzer-algo-trader/CODE_REVIEW_[feature].md`

(Note: This file is gitignored via `CODE_REVIEW_*.md` pattern)

## Review Cadence

- **Agent PRs**: Always review before merge
- **Migration PRs**: Extra scrutiny for architecture changes
- **Trading Logic PRs**: Mandatory detailed review with trading logic validation
- **Docs/Config PRs**: Lighter review, can fast-track if CI passes

## Example Usage

```bash
# Agent generates PR
git checkout feature/new-entry-logic
git push

# Review process
1. CI runs automatically (lint, typecheck, tests)
2. Agent or human uses this prompt to generate review
3. Review saved to CODE_REVIEW_new-entry-logic.md
4. Issues posted to PR comments
5. Author fixes issues
6. Re-review after fixes
7. Approve and merge when clean
```

## Tips for Effective Reviews

### For Reviewers

- **Start with CI**: Don't review if CI failing
- **Read tests first**: Tests show intent
- **Trace trading logic**: Manually walk through entry/exit
- **Check mocks**: Verify no real API calls in tests
- **Look for edge cases**: What breaks this?

### For Agents Generating Reviews

- **Be specific**: Point to exact files and line numbers
- **Explain impact**: Why is this issue important?
- **Suggest fixes**: Provide actionable guidance
- **Acknowledge good work**: Positive reinforcement helps
- **Prioritize correctly**: Don't block PRs for nitpicks

### For Authors Responding to Reviews

- **Address all comments**: Even if just "acknowledged"
- **Explain decisions**: If you disagree, explain why
- **Test fixes**: Run full test suite after changes
- **Update tests**: If logic changed, update tests too
- **Request re-review**: After fixes, ask for second look

## Integration with GitHub

This prompt works with GitHub CLI and GitHub MCP tools:

```bash
# Using MCP tools in Claude
mcp_io_github_git_create_pull_request  # Create PR
mcp_io_github_git_request_copilot_review  # Request AI review
mcp_io_github_git_add_comment_to_pending_review  # Add review comments
```

---

**Remember**: Code reviews exist to catch mistakes before they hit production. Trading platforms require extra vigilance - mistakes here cost money.
