from enum import Enum

from pydantic import BaseModel


class TopTickers(BaseModel):
    ticker: str
    confidence: float
    recommendation: str


# Pydantic model for top swing trade tickers
class TopTickersResponse(BaseModel):
    top_tickers: list[TopTickers]


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

    class Config:
        use_enum_values = True


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
