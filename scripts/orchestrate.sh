#!/usr/bin/env bash
# orchestrate.sh — Parallel issue orchestrator
#
# Stand-in for the human-in-the-loop. Fetches issues, resolves dependencies,
# dispatches parallel agent sessions via worktrees, monitors progress,
# and handles auto-merge + cleanup for eligible issues.
#
# Usage:
#   scripts/orchestrate.sh --label orchestrator-ready
#   scripts/orchestrate.sh --issues 101,102,103
#   scripts/orchestrate.sh --dry-run --label orchestrator-ready
#   scripts/orchestrate.sh --max-parallel 2 --issues 101,102

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

MAX_PARALLEL=$(read_config max_parallel 3)
POLL_INTERVAL=$(read_config poll_interval_seconds 60)
STALL_MULTIPLIER=$(read_config stall_detection_multiplier 2)
STALL_TIMEOUT=$(read_config stall_timeout_seconds 300)
ORCH_LOG=$(read_config "log" ".agents/orchestrator-log.jsonl")
MERGE_METHOD=$(read_config auto_merge_method "squash")
DEFAULT_TOOL=$(read_config default_agent_tool "opencode")
DEFAULT_LABEL=$(read_config default_label "orchestrator-ready")
KILL_GRACE=$(read_config kill_grace_seconds 5)

# --- Parse CLI args ---

LABEL=""
ISSUES_ARG=""
DRY_RUN=false

while [ $# -gt 0 ]; do
    case "$1" in
        --label) LABEL="$2"; shift ;;
        --issues) ISSUES_ARG="$2"; shift ;;
        --max-parallel) MAX_PARALLEL="$2"; shift ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            echo "Usage: $(basename "$0") [--label LABEL] [--issues N,N,N] [--max-parallel N] [--dry-run]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
    shift
done

if [ -z "$LABEL" ] && [ -z "$ISSUES_ARG" ]; then
    LABEL="$DEFAULT_LABEL"
    echo "No --label or --issues specified, using default label: $LABEL"
fi

# --- Resolve repo ---

REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "")
if [ -z "$REMOTE_URL" ]; then
    echo "Error: not in a git repo or no origin remote" >&2
    exit 1
fi
OWNER_REPO=$(echo "$REMOTE_URL" | sed -E 's#.*[:/]([^/]+)/([^/.]+)(\.git)?$#\1/\2#')
OWNER=$(echo "$OWNER_REPO" | cut -d'/' -f1)
REPO=$(echo "$OWNER_REPO" | cut -d'/' -f2)

# --- Logging ---

TIMESTAMP() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log_event() {
    local event_json="$1"
    local ts
    ts=$(TIMESTAMP)
    local line="{\"timestamp\":\"$ts\",$event_json}"
    echo "$line" >> "$ORCH_LOG" 2>/dev/null || true
    echo "[$(date +%H:%M:%S)] $line" >&2
}

# --- Lockfile ---

LOCKFILE=".agents/orchestrator.lock"

acquire_lock() {
    if [ -f "$LOCKFILE" ]; then
        local old_pid
        old_pid=$(cat "$LOCKFILE" 2>/dev/null || echo "")
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            echo "Error: another orchestrator is running (PID $old_pid)" >&2
            exit 1
        fi
        echo "Stale lockfile found (PID $old_pid not running), removing" >&2
        rm -f "$LOCKFILE"
    fi
    echo $$ > "$LOCKFILE"
}

release_lock() {
    rm -f "$LOCKFILE" 2>/dev/null || true
}

trap release_lock EXIT


# ============================================================================
# Phase 1: Issue Discovery
# ============================================================================

