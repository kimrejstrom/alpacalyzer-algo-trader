# AI Agent Instructions for Alpacalyzer Algo Trader

> **Critical**: You are a principal software engineer working on Alpacalyzer Algo Trader. Your job: build features incrementally using test-first development.

📋 **Related Documentation**:

- [Code Review Subagent](.opencode/agent/code-reviewer.md) - Automated PR review agent
- [Migration Plan](migration_roadmap.md) - Architecture refactoring roadmap
- [Superpowers Plugin Integration](SUPERPOWERS_INTEGRATION.md) - How to use superpowers skills with this project

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

## 🏗️ Architecture Overview

Alpacalyzer is an AI-powered algorithmic trading platform that combines technical analysis, social media sentiment, and multi-agent decision-making.

### Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPPORTUNITY PIPELINE                         │
├─────────────────────────────────────────────────────────────────┤
│  ScannerRegistry                                                 │
│  ├── RedditScannerAdapter                                        │
│  └── SocialScannerAdapter                                        │
│              │                                                   │
│              ▼                                                   │
│  OpportunityAggregator                                           │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TRADING ORCHESTRATOR                           │
├─────────────────────────────────────────────────────────────────┤
│  TradingOrchestrator                                             │
│  ├── scan() → OpportunityAggregator                             │
│  ├── analyze() → Hedge Fund Agents                              │
│  └── execute() → ExecutionEngine                                │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EXECUTION ENGINE                             │
├─────────────────────────────────────────────────────────────────┤
│  ExecutionEngine                                                 │
│  ├── SignalQueue                                                 │
│  ├── PositionTracker                                            │
│  ├── CooldownManager                                            │
│  └── OrderManager                                                │
│                                                                  │
│  Strategy (via StrategyRegistry)                                │
│  ├── MomentumStrategy                                            │
│  ├── BreakoutStrategy                                            │
│  └── MeanReversionStrategy                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component       | Tech            | Location                                         | Key Pattern            |
| --------------- | --------------- | ------------------------------------------------ | ---------------------- |
| CLI Entry       | Click           | `src/alpacalyzer/cli.py`                         | Command + scheduling   |
| Orchestrator    | Python          | `src/alpacalyzer/orchestrator.py`                | Pipeline coordination  |
| Execution       | Python          | `src/alpacalyzer/execution/`                     | Single loop engine     |
| Strategies      | Protocol        | `src/alpacalyzer/strategies/`                    | Pluggable strategies   |
| Pipeline        | Python          | `src/alpacalyzer/pipeline/`                      | Scanner aggregation    |
| Events          | Pydantic        | `src/alpacalyzer/events/`                        | Structured logging     |
| Hedge Fund      | LangGraph       | `src/alpacalyzer/hedge_fund.py`                  | DAG workflow           |
| Agents          | LangGraph nodes | `src/alpacalyzer/agents/`                        | Agent pattern          |
| Scanners        | Python classes  | `src/alpacalyzer/scanners/`                      | Data collectors        |
| Tech Analysis   | TA-Lib          | `src/alpacalyzer/analysis/technical_analysis.py` | Indicator calculations |
| Alpaca Client   | alpaca-py       | `src/alpacalyzer/trading/alpaca_client.py`       | API wrapper            |
| Data Models     | Pydantic        | `src/alpacalyzer/data/models.py`                 | Type-safe models       |
| GPT Integration | OpenAI API      | `src/alpacalyzer/gpt/call_gpt.py`                | Structured output      |

### Agent vs. Strategy Decision Authority

The trading system uses a two-tier decision model:

**Tier 1: Agent (GPT-4 via TradingStrategist)**

- Analyzes ticker from multiple perspectives
- Proposes optimal trade setup:
  - Entry point (price)
  - Stop loss
  - Take profit target
  - Position size (quantity)
  - Trade direction (long/short)
- Provides reasoning

**Tier 2: Trading Strategy**

- Validates that agent's setup fits strategy's philosophy
- Can REJECT if conditions don't match:
  - MomentumStrategy: Rejects negative momentum, weak technicals
  - BreakoutStrategy: Rejects no consolidation pattern
  - MeanReversionStrategy: Rejects not-oversold/overbought conditions
