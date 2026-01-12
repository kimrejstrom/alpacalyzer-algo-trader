from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Price(BaseModel):
    open: float
    close: float
    high: float
    low: float
    volume: int
    time: str


class PriceResponse(BaseModel):
    ticker: str
    prices: list[Price]


class FinancialMetrics(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str
    market_cap: float | None
    enterprise_value: float | None
    price_to_earnings_ratio: float | None
    price_to_book_ratio: float | None
    price_to_sales_ratio: float | None
    enterprise_value_to_ebitda_ratio: float | None
    enterprise_value_to_revenue_ratio: float | None
    free_cash_flow_yield: float | None
    peg_ratio: float | None
    gross_margin: float | None
    operating_margin: float | None
    net_margin: float | None
    return_on_equity: float | None
    return_on_assets: float | None
    return_on_invested_capital: float | None
    asset_turnover: float | None
    inventory_turnover: float | None
    receivables_turnover: float | None
    days_sales_outstanding: float | None
    operating_cycle: float | None
    working_capital_turnover: float | None
    current_ratio: float | None
    quick_ratio: float | None
    cash_ratio: float | None
    operating_cash_flow_ratio: float | None
    debt_to_equity: float | None
    debt_to_assets: float | None
    interest_coverage: float | None
    revenue_growth: float | None
    earnings_growth: float | None
    book_value_growth: float | None
    earnings_per_share_growth: float | None
    free_cash_flow_growth: float | None
    operating_income_growth: float | None
    ebitda_growth: float | None
    payout_ratio: float | None
    earnings_per_share: float | None
    book_value_per_share: float | None
    free_cash_flow_per_share: float | None


class FinancialMetricsResponse(BaseModel):
    financial_metrics: list[FinancialMetrics]


class LineItem(BaseModel):
    ticker: str
    report_period: str
    period: str
    currency: str
    free_cash_flow: float | None = None
    revenue: float | None = None
    operating_margin: float | None = None
    debt_to_equity: float | None = None
    total_assets: float | None = None
    total_liabilities: float | None = None
    dividends_and_other_cash_distributions: float | None = None
    outstanding_shares: float | None = None
    research_and_development: float | None = None
    capital_expenditure: float | None = None
    operating_expense: float | None = None
    earnings_per_share: float | None = None
    net_income: float | None = None
    book_value_per_share: float | None = None
    current_assets: float | None = None
    current_liabilities: float | None = None

    # Allow additional fields dynamically
    model_config = ConfigDict(extra="allow")


class LineItemResponse(BaseModel):
    search_results: list[LineItem]


class InsiderTrade(BaseModel):
    ticker: str
    issuer: str | None
    name: str | None
    title: str | None
    is_board_director: bool | None
    transaction_date: str | None
    transaction_shares: float | None
    transaction_price_per_share: float | None
    transaction_value: float | None
    shares_owned_before_transaction: float | None
    shares_owned_after_transaction: float | None
    security_title: str | None
    filing_date: str


class InsiderTradeResponse(BaseModel):
    insider_trades: list[InsiderTrade]


class CompanyNews(BaseModel):
    ticker: str
    title: str
    author: str
    source: str
    date: str
    url: str
    sentiment: str | None = None


class CompanyNewsResponse(BaseModel):
    news: list[CompanyNews]


class AnalystSignal(BaseModel):
    signal: str | None = None
    confidence: float | None = None
    reasoning: dict[Any, Any] | str | None = None


class TickerAnalysis(BaseModel):
    ticker: str
    analyst_signals: dict[str, AnalystSignal]  # agent_name -> signal mapping


class AgentStateMetadata(BaseModel):
    show_reasoning: bool = False
    model_config = {"extra": "allow"}


class PortfolioDecision(BaseModel):
    ticker: str
    action: Literal["buy", "sell", "short", "cover", "hold"]
    quantity: int = Field(description="Number of shares to trade")
    confidence: float = Field(description="Confidence in the decision, between 0.0 and 100.0")
    reasoning: str = Field(description="Reasoning for the decision")


class PortfolioManagerOutput(BaseModel):
    decisions: list[PortfolioDecision]


class TopTicker(BaseModel):
    ticker: str
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str
    mentions: int = 0
    upvotes: int = 0
    rank: int = 0


# Pydantic model for top swing trade tickers
class TopTickersResponse(BaseModel):
    top_tickers: list[TopTicker]


# Enum for predefined entry criteria conditions
class EntryType(Enum):
    PRICE_NEAR_SUPPORT = "price_near_support"  # Price is at/near a historical support level
    PRICE_NEAR_RESISTANCE = "price_near_resistance"  # Price is at/near a resistance level
    BREAKOUT_ABOVE = "breakout_above"  # Price breaking above a level (e.g., prior high)
    BREAKDOWN_BELOW = "breakdown_below"  # Price breaking below a level (e.g., prior low)
    RSI_OVERSOLD = "rsi_oversold"  # RSI below a certain threshold (typically 30)
    RSI_OVERBOUGHT = "rsi_overbought"  # RSI above a certain threshold (typically 70)
    ABOVE_MOVING_AVERAGE_20 = "above_ma20"  # Price is above the 20-day SMA/EMA
    BELOW_MOVING_AVERAGE_20 = "below_ma20"  # Price is below the 20-day SMA/EMA
    ABOVE_MOVING_AVERAGE_50 = "above_ma50"  # Price is above the 50-day SMA/EMA
    BELOW_MOVING_AVERAGE_50 = "below_ma50"  # Price is below the 50-day SMA/EMA
    # Candlestick Patterns
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    SHOOTING_STAR = "shooting_star"
    HAMMER = "hammer"
    DOJI = "doji"


class EntryCriteria(BaseModel):
    entry_type: EntryType
    value: float

    model_config = ConfigDict(use_enum_values=True)


# Pydantic model for trading strategy
class TradingStrategy(BaseModel):
    ticker: str
    quantity: int
    entry_point: float
    stop_loss: float
    target_price: float
    risk_reward_ratio: float
    strategy_notes: str
    trade_type: str  # "long" or "short"
    entry_criteria: list[EntryCriteria]


class TradingStrategyResponse(BaseModel):
    strategies: list[TradingStrategy]


class SentimentAnalysis(BaseModel):
    sentiment: Literal["Bullish", "Bearish", "Neutral"]
    score: float
    highlights: list[str]
    rationale: str


class SentimentAnalysisResponse(BaseModel):
    sentiment_analysis: list[SentimentAnalysis]