discover_issues() {
    local issue_nums=()

    if [ -n "$ISSUES_ARG" ]; then
        # Explicit issue list from --issues flag
        IFS=',' read -ra issue_nums <<< "$ISSUES_ARG"
    else
        # Fetch from GitHub by label
        local gh_json
        gh_json=$(gh issue list --repo "${OWNER}/${REPO}" --label "$LABEL" --state open --json number --jq '.[].number' 2>/dev/null || echo "")
        if [ -z "$gh_json" ]; then
            echo "No open issues found with label '$LABEL'" >&2
            return 1
        fi
        while IFS= read -r num; do
            issue_nums+=("$num")
        done <<< "$gh_json"
    fi

    if [ ${#issue_nums[@]} -eq 0 ]; then
        echo "No issues to process" >&2
        return 1
    fi

    log_event "\"event\":\"discovery_start\",\"issue_count\":${#issue_nums[@]},\"issues\":[$(IFS=,; echo "${issue_nums[*]}")]"

    # Run preflight on each issue, collect metadata
    READY_ISSUES=()
    SKIPPED_ISSUES=()

    for num in "${issue_nums[@]}"; do
        local meta
        meta=$("${SCRIPT_DIR}/issue-preflight.sh" "$num" 2>/dev/null) || true
        local ready
        ready=$(echo "$meta" | jq -r '.ready' 2>/dev/null || echo "false")

        if [ "$ready" = "true" ]; then
            READY_ISSUES+=("$meta")
            echo "  ✓ Issue #$num — ready" >&2
        else
            SKIPPED_ISSUES+=("$meta")
            local reason
            reason=$(echo "$meta" | jq -r '.block_reason // "unknown"' 2>/dev/null)
            echo "  ✗ Issue #$num — skipped: $reason" >&2
            log_event "\"event\":\"issue_skipped\",\"issue\":$num,\"reason\":$(echo "$reason" | jq -Rs .)"
        fi
    done

    if [ ${#READY_ISSUES[@]} -eq 0 ]; then
        echo "No issues are ready to start" >&2
        log_event "\"event\":\"discovery_complete\",\"ready\":0,\"skipped\":${#SKIPPED_ISSUES[@]}"
        return 1
    fi

    log_event "\"event\":\"discovery_complete\",\"ready\":${#READY_ISSUES[@]},\"skipped\":${#SKIPPED_ISSUES[@]}"
    return 0
}

# ============================================================================
# Phase 2: Dependency Resolution (Kahn's algorithm → wave grouping)
# ============================================================================

# Globals populated by resolve_dependencies:
#   WAVES — bash array of space-separated issue numbers per wave
#   WAVE_COUNT — number of waves
#   ISSUE_META — associative array: issue_num → JSON metadata

declare -A ISSUE_META
declare -a WAVES
WAVE_COUNT=0

resolve_dependencies() {
    # Build lookup: issue_num → metadata JSON
    local all_nums=()
    for meta in "${READY_ISSUES[@]}"; do
        local num
        num=$(echo "$meta" | jq -r '.issue_number')
        ISSUE_META[$num]="$meta"
        all_nums+=("$num")
    done

    # Build adjacency list and in-degree count
    declare -A IN_DEGREE
    declare -A DEPENDENTS  # dep_num → space-separated list of issues that depend on it

    for num in "${all_nums[@]}"; do
        IN_DEGREE[$num]=0
    done

    for num in "${all_nums[@]}"; do
        local deps
        deps=$(echo "${ISSUE_META[$num]}" | jq -r '.depends_on[]' 2>/dev/null || echo "")
        for dep in $deps; do
            # Only count deps that are in our ready set
            if [ -n "${ISSUE_META[$dep]:-}" ]; then
                IN_DEGREE[$num]=$(( ${IN_DEGREE[$num]} + 1 ))
                DEPENDENTS[$dep]="${DEPENDENTS[$dep]:-} $num"
            fi
            # Deps outside our set are assumed already resolved (preflight checked)
        done
    done

    # Kahn's algorithm: peel off zero-in-degree nodes in waves
    local remaining=("${all_nums[@]}")
    WAVE_COUNT=0

    while [ ${#remaining[@]} -gt 0 ]; do
        local wave=()
        local next_remaining=()

        for num in "${remaining[@]}"; do
            if [ "${IN_DEGREE[$num]}" -eq 0 ]; then
                wave+=("$num")
            else
                next_remaining+=("$num")
            fi
        done

        if [ ${#wave[@]} -eq 0 ]; then
            echo "Error: dependency cycle detected among issues: ${remaining[*]}" >&2
            log_event "\"event\":\"cycle_detected\",\"issues\":[$(IFS=,; echo "${remaining[*]}")]"
            return 1
        fi

        # Separate parallel-safe and non-parallel-safe within this wave
        local parallel_batch=()
        local sequential_batch=()
        for num in "${wave[@]}"; do
            local psafe
            psafe=$(echo "${ISSUE_META[$num]}" | jq -r '.parallel_safe')
            if [ "$psafe" = "true" ]; then
                parallel_batch+=("$num")
            else
                sequential_batch+=("$num")
            fi
        done

        # Store wave: parallel issues first (space-separated), then sequential
        # Format: "P:101,102 S:103" — parsed by dispatch_wave
        local wave_str=""
        if [ ${#parallel_batch[@]} -gt 0 ]; then
            wave_str="P:$(IFS=,; echo "${parallel_batch[*]}")"
        fi
        if [ ${#sequential_batch[@]} -gt 0 ]; then
            [ -n "$wave_str" ] && wave_str+=" "
            wave_str+="S:$(IFS=,; echo "${sequential_batch[*]}")"
        fi
        WAVES[$WAVE_COUNT]="$wave_str"
        WAVE_COUNT=$(( WAVE_COUNT + 1 ))

        # Decrease in-degree for dependents of completed wave
        for num in "${wave[@]}"; do
            for dep_of in ${DEPENDENTS[$num]:-}; do
                IN_DEGREE[$dep_of]=$(( ${IN_DEGREE[$dep_of]} - 1 ))
            done
        done

        remaining=("${next_remaining[@]}")
    done

    # Print wave plan
    echo "" >&2
    echo "=== Wave Plan ===" >&2
    for (( w=0; w<WAVE_COUNT; w++ )); do
        echo "  Wave $((w+1)): ${WAVES[$w]}" >&2
    done
    echo "" >&2

    log_event "\"event\":\"waves_resolved\",\"wave_count\":$WAVE_COUNT,\"issues\":[$(IFS=,; echo "${all_nums[*]}")]"
    return 0
}


# ============================================================================
# Phase 3: Dispatch + Monitor
# ============================================================================

# Tracking arrays (indexed by issue number)
declare -A PIDS          # issue_num → PID
declare -A WT_PATHS      # issue_num → worktree path
declare -A DISPATCH_TIME # issue_num → epoch seconds
declare -A OUTCOMES      # issue_num → terminal state

launch_agent() {
    local issue_num="$1"
    local meta="${ISSUE_META[$issue_num]}"
    local tool
    tool=$(echo "$meta" | jq -r '.agent_tool')

    # Create worktree (setup only — don't launch agent yet)
    local wt_path
    wt_path=$("${SCRIPT_DIR}/wti.sh" "$issue_num" --setup-only 2>/dev/null)
    if [ -z "$wt_path" ] || [ ! -d "$wt_path" ]; then
        echo "  Error: failed to create worktree for issue #$issue_num" >&2
        OUTCOMES[$issue_num]="worktree_failed"
        log_event "\"event\":\"worktree_failed\",\"issue\":$issue_num"
        return 1
    fi
    WT_PATHS[$issue_num]="$wt_path"

    local prompt="Run /start-issue ${issue_num}"

    if [ "$DRY_RUN" = true ]; then
        echo "  [dry-run] Would launch $tool in $wt_path for issue #$issue_num" >&2
        OUTCOMES[$issue_num]="dry_run"
        log_event "\"event\":\"dry_run_dispatch\",\"issue\":$issue_num,\"agent_tool\":\"$tool\",\"worktree\":\"$wt_path\""
        return 0
    fi

    # Launch agent in background subshell
    case "$tool" in
        opencode)
            ( cd "$wt_path" && opencode --prompt "$prompt" ) &
            ;;
        claude)
            ( cd "$wt_path" && claude "$prompt" ) &
            ;;
        *)
            echo "  Warning: unknown tool '$tool' for issue #$issue_num, using opencode" >&2
            ( cd "$wt_path" && opencode --prompt "$prompt" ) &
            ;;
    esac

    local pid=$!
    PIDS[$issue_num]=$pid
    DISPATCH_TIME[$issue_num]=$(date +%s)

    echo "  → Issue #$issue_num dispatched (PID $pid, tool=$tool, path=$wt_path)" >&2
    log_event "\"event\":\"dispatch\",\"issue\":$issue_num,\"agent_tool\":\"$tool\",\"pid\":$pid,\"worktree\":\"$wt_path\""
    return 0
}

kill_agent() {
    local issue_num="$1"
    local pid="${PIDS[$issue_num]:-}"
    if [ -z "$pid" ]; then return 0; fi

    if kill -0 "$pid" 2>/dev/null; then
        echo "  Sending SIGTERM to PID $pid (issue #$issue_num)..." >&2
        kill "$pid" 2>/dev/null || true
        log_event "\"event\":\"kill_agent\",\"issue\":$issue_num,\"pid\":$pid,\"signal\":\"SIGTERM\""

        # Grace period
        local waited=0
        while [ $waited -lt "$KILL_GRACE" ] && kill -0 "$pid" 2>/dev/null; do
            sleep 1
            waited=$(( waited + 1 ))
        done

        if kill -0 "$pid" 2>/dev/null; then
            echo "  SIGKILL PID $pid (issue #$issue_num)" >&2
            kill -9 "$pid" 2>/dev/null || true
            log_event "\"event\":\"kill_agent\",\"issue\":$issue_num,\"pid\":$pid,\"signal\":\"SIGKILL\""
        fi
    fi
}

cleanup_worktree() {
    local issue_num="$1"
    echo "  Cleaning up worktree for issue #$issue_num..." >&2
    "${SCRIPT_DIR}/wtr.sh" "$issue_num" 2>/dev/null || true
    log_event "\"event\":\"cleanup\",\"issue\":$issue_num,\"worktree_removed\":true"
}

check_issue_status() {
    local issue_num="$1"
    local meta="${ISSUE_META[$issue_num]}"
    local auto_merge
    auto_merge=$(echo "$meta" | jq -r '.auto_merge')

    # 1. Check if PR exists
    local pr_num
    pr_num=$(gh pr list --repo "${OWNER}/${REPO}" --head "issue-${issue_num}" --json number --jq '.[0].number' 2>/dev/null || echo "")

    if [ -z "$pr_num" ]; then
        # No PR yet — check if agent is still running
        local pid="${PIDS[$issue_num]:-}"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            # Check for stall
            local now
            now=$(date +%s)
            local dispatched="${DISPATCH_TIME[$issue_num]}"
            local elapsed=$(( now - dispatched ))
            local stall_limit=$(( STALL_TIMEOUT * STALL_MULTIPLIER ))
            if [ $elapsed -gt $stall_limit ]; then
                echo "  ⚠ Issue #$issue_num stalled ($elapsed s elapsed)" >&2
                log_event "\"event\":\"stalled\",\"issue\":$issue_num,\"elapsed_s\":$elapsed"
                echo "stalled"
                return
            fi
            echo "running"
            return
        else
            # Agent exited without creating a PR
            echo "  ✗ Issue #$issue_num — agent exited without PR" >&2
            echo "session_ended_incomplete"
            return
        fi
    fi

    # PR exists — log first sighting
    if [ -z "${PR_NUMS[$issue_num]:-}" ]; then
        PR_NUMS[$issue_num]="$pr_num"
        log_event "\"event\":\"pr_created\",\"issue\":$issue_num,\"pr_number\":$pr_num"
    fi

    # 2. Check CI status
    local ci_status
    ci_status=$(gh pr checks "$pr_num" --repo "${OWNER}/${REPO}" --json state --jq '[.[].state] | if all(. == "SUCCESS") then "green" elif any(. == "FAILURE") then "red" else "pending" end' 2>/dev/null || echo "pending")

    # 3. Check mergeable status
    local mergeable
    mergeable=$(gh pr view "$pr_num" --repo "${OWNER}/${REPO}" --json mergeable --jq '.mergeable' 2>/dev/null || echo "UNKNOWN")

    if [ "$mergeable" = "CONFLICTING" ]; then
        echo "  ⚠ Issue #$issue_num (PR #$pr_num) — merge conflict" >&2
        log_event "\"event\":\"conflict_detected\",\"issue\":$issue_num,\"pr_number\":$pr_num"
        echo "conflict_detected"
        return
    fi

    if [ "$ci_status" = "red" ]; then
        # CI failed — agent may still be fixing. Check if PID alive.
        local pid="${PIDS[$issue_num]:-}"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "running"
            return
        fi
        echo "  ✗ Issue #$issue_num (PR #$pr_num) — CI failed, agent exited" >&2
        echo "session_ended_incomplete"
        return
    fi

    if [ "$ci_status" = "pending" ]; then
        echo "running"
        return
    fi

    # CI green + mergeable
    if [ "$ci_status" = "green" ] && [ "$mergeable" = "MERGEABLE" ]; then
        if [ "$auto_merge" = "true" ]; then
            echo "ready_to_merge"
        else
            echo "ready_for_review"
        fi
        return
    fi

    echo "running"
}

auto_merge_pr() {
    local issue_num="$1"
    local pr_num="${PR_NUMS[$issue_num]}"

    echo "  ✓ Auto-merging PR #$pr_num for issue #$issue_num..." >&2
    if gh pr merge "$pr_num" --repo "${OWNER}/${REPO}" --"$MERGE_METHOD" --delete-branch 2>/dev/null; then
        local now
        now=$(date +%s)
        local duration=$(( now - ${DISPATCH_TIME[$issue_num]} ))
        log_event "\"event\":\"auto_merged\",\"issue\":$issue_num,\"pr_number\":$pr_num,\"duration_s\":$duration"
        kill_agent "$issue_num"
        cleanup_worktree "$issue_num"
        OUTCOMES[$issue_num]="auto_merged"
    else
        echo "  ✗ Failed to merge PR #$pr_num" >&2
        log_event "\"event\":\"merge_failed\",\"issue\":$issue_num,\"pr_number\":$pr_num"
        OUTCOMES[$issue_num]="merge_failed"
    fi
}

declare -A PR_NUMS  # issue_num → PR number (populated on first sighting)

monitor_wave() {
    local wave_issues=("$@")
    local active=("${wave_issues[@]}")

    echo "" >&2
    echo "--- Monitoring ${#active[@]} issues ---" >&2

    while [ ${#active[@]} -gt 0 ]; do
        sleep "$POLL_INTERVAL"

        local still_active=()
        for num in "${active[@]}"; do
            local status
            status=$(check_issue_status "$num")

            case "$status" in
                running)
                    still_active+=("$num")
                    ;;
                ready_to_merge)
                    auto_merge_pr "$num"
                    ;;
                ready_for_review)
                    echo "  ✓ Issue #$num — PR ready for human review" >&2
                    log_event "\"event\":\"ready_for_review\",\"issue\":$num,\"pr_number\":${PR_NUMS[$num]:-0}"
                    OUTCOMES[$num]="ready_for_review"
                    ;;
                conflict_detected)
                    OUTCOMES[$num]="conflict_detected"
                    ;;
                session_ended_incomplete)
                    OUTCOMES[$num]="session_ended_incomplete"
                    log_event "\"event\":\"session_ended_incomplete\",\"issue\":$num"
                    ;;
                stalled)
                    # Kill stalled agent
                    kill_agent "$num"
                    OUTCOMES[$num]="killed_stalled"
                    log_event "\"event\":\"killed_stalled\",\"issue\":$num"
                    ;;
            esac
        done

        active=("${still_active[@]}")
        if [ ${#active[@]} -gt 0 ]; then
            echo "  ... ${#active[@]} still active" >&2
        fi
    done
}

dispatch_wave() {
    local wave_num="$1"
    local wave_str="${WAVES[$((wave_num - 1))]}"

    log_event "\"event\":\"wave_start\",\"wave\":$wave_num,\"spec\":\"$wave_str\""
    echo "=== Wave $wave_num: $wave_str ===" >&2

    local all_wave_issues=()

    # Parse wave string: "P:101,102 S:103"
    for segment in $wave_str; do
        local type="${segment%%:*}"
        local nums_csv="${segment#*:}"
        IFS=',' read -ra nums <<< "$nums_csv"

        if [ "$type" = "P" ]; then
            # Parallel batch — launch up to MAX_PARALLEL concurrently
            local batch=()
            for num in "${nums[@]}"; do
                launch_agent "$num"
                if [ "${OUTCOMES[$num]:-}" != "worktree_failed" ] && [ "${OUTCOMES[$num]:-}" != "dry_run" ]; then
                    batch+=("$num")
                fi
                all_wave_issues+=("$num")

                # Throttle if at max parallel
                if [ ${#batch[@]} -ge "$MAX_PARALLEL" ]; then
                    echo "  (max parallel $MAX_PARALLEL reached, waiting for batch)" >&2
                    if [ "$DRY_RUN" = false ]; then
                        monitor_wave "${batch[@]}"
                    fi
                    batch=()
                fi
            done
            # Monitor remaining parallel batch
            if [ ${#batch[@]} -gt 0 ] && [ "$DRY_RUN" = false ]; then
                monitor_wave "${batch[@]}"
            fi
        elif [ "$type" = "S" ]; then
            # Sequential — one at a time
            for num in "${nums[@]}"; do
                launch_agent "$num"
                all_wave_issues+=("$num")
                if [ "${OUTCOMES[$num]:-}" != "worktree_failed" ] && [ "${OUTCOMES[$num]:-}" != "dry_run" ]; then
                    if [ "$DRY_RUN" = false ]; then
                        monitor_wave "$num"
                    fi
                fi
            done
        fi
    done

    log_event "\"event\":\"wave_complete\",\"wave\":$wave_num"
    echo "=== Wave $wave_num complete ===" >&2
    echo "" >&2
}

update_main() {
    echo "Updating local main from origin..." >&2
    git fetch origin main 2>/dev/null || true
    local current_branch
    current_branch=$(git branch --show-current 2>/dev/null || echo "")

    if [ "$current_branch" != "main" ]; then
        git checkout main 2>/dev/null || true
    fi

    if git merge --ff-only origin/main 2>/dev/null; then
        local sha
        sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
        log_event "\"event\":\"main_updated\",\"sha\":\"$sha\""
        echo "  Main updated to $sha" >&2
    else
        echo "  Warning: fast-forward merge failed, resetting to origin/main" >&2
        git reset --hard origin/main 2>/dev/null || true
        log_event "\"event\":\"main_updated\",\"sha\":\"$(git rev-parse --short HEAD 2>/dev/null)\",\"method\":\"reset\""
    fi
}


# ============================================================================
# Phase 4: Summary
# ============================================================================

print_summary() {
    echo "" >&2
    echo "============================================" >&2
    echo "  Orchestrator Summary" >&2
    echo "============================================" >&2

    local merged=0 review=0 conflicts=0 incomplete=0 stalled=0 failed=0 dry=0

    for num in "${!OUTCOMES[@]}"; do
        local outcome="${OUTCOMES[$num]}"
        local title
        title=$(echo "${ISSUE_META[$num]}" | jq -r '.title' 2>/dev/null || echo "?")
        printf "  #%-5s %-25s %s\n" "$num" "$outcome" "$title" >&2

        case "$outcome" in
            auto_merged) merged=$(( merged + 1 )) ;;
            ready_for_review) review=$(( review + 1 )) ;;
            conflict_detected) conflicts=$(( conflicts + 1 )) ;;
            session_ended_incomplete|merge_failed|worktree_failed) incomplete=$(( incomplete + 1 )) ;;
            killed_stalled) stalled=$(( stalled + 1 )) ;;
            dry_run) dry=$(( dry + 1 )) ;;
        esac
    done

    echo "--------------------------------------------" >&2
    echo "  Merged: $merged  Review: $review  Conflicts: $conflicts  Incomplete: $incomplete  Stalled: $stalled" >&2
    if [ $dry -gt 0 ]; then
        echo "  Dry-run: $dry" >&2
    fi
    echo "============================================" >&2

    log_event "\"event\":\"summary\",\"merged\":$merged,\"ready_for_review\":$review,\"conflicts\":$conflicts,\"incomplete\":$incomplete,\"stalled\":$stalled"
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo "Orchestrator starting (repo: ${OWNER}/${REPO}, max_parallel: $MAX_PARALLEL)" >&2
    log_event "\"event\":\"start\",\"repo\":\"${OWNER}/${REPO}\",\"max_parallel\":$MAX_PARALLEL,\"dry_run\":$DRY_RUN"

    acquire_lock

    # Phase 1: Discover
    if ! discover_issues; then
        log_event "\"event\":\"abort\",\"reason\":\"no issues ready\""
        exit 0
    fi

    # Phase 2: Resolve dependencies
    if ! resolve_dependencies; then
        log_event "\"event\":\"abort\",\"reason\":\"dependency resolution failed\""
        exit 1
    fi

    # Dry-run summary
    if [ "$DRY_RUN" = true ]; then
        echo "" >&2
        echo "[dry-run] Would execute $WAVE_COUNT wave(s):" >&2
        for (( w=0; w<WAVE_COUNT; w++ )); do
            echo "  Wave $((w+1)): ${WAVES[$w]}" >&2
        done

        # Still dispatch in dry-run mode (prints what would happen)
        for (( w=0; w<WAVE_COUNT; w++ )); do
            dispatch_wave $(( w + 1 ))
        done

        print_summary
        exit 0
    fi

    # Phase 3: Execute waves
    for (( w=0; w<WAVE_COUNT; w++ )); do
        dispatch_wave $(( w + 1 ))

        # Update main between waves (not after the last one)
        if [ $(( w + 1 )) -lt "$WAVE_COUNT" ]; then
            update_main
        fi
    done

    # Phase 4: Summary
    print_summary
}

main
