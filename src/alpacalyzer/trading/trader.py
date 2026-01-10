import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal, cast

import pandas as pd
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.models import Asset, Order, Position
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.data.models import EntryType, TopTicker, TradingStrategy
from alpacalyzer.hedge_fund import call_hedge_fund_agents
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.scanners.social_scanner import SocialScanner
from alpacalyzer.trading.alpaca_client import get_market_status, get_positions, log_order, trading_client
from alpacalyzer.trading.opportunity_finder import (
    get_reddit_insights,
    get_top_candidates,
)
from alpacalyzer.trading.yfinance_client import YFinanceClient
from alpacalyzer.utils.display import print_strategy_output, print_trading_output
from alpacalyzer.utils.logger import get_logger

if TYPE_CHECKING:
    from alpacalyzer.execution.signal_queue import PendingSignal

logger = get_logger()


class Trader:
    def __init__(self, analyze_mode=False, direct_tickers=None, agents: Literal["ALL", "TRADE", "INVEST"] = "ALL", ignore_market_status=False):
        """Initialize the Trader instance."""
        self.technical_analyzer = TechnicalAnalyzer()
        self.finviz_scanner = FinvizScanner()
        self.yfinance_client = YFinanceClient()
        self.social_scanner = SocialScanner()
        self.latest_strategies: list[TradingStrategy] = []
        self.opportunities: list[TopTicker] = []
        self.market_status = get_market_status()
        self.analyze_mode = analyze_mode
        self.direct_tickers = direct_tickers or []
        self.agents: Literal["ALL", "TRADE", "INVEST"] = agents
        self.recently_exited_tickers: dict[str, datetime] = {}
        self.cooldown_period = timedelta(hours=3)
        self.ignore_market_status = ignore_market_status

        if self.ignore_market_status:
            self.is_market_open = True
            logger.info("Market status checks are ignored.")
        else:
            self.is_market_open = self.market_status == "open"

    def scan_for_insight_opportunities(self):
        if not self.is_market_open:
            logger.info(f"=== Reddit Scanner Paused - Market Status: {self.market_status} ===")
            return None

        logger.info(f"\n=== Reddit Scanner Starting - Market Status: {self.market_status} ===")

        try:
            reddit_insights = get_reddit_insights()
            reddit_picks = reddit_insights.top_tickers if reddit_insights else []
            reddit_tickers = [x.ticker for x in reddit_picks]
            top_tickers = list(set(reddit_tickers))
            input_ta_df = self.finviz_scanner.fetch_stock_data(tuple(top_tickers))
            top_candidates = get_top_candidates(reddit_picks, input_ta_df)
            opportunities = top_candidates.top_tickers if top_candidates else []

            for opportunity in opportunities:
                if opportunity.ticker not in [o.ticker for o in self.opportunities]:
                    self.opportunities.append(opportunity)

        except Exception as e:
            logger.error(f"Error in scan_for_insight_opportunities: {str(e)}", exc_info=True)

    def scan_for_technical_opportunities(self):
        """Main trading loop."""

        if not self.ignore_market_status:
            self.market_status = get_market_status()
            self.is_market_open = self.market_status == "open"

        if not self.is_market_open:
            logger.info(f"=== Momentum Scanner Paused - Market Status: {self.market_status} ===")
            return

        logger.info(f"\n=== Momentum Scanner Starting - Market Status: {self.market_status} ===")

        try:
            # Get ranked stocks
            trending_stocks = self.social_scanner.get_trending_stocks(10)

            # Get VIX
            vix_close = self.yfinance_client.get_vix()

            if trending_stocks.empty:
                return

            # Get technical analysis for each stock
            for _, stock in trending_stocks.iterrows():
                entry_blockers = []
                trading_signals = cast(TradingSignals, stock["trading_signals"])

                if not isinstance(trading_signals, dict):
                    logger.info(f"Skipping {stock['ticker']} - No trading signals")
                    continue

                # Check technicals
                signals = trading_signals["signals"]
                momentum = trading_signals["momentum"]

                atr_pct = trading_signals["atr"] / trading_signals["price"]
                ta_threshold = self.technical_analyzer.calculate_ta_threshold(
                    vix_close,
                    trading_signals["rvol"],
                    atr_pct,
                )

                if trading_signals["score"] < ta_threshold:
                    entry_blockers.append(f"Technical data too weak: {trading_signals['score']:.2f} < {ta_threshold:.2f}")

                # Check for conflicting signals
                if momentum < 0 and stock["sentiment_rank"] > 20:
                    entry_blockers.append("Conflicting momentum and sentiment signals.")

                if momentum < -3:
                    entry_blockers.append(f"Weak momentum {momentum:.1f}%")

                # Only allow weaker setups if breakout pattern detected
                if 15 < vix_close < 30 and trading_signals["score"] < 0.8 and not any("TA: Breakout" in signal for signal in signals):
                    entry_blockers.append("No breakout pattern detected")

                # 3. Technical Weakness
                weak_tech_signals = self.technical_analyzer.weak_technicals(signals, OrderSide.BUY)
                if weak_tech_signals is not None:
                    entry_blockers.append(f"{weak_tech_signals}")

                if entry_blockers:
                    logger.debug(f"Entry blocked for {stock['ticker']}:")
                    for blocker in entry_blockers:
                        logger.debug(f"- {blocker}")
                    continue

                # Convert back to signal
                if trading_signals["score"] > 0.8:
                    signal = "bullish"
                elif trading_signals["score"] < 0.5:
                    signal = "bearish"
                else:
                    signal = "neutral"

                opportunity = TopTicker(
                    ticker=stock["ticker"],
                    confidence=75,
                    signal=signal,
                    reasoning=f"Technical Score: {trading_signals['score']:.2f} - {trading_signals['signals']}",
                )

                if opportunity.ticker not in [o.ticker for o in self.opportunities]:
                    self.opportunities.append(opportunity)

        except Exception as e:
            logger.error(f"Error in scan_for_technical_opportunities: {str(e)}", exc_info=True)

    def run_hedge_fund(self):
        """Hedge fund."""

        if not self.is_market_open:
            logger.info(f"=== Hedge Fund Paused - Market Status: {self.market_status} ===")
            return

        logger.info(f"\n=== Hedge Fund Starting - Market Status: {self.market_status} ===")

        # If direct tickers were provided, use those instead of opportunity scanners
        if self.direct_tickers:
            logger.info(f"Using directly provided tickers: {', '.join(self.direct_tickers)}")
            # Clear any existing opportunities and add the direct tickers
            self.opportunities = []
            for ticker in self.direct_tickers:
                self.opportunities.append(
                    TopTicker(
                        ticker=ticker,
                        confidence=50.0,
                        signal="neutral",
                        reasoning="Ticker is of interest to the user.",
                    )
                )

        try:
            if not self.opportunities:
                logger.info("No opportunities available.")
                return

            # Remove tickers from cooldown if the period has passed
            now = datetime.now(UTC)
            for ticker, exit_time in list(self.recently_exited_tickers.items()):
                if now > exit_time + self.cooldown_period:
                    logger.info(f"Ticker {ticker} cooldown finished.")
                    del self.recently_exited_tickers[ticker]

            positions = get_positions()
            active_tickers = [p.symbol for p in positions]
            cooldown_tickers = list(self.recently_exited_tickers.keys())

            filtered_opportunities = [opp for opp in self.opportunities if opp.ticker not in active_tickers and opp.ticker not in cooldown_tickers]

            if not filtered_opportunities:
                logger.info("No new opportunities available to trade (all tickers are active or in cooldown).")
                return

            hedge_fund_response = call_hedge_fund_agents(filtered_opportunities, self.agents, show_reasoning=True)
            print_trading_output(hedge_fund_response)

            if not hedge_fund_response["decisions"] or hedge_fund_response["decisions"] is None:
                logger.info("No trade decisions from hedge fund.")
                return

            # Create trading strategies from hedge fund response
            for data in hedge_fund_response["decisions"].values():
                strategies = data.get("strategies", [])
                for strategy in strategies:
                    strategy = TradingStrategy.model_validate(strategy)
                    if strategy.ticker in [s.ticker for s in self.latest_strategies]:
                        logger.info(f"Strategy already exists for {strategy.ticker} - Skipping")
                        continue
                    self.latest_strategies.append(strategy)

            self.opportunities = []

        except Exception as e:
            logger.error(f"Error in run_hedge_fund: {str(e)}", exc_info=True)

    def get_signals_from_strategies(self) -> list["PendingSignal"]:
        """
        Convert latest_strategies to PendingSignal objects for ExecutionEngine.

        Returns:
            List of PendingSignal objects created from hedge fund strategies.
        """
        from alpacalyzer.execution.signal_queue import PendingSignal

        signals = []
        for strategy in self.latest_strategies:
            signal = PendingSignal.from_strategy(strategy, source="hedge_fund")
            signals.append(signal)

        return signals

    # Function to check real-time price and execute orders
    def monitor_and_trade(self):
        """Monitor positions and trade every X minutes."""

        if not self.is_market_open:
            logger.info(f"=== Trading Monitor Loop Paused - Market Status: {self.market_status} ===")
            return

        logger.info(f"\n=== Trading Monitor Loop Starting - Market Status: {self.market_status} ===")
        logger.info(f"Active Strategies: {len(self.latest_strategies)}")

        executed_tickers: list[str] = []  # Track tickers whose strategies have been executed

        try:
            for strategy in self.latest_strategies[:]:
                logger.debug(f"executed_tickers: {executed_tickers}")
                if strategy.ticker in executed_tickers:
                    continue  # Skip strategies for tickers that already executed

                signals = self.technical_analyzer.analyze_stock(strategy.ticker)
                if signals is None:
                    continue

                logger.info(
                    f"\nChecking strategy for {strategy.ticker} (Current price: {signals['price']}):\n"
                    f"Type: {strategy.trade_type}, Entry: {strategy.entry_point}, "
                    f"Target: {strategy.target_price}, Stop Loss: {strategy.stop_loss}"
                )

                # Check if entry conditions are met
                if check_entry_conditions(strategy, signals):
                    asset_response = trading_client.get_asset(strategy.ticker)
                    asset = cast(Asset, asset_response)

                    if not asset.tradable:
                        logger.info(f"Asset is not tradable {strategy.ticker} - Removing strategy")
                        self.latest_strategies.remove(strategy)
                        continue

                    if strategy.trade_type == "short" and not asset.shortable:
                        logger.info(f"Asset can not be shorted {strategy.ticker} - Removing strategy")
                        self.latest_strategies.remove(strategy)
                        continue

                    print_strategy_output(strategy)

                    # Determine order type
                    side = OrderSide.BUY if strategy.trade_type.lower() == "long" else OrderSide.SELL

                    # Correct rounding for prices
                    def round_price(price):
                        return round(price, 2) if price > 1 else round(price, 4)

                    bracket_order = LimitOrderRequest(
                        symbol=strategy.ticker,
                        qty=strategy.quantity,
                        side=side,
                        type="limit",
                        time_in_force=TimeInForce.GTC,
                        limit_price=round_price(strategy.entry_point),
                        order_class="bracket",
                        stop_loss={"stop_price": round_price(strategy.stop_loss)},
                        take_profit={"limit_price": round_price(strategy.target_price)},
                        client_order_id=f"hedge_{strategy.ticker}_{side}_{uuid.uuid4()}",
                    )
                    # Submit order with bracket structure
                    logger.debug(f"Submitting order: {bracket_order}")
                    order_resp = trading_client.submit_order(bracket_order)
                    order = cast(Order, order_resp)
                    log_order(order)

                    # Mark strategy as executed
                    executed_tickers.append(strategy.ticker)
                    logger.analyze(
                        f"Ticker: {strategy.ticker}, Trade Type: {strategy.trade_type}, Quantity: {strategy.quantity}, "
                        f"Entry Point: {round_price(strategy.entry_point)}, Target Price: {round_price(strategy.target_price)}, "
                        f"Risk/Reward Ratio: {strategy.risk_reward_ratio}, Notes: {strategy.strategy_notes}, "
                        f"ClientOrderId: {order.client_order_id}"
                    )

            # Remove all strategies for executed tickers
            self.latest_strategies = [s for s in self.latest_strategies if s.ticker not in executed_tickers]

        except Exception as e:
            logger.error(f"Error in monitor_and_trade entries: {str(e)}", exc_info=True)

        try:
            positions = get_positions()
            for position in positions:
                if position.symbol in executed_tickers:
                    continue
                signals = self.technical_analyzer.analyze_stock(position.symbol)
                if signals is None:
                    continue
                logger.info(
                    f"\nChecking exit conditions for {position.symbol} (Current price: {position.current_price}):\n"
                    f"Type: {position.side}, Entry: {position.avg_entry_price}, "
                    f"Unrealized P/L:  {float(position.unrealized_plpc or 0.0):.2%}, "
                    f"Market value: ${position.market_value}"
                )
                # Check if exit conditions are met
                if check_exit_conditions(position, signals):
                    # Close position
                    logger.info(f"Closing position for {position.symbol}")

                    try:
                        # 1. Cancel all open orders for this symbol to avoid race conditions with bracket orders.
                        open_orders_resp = trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[position.symbol]))
                        open_orders = cast(list[Order], open_orders_resp)

                        if open_orders:
                            logger.info(f"Found {len(open_orders)} open orders for {position.symbol}. Canceling them.")
                            for o in open_orders:
                                try:
                                    trading_client.cancel_order_by_id(o.id)
                                    logger.info(f"Requested cancellation for order {o.id}")
                                except APIError as e:
                                    if e.code == 42210000:  # PENDING_CANCEL
                                        logger.debug(f"Order {o.id} is already pending cancel.")
                                    elif e.code == 40410000:  # ORDER_NOT_FOUND
                                        logger.debug(f"Order {o.id} not found, likely already canceled or filled.")
                                    else:
                                        # Re-raise the exception if it's an unexpected error.
                                        raise e
                                except Exception as e:
                                    logger.warning(f"An unexpected error occurred while canceling order {o.id}: {e}")

                            # 2. Poll to confirm cancellation. Wait up to 30 seconds.
                            for _ in range(15):
                                time.sleep(2)
                                orders_after_cancel_resp = trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[position.symbol]))
                                if not cast(list[Order], orders_after_cancel_resp):
                                    logger.debug(f"Confirmed all open orders for {position.symbol} are canceled.")
                                    break
                                logger.debug(f"Waiting for order cancellation confirmation for {position.symbol}...")
                            else:
                                logger.error(f"Timed out waiting for order cancellation for {position.symbol}.")
                                continue

                        # 3. Now it's safe to close the position.
                        logger.info(f"Proceeding to close position for {position.symbol}.")
                        order_resp = trading_client.close_position(position.symbol)
                        order = cast(Order, order_resp)
                        log_order(order)
                        self.recently_exited_tickers[position.symbol] = datetime.now(UTC)

                    except Exception as e:
                        logger.error(f"Failed to close position for {position.symbol}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error in monitor_and_trade exits: {str(e)}", exc_info=True)


