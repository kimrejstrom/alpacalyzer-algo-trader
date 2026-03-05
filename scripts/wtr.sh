#!/usr/bin/env bash
# wtr.sh — Portable worktree issue remove
# Extracted from zshrc wtr() function. Works in bash and zsh.
#
# Usage:
#   scripts/wtr.sh <issue_number>        # Remove worktree
#   scripts/wtr.sh <issue_number> -m     # Merge then remove

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $(basename "$0") <issue-number> [-m]"
    echo ""
    echo "  -m    Merge branch into target before removing"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0") 101"
    echo "  $(basename "$0") 101 -m"
    exit 1
fi

ISSUE_NUM="$1"
BRANCH_NAME="issue-${ISSUE_NUM}"
MERGE=false

if [ "${2:-}" = "-m" ]; then
    MERGE=true
fi

if [ "$MERGE" = true ]; then
    echo "Merging and removing worktree for issue #${ISSUE_NUM}..."
    wt merge "$BRANCH_NAME"
else
    echo "Removing worktree for issue #${ISSUE_NUM}..."
    wt remove "$BRANCH_NAME" -D
fi
