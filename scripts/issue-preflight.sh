#!/usr/bin/env bash
# issue-preflight.sh — Validate a single issue is ready to work on
#
# Checks:
#   - Issue exists and is open
#   - No existing open PR for this issue
#   - All dependencies (from Agent Metadata) have merged PRs
#   - Parses Agent Metadata table from issue body
#
# Exit codes:
#   0 = ready to work (JSON on stdout)
#   1 = blocked (JSON on stdout with block_reason)
#   2 = issue not found or closed
#
# Usage:
#   scripts/issue-preflight.sh <issue_number>

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $(basename "$0") <issue_number>" >&2
    exit 2
fi

ISSUE_NUM="$1"

# --- Resolve repo ---

REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE_URL" ]; then
    echo "Error: not in a git repo or no origin remote" >&2
    exit 2
fi

# Parse owner/repo from SSH or HTTPS URL
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+)/([^/.]+)(\.git)?$#\1/\2#')
OWNER=$(echo "$OWNER_REPO" | cut -d'/' -f1)
REPO=$(echo "$OWNER_REPO" | cut -d'/' -f2)

# --- Fetch issue ---

ISSUE_JSON=$(gh issue view "$ISSUE_NUM" --repo "${OWNER}/${REPO}" --json state,body,title,number 2>/dev/null || echo "")
if [ -z "$ISSUE_JSON" ]; then
    echo "{\"issue_number\":$ISSUE_NUM,\"ready\":false,\"block_reason\":\"Issue #$ISSUE_NUM not found\"}"
    exit 2
fi

STATE=$(echo "$ISSUE_JSON" | jq -r '.state')
TITLE=$(echo "$ISSUE_JSON" | jq -r '.title')
BODY=$(echo "$ISSUE_JSON" | jq -r '.body // ""')

if [ "$STATE" != "OPEN" ]; then
    echo "{\"issue_number\":$ISSUE_NUM,\"title\":$(echo "$TITLE" | jq -Rs .),\"ready\":false,\"block_reason\":\"Issue #$ISSUE_NUM is $STATE\"}"
    exit 2
fi

# --- Check for existing PR ---

EXISTING_PR=$(gh pr list --repo "${OWNER}/${REPO}" --head "issue-${ISSUE_NUM}" --json number --jq '.[0].number' 2>/dev/null || echo "")
if [ -n "$EXISTING_PR" ]; then
    echo "{\"issue_number\":$ISSUE_NUM,\"title\":$(echo "$TITLE" | jq -Rs .),\"ready\":false,\"block_reason\":\"PR #$EXISTING_PR already exists for issue #$ISSUE_NUM\"}"
    exit 1
fi

# --- Parse Agent Metadata ---

# Helper: extract value from Agent Metadata table row
extract_meta() {
    local field="$1"
    local default="$2"
    local value
    value=$(echo "$BODY" | grep -i "| *${field} *|" | head -1 | sed 's/.*| *'"${field}"' *| *\(.*\) *|.*/\1/' | sed 's/^ *//;s/ *$//' || echo "")
    if [ -n "$value" ] && [ "$value" != "$BODY" ]; then
        echo "$value"
    else
        echo "$default"
    fi
}

META_DEPENDS=$(extract_meta "Depends on" "#none")
META_PARALLEL=$(extract_meta "Parallel safe" "yes")
META_AUTOMERGE=$(extract_meta "Auto-merge" "no")
META_TOOL=$(extract_meta "Agent tool" "opencode")
META_COMPLEXITY=$(extract_meta "Estimated complexity" "medium")

# Normalize booleans
PARALLEL_SAFE=true
if echo "$META_PARALLEL" | grep -qi "no"; then
    PARALLEL_SAFE=false
fi

AUTO_MERGE=false
if echo "$META_AUTOMERGE" | grep -qi "yes"; then
    AUTO_MERGE=true
fi

# Normalize agent tool
AGENT_TOOL="opencode"
case "$(echo "$META_TOOL" | tr '[:upper:]' '[:lower:]')" in
    claude*) AGENT_TOOL="claude" ;;
    opencode*) AGENT_TOOL="opencode" ;;
    *) AGENT_TOOL="opencode" ;;
esac

# Normalize complexity
COMPLEXITY="medium"
case "$(echo "$META_COMPLEXITY" | tr '[:upper:]' '[:lower:]')" in
    small) COMPLEXITY="small" ;;
    medium) COMPLEXITY="medium" ;;
    large) COMPLEXITY="large" ;;
esac

# --- Parse dependencies ---

DEPENDS_ON="[]"
BLOCK_REASON=""

if [ "$META_DEPENDS" != "#none" ] && [ -n "$META_DEPENDS" ]; then
    # Extract issue numbers from "#41, #42" format
    DEP_NUMS=$(echo "$META_DEPENDS" | grep -oE '#[0-9]+' | sed 's/#//' || echo "")

    if [ -n "$DEP_NUMS" ]; then
        DEP_ARRAY="["
        FIRST=true
        for dep in $DEP_NUMS; do
            if [ "$FIRST" = true ]; then FIRST=false; else DEP_ARRAY+=","; fi
            DEP_ARRAY+="$dep"

            # Check if dependency has a merged PR
            MERGED_PR=$(gh pr list --repo "${OWNER}/${REPO}" --head "issue-${dep}" --state merged --json number --jq '.[0].number' 2>/dev/null || echo "")
            if [ -z "$MERGED_PR" ]; then
                # Also check if the issue itself is closed (might have been merged via different branch name)
                DEP_STATE=$(gh issue view "$dep" --repo "${OWNER}/${REPO}" --json state --jq '.state' 2>/dev/null || echo "UNKNOWN")
                if [ "$DEP_STATE" != "CLOSED" ]; then
                    BLOCK_REASON="Dependency #$dep is not yet resolved (no merged PR, issue state: $DEP_STATE)"
                fi
            fi
        done
        DEP_ARRAY+="]"
        DEPENDS_ON="$DEP_ARRAY"
    fi
fi

# --- Output ---

READY=true
EXIT_CODE=0
if [ -n "$BLOCK_REASON" ]; then
    READY=false
    EXIT_CODE=1
fi

ESCAPED_TITLE=$(echo "$TITLE" | jq -Rs .)
ESCAPED_REASON="null"
if [ -n "$BLOCK_REASON" ]; then
    ESCAPED_REASON=$(echo "$BLOCK_REASON" | jq -Rs .)
fi

cat <<EOF
{
  "issue_number": $ISSUE_NUM,
  "title": $ESCAPED_TITLE,
  "depends_on": $DEPENDS_ON,
  "parallel_safe": $PARALLEL_SAFE,
  "auto_merge": $AUTO_MERGE,
  "agent_tool": "$AGENT_TOOL",
  "complexity": "$COMPLEXITY",
  "ready": $READY,
  "block_reason": $ESCAPED_REASON
}
EOF

exit $EXIT_CODE
