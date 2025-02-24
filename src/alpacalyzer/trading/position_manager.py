import time
from datetime import UTC, datetime
from typing import cast

import pandas as pd
from alpaca.trading.enums import OrderSide, OrderStatus, QueryOrderStatus, TimeInForce
from alpaca.trading.models import Order, TradeAccount
from alpaca.trading.models import Position as AlpacaPosition
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from dotenv import load_dotenv

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.scanners.social_scanner import SocialScanner
from alpacalyzer.trading.alpaca_client import get_market_status, trading_client
from alpacalyzer.utils.logger import logger


class Position:
    def __init__(self, symbol, qty, entry_price, side, entry_time):
        self.symbol = symbol
        self.qty = float(qty)
        self.entry_price = float(entry_price)
        self.side = side
        self.entry_time = entry_time
        self.target_qty = float(qty)  # For gradual position building/reduction
        self.pl_pct = 0.0  # Current P&L percentage
        self.current_price = float(entry_price)
        self.high_water_mark = float(entry_price)  # Track highest price reached
        self.technical_data = None  # Technical analysis data

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

    def update_ta(self, technical_data: TradingSignals):
        """Update position with technical analysis data."""
        self.technical_data = technical_data

    def get_exposure(self, equity: float):
        """Calculate position exposure as percentage of equity."""
        position_value = abs(self.qty * self.current_price)
        return position_value / equity

    def __str__(self):
        return f"{self.symbol}: {self.qty} shares @ ${self.entry_price:.2f} ({self.pl_pct:.1%} P&L)"


