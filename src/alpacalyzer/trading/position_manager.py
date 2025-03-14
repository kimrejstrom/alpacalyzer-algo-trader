import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

from alpaca.trading.enums import OrderSide, OrderStatus, QueryOrderStatus, TimeInForce
from alpaca.trading.models import Order, TradeAccount
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from dotenv import load_dotenv

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.db.db import (
    get_strategy_positions,
    remove_position,
    update_prices,
)
from alpacalyzer.trading.alpaca_client import get_account_info, get_market_status, log_order, trading_client
from alpacalyzer.utils.logger import logger


class Position:
    def __init__(self, symbol, qty, entry_price, high_water_mark, side, entry_time):
        self.symbol = symbol
        self.qty = float(qty)
        self.entry_price = float(entry_price)
        self.side = side
        self.entry_time = entry_time
        self.pl_pct = 0.0  # Current P&L percentage
        self.current_price = float(entry_price)
        self.high_water_mark = float(high_water_mark)  # Track highest price reached

    def update_pl(self, current_price):
        """Update position P&L and high water mark."""
        self.current_price = float(current_price)
        multiplier = 1 if self.side == OrderSide.BUY else -1
        self.pl_pct = ((self.current_price / self.entry_price) - 1) * multiplier

        # Update high water mark if price is higher
        if self.current_price > self.high_water_mark:
            self.high_water_mark = self.current_price

        # Calculate drawdown from high
        self.drawdown = ((self.current_price / self.high_water_mark) - 1) * 100
        update_prices("day", self.symbol, self.current_price, self.high_water_mark, self.pl_pct)

    def get_exposure(self, equity: float):
        """Calculate position exposure as percentage of equity."""
        position_value = abs(self.qty * self.current_price)
        return position_value / equity

    def __str__(self):
        return f"{self.symbol}: {self.qty} shares @ ${self.entry_price:.2f} ({self.pl_pct:.1%} P&L)"