- MUST USE agent values for entry/stop/target/size (no recalculation)

> **Note**: Not all strategies currently accept agent recommendations. BreakoutStrategy and MeanReversionStrategy currently detect opportunities independently through technical analysis. Agent integration for these strategies is planned for a future enhancement. MomentumStrategy is the primary strategy that follows the agent-propose/validate model.

**Key Principle**

> Agents propose, strategies validate. Strategies never override agent's calculated trade parameters.

**Example Valid Flow:**

1. Agent: "Buy AAPL @ $150, stop $145.5, target $163.5, 100 shares"
2. MomentumStrategy: Validates momentum positive, technicals strong ✓
3. ExecutionEngine: Submits order using agent's values

**Example Valid Rejection:**

1. Agent: "Buy AAPL @ $150, stop $145.5, target $163.5, 100 shares"
2. MomentumStrategy: "Momentum -5% (negative), rejects" ✗
3. ExecutionEngine: Discards signal

**What Strategies Don't Do:**

- Don't recalculate entry price
- Don't change stop loss level
- Don't modify take profit target
- Don't adjust quantity based on their own logic

### Migration in Progress

**See `migration_roadmap.md` for the target architecture**. We are refactoring from a monolithic trader to:

- **Strategy Abstraction** - Pluggable trading strategies (`strategies/`)
- **Execution Engine** - Clean execution loop (`execution/`)
- **Event System** - Structured JSON logging (`events/`)
- **Pipeline** - Unified opportunity aggregation (`pipeline/`)

## � Pre-Flight Checks

**Before starting ANY work, verify your environment:**

```bash
# 1. Confirm current directory
pwd

# 2. Get repo owner/name from git remote (CRITICAL for GitHub API calls)
git remote get-url origin
# Parse: git@github.com:OWNER/REPO.git → use OWNER and REPO for all GitHub MCP tools

# 3. Check git status - review any existing staged/unstaged changes
git status

# 4. Verify you're on the correct branch
git branch --show-current

# 5. If staged changes exist from previous sessions, review before proceeding
git diff --cached
```

**Why this matters**:

- Previous agent sessions may have left staged changes that conflict with your work
- The repo owner/name in the git remote is the source of truth for GitHub API calls
- **Never hardcode or assume these values**

## �🔄 Development Flow

### Starting Work on an Issue

When the user says "start work on issue XX":

1. **Get Repo Info from Git Remote** (CRITICAL - do this FIRST):

   ```bash
   git remote get-url origin
   ```

   Parse owner and repo name. **Never hardcode or assume repo owner/name.**

2. **Fetch the Issue**: Use GitHub MCP tools with correct owner/repo
3. **Verify Branch**: Confirm you're on the correct feature branch
4. **Plan Implementation**: Break down tasks, define specs, list test scenarios
5. **Create Local Plan File**: `_PLAN_issue-XX.md` (git-ignored)
6. **Follow TDD Flow**

### Standard TDD Flow

```bash
# 1. Write test in tests/
# Example: tests/test_momentum_strategy.py

# 2. Verify test fails
uv run pytest tests/test_momentum_strategy.py -v

# 3. Implement minimal code to pass
# Example: src/alpacalyzer/strategies/momentum.py

# 4. Verify test passes
uv run pytest tests/test_momentum_strategy.py -v

# 5. Commit
git add tests/test_momentum_strategy.py src/alpacalyzer/strategies/momentum.py
git commit -m "feat(strategies): implement momentum strategy for #XX"

# 6. Create PR using GitHub MCP tools
```

### Completing a Feature

1. **Ensure all tests pass**

   ```bash
   uv run pytest tests
   ```

