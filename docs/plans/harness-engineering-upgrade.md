# Harness Engineering Upgrade Plan

**Based on**:

- [OpenAI — Harness Engineering](https://openai.com/index/harness-engineering/)
- [Cursor — Agent Best Practices](https://cursor.com/blog/agent-best-practices)

**Tools**: Claude Code + OpenCode (multi-provider via `wti` shell function)
**Repo**: Alpacalyzer Algo Trader
**Date**: February 16, 2026

---

## Current State Assessment

### What This Repo Already Does Well

| Concept from Blog          | Repo Implementation                                                                   | Status   |
| -------------------------- | ------------------------------------------------------------------------------------- | -------- |
| AGENTS.md as entry point   | 400+ line AGENTS.md with architecture, rules, TDD flow                                | ✅ Solid |
| Skills / procedural guides | 7 skill files in `.claude/skills/` (agents, scanners, strategies, etc.)               | ✅ Good  |
| Automated code review      | `code-reviewer` subagent writes `CODE_REVIEW_*.md` (~90% auto-triggered via steering) | ✅ Good  |
| Worktree isolation         | `wt.toml` with post-create hooks, pre-merge gates                                     | ✅ Good  |
| Pre-commit enforcement     | ruff, ty, bandit, pytest, prettier                                                    | ✅ Good  |
| CI merge gates             | PR workflow: lint → typecheck → test (parallel)                                       | ✅ Good  |
| Multi-provider workflow    | `wti 66 -c` (Claude Code) / `wti 66 -o` (OpenCode)                                    | ✅ Good  |
| Feature flags for rollback | `USE_NEW_LLM` flag for LLM migration                                                  | ✅ Good  |

### Current Development Flow

```
wti 66 -c  →  worktrunk creates worktree  →  post-create hooks (uv sync, .env copy)
           →  agent reads AGENTS.md       →  implements feature (TDD)
           →  steering triggers code-reviewer ~90% of the time
           →  agent creates PR
           →  pre-merge gates (pytest, ruff, ty) block bad merges
           →  wtr 66 cleans up
```

### What's Missing (Gap Analysis vs. Both Blogs)

Both blogs describe systems where agents operate with near-full autonomy across the entire dev lifecycle. This repo has strong foundations but is missing several key layers that both sources identify as critical multipliers.

---

## Gap 1: Observability Is Not Agent-Legible

**Blog says**: "Logs, metrics, and traces are exposed to agents via a local observability stack."

**Current state**: The repo has `events/` module with structured JSON logging and log files in `logs/`, but:

- No structured observability stack agents can query
- No way for an agent to inspect runtime behavior (latency, error rates, LLM costs)
- Log files are append-only text — not queryable by agents

**Upgrade**:

1. Add structured JSON log output that agents can grep/parse
2. Create `scripts/agent-metrics-summary.py` that summarizes key metrics from recent runs:
   - LLM call count, latency, token usage, cost per agent
   - Trade execution metrics (fills, rejects, slippage)
   - Error rates by component
3. Wire this into a skill in `.agents/skills/observability/SKILL.md` so both Claude Code and OpenCode know how to check system health

**Priority**: P1 — This is the biggest gap. Without it, agents can't self-diagnose issues.

---

## Gap 2: No Progressive Disclosure / Knowledge Architecture

**Blog says**: "AGENTS.md serves as the table of contents (~100 lines). Repository knowledge lives in a structured `docs/` directory treated as the system of record."

**Current state**: AGENTS.md is ~400 lines and tries to be both the map AND the manual. The `docs/` directory exists but contains auto-generated tutorial-style docs — not indexed, verification-tracked design docs.

**Upgrade**:

1. Slim AGENTS.md down to ~100-150 lines: golden rules, architecture diagram, and pointers to deeper docs
2. Move detailed procedures (TDD flow, commit conventions, debugging, GitHub operations) into `docs/dev/` as separate files
3. Create a `docs/architecture/` directory with:
   - `overview.md` — top-level domain map and package layering
   - `decisions/` — ADRs (Architecture Decision Records) for key choices
4. Add an index file (`docs/INDEX.md`) that agents can use for progressive disclosure

**Priority**: P1 — The current AGENTS.md is too dense. Agents lose signal in the noise.

---

## Gap 3: No Agent-to-Agent Review Loop

**Blog says**: "Over time, we've pushed almost all review effort towards being handled agent-to-agent."

**Current state**: The `code-reviewer` subagent exists for both Claude Code (`.claude/agents/code-reviewer.md`) and OpenCode (`.opencode/agent/code-reviewer.md`), but:

- It's ~90% auto-triggered via steering, not 100%
- No automated loop where the implementing agent reads the review, addresses issues, and re-requests review
- The reviewer runs as a subagent within the same session — it can see the worker's reasoning, which biases it toward approval

**Upgrade**:

1. **Blind validation**: After the implementing agent finishes, spawn a _separate_ agent session for review with no shared context. For Claude Code, use `context: fork` on the review skill. For OpenCode, invoke the reviewer as a `subtask: true` command.
2. **Review-response loop**: Wire into the grind loop (Gap 10) — if `CODE_REVIEW_*.md` has Critical/High items, re-prompt the worker to address them.
3. Add auto-approve criteria so trivial PRs (docs, deps, formatting) merge without human intervention.

**Implementation for each tool**:

- Claude Code: Create a `Stop` hook that checks for unresolved review findings and sends a follow-up prompt
- OpenCode: Build this into the `wti` grind loop wrapper (OpenCode has no hooks system)

**Priority**: P2 — The manual trigger works but doesn't scale. This is about increasing autonomy.

---

## Gap 4: No Mechanical Enforcement of Knowledge Freshness

**Blog says**: "Dedicated linters and CI jobs validate that the knowledge base is up to date, cross-linked, and structured correctly."

**Current state**: No validation that docs match code. Skills reference file paths and patterns that may drift. No staleness detection.

**Upgrade**:

1. Add a CI job or pre-commit hook that validates:
   - All file paths referenced in AGENTS.md and skill files actually exist
   - All module references in architecture docs are valid
   - Skill files reference correct class names and function signatures
2. Create a `scripts/validate-docs.py` that checks cross-references
3. Consider a periodic "doc-gardening" task (Claude Code `Stop` hook that checks if touched files have stale docs)

**Priority**: P2 — Prevents knowledge rot, which compounds over time.

---

## Gap 5: No Custom Linters with Agent-Readable Error Messages

**Blog says**: "Custom linters enforce structured logging, naming conventions, file size limits. Error messages inject remediation instructions into agent context."

**Current state**: ruff + bandit + ty handle standard linting. No custom lints for:

- Trading safety invariants (e.g., "every entry must have a stop loss")
- Architecture boundary enforcement (e.g., "strategies/ must not import from agents/")
- File size limits

**Upgrade**:

1. Add `scripts/lint-architecture.py` that enforces:
   - Import direction rules (strategies → base, not strategies → agents)
   - Every `EntryDecision(should_enter=True)` must include `stop_loss`
   - File size warnings (>500 lines)
2. Error messages should include remediation: "Import `agents.foo` from `strategies/bar.py` violates architecture. See `docs/architecture/overview.md`."
3. Wire into pre-commit and CI

**Priority**: P2 — Prevents architectural drift, especially important as agents generate more code.

---

## Gap 6: No Application Legibility for Agents

**Blog says**: "We made the app bootable per git worktree, so agents could launch and drive one instance per change."

**Current state**: The app is a CLI trading tool. `--analyze` mode exists but output goes to logs that aren't structured for agent consumption.

**Upgrade**:

1. Add a `--dry-run --json` CLI flag that runs one analysis cycle and outputs structured JSON to stdout
2. This lets agents invoke `uv run alpacalyzer --analyze --dry-run --json` and parse the result
3. Add this as a skill in `.agents/skills/validate-e2e/SKILL.md`

**Priority**: P3 — Nice to have. The current `--analyze` mode partially covers this.

---

## Gap 7: No "Golden Principles" or Recurring Cleanup

**Blog says**: "We encode 'golden principles' directly into the repository and built a recurring cleanup process."

**Current state**: The "Golden Rules" in AGENTS.md are process rules (issue first, tests first), not code quality principles. No automated cleanup.

**Upgrade**:

1. Define golden principles as code invariants in `docs/principles.md`:
   - "Every position has a stop loss"
   - "Validate at boundaries" (all external data parsed through Pydantic)
   - "Exits before entries in execution cycle"
2. Create a `scripts/audit-principles.py` that checks for violations
3. Consider a periodic GitHub Action that runs the audit and opens issues for deviations

**Priority**: P3 — Compounds over time but not urgent.

---

## Gap 8: Execution Plans as First-Class Artifacts

**Blog says**: "Complex work is captured in execution plans with progress and decision logs that are checked into the repository."

**Current state**: `_PLAN_issue-XX.md` files are git-ignored. `NEXT_ITERATION_OVERVIEW.md` is a single monolithic file.

**Upgrade**:

1. Create `docs/plans/` directory
2. Move iteration plans into individual plan files
3. Stop git-ignoring plan files — version them as the blog recommends
4. Add a `docs/plans/INDEX.md` that lists active, completed, and backlog plans

**Priority**: P3 — Organizational improvement. Current approach works but doesn't compound.

---

## Gap 9: No Reusable Agent Commands

**Blog says**: "Commands are ideal for workflows you run many times per day. Store them as Markdown files and check them into git."

**Current state**: Common multi-step workflows (start work on issue, create PR, run review) are described in prose in AGENTS.md but not encoded as invocable commands. Each agent session re-reads the full AGENTS.md to figure out the workflow.

**Upgrade**:
Create reusable commands in `.agents/commands/` (source of truth):

- `start-issue.md` — Fetch issue, verify branch, create plan file, scaffold test
- `create-pr.md` — Run tests + lint + typecheck, push, create PR, trigger review
- `fix-issue.md` — Fetch issue details, find relevant code, implement fix, open PR

**Implementation for each tool**:

- **OpenCode**: Commands go in `.opencode/commands/` (symlinked from `.agents/commands/`). Invoked via `/start-issue 42`. OpenCode commands support `$ARGUMENTS`, `!`command``for shell injection,`@file`for file inclusion, and`agent`/`subtask`/`model` routing.
- **Claude Code**: Commands go in `.claude/commands/` (symlinked from `.agents/commands/`). Claude treats commands identically to skills — same `/name` invocation. Skills win on name conflict. For richer behavior, create equivalent skills with `context: fork` and `disable-model-invocation: true`.

**Compatibility notes**:

- Both tools support `$ARGUMENTS` and `!`command`` syntax
- Argument indexing differs: Claude uses `$0`-indexed, OpenCode uses `$1`-indexed — avoid positional args or document both
- OpenCode has richer command routing (`agent`, `subtask`, `model` fields) that Claude doesn't support

**Priority**: P1 — High-frequency workflows should be one-shot invocable, not re-derived from prose every session.

---

## Gap 10: No Grind Loop / Iterate-Until-Done Pattern

**Blog says**: "One powerful pattern is using hooks to create agents that run for extended periods, iterating until they achieve a goal."

**Current state**: Agents run single-shot. When tests fail or the code reviewer finds issues, a human must manually re-prompt the agent to continue.

**Upgrade**:

**Claude Code** — Use the `Stop` hook system:

1. Create a `Stop` hook in `.claude/settings.json` that checks:
   - Did tests pass? If not, send followup: "Tests are still failing. Fix the failures and re-run."
   - Is there an unresolved `CODE_REVIEW_*.md` with Critical/High items? If so, send followup: "Address the review findings."
2. Add a scratchpad pattern (`.claude/scratchpad.md`) where the agent tracks progress and signals "DONE"
3. Cap iterations (e.g., max 5) to prevent infinite loops

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".agents/hooks/check-completion.sh"
          }
        ]
      }
    ]
  }
}
```

**OpenCode** — No hooks system, so build into the `wti` wrapper:

1. Wrap the `opencode --prompt` call in a loop
2. After each agent exit, check completion criteria (tests pass, review clean, PR exists)
3. If incomplete, re-invoke with a targeted follow-up prompt
4. Cap at 5 iterations

```bash
# In wti function, for opencode:
MAX_ITERATIONS=5
for i in $(seq 1 $MAX_ITERATIONS); do
  opencode --prompt "$prompt"
  if tests_pass && review_clean && pr_exists; then
    break
  fi
  prompt=$(build_followup_prompt)
