#!/usr/bin/env bash
# wti.sh — Portable worktree issue start
# Extracted from zshrc wti() function. Works in bash and zsh.
#
# Usage:
#   scripts/wti.sh <issue_number> -o       # Create worktree + launch OpenCode
#   scripts/wti.sh <issue_number> -c       # Create worktree + launch Claude Code
#   scripts/wti.sh <issue_number> --setup-only  # Create worktree only, print path
#
# The orchestrator uses --setup-only to get the worktree path, then launches
# the agent separately so it can manage the PID.

set -euo pipefail

usage() {
    echo "Usage: $(basename "$0") <issue-number> (-o|-c) [--setup-only]"
    echo ""
    echo "  -o              Launch with OpenCode"
    echo "  -c              Launch with Claude Code"
    echo "  --setup-only    Create worktree only, print path to stdout"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") 101 -o"
    echo "  $(basename "$0") 101 --setup-only"
    exit 1
}

# --- Parse args ---

ISSUE_NUM=""
ACTION=""
SETUP_ONLY=false

while [ $# -gt 0 ]; do
    case "$1" in
        -o) ACTION="opencode" ;;
        -c) ACTION="claude" ;;
        --setup-only) SETUP_ONLY=true ;;
        -h|--help) usage ;;
        *)
            if [ -z "$ISSUE_NUM" ] && [[ "$1" =~ ^[0-9]+$ ]]; then
                ISSUE_NUM="$1"
            else
                echo "Error: unexpected argument '$1'" >&2
                usage
            fi
            ;;
    esac
    shift
done

if [ -z "$ISSUE_NUM" ]; then
    echo "Error: issue number required" >&2
    usage
fi

if [ "$SETUP_ONLY" = false ] && [ -z "$ACTION" ]; then
    echo "Error: specify -o (OpenCode) or -c (Claude), or --setup-only" >&2
    usage
fi

BRANCH_NAME="issue-${ISSUE_NUM}"

# --- Create worktree ---

echo "Creating worktree for issue #${ISSUE_NUM}..." >&2
wt switch -c "$BRANCH_NAME" --no-cd
if [ $? -ne 0 ]; then
    echo "Error: failed to create worktree" >&2
    exit 1
fi

# --- Get worktree path ---

WT_PATH=$(wt list --format json 2>/dev/null | jq -r ".[] | select(.branch == \"$BRANCH_NAME\") | .path")
if [ -z "$WT_PATH" ] || [ "$WT_PATH" = "null" ]; then
    echo "Error: could not determine worktree path for branch $BRANCH_NAME" >&2
    exit 1
fi

# --- Setup-only mode: print path and exit ---

if [ "$SETUP_ONLY" = true ]; then
    echo "$WT_PATH"
    exit 0
fi

# --- Launch agent ---

PROMPT="read AGENTS.md and start work on issue ${ISSUE_NUM}. Make sure to use skills from SKILL.md when appropriate."

echo "Worktree: $WT_PATH" >&2
echo "Agent: $ACTION" >&2
echo "Prompt: $PROMPT" >&2

case "$ACTION" in
    opencode)
        echo "Launching OpenCode..." >&2
        (cd "$WT_PATH" && opencode --prompt "$PROMPT")
        ;;
    claude)
        echo "Launching Claude Code..." >&2
        (cd "$WT_PATH" && claude "$PROMPT")
        ;;
esac
