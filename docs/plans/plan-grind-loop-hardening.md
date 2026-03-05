# Plan: Grind Loop Hardening & Agent Harness Improvements

## Goal

Harden the grind loop against stalled/idle agents, add structured state tracking, improve re-prompt quality, and add session observability — making the iterate-until-done pattern more reliable and debuggable.

## Context

The current grind loop (`check-completion.sh` + Claude Stop hook + OpenCode `grind-loop.ts`) works well for the happy path but has blind spots:

1. **Agent silently stops**: LLM provider load, failed tool calls, or rate limits cause the agent to stop producing output without signaling completion. The Claude `Stop` hook fires (good), but the OpenCode `session.idle` event may not fire reliably in all cases. The bash wrapper (`opencode-grind-loop.sh`) handles this better since `opencode --prompt` exits when the agent stops.
2. **No timeout protection**: An agent stuck in a long LLM call or infinite reasoning loop runs until the human notices. No time-based circuit breaker exists.
3. **Re-prompts are reactive, not strategic**: `check-completion.sh` outputs free-text follow-ups ("Tests are still failing. Fix these...") without context about iteration history or what was already tried.
4. **Scratchpad is unused**: `.agents/scratchpad.md` just says `STATUS: DONE` — no structured state for cross-iteration memory.
5. **No session logging**: No post-hoc record of what happened across grind loop iterations.
6. **No shared config**: Settings like max iterations, stall timeout, and completion criteria are hardcoded in multiple places.

## Acceptance Criteria

- [x] Stall/timeout protection: agent sessions that produce no progress within a configurable timeout are detected and re-prompted
- [x] Idle agent detection: agents that stop working (not stalled, just stopped) are re-prompted to continue
- [x] Structured scratchpad schema for cross-iteration state tracking
- [x] `check-completion.sh` outputs structured JSON (backward-compatible: JSON on stdout, human-readable on stderr)
- [x] Session log (`.agents/session-log.jsonl`) records each grind loop iteration with timestamp, checks, and outcome
- [x] Shared config file (`.agents/config.yaml`) centralizes grind loop settings
- [x] All three grind loop implementations updated: Claude Stop hook (via `check-completion.sh`), OpenCode plugin (`grind-loop.ts`), bash wrapper (`opencode-grind-loop.sh`)
- [x] Existing tests and CI unaffected

## Design

### Shared Config: `.agents/config.yaml`

Single source of truth for grind loop settings, read by all three implementations:

```yaml
grind_loop:
  max_iterations: 5
  stall_timeout_seconds: 300 # 5 min — no output from agent
  idle_timeout_seconds: 120 # 2 min — agent stopped but work incomplete
  session_log: .agents/session-log.jsonl

scratchpad:
  path: .agents/scratchpad.md
```

- `check-completion.sh` reads this via `yq` or simple grep (keep it shell-friendly)
- `grind-loop.ts` reads this via `fs.readFileSync` + yaml parse
- `opencode-grind-loop.sh` reads this via grep/awk

### Structured Scratchpad Schema

```markdown
## STATUS: IN_PROGRESS

## ITERATION: 2/5

## STARTED_AT: 2026-03-05T14:30:00Z

## COMPLETED

- [x] Plan file created
- [x] Tests written
- [ ] Implementation done
- [ ] Code review passed

## CURRENT_FOCUS

Implementing the FooBar component per test_foo.py

## PREVIOUS_ATTEMPTS

- Iteration 1: Wrote tests, started implementation. Stopped due to LLM timeout.

## BLOCKERS

None
```

The agent updates this during work. The grind loop reads it to:

- Detect if the agent made progress between iterations (compare ITERATION field)
- Build targeted re-prompts based on CURRENT_FOCUS and COMPLETED
- Detect stuck loops (same CURRENT_FOCUS across 2+ iterations)

### Structured `check-completion.sh` Output

Currently outputs free text on stdout. Change to JSON:

```json
{
  "complete": false,
  "iteration": 2,
  "max_iterations": 5,
  "checks": {
    "tests_pass": false,
    "review_clean": true,
    "review_exists": false,
    "scratchpad_done": false
  },
  "failed_checks": ["tests_pass"],
  "followup_prompt": "Tests are still failing. Fix these failures:\n\nFAILED tests/test_foo.py::test_bar\n\nFocus on the assertion error in test_bar — the return type changed.",
  "context": {
    "failed_tests": ["tests/test_foo.py::test_bar"],
    "scratchpad_status": "IN_PROGRESS",
    "scratchpad_focus": "Implementing the FooBar component"
  }
}
```

Backward compatibility: JSON goes to stdout, human-readable diagnostics to stderr (already the pattern for "GRIND_LOOP: Checking tests..." messages).

### Session Log: `.agents/session-log.jsonl`

Appended by `check-completion.sh` after each check:

```json
{
  "timestamp": "2026-03-05T14:35:00Z",
  "iteration": 2,
  "checks": { "tests_pass": false, "review_clean": true },
  "failed": ["tests_pass"],
  "scratchpad_status": "IN_PROGRESS",
  "duration_since_last_s": 180
}
```

This gives post-hoc observability: how many iterations did it take, what kept failing, how long between iterations.