done
```

**Shared**: The completion-check logic lives in `.agents/hooks/check-completion.sh` — used by both the Claude `Stop` hook and the `wti` OpenCode loop.

**Priority**: P2 — This is the mechanism that makes Gaps 3 and 7 actually work.

---

## Gap 11: No Plan-First Workflow Enforcement

**Blog says**: "The most impactful change you can make is planning before coding."

**Current state**: AGENTS.md mentions creating `_PLAN_issue-XX.md` files, but:

- Plans are git-ignored (lost after worktree removal)
- No enforcement that a plan exists before coding starts
- No structured plan format

**Upgrade**:

**Option A (steering-based, zero code)**: Add to AGENTS.md:

```
Before writing ANY code, create `docs/plans/issue-{NUMBER}.md` with:
- Goal (1 sentence)
- Acceptance criteria (from the issue)
- Files to modify
- Test scenarios
- Risks
Do NOT proceed to implementation until the plan is written.
```

This works ~90% of the time (same reliability as current code-reviewer trigger).

**Option B (enforced)**:

- Claude Code: Add a `PreToolUse` hook on `Write|Edit` that checks if a plan file exists. If not, return a deny with "Create a plan first."
- OpenCode: Check for plan file in the `wti` grind loop. If missing after first iteration, re-prompt.

**Priority**: P2 — Plans are the highest-leverage prompt improvement. The repo already creates them but doesn't enforce or preserve them.

---

## Gap 12: No Parallel Agent Strategy

**Blog says**: "Run the same prompt across multiple models simultaneously. Compare results side by side."

**Current state**: The worktree setup supports parallel agents on different issues via `wti`, but there's no pattern for running multiple agents on the same problem.

**Upgrade**:

1. Document a "parallel exploration" pattern in `docs/dev/parallel-exploration.md`:
   - For hard problems, create 2-3 worktrees with the same issue
   - `wti 66 -c` in one terminal, `wti 66 -o` in another
   - Compare results and pick the best
2. The existing `wt.toml` infrastructure already supports this; it just needs documentation

**Priority**: P3 — The infrastructure exists. This is about documenting the pattern.

---

## Gap 13: Rules Should Be Minimal and Reactive

**Blog says**: "Start simple. Add rules only when you notice the agent making the same mistake repeatedly. Reference files instead of copying their contents."

**Current state**: Some skills copy full code templates inline rather than referencing existing files. Skills are ~300-500 lines each, which crowds out task-specific context.

**Upgrade**:

1. Audit skill files — replace inline code templates with references to actual files:
   - Instead of a 200-line test template in `new-strategy/SKILL.md`, say "Follow the pattern in `tests/strategies/test_momentum.py`"
   - Instead of a full agent template, say "Copy `src/alpacalyzer/agents/warren_buffet_agent.py` and modify"
2. Add a `docs/dev/common-mistakes.md` that captures recurring agent errors and their fixes
3. Only add new rules when an agent makes the same mistake twice

**Priority**: P2 — Reduces context bloat.

---

## Gap 14: No Debug Mode / Hypothesis-Driven Debugging

**Blog says**: "Debug Mode generates multiple hypotheses, instruments code with logging, analyzes actual behavior, and makes targeted fixes based on evidence."

**Current state**: AGENTS.md has a debugging section but it's purely mechanical ("run once, save output, grep for FAILED").

**Upgrade**:

1. Add a `docs/dev/debugging-guide.md` with a hypothesis-driven debugging workflow:
   - Step 1: Read the error, form 2-3 hypotheses
   - Step 2: For each hypothesis, identify what evidence would confirm/deny it
   - Step 3: Add targeted logging or assertions to gather evidence
   - Step 4: Run once, analyze evidence, narrow hypotheses
   - Step 5: Fix the confirmed root cause, remove instrumentation
2. This is especially important for trading logic bugs where the wrong fix can cause financial loss

**Priority**: P3 — The current mechanical approach works for simple failures. This matters more for subtle trading logic bugs.

---

## Gap 15: Duplicated Agent Config Across Tools

**Problem**: The repo currently duplicates agent/skill definitions across tool-specific directories:

```
.claude/
├── agents/code-reviewer.md        # Claude Code subagent
├── skills/                        # 7 skill dirs (Claude Code format)
└── settings.local.json