2. **Run linting and type checking**

   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run ty check src
   ```

3. **Push changes and create PR** using GitHub MCP tools

4. **Run automated code review** (MANDATORY):

   ```
   @code-reviewer Please review:
   - ISSUE_NUMBER: <issue_number>
   - PR_NUMBER: <pr_number>
   - OWNER: <repo_owner>
   - REPO: <repo_name>
   - FEATURE_DESCRIPTION: <brief description>
   ```

5. **Address any Critical/High issues** found in `CODE_REVIEW_<ISSUE>.md`

6. **Reply with completion message**:
   ```
   Feature #XX ready for review. PR url: {PR_URL}, also see _PLAN_issue-XX.md for details
   ```

> **Note**: The `@code-reviewer` subagent is defined in `.opencode/agent/code-reviewer.md`. It will write findings to `CODE_REVIEW_<ISSUE>.md` in the root directory.

### Closing a Pull Request

When the feature is approved and ready to merge:

1. **Review docs impact**: Update README.md or AGENTS.md if the change affects setup or architecture
2. **Merge PR**: Use GitHub MCP tools to squash merge (auto-closes linked issue)
3. **Highlight future work**: Call out any follow-ups or ideas discovered during implementation, ask user whether each should be tracked as a new GitHub issue
4. **Notify user**: Tell the user the PR is merged and they can remove the worktree:
   ```
   PR merged! You can now close this IDE window and run `wt remove` from the main worktree.
   ```

> **Note**: Worktree removal is handled by the human orchestrator, not the agent.

## 🧪 Testing

### Test Structure

```
tests/
├── conftest.py              # Fixtures (OpenAI client auto-mocked!)
├── test_agents/             # Agent tests
├── test_scanners/           # Scanner tests
├── test_strategies/         # Strategy tests (new)
├── test_technical_analysis.py
└── test_*.py
```

### Key Testing Patterns

**OpenAI mocking is automatic** via `conftest.py`:

```python
# No need to mock in individual tests!
# The fixture does it automatically
def test_agent_analysis(mock_openai_client):
    mock_openai_client.chat.completions.create.return_value = ...
```

**Trading logic tests** should mock Alpaca API:

```python
from unittest.mock import MagicMock

def test_place_order(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_client",
                       lambda: mock_client)
    # Test order placement
```

### Debugging Test Failures

**CRITICAL: Follow this exact process!**

```bash
# Step 1: Run ONCE and save output
uv run pytest tests > test-output.txt 2>&1

# Step 2: Identify failing tests
cat test-output.txt | grep "FAILED"

# Step 3: Read error messages BEFORE looking at code
cat test-output.txt | grep -A 20 "Error:"

# Step 4: Run ONLY failing test file
uv run pytest tests/test_failing_module.py -vv
```

**Never run the full test suite repeatedly during debugging!**

## 📝 Conventions

### Files

- Python files: `snake_case.py`
- Test files: `test_{module_name}.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`

### Commits

Follow conventional commits with **single-line format only** (avoids terminal issues):

```bash
# ✅ GOOD - single line
git commit -m "feat(strategies): implement momentum strategy for #XX"

# ❌ BAD - multi-line causes issues
git commit -m "feat(strategies): implement momentum strategy

This adds..."
```

Examples:

- `feat(scope): add momentum strategy for #XX`
- `fix(agents): correct sentiment analysis bug for #XX`
- `docs(readme): update architecture diagram for #XX`
- `test(strategies): add breakout strategy tests for #XX`

### Branches

Format: `feature/issue-XX-short-description`

- Example: `feature/issue-4-strategy-config`
- Example: `feature/issue-17-event-models`

### Imports

Use absolute imports from package root:

```python
from alpacalyzer.agents.technicals_agent import TechnicalsAgent
from alpacalyzer.data.models import TradingSignals
from alpacalyzer.strategies.base import BaseStrategy
```

## 📚 Common Tasks & Skills

For detailed step-by-step procedures, see skill files in `.agents/skills/` (symlinked from `.claude/skills/`):

