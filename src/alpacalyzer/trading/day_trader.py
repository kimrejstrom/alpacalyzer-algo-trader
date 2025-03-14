from datetime import UTC, datetime

from alpaca.trading.enums import OrderSide

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.scanners.social_scanner import SocialScanner
from alpacalyzer.trading.alpaca_client import get_account_info, get_market_status
from alpacalyzer.trading.position_manager import PositionManager
from alpacalyzer.trading.yfinance_client import YFinanceClient
from alpacalyzer.utils.logger import logger


class DayTrader:
    def __init__(self):
        self.position_manager = PositionManager(max_position_size=0.05, max_total_exposure=0.5, strategy="day")
        self.yfinance_client = YFinanceClient()
        self.technical_analyzer = TechnicalAnalyzer()
        self.social_scanner = SocialScanner()

    def manage_existing_positions(self):
        """Manage existing positions."""
        # Update positions
        current_positions = self.position_manager.update_positions()
        if not current_positions:
            return

        # Check each position for exit signals
        for symbol in list(current_positions.keys()):
            technical_data = self.technical_analyzer.analyze_stock(symbol)

            if not technical_data:
                logger.warning(f"Technical data missing for {symbol}")
                continue

            if self.should_close_position(symbol, technical_data):
                self.position_manager.close_position(symbol)

        # Check for over exposure
        if self.position_manager.get_total_exposure() > self.position_manager.max_total_exposure:
            logger.info(
                f"\nOver exposure detected ({self.position_manager.total_exposure:.1%}) - closing worst positions"
            )
            self.handle_over_exposure()

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

    def find_new_opportunities(self, trending_stocks):
        """Find and execute new trades."""

        # Update positions and orders silently
        self.position_manager.update_pending_orders()

        # Get top 10 stocks
        top_stocks = trending_stocks.head(10)

        # Get pending orders
        pending_orders = {order["symbol"] for order in self.position_manager.pending_orders}

        # Get VIX
        vix_close = self.yfinance_client.get_vix()

        # Enter new positions only if not at max exposure
        if self.position_manager.get_total_exposure() >= self.position_manager.max_total_exposure:
            logger.info(f"Skipping new positions - at max exposure ({self.position_manager.total_exposure:.1%})")
            return

        # TODO refactor this block into a separate method
        for _, stock in top_stocks.iterrows():
            ticker = stock["ticker"]

            entry_blockers = []

            logger.info(f"\nEvaluating entry for {ticker}")
            # Skip if we already have a pending order
            if ticker in pending_orders:
                entry_blockers.append("Pending order already exists")
                continue

            technical_data = self.technical_analyzer.analyze_stock(ticker)
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
                entry_blockers.append(f"Technical data too weak: {technical_data['score']:.2f} < {ta_threshold:.2f}")

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
            weak_tech_signals = self.technical_analyzer.weak_technicals(signals, OrderSide.BUY)
            if weak_tech_signals is not None:
                entry_blockers.append(f"{weak_tech_signals}")

            if entry_blockers:
                logger.info(f"Entry blocked for {ticker}:")
                for blocker in entry_blockers:
                    logger.info(f"- {blocker}")
                continue

            # TODO refactor this block into a separate method
            shares, allow_trade = self.position_manager.calculate_target_position(
                ticker,
                technical_data["price"],
                technical_data,
            )

            if not allow_trade and shares <= 0:
                logger.info(f"SKIP {ticker}: Expanding current position requirements not met")
                continue

            try:
                logger.info(
                    f"BUY {ticker}: Rank {stock['final_rank']:.1f} "
                    f"(Sentiment: {stock['sentiment_rank']:.1f}, TA: {stock['ta_rank']:.0f})"
                )
                logger.debug(f"Technical signals Daily at BUY: {technical_data['raw_data_daily'].iloc[-2].to_string()}")
                logger.debug(
                    f"Technical signals Intraday at BUY: {technical_data['raw_data_intraday'].iloc[-2].to_string()}"
                )
                limit_price = self.position_manager.get_limit_price(OrderSide.BUY, technical_data)
                if limit_price:
                    self.position_manager.place_limit_order(ticker, shares, limit_price, side=OrderSide.BUY)
                else:
                    self.position_manager.place_market_order(ticker, shares, side=OrderSide.BUY)
            except Exception as e:
                logger.error(f"Error placing order: {str(e)}", exc_info=True)

    def should_close_position(self, symbol: str, technical_data: TradingSignals):
        """Determine if a position should be closed based on technical analysis."""
        position = self.position_manager.positions.get(symbol)
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
                exit_signals.append(f"Hard stop: {position.pl_pct:.1%} loss")

            # 2. Big profit + reversal (lock in gains)
            if position.pl_pct > 0.075 and position.drawdown < -5:
                exit_signals.append(
                    f"Profit lock: {position.drawdown:.1f}% drop from high while +{position.pl_pct:.1%} up"
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
            weak_tech_signals = self.technical_analyzer.weak_technicals(signals, OrderSide.SELL)
            if weak_tech_signals is not None:
                exit_signals.append(weak_tech_signals)

        # 5. Mediocre performance with significant age
        position_age = (datetime.now(UTC) - position.entry_time).days
        if position_age > 1:  # At least 1 day old
            if (
                score < 0.6  # Weaker technicals
                and abs(position.pl_pct) < 0.03  # Little movement
            ):
                exit_signals.append(f"Stale position ({position_age:.1f}h old and weak technicals)")

        # 6. Stagnant position
        if position_age > 3 and abs(position.pl_pct) < 0.01:
            exit_signals.append(f"Stagnant position after {position_age} days")

        # Check if any exit signals triggered
        if exit_signals:
            reason_str = ", ".join(exit_signals)
            # Store exit reason to block immediate re-entry
            self.position_manager.exited_positions[symbol] = {
                "reason": reason_str,
                "timestamp": datetime.now(UTC),
            }
            logger.info(f"\nSELL {symbol} due to: {reason_str}")
            logger.info(f"Position details: {position}")
            logger.debug(f"Technical signals Daily at SELL: {technical_data['raw_data_daily'].iloc[-2].to_string()}")
            logger.debug(
                f"Technical signals Intraday at SELL: {technical_data['raw_data_intraday'].iloc[-2].to_string()}"
            )
            if position.pl_pct < 0:
                logger.info(f"LOSS: {position.pl_pct:.1%} P&L loss on trade")
            else:
                logger.info(f"WIN: {position.pl_pct:.1%} P&L gain on trade")
            return True

        return False

    def handle_over_exposure(self):
        # Get rankings for current positions
        tickers_list = list(self.position_manager.positions.keys())
        ranked_positions = self.social_scanner.rank_stocks(tickers_list, limit=len(tickers_list))

        # add position.pl_pct to the ranked_positions
        for symbol, position in self.position_manager.positions.items():
            ranked_positions.loc[ranked_positions["ticker"] == symbol, "pl_pct"] = position.pl_pct

        # Sort ranked_positions by final_rank and pl_pct (negative is worst)
        # in descending order to sell the worst-ranked positions first
        ranked_positions = ranked_positions.sort_values(by=["final_rank", "pl_pct"], ascending=[False, False])

        logger.debug("\nSorted Positions:")
        for _, row in ranked_positions.iterrows():
            logger.debug(f"{row['ticker']}: Rank {row['final_rank']:.2f}, P&L: {row['pl_pct']:.1%}")

        # Calculate over-exposure
        over_exposure = self.position_manager.get_total_exposure() - self.position_manager.max_total_exposure
        logger.info(
            f"Current total exposure: {self.position_manager.total_exposure:.1%}, Over-exposure: {over_exposure:.1%}"
        )
        account = get_account_info()

        # Iterate through the worst-ranked positions until over_exposure is resolved
        for _, row in ranked_positions.iterrows():
            # Get the current position for the ticker
            current_position = self.position_manager.positions.get(row["ticker"])

            if current_position is not None:  # Ensure the position exists
                position_exposure = current_position.get_exposure(account["equity"])  # Get the exposure of the position
                logger.info(
                    f"SELL {row['ticker']} due to: Over exposure - sell worst-ranked positions"
                    f" (Rank {row['final_rank']:.1f})."
                )

                # Close the position
                self.position_manager.close_position(row["ticker"])

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

    def analyze_and_day_trade(self):
        """Main day-trading loop."""
        market_status = get_market_status()

        if market_status == "closed":
            logger.info(f"=== Day Trading Loop Paused - Market Status: {market_status} ===")
            return

        logger.info(f"\n=== Day Trading Loop Starting - Market Status: {market_status} ===")

        # Get ranked stocks
        trending_stocks = self.social_scanner.get_trending_stocks(20)
        if trending_stocks.empty:
            return
        self.social_scanner.display_top_stocks(trending_stocks)

        # Run full trading cycle
        self.manage_existing_positions()
        self.find_new_opportunities(trending_stocks)


def main():
    trader = DayTrader()
    trader.analyze_and_day_trade()


if __name__ == "__main__":
    main()
