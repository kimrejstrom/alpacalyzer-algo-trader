import uuid
from typing import cast

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.models import Asset, Order
from alpaca.trading.requests import LimitOrderRequest

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.gpt.call_gpt import (
    get_reddit_insights,
    get_top_candidates,
    get_trading_strategies,
)
from alpacalyzer.gpt.response_models import EntryType, TradingStrategy
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.trading.alpaca_client import get_market_status, log_order, trading_client
from alpacalyzer.trading.position_manager import PositionManager
from alpacalyzer.utils.logger import logger


class SwingTrader:
    def __init__(self):
        """Initialize the SwingTrader instance."""
        self.position_manager = PositionManager(max_position_size=0.10, max_total_exposure=0.5, strategy="swing")
        self.technical_analyzer = TechnicalAnalyzer()
        self.latest_strategies: list[TradingStrategy] = []
        self.finviz_scanner = FinvizScanner()

    def analyze_and_swing_trade(self):
        """Main swing-trading loop."""
        market_status = get_market_status()

        if market_status != "open":
            logger.info(f"=== Swing Trading Prospect Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Swing Trading Prospect Loop Starting - Market Status: {market_status} ===")

        try:
            reddit_insights = get_reddit_insights()
            reddit_picks = reddit_insights.top_tickers if reddit_insights else []
            reddit_tickers = [x.ticker for x in reddit_picks]
            top_tickers = list(set(reddit_tickers))
            input_ta_df = self.finviz_scanner.fetch_stock_data(tuple(top_tickers))
            analyzer_response = get_top_candidates(input_ta_df)
            analyzer_picks = analyzer_response.top_tickers if analyzer_response else []

            final_tickers = [x.ticker for x in analyzer_picks]
            self.latest_strategies = []

            for ticker in final_tickers:
                signals = self.technical_analyzer.analyze_stock(ticker)
                if signals is None:
                    continue
                # Combine recommendations from Reddit and Finviz
                reddit_recommendations = [x.recommendation for x in reddit_picks if x.ticker == ticker]
                finviz_recommendations = [x.recommendation for x in analyzer_picks if x.ticker == ticker]
                recommendations = list(reddit_recommendations + finviz_recommendations)

                trading_strategies_response = get_trading_strategies(signals, recommendations)
                trading_strategies = trading_strategies_response.strategies if trading_strategies_response else []
                if len(trading_strategies) > 0:
                    self.latest_strategies.extend(trading_strategies)
                    logger.info(f"Added {len(trading_strategies)} new strategies for {ticker}")

            for strategy in self.latest_strategies:
                logger.info(
                    f"Added strategy for {strategy.ticker}:\n"
                    f"Type: {strategy.trade_type}, Entry: {strategy.entry_point}, "
                    f"Target: {strategy.target_price}, Stop Loss: {strategy.stop_loss}\n"
                    f"Criteria: {strategy.entry_criteria}\n"
                    f"Notes: {strategy.strategy_notes}\n\n"
                )
        except Exception as e:
            logger.error(f"Error in analyze_and_swing_trade: {str(e)}", exc_info=True)

    # Function to check real-time price and execute orders
    def monitor_and_trade(self):
        """Monitor positions and trade every X minutes."""

        if not self.latest_strategies:
            logger.info("No active strategies to monitor.")
            return

        market_status = get_market_status()

        if market_status != "open":
            logger.info(f"=== Swing Trading Monitor Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Swing Trading Monitor Loop Starting - Market Status: {market_status} ===")
        logger.info(f"Active Strategies: {len(self.latest_strategies)}")

        # Update positions and orders silently
        current_positions = self.position_manager.update_positions()
        self.position_manager.update_pending_orders()

        executed_tickers = set(current_positions.keys())  # Track tickers whose strategies have been executed

        try:
            for strategy in self.latest_strategies[:]:
                logger.info(f"executed_tickers: {executed_tickers}")
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

                    logger.info(f"Executing strategy for {strategy.ticker}:\n{strategy.strategy_notes}")

                    # Determine order type
                    side = OrderSide.BUY if strategy.trade_type.lower() == "long" else OrderSide.SELL
                    shares, allow_trade = self.position_manager.calculate_target_position(
                        symbol=strategy.ticker, price=strategy.entry_point, technical_data=signals
                    )

                    if allow_trade and shares > 0:
                        bracket_order = LimitOrderRequest(
                            symbol=strategy.ticker,
                            qty=shares,
                            side=side,
                            type="limit",
                            time_in_force=TimeInForce.GTC,
                            limit_price=strategy.entry_point,
                            order_class="bracket",
                            stop_loss={"stop_price": strategy.stop_loss},
                            take_profit={"limit_price": strategy.target_price},
                            client_order_id=f"swing_{strategy.ticker}_{side}_{uuid.uuid4()}",
                        )
                        # Submit order with bracket structure
                        logger.debug(f"Submitting order: {bracket_order}")
                        order_resp = trading_client.submit_order(bracket_order)
                        order = cast(Order, order_resp)
                        log_order(order)

                        # Mark strategy as executed
                        executed_tickers.add(strategy.ticker)

            # Remove all strategies for executed tickers
            self.latest_strategies = [s for s in self.latest_strategies if s.ticker not in executed_tickers]

        except Exception as e:
            logger.error(f"Error in monitor_and_trade: {str(e)}", exc_info=True)