| Task                        | Skill File                     | When to Use                                                   |
| --------------------------- | ------------------------------ | ------------------------------------------------------------- |
| Create new hedge fund agent | `new-agent/SKILL.md`           | Adding Warren Buffett, Ray Dalio, etc.                        |
| Create new data scanner     | `new-scanner/SKILL.md`         | Adding Twitter, StockTwits scanner                            |
| Create trading strategy     | `new-strategy/SKILL.md`        | Adding breakout, mean reversion strategy                      |
| Add technical indicator     | `technical-indicator/SKILL.md` | Adding Bollinger Bands, ATR, etc.                             |
| Work with GPT/prompts       | `gpt-integration/SKILL.md`     | Modifying agent prompts, GPT calls                            |
| Create Pydantic models      | `pydantic-model/SKILL.md`      | Event types, configs, data models                             |
| Modify execution engine     | `execution/SKILL.md`           | Modifying execution loop, position tracking, order management |

**Always reference skill files when performing these tasks.**

## Pre-Commit Checklist

Before every commit:

- [ ] GitHub issue exists and referenced (`#XX`)
- [ ] Test written BEFORE implementation
- [ ] All tests pass (`uv run pytest tests`)
- [ ] Linting clean (`uv run ruff check .`)
- [ ] Formatting applied (`uv run ruff format .`)
- [ ] Type checking passes (`uv run ty check src`)
- [ ] Commit follows conventional format
- [ ] No hardcoded secrets (check for API keys, tokens)
- [ ] Single focused change only

## 🚫 Never Do This

- ❌ Code without tests
- ❌ Hardcode API keys, secrets, or credentials
- ❌ Skip test verification
- ❌ Large multi-feature PRs
- ❌ Run full test suite repeatedly to debug (save to file first!)
- ❌ Assume staged git changes are correct without reviewing
- ❌ Hardcode GitHub repo owner/name (always parse from `git remote`)
- ❌ Modify production database or live trading without explicit confirmation
- ❌ Place real trades in test mode
- ❌ Start a new issue in the same worktree session (each issue needs its own worktree)

## 🌳 Worktree Management

> **Important**: You are working in a **git worktree** - an isolated workspace with its own branch and Python venv. The human orchestrator manages worktree creation/removal from the terminal. Your job is feature implementation.

### What the Worktree Provides (Already Configured)

- **Isolated branch**: Your changes don't affect main or other worktrees
- **Isolated venv**: Dependencies are copied/synced per worktree
- **Safe development**: Multiple agents can work on different features simultaneously

### Parallel Work Safety

Multiple worktrees can run simultaneously without conflicts because each has:

- Different branch
- Different virtual environment (`.venv/`)
- Different test databases (if applicable)

### Human Orchestrator Workflow

The human manages worktrees from the terminal using `wt` (worktrunk):

```bash
# Create and switch to new worktree for an issue
wt switch -c feature/issue-XX-description

# Open in IDE with AI agent
kiro .   # or: cursor . / code .

# Monitor active worktrees
wt list

# After PR is merged, cleanup worktree
wt remove
```

### Agent Responsibilities

- **DO**: Implement features, write tests, create PRs, merge PRs
- **DO NOT**: Create worktrees, remove worktrees, switch branches, start new issues

The human will tell you when you're in a worktree. Just focus on the feature work.

### Session Scope (CRITICAL)

**One worktree = One issue = One session**. This is a hard boundary.

When your assigned issue is complete (PR created or merged):

1. **STOP** - Do not look for "next steps" or "follow-up issues"
2. **Report completion** - Tell the user the PR is ready/merged
3. **Wait** - The human orchestrator will create a new worktree for the next issue

**If asked to "continue" after completing an issue:**

- Clarify: "Issue #XX is complete. Should I continue work within this issue, or are you asking about a different issue?"
- Never assume "continue" means "start the next issue"

**Why this matters:**

- Each worktree has an isolated branch for ONE feature
- Starting a new issue in the same session causes branch pollution
- The human orchestrator manages parallel work across worktrees

### Worktree Commands (Reference Only)

> **Note**: These commands are for the human orchestrator. Do not run them from the IDE.

| Task                     | Command (Terminal)                 |
| ------------------------ | ---------------------------------- |
| Create worktree + switch | `wt switch -c feature/issue-XX`    |
| Switch to existing       | `wt switch feature/issue-XX`       |
| List all worktrees       | `wt list`                          |
| Open in IDE              | `kiro .` (from worktree directory) |
| Remove worktree          | `wt remove`                        |

