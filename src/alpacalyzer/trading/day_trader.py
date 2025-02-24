from datetime import UTC, datetime

import pandas as pd
from alpaca.trading.enums import OrderSide

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer
from alpacalyzer.scanners.social_scanner import SocialScanner
from alpacalyzer.trading.alpaca_client import get_market_status
from alpacalyzer.trading.position_manager import PositionManager
from alpacalyzer.trading.yfinance_client import YFinanceClient
from alpacalyzer.utils.logger import logger


class DayTrader:
    def __init__(self):
        self.position_manager = PositionManager()
        self.yfinance_client = YFinanceClient()

    def manage_existing_positions(self, analyzer: TechnicalAnalyzer, trending_stocks: pd.DataFrame):
        """Manage existing positions."""
        # Update positions
        current_positions = self.position_manager.update_positions()
        if not current_positions:
            return

        # Get top 15 stocks
        top_stocks = trending_stocks.head(15)

        # Check each position for exit signals
        for symbol in list(current_positions.keys()):
            technical_data = analyzer.analyze_stock(symbol)

            if not technical_data:
                logger.warning(f"Technical data missing for {symbol}")
                continue

            current_positions[symbol].update_ta(technical_data)
            if self.position_manager.should_close_position(symbol, technical_data, top_stocks):
                self.position_manager.close_position(symbol)

        # Check for over exposure
        if self.position_manager.get_total_exposure() > self.position_manager.max_total_exposure:
            logger.info(
                f"\nOver exposure detected ({self.position_manager.total_exposure:.1%}) - closing worst positions"
            )
            self.position_manager.handle_over_exposure()

    def calculate_ta_threshold(self, vix_close, rel_vol, atr_pct):
        """Dynamically adjust technical score threshold based on VIX, volume, and volatility."""

        logger.debug(f"VIX: {vix_close:.1f}, Rel Vol: {rel_vol:.1f}, ATR %: {atr_pct:.2f}")
        if vix_close > 35:
            if rel_vol >= 3 and atr_pct < 0.08:  # Slightly raised ATR limit
                return 0.8  # Allow strong setups
            return 0.9  # Stricter threshold

        if 30 <= vix_close <= 35:
            if rel_vol >= 2 and atr_pct < 0.10:  # Allow higher ATR in high VIX
                return 0.7
            return 0.75

        if 20 <= vix_close <= 30:
            if rel_vol >= 1.5 and atr_pct < 0.12:  # More flexibility in calm markets
                return 0.6
            return 0.65

        # VIX < 20 (Calm market)
        return 0.5  # Allow all setups

    def find_new_opportunities(self, analyzer: TechnicalAnalyzer, trending_stocks):
        """Find and execute new trades."""

        # Update positions and orders silently
        self.position_manager.positions = self.position_manager.update_positions(show_status=False)
        self.position_manager.update_pending_orders()

        # Get top 10 stocks
        top_stocks = trending_stocks.head(10)

        # Get pending orders
        pending_orders = {order["symbol"] for order in self.position_manager.pending_orders}

        # Get VIX and ATR data
        vix_close = self.yfinance_client.get_vix()

        # Enter new positions only if not at max exposure
        if self.position_manager.get_total_exposure() < self.position_manager.max_total_exposure:
            for _, stock in top_stocks.iterrows():
                ticker = stock["ticker"]

                entry_blockers = []

                logger.info(f"\nEvaluating entry for {ticker}")
                # Skip if we already have a pending order
                if ticker in pending_orders:
                    entry_blockers.append("Pending order already exists")
                    continue

                technical_data = analyzer.analyze_stock(ticker)
                if not technical_data:
                    entry_blockers.append("Technical data missing")
                    continue

                # Check if stock was previously exited and decide if it's cleared
                if ticker in self.position_manager.exited_positions:
                    exit_info = self.position_manager.exited_positions[ticker]
                    exit_reason = exit_info["reason"]
                    exit_time = exit_info["timestamp"]
                    time_since_exit = (datetime.now(UTC) - exit_time).total_seconds() / 3600  # Hours since exit

                    # Clear re-entry blocker if:
                    # 1. More than 1 hour has passed OR
                    # 2. A breakout pattern is detected
                    breakout_detected = any("TA: Breakout" in signal for signal in technical_data["signals"])

                    if time_since_exit > 1 or breakout_detected:
                        logger.info(f"Allowing re-entry for {ticker} (Exit reason: {exit_reason})")
                        del self.position_manager.exited_positions[ticker]  # Clear blocker
                    else:
                        entry_blockers.append(
                            f"BLOCKED: {ticker} was exited due to {exit_reason} ({int(time_since_exit)}h ago)"
                        )

                # Check technicals
                signals = technical_data.get("signals", [])
                momentum = technical_data.get("momentum", 0)

                atr_pct = technical_data["atr"] / technical_data["price"]
                ta_threshold = self.calculate_ta_threshold(
                    vix_close,
                    technical_data["rvol"],
                    atr_pct,
                )

                if technical_data["score"] < ta_threshold:
                    entry_blockers.append(
                        f"Technical data too weak: {technical_data['score']:.2f} < {ta_threshold:.2f}"
                    )

                # Check for conflicting signals
                if momentum < 0 and stock["sentiment_rank"] > 20:
                    entry_blockers.append("Conflicting momentum and sentiment signals.")

                if momentum < -3:
                    entry_blockers.append(f"Weak momentum {momentum:.1f}%")

                # Only allow weaker setups if breakout pattern detected
                if (
                    15 < vix_close < 30
                    and technical_data["score"] < 0.8
                    and not any("TA: Breakout" in signal for signal in signals)
                ):
                    entry_blockers.append("No breakout pattern detected")

                # 3. Technical Weakness
                weak_tech_signals = analyzer.weak_technicals(signals)
                if weak_tech_signals is not None:
                    entry_blockers.append(f"{weak_tech_signals}")

                if entry_blockers:
                    logger.info(f"Entry blocked for {ticker}:")
                    for blocker in entry_blockers:
                        logger.info(f"- {blocker}")
                    continue

                # Calculate position size with sentiment data
                sentiment_data = {
                    "final_rank": stock["final_rank"],
                    "sentiment_rank": stock["sentiment_rank"],
                    "ta_rank": stock["ta_rank"],
                }

                shares, allow_trade = self.position_manager.calculate_target_position(
                    ticker,
                    technical_data["price"],
                    OrderSide.BUY,
                    target_pct=0.05,
                    technical_data=technical_data,
                    sentiment_data=sentiment_data,
                )

                if allow_trade and shares > 0:
                    try:
                        logger.info(
                            f"BUY {ticker}: Rank {stock['final_rank']:.1f} "
                            f"(Sentiment: {stock['sentiment_rank']:.1f}, TA: {stock['ta_rank']:.0f})"
                        )
                        logger.debug(f"Technical signals Daily at BUY: {technical_data['raw_data_daily'].to_string()}")
                        logger.debug(
                            f"Technical signals Intraday at BUY: {technical_data['raw_data_intraday'].to_string()}"
                        )
                        limit_price = self.position_manager.get_limit_price(ticker, OrderSide.BUY)
                        if limit_price:
                            self.position_manager.place_limit_order(ticker, shares, limit_price, side=OrderSide.BUY)
                        else:
                            self.position_manager.place_market_order(ticker, shares, side=OrderSide.BUY)
                    except Exception as e:
                        logger.error(f"Error placing order: {str(e)}", exc_info=True)
                else:
                    logger.info(f"SKIP {ticker}: Expanding current position requirements not met")
        else:
            logger.info(f"Skipping new positions - at max exposure ({self.position_manager.total_exposure:.1%})")

    def analyze_and_day_trade(self):
        """Main day-trading loop."""
        analyzer = TechnicalAnalyzer()
        scanner = SocialScanner()
        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Day Trading Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Day Trading Loop Starting - Market Status: {market_status} ===")

        # Get ranked stocks
        trending_stocks = scanner.get_trending_stocks(20)
        if trending_stocks.empty:
            return
        scanner.display_top_stocks(trending_stocks)

        # Run full trading cycle
        self.manage_existing_positions(analyzer, trending_stocks)
        self.find_new_opportunities(analyzer, trending_stocks)


def main():
    trader = DayTrader()
    trader.analyze_and_day_trade()


if __name__ == "__main__":
    main()