def check_entry_conditions(strategy: TradingStrategy, signals: TradingSignals) -> bool:
    try:
        # Use 3-candle averages for consistency with exit conditions
        daily_data = signals["raw_data_daily"]
        intraday_data = signals["raw_data_intraday"]

        # Get last 3 candles for averaging - returns Series
        daily_3candle = cast(pd.Series, daily_data.iloc[-3:].mean())
        intraday_3candle = cast(pd.Series, intraday_data.iloc[-3:].mean())

        price = signals["price"]
        rsi = daily_3candle["RSI"]
        sma20 = daily_3candle["SMA_20"]
        sma50 = daily_3candle["SMA_50"]

        # Track met and failed conditions for fuzzy logic
        conditions_met_count = 0
        total_conditions = len(strategy.entry_criteria)
        failed_conditions = []

        for criteria in strategy.entry_criteria:
            condition_met = True

            if criteria.entry_type == EntryType.PRICE_NEAR_SUPPORT:
                # Increased tolerance from 0.5% to 1.5%
                if not criteria.value * (1 - 0.015) <= price <= criteria.value * (1 + 0.015):
                    logger.debug(f"Price near support: {price} +/- 1.5% from {criteria.value}")
                    condition_met = False
            elif criteria.entry_type == EntryType.PRICE_NEAR_RESISTANCE:
                # Increased tolerance from 0.5% to 1.5%
                if not criteria.value * (1 - 0.015) <= price <= criteria.value * (1 + 0.015):
                    logger.debug(f"Price near resistance: {price} +/- 1.5% from {criteria.value}")
                    condition_met = False
            elif criteria.entry_type == EntryType.BREAKOUT_ABOVE and price <= criteria.value:
                logger.debug(f"Breakout above: {price} <= {criteria.value}")
                condition_met = False
            elif criteria.entry_type == EntryType.RSI_OVERSOLD and rsi > criteria.value:
                logger.debug(f"RSI oversold: {rsi} > {criteria.value}")
                condition_met = False
            elif criteria.entry_type == EntryType.RSI_OVERBOUGHT and rsi < criteria.value:
                logger.debug(f"RSI overbought: {rsi} < {criteria.value}")
                condition_met = False
            elif criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_20 and price < sma20:
                logger.debug(f"Price above SMA20: {price} < {sma20}")
                condition_met = False
            elif criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_20 and price > sma20:
                logger.debug(f"Price below SMA20: {price} > {sma20}")
                condition_met = False
            elif criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_50 and price < sma50:
                logger.debug(f"Price above SMA50: {price} < {sma50}")
                condition_met = False
            elif criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_50 and price > sma50:
                logger.debug(f"Price below SMA50: {price} > {sma50}")
                condition_met = False
            elif criteria.entry_type == EntryType.BULLISH_ENGULFING:
                # Accept 80+ confidence instead of exact 100, using 3-candle average
                bullish_engulfing_conf = intraday_3candle["Bullish_Engulfing"]
                if bullish_engulfing_conf < 80:
                    logger.debug(f"Bullish Engulfing not detected (3-candle avg confidence: {bullish_engulfing_conf:.1f})")
                    condition_met = False
            elif criteria.entry_type == EntryType.BEARISH_ENGULFING:
                # Accept -80 or lower confidence instead of exact -100, using 3-candle average
                bearish_engulfing_conf = intraday_3candle["Bearish_Engulfing"]
                if bearish_engulfing_conf > -80:
                    logger.debug(f"Bearish Engulfing not detected (3-candle avg confidence: {bearish_engulfing_conf:.1f})")
                    condition_met = False
            elif criteria.entry_type == EntryType.SHOOTING_STAR:
                # Accept 80+ confidence instead of exact 100, using 3-candle average
                shooting_star_conf = intraday_3candle["Shooting_Star"]
                if shooting_star_conf < 80:
                    logger.debug(f"Shooting Star not detected (3-candle avg confidence: {shooting_star_conf:.1f})")
                    condition_met = False
            elif criteria.entry_type == EntryType.HAMMER:
                # Accept 80+ confidence instead of exact 100, using 3-candle average
                hammer_conf = intraday_3candle["Hammer"]
                if hammer_conf < 80:
                    logger.debug(f"Hammer not detected (3-candle avg confidence: {hammer_conf:.1f})")
                    condition_met = False
            elif criteria.entry_type == EntryType.DOJI:
                # Accept 80+ confidence instead of exact 100, using 3-candle average
                doji_conf = intraday_3candle["Doji"]
                if doji_conf < 80:
                    logger.debug(f"Doji not detected (3-candle avg confidence: {doji_conf:.1f})")
                    condition_met = False

            if condition_met:
                conditions_met_count += 1
            else:
                failed_conditions.append(criteria.entry_type.value)

        # Fuzzy logic: require 70% of conditions met, not 100%
        conditions_ratio = conditions_met_count / total_conditions if total_conditions > 0 else 0
        conditions_met = conditions_ratio >= 0.7

        logger.info(f"Entry conditions for {strategy.ticker}: {conditions_met_count}/{total_conditions} met ({conditions_ratio:.1%})")
        if failed_conditions:
            logger.debug(f"Failed conditions: {', '.join(failed_conditions)}")
        logger.info(f"Entry conditions met for {strategy.ticker}: {conditions_met}")

        return conditions_met

    except Exception as e:
        logger.error(f"Error checking conditions: {str(e)}", exc_info=True)
        return False


