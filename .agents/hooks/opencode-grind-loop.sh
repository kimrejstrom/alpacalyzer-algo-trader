#!/usr/bin/env bash
# opencode-grind-loop.sh — Grind loop wrapper for OpenCode
#
# Since OpenCode has no hooks system, this script wraps the agent
# invocation in a loop that checks completion after each exit.
#
# Usage (from wti function):
#   source .agents/hooks/opencode-grind-loop.sh
#   grind_loop "your prompt here"
#
# Or standalone:
#   bash .agents/hooks/opencode-grind-loop.sh "your prompt here"

set -euo pipefail

MAX_ITERATIONS="${MAX_GRIND_ITERATIONS:-5}"

# --- Plan-first check ---
# Equivalent to Claude's PreToolUse hook on Write|Edit
check_plan_exists() {
    local plan_files
    plan_files=$(find docs/plans -maxdepth 1 \( -name "issue-*.md" -o -name "plan-*.md" \) 2>/dev/null | head -1)

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

# --- Grind loop ---
grind_loop() {
    local prompt="${1:-}"
    if [ -z "$prompt" ]; then
        echo "Usage: grind_loop 'your prompt here'"
        return 1
    fi

    for i in $(seq 1 "$MAX_ITERATIONS"); do
        echo "━━━ GRIND LOOP: Iteration $i/$MAX_ITERATIONS ━━━"

        # Run OpenCode agent
        opencode --prompt "$prompt"

        # Check completion
        export GRIND_ITERATION="$i"
        local followup
        followup=$(bash .agents/hooks/check-completion.sh 2>/dev/null) || true
        local exit_code=$?

        if [ $exit_code -eq 0 ]; then
            echo "━━━ GRIND LOOP: Complete after $i iteration(s) ━━━"
            return 0
        fi

        # Build follow-up prompt from check-completion output
        if [ -n "$followup" ]; then
            prompt="$followup"
            echo ""
            echo "━━━ GRIND LOOP: Incomplete. Re-prompting with: ━━━"
            echo "$followup" | head -5
            echo ""
        else
            echo "━━━ GRIND LOOP: check-completion returned non-zero but no follow-up. Stopping. ━━━"
            return 1
        fi
    done

    echo "━━━ GRIND LOOP: Max iterations ($MAX_ITERATIONS) reached. ━━━"
    return 1
}

# If run directly (not sourced), execute with args
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    grind_loop "$@"
fi
