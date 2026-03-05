#!/usr/bin/env bash
# check-completion.sh — Shared completion checker for grind loop
# Used by: Claude Code Stop hook, OpenCode grind-loop.ts, opencode-grind-loop.sh
#
# Exit codes:
#   0 = all done, no follow-up needed
#   1 = incomplete, structured JSON on stdout, diagnostics on stderr
#
# Environment:
#   GRIND_ITERATION (default: 0) — current iteration count
#   MAX_GRIND_ITERATIONS — override max iterations (optional)
#
# Output (stdout): JSON object with completion status and follow-up prompt
# Output (stderr): Human-readable diagnostic messages

set -euo pipefail

# --- Config reading ---
# Read from .agents/config.yaml with grep/awk fallback to defaults

CONFIG_FILE=".agents/config.yaml"

read_config() {
    local key="$1"
    local default="$2"
    if [ -f "$CONFIG_FILE" ]; then
        local value
        value=$(grep -E "^\s+${key}:" "$CONFIG_FILE" 2>/dev/null | head -1 | sed 's/.*:\s*//' | tr -d '"' | tr -d "'" || echo "")
        if [ -n "$value" ]; then
            echo "$value"
            return
        fi
    fi
    echo "$default"
}

MAX_ITERATIONS="${MAX_GRIND_ITERATIONS:-$(read_config max_iterations 5)}"
CURRENT_ITERATION="${GRIND_ITERATION:-0}"
SESSION_LOG=$(read_config session_log ".agents/session-log.jsonl")
SESSION_LOG_MAX=$(read_config session_log_max_lines 200)
SCRATCHPAD=$(read_config path ".agents/scratchpad.md")

# --- Helpers ---

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
CHECKS_TESTS_PASS=true
CHECKS_REVIEW_CLEAN=true
CHECKS_REVIEW_EXISTS=false
CHECKS_SCRATCHPAD_DONE=false
FAILED_CHECKS=()
FAILED_TESTS_LIST=""
SCRATCHPAD_STATUS=""
SCRATCHPAD_FOCUS=""
SCRATCHPAD_PREV_FOCUS=""
FOLLOWUP_PROMPT=""

# Read scratchpad state
read_scratchpad() {
    if [ ! -f "$SCRATCHPAD" ]; then
        return
    fi
    SCRATCHPAD_STATUS=$(grep -E "^## STATUS:" "$SCRATCHPAD" 2>/dev/null | sed 's/## STATUS:\s*//' || echo "")
    SCRATCHPAD_FOCUS=$(grep -A1 "^## CURRENT_FOCUS" "$SCRATCHPAD" 2>/dev/null | tail -1 | sed 's/^\s*//' || echo "")
    # Check if focus is just the header or empty
    if [ "$SCRATCHPAD_FOCUS" = "## CURRENT_FOCUS" ] || [ -z "$SCRATCHPAD_FOCUS" ]; then
        SCRATCHPAD_FOCUS=""
    fi
}

# Escape string for JSON
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/}"
    s="${s//$'\t'/\\t}"
    echo "$s"
}

# Build and output structured JSON result
output_json() {
    local complete="$1"
    local escaped_prompt
    escaped_prompt=$(json_escape "$FOLLOWUP_PROMPT")
    local escaped_focus
    escaped_focus=$(json_escape "$SCRATCHPAD_FOCUS")
    local escaped_status
    escaped_status=$(json_escape "$SCRATCHPAD_STATUS")
    local escaped_tests
    escaped_tests=$(json_escape "$FAILED_TESTS_LIST")

    # Build failed_checks JSON array
    local failed_json="[]"
    if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
        failed_json="["
        local first=true
        for check in "${FAILED_CHECKS[@]}"; do
            if [ "$first" = true ]; then
                first=false
            else
                failed_json+=","
            fi
            failed_json+="\"$check\""
        done
        failed_json+="]"
    fi

    cat <<EOF
{
  "complete": $complete,
  "iteration": $CURRENT_ITERATION,
  "max_iterations": $MAX_ITERATIONS,
  "timestamp": "$TIMESTAMP",
  "checks": {
    "tests_pass": $CHECKS_TESTS_PASS,
    "review_clean": $CHECKS_REVIEW_CLEAN,
    "review_exists": $CHECKS_REVIEW_EXISTS,
    "scratchpad_done": $CHECKS_SCRATCHPAD_DONE
  },
  "failed_checks": $failed_json,
  "followup_prompt": "$escaped_prompt",
  "context": {
    "failed_tests": "$escaped_tests",
    "scratchpad_status": "$escaped_status",
    "scratchpad_focus": "$escaped_focus"
  }
}
EOF
}

