#!/usr/bin/env bash
# check-plan-exists.sh — PreToolUse hook for plan-first enforcement
# Checks that a plan file exists in docs/plans/ before allowing code writes.
#
# Exit codes:
#   0 = plan exists, proceed with tool use
#   1 = no plan found, deny tool use (message on stdout)

set -euo pipefail

# Allow writes to plan files themselves, docs, and non-code files
TOOL_PATH="${1:-}"
if [ -n "$TOOL_PATH" ]; then
    case "$TOOL_PATH" in
        docs/plans/*|docs/templates/*|.agents/*|.claude/*|.opencode/*|*.md|*.json|*.toml|*.yaml|*.yml)
            exit 0
            ;;
    esac
fi

# Check if any plan file exists in docs/plans/ (excluding INDEX.md and templates)
PLAN_FILES=$(find docs/plans -maxdepth 1 -name "issue-*.md" -o -name "plan-*.md" 2>/dev/null | head -1)

if [ -z "$PLAN_FILES" ]; then
    echo "DENIED: No plan file found in docs/plans/. Before writing code, create a plan:

1. Copy the template: docs/templates/plan-template.md
2. Save as: docs/plans/issue-{NUMBER}.md
3. Fill in: goal, acceptance criteria, files to modify, test scenarios, risks

See docs/templates/plan-template.md for the format."
    exit 1
fi

exit 0
