---
name: addressing-code-review
description: Use when CODE_REVIEW_<ISSUE>.md exists with Critical or High issues that need fixing before merge
---

# Addressing Code Review

Fix issues identified in code review before proceeding to merge.

**Core principle:** Verify before implementing. Technical correctness over speed.

## When to Use

- `CODE_REVIEW_*.md` file exists with Critical or High issues
- After `project:pr-code-review` finds issues to address

## The Process

```dot
digraph addressing_review {
    rankdir=TB;

    "Read CODE_REVIEW_<ISSUE>.md" [shape=box];
    "Understand all issues before fixing" [shape=box];
    "Any issues unclear?" [shape=diamond];
    "Ask for clarification" [shape=box];
    "Process issues by priority" [shape=box];
    "Fix Critical issues first" [shape=box];
    "Fix High issues" [shape=box];
    "Test each fix individually" [shape=box];
    "Push fixes and update PR" [shape=box];
    "Re-run pr-code-review skill" [shape=box];
    "All issues resolved?" [shape=diamond];
    "PR ready for human review" [shape=box];

    "Read CODE_REVIEW_<ISSUE>.md" -> "Understand all issues before fixing";
    "Understand all issues before fixing" -> "Any issues unclear?";
    "Any issues unclear?" -> "Ask for clarification" [label="yes"];
    "Ask for clarification" -> "Understand all issues before fixing";
    "Any issues unclear?" -> "Process issues by priority" [label="no"];
    "Process issues by priority" -> "Fix Critical issues first";
    "Fix Critical issues first" -> "Fix High issues";
    "Fix High issues" -> "Test each fix individually";
    "Test each fix individually" -> "Push fixes and update PR";
    "Push fixes and update PR" -> "Re-run pr-code-review skill";
    "Re-run pr-code-review skill" -> "All issues resolved?";
    "All issues resolved?" -> "Process issues by priority" [label="no - new issues"];
    "All issues resolved?" -> "PR ready for human review" [label="yes"];
}
```

## How to Address Issues

**1. Read the CODE_REVIEW file:**

```bash
ls CODE_REVIEW_*.md
```

**2. Understand ALL issues before fixing.** Items may be related. If unclear, ask first.

**3. Process by priority:**

| Priority | Action                                                     |
| -------- | ---------------------------------------------------------- |
| Critical | Must fix immediately - security, trading safety, data loss |
| High     | Should fix before merge - missing tests, architecture      |
| Medium   | Fix if trivial, otherwise document for later               |
| Low      | Optional - style, minor optimizations                      |

**4. For each issue:** Read suggestion -> Verify in code -> Apply fix -> Test -> Commit

**5. Test each fix:**

```bash
uv run pytest tests/test_<relevant>.py -v
```

**6. Commit and re-run review:**

```bash
git commit -m "fix(scope): address review feedback for #ISSUE"
git push
# Then use project:pr-code-review skill again
```

## Handling Feedback

**When correct:** Just fix it. Actions speak.

```
Fix: "Fixed. Added null check at trader.py:42"
Don't: "You're absolutely right!" / "Great point!"
```

**When wrong:** Push back with technical reasoning.

```
"Checked - this legacy path is needed for backward compat.
Should we drop pre-v1 support instead?"
```

**Push back when:** Breaks functionality, lacks context, violates YAGNI, conflicts with AGENTS.md

## Trading Logic Fixes

**Extra scrutiny for:**

- Entry/exit condition changes
- Position sizing modifications
- Stop loss calculations
- Risk limit adjustments

**Always verify:**

- Tests exist for the trading scenario
- Alpaca API is mocked in tests
- No real trades possible in test mode

## Red Flags

**Never:**

- Start fixing before understanding all issues
- Fix out of order (Critical must be first)
- Skip testing individual fixes
- Merge with unfixed Critical issues
- Implement unclear feedback without asking
- Skip trading logic tests for execution changes

## Quick Reference

| Step           | Action                                       |
| -------------- | -------------------------------------------- |
| Find review    | `ls CODE_REVIEW_*.md`                        |
| Priority order | Critical -> High -> Medium -> Low            |
| Test each fix  | `uv run pytest tests/<specific-file>.py -v`  |
| Commit         | `fix(scope): address review feedback for #N` |
| Re-verify      | Use `project:pr-code-review` skill again     |
