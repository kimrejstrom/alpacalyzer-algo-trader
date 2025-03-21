import argparse
import threading
import time

import schedule

from alpacalyzer.db.db import init_db
from alpacalyzer.hedge_fund import run_hedge_fund
from alpacalyzer.trading.alpaca_client import consume_trade_updates
from alpacalyzer.trading.day_trader import DayTrader
from alpacalyzer.trading.swing_trader import SwingTrader
from alpacalyzer.utils.logger import logger
from alpacalyzer.utils.scheduler import start_scheduler


def main():  # pragma: no cover
    """
    The main function executes on commands.

    `python -m alpacalyzer` and `$ alpacalyzer `.
    `--swing` flag enables swing trading mode.
    `--day` flag enables day trading mode.

    This is your program's entry point.

    Run trader and monitor positions:
    1. Place initial orders
    2. Monitor every 5 minutes
    3. Exit positions on signals
    4. Place new orders as needed
    """

    parser = argparse.ArgumentParser(description="Run the trading bot with optional swing trading mode.")
    parser.add_argument("--swing", action="store_true", help="Enable swing trading mode")
    parser.add_argument("--day", action="store_true", help="Enable day trading mode")
    parser.add_argument("--stream", action="store_true", help="Enable websocket streaming")
    args = parser.parse_args()
    init_db()

    try:
        if args.stream:
            logger.info("Websocket Streaming Enabled")
            # Start streaming in a separate thread so it runs concurrently
            stream_thread = threading.Thread(target=consume_trade_updates, daemon=True)
            stream_thread.start()

        if args.swing:
            logger.info("Swing Trading Mode Enabled")
            swing_trader = SwingTrader()

            # Execute immediately
            safe_execute(swing_trader.analyze_and_swing_trade)
            schedule.every(4).hours.do(lambda: safe_execute(swing_trader.analyze_and_swing_trade))

            # Run immediately & schedule every 1 minutes
            safe_execute(swing_trader.monitor_and_trade)
            schedule.every(60).seconds.do(lambda: safe_execute(swing_trader.monitor_and_trade))

        if args.day:
            logger.info("Day Trading Mode Enabled")
            day_trader = DayTrader()

            # Execute immediately
            safe_execute(day_trader.analyze_and_day_trade)

            schedule.every(2).minutes.do(lambda: safe_execute(day_trader.analyze_and_day_trade))

        if args.hedge:
            # New trading flow
            # Run opportunity scanners every 2 minutes and 4 hours
            # Saves opportunity tickers in memory
            # Run hedge fund every 5 minutes if new positions are available
            # Creates trading strategies for each ticker
            # Monitor trading strategies every 2 minutes
            # Execute trading strategies

            # New exit flow
            # Monitor positions every 2 minutes
            # Exit positions on signals
            logger.info("Hedge Fund Mode Enabled")

            # Execute immediately
            swing_trader = SwingTrader()
            safe_execute(swing_trader.analyze_and_swing_trade)
            schedule.every(4).hours.do(lambda: safe_execute(swing_trader.analyze_and_swing_trade))

            # Execute immediately
            day_trader = DayTrader()
            safe_execute(day_trader.analyze_and_day_trade)
            schedule.every(2).minutes.do(lambda: safe_execute(day_trader.analyze_and_day_trade))

            # Run hedge fund every 5 minutes
            schedule.every(5).minutes.do(lambda: safe_execute(run_hedge_fund))

            # Monitor Trading strategies every 2 minutes
            schedule.every(2).minutes.do(lambda: safe_execute(swing_trader.monitor_and_trade))

            # Monitor positions every 2 minutes
            schedule.every(2).minutes.do(lambda: safe_execute(day_trader.manage_existing_positions))

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
