import argparse
import os
import threading
import time

import schedule

from alpacalyzer.trading.alpaca_client import consume_trade_updates
from alpacalyzer.trading.trader import Trader
from alpacalyzer.utils.logger import logger
from alpacalyzer.utils.scheduler import start_scheduler


def main():  # pragma: no cover
    """
    The main function executes on commands.

    `uv run alpacalyzer`
    `--hedge` flag enables hedge fund trading mode.
    `--stream` flag enables Alpaca websocket streaming.

    Run hedge fund trader and monitor positions:
    1. Find opportunities every 2 minutes and 4 hours
    2. Save opportunity tickers in memory
    3. Run hedge fund every 5 minutes if new positions are available
    4. Create trading strategies for each ticker
    5. Monitor trading strategies every 2 minutes
    6. Enter and exit positions on signals
    """

    os.environ["TQDM_DISABLE"] = "1"
    parser = argparse.ArgumentParser(description="Run the trading bot with optional swing trading mode.")
    parser.add_argument("--stream", action="store_true", help="Enable websocket streaming")
    parser.add_argument("--analyze", action="store_true", help="Run in dry run mode (disables trading)")
    parser.add_argument("--tickers", type=str, help="Comma-separated list of tickers to analyze (e.g., AAPL,MSFT,GOOG)")
    args = parser.parse_args()

    try:
        if args.analyze:
            logger.info("ANALYZE MODE: Trading actions are disabled")

        # Parse tickers if provided
        direct_tickers = []
        if args.tickers:
            direct_tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")]
            logger.info(f"Analyzing provided tickers: {', '.join(direct_tickers)}")

        trader = Trader(analyze_mode=args.analyze, direct_tickers=direct_tickers)

        if not direct_tickers:
            # Run insight scanner every 4 hours
            safe_execute(trader.scan_for_insight_opportunities)
            schedule.every(4).hours.do(lambda: safe_execute(trader.scan_for_insight_opportunities))

            # Run momentum scanner every 4 minutes
            safe_execute(trader.scan_for_technical_opportunities)
            schedule.every(4).minutes.do(lambda: safe_execute(trader.scan_for_technical_opportunities))

        # Run hedge fund every 5 minutes
        safe_execute(trader.run_hedge_fund)
        schedule.every(5).minutes.do(lambda: safe_execute(trader.run_hedge_fund))

        # Monitor Trading strategies every 2 minutes (skip if analyze enabled)
        if not args.analyze:
            safe_execute(trader.monitor_and_trade)
            schedule.every(2).minutes.do(lambda: safe_execute(trader.monitor_and_trade))
        else:
            logger.info("Trading disabled in analyze mode - skipping monitor_and_trade")

        if args.stream:
            logger.info("Websocket Streaming Enabled")
            # Start streaming in a separate thread so it runs concurrently
            stream_thread = threading.Thread(target=consume_trade_updates, daemon=True)
            stream_thread.start()

        # Start the scheduler thread
        start_scheduler()

        # Keep main thread alive and handle graceful shutdown
        while True:
            time.sleep(10)

    except KeyboardInterrupt:
        logger.info("\nTrading bot stopped by user.")
    except Exception as e:
        logger.error(f"\nUnexpected error in main: {str(e)}", exc_info=True)
    finally:
        logger.info("Shutting down trading bot safely...")


def safe_execute(trading_function):
    """
    Safely executes trading function with error handling.

    Retries after 30 seconds if an error occurs.
    """
    try:
        trading_function()
    except Exception as e:
        logger.error(f"Error in trading function: {str(e)}", exc_info=True)
        logger.info("Retrying in 30 seconds...")
        time.sleep(30)


if __name__ == "__main__":
    main()
