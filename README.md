# Alpacalyzer Algo Trader

An AI-powered algorithmic trading platform that combines technical analysis, social media sentiment, and multi-agent decision-making to execute automated trading strategies through the Alpaca Markets API.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Development](#development)
- [Testing](#testing)
- [Documentation](#documentation)

---

## Overview

Alpacalyzer is an algorithmic, AI-powered hedge fund suite with analytic and trading capabilities. It combines multiple data sources to identify trading opportunities:

- **Technical Analysis**: Evaluates price patterns, momentum indicators (RSI, MACD), and chart formations via TA-Lib
- **Social Media Insights**: Analyzes Reddit (r/wallstreetbets, r/stocks), Stocktwits, and Finviz for trending stocks
- **AI Decision Engine**: Uses a LangGraph-based "Hedge Fund Agent" framework with GPT-4 for final trading decisions

The system executes trades automatically with predefined risk management parameters through bracket orders.

---

## Features

- **Multi-source Market Scanning**: Combines technical, social media, and fundamental analysis
- **Hedge Fund Agent Framework**: LangGraph workflow with specialized AI agents (value investors, quants, sentiment analysts)
- **Automated Trading**: Executes trades with configurable strategies via Alpaca API
- **Technical Analysis**: TA-Lib powered indicators (RSI, MACD, Bollinger Bands, moving averages)
- **Position Management**: Monitors open positions with stop loss/take profit rules
- **Bracket Orders**: Uses Alpaca's bracket orders for trade management with predefined exits

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPPORTUNITY SCANNERS                         │
├─────────────────────────────────────────────────────────────────┤
│  RedditScanner      - Analyzes r/wallstreetbets, r/stocks       │
│  SocialScanner      - WSB + Stocktwits + Finviz trending        │
│  FinvizScanner      - Fundamental + technical screening          │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HEDGE FUND AGENT WORKFLOW (LangGraph)          │
├─────────────────────────────────────────────────────────────────┤
│  Technical Analyst  - RSI, MACD, moving averages, patterns      │
│  Sentiment Agent    - Social media sentiment analysis           │
│  Quant Agent        - Quantitative metrics analysis             │
│  Value Investors    - Graham, Buffett, Munger, Ackman, Wood    │
│           │                                                      │
│           ▼                                                      │
│  Risk Manager       - Position sizing, risk assessment          │
│  Portfolio Manager  - Portfolio allocation decisions            │
│  Trading Strategist - Final trading recommendation              │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                        TRADER (Execution)                        │
├─────────────────────────────────────────────────────────────────┤
│  Monitors positions and market conditions                        │
│  Evaluates entry/exit conditions                                │
│  Places bracket orders (LONG/SHORT with stop-loss + target)     │
│  Executes liquidations when conditions met                       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component       | Tech            | Location                                         |
| --------------- | --------------- | ------------------------------------------------ |
| CLI Entry       | Click           | `src/alpacalyzer/cli.py`                         |
| Hedge Fund      | LangGraph       | `src/alpacalyzer/hedge_fund.py`                  |
| Agents          | LangGraph nodes | `src/alpacalyzer/agents/`                        |
| Scanners        | Python classes  | `src/alpacalyzer/scanners/`                      |
| Tech Analysis   | TA-Lib          | `src/alpacalyzer/analysis/technical_analysis.py` |
| Trader          | Stateful class  | `src/alpacalyzer/trading/trader.py`              |
| Alpaca Client   | alpaca-py       | `src/alpacalyzer/trading/alpaca_client.py`       |
| Data Models     | Pydantic        | `src/alpacalyzer/data/models.py`                 |
| GPT Integration | OpenAI API      | `src/alpacalyzer/gpt/call_gpt.py`                |

---

## Quick Start

### Prerequisites

- **Python** >=3.13.0 <3.14.0
- **uv** >=0.5.7 ([installation](https://docs.astral.sh/uv/getting-started/installation/))
- **TA-Lib** system library (see below)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/kimrejstrom/alpacalyzer-algo-trader.git
cd alpacalyzer-algo-trader

# 2. Install TA-Lib system library
# macOS
brew install ta-lib

# Linux (Ubuntu/Debian)
wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
tar -xzf ta-lib-0.6.4-src.tar.gz
cd ta-lib-0.6.4 && ./configure && make && sudo make install
cd ..

# 3. Install Python dependencies
uv sync

# 4. Setup environment
cp .env.example .env
# Edit .env with your API keys (see below)

# 5. Enable pre-commit hooks
pre-commit install
```

### Environment Variables

Create a `.env` file with:

```bash
# Alpaca API (paper trading recommended for development)
APCA_API_KEY_ID=your_key_here
APCA_API_SECRET_KEY=your_secret_here
APCA_API_BASE_URL=https://paper-api.alpaca.markets

# OpenAI API (for GPT-4 agents)
OPENAI_API_KEY=your_key_here

# Optional
LOG_LEVEL=INFO
```

---

## Usage

### Analysis Mode (No Trades)

```bash
uv run alpacalyzer --analyze
```

### Full Trading Mode

```bash
uv run alpacalyzer
```

### Focus on Specific Tickers

```bash
uv run alpacalyzer --analyze --tickers=AAPL,MSFT,GOOG
```

---

## Development

### Tooling

| Tool                                      | Purpose                   | Config                      |
| ----------------------------------------- | ------------------------- | --------------------------- |
| [uv](https://github.com/astral-sh/uv)     | Package & project manager | `pyproject.toml`, `uv.lock` |
| [pre-commit](https://pre-commit.com/)     | Git hooks                 | `.pre-commit-config.yaml`   |
| [ruff](https://github.com/astral-sh/ruff) | Linting & formatting      | `pyproject.toml`            |
| [ty](https://github.com/astral-sh/ty)     | Type checking             | -                           |
| [pytest](https://docs.pytest.org/)        | Testing                   | `pyproject.toml`            |

### Commands

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run ty check src

# Run all checks
uv run ruff check . && uv run ruff format . && uv run ty check src
```

### For AI Agents

See [AGENTS.md](AGENTS.md) for comprehensive development guidelines including:

- Test-driven development workflow
- Skill files for common tasks (`.claude/skills/`)
- Code review instructions
- Worktree management for parallel development

---

## Testing

```bash
# Run all tests
uv run pytest tests

# Run with coverage
uv run pytest tests --cov=src

# Run specific test file
uv run pytest tests/test_technical_analysis.py -v
```

### Key Testing Patterns

- **OpenAI mocking**: Automatic via `conftest.py` fixture
- **Alpaca API mocking**: Use `monkeypatch` for trading logic tests
- **No real API calls**: All external APIs must be mocked in tests

---

## Documentation

- [AGENTS.md](AGENTS.md) - AI agent development guidelines
- [migration_plan.md](migration_plan.md) - Architecture refactoring roadmap
- [docs/](docs/index.md) - In-depth technical documentation

---

## License

MIT License - see [LICENSE](LICENSE)