### Code Review Files

When generating or reading code reviews:

- **Location**: Root directory of the worktree
- **Naming**: `CODE_REVIEW_<issue_number>.md` or `CODE_REVIEW_<feature_name>.md`
- **Example**: `CODE_REVIEW_42.md`, `CODE_REVIEW_momentum_strategy.md`
- **Note**: These files are git-ignored (see `.gitignore`)

When asked to read a code review file, search for `CODE_REVIEW_*.md` in the root.

## 📋 GitHub Operations

**Use GitHub MCP tools** instead of `gh` CLI for all GitHub operations:

### Issue Management

- Read issue: `mcp_io_github_git_issue_read(owner, repo, issue_number, method="get")`
- Create issue: `mcp_io_github_git_issue_write(method="create", owner, repo, title, body)`
- Update issue: `mcp_io_github_git_issue_write(method="update", owner, repo, issue_number, state="closed")`

### Pull Requests

- Create PR: `mcp_io_github_git_create_pull_request(owner, repo, title, body, head, base)`
- Update PR: `mcp_io_github_git_update_pull_request(owner, repo, pullNumber, ...)`
- Merge PR: `mcp_io_github_git_merge_pull_request(owner, repo, pullNumber, merge_method="squash")`

**Always get repo info first**:

```bash
git remote get-url origin
# Parse: owner = "kimrejstrom", repo = "alpacalyzer-algo-trader"
```

**Never hardcode** owner/repo values. Always parse from git remote.

## 🔍 Project-Specific Context

### Trading Platform Critical Safety

**This is a real trading platform**. Mistakes can cause financial loss:

1. **Analyze Mode First**: Always test in analyze mode before enabling real trades
2. **Mock External APIs**: All tests must mock Alpaca API and OpenAI
3. **No Hardcoded Symbols**: Never hardcode ticker symbols in production code
4. **Validate Orders**: Always validate order parameters before submission
5. **Risk Limits**: Respect risk management rules (position sizing, stop losses)

### Environment Variables

Required in `.env` (see `.env.example`):

```bash
# Alpaca API (paper trading recommended for development)
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here

# OpenAI API (for GPT-4 agents)
OPENAI_API_KEY=your_key_here

# Optional
LOG_LEVEL=INFO
```

**Never commit `.env` file!**

### Technical Analysis

This project uses **TA-Lib** extensively. Installation requires system library:

```bash
# macOS
brew install ta-lib

# Linux (CI workflow shows the process)
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xvzf ta-lib-0.4.0-src.tar.gz
cd ta-lib && ./configure --prefix=/usr && make && sudo make install
```

Python wrapper: `pip install ta-lib` (via `uv sync`)

### LangGraph Workflows

Agents are implemented as LangGraph nodes. When modifying agent workflow:

1. Understand the DAG structure in `hedge_fund.py`
2. Each agent returns a dictionary that updates shared state
3. State is defined in `graph/state.py`
4. Test agents in isolation first, then integration

### Migration Context

**Migration Complete** - see `migration_roadmap.md` for full details.

All phases of the architecture migration are now complete:

- **Phase 1**: `strategies/` module with 3 strategies
- **Phase 2**: `execution/` module (ExecutionEngine, SignalQueue, PositionTracker, CooldownManager, OrderManager)
- **Phase 3**: `events/` module with structured JSON logging
- **Phase 4**: `pipeline/` module (ScannerRegistry, OpportunityAggregator)
- **Phase 5**: Backtesting framework and performance dashboard
- **Phase 6**: Clean break - `Trader` class removed, `TradingOrchestrator` is the entry point

**Final Architecture Components**:

- `orchestrator.py` - TradingOrchestrator (replaces Trader)
- `strategies/` - Momentum, Breakout, MeanReversion strategies
- `execution/` - Single loop execution engine
- `pipeline/` - Scanner aggregation
- `events/` - Structured event logging

---

**Remember**: Tests first, small changes, always reference issues. You're building a production trading system - precision and safety matter!
