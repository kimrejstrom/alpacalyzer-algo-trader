import os
from datetime import UTC, datetime, timedelta
from typing import cast

import pandas as pd
from alpaca.data.enums import Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.models import Bar, BarSet
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide
from alpaca.trading.models import Calendar, Clock, Order, Position, TradeAccount, TradeUpdate
from alpaca.trading.requests import GetCalendarRequest
from alpaca.trading.stream import TradingStream
from dotenv import load_dotenv

from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import get_logger

logger = get_logger()

# Load environment variables
load_dotenv()

# Retrieve API keys
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "test")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "test")

# Initialize Alpaca TradingClient (Set paper=True for paper trading)
trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
history_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
trading_stream = TradingStream(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)


# Expose trading_client for import
__all__ = ["trading_client", "history_client"]


def log_order(order: Order) -> None:
    """Logs key details of an Alpaca order in a readable format."""
    log_message = f"""
======================================
Order Summary - {order.symbol}
======================================
Order ID: {order.id}
Client Order ID: {order.client_order_id}
Order Type: {order.order_type or "N/A"}
Order Class: {order.order_class.value}
Side: {order.side}
Quantity: {order.qty}
Limit Price: {order.limit_price or "N/A"}
Stop Price: {order.stop_price or "N/A"}
Time in Force: {order.time_in_force.value}
Status: {order.status.value}
Created At: {order.created_at.strftime("%Y-%m-%d %H:%M:%S %Z")}
Updated At: {order.updated_at.strftime("%Y-%m-%d %H:%M:%S %Z")}
Filled Quantity: {order.filled_qty}
Filled Avg Price: {order.filled_avg_price or "N/A"}
Expiration: {order.expires_at.strftime("%Y-%m-%d %H:%M:%S %Z") if order.expires_at else "N/A"}
Extended Hours: {"Yes" if order.extended_hours else "No"}

Bracket Order Details:
--------------------------------------
"""

    # Log bracket orders if present
    if order.legs:
        for leg in order.legs:
            log_message += f"""
Leg Order: {leg.side}
Order Type: {leg.order_type}
Quantity: {leg.qty}
Limit Price: {leg.limit_price or "N/A"}
Stop Price: {leg.stop_price or "N/A"}
Status: {leg.status.value}
Client Order ID: {leg.client_order_id}
Created At: {leg.created_at.strftime("%Y-%m-%d %H:%M:%S %Z")}
            """
    else:
        log_message += "No bracket legs found.\n"

    log_message += "\n======================================="

    logger.info(log_message)  # Log the formatted message


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


@timed_lru_cache(seconds=60, maxsize=128)
def get_current_price(ticker: str) -> float | None:
    """
    Fetches the latest trade price for the given ticker from Alpaca.

    Args:
        ticker (str): Stock ticker symbol (e.g., 'AAPL')

    Returns:
        Optional[float]: Latest trade price or None if not found
    """
    try:
        response = history_client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=ticker))
        return float(response[ticker].price)
    except Exception as e:
        logger.debug(f"Error fetching price for {ticker}: {str(e)}", exc_info=True)
        return None


@timed_lru_cache(seconds=60, maxsize=128)
def get_stock_bars(symbol, request_type="minute") -> pd.DataFrame | None:
    """Get historical data from Alpaca."""
    try:
        now_utc = datetime.now(UTC)  # Get the current UTC time
        end = now_utc - timedelta(seconds=930)  # 15.5 minutes ago

        # Determine the `start` time based on the `request_type`
        if request_type == "minute":
            start = end - timedelta(minutes=1440)  # Last 24 hours
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                start=start,
                end=end,
                adjustment=Adjustment.ALL,
            )
        else:
            start = end - timedelta(days=100)  # Last 100 days
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                adjustment=Adjustment.ALL,
            )
        try:
            bars_response = history_client.get_stock_bars(request)
            candles = cast(BarSet, bars_response).data.get(symbol)
            if not candles or candles is None:
                return None

            # Check market status
            if get_market_status() == "open":
                # Fetch the latest bar for fresh data (only available during market hours)
                latest_bar_response = history_client.get_stock_latest_bar(
                    StockLatestBarRequest(symbol_or_symbols=symbol)
                )
                latest_bar = cast(dict[str, Bar], latest_bar_response).get(symbol)

                # Append the latest bar if available, otherwise duplicate the last candle
                candles.append(latest_bar if latest_bar else candles[-1])
            else:
                # Market is closed, duplicate the last candle
                candles.append(candles[-1])

            return bars_to_df(candles)

        except Exception as e:
            logger.error(f"Error fetching stock bars for {symbol}: {str(e)}", exc_info=True)
            return None

    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}", exc_info=True)
        return None


