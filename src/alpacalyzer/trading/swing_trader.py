import pandas as pd
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer
from alpacalyzer.gpt.call_gpt import (
    get_reddit_insights,
    get_top_candidates,
    get_trading_strategies,
)
from alpacalyzer.gpt.response_models import EntryType, TradingStrategy
from alpacalyzer.scanners.finviz_scanner import FinvizScanner
from alpacalyzer.trading.alpaca_client import get_market_status, trading_client
from alpacalyzer.utils.logger import logger


class SwingTrader:
    def __init__(self):
        """Initialize the SwingTrader instance."""

        self.latest_strategies: list[TradingStrategy] = []

    def analyze_and_swing_trade(self):
        """Main swing-trading loop."""
        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Swing Trading Prospect Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Swing Trading Prospect Loop Starting - Market Status: {market_status} ===")

        reddit_insights = get_reddit_insights()
        reddit_picks = reddit_insights.top_tickers if reddit_insights else []
        finviz_df = FinvizScanner().get_trending_stocks()
        finviz_tickers = finviz_df["Ticker"].tolist()
        reddit_tickers = [x.ticker for x in reddit_picks]
        top_tickers = list(set(reddit_tickers + finviz_tickers))

        input_ta_df = FinvizScanner().fetch_stock_data(tuple(top_tickers))
        analyzer_response = get_top_candidates(input_ta_df)
        analyzer_picks = analyzer_response.top_tickers if analyzer_response else []

        final_tickers = [x.ticker for x in analyzer_picks]
        self.latest_strategies = []

        for ticker in final_tickers:
            logger.info(f"Analyzing {ticker}...")
            df = TechnicalAnalyzer().analyze_stock_daily(ticker)
            if df is None or df.empty:
                continue
            trading_strategies_response = get_trading_strategies(df, ticker)
            trading_strategies = trading_strategies_response.strategies if trading_strategies_response else []
            self.latest_strategies.extend(trading_strategies)

        logger.debug(f"Updated latest strategies: {self.latest_strategies}")

    # Function to check real-time price and execute orders
    def monitor_and_trade(self):
        """Monitor positions and trade every X minutes."""

        if not self.latest_strategies:
            logger.info("No active strategies to monitor.")
            return

        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Swing Trading Monitor Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Swing Trading Monitor Loop Starting - Market Status: {market_status} ===")

        analyzer = TechnicalAnalyzer()

        try:
            for strategy in self.latest_strategies:
                if strategy.executed:
                    continue  # Skip strategies already executed

                daily_ta = analyzer.analyze_stock_daily(strategy.ticker)
                if daily_ta is None or daily_ta.empty:
                    continue

                # Check if entry conditions are met
                if check_entry_conditions(strategy, daily_ta):
                    logger.info(f"Executing strategy: {strategy.strategy_notes}")

                    # Determine order type
                    side = OrderSide.BUY if strategy.trade_type == "long" else OrderSide.SELL
                    qty = 10  # Adjust based on risk management
                    logger.debug(f"{strategy}")
                    bracket_order = LimitOrderRequest(
                        symbol=strategy.ticker,
                        qty=qty,
                        side=side,
                        type="limit",
                        time_in_force=TimeInForce.DAY,
                        limit_price=strategy.entry_point,
                        order_class="bracket",
                        stop_loss={"stop_price": strategy.stop_loss},
                        take_profit={"limit_price": strategy.target_price},
                        client_order_id=f"{strategy.ticker}-{strategy.entry_point}-{strategy.trade_type}",
                    )
                    # Submit order with bracket structure
                    order = trading_client.submit_order(bracket_order)

                    strategy.executed = True  # Mark strategy as executed
                    logger.info(f"Order placed: {order}")

        except Exception as e:
            logger.error(f"Error in monitor_and_trade: {e}")


def check_entry_conditions(strategy: TradingStrategy, df: pd.DataFrame) -> bool:
    try:
        latest = df.iloc[-1]
        price = latest["close"]
        recent_high = latest["high"].max()  # Highest price in last 50 periods
        recent_low = latest["low"].min()  # Lowest price in last 50 periods
        rsi = latest["RSI"]
        volume_spike = latest["RVOL"]  # Relative volume
        sma20 = latest["SMA_20"]
        sma50 = latest["SMA_50"]

        conditions_met = True

        for criteria in strategy.entry_criteria:
            if criteria.entry_type == EntryType.PRICE_NEAR_SUPPORT and price > criteria.value:
                conditions_met = False
            if criteria.entry_type == EntryType.PRICE_NEAR_RESISTANCE and price < criteria.value:
                conditions_met = False
            if criteria.entry_type == EntryType.BREAKOUT_ABOVE and price <= criteria.value:
                conditions_met = False
            if criteria.entry_type == EntryType.RSI_OVERSOLD and rsi > criteria.value:
                conditions_met = False
            if criteria.entry_type == EntryType.RSI_OVERBOUGHT and rsi < criteria.value:
                conditions_met = False
            if criteria.entry_type == EntryType.VOLUME_SPIKE and volume_spike < criteria.value:
                conditions_met = False
            if criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_20 and price < sma20:
                conditions_met = False
            if criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_20 and price > sma20:
                conditions_met = False
            if criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_50 and price < sma50:
                conditions_met = False
            if criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_50 and price > sma50:
                conditions_met = False
            if criteria.entry_type == EntryType.MOMENTUM_CONTINUATION:
                if price < recent_high * 0.98:  # Ensures strong continuation (2% off high)
                    conditions_met = False
            if criteria.entry_type == EntryType.MOMENTUM_REVERSAL:
                if price > recent_low * 1.02:  # Ensures strong reversal (2% off low)
                    conditions_met = False

            # Check Candlestick Patterns
            if criteria.entry_type == EntryType.BULLISH_ENGULFING:
                conditions_met = conditions_met and latest["Bullish_Engulfing"] == 100
            if criteria.entry_type == EntryType.BEARISH_ENGULFING:
                conditions_met = conditions_met and latest["Bearish_Engulfing"] == -100
            if criteria.entry_type == EntryType.SHOOTING_STAR:
                conditions_met = conditions_met and latest["Shooting_Star"] == 100
            if criteria.entry_type == EntryType.HAMMER:
                conditions_met = conditions_met and latest["Hammer"] == 100
            if criteria.entry_type == EntryType.DOJI:
                conditions_met = conditions_met and latest["Doji"] == 100

        return conditions_met

    except Exception as e:
        logger.error(f"Error checking conditions: {e}")
        return False