.opencode/
├── agent/code-reviewer.md         # OpenCode subagent (different frontmatter!)
└── package.json
```

The `code-reviewer.md` files are nearly identical in content but differ in frontmatter format. Skills only exist in `.claude/skills/` — OpenCode reads them via Claude-compatibility fallback but this is fragile.

### How Each Tool Discovers Files

**Claude Code**:

| Concept   | Directory                        | Invocation                                              |
| --------- | -------------------------------- | ------------------------------------------------------- |
| Rules     | `CLAUDE.md` (root)               | Always in context                                       |
| Skills    | `.claude/skills/<name>/SKILL.md` | Auto by model or `/skill-name`                          |
| Subagents | `.claude/agents/<name>.md`       | Auto delegation or `@agent-name`                        |
| Commands  | `.claude/commands/<name>.md`     | `/command-name` (skills win on name conflict)           |
| Hooks     | `.claude/settings.json`          | Lifecycle events (PreToolUse, Stop, SubagentStop, etc.) |

**OpenCode**:

| Concept   | Directory                                               | Invocation                          |
| --------- | ------------------------------------------------------- | ----------------------------------- |
| Rules     | `AGENTS.md` (root)                                      | Always in context                   |
| Skills    | `.opencode/skills/<name>/SKILL.md`                      | On-demand via `skill` tool          |
| Agents    | `.opencode/agents/<name>.md`                            | Tab (primary) or `@name` (subagent) |
| Commands  | `.opencode/commands/<name>.md`                          | `/command-name`                     |
| Fallbacks | `.claude/skills/`, `.agents/skills/`, `.agents/agents/` | Same discovery                      |

**Key compatibility facts**:

- Skills: ✅ Same `SKILL.md` format. OpenCode reads `.claude/skills/` and `.agents/skills/` as fallbacks.
- Agents: ⚠️ Same concept, incompatible frontmatter. Claude uses `permissionMode`, `tools` as list. OpenCode uses `mode`, `tools` as object, `permission` as object.
- Commands: ⚠️ Similar concept. Claude treats commands as lightweight skills. OpenCode has richer routing (`agent`, `subtask`, `model`).
- Hooks: ❌ Claude-only. No OpenCode equivalent.
- Dynamic context: ✅ Both support `!`command`` syntax in skills/commands.
- Arguments: ⚠️ Claude uses `$0`-indexed, OpenCode uses `$1`-indexed.

### Upgrade: Unified `.agents/` Directory

```
.agents/                              # Source of truth (checked into git)
├── skills/                           # Shared skills (SKILL.md format — fully compatible)
│   ├── execution/SKILL.md
│   ├── gpt-integration/SKILL.md
│   ├── new-agent/SKILL.md
│   ├── new-scanner/SKILL.md
│   ├── new-strategy/SKILL.md
│   ├── pydantic-model/SKILL.md
│   ├── technical-indicator/SKILL.md
│   ├── observability/SKILL.md        # NEW (Gap 1)
│   └── validate-e2e/SKILL.md         # NEW (Gap 6)
├── agents/                           # Subagent definitions (per-tool frontmatter)
│   └── code-reviewer/
│       ├── prompt.md                 # Shared review instructions
│       ├── claude.md                 # Claude Code frontmatter wrapper
│       └── opencode.md              # OpenCode frontmatter wrapper
├── commands/                         # Reusable commands (Gap 9)
│   ├── start-issue.md
│   ├── create-pr.md
│   └── fix-issue.md
└── hooks/                            # Shared hook scripts (Claude hooks + wti loop)
    └── check-completion.sh           # Used by Claude Stop hook AND wti grind loop