### Idle/Stall Detection

**The core problem**: The agent stops producing output. Two variants:

1. **Stalled**: Agent is alive but stuck (infinite LLM call, reasoning loop). Needs a timeout kill.
2. **Idle**: Agent finished its turn but didn't complete the work. The Stop/session.idle hook fires, but the agent just... stopped. Needs a re-prompt.

**Claude Code**: The `Stop` hook already fires when the agent stops. The idle case is handled — `check-completion.sh` runs and re-prompts. For stalls, Claude Code doesn't expose a timeout mechanism in hooks. The mitigation is to document that the human should set a session timeout in their Claude Code config, or we add a watchdog.

**OpenCode plugin**: `session.idle` fires when the agent stops. Same as Claude — idle is handled. For stalls, we can add a timer in the plugin that fires if no `session.idle` event arrives within `stall_timeout_seconds`. On timeout, send a "You appear to be stuck. Check your current approach and try a different angle." prompt.

**Bash wrapper**: `opencode --prompt` blocks until the agent exits, so idle is handled (the loop continues). For stalls, wrap the `opencode` call in `timeout` command: `timeout ${STALL_TIMEOUT}s opencode --prompt "$prompt"`.

**Key insight for idle detection**: The real problem isn't that the hook doesn't fire — it's that the agent sometimes stops after a failed tool call or rate limit without realizing it should continue. The fix is in the re-prompt quality: instead of just "tests are failing," include "You stopped working. The scratchpad shows you were working on X. Continue from where you left off."

## Files to Modify

| File                                   | Change                                                                                |
| -------------------------------------- | ------------------------------------------------------------------------------------- |
| `.agents/config.yaml`                  | NEW — shared grind loop config                                                        |
| `.agents/hooks/check-completion.sh`    | Structured JSON output, read config, session logging, scratchpad-aware re-prompts     |
| `.agents/hooks/opencode-grind-loop.sh` | Read config, stall timeout via `timeout` command, structured output parsing           |
| `.opencode/plugins/grind-loop.ts`      | Read config, stall timer, parse structured JSON from check-completion, idle detection |
| `.agents/scratchpad.md`                | Update to structured schema (template)                                                |
| `docs/dev/tdd-flow.md`                 | Update grind loop section with new config and scratchpad schema                       |
| `.agents/session-log.jsonl`            | NEW — created by check-completion.sh (gitignored)                                     |
| `.gitignore`                           | Add `.agents/session-log.jsonl`                                                       |

## Test Scenarios

| Scenario                                         | Expected                                                                             |
| ------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `check-completion.sh` with all checks passing    | Exit 0, JSON `{"complete": true, ...}` on stdout                                     |
| `check-completion.sh` with failing tests         | Exit 1, JSON with `followup_prompt` containing test failures                         |
| `check-completion.sh` with no scratchpad         | Works (scratchpad is optional, not required)                                         |
| `check-completion.sh` reads config.yaml          | Uses `max_iterations` and `stall_timeout_seconds` from config                        |
| `check-completion.sh` missing config.yaml        | Falls back to hardcoded defaults (backward compatible)                               |
| Bash grind loop with stall timeout               | `timeout` kills hung `opencode` process, loop continues with re-prompt               |
| Bash grind loop reads config                     | Picks up `max_iterations` from `.agents/config.yaml`                                 |
| OpenCode plugin stall timer                      | Fires after `stall_timeout_seconds` of no `session.idle`, sends re-prompt            |
| OpenCode plugin parses JSON output               | Extracts `followup_prompt` from structured check-completion output                   |
| Session log appended each iteration              | `.agents/session-log.jsonl` grows by one line per check-completion run               |
| Agent stopped but not done (idle)                | Re-prompt includes scratchpad context: "You stopped. Continue from: {CURRENT_FOCUS}" |
| Agent stalled (no output for 5 min)              | Timeout fires, agent re-prompted with "You appear stuck" message                     |
| Scratchpad shows no progress across 2 iterations | Re-prompt escalates: "Same focus for 2 iterations. Try a different approach."        |

## Risks

- `yq` dependency for YAML parsing in shell: mitigate by using simple `grep`/`awk` patterns on the flat YAML structure, or fall back to defaults if parsing fails
- OpenCode plugin stall timer may fire during legitimate long operations (large test suite): mitigate with a generous default (300s) and make it configurable
- Structured JSON output from `check-completion.sh` could break consumers that expect plain text: mitigate by keeping the JSON format simple and testing both Claude and OpenCode integrations
- Session log could grow unbounded: mitigate by rotating or truncating in check-completion.sh (keep last 100 lines)

## Implementation Order

1. `.agents/config.yaml` — foundation, everything reads from it
2. Structured scratchpad schema in `.agents/scratchpad.md`
3. `check-completion.sh` — structured JSON output + config reading + session logging + scratchpad-aware prompts
4. `opencode-grind-loop.sh` — stall timeout + config reading + structured output parsing
5. `.opencode/plugins/grind-loop.ts` — stall timer + config reading + structured output parsing
6. `docs/dev/tdd-flow.md` — update documentation
7. `.gitignore` — add session log
