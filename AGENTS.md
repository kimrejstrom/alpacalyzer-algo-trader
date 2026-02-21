# AI Agent Instructions for Alpacalyzer Algo Trader

> **Critical**: You are a principal software engineer working on Alpacalyzer Algo Trader. Your job: build features incrementally using test-first development.

📋 **Related Documentation**:

- [Code Review Subagent](.opencode/agent/code-reviewer.md) - Automated PR review agent
- [Migration Plan](migration_roadmap.md) - Architecture refactoring roadmap
- [Superpowers Plugin Integration](SUPERPOWERS_INTEGRATION.md) - How to use superpowers skills with this project
- [Docs Index](docs/INDEX.md) - Progressive disclosure entry point

> **Important**: This document (AGENTS.md) always takes precedence over generic superpowers plugin skills. See [SUPERPOWERS_INTEGRATION.md](SUPERPOWERS_INTEGRATION.md) for details.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Setup environment
cp .env.example .env
# Edit .env with required API keys:
# - ALPACA_API_KEY (Alpaca API)
# - ALPACA_SECRET_KEY (Alpaca secret)
# - LLM_API_KEY (OpenAI-compatible LLM provider, e.g., OpenRouter)
# - USE_NEW_LLM=true (use new LLM abstraction layer)

# 3. Start development
uv run alpacalyzer --analyze  # Analysis mode (no real trades)
uv run alpacalyzer            # Full trading mode
```

## 🎯 Golden Rules

1. **GitHub Issue First** - No work without an issue. Create one if missing.
2. **Tests Before Code** - Write tests first, then implement.
3. **One Issue Per Session** - Each worktree session handles exactly ONE issue. Never start a new issue in the same session.
4. **One Thing At A Time** - Single feature per PR, focused commits.
5. **No Secrets** - Use environment variables, never hardcode credentials.
6. **Debug Efficiently** - Run tests once, save output, analyze. Never run full test suite repeatedly.

See [docs/dev/tdd-flow.md](docs/dev/tdd-flow.md) for detailed workflow. For code invariants, see [docs/principles.md](docs/principles.md).

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPPORTUNITY PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│  ScannerRegistry → OpportunityAggregator                         │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRADING ORCHESTRATOR                           │
├─────────────────────────────────────────────────────────────────┤
│  TradingOrchestrator: scan() → analyze() → execute()           │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION ENGINE                             │
├─────────────────────────────────────────────────────────────────┤
│  ExecutionEngine: SignalQueue, PositionTracker, OrderManager   │
│  Strategies: Momentum, Breakout, MeanReversion                 │
└─────────────────────────────────────────────────────────────────┘
```

| Component    | Location                          |
| ------------ | --------------------------------- |
| CLI          | `src/alpacalyzer/cli.py`          |
| Orchestrator | `src/alpacalyzer/orchestrator.py` |
| Execution    | `src/alpacalyzer/execution/`      |
| Strategies   | `src/alpacalyzer/strategies/`     |
| Pipeline     | `src/alpacalyzer/pipeline/`       |
| Events       | `src/alpacalyzer/events/`         |
| Hedge Fund   | `src/alpacalyzer/hedge_fund.py`   |
| Agents       | `src/alpacalyzer/agents/`         |
| Scanners     | `src/alpacalyzer/scanners/`       |

See [docs/architecture/overview.md](docs/architecture/overview.md) for full architecture details.

## Pre-Flight Checks

**Before starting ANY work, verify your environment:**

```bash
# 1. Confirm current directory
pwd

# 2. Get repo owner/name from git remote (CRITICAL for GitHub API calls)
git remote get-url origin

# 3. Check git status
git status

# 4. Verify you're on the correct branch
git branch --show-current
```

## 🔄 Development Flow

**Plan First**: Before writing ANY code, create `docs/plans/issue-{NUMBER}.md` using the template at `docs/templates/plan-template.md`. The PreToolUse hook enforces this — code writes are blocked until a plan exists.

See [docs/dev/tdd-flow.md](docs/dev/tdd-flow.md) for:

- Starting work on an issue
- TDD workflow
- Completing a feature
- Closing a pull request

## Testing

See [docs/dev/testing.md](docs/dev/testing.md) for:

- Test structure
- Testing patterns
- Debugging test failures

## 📝 Conventions

- Python files: `snake_case.py`
- Test files: `test_{module_name}.py`
- Classes: `PascalCase`
- Commits: single-line conventional format

See [docs/dev/commit-conventions.md](docs/dev/commit-conventions.md) for full conventions.

## Skills & Tasks

| Task                    | Skill File                                    |
| ----------------------- | --------------------------------------------- |
| Create hedge fund agent | `.agents/skills/new-agent/SKILL.md`           |
| Create data scanner     | `.agents/skills/new-scanner/SKILL.md`         |
| Create trading strategy | `.agents/skills/new-strategy/SKILL.md`        |
| Add technical indicator | `.agents/skills/technical-indicator/SKILL.md` |
| Work with GPT/prompts   | `.agents/skills/gpt-integration/SKILL.md`     |
| Create Pydantic models  | `.agents/skills/pydantic-model/SKILL.md`      |
| Modify execution engine | `.agents/skills/execution/SKILL.md`           |

## 🚫 Never Do This

- ❌ Code without tests
- ❌ Hardcode API keys or secrets
- ❌ Skip test verification
- ❌ Large multi-feature PRs
- ❌ Run full test suite repeatedly to debug
- ❌ Hardcode GitHub repo owner/name
- ❌ Place real trades in test mode

## 🌳 Worktree Management

You are working in a **git worktree** - an isolated workspace. See [docs/dev/tdd-flow.md](docs/dev/tdd-flow.md) for workflow details.

**One worktree = One issue = One session.**

## GitHub Operations

See [docs/dev/github-operations.md](docs/dev/github-operations.md) for GitHub MCP tools reference.

---

**Remember**: Tests first, small changes, always reference issues. You're building a production trading system - precision and safety matter!