.claude/                              # Claude Code config (symlinks to .agents/)
├── settings.local.json               # Permissions + hooks config
├── agents/code-reviewer.md           # Symlink → .agents/agents/code-reviewer/claude.md
└── skills/                           # Symlinks → .agents/skills/*

.opencode/                            # OpenCode config (symlinks to .agents/)
├── agents/code-reviewer.md           # Symlink → .agents/agents/code-reviewer/opencode.md
├── commands/                         # Symlinks → .agents/commands/*
└── package.json
```

**Alternative for OpenCode**: Instead of symlinks, set `OPENCODE_CONFIG_DIR=.agents` in the `wti` function. OpenCode natively reads `.agents/` for skills and agents. Only Claude Code needs symlinks.

**Symlink setup script** (`scripts/setup-agent-links.sh`):

```bash
#!/bin/bash
set -e

# Skills: .claude/skills/* → .agents/skills/*
mkdir -p .claude/skills
for skill_dir in .agents/skills/*/; do
  skill_name=$(basename "$skill_dir")
  ln -sfn "../../.agents/skills/$skill_name" ".claude/skills/$skill_name"
done

# Agents
mkdir -p .claude/agents .opencode/agents
ln -sf "../../.agents/agents/code-reviewer/claude.md" ".claude/agents/code-reviewer.md"
ln -sf "../../.agents/agents/code-reviewer/opencode.md" ".opencode/agents/code-reviewer.md"

# Commands: .opencode/commands/* → .agents/commands/*
mkdir -p .opencode/commands
for cmd_file in .agents/commands/*.md; do
  [ -f "$cmd_file" ] || continue
  ln -sfn "../../.agents/commands/$(basename "$cmd_file")" ".opencode/commands/$(basename "$cmd_file")"
done

echo "Agent links created."
```

Wire into worktrunk:

```toml
[post-create]
copy-env = "cp {{ main_worktree_path }}/.env {{ worktree_path }}/.env 2>/dev/null || true"
uv-sync = "uv sync"
agent-links = "bash scripts/setup-agent-links.sh"
```

**Priority**: P1 — Foundation for all other improvements. Skills, commands, and agents need a single source of truth before building on top.

---

## Implementation Roadmap

### Wave 1 (High Impact, Foundation)

| #   | Issue                                                                     | Task                                                                                   | Priority | Effort | Source |
| --- | ------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------- | ------ | ------ |
| 1   | [#137](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/137) | Create `.agents/` directory structure + symlink setup script + `wt.toml` hook          | P1       | M      | Gap 15 |
| 2   | [#138](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/138) | Migrate skills from `.claude/skills/` → `.agents/skills/`                              | P1       | S      | Gap 15 |
| 3   | [#139](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/139) | Migrate `code-reviewer` to `.agents/agents/` with shared prompt + per-tool frontmatter | P1       | S      | Gap 15 |
| 4   | [#140](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/140) | Restructure AGENTS.md → slim entry point + `docs/dev/` for procedures                  | P1       | M      | Gap 2  |
| 5   | [#141](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/141) | Create `docs/architecture/overview.md` with domain map and layer rules                 | P1       | S      | Gap 2  |
| 6   | [#142](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/142) | Build `scripts/agent-metrics-summary.py` + observability skill                         | P1       | M      | Gap 1  |
| 7   | [#143](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/143) | Create reusable commands (`start-issue`, `create-pr`, `fix-issue`)                     | P1       | M      | Gap 9  |

### Wave 2 (Enforcement & Autonomy)

| #   | Issue                                                                     | Task                                                                         | Priority | Effort | Source |
| --- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------- | -------- | ------ | ------ |
| 8   | [#144](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/144) | Build grind loop: Claude `Stop` hook + `wti` wrapper + `check-completion.sh` | P2       | M      | Gap 10 |
| 9   | [#145](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/145) | Wire blind validation into grind loop (separate agent session for review)    | P2       | S      | Gap 3  |
| 10  | [#146](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/146) | Enforce plan-first workflow (PreToolUse hook + plan template)                | P2       | S      | Gap 11 |
| 11  | [#147](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/147) | Add architecture boundary linter (`scripts/lint-architecture.py`)            | P2       | M      | Gap 5  |
| 12  | [#148](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/148) | Add CI job to validate doc cross-references                                  | P2       | S      | Gap 4  |
| 13  | [#149](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/149) | Slim down skill files — replace inline templates with file references        | P2       | M      | Gap 13 |

### Wave 3 (Compounding Improvements)

| #   | Issue                                                                     | Task                                                                | Priority | Effort | Source |
| --- | ------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------- | ------ | ------ |
| 14  | [#150](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/150) | Add structured JSON output to `--analyze` mode + validate-e2e skill | P3       | M      | Gap 6  |
| 15  | [#151](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/151) | Define golden principles in `docs/principles.md` + audit script     | P3       | M      | Gap 7  |
| 16  | [#152](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/152) | Restructure plans into `docs/plans/` as versioned artifacts         | P3       | S      | Gap 8  |
| 17  | [#153](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/153) | Add doc-gardening periodic task                                     | P3       | M      | Gap 4  |
| 18  | [#154](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/154) | Document parallel exploration pattern                               | P3       | S      | Gap 12 |
| 19  | [#155](https://github.com/kimrejstrom/alpacalyzer-algo-trader/issues/155) | Add hypothesis-driven debugging guide                               | P3       | S      | Gap 14 |

---

## Key Takeaway

Both blogs converge on the same insight: the engineering discipline shifts from writing code to building scaffolding that makes agents effective. This repo has strong scaffolding for the "write code" phase (skills, TDD flow, pre-commit) but is weaker on the feedback loops that close the autonomy gap: observability, self-diagnosis, automated review cycles, and knowledge architecture that scales.

The highest-leverage investments are the `.agents/` unification (Gap 15) and knowledge architecture (Gap 2) because everything else builds on top of them. Once skills, commands, and agents live in a single source of truth that both Claude Code and OpenCode discover correctly, the grind loop, blind validation, and reusable commands become straightforward additions.

The grind loop (Gap 10) is the key autonomy unlock — it's what turns the current "agent does one pass, human re-prompts" flow into "agent iterates until done." Claude Code's `Stop` hook handles this natively. For OpenCode, the `wti` shell wrapper provides the same capability. The shared `check-completion.sh` script ensures both tools use identical completion criteria.
