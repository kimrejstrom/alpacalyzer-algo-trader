#!/usr/bin/env bash
# opencode-grind-loop.sh — Grind loop wrapper for OpenCode
#
# Since OpenCode has no hooks system, this script wraps the agent
# invocation in a loop that checks completion after each exit.
#
# Features:
#   - Reads config from .agents/config.yaml
#   - Stall timeout via `timeout` command (kills hung agent)
#   - Idle detection via check-completion.sh (re-prompts stopped agent)
#   - Structured JSON parsing from check-completion.sh
#   - Session logging for post-hoc observability
#
# Usage (from wti function):
#   source .agents/hooks/opencode-grind-loop.sh
#   grind_loop "your prompt here"
#
# Or standalone:
#   bash .agents/hooks/opencode-grind-loop.sh "your prompt here"

set -euo pipefail

# --- Config reading ---

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
STALL_TIMEOUT=$(read_config stall_timeout_seconds 300)

# --- Plan-first check ---

check_plan_exists() {
    local plan_files
    plan_files=$(find docs/plans -maxdepth 1 \( -name "issue-*.md" -o -name "plan-*.md" -o -name "_PLAN_*.md" \) 2>/dev/null | head -1)

    if [ -z "$plan_files" ]; then
        echo ""
        echo "⚠️  PLAN-FIRST: No plan file found in docs/plans/"
        echo "   Before coding, create docs/plans/issue-{NUMBER}.md"
        echo "   Template: docs/templates/plan-template.md"
        echo ""
        return 1
    fi
    return 0
}

# --- Extract followup from structured JSON ---

extract_followup() {
    local json="$1"
    # Try jq first, fall back to grep/sed
    if command -v jq &>/dev/null; then
        echo "$json" | jq -r '.followup_prompt // empty' 2>/dev/null || echo "$json"
    else
        # Fallback: extract followup_prompt value (handles simple cases)
        local prompt
        prompt=$(echo "$json" | grep -o '"followup_prompt":\s*"[^"]*"' 2>/dev/null | sed 's/"followup_prompt":\s*"//' | sed 's/"$//' || echo "")
        if [ -n "$prompt" ]; then
            # Unescape \n
            echo -e "$prompt"
        else
            # If JSON parsing fails, use raw output as prompt
            echo "$json"
        fi
    fi
}

# --- Grind loop ---

grind_loop() {
    local prompt="${1:-}"
    if [ -z "$prompt" ]; then
        echo "Usage: grind_loop 'your prompt here'"
        return 1
    fi

    echo "━━━ GRIND LOOP CONFIG ━━━"
    echo "  Max iterations: $MAX_ITERATIONS"
    echo "  Stall timeout:  ${STALL_TIMEOUT}s"
    echo "  Config file:    $CONFIG_FILE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━"

    for i in $(seq 1 "$MAX_ITERATIONS"); do
        echo ""
        echo "━━━ GRIND LOOP: Iteration $i/$MAX_ITERATIONS ━━━"

        # Run OpenCode agent with stall timeout
        local agent_exit=0
        if [ "$STALL_TIMEOUT" -gt 0 ]; then
            timeout "${STALL_TIMEOUT}s" opencode --prompt "$prompt" || agent_exit=$?
        else
            opencode --prompt "$prompt" || agent_exit=$?
        fi

        # Check if killed by timeout (exit code 124)
        if [ "$agent_exit" -eq 124 ]; then
            echo "━━━ GRIND LOOP: Agent stalled (no output for ${STALL_TIMEOUT}s). Re-prompting. ━━━"
            prompt="You appear to be stuck — the session timed out after ${STALL_TIMEOUT} seconds of inactivity. Check your current approach and try a different angle. If you're waiting on an external service, note the issue and move on to something else."
            continue
        fi

        # Check completion
        export GRIND_ITERATION="$i"
        local check_output=""
        local check_exit=0
        check_output=$(bash .agents/hooks/check-completion.sh 2>/dev/null) || check_exit=$?

        if [ "$check_exit" -eq 0 ]; then
            echo "━━━ GRIND LOOP: Complete after $i iteration(s) ━━━"
            return 0
        fi

        # Extract follow-up prompt from structured JSON output
        if [ -n "$check_output" ]; then
            local followup
            followup=$(extract_followup "$check_output")

            if [ -n "$followup" ]; then
                prompt="$followup"
                echo ""
                echo "━━━ GRIND LOOP: Incomplete. Re-prompting: ━━━"
                echo "$followup" | head -5
                echo ""
            else
                echo "━━━ GRIND LOOP: check-completion returned non-zero but no follow-up. Stopping. ━━━"
                return 1
            fi
        else
            echo "━━━ GRIND LOOP: check-completion returned non-zero but no output. Stopping. ━━━"
            return 1
        fi
    done

    echo ""
    echo "━━━ GRIND LOOP: Max iterations ($MAX_ITERATIONS) reached. ━━━"
    return 1
}

# If run directly (not sourced), execute with args
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    grind_loop "$@"
fi
