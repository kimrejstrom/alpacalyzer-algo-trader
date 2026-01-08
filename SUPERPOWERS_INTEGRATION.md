# Superpowers Plugin Integration

## Overview

This project uses the Superpowers Plugin which provides generic skills for common development patterns. However, **AGENTS.md always takes precedence** over superpowers skills when conflicts arise.

## Precedence Rules

1. **AGENTS.md is source of truth** - Project-specific workflows trump generic skills
2. **Project skills first** - Custom skills in `.claude/skills/` align with AGENTS.md
3. **Selective superpowers use** - Only use superpowers that complement, don't conflict

## When to Use Each

### Use Project Workflow (AGENTS.md):

- ✅ Trading strategy development (use custom skills: new-strategy, pydantic-model, technical-indicator)
- ✅ Hedge fund agent development (use custom skill: new-agent)
- ✅ Data scanner development (use custom skill: new-scanner)
- ✅ GPT integration (use custom skill: gpt-integration)
- ✅ Git operations and worktree management
- ✅ PR creation and commits
- ✅ Testing with project structure

### Use Superpowers (Complementary):

- ✅ `superpowers:systematic-debugging` - For complex bugs
- ✅ `superpowers:verification-before-completion` - Before PRs/merges
- ✅ `superpowers:receiving-code-review` - When getting feedback
- ✅ `superpowers:brainstorming` - For early-stage idea exploration (before issue creation)

### Avoid These Superpowers (Conflict with AGENTS.md):

- ❌ `superpowers:using-git-worktrees` - Human orchestrator manages worktrees, AGENTS.md instructions apply
- ❌ `superpowers:test-driven-development` - Follow AGENTS.md TDD flow instead
- ❌ `superpowers:finishing-a-development-branch` - Use AGENTS.md completion flow instead

## Decision Flow

```
Starting work on a task?
├── Is there a GitHub issue? → No → Create one first (AGENTS.md)
├── Is it a trading strategy? → Yes → Use custom skill: new-strategy
├── Is it a hedge fund agent? → Yes → Use custom skill: new-agent
├── Is it a data scanner? → Yes → Use custom skill: new-scanner
├── Is it a technical indicator? → Yes → Use custom skill: technical-indicator
├── Is it a Pydantic model? → Yes → Use custom skill: pydantic-model
├── Is it GPT integration? → Yes → Use custom skill: gpt-integration
├── Is it a bug? → Yes → Use superpowers:systematic-debugging
├── Need to brainstorm ideas? → Yes → Use superpowers:brainstorming (before issue)
└── Ready to complete? → Use superpowers:verification-before-completion
```

## Key Conflicts and Resolutions

| Superpowers Rule                       | AGENTS.md Rule             | Resolution                 |
| -------------------------------------- | -------------------------- | -------------------------- |
| Must invoke skill at 1% chance         | Project conventions first  | AGENTS.md takes precedence |
| Delete code written before tests       | Write failing test first   | Follow AGENTS.md TDD flow  |
| Save plans to docs/plans/              | Use local git-ignored plan | Use AGENTS.md approach     |
| Mandatory verification in same message | Run tests efficiently      | Use AGENTS.md debugging    |

## Examples

### Correct: Adding a new trading strategy

1. Ensure GitHub issue exists
2. Follow AGENTS.md pre-flight checks
3. Use custom skill: new-strategy (writes test first, implements strategy)
4. Follow AGENTS.md TDD flow
5. Use superpowers:verification-before-completion before PR

### Correct: Adding a new hedge fund agent

1. Ensure GitHub issue exists
2. Follow AGENTS.md pre-flight checks
3. Use custom skill: new-agent (creates agent, tests, prompts)
4. Test agent in isolation, then integration
5. Use superpowers:verification-before-completion before PR

### Correct: Adding a technical indicator

1. Ensure GitHub issue exists
2. Follow AGENTS.md pre-flight checks
3. Use custom skill: technical-indicator (adds to technical_analysis.py)
4. Test indicator calculation with known values
5. Use superpowers:verification-before-completion before PR

### Correct: Debugging a test failure

1. Use superpowers:systematic-debugging
2. Follow its systematic approach
3. Still run single test files per AGENTS.md debugging guidelines
4. Commit with AGENTS.md format

### Incorrect: Git worktree management

1. ❌ Using superpowers:using-git-worktrees to create worktree
2. ✅ Per AGENTS.md let user manage worktrees via wt CLI

## Remember

- Superpowers provides generic skills
- AGENTS.md provides project-specific workflows
- When in doubt, follow AGENTS.md
- The goal is to ship features following the project's established patterns
- Alpacalyzer is a real trading system - precision and safety matter above all else
