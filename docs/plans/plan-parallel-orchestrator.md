# Plan: Parallel Issue Orchestrator

## Goal

Build a lightweight orchestrator that replaces the human-in-the-loop for batch issue execution. It fetches open issues from the repo, analyzes which are ready to start (no unmerged blockers), dispatches parallel agent sessions via worktrees, and for auto-merge-eligible issues handles the full lifecycle through to merge + cleanup. The orchestrator does NOT own the grind loop, code review, or fix loop — those remain issue-level concerns handled by the existing agent harness.

## Context

Current workflow: human runs `wti <issue> -c/-o` to create a worktree and launch an agent. The agent handles everything (plan, TDD, grind loop, review, PR). Human then reviews and merges.

The orchestrator replaces the human's role in:

1. Deciding which issues to start (dependency analysis)
2. Starting the worktree + agent session
3. Monitoring progress (did the agent produce a reviewed PR with green CI?)
4. For auto-merge issues: merging the PR and cleaning up the worktree
5. For human-review issues: stopping at "PR ready for review" and notifying

It does NOT replace:

- The grind loop (per-session, handled by check-completion.sh / grind-loop.ts)
- Code review (code-reviewer subagent, triggered by the agent)
- The fix loop (agent fixes review findings, re-runs review)
- Plan creation (agent creates the plan file per start-issue.md)

Think of it as: `orchestrate.sh` is the human who opens N terminal tabs, runs `wti` in each, and periodically checks "is the PR ready yet?"

## Design Principles

- The orchestrator is a stand-in for the human, not a replacement for the agent harness
- Shell-first: bash script using `gh`, `jq`, `wt` (worktrunk CLI)
- Issue metadata in the issue body drives behavior (dependencies, parallelism, auto-merge)
- `wti`/`wtr` logic extracted from zshrc into portable bash scripts in `scripts/`
- Fail-safe: ambiguous metadata = don't start, don't merge
- Observable: logs to `.agents/orchestrator-log.jsonl`

## Issue Template

GitHub issue template with Agent Metadata table. The orchestrator parses this from the issue body.

```markdown
---
name: Feature / Task
about: Standard issue with orchestrator metadata
labels: []
---

## Description

_What needs to be done._

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Agent Metadata

<!-- The orchestrator reads these fields. Keep the format exact. -->

| Field                | Value    |
| -------------------- | -------- |
| Depends on           | #none    |
| Parallel safe        | yes      |
| Auto-merge           | no       |
| Agent tool           | opencode |
| Estimated complexity | small    |
```

### Field definitions

- **Depends on**: Comma-separated issue numbers (e.g., `#41, #42`) or `#none`. Orchestrator won't start this issue until all dependencies have merged PRs.
- **Parallel safe**: `yes` / `no`. If `no`, the orchestrator runs this issue alone (not concurrently with others).
- **Auto-merge**: `yes` / `no`. If `yes`, the orchestrator merges the PR and cleans up the worktree once all gates pass. If `no`, stops at "PR ready" and waits for human.
- **Agent tool**: `opencode` / `claude`. Which agent tool to launch. Defaults to `opencode` if missing. (`kiro` is interactive-only, not supported in orchestrator mode.)
- **Estimated complexity**: `small` / `medium` / `large`. Informational.

### Enforcement

GitHub's template chooser config (`.github/ISSUE_TEMPLATE/config.yml`) disables blank issues, forcing all new issues through a template. This ensures every issue has the Agent Metadata table.

```yaml
blank_issues_enabled: false
```

### Migration