# Append to session log
append_session_log() {
    local complete="$1"
    local log_dir
    log_dir=$(dirname "$SESSION_LOG")
    mkdir -p "$log_dir" 2>/dev/null || true

    # Build compact log line
    local failed_json="[]"
    if [ ${#FAILED_CHECKS[@]} -gt 0 ]; then
        failed_json="["
        local first=true
        for check in "${FAILED_CHECKS[@]}"; do
            if [ "$first" = true ]; then first=false; else failed_json+=","; fi
            failed_json+="\"$check\""
        done
        failed_json+="]"
    fi

    local escaped_status
    escaped_status=$(json_escape "$SCRATCHPAD_STATUS")

    echo "{\"timestamp\":\"$TIMESTAMP\",\"iteration\":$CURRENT_ITERATION,\"complete\":$complete,\"failed\":$failed_json,\"scratchpad_status\":\"$escaped_status\"}" >> "$SESSION_LOG" 2>/dev/null || true

    # Truncate if too long
    if [ -f "$SESSION_LOG" ]; then
        local line_count
        line_count=$(wc -l < "$SESSION_LOG" 2>/dev/null || echo "0")
        if [ "$line_count" -gt "$SESSION_LOG_MAX" ]; then
            tail -n "$SESSION_LOG_MAX" "$SESSION_LOG" > "${SESSION_LOG}.tmp" 2>/dev/null && mv "${SESSION_LOG}.tmp" "$SESSION_LOG" 2>/dev/null || true
        fi
    fi
}

fail_with_prompt() {
    FOLLOWUP_PROMPT="$1"
    append_session_log "false"
    output_json "false"
    exit 1
}

# --- Read scratchpad ---

read_scratchpad

# --- Iteration cap ---

if [ "$CURRENT_ITERATION" -ge "$MAX_ITERATIONS" ]; then
    echo "GRIND_LOOP: Max iterations ($MAX_ITERATIONS) reached. Stopping." >&2
    append_session_log "true"
    output_json "true"
    exit 0
fi

# --- Check 1: Tests pass ---

echo "GRIND_LOOP: Checking tests..." >&2
TEST_OUTPUT=$(uv run pytest tests --tb=short -q 2>&1) || true
if echo "$TEST_OUTPUT" | grep -qE "(FAILED|ERROR|error)"; then
    CHECKS_TESTS_PASS=false
    FAILED_CHECKS+=("tests_pass")
    FAILED_TESTS_LIST=$(echo "$TEST_OUTPUT" | grep -E "^FAILED" | head -5)
    TEST_TAIL=$(echo "$TEST_OUTPUT" | tail -20)

    # Build context-aware re-prompt
    local_prompt="Tests are still failing. Fix these failures and re-run:"
    local_prompt+="\n\n${FAILED_TESTS_LIST}"
    local_prompt+="\n\nTest output (last 20 lines):\n${TEST_TAIL}"

    # Add scratchpad context if available
    if [ -n "$SCRATCHPAD_FOCUS" ]; then
        local_prompt+="\n\nYou were working on: ${SCRATCHPAD_FOCUS}"
        local_prompt+="\nContinue from where you left off."
    fi

    fail_with_prompt "$local_prompt"
fi

# --- Check 2: Code review findings ---

REVIEW_FILES=$(find . -maxdepth 1 -name "CODE_REVIEW_*.md" 2>/dev/null || echo "")
if [ -n "$REVIEW_FILES" ]; then
    CHECKS_REVIEW_EXISTS=true
    for review_file in $REVIEW_FILES; do
        if grep -qiE "^##.*critical|^##.*high|\*\*severity\*\*:.*critical|\*\*severity\*\*:.*high|\*\*Priority\*\*:.*Critical|\*\*Priority\*\*:.*High" "$review_file" 2>/dev/null; then
            CHECKS_REVIEW_CLEAN=false
            FAILED_CHECKS+=("review_clean")
            FINDINGS=$(grep -iE "critical|high" "$review_file" | head -5)

            local_prompt="CODE_REVIEW has unresolved Critical/High findings in $review_file:"
            local_prompt+="\n\n${FINDINGS}"
            local_prompt+="\n\nAddress these findings, then re-run the code reviewer."

            fail_with_prompt "$local_prompt"
        fi
    done
fi

# --- Check 3: Blind review needed ---

PR_EXISTS=$(gh pr list --head "$(git branch --show-current)" --json number --jq '.[0].number' 2>/dev/null || echo "")
if [ -n "$PR_EXISTS" ] && [ -z "$REVIEW_FILES" ]; then
    CHANGED_FILES=$(git diff --name-only "$(git merge-base HEAD main)..HEAD" 2>/dev/null || echo "")
    IS_TRIVIAL=true
    while IFS= read -r file; do
        [ -z "$file" ] && continue
        case "$file" in
            *.md|*.txt|*.json|*.toml|*.yaml|*.yml|*.lock) ;;
            *) IS_TRIVIAL=false; break ;;
        esac
    done <<< "$CHANGED_FILES"

    if [ "$IS_TRIVIAL" = false ]; then
        FAILED_CHECKS+=("review_exists")
        fail_with_prompt "Tests pass and PR #$PR_EXISTS exists, but no code review has been performed yet. Run the code-reviewer subagent to review PR #$PR_EXISTS before marking as done. Use a separate agent session (context: fork) for blind validation."
    fi
