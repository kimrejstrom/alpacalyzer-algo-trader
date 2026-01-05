# Code Review Instructions for Alpacalyzer Algo Trader

Guidelines for code reviews on Alpacalyzer Algo Trader - an algorithmic trading platform.

## 🎯 Goals

- Verify correctness, safety, and consistency
- Enforce test-first development
- Guard security, performance, and maintainability
- **Prevent financial loss from trading logic errors**

## 🛡️ Golden Rules (from AGENTS.md)

- GitHub issue exists and is referenced
- Tests written first and updated for every change
- One feature/fix per PR with focused commits
- No secrets in code
- Trading logic must be safe and correct

## 🔍 Review Focus Areas

### 1) Correctness

**General**:

- Business logic matches requirements
- Edge cases handled (null, empty, large inputs)
- Error paths handled with helpful responses

**Trading-Specific**:

- Entry conditions correctly evaluate signals
- Exit conditions protect against losses
- Position sizing respects portfolio limits
- Stop loss and target calculations are correct
- No accidental trades in analyze mode

### 2) Test Coverage

- Tests present for all code changes
- Tests written before implementation (TDD)
- Tests are deterministic (no random data)
- External APIs properly mocked (Alpaca, OpenAI)
- Financial calculations have explicit test cases
- Trading scenarios covered: entry, exit, stop loss, target hit

### 3) Type Safety

- No `Any` types without justification
- Explicit return types for exported functions
- Pydantic models used for structured data
- Type checking passes (`ty check src`)

### 4) Security

**Critical for Trading Platform**:

- No hardcoded API keys or secrets
- Environment variables for all credentials
- No trading credentials in tests or logs
- Input validation at all boundaries
- Proper authentication/authorization for external APIs

### 5) Trading Logic Safety

**CRITICAL - This can cause real financial loss**:

- [ ] Entry logic prevents duplicate positions
- [ ] Position sizing never exceeds limits
- [ ] Stop loss is ALWAYS set for every position
- [ ] Market hours respected (no after-hours trades without explicit intent)
- [ ] Cooldown periods respected
- [ ] No trades when `--analyze` flag is set
- [ ] Order parameters validated before submission
- [ ] Risk limits enforced (max position %, max portfolio exposure)

### 6) Code Quality

- Clear, descriptive naming
- Single responsibility principle
- No dead code or commented-out blocks
- Docstrings for public APIs
- Follows project conventions (see AGENTS.md)

### 7) Migration Awareness

**Context**: Ongoing migration (see `migration_plan.md`)

- [ ] Changes align with migration phases
- [ ] New code uses new architecture patterns where applicable
- [ ] Old components are preserved or explicitly deprecated
- [ ] Tests cover both old and new behavior during transition

## 🚨 Auto-Block Criteria

**These issues MUST be fixed before merge**:

1. **Hardcoded secrets or credentials** - API keys, tokens visible in code
2. **Missing tests for code changes** - All new logic must have tests
3. **Lint errors** - `ruff check` must pass
4. **Type check errors** - `ty check` must pass
5. **No issue reference** - PR description must reference issue number
6. **Multiple unrelated features** - Split into separate PRs
7. **Trading logic without tests** - Entry/exit logic MUST have tests
8. **Missing stop loss** - Every position must have stop loss
9. **Unbounded risk** - Position sizing must respect limits

## ⚠️ High Priority Issues

**Should be fixed before merge, but can be addressed in comments**:

- Insufficient test coverage (< 80% for critical paths)
- Complex functions without documentation
- Performance concerns (N+1 queries, unnecessary loops)
- Inconsistent error handling
- Magic numbers (hardcoded values instead of constants)
- Missing type hints
- Weak technical signals not validated

## ✅ Auto-Approve Candidates

**Low-risk changes that can be fast-tracked**:

1. Documentation-only changes (README, AGENTS.md, docstrings)
2. Dependency updates (with passing tests)
3. Config tweaks without behavior changes (ruff settings, etc.)
4. Test-only additions (adding tests for existing code)
5. Formatting changes (ruff format)

## 🔧 Review Checklist

### Every PR Must Have:

- [ ] Issue number in title or description (`#XX`)
- [ ] Tests added/updated
- [ ] All tests passing locally and in CI
- [ ] Lint passing (`ruff check`)
- [ ] Type check passing (`ty check src`)
- [ ] Conventional commit messages
- [ ] No hardcoded secrets
- [ ] Single focused change

### Trading Logic PRs Additionally Need:

- [ ] Entry conditions tested
- [ ] Exit conditions tested
- [ ] Position sizing tested
- [ ] Stop loss calculation tested
- [ ] Risk limits validated
- [ ] Alpaca API calls mocked in tests
- [ ] No real trades in test mode

### Migration PRs Additionally Need:

- [ ] Aligns with phase in `migration_plan.md`
- [ ] Follows new architecture patterns
- [ ] Preserves existing functionality (unless explicitly deprecating)
- [ ] Integration tests pass

## 📋 Review Process

1. **Automated Checks**: CI must pass (lint, typecheck, tests)
2. **Manual Review**: Reviewer checks all focus areas above
3. **Trading Safety Review**: For trading logic changes, extra scrutiny
4. **Request Changes**: Document specific issues with line numbers
5. **Approve**: Only when all criteria met
6. **Merge**: Squash merge to keep clean history

## 🎓 Review Tips

### For Reviewers

- Start with automated checks - if CI fails, request fixes first
- Read tests before implementation to understand intent
- Check PR description for clarity and issue link
- For trading logic, trace through entry/exit scenarios manually
- Look for edge cases in financial calculations
- Verify mocks are used for Alpaca and OpenAI calls

### For Authors

- Run all checks locally before pushing: `uv run pytest tests && uv run ruff check . && uv run ty check src`
- Write PR description explaining what and why
- Reference issue number (`#XX`)
- Add screenshots/logs for trading behavior changes
- Pre-review your own code before requesting review
- Respond to all review comments, even if just "done"

## 🔍 Common Issues to Watch For

### Trading Logic

- ❌ Entry without checking existing position
- ❌ Position sizing that exceeds buying power
- ❌ Stop loss too wide (> 5% typically)
- ❌ No target price set
- ❌ Ignoring cooldown period
- ❌ Trading during market close

### Testing

- ❌ Tests that make real API calls
- ❌ Tests with random data (non-deterministic)
- ❌ Missing test for error paths
- ❌ Tests that don't actually assert anything
- ❌ Hardcoded dates that will break over time

### Code Quality

- ❌ Functions > 50 lines
- ❌ Nested if statements > 3 levels
- ❌ Magic numbers instead of named constants
- ❌ Broad exception catching (`except Exception`)
- ❌ Commented-out code

## 🚦 Priority Levels

| Level    | Symbol | Meaning                      | Action Required     |
| -------- | ------ | ---------------------------- | ------------------- |
| Critical | ⛔     | Must fix before merge        | Block PR            |
| High     | 🛑     | Should fix before merge      | Request changes     |
| Medium   | 🟡     | Should address but can defer | Comment/suggest     |
| Low      | 🟢     | Nice to have                 | Optional suggestion |
| Nitpick  | ⛏️     | Style/preference             | Optional            |
| Positive | 👍     | Good practice                | Acknowledge         |

---

**Remember**: This is a real trading platform. Mistakes can cause financial loss. Be thorough, be safe, and don't hesitate to ask questions.
