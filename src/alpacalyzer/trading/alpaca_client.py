import os
from datetime import UTC, timedelta
from typing import cast

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Calendar, Clock
from alpaca.trading.requests import GetCalendarRequest
from dotenv import load_dotenv

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import logger

# Load environment variables
load_dotenv()

# Retrieve API keys
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "test")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "test")

# Initialize Alpaca TradingClient (Set paper=True for paper trading)
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
history_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


# Expose trading_client for import
__all__ = ["trading_client", "history_client"]


@timed_lru_cache(seconds=60, maxsize=128)
def get_market_status() -> str:
    """
    Determine the current market session: open, pre-market, after-hours, or closed.

    Returns:
        str: "open", "pre-market", "after-hours", or "closed".
    """
    # Fetch current market clock (timestamps are in UTC)
    clock = trading_client.get_clock()
    clock_instance = cast(Clock, clock)

    # Convert timestamps to UTC timezone-aware datetimes
    current_time = clock_instance.timestamp.replace(tzinfo=UTC)
    market_open_time = clock_instance.next_open.replace(tzinfo=UTC)

    # Get today's close by checking the most recent trading day

    trading_days = trading_client.get_calendar(GetCalendarRequest(start=current_time.date(), end=current_time.date()))
    trading_days_instance = cast(list[Calendar], trading_days)
    if not trading_days:
        logger.info(f"{current_time.date()} is not a trading day. Next market open: {market_open_time}")
        return "closed"  # No market data available, assume closed

    today_market_close = trading_days_instance[0].close.replace(tzinfo=UTC)

    # US Market pre-market starts 4 hours before the official open
    pre_market_start_time = market_open_time - timedelta(hours=4)

    # US Market after-hours trading lasts 4 hours after the close
    after_hours_end_time = today_market_close + timedelta(hours=4)

    # Market session logic
    if clock_instance.is_open:
        return "open"

    if pre_market_start_time <= current_time < market_open_time:
        return "pre-market"

    if today_market_close <= current_time < after_hours_end_time:
        return "after-hours"

    return "closed"  # Default case: market is fully closed