fi

# --- Check 4: Scratchpad signals DONE ---

if [ -f "$SCRATCHPAD" ]; then
    if grep -q "STATUS: DONE" "$SCRATCHPAD" 2>/dev/null; then
        CHECKS_SCRATCHPAD_DONE=true
        echo "GRIND_LOOP: Scratchpad signals DONE." >&2
    fi
fi

# --- Check 5: Agent idle detection ---
# If the agent stopped but scratchpad doesn't say DONE and there's unfinished work,
# nudge it to continue. This catches the "agent silently stopped" case.

if [ "$SCRATCHPAD_STATUS" = "IN_PROGRESS" ] && [ "$CHECKS_SCRATCHPAD_DONE" = false ]; then
    # Check if scratchpad has unchecked items
    UNCHECKED=$(grep -c "\- \[ \]" "$SCRATCHPAD" 2>/dev/null || echo "0")
    if [ "$UNCHECKED" -gt 0 ]; then
        # Check session log for repeated same-focus (stuck detection)
        STUCK_PROMPT=""
        if [ -f "$SESSION_LOG" ] && [ -n "$SCRATCHPAD_FOCUS" ]; then
            # Count how many recent iterations had the same focus
            RECENT_SAME_FOCUS=$(tail -3 "$SESSION_LOG" 2>/dev/null | grep -c "$(json_escape "$SCRATCHPAD_FOCUS")" 2>/dev/null || echo "0")
            if [ "$RECENT_SAME_FOCUS" -ge 2 ]; then
                STUCK_PROMPT="\n\nYou've been stuck on the same task for $RECENT_SAME_FOCUS iterations. Try a different approach — simplify, break it into smaller steps, or reconsider the design."
            fi
        fi

        local_prompt="You stopped working but the task isn't complete. The scratchpad shows $UNCHECKED unchecked items remaining."
        if [ -n "$SCRATCHPAD_FOCUS" ]; then
            local_prompt+="\n\nYou were working on: ${SCRATCHPAD_FOCUS}"
        fi
        local_prompt+="\n\nContinue from where you left off. Update the scratchpad as you make progress."
        if [ -n "$STUCK_PROMPT" ]; then
            local_prompt+="$STUCK_PROMPT"
        fi

        FAILED_CHECKS+=("agent_idle")
        fail_with_prompt "$local_prompt"
    fi
fi

# --- All checks passed ---

echo "GRIND_LOOP: All checks passed." >&2
append_session_log "true"
output_json "true"
exit 0
