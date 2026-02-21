#!/usr/bin/env bash
# check-completion.sh — Shared completion checker for grind loop
# Used by: Claude Code Stop hook, wti OpenCode wrapper
#
# Exit codes:
#   0 = all done, no follow-up needed
#   1 = incomplete, follow-up prompt on stdout
#
# Environment:
#   MAX_GRIND_ITERATIONS (default: 5) — cap to prevent infinite loops
#   GRIND_ITERATION (default: 0) — current iteration count

set -euo pipefail

MAX_ITERATIONS="${MAX_GRIND_ITERATIONS:-5}"
CURRENT_ITERATION="${GRIND_ITERATION:-0}"

# --- Helpers ---

fail_with_prompt() {
    echo "$1"
    exit 1
}

# --- Iteration cap ---

if [ "$CURRENT_ITERATION" -ge "$MAX_ITERATIONS" ]; then
    echo "GRIND_LOOP: Max iterations ($MAX_ITERATIONS) reached. Stopping."
    exit 0
fi

# --- Check 1: Tests pass ---

echo "GRIND_LOOP: Checking tests..." >&2
TEST_OUTPUT=$(uv run pytest tests --tb=short -q 2>&1) || true
if echo "$TEST_OUTPUT" | grep -qE "(FAILED|ERROR|error)"; then
    FAILED_TESTS=$(echo "$TEST_OUTPUT" | grep -E "^FAILED" | head -5)
    fail_with_prompt "Tests are still failing. Fix these failures and re-run:

$FAILED_TESTS

Test output (last 20 lines):
$(echo "$TEST_OUTPUT" | tail -20)"
fi

# --- Check 2: Code review findings ---

REVIEW_FILES=$(find . -maxdepth 1 -name "CODE_REVIEW_*.md" 2>/dev/null)
if [ -n "$REVIEW_FILES" ]; then
    for review_file in $REVIEW_FILES; do
        if grep -qiE "^##.*critical|^##.*high|\*\*severity\*\*:.*critical|\*\*severity\*\*:.*high" "$review_file" 2>/dev/null; then
            FINDINGS=$(grep -iE "critical|high" "$review_file" | head -5)
            fail_with_prompt "CODE_REVIEW has unresolved Critical/High findings in $review_file:

$FINDINGS

Address these findings, then re-run the code reviewer."
        fi
    done
fi

# --- Check 3: Blind review needed ---
# If tests pass but no review file exists, request a blind review
# The review should be done in a separate agent session (context: fork)

PR_EXISTS=$(gh pr list --head "$(git branch --show-current)" --json number --jq '.[0].number' 2>/dev/null || echo "")
if [ -n "$PR_EXISTS" ] && [ -z "$REVIEW_FILES" ]; then
    # Check if this is a trivial PR (docs-only, deps-only, formatting-only)
    CHANGED_FILES=$(git diff --name-only "$(git merge-base HEAD main)..HEAD" 2>/dev/null || echo "")
    IS_TRIVIAL=true
    while IFS= read -r file; do
        [ -z "$file" ] && continue
        case "$file" in
            *.md|*.txt|*.json|*.toml|*.yaml|*.yml|*.lock) ;;  # docs/config/deps
            *) IS_TRIVIAL=false; break ;;
        esac
    done <<< "$CHANGED_FILES"

    if [ "$IS_TRIVIAL" = false ]; then
        fail_with_prompt "Tests pass and PR #$PR_EXISTS exists, but no code review has been performed yet. Run the code-reviewer subagent to review PR #$PR_EXISTS before marking as done. Use a separate agent session (context: fork) for blind validation."
    fi
fi

# --- Check 4: Scratchpad signals DONE ---

SCRATCHPAD=".agents/scratchpad.md"
if [ -f "$SCRATCHPAD" ]; then
    if grep -q "STATUS: DONE" "$SCRATCHPAD" 2>/dev/null; then
        echo "GRIND_LOOP: Scratchpad signals DONE." >&2
        exit 0
    fi
fi

# --- All checks passed ---

echo "GRIND_LOOP: All checks passed." >&2
exit 0