def check_exit_conditions(position: Position, signals: TradingSignals) -> bool:
    """
    Determine if a position should be closed based on technical analysis.

    This function serves as a safeguard against extreme adverse conditions,
    allowing the primary bracket order to manage the trade under normal circumstances.

    Updated to use 3-candle averages for consistency and removed AND logic.
    """
    # Calculate 3-candle averages for consistency
    daily_data = signals["raw_data_daily"]
    intraday_data = signals["raw_data_intraday"]

    # Get last 3 candles for averaging - returns Series
    daily_3candle = cast(pd.Series, daily_data.iloc[-3:].mean())
    intraday_3candle = cast(pd.Series, intraday_data.iloc[-3:].mean())

    # Use averaged values for consistency
    momentum = signals["momentum"]
    score = signals["score"]
    is_long = position.side == "long"
    unrealized_plpc = float(position.unrealized_plpc or 0.0)
    is_profitable = unrealized_plpc > 0

    exit_signals = []

    # This logic is a safeguard, not the primary exit strategy.
    # The primary exit is handled by the bracket order's take_profit and stop_loss.

    if is_profitable:
        # --- Let Winners Run ---
        # Only exit profitable trades on a major reversal signal.
        # Relaxed thresholds to give trades more room
        if is_long:
            if momentum < -15:  # A very significant momentum drop
                exit_signals.append(f"Major momentum reversal: {momentum:.1f}% drop")
            if score < 0.3:  # Technicals have severely degraded (relaxed from 0.4)
                exit_signals.append(f"Technical score collapse: {score:.2f}")
        else:  # is_short
            if momentum > 15:  # A very significant momentum spike against the short
                exit_signals.append(f"Major momentum reversal: {momentum:.1f}% rise")
            if score > 0.8:  # Technicals have become strongly bullish
                exit_signals.append(f"Technical score collapse for short: {score:.2f}")

    else:
        # --- Cut Losses on Clear Signals ---
        # Exit losing trades if conditions significantly worsen beyond the original thesis.
        # REMOVED AND LOGIC - now uses separate conditions
        if is_long:
            weak_tech_signals = TechnicalAnalyzer().weak_technicals(signals["signals"], OrderSide.BUY)

            # Require BOTH momentum degradation AND technical weakness
            if momentum < -15 and weak_tech_signals:
                exit_signals.append(f"Strong momentum drop: {momentum:.1f}% with weak technicals")
            # OR severe technical collapse alone
            elif score < 0.3 and weak_tech_signals:
                exit_signals.append(f"Technical score collapse: {score:.2f} with weak technicals")
            # OR catastrophic momentum without needing technical confirmation
            elif momentum < -25:  # Emergency threshold
                exit_signals.append(f"Catastrophic momentum drop: {momentum:.1f}%")

        else:  # is_short
            weak_tech_signals = TechnicalAnalyzer().weak_technicals(signals["signals"], OrderSide.SELL)

            if momentum > 15 and weak_tech_signals:
                exit_signals.append(f"Strong momentum rise: {momentum:.1f}% with weak technicals")
            elif score > 0.7 and weak_tech_signals:
                exit_signals.append(f"Technical score strength: {score:.2f} with weak technicals")
            elif momentum > 25:  # Emergency threshold
                exit_signals.append(f"Catastrophic momentum rise: {momentum:.1f}%")

    if exit_signals:
        reason_str = ", ".join(exit_signals)
        logger.info(f"\nDYNAMIC EXIT FOR {position.symbol} due to: {reason_str}")
        logger.debug(f"Position details: {position}")
        logger.debug(
            f"Using 3-candle averages - Daily: {daily_3candle.name if hasattr(daily_3candle, 'name') else 'N/A'}, Intraday: {intraday_3candle.name if hasattr(intraday_3candle, 'name') else 'N/A'}"
        )
        if unrealized_plpc < 0:
            logger.info(f"LOSS: {unrealized_plpc:.2%} P&L on trade")
        else:
            logger.info(f"WIN: {unrealized_plpc:.2%} P&L on trade")
        logger.analyze(f"Ticker: {position.symbol}, Side: {position.side}, Exit Reason: {reason_str}, P/L: {unrealized_plpc:.2%}, Momentum: {momentum:.1f}%, Score: {score:.2f}")
        return True

    return False