def check_entry_conditions(strategy: TradingStrategy, signals: TradingSignals) -> bool:
    try:
        latest_daily = signals["raw_data_daily"].iloc[-2]
        latest_intraday = signals["raw_data_intraday"].iloc[-2]
        price = signals["price"]
        rsi = latest_daily["RSI"]
        sma20 = latest_daily["SMA_20"]
        sma50 = latest_daily["SMA_50"]

        conditions_met = True

        for criteria in strategy.entry_criteria:
            if criteria.entry_type == EntryType.PRICE_NEAR_SUPPORT and not criteria.value * (
                1 - 0.005
            ) <= price <= criteria.value * (1 + 0.005):
                logger.info(f"Price near support: {price} +/- 0.5% from {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.PRICE_NEAR_RESISTANCE and not criteria.value * (
                1 - 0.005
            ) <= price <= criteria.value * (1 + 0.005):
                logger.info(f"Price near resistance: {price} +/- 0.5% from {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.BREAKOUT_ABOVE and price <= criteria.value:
                logger.info(f"Breakout above: {price} <= {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.RSI_OVERSOLD and rsi > criteria.value:
                logger.info(f"RSI oversold: {rsi} > {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.RSI_OVERBOUGHT and rsi < criteria.value:
                logger.info(f"RSI overbought: {rsi} < {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_20 and price < sma20:
                logger.info(f"Price above SMA20: {price} < {sma20}")
                conditions_met = False
            if criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_20 and price > sma20:
                logger.info(f"Price below SMA20: {price} > {sma20}")
                conditions_met = False
            if criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_50 and price < sma50:
                logger.info(f"Price above SMA50: {price} < {sma50}")
                conditions_met = False
            if criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_50 and price > sma50:
                logger.info(f"Price below SMA50: {price} > {sma50}")
                conditions_met = False
            if criteria.entry_type == EntryType.BULLISH_ENGULFING and latest_intraday["Bullish_Engulfing"] != 100:
                logger.info("Bullish Engulfing not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.BEARISH_ENGULFING and latest_intraday["Bearish_Engulfing"] != -100:
                logger.info("Bearish Engulfing not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.SHOOTING_STAR and latest_intraday["Shooting_Star"] != 100:
                logger.info("Shooting Star not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.HAMMER and latest_intraday["Hammer"] != 100:
                logger.info("Hammer not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.DOJI and latest_intraday["Doji"] != 100:
                logger.info("Doji not detected")
                conditions_met = False

        logger.info(f"Entry conditions met for {strategy.ticker}: {conditions_met}")
        return conditions_met

    except Exception as e:
        logger.error(f"Error checking conditions: {str(e)}", exc_info=True)
        return False