class PositionManager:
    def __init__(self):
        load_dotenv()
        self.social_scanner = SocialScanner()
        self.technical_analyzer = TechnicalAnalyzer()
        self.positions: dict[str, Position] = {}  # symbol -> Position object
        self.pending_closes = set()  # Symbols with pending close orders
        self.pending_orders = []  # List of pending new position orders
        self.exited_positions = {}  # Stores exit reasons

        # Position sizing parameters
        self.max_position_size = 0.05  # 5% max per position
        self.position_step_size = 0.02  # 2% per trade for gradual building
        self.max_total_exposure = 0.5  # 50% total exposure limit
        self.total_exposure = 0  # Current total exposure

        # Total exposure
        self.get_total_exposure()

        # Initialize current positions and pending orders
        self.update_positions()
        self.update_pending_orders()

    def get_total_exposure(self):
        """Calculate current total exposure."""
        account = self.get_account_info()
        active_positions = {s: p for s, p in self.positions.items() if s not in self.pending_closes}
        self.total_exposure = sum(p.get_exposure(account["equity"]) for p in active_positions.values())
        return self.total_exposure

    def update_pending_orders(self):
        """Update list of pending orders, removing executed ones."""
        try:
            # Get all open orders
            orders = trading_client.get_orders()
            orders_instance = cast(list[Order], orders)

            # Clear old pending orders
            self.pending_orders = []

            # Only track orders that are still pending
            for order in orders_instance:
                if order.status in ["new", "accepted", "pending"]:
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

    def get_account_info(self):
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

    def update_positions(self, show_status=True) -> dict[str, Position]:
        """
        Update position tracking with current market data.

        Args:
            show_status: Whether to print current portfolio status
        """
        try:
            alpaca_positions = trading_client.get_all_positions()
            positions = cast(list[AlpacaPosition], alpaca_positions)
            current_symbols = set()

            # Update existing positions and add new ones
            for p in positions:
                symbol = p.symbol
                current_symbols.add(symbol)
                qty = float(p.qty)
                current_price = float(p.current_price) if p.current_price else 0
                entry_price = float(p.avg_entry_price)
                side = OrderSide.BUY if qty > 0 else OrderSide.SELL

                # Try to find original order time
                try:
                    req = GetOrdersRequest(
                        status=QueryOrderStatus.CLOSED,
                        symbols=[symbol],
                        side=side,
                        limit=1,
                        nested=True,  # Include nested orders
                    )
                    orders = trading_client.get_orders(req)
                    order_list = cast(list[Order], orders)
                    if order_list:
                        # Get earliest filled order
                        entry_time = min(order.filled_at for order in order_list if order.filled_at)
                    else:
                        entry_time = datetime.now(UTC)
                except Exception:
                    entry_time = datetime.now(UTC)

                if symbol not in self.positions:
                    # New position with stored entry time
                    self.positions[symbol] = Position(symbol, qty, entry_price, side, entry_time)

                # Update position data
                pos = self.positions[symbol]
                pos.qty = qty
                pos.entry_price = entry_price
                pos.update_pl(current_price)

            # Remove closed positions and their times
            closed_positions = set(self.positions.keys()) - current_symbols
            for symbol in closed_positions:
                self.positions.pop(symbol)

            # Update positions dict
            self.positions = {s: p for s, p in self.positions.items() if s in current_symbols}
            active_positions = {s: p for s, p in self.positions.items() if s not in self.pending_closes}

            if show_status:
                logger.info(f"\nCurrent Portfolio Status: {len(active_positions)} active positions")
                logger.info(f"Total Exposure: {self.get_total_exposure():.1%}")
                for pos in active_positions.values():
                    exposure = pos.get_exposure(self.get_account_info()["equity"])
                    age_hours = (datetime.now(UTC) - pos.entry_time).total_seconds() / 3600
                    age_str = f"{age_hours:.1f}h" if age_hours < 24 else f"{age_hours / 24:.1f}d"
                    logger.info(
                        f"{pos} now @ ${pos.current_price:.2f}"
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

            return self.positions

        except Exception as e:
            logger.error(f"Error updating positions: {str(e)}", exc_info=True)
            return {}

    def calculate_target_position(
        self,
        symbol,
        price,
        side,
        target_pct=None,
        technical_data=None,
        sentiment_data=None,
    ):
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
        account = self.get_account_info()
        equity = account["equity"]

        # Calculate current total exposure excluding pending closes
        active_positions = {s: p for s, p in self.positions.items() if s not in self.pending_closes}
        total_exposure = sum(p.get_exposure(equity) for p in active_positions.values())

        # Check if we're already at max exposure
        if total_exposure >= self.max_total_exposure:
            logger.info(f"HOLD: Maximum total exposure reached: {self.total_exposure:.1%}")
            return 0, False

        # Start with base position size
        position_size = target_pct if target_pct is not None else self.max_position_size

        # Adjust size based on technical strength (0.7 to 1.0 multiplier)
        if technical_data:
            tech_multiplier = max(0.4, technical_data["score"])
            position_size *= tech_multiplier

        # Adjust for sentiment strength if available
        if sentiment_data:
            # Higher rank = smaller size
            rank_multiplier = max(0.5, 1.0 - (sentiment_data["final_rank"] / 40))
            position_size *= rank_multiplier

        # Calculate value with adjusted size
        target_position_value = equity * position_size
        current_position = active_positions.get(symbol)

        if current_position:
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

    def should_close_position(self, symbol: str, technical_data: TradingSignals, top_stocks: pd.DataFrame):
        """Determine if a position should be closed based on technical analysis."""
        position = self.positions.get(symbol)
        if not position:
            return False

        signals = technical_data["signals"]
        momentum = technical_data["momentum"]
        score = technical_data["score"]
        atr = technical_data["atr"]

        # Close if any of these conditions are met:
        exit_signals = []

        # 0. Market open protection logic
        position_age_mins = (datetime.now(UTC) - position.entry_time).total_seconds() / 60
        if position_age_mins < 30:  # 30-min protection period
            # Only exit if:
            # 1. Hard stop hit (-10% from entry)
            if position.pl_pct < -0.1:
                exit_signals.append(f"Hard stop: {position.pl_pct:.1f}% loss")

            # 2. Big profit + reversal (lock in gains)
            if position.pl_pct > 0.075 and position.drawdown < -5:
                exit_signals.append(
                    f"Profit lock: {position.drawdown:.1f}% drop from high while +{position.pl_pct:.1f}% up"
                )

        # 1. Adaptive ATR-based dynamic stop-loss
        if atr:
            hard_stop_price = position.entry_price - (atr * 2)  # Example: 2x ATR as stop-loss
            trailing_stop_price = position.high_water_mark - (atr * 2)
            if position.current_price <= hard_stop_price:
                exit_signals.append(f"ATR-based hard stop: {position.current_price} <= {hard_stop_price}")
            elif position.current_price <= trailing_stop_price:
                exit_signals.append(f"ATR-based trailing stop: {position.current_price} <= {trailing_stop_price}")

        # 1. Significant loss
        if position.pl_pct < -0.05:  # -5% stop loss
            exit_signals.append(f"Stop loss hit: {position.pl_pct:.1%} P&L")

        # 2. Protect Profits - Tighten stops as profit grows
        if position.pl_pct > 0.10:  # In +10% profit
            if position.drawdown < -5:  # Tighter 5% trailing stop
                exit_signals.append(
                    f"Profit protection: {position.drawdown:.1%}% drop from high while +{position.pl_pct:.1%}% up"
                )
        elif position.drawdown < -7.5:  # Normal 7.5% trailing stop
            exit_signals.append(f"Trailing stop: {position.drawdown:.1%}% from high")

        # 2. Quick Momentum Shifts - Only exit if significant drop
        if momentum < -5 and position.pl_pct > 0:  # Need profit to use quick exit
            if position.pl_pct > 0.05:  # Need 5% profit to use quick exit
                exit_signals.append(f"Momentum reversal: {momentum:.1f}% drop while +{position.pl_pct:.1%}% up")

        # 3. Technical Weakness
        if score < 0.6:  # Weak technical score
            weak_tech_signals = self.technical_analyzer.weak_technicals(signals)
            # Only exit on technical weakness if multiple signals
            if weak_tech_signals is not None:
                exit_signals.append(weak_tech_signals)

        # 5. Mediocre performance with significant age
        position_age = (datetime.now(UTC) - position.entry_time).days
        if position_age > 1:  # At least 1 day old
            if (
                score < 0.6  # Weaker technicals
                and abs(position.pl_pct) < 0.03  # Little movement
                and symbol not in top_stocks["ticker"].values  # Not in top 15
            ):
                exit_signals.append(f"Stale position ({position_age:.1f}h old, weak technicals and not in top 15)")

        if position_age > 3 and abs(position.pl_pct) < 0.01:
            exit_signals.append(f"Stagnant position after {position_age} days")

        # Check if any exit signals triggered
        if exit_signals:
            reason_str = ", ".join(exit_signals)
            # Store exit reason to block immediate re-entry
            self.exited_positions[symbol] = {
                "reason": reason_str,
                "timestamp": datetime.now(UTC),
            }
            logger.info(f"\nSELL {symbol} due to: {reason_str}")
            logger.info(f"Position details: {position}")
            if position.technical_data:
                logger.debug(
                    f"Technical signals Daily at SELL: {position.technical_data['raw_data_daily'].to_string()}"
                )
                logger.debug(
                    f"Technical signals Intraday at SELL: {position.technical_data['raw_data_intraday'].to_string()}"
                )
            if position.pl_pct < 0:
                logger.info(f"LOSS: {position.pl_pct:.1%} P&L loss on trade")
            else:
                logger.info(f"WIN: {position.pl_pct:.1%} P&L gain on trade")
            return True

        return False

    def handle_over_exposure(self):
        # Get rankings for current positions
        tickers_list = list(self.positions.keys())
        ranked_stocks = self.social_scanner.rank_stocks(tickers_list, limit=len(tickers_list))

        # add position.pl_pct to the ranked_stocks
        for symbol, position in self.positions.items():
            ranked_stocks.loc[ranked_stocks["ticker"] == symbol, "pl_pct"] = position.pl_pct

        # Sort ranked_stocks by final_rank and pl_pct (negative is worst)
        # in descending order to sell the worst-ranked positions first
        ranked_stocks = ranked_stocks.sort_values(by=["final_rank", "pl_pct"], ascending=[False, False])

        logger.debug("\nSorted Positions:")
        for _, row in ranked_stocks.iterrows():
            logger.debug(f"{row['ticker']}: Rank {row['final_rank']:.2f}, P&L: {row['pl_pct']:.1%}")

        # Calculate over-exposure
        over_exposure = self.get_total_exposure() - self.max_total_exposure
        account = self.get_account_info()

        # Iterate through the worst-ranked positions until over_exposure is resolved
        for _, row in ranked_stocks.iterrows():
            # Get the current position for the ticker
            current_position = self.positions.get(row["ticker"])

            if current_position is not None:  # Ensure the position exists
                position_exposure = current_position.get_exposure(account["equity"])  # Get the exposure of the position
                logger.info(
                    f"SELL {row['ticker']} due to: Over exposure - sell worst-ranked positions"
                    f" (Rank {row['final_rank']:.1f})."
                )

                # Close the position
                self.close_position(row["ticker"])

                # Reduce exposure
                over_exposure -= position_exposure

                # Exit loop if over-exposure is resolved
                if over_exposure <= 0:
                    break

        # Log remaining over-exposure if applicable
        if over_exposure > 0:
            logger.info(f"Warning: Over-exposure of {over_exposure} remains after selling positions.")
        else:
            logger.info("Successfully resolved over-exposure.")

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
            return order
        except Exception as e:
            logger.error(f"Error placing limit order ({side}): {str(e)}", exc_info=True)
            return None

    def place_market_order(self, symbol: str, shares: int, side=OrderSide.BUY):
        """Place a market order."""
        if shares <= 0:
            return None

        order_details = MarketOrderRequest(symbol=symbol, qty=shares, side=side, time_in_force=TimeInForce.DAY)

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
                # Calculate position size as % of equity
                account_info = self.get_account_info()
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
                account_info = self.get_account_info()
                if order.filled_avg_price:
                    position_value = shares * float(order.filled_avg_price)
                    position_pct = (position_value / account_info["equity"]) * 100
                    logger.info(f"Market order executed: {shares} shares of {symbol} ({position_pct:.1f}% position)")
                else:
                    logger.info(f"Market order executed: {shares} shares of {symbol}")

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
            # Get current position
            position_response = trading_client.get_open_position(symbol)
            position = cast(AlpacaPosition, position_response)

            if not position:
                logger.warning("Position not found")
                return None

            if int(position.qty_available if position.qty_available else 0) == 0:
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
                    logger.debug(f"Close order details: {order}")
            else:
                order_response = self.place_limit_order(
                    symbol,
                    abs(int(float(position.qty))),
                    round(float(position.current_price if position.current_price else 0) * 0.995, 2),
                    OrderSide.SELL,
                )
                order = cast(Order, order_response)
                if order.status == OrderStatus.ACCEPTED:
                    self.pending_closes.add(symbol)
                    logger.info(f"Close order queued: {symbol}")
                    logger.debug(f"Close order details: {order}")

        except Exception as e:
            logger.error(f"Error closing position {symbol}: {str(e)}", exc_info=True)
            return None

    def get_limit_price(self, symbol: str, side: OrderSide) -> float | None:
        """
        Calculate a dynamic limit price based on RVOL, ATR, and technical indicators.

        Args:
            symbol (str): The stock ticker.
            side (OrderSide): BUY or SELL.

        Returns:
            float: The calculated limit price.
        """
        market_session = get_market_status()
        intraday_df = self.technical_analyzer.analyze_stock_intraday(symbol)
        if intraday_df is None or intraday_df.empty:
            return None

        latest = intraday_df.iloc[-1]
        rvol = float(latest.get("RVOL", 1))  # Default to 1 if RVOL isn't available
        atr = float(latest["ATR"])
        vwap = float(latest["vwap"])
        close_price = float(latest["close"])
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
