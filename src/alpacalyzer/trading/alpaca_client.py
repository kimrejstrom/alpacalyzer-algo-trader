import os
from datetime import UTC, timedelta
from typing import Any, cast

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide
from alpaca.trading.models import Calendar, Clock, Order, Position, TradeAccount, TradeUpdate
from alpaca.trading.requests import GetCalendarRequest
from alpaca.trading.stream import TradingStream
from dotenv import load_dotenv

from alpacalyzer.db.db import (
    get_position_by_symbol_and_strategy,
    remove_position,
    upsert_position,
)
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
    }


def parse_strategy_from_client_order_id(client_order_id: str) -> str:
    """Assuming client_order_id format is '{strategy}_{symbol}_{side}_{uuid}'."""
    parts = client_order_id.split("_")
    if len(parts) > 1:
        return parts[0]
    if "day" in client_order_id:
        return "day"
    if "swing" in client_order_id:
        return "swing"
    return "swing"  # Bracket order legs do not have strategy in client_order_id


def update_position(symbol: str, strategy: str, existing_position: Any | None):
    """
    Update a single position.

    Args:
        symbol: Stock symbol
    """
    try:
        try:
            # Get fresh position from Alpaca
            alpaca_resp = trading_client.get_open_position(symbol)
            alpaca_position = cast(Position, alpaca_resp)
        except Exception as e:
            remove_position(symbol)
            logger.warning(f"Position not found for {symbol}. Removing from db: {str(e)}", exc_info=True)

        else:
            price = float(alpaca_position.current_price) if alpaca_position.current_price else 0
            high_water_mark = (
                float(price) if existing_position is None else max(existing_position["high_water_mark"], float(price))
            )

            upsert_position(
                strategy=strategy,
                symbol=symbol,
                qty=float(alpaca_position.qty),
                entry_price=float(alpaca_position.avg_entry_price),
                current_price=price,
                high_water_mark=high_water_mark,
                pl_pct=float(alpaca_position.unrealized_plpc) if alpaca_position.unrealized_plpc else 0.0,
                side=OrderSide.BUY if float(alpaca_position.qty) > 0 else OrderSide.SELL,
            )

    except Exception as e:
        logger.error(f"Error updating position {symbol}: {str(e)}", exc_info=True)


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

        existing_position = get_position_by_symbol_and_strategy(symbol, strategy)

        update_position(
            symbol=symbol,
            strategy=strategy,
            existing_position=existing_position,
        )
        logger.info(f"Updated position for ticker: {symbol} - Strategy: {strategy} ({side})")

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