class PositionManager:
    def __init__(self, max_position_size=0.05, max_total_exposure=0.5, strategy="day"):
        load_dotenv()
        self.technical_analyzer = TechnicalAnalyzer()
        self.positions: dict[str, Position] = {}  # symbol -> Position object
        self.pending_closes = set()  # Symbols with pending close orders
        self.pending_orders = []  # List of pending new position orders
        self.exited_positions = {}  # Stores exit reasons
        self.strategy = strategy

        # Position sizing parameters
        self.max_position_size = max_position_size  # 5% of equity per trade
        self.max_total_exposure = max_total_exposure  # 50% of equity total exposure
        self.total_exposure = 0  # Current total exposure

        # Total exposure
        self.get_total_exposure()

    def show_status(self):
        """
        Show position manager status.

        Logs the current portfolio status including active positions,
        total exposure, pending close orders, and pending new orders.
        """
        active_positions = {s: p for s, p in self.positions.items() if s not in self.pending_closes}
        logger.info(
            f"\nCurrent Portfolio Status: {len(active_positions)} active positions for {self.strategy} strategy"
        )
        logger.info(f"Total Exposure: {self.get_total_exposure():.1%}")

        for pos in active_positions.values():
            exposure = pos.get_exposure(get_account_info()["equity"])
            age_hours = (datetime.now(UTC) - pos.entry_time).total_seconds() / 3600
            age_str = f"{age_hours:.1f}h" if age_hours < 24 else f"{age_hours / 24:.1f}d"
            logger.info(
                f"{pos} now @ ${pos.current_price:.2f} "
                f"({exposure:.1%} exposure, {age_str} old, {pos.drawdown:.1f}% from high)"
            )

        if self.pending_closes:
            logger.info("\nPending Close Orders:")
            for symbol in self.pending_closes:
                logger.info(f"- {symbol}")

        if self.pending_orders:
            logger.info("\nPending New Orders:")
            for order in self.pending_orders:
                logger.info(f"- {order['symbol']} ({order['side']})")

    def get_total_exposure(self):
        """Calculate current total exposure."""
        account = get_account_info()
        active_positions = {s: p for s, p in self.positions.items() if s not in self.pending_closes}
        self.total_exposure = sum(p.get_exposure(account["equity"]) for p in active_positions.values())
        return self.total_exposure

    def update_pending_orders(self):
        """Update list of pending orders, removing executed ones."""
        try:
            # Get all open orders
            orders = trading_client.get_orders()
            orders_instance = cast(list[Order], orders)

            # Filter only pending orders where order ID contains strategy name
            filtered_orders = [
                order
                for order in orders_instance
                if order.status in ["new", "accepted", "pending"] and self.strategy in order.client_order_id.lower()
            ]

            # Clear old pending orders
            self.pending_orders = []

            # Current time in UTC
            now = datetime.now(UTC)

            # Only track orders that are still pending
            for order in filtered_orders:
                order_age = now - order.submitted_at
                if order_age > timedelta(minutes=5):
                    # Cancel the order if it's older than 5 minutes
                    trading_client.cancel_order_by_id(order.id)
                    logger.info(f"Cancelled pending BUY order for {order.symbol} due to timeout.")
                else:
                    self.pending_orders.append(
                        {
                            "symbol": order.symbol,
                            "shares": float(order.qty) if order.qty else 0,
                            "side": order.side,
                            "order_id": order.id,
                        }
                    )

        except Exception as e:
            logger.error(f"Error updating orders: {str(e)}", exc_info=True)

    def update_positions(self, show_status=True) -> dict[str, Position]:
        """
        Update position tracking with current market data.

        Args:
            show_status: Whether to print current portfolio status
        """
        try:
            # Get fresh positions from Alpaca
            alpaca_positions_response = trading_client.get_all_positions()
            alpaca_positions = cast(list[AlpacaPosition], alpaca_positions_response)
            alpaca_symbols = {p.symbol for p in alpaca_positions}
            logger.info(f"Current Alpaca positions: {len(alpaca_positions)}")

            # Retrieve all selected strategy positions from the DB
            db_strategy_rows = get_strategy_positions(self.strategy)
            db_strategy_positions = {row["symbol"]: row for row in db_strategy_rows}

            # Remove positions from the DB that no longer exist in Alpaca
            for symbol in db_strategy_positions:
                if symbol not in alpaca_symbols:  # Only remove if it's missing in Alpaca
                    logger.info(f"Removing stale position from DB: {symbol}")
                    remove_position(symbol, self.strategy)

            current_symbols = set()
            for p in alpaca_positions:
                symbol = p.symbol
                if symbol in db_strategy_positions.keys():
                    current_symbols.add(symbol)
                    db_record = db_strategy_positions[symbol]

                    qty = float(p.qty)
                    current_price = float(p.current_price) if p.current_price else 0.0
                    entry_price = float(db_record["entry_price"])
                    entry_time = datetime.fromisoformat(db_record["entry_time"])
                    # Use the higher of the DB high water mark or the fresh current price
                    high_water_mark = max(float(db_record["high_water_mark"]), current_price)
                    side = OrderSide.BUY if qty > 0 else OrderSide.SELL

                    # Update in-memory positions
                    if symbol not in self.positions:
                        self.positions[symbol] = Position(symbol, qty, entry_price, high_water_mark, side, entry_time)
                    self.positions[symbol].update_pl(current_price)

            # Remove positions that are no longer active in Alpaca
            for symbol in list(self.positions.keys()):
                if symbol not in current_symbols:
                    self.positions.pop(symbol)

            if show_status:
                self.show_status()

            return self.positions

        except Exception as e:
            logger.error(f"Error updating positions: {str(e)}", exc_info=True)
            return {}

    def calculate_target_position(
        self,
        symbol: str,
        price: float,
        technical_data: TradingSignals,
    ) -> tuple[int, bool]:
        """
        Calculate target position size considering risk factors.

        Args:
            symbol: Stock symbol
            price: Current price
            side: OrderSide.BUY or OrderSide.SELL
            target_pct: Base target size as % of equity (e.g. 0.08 for 8%)
            technical_data: Technical analysis data
            sentiment_data: Social sentiment data
        Returns target shares and whether to allow the trade
        """
        account_resp = trading_client.get_account()
        account = cast(TradeAccount, account_resp)
        equity = float(account.equity or 0)

        # Calculate current total exposure excluding pending closes
        active_positions = {s: p for s, p in self.positions.items() if s not in self.pending_closes}
        total_exposure = sum(p.get_exposure(equity) for p in active_positions.values())

        # Check if we're already at max exposure
        if total_exposure >= self.max_total_exposure:
            logger.info(f"HOLD: Maximum total exposure reached: {self.total_exposure:.1%}")
            return 0, False

        # Start with base position size
        position_size = self.max_position_size

        # Adjust size based on technical strength (0.7 to 1.0 multiplier)
        if technical_data and self.strategy == "day":
            tech_multiplier = max(0.7, technical_data["score"])
            position_size *= tech_multiplier

        # Calculate value with adjusted size
        target_position_value = equity * position_size
        current_position = active_positions.get(symbol)

        if current_position and self.strategy == "day":
            # Position exists - check if we should add more
            current_exposure = current_position.get_exposure(equity)

            # Don't add if already at target size
            if current_exposure >= position_size:
                logger.info(f"HOLD: Target position size reached for {symbol}: {current_exposure:.1%}")
                return 0, False

            # Don't add if position moving against us
            if current_position.pl_pct < -0.02:  # -2% loss threshold
                logger.info(f"HOLD: Position moving against us: {current_position.pl_pct:.1%} P&L")
                return 0, False

            # Calculate remaining size to reach target
            remaining_size = target_position_value - (current_position.qty * price)
            return int(remaining_size / price), True

        # New position - use full target size
        target_shares = int(target_position_value / price)
        return target_shares, True

    def place_limit_order(self, symbol: str, shares: int, limit_price: float, side=OrderSide.BUY):
        """Place a limit order."""
        if shares <= 0 or limit_price is None:
            return None

        order_details = LimitOrderRequest(
            symbol=symbol,
            qty=shares,
            side=side,
            limit_price=limit_price,
            time_in_force=TimeInForce.DAY,
            extended_hours=True,  # Allow after-hours trading
            client_order_id=f"day_{symbol}_{side}_{uuid.uuid4()}",
        )

        try:
            # Place order and track status
            order_response = trading_client.submit_order(order_details)
            order = cast(Order, order_response)
            if order.status in ["new", "accepted", "pending"]:
                self.pending_orders.append(
                    {
                        "symbol": symbol,
                        "shares": shares,
                        "side": side,
                        "order_id": order.id,
                    }
                )
                logger.info(f"Limit order ({side}) queued: {shares} shares of {symbol} at ${limit_price:.2f}")
            else:
                logger.info(f"Limit Order ({side}) executed: {shares} shares of {symbol} at ${limit_price:.2f}")
            log_order(order)
            return order
        except Exception as e:
            logger.error(f"Error placing limit order ({side}): {str(e)}", exc_info=True)
            return None

    def place_market_order(self, symbol: str, shares: int, side=OrderSide.BUY) -> Order | None:
        """Place a market order."""
        if shares <= 0:
            return None

        order_details = MarketOrderRequest(
            symbol=symbol,
            qty=shares,
            side=side,
            time_in_force=TimeInForce.DAY,
            client_order_id=f"day_{symbol}_{side}_{uuid.uuid4()}",
        )

        try:
            # Place order and track status
            order_response = trading_client.submit_order(order_details)
            order = cast(Order, order_response)
            account_info = get_account_info()
            if order.status in ["new", "accepted", "pending"]:
                self.pending_orders.append(
                    {
                        "symbol": symbol,
                        "shares": shares,
                        "side": side,
                        "order_id": order.id,
                    }
                )
                # Calculate position size as % of equity
                # Use first available price
                order_price = None
                for price_field in [
                    order.filled_avg_price,
                    order.limit_price,
                    order.notional,
                ]:
                    if price_field is not None:
                        order_price = float(price_field)
                        break

                if order_price is None:
                    logger.info(f"Market order queued: {shares} shares of {symbol}")
                else:
                    position_value = shares * order_price
                    position_pct = (position_value / account_info["equity"]) * 100
                    logger.info(f"Market order queued: {shares} shares of {symbol} ({position_pct:.1f}% position)")
            else:
                # Calculate executed position size if price available
                if order.filled_avg_price:
                    position_value = shares * float(order.filled_avg_price)
                    position_pct = (position_value / account_info["equity"]) * 100
                    logger.info(f"Market order executed: {shares} shares of {symbol} ({position_pct:.1f}% position)")
                else:
                    logger.info(f"Market order executed: {shares} shares of {symbol}")
            log_order(order)
            return order
        except Exception as e:
            logger.error(f"Error placing order: {str(e)}", exc_info=True)
            return None

    def close_position(self, symbol: str):
        """Close an existing position."""
        # Skip if already pending close or shares held
        if symbol in self.pending_closes:
            logger.info(f"Skipping {symbol} - close order already pending")
            return None

        try:
            try:
                # Get fresh position from Alpaca
                alpaca_resp = trading_client.get_open_position(symbol)
                alpaca_position = cast(AlpacaPosition, alpaca_resp)
            except Exception as e:
                logger.warning(f"Error fetching position for {symbol}: {str(e)}", exc_info=True)
                return None

            if int(alpaca_position.qty_available if alpaca_position.qty_available else 0) == 0:
                logger.info(f"Canceling open sell orders for {symbol} before replacing...")

                # Get open orders for the symbol
                request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
                open_orders = cast(list[Order], trading_client.get_orders(request_params))

                # Cancel all open sell orders
                for order in open_orders:
                    if order.side == OrderSide.SELL:
                        logger.info(f"Canceling order {order.id} for {symbol}")
                        trading_client.cancel_order_by_id(order.id)
                        time.sleep(0.5)  # Small delay to ensure cancellation propagates

                logger.info(f"All open sell orders for {symbol} canceled. Ready to place new orders.")

            market_session = get_market_status()
            if market_session == "open":
                order_response = trading_client.close_position(symbol)
                order = cast(Order, order_response)
                if order.status == OrderStatus.ACCEPTED:
                    self.pending_closes.add(symbol)
                    logger.info(f"Close order queued: {symbol}")
                    log_order(order)
            else:
                order_response = self.place_limit_order(
                    symbol,
                    abs(int(float(alpaca_position.qty))),
                    round(float(alpaca_position.current_price if alpaca_position.current_price else 0) * 0.995, 2),
                    OrderSide.SELL,
                )
                order = cast(Order, order_response)
                if order.status == OrderStatus.ACCEPTED:
                    self.pending_closes.add(symbol)
                    logger.info(f"Close order queued: {symbol}")
                    log_order(order)

        except Exception as e:
            logger.error(f"Error closing position {symbol}: {str(e)}", exc_info=True)
            return None

    def get_limit_price(self, side: OrderSide, technical_data: TradingSignals) -> float | None:
        """
        Calculate a dynamic limit price based on RVOL, ATR, and technical indicators.

        Args:
            symbol (str): The stock ticker.
            side (OrderSide): BUY or SELL.

        Returns:
            float: The calculated limit price.
        """
        market_session = get_market_status()
        intraday_df = technical_data["raw_data_intraday"]
        if intraday_df is None or intraday_df.empty:
            return None

        latest = intraday_df.iloc[-2]
        rvol = float(latest.get("RVOL", 1))  # Default to 1 if RVOL isn't available
        atr = float(latest["ATR"])
        vwap = float(latest["vwap"])
        close_price = float(intraday_df.iloc[-1]["close"])
        bb_lower = float(latest["BB_Lower"])
        bb_upper = float(latest["BB_Upper"])

        # ATR multiplier based on market session
        atr_multiplier = 0.5 if market_session == "open" else 1.0  # Wider buffer for pre/post-market

        # Adjust ATR multiplier based on RVOL to make it dynamic
        rvol_factor = max(1, rvol)  # Ensure RVOL doesn't reduce the multiplier below 1
        atr_adjusted = atr * atr_multiplier * (1 + (rvol_factor - 1) * 0.2)  # Scale ATR by RVOL

        if side == OrderSide.BUY:
            # Dynamic limit price for buying
            limit_price = max(bb_lower, vwap, close_price - atr_adjusted)
        elif side == OrderSide.SELL:
            # Dynamic limit price for selling
            limit_price = min(bb_upper, vwap, close_price + atr_adjusted)
        else:
            return None

        if limit_price >= 1.00:
            return round(limit_price, 2)  # Round to nearest cent ($0.01 increments)
        return round(limit_price, 4)  # Round to nearest $0.0001 for stocks under $1.00
