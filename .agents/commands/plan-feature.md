# Plan Feature Command

Decompose a high-level feature into well-formed, agent-sized GitHub issues with dependency ordering and Agent Metadata — ready for the orchestrator.

## Usage

```
/plan-feature <feature_description>
```

**Arguments:**

- `feature_description`: A natural-language description of the feature to plan. Can be a sentence, a paragraph, or a reference to an existing issue/doc.

## Argument Indexing

- **Claude Code**: Use `$1` for the first argument (feature description, may be multi-word)
- **OpenCode**: Use `$ARGUMENTS` to get all arguments

## Steps

### 1. Get Repo Info

```bash
git remote get-url origin
```

Parse owner and repo name.

### 2. Understand the Codebase Context

Read the key context files to understand what exists:

- `AGENTS.md` — architecture overview, component locations
- `docs/architecture/overview.md` — module structure, layering rules
- `docs/principles.md` — code invariants (if exists)

Scan the source directory to understand the current module structure.

### 3. Analyze the Feature

Break the feature description into concrete work items. For each, determine:

- **What changes**: Which files/modules are affected
- **Scope**: Is this a new module, modification to existing, or cross-cutting?
- **Complexity**: small (< 1 hour agent work), medium (1-3 hours), large (needs further decomposition)
- **Dependencies**: Does this require another piece to land first?
- **Parallel safety**: Can an agent work on this while other agents work on sibling issues?

### 4. Decomposition Rules

Follow these rules when breaking down work:

1. **One issue = one agent session = one worktree**. If a task requires touching more than 3-4 files across different modules, it's probably too big.
2. **Large → split further**. Any issue estimated as "large" must be decomposed into small/medium sub-issues. Agents work best with focused, bounded tasks.
3. **Test-first is non-negotiable**. Every issue must be testable. If you can't describe a test scenario, the issue is too vague.
4. **Data models before consumers**. If the feature needs new data models, that's issue #1. Code that uses those models depends on it.
5. **Infrastructure before features**. Config, schemas, migrations, shared utilities come before the features that use them.
6. **Vertical slices over horizontal layers**. Prefer "implement feature X end-to-end" over "add all database models, then add all API routes, then add all tests." But respect dependency ordering — if 3 features share a model, the model is its own issue.
7. **Explicit acceptance criteria**. Every issue needs concrete, checkable criteria. "Implement the thing" is not an acceptance criterion. "Function X returns Y when given Z" is.
8. **No orphan issues**. Every issue should be reachable from the dependency graph. If an issue has no dependents and no dependencies, question whether it belongs in this feature.

### 5. Build the Dependency Graph

Arrange issues into a dependency DAG:

- Identify which issues block which others
- Group independent issues that can run in parallel (same wave)
- Verify there are no cycles
- Verify the graph is connected (no orphans)

Present the graph as waves:

```
Wave 1 (parallel): #A Data models, #B Config schema
Wave 2 (parallel): #C Service layer (depends on #A), #D CLI commands (depends on #B)
Wave 3: #E Integration tests (depends on #C, #D)
```

### 6. Present the Plan to the Developer

Show the complete plan in this format:

```markdown
## Feature: <feature_description>

### Issue Breakdown

#### Wave 1 (parallel)

**Issue 1: <title>**

- Description: <what and why>
- Acceptance Criteria:
  - [ ] Criterion 1
  - [ ] Criterion 2
- Files: <key files to modify/create>
- Complexity: small
- Depends on: #none
- Parallel safe: yes

**Issue 2: <title>**

- ...

#### Wave 2

**Issue 3: <title>**

- ...
- Depends on: Issue 1
- ...

### Dependency Graph

Wave 1: Issue 1, Issue 2 (parallel)
Wave 2: Issue 3 (depends on 1), Issue 4 (depends on 2)
Wave 3: Issue 5 (depends on 3, 4)

### Orchestrator Command

After issues are created:
scripts/orchestrate.sh --issues <comma-separated-numbers>
```

### 7. Wait for Developer Approval

**STOP HERE.** Ask the developer:

> "Here's the proposed breakdown into N issues across M waves. Want me to:
>
> 1. Create all issues as-is
> 2. Modify the plan (tell me what to change)
> 3. Cancel"

**Do NOT create issues without explicit approval.** The developer may want to:

- Adjust complexity estimates
- Change dependency ordering
- Merge or split issues
- Add/remove acceptance criteria
- Change which issues are auto-merge eligible

### 8. Create Issues

Once approved, create each issue via `gh`:

```bash
gh issue create --repo <owner>/<repo> \
  --title "<title>" \
  --label "orchestrator-ready" \
  --body "## Description

<description>

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Agent Metadata

| Field                | Value              |
| -------------------- | ------------------ |
| Depends on           | #<dep1>, #<dep2>   |
| Parallel safe        | yes                |
| Auto-merge           | no                 |
| Agent tool           | opencode           |
| Estimated complexity | small              |
"
```

**Important**: Create issues in dependency order (Wave 1 first) so that `Depends on` fields can reference real issue numbers.

After creating each issue, capture the issue number from the output and use it in subsequent `Depends on` fields.

### 9. Report Summary

After all issues are created, report:

```
Created N issues for feature: <feature_description>

Issues:
  #101 - Data models (Wave 1, small)
  #102 - Config schema (Wave 1, small)
  #103 - Service layer (Wave 2, depends on #101)
  #104 - CLI commands (Wave 2, depends on #102)
  #105 - Integration tests (Wave 3, depends on #103, #104)

To run the orchestrator:
  scripts/orchestrate.sh --issues 101,102,103,104,105

Or add the 'orchestrator-ready' label and run:
  scripts/orchestrate.sh --label orchestrator-ready
```

## Notes

- This command is for PLANNING, not implementation. It creates issues; agents implement them later.
- Always wait for developer approval before creating issues.
- The orchestrator handles wave ordering automatically via dependency resolution — you just need to get the `Depends on` fields right.
- Default to `Auto-merge: no` unless the developer explicitly says otherwise. Auto-merge is for low-risk, well-tested changes only.
- Default to `Agent tool: opencode` unless the developer specifies otherwise.
- If the feature is too large to decompose in one pass (> 15 issues), suggest breaking it into sub-features first.
