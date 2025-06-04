import time
import uuid
from typing import Literal, cast

from alpaca.trading.enums import OrderSide, TimeInForce
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
from alpacalyzer.utils.logger import logger
from colorama import Fore, Style


class Trader:
    def __init__(self, analyze_mode=False, direct_tickers=None, agents="ALL"):
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

    def scan_for_insight_opportunities(self):
        market_status_colored = f"{Fore.YELLOW}{self.market_status}{Style.RESET_ALL}" if self.market_status == "closed" else f"{Fore.GREEN}{self.market_status}{Style.RESET_ALL}"
        if self.market_status == "closed":
            logger.info(f"{Fore.YELLOW}=== Reddit Scanner {Fore.RED}Paused{Style.RESET_ALL} - Market Status: {market_status_colored} ===")
            return None

        logger.info(f"\n{Fore.BLUE}=== Reddit Scanner {Fore.GREEN}Starting{Style.RESET_ALL} - Market Status: {market_status_colored} ===")

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
        market_status_colored = f"{Fore.YELLOW}{self.market_status}{Style.RESET_ALL}" if self.market_status == "closed" else f"{Fore.GREEN}{self.market_status}{Style.RESET_ALL}"

        if self.market_status == "closed":
            logger.info(f"{Fore.YELLOW}=== Momentum Scanner {Fore.RED}Paused{Style.RESET_ALL} - Market Status: {market_status_colored} ===")
            return

        logger.info(f"\n{Fore.BLUE}=== Momentum Scanner {Fore.GREEN}Starting{Style.RESET_ALL} - Market Status: {market_status_colored} ===")

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
                    logger.info(f"Skipping {Fore.CYAN}{stock['ticker']}{Style.RESET_ALL} - No trading signals")
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
        market_status_colored = f"{Fore.YELLOW}{self.market_status}{Style.RESET_ALL}" if self.market_status == "closed" else f"{Fore.GREEN}{self.market_status}{Style.RESET_ALL}"

        if self.market_status == "closed":
            logger.info(f"{Fore.YELLOW}=== Hedge Fund {Fore.RED}Paused{Style.RESET_ALL} - Market Status: {market_status_colored} ===")
            return

        logger.info(f"\n{Fore.BLUE}=== Hedge Fund {Fore.GREEN}Starting{Style.RESET_ALL} - Market Status: {market_status_colored} ===")

        # If direct tickers were provided, use those instead of opportunity scanners
        if self.direct_tickers:
            colored_direct_tickers = [f"{Fore.CYAN}{ticker}{Style.RESET_ALL}" for ticker in self.direct_tickers]
            logger.info(f"Using directly provided tickers: {', '.join(colored_direct_tickers)}")
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
                logger.info(f"{Fore.YELLOW}No opportunities available.{Style.RESET_ALL}")
                return

            hedge_fund_response = call_hedge_fund_agents(self.opportunities, self.agents, show_reasoning=True)
            print_trading_output(hedge_fund_response) # Assuming this function handles its own coloring or is out of scope

            if not hedge_fund_response["decisions"] or hedge_fund_response["decisions"] is None:
                logger.info(f"{Fore.YELLOW}No trade decisions from hedge fund.{Style.RESET_ALL}")
                return

            # Create trading strategies from hedge fund response
            for data in hedge_fund_response["decisions"].values():
                strategies = data.get("strategies", [])
                for strategy in strategies:
                    strategy = TradingStrategy.model_validate(strategy)
                    if strategy.ticker in [s.ticker for s in self.latest_strategies]:
                        logger.info(f"Strategy already exists for {Fore.CYAN}{strategy.ticker}{Style.RESET_ALL} - {Fore.YELLOW}Skipping{Style.RESET_ALL}")
                        continue
                    self.latest_strategies.append(strategy)

            self.opportunities = []

        except Exception as e:
            logger.error(f"Error in run_hedge_fund: {str(e)}", exc_info=True)

    # Function to check real-time price and execute orders
    def monitor_and_trade(self):
        """Monitor positions and trade every X minutes."""
        market_status_colored = f"{Fore.YELLOW}{self.market_status}{Style.RESET_ALL}" if self.market_status == "closed" else f"{Fore.GREEN}{self.market_status}{Style.RESET_ALL}"

        if not self.latest_strategies:
            logger.info(f"{Fore.YELLOW}No active strategies to monitor.{Style.RESET_ALL}")
            return

        if self.market_status == "closed":
            logger.info(f"{Fore.YELLOW}=== Trading Monitor Loop {Fore.RED}Paused{Style.RESET_ALL} - Market Status: {market_status_colored} ===")
            return

        logger.info(f"\n{Fore.BLUE}=== Trading Monitor Loop {Fore.GREEN}Starting{Style.RESET_ALL} - Market Status: {market_status_colored} ===")
        logger.info(f"Active Strategies: {Fore.GREEN}{len(self.latest_strategies)}{Style.RESET_ALL}")

        executed_tickers: list[str] = []  # Track tickers whose strategies have been executed

        try:
            for strategy in self.latest_strategies[:]:
                logger.debug(f"executed_tickers: {executed_tickers}")
                if strategy.ticker in executed_tickers:
                    continue  # Skip strategies for tickers that already executed

                signals = self.technical_analyzer.analyze_stock(strategy.ticker)
                if signals is None:
                    continue

                colored_ticker = f"{Fore.CYAN}{strategy.ticker}{Style.RESET_ALL}"
                colored_price = f"{Fore.GREEN}{signals['price']}{Style.RESET_ALL}"
                colored_trade_type = f"{Fore.MAGENTA}{strategy.trade_type}{Style.RESET_ALL}"
                colored_entry_point = f"{Fore.GREEN}{strategy.entry_point}{Style.RESET_ALL}"
                colored_target_price = f"{Fore.GREEN}{strategy.target_price}{Style.RESET_ALL}"
                colored_stop_loss = f"{Fore.RED}{strategy.stop_loss}{Style.RESET_ALL}"

                logger.info(
                    f"\nChecking strategy for {colored_ticker} (Current price: {colored_price}):\n"
                    f"Type: {colored_trade_type}, Entry: {colored_entry_point}, "
                    f"Target: {colored_target_price}, Stop Loss: {colored_stop_loss}"
                )

                # Check if entry conditions are met
                if check_entry_conditions(strategy, signals):
                    asset_response = trading_client.get_asset(strategy.ticker)
                    asset = cast(Asset, asset_response)

                    if not asset.tradable:
                        logger.info(f"Asset {Fore.RED}is not tradable{Style.RESET_ALL} {colored_ticker} - {Fore.YELLOW}Removing strategy{Style.RESET_ALL}")
                        self.latest_strategies.remove(strategy)
                        continue

                    if strategy.trade_type == "short" and not asset.shortable:
                        logger.info(f"Asset {Fore.RED}can not be shorted{Style.RESET_ALL} {colored_ticker} - {Fore.YELLOW}Removing strategy{Style.RESET_ALL}")
                        self.latest_strategies.remove(strategy)
                        continue

                    print_strategy_output(strategy) # Assuming this function handles its own coloring or is out of scope

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
                        client_order_id=f"hedge_{strategy.ticker}_{side}_{uuid.uuid4()}",
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
            logger.error(f"Error in monitor_and_trade entries: {str(e)}", exc_info=True)

        try:
            positions = get_positions()
            for position in positions:
                if position.symbol in executed_tickers:
                    continue
                signals = self.technical_analyzer.analyze_stock(position.symbol)
                if signals is None:
                    continue

                pos_symbol_colored = f"{Fore.CYAN}{position.symbol}{Style.RESET_ALL}"
                pos_price_colored = f"{Fore.GREEN}{position.current_price}{Style.RESET_ALL}"
                pos_side_colored = f"{Fore.MAGENTA}{position.side}{Style.RESET_ALL}"
                pos_entry_colored = f"{Fore.GREEN}{position.avg_entry_price}{Style.RESET_ALL}"

                plpc_val = float(position.unrealized_plpc or 0.0)
                plpc_color = Fore.GREEN if plpc_val >= 0 else Fore.RED
                pos_plpc_colored = f"{plpc_color}{plpc_val:.2%}{Style.RESET_ALL}"
                pos_mv_colored = f"{Fore.GREEN}${float(position.market_value or 0.0):.2f}{Style.RESET_ALL}"

                logger.info(
                    f"\nChecking exit conditions for {pos_symbol_colored} (Current price: {pos_price_colored}):\n"
                    f"Type: {pos_side_colored}, Entry: {pos_entry_colored}, "
                    f"Unrealized P/L: {pos_plpc_colored}, Market value: {pos_mv_colored}, "
                )
                # Check if exit conditions are met
                if check_exit_conditions(position, signals):
                    # Close position
                    logger.info(f"{Fore.YELLOW}Closing position for {pos_symbol_colored}{Style.RESET_ALL}")
                    open_orders_resp = trading_client.get_orders(GetOrdersRequest(status="open"))
                    open_orders = cast(list[Order], open_orders_resp)
                    for order in open_orders:
                        if order.symbol == position.symbol:
                            trading_client.cancel_order_by_id(order.id)
                    time.sleep(1.0)
                    order_resp = trading_client.close_position(position.symbol)
                    order = cast(Order, order_resp)
                    log_order(order)
        except Exception as e:
            logger.error(f"Error in monitor_and_trade exits: {str(e)}", exc_info=True)


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
                logger.debug(f"Price near support: {price} +/- 0.5% from {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.PRICE_NEAR_RESISTANCE and not criteria.value * (
                1 - 0.005
            ) <= price <= criteria.value * (1 + 0.005):
                logger.debug(f"Price near resistance: {price} +/- 0.5% from {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.BREAKOUT_ABOVE and price <= criteria.value:
                logger.debug(f"Breakout above: {price} <= {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.RSI_OVERSOLD and rsi > criteria.value:
                logger.debug(f"RSI oversold: {rsi} > {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.RSI_OVERBOUGHT and rsi < criteria.value:
                logger.debug(f"RSI overbought: {rsi} < {criteria.value}")
                conditions_met = False
            if criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_20 and price < sma20:
                logger.debug(f"Price above SMA20: {price} < {sma20}")
                conditions_met = False
            if criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_20 and price > sma20:
                logger.debug(f"Price below SMA20: {price} > {sma20}")
                conditions_met = False
            if criteria.entry_type == EntryType.ABOVE_MOVING_AVERAGE_50 and price < sma50:
                logger.debug(f"Price above SMA50: {price} < {sma50}")
                conditions_met = False
            if criteria.entry_type == EntryType.BELOW_MOVING_AVERAGE_50 and price > sma50:
                logger.debug(f"Price below SMA50: {price} > {sma50}")
                conditions_met = False
            if criteria.entry_type == EntryType.BULLISH_ENGULFING and latest_intraday["Bullish_Engulfing"] != 100:
                logger.debug("Bullish Engulfing not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.BEARISH_ENGULFING and latest_intraday["Bearish_Engulfing"] != -100:
                logger.debug("Bearish Engulfing not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.SHOOTING_STAR and latest_intraday["Shooting_Star"] != 100:
                logger.debug("Shooting Star not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.HAMMER and latest_intraday["Hammer"] != 100:
                logger.debug("Hammer not detected")
                conditions_met = False
            if criteria.entry_type == EntryType.DOJI and latest_intraday["Doji"] != 100:
                logger.debug("Doji not detected")
                conditions_met = False

        colored_ticker = f"{Fore.CYAN}{strategy.ticker}{Style.RESET_ALL}"
        colored_conditions_met = f"{Fore.GREEN}{conditions_met}{Style.RESET_ALL}" if conditions_met else f"{Fore.RED}{conditions_met}{Style.RESET_ALL}"
        logger.info(f"Entry conditions met for {colored_ticker}: {colored_conditions_met}")
        return conditions_met

    except Exception as e:
        logger.error(f"Error checking conditions: {str(e)}", exc_info=True)
        return False


def check_exit_conditions(position: Position, signals: TradingSignals) -> bool:
    """Determine if a position should be closed based on technical analysis."""

    ticker_signals = signals["signals"]
    momentum = signals["momentum"]
    score = signals["score"]

    # Close if any of these conditions are met:
    exit_signals = []

    # 1. Significant loss
    unrealized_plpc = float(position.unrealized_plpc or 0.0)
    if float(unrealized_plpc) < -0.05:  # -5% stop loss
        exit_signals.append(f"Stop loss hit: {unrealized_plpc:.1%} P&L")

    # 2. Quick Momentum Shifts - Only exit if significant drop
    if momentum < -5 and unrealized_plpc > 0:  # Need profit to use quick exit
        if unrealized_plpc > 0.05:  # Need 5% profit to use quick exit
            exit_signals.append(f"Momentum reversal: {momentum:.1f}% drop while +{unrealized_plpc:.1%}% up")

    # 3. Technical Weakness
    if score < 0.6:  # Weak technical score
        weak_tech_signals = TechnicalAnalyzer().weak_technicals(ticker_signals, OrderSide.SELL)
        if weak_tech_signals is not None:
            exit_signals.append(weak_tech_signals)

    # Check if any exit signals triggered
    if exit_signals:
        reason_str = ", ".join(exit_signals) # Reasons themselves might need coloring if they contain specific keywords
        colored_symbol = f"{Fore.CYAN}{position.symbol}{Style.RESET_ALL}"
        # Store exit reason to block immediate re-entry
        logger.info(f"\n{Fore.RED}SELL {colored_symbol}{Style.RESET_ALL} due to: {reason_str}")
        logger.debug(f"Position details: {position}") # debug logs are not in scope for this task
        if unrealized_plpc < 0:
            colored_plpc = f"{Fore.RED}{unrealized_plpc:.1%}{Style.RESET_ALL}"
            logger.info(f"{Fore.RED}LOSS: {colored_plpc} P&L loss on trade{Style.RESET_ALL}")
        else:
            colored_plpc = f"{Fore.GREEN}{unrealized_plpc:.1%}{Style.RESET_ALL}"
            logger.info(f"{Fore.GREEN}WIN: {colored_plpc} P&L gain on trade{Style.RESET_ALL}")
        return True

    return False