Existing open issues that predate the template need their body updated to include the Agent Metadata table with appropriate defaults. Currently there is 1 open issue (#164 — automated doc gardening). The `issue-preflight.sh` script handles missing metadata gracefully (defaults to `parallel_safe: true, auto_merge: false, agent_tool: opencode`) so migration is not blocking, but the orchestrator works best when metadata is explicit.

## Acceptance Criteria

- [x] `scripts/wti.sh` — portable bash version of the `wti` zshrc function
- [x] `scripts/wtr.sh` — portable bash version of the `wtr` zshrc function
- [x] GitHub issue template (`.github/ISSUE_TEMPLATE/feature-task.md`) with Agent Metadata table
- [x] GitHub template chooser config (`.github/ISSUE_TEMPLATE/config.yml`) — blank issues disabled
- [x] Existing open issues updated with Agent Metadata table (currently #164)
- [x] `scripts/issue-preflight.sh` — validates a single issue, parses Agent Metadata, checks deps
- [x] `scripts/orchestrate.sh` — fetches open issues, analyzes readiness, dispatches, monitors, handles auto-merge + cleanup
- [x] Orchestrator resolves repo owner/name from `git remote` (no hardcoding)
- [x] Orchestrator respects `Depends on` — topological sort, won't start blocked issues
- [x] Orchestrator respects `Parallel safe: no` — runs those sequentially
- [x] Orchestrator respects `Auto-merge: yes` — merges via `gh pr merge --squash` + calls `wtr.sh` for cleanup
- [x] Orchestrator respects `Agent tool` — launches the correct tool per issue
- [x] Orchestrator keeps local main updated between waves
- [x] Merge conflicts resolved within the worktree by the agent (not orchestrator)
- [x] Agent sessions terminated cleanly after merge
- [x] Orchestrator log (`.agents/orchestrator-log.jsonl`)
- [x] `start-issue.md` updated to call `issue-preflight.sh`
- [x] Documentation updated
- [x] Existing tests unaffected

## Key Operational Questions (Answered)

### Q1: Worktrees are siblings — how does the orchestrator launch agents in the right directory?

`wt switch -c issue-N` creates a worktree as a sibling directory to the main repo (e.g., `~/Development/personal/alpacalyzer/issue-101/`). The orchestrator needs to:

1. Create the worktree: `wt switch -c "issue-$N" --no-cd` (creates without changing the orchestrator's cwd)
2. Discover the worktree path: `wt list --format json | jq -r '.[] | select(.branch == "issue-N") | .path'`
3. Launch the agent in that directory:
   - OpenCode: `(cd "$wt_path" && bash .agents/hooks/opencode-grind-loop.sh "$prompt") &`
   - Claude: `(cd "$wt_path" && claude "$prompt") &`

The `post-create` hooks in `wt.toml` handle environment setup (copy `.env`, `uv sync`, `setup-agent-links.sh`) — these fire automatically when `wt switch -c` runs, so by the time the orchestrator gets the path back, the worktree is fully provisioned.

The prompt is issue-specific: `"read AGENTS.md and start work on issue $N. Make sure to use skills from SKILL.md when appropriate."` — same as the current `wti` function.

### Q2: How are agent sessions terminated after merge?

Two scenarios:

**Agent already exited (normal case):** The agent runs through the grind loop, creates a PR, and the grind loop's `check-completion.sh` eventually returns exit 0 (all checks pass). The `opencode --prompt` or `claude` command exits. The orchestrator's background PID completes. Nothing to kill.

**Agent still running when orchestrator wants to merge:** This shouldn't happen in the normal flow because the orchestrator only merges after detecting "PR exists + CI green + review clean" — which means the agent already finished its work and the grind loop exited. But as a safety net:

1. After `gh pr merge`, the orchestrator sends `SIGTERM` to the agent PID (if still running)
2. Waits 10s for graceful shutdown
3. If still alive, `SIGKILL`
4. Then `wtr.sh` cleans up the worktree

For Claude Code: `claude` respects SIGTERM and exits cleanly.
For OpenCode: `opencode --prompt` exits when the agent stops; the `opencode-grind-loop.sh` wrapper's `timeout` command also handles this.

### Q3: Where are merge conflicts resolved?

**Within the worktree, by the agent.** The orchestrator never resolves conflicts.

The scenario: issues #101 and #102 run in parallel. #101 merges first. Now #102's branch is behind main and may have conflicts.

How it works:

1. GitHub's PR checks will show "branch is out of date" or merge conflicts
2. The agent in #102's worktree is responsible for rebasing/merging main into its branch — this is already part of the agent's normal workflow (the `create-pr.md` command pushes to a branch, and GitHub shows conflict status)
3. If the agent has already exited and the PR has conflicts, the orchestrator logs `conflict_detected` and flags it for human attention — it does NOT attempt to resolve conflicts itself

**Prevention strategy:** The orchestrator processes waves sequentially. Issues in the same wave are parallel-safe (they shouldn't touch the same files). Dependencies are in earlier waves and merge before dependents start. This minimizes conflict risk.

**If conflicts still happen** (parallel-safe issues unexpectedly overlap):

- The orchestrator detects it via `gh pr view $PR --json mergeable` returning `"CONFLICTING"`
- Logs `conflict_detected` event
- Does NOT auto-merge (even if `auto_merge: yes`)
- Flags for human intervention

### Q4: Who keeps local main updated with origin changes?

**The orchestrator, between waves.**

After each wave completes (all issues in the wave reach terminal state):

1. `git fetch origin main` — get latest from remote
2. `git checkout main && git merge --ff-only origin/main` — fast-forward local main (this is safe because the orchestrator runs from the main worktree and doesn't make changes there)
3. This ensures the next wave's worktrees branch from the latest main, which includes the merged PRs from the previous wave

Within a wave, main is NOT updated — parallel worktrees all branched from the same main at wave start. This is intentional: updating main mid-wave would require rebasing running worktrees, which is dangerous.

The `pre-switch` hook in `wt.toml` already does a `git fetch` if stale (>6 hours), but the orchestrator is more aggressive — it fetches between every wave.

For auto-merged PRs: GitHub merges to remote main. The orchestrator's `git fetch + ff-only merge` picks this up before the next wave.

## Architecture

```
orchestrate.sh (runs from main worktree)
│
├─ Phase 1: Discovery
│  ├─ git remote get-url origin → OWNER/REPO
│  ├─ gh issue list --label orchestrator-ready --state open
│  └─ issue-preflight.sh each → metadata JSON
│
├─ Phase 2: Dependency Resolution
│  ├─ Build adjacency list from Depends on
│  ├─ Topological sort (Kahn's algorithm)
│  └─ Group into waves
│
├─ Phase 3: Per-Wave Execution
│  │
│  ├─ Wave 1: [#101, #102] (parallel safe, no deps)
│  │  ├─ wt switch -c issue-101 --no-cd
│  │  │  └─ post-create hooks fire (uv sync, .env, agent-links)
│  │  ├─ wt_path=$(wt list --format json | jq ...)
│  │  ├─ (cd $wt_path && opencode --prompt "$prompt") &        → PID_101
│  │  ├─ (cd $wt_path && claude "$prompt") &                   → PID_102
│  │  │
│  │  ├─ Monitor loop (poll every 60s):
│  │  │  ├─ gh pr list --head issue-101 → PR exists?
│  │  │  ├─ gh pr checks $PR → CI green?
│  │  │  ├─ gh pr view $PR --json mergeable → conflicts?
│  │  │  ├─ PID still running?
│  │  │  └─ Session log updated recently?
│  │  │
│  │  ├─ #101: auto_merge=yes + all green → gh pr merge --squash
│  │  │  ├─ kill PID_101 (if still running)
│  │  │  └─ wtr.sh 101
│  │  ├─ #102: auto_merge=no + all green → log "ready_for_review"
│  │  │
│  │  └─ Wave 1 complete
│  │
│  ├─ Update local main: git fetch origin && git merge --ff-only origin/main
│  │
│  └─ Wave 2: [#103] (depends on #101)
│     ├─ wt switch -c issue-103 --no-cd  (branches from updated main)
│     └─ ... same pattern ...
│
└─ Phase 4: Summary
   ├─ Print results table
   └─ Write to orchestrator-log.jsonl
```

## Detailed Design

### 1. `scripts/wti.sh` — Portable Worktree Issue Start

Extracted from the zshrc `wti()` function. Pure bash, no zsh dependencies.

```bash
scripts/wti.sh <issue_number> (-o|-c) [--setup-only]

# Normal use (same as zshrc wti):
scripts/wti.sh 101 -o    # Create worktree + launch OpenCode
scripts/wti.sh 101 -c    # Create worktree + launch Claude Code

# Orchestrator use:
scripts/wti.sh 101 --setup-only   # Create worktree only, print path
```

Implementation:

1. `wt switch -c "issue-$issue_num" --no-cd` — create worktree without cd'ing
2. Get worktree path: `wt list --format json | jq -r ".[] | select(.branch == \"issue-$issue_num\") | .path"`
3. If `--setup-only`: print path to stdout and exit 0
4. Otherwise, build prompt and launch agent:
   - `-o`: `cd "$wt_path" && opencode --prompt "$prompt"` (grind loop handled by `grind-loop.ts` plugin loaded automatically from `.opencode/plugins/`)
   - `-c`: `cd "$wt_path" && claude "$prompt"` (grind loop handled by Claude's Stop hook firing `check-completion.sh`)
5. Exit code passthrough from agent tool

### 2. `scripts/wtr.sh` — Portable Worktree Issue Remove

```bash
scripts/wtr.sh <issue_number> [-m]
```

Implementation:

1. `branch_name="issue-$issue_num"`
2. If `-m`: `wt merge "$branch_name"` then remove
3. Else: `wt remove "$branch_name" -D`

### 3. `scripts/issue-preflight.sh` — Single Issue Validation

```bash
scripts/issue-preflight.sh <issue_number>
```

Steps:

1. Resolve OWNER/REPO from `git remote get-url origin`
2. Fetch issue: `gh issue view $N --json state,body,title,number`
3. Check issue is open (exit 2 if closed/not found)
4. Check no existing open PR: `gh pr list --head "issue-$N" --json number`
5. Parse Agent Metadata table from issue body via grep/sed:
   - `| Depends on | ... |` → extract issue numbers
   - `| Parallel safe | ... |` → yes/no
   - `| Auto-merge | ... |` → yes/no
   - `| Agent tool | ... |` → opencode/claude
   - `| Estimated complexity | ... |` → small/medium/large
   - No Agent Metadata → defaults: `depends_on=[], parallel_safe=true, auto_merge=false, agent_tool=opencode, complexity=medium`
6. For each dependency: check if merged via `gh pr list --search "issue-$dep in:head" --state merged`
   - Unmerged dep → exit 1 with block reason
7. Output JSON to stdout:

```json
{
  "issue_number": 101,
  "title": "Add foo feature",
  "depends_on": [],
  "parallel_safe": true,
  "auto_merge": false,
  "agent_tool": "opencode",
  "complexity": "small",
  "ready": true,
  "block_reason": null
}
```

Exit codes: 0 = ready, 1 = blocked, 2 = not found/closed.

### 4. `scripts/orchestrate.sh` — The Orchestrator

```bash
scripts/orchestrate.sh [--max-parallel N] [--dry-run] [--label LABEL] [--issues N,N,N]

# Fetch all open issues with label:
scripts/orchestrate.sh --label orchestrator-ready

# Specific issues:
scripts/orchestrate.sh --issues 101,102,103

# Dry run:
scripts/orchestrate.sh --dry-run --label orchestrator-ready

# Limit parallelism:
scripts/orchestrate.sh --max-parallel 2 --label orchestrator-ready
```

#### Phase 1: Issue Discovery

1. Resolve OWNER/REPO from `git remote get-url origin`
2. If `--issues`: use those. Else: `gh issue list --label "$LABEL" --state open --json number`
3. Run `issue-preflight.sh` on each → collect metadata JSON
4. Filter to `ready: true` only. Log skipped issues with reasons.

#### Phase 2: Dependency Resolution

1. Build adjacency list from `depends_on` fields
2. Topological sort (Kahn's algorithm — bash arrays + loop)
3. Cycle detected → abort with error
4. Group into waves: wave N = issues whose deps are all in waves < N
5. Within each wave, separate `parallel_safe: false` issues

#### Phase 3: Per-Wave Dispatch + Monitor

For each wave:

**Dispatch:**

1. For each issue in the wave:
   - `scripts/wti.sh $N --setup-only` → get `$wt_path`
   - Determine agent command from metadata:
     - `opencode`: `opencode --prompt "$prompt"` (grind loop is the `grind-loop.ts` plugin, loaded automatically from `.opencode/plugins/`)
     - `claude`: `claude "$prompt"` (grind loop is the Stop hook firing `check-completion.sh`)
   - Launch in subshell: `(cd "$wt_path" && $agent_cmd) &` → capture PID
   - Log dispatch event
   - Parallel-safe issues launch concurrently (up to `--max-parallel`)
   - Non-parallel-safe issues launch sequentially after parallel batch

**Monitor (poll every `poll_interval_seconds`):**

For each dispatched issue, check:

1. Is PID still running? (`kill -0 $PID 2>/dev/null`)
2. Does a PR exist? (`gh pr list --head "issue-$N" --json number,state`)
3. Is CI green? (`gh pr checks $PR_NUMBER --json name,state,conclusion`)
4. Is it mergeable? (`gh pr view $PR --json mergeable` — catches conflicts)
5. Is review approved? (PR review status or `CODE_REVIEW_*.md` in worktree)

**Terminal states per issue:**

| State                      | Condition                                                  | Action                                                                 |
| -------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------- |
| `auto_merged`              | PR + CI green + mergeable + `auto_merge: yes`              | `gh pr merge --squash --delete-branch`, kill PID if alive, `wtr.sh $N` |
| `ready_for_review`         | PR + CI green + mergeable + `auto_merge: no`               | Log, move on (human takes over)                                        |
| `conflict_detected`        | PR exists but `mergeable: CONFLICTING`                     | Log, flag for human. Do NOT merge.                                     |
| `session_ended_incomplete` | PID exited but no PR or CI not green                       | Log, flag for human. Don't retry.                                      |
| `stalled`                  | PID running but no session log update for 2× stall_timeout | Log warning. If persists, kill PID + log `killed_stalled`.             |

**Terminating agent sessions after auto-merge:**

After `gh pr merge` succeeds:

1. Check if PID is still alive: `kill -0 $PID 2>/dev/null`
2. If alive (agent still running — rare, means grind loop hasn't noticed completion yet):
   - `kill $PID` (SIGTERM — both `claude` and `opencode` handle this gracefully)
   - `sleep 5`
   - If still alive: `kill -9 $PID` (SIGKILL as last resort)
3. `scripts/wtr.sh $N` — remove the worktree

For `ready_for_review` issues: the orchestrator does NOT kill the agent. The agent may still be running its grind loop. The human takes over from here.

**Note on grind loop mechanisms:** OpenCode has two grind loop implementations:

- `grind-loop.ts` plugin (`.opencode/plugins/`) — runs inside OpenCode, listens to `session.idle` events, re-prompts internally. This is the primary mechanism and what the orchestrator relies on.
- `opencode-grind-loop.sh` (`.agents/hooks/`) — external bash wrapper that loops `opencode --prompt` with `timeout`. This is a fallback for environments where the plugin isn't available (e.g., CI without the `.opencode/` directory).

The orchestrator uses `opencode --prompt` directly, relying on the plugin for grind loop behavior. The plugin is available in every worktree because `.opencode/plugins/grind-loop.ts` is a tracked file in the repo — `wt switch -c` creates a full git checkout that includes it.

**Between waves — update local main:**

```bash
git fetch origin main
git checkout main
git merge --ff-only origin/main
```

This ensures the next wave's `wt switch -c` branches from main that includes all merged PRs from previous waves. The `--ff-only` is safe because the orchestrator never commits to main directly.

### 5. Merge Conflict Resolution Strategy

**Conflicts are the agent's problem, not the orchestrator's.**

Why: the agent has full context about the changes it made. The orchestrator has zero context — it just monitors outcomes.

**Prevention (orchestrator's job):**

- Dependency ordering via waves: if #102 depends on #101, #101 merges first, #102 starts from updated main
- `parallel_safe: no` issues run alone — no concurrent modifications
- Between-wave main update ensures clean branch points

**Detection (orchestrator's job):**

- Poll `gh pr view $PR --json mergeable` — GitHub reports `CONFLICTING` if the PR can't be cleanly merged
- If detected: log `conflict_detected`, do NOT auto-merge, flag for human

**Resolution (NOT orchestrator's job — two paths):**

Path A — Agent still running: The agent's grind loop will eventually run tests. If the branch is behind main and tests fail due to missing upstream changes, the agent should rebase. The `check-completion.sh` follow-up prompt will tell it "tests are failing" and the agent can investigate. This is the normal grind loop flow.

Path B — Agent exited, PR has conflicts: The orchestrator logs `conflict_detected`. Human intervention required. The human can either:

- Manually resolve in the worktree
- Re-run `wti.sh $N -o` to start a new agent session that rebases and fixes

The orchestrator never touches code. It's a dispatcher and monitor.

### 6. Who Updates Local Main?

**The orchestrator, between waves only.**

| When              | Who               | What                                                  | Why                                                        |
| ----------------- | ----------------- | ----------------------------------------------------- | ---------------------------------------------------------- |
| Between waves     | Orchestrator      | `git fetch origin && git merge --ff-only origin/main` | Next wave branches from latest main                        |
| During a wave     | Nobody            | Main is frozen for the wave's duration                | Updating mid-wave would require rebasing running worktrees |
| Within a worktree | Agent (if needed) | `git fetch origin main && git rebase origin/main`     | Agent rebases its own branch if behind                     |
| After auto-merge  | GitHub            | Remote main updated via PR merge                      | Orchestrator picks this up in the between-wave fetch       |

The orchestrator runs from the main worktree directory. It never makes commits to main — only fast-forward merges from origin. This is safe because the main worktree is read-only during orchestration.

### 7. Config additions to `.agents/config.yaml`

```yaml
orchestrator:
  max_parallel: 3
  poll_interval_seconds: 60
  stall_detection_multiplier: 2 # stall if no update for 2x grind_loop.stall_timeout_seconds
  log: .agents/orchestrator-log.jsonl
  auto_merge_method: squash # squash | merge | rebase
  default_agent_tool: opencode # opencode | claude
  default_label: orchestrator-ready
  kill_grace_seconds: 5 # time between SIGTERM and SIGKILL
```

### 8. Orchestrator Log

`.agents/orchestrator-log.jsonl` — one line per event:

```json
{"timestamp":"...","event":"start","issues":[101,102,103],"waves":2}
{"timestamp":"...","event":"wave_start","wave":1,"issues":[101,102]}
{"timestamp":"...","event":"dispatch","issue":101,"agent_tool":"opencode","pid":12345,"worktree":"/path/to/issue-101"}
{"timestamp":"...","event":"pr_created","issue":101,"pr_number":42}
{"timestamp":"...","event":"ci_green","issue":101,"pr_number":42}
{"timestamp":"...","event":"auto_merged","issue":101,"pr_number":42,"duration_s":1080}
{"timestamp":"...","event":"kill_agent","issue":101,"pid":12345,"signal":"SIGTERM"}
{"timestamp":"...","event":"cleanup","issue":101,"worktree_removed":true}
{"timestamp":"...","event":"ready_for_review","issue":102,"pr_number":43}
{"timestamp":"...","event":"wave_complete","wave":1}
{"timestamp":"...","event":"main_updated","sha":"abc123"}
{"timestamp":"...","event":"wave_start","wave":2,"issues":[103]}
{"timestamp":"...","event":"conflict_detected","issue":103,"pr_number":44}
{"timestamp":"...","event":"summary","merged":1,"ready_for_review":1,"conflicts":1,"incomplete":0}
```

## Files to Create/Modify

| File                                     | Change                                             |
| ---------------------------------------- | -------------------------------------------------- |
| `scripts/wti.sh`                         | NEW — portable wti (bash), supports `--setup-only` |
| `scripts/wtr.sh`                         | NEW — portable wtr (bash)                          |
| `.github/ISSUE_TEMPLATE/feature-task.md` | NEW — issue template with Agent Metadata           |
| `.github/ISSUE_TEMPLATE/config.yml`      | NEW — disable blank issues, enforce template usage |
| `scripts/issue-preflight.sh`             | NEW — single-issue validation + metadata parsing   |
| `scripts/orchestrate.sh`                 | NEW — batch orchestrator                           |
| `.agents/config.yaml`                    | ADD orchestrator section                           |
| `.agents/commands/start-issue.md`        | ADD preflight step                                 |
| `.gitignore`                             | ADD `.agents/orchestrator-log.jsonl`               |
| `docs/dev/tdd-flow.md`                   | ADD orchestrator section                           |
| `docs/dev/parallel-exploration.md`       | UPDATE — reference orchestrator                    |
| `docs/INDEX.md`                          | ADD orchestrator entries                           |

Migration (one-time, during implementation):

- Update open issue #164 body to include Agent Metadata table with defaults

## Implementation Order

1. `.github/ISSUE_TEMPLATE/feature-task.md` + `.github/ISSUE_TEMPLATE/config.yml` — template + enforcement
2. Migrate open issue #164 to include Agent Metadata table
3. `scripts/wti.sh` + `scripts/wtr.sh` — extract from zshrc, make portable
4. `scripts/issue-preflight.sh` — standalone, testable
5. Update `start-issue.md` to call preflight
6. Config additions to `.agents/config.yaml`
7. `scripts/orchestrate.sh` — the main orchestrator
8. Documentation updates + `.gitignore`

## Test Scenarios

| Scenario                                                         | Expected                                                            |
| ---------------------------------------------------------------- | ------------------------------------------------------------------- |
| `wti.sh 101 -o`                                                  | Creates worktree `issue-101`, launches opencode grind loop          |
| `wti.sh 101 --setup-only`                                        | Creates worktree, prints path, doesn't launch agent                 |
| `wtr.sh 101`                                                     | Removes worktree for issue-101                                      |
| `wtr.sh 101 -m`                                                  | Merges then removes                                                 |
| `issue-preflight.sh` on open issue, no blockers                  | Exit 0, JSON `ready: true`                                          |
| `issue-preflight.sh` on closed issue                             | Exit 2                                                              |
| `issue-preflight.sh` on issue with unmerged dep                  | Exit 1, `block_reason` explains                                     |
| `issue-preflight.sh` on issue with existing PR                   | Exit 1                                                              |
| `issue-preflight.sh` on issue without Agent Metadata             | Exit 0, defaults applied                                            |
| `orchestrate.sh --dry-run --issues 101,102,103` (independent)    | Shows 1 wave, 3 parallel                                            |
| `orchestrate.sh --dry-run --issues 101,102` (102 depends on 101) | Shows 2 waves                                                       |
| `orchestrate.sh --dry-run` with cycle                            | Aborts with cycle error                                             |
| `orchestrate.sh --dry-run` with `parallel_safe: no`              | That issue runs alone                                               |
| Orchestrate dispatches and monitors                              | Launches agents in correct worktree dirs                            |
| Auto-merge fires                                                 | `gh pr merge --squash`, kill PID, `wtr.sh` cleanup                  |
| Auto-merge skipped for conflicts                                 | Logs `conflict_detected`, flags for human                           |
| Between-wave main update                                         | `git fetch + merge --ff-only`, next wave branches from updated main |
| Agent PID terminated after merge                                 | SIGTERM → wait → SIGKILL if needed                                  |
| Stall detection                                                  | Logs stall after 2× timeout with no session update                  |

## Risks

- `wt switch -c --no-cd` may still trigger shell integration that changes directory. Mitigation: test, fall back to raw `git worktree add` + manual hook execution.
- `opencode --prompt` and `claude` may need TTY for some features. Mitigation: test headless, use `script -q /dev/null` wrapper if needed for pseudo-TTY.
- Agent Metadata parsing from issue body is regex-based. Mitigation: strict template format, default to safe values on parse failure.
- Multiple orchestrator instances could race. Mitigation: lockfile `.agents/orchestrator.lock` with PID check.
- `gh pr merge` could fail if branch protection requires specific reviewers. Mitigation: check merge status before attempting, log failure.
- Parallel-safe issues may still conflict if they unexpectedly touch the same files. Mitigation: orchestrator detects via `mergeable` check, flags for human.
- `git merge --ff-only` fails if main has diverged (shouldn't happen if orchestrator is the only merger). Mitigation: fall back to `git reset --hard origin/main`.

## Future Extensions (not in scope)

- Cron/launchd job that runs `orchestrate.sh --label orchestrator-ready` nightly
- Slack/Discord webhook notifications on completion or stall
- Cost tracking per issue (aggregate token usage from session logs)
- Web dashboard reading orchestrator log
- Retry logic for incomplete sessions
- Priority-based dispatch within waves