def bars_to_df(bars: list[Bar]) -> pd.DataFrame:
    """Convert the list of Alpaca Bars to a DataFrame."""
    # Convert list of Bar objects to dictionaries
    df = pd.DataFrame([bar.model_dump() for bar in bars])

    # Ensure timestamp is converted to datetime and set as index
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df.set_index("timestamp", inplace=True)

    # Convert numeric columns to appropriate types
    numeric_cols = ["open", "high", "low", "close", "volume", "trade_count", "vwap"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    # Sort by timestamp (ascending order)
    df.sort_index(inplace=True)

    return df


def get_account_info():
    """Get account information."""
    account = trading_client.get_account()
    account_instance = cast(TradeAccount, account)
    return {
        "equity": float(account_instance.equity) if account_instance.equity else 0,
        "buying_power": float(account_instance.buying_power) if account_instance.buying_power else 0,
        "initial_margin": float(account_instance.initial_margin) if account_instance.initial_margin else 0,
        "margin_multiplier": float(account_instance.multiplier) if account_instance.multiplier else 0,
        "daytrading_buying_power": float(account_instance.daytrading_buying_power)
        if account_instance.daytrading_buying_power
        else 0,
        "maintenance_margin": float(account_instance.maintenance_margin) if account_instance.maintenance_margin else 0,
    }


def get_positions() -> list[Position]:
    """Get all positions."""
    try:
        positions = trading_client.get_all_positions()
        return cast(list[Position], positions)
    except Exception as e:
        logger.error(f"Error fetching positions: {str(e)}", exc_info=True)
        return []


def parse_strategy_from_client_order_id(client_order_id: str) -> str:
    """Assuming client_order_id format is '{strategy}_{symbol}_{side}_{uuid}'."""
    parts = client_order_id.split("_")
    if len(parts) > 1:
        return parts[0]
    if "day" in client_order_id:
        return "day"
    if "swing" in client_order_id:
        return "swing"
    if "hedge" in client_order_id:
        return "hedge"
    return "bracket"


async def trade_updates_handler(update: TradeUpdate):
    """Processes trade update and writes to SQLite via `upsert_position`."""

    client_order_id = update.order.client_order_id
    symbol = update.order.symbol
    event = update.event
    side = update.order.side if update.order.side else OrderSide.BUY
    strategy = parse_strategy_from_client_order_id(client_order_id)

    logger.info(f"\nTrade Update: {event} for ticker: {symbol} - Strategy: {strategy} ({side})")

    if event in {"fill", "partial_fill"}:
        if symbol is None:
            logger.warning(f"Trade update missing symbol: {update}")
            return
        logger.info(f"Order filled for ticker: {symbol} - Strategy: {strategy} ({side})")

    elif event == "canceled":
        logger.warning(f"Order canceled for ticker: {symbol} - Strategy: {strategy} ({side})")

    elif event == "rejected":
        logger.warning(f"Order rejected for ticker: {symbol} - Strategy: {strategy} ({side})")


def consume_trade_updates():
    """Start listening to trade updates from Alpaca."""
    trading_stream.subscribe_trade_updates(trade_updates_handler)
    logger.info("Listening for trade updates...")
    trading_stream.run()


if __name__ == "__main__":
    consume_trade_updates()
