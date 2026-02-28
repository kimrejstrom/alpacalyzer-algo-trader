from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentSignalRecord(BaseModel):
    """One agent's contribution to the trade decision."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    agent: str = Field(description="Agent name, e.g. technical_analyst, warren_buffett")
    signal: str | None = Field(default=None, description="Signal: bullish, bearish, or neutral")
    confidence: float | None = Field(default=None, ge=0, le=100, description="Confidence score 0-100")
    reasoning: dict[str, Any] | str | None = Field(default=None, description="Full reasoning output from agent")


class DecisionContext(BaseModel):
    """The full decision chain for a trade."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    agent_signals: list[AgentSignalRecord] = Field(default_factory=list, description="All agents' signals/votes")
    portfolio_decision: dict[str, Any] | None = Field(default=None, description="PortfolioDecision as dict")
    risk_assessment: dict[str, Any] | None = Field(default=None, description="Risk manager output")
    strategy_params: dict[str, Any] | None = Field(default=None, description="TradingStrategy as dict")
    scanner_source: str | None = Field(default=None, description="Scanner source: reddit, social, technical, finviz")
    scanner_reasoning: str | None = Field(default=None, description="Why this ticker was surfaced")
    llm_costs: list[dict[str, Any]] | None = Field(default=None, description="LLMCallEvent summaries")


class TradeDecisionRecord(BaseModel):
    """Complete trade record for journal sync."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    ticker: str = Field(description="Stock ticker symbol")
    side: Literal["LONG", "SHORT"] = Field(description="Position side")
    shares: int = Field(gt=0, description="Number of shares")

    entry_price: str = Field(description="Entry price as decimal string")
    exit_price: str | None = Field(default=None, description="Exit price as decimal string")
    target_price: str | None = Field(default=None, description="Target price as decimal string")
    stop_price: str | None = Field(default=None, description="Stop price as decimal string")

    entry_date: str = Field(description="Entry date in ISO 8601 format")
    exit_date: str | None = Field(default=None, description="Exit date in ISO 8601 format")

    status: Literal["OPEN", "WIN", "LOSS"] = Field(description="Trade status")
    realized_pnl: float | None = Field(default=None, description="Realized profit/loss in dollars")
    realized_pnl_pct: float | None = Field(default=None, description="Realized profit/loss as percentage")
    hold_duration_hours: float | None = Field(default=None, description="How long position was held in hours")
    exit_reason: str | None = Field(default=None, description="Reason for exit")
    exit_mechanism: str | None = Field(default=None, description="Exit mechanism: dynamic_exit, bracket_order, etc.")

    decision_context: DecisionContext = Field(default_factory=DecisionContext, description="Full decision context")

    strategy_name: str | None = Field(default=None, description="Strategy name")
    setup_notes: str | None = Field(default=None, description="Setup notes")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
