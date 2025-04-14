import uuid
from typing import cast

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.models import Asset, Order
from alpaca.trading.requests import LimitOrderRequest

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.gpt.call_gpt import (
    get_reddit_insights,
    get_top_candidates,
)
from alpacalyzer.gpt.response_models import EntryType, TopTickers, TradingStrategy
from alpacalyzer.hedge_fund import call_hedge_fund_agents
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.scanners.social_scanner import SocialScanner
from alpacalyzer.trading.alpaca_client import get_market_status, log_order, trading_client
from alpacalyzer.trading.position_manager import PositionManager
from alpacalyzer.trading.yfinance_client import YFinanceClient
from alpacalyzer.utils.logger import logger


class Trader:
    def __init__(self):
        """Initialize the Trader instance."""
        self.position_manager = PositionManager(max_position_size=0.10, max_total_exposure=0.5, strategy="swing")
        self.technical_analyzer = TechnicalAnalyzer()
        self.finviz_scanner = FinvizScanner()
        self.yfinance_client = YFinanceClient()
        self.social_scanner = SocialScanner()
        self.latest_strategies: list[TradingStrategy] = []
        self.opportunities: list[TopTickers] = []

    def scan_for_insight_opportunities(self):
        """Main trading loop."""
        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Reddit Scanner Paused - Market Status: {market_status} ===")
            return None

        logger.info(f"\n=== Reddit Scanner Starting - Market Status: {market_status} ===")

        try:
            reddit_insights = get_reddit_insights()
            reddit_picks = reddit_insights.top_tickers if reddit_insights else []
            reddit_tickers = [x.ticker for x in reddit_picks]
            top_tickers = list(set(reddit_tickers))
            input_ta_df = self.finviz_scanner.fetch_stock_data(tuple(top_tickers))
            top_candidates = get_top_candidates(input_ta_df)
            opportunities = top_candidates.top_tickers if top_candidates else []

            for opportunity in opportunities:
                if opportunity.ticker not in [o.ticker for o in self.opportunities]:
                    self.opportunities.append(opportunity)

        except Exception as e:
            logger.error(f"Error in scan_for_insight_opportunities: {str(e)}", exc_info=True)

    def scan_for_technical_opportunities(self):
        """Main trading loop."""
        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Momentum Scanner Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Momentum Scanner Starting - Market Status: {market_status} ===")

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
                    entry_blockers.append(
                        f"Technical data too weak: {trading_signals['score']:.2f} < {ta_threshold:.2f}"
                    )

                # Check for conflicting signals
                if momentum < 0 and stock["sentiment_rank"] > 20:
                    entry_blockers.append("Conflicting momentum and sentiment signals.")

                if momentum < -3:
                    entry_blockers.append(f"Weak momentum {momentum:.1f}%")

                # Only allow weaker setups if breakout pattern detected
                if (
                    15 < vix_close < 30
                    and trading_signals["score"] < 0.8
                    and not any("TA: Breakout" in signal for signal in signals)
                ):
                    entry_blockers.append("No breakout pattern detected")

                # 3. Technical Weakness
                weak_tech_signals = self.technical_analyzer.weak_technicals(signals, OrderSide.BUY)
                if weak_tech_signals is not None:
                    entry_blockers.append(f"{weak_tech_signals}")

                if entry_blockers:
                    logger.info(f"Entry blocked for {stock['ticker']}:")
                    for blocker in entry_blockers:
                        logger.info(f"- {blocker}")
                    continue

                # Convert back to signal
                if trading_signals["score"] > 0.8:
                    signal = "bullish"
                elif trading_signals["score"] < 0.5:
                    signal = "bearish"
                else:
                    signal = "neutral"

                opportunity = TopTickers(
                    ticker=stock["ticker"],
                    confidence=80,
                    recommendation=signal,
                )

                if opportunity.ticker not in [o.ticker for o in self.opportunities]:
                    self.opportunities.append(opportunity)

        except Exception as e:
            logger.error(f"Error in scan_for_tehcnical_opportunities: {str(e)}", exc_info=True)

    def run_hedge_fund(self):
        """Hedge fund."""
        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Hedge Fund Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Hedge Fund Starting - Market Status: {market_status} ===")

        self.opportunities.append(TopTickers(ticker="AAPL", confidence=70, recommendation="bullish"))

        try:
            if not self.opportunities:
                logger.info("No opportunities available.")
                return

            hedge_fund_response = call_hedge_fund_agents(self.opportunities, show_reasoning=True)
            logger.info(f"Hedge Fund Response: {hedge_fund_response}")
            self.opportunities = []
            if not hedge_fund_response["decisions"] or hedge_fund_response["decisions"] is None:
                logger.info("No trade decisions from hedge fund.")
                return
            # TODO - Create trading strategies from hedge fund response
            for data in hedge_fund_response["decisions"].values():
                strategies = data.get("strategies", [])
                for strategy in strategies:
                    strategy = TradingStrategy.model_validate(strategy)
                    if strategy.ticker in [s.ticker for s in self.latest_strategies]:
                        logger.info(f"Strategy already exists for {strategy.ticker} - Skipping")
                        continue
                    self.latest_strategies.append(strategy)
                    logger.info(f"New strategy created: {strategy}")

        except Exception as e:
            logger.error(f"Error in run_hedge_fund: {str(e)}", exc_info=True)

    # Function to check real-time price and execute orders
    def monitor_and_trade(self):
        """Monitor positions and trade every X minutes."""

        if not self.latest_strategies:
            logger.info("No active strategies to monitor.")
            return

        market_status = get_market_status()

        if market_status != "open":
            logger.info(f"=== Trading Monitor Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Trading Monitor Loop Starting - Market Status: {market_status} ===")
        logger.info(f"Active Strategies: {len(self.latest_strategies)}")

        # Update positions and orders silently
        # current_positions = self.position_manager.update_positions()
        # self.position_manager.update_pending_orders()

        executed_tickers: list[str] = []  # Track tickers whose strategies have been executed

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
                    # Correct rounding for limit price
                    if strategy.entry_point > 1:
                        limit_price = round(strategy.entry_point, 2)
                    else:
                        limit_price = round(strategy.entry_point, 4)

                    bracket_order = LimitOrderRequest(
                        symbol=strategy.ticker,
                        qty=strategy.quantity,
                        side=side,
                        type="limit",
                        time_in_force=TimeInForce.GTC,
                        limit_price=limit_price,
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
                    executed_tickers.append(strategy.ticker)

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
