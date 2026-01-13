import argparse
import os
import threading
import time
from datetime import datetime, timedelta

import schedule

from alpacalyzer.analysis.dashboard import dashboard_command
from alpacalyzer.analysis.eod_performance import EODPerformanceAnalyzer
from alpacalyzer.trading.alpaca_client import consume_trade_updates, get_market_close_time, liquidate_all_positions
from alpacalyzer.trading.trader import Trader
from alpacalyzer.utils.logger import get_logger
from alpacalyzer.utils.scheduler import start_scheduler

logger = get_logger()


def schedule_daily_liquidation():
    """Schedules a daily liquidation of all positions 5 minutes before market close."""
    close_time = get_market_close_time()
    if close_time:
        # Convert market close time to local timezone
        liquidation_time_utc = close_time - timedelta(minutes=5)
        liquidation_time_local = liquidation_time_utc.astimezone()  # Convert to local timezone
        liquidation_time_str = liquidation_time_local.strftime("%H:%M")
        schedule.every().day.at(liquidation_time_str).do(liquidate_all_positions)
        logger.info(f"Scheduled daily liquidation at {liquidation_time_str} local time")
    else:
        logger.info("Not a trading day, no liquidation scheduled.")


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
    parser = argparse.ArgumentParser(description="Run the trading bot with options.")
    parser.add_argument("--stream", action="store_true", help="Enable websocket streaming")
    parser.add_argument("--analyze", action="store_true", help="Run in dry run mode (disables trading)")
    parser.add_argument("--tickers", type=str, help="Comma-separated list of tickers to analyze (e.g., AAPL,MSFT,GOOG)")
    parser.add_argument("--agents", type=str, default="ALL", help="Comma-separated list of agents to use (e.g., ALL,TRADE,INVEST)")
    parser.add_argument("--ignore-market-status", action="store_true", help="Ignore market status and trade at any time")
    parser.add_argument("--strategy", type=str, help="Trading strategy to use from registry (e.g., momentum, breakout)")
    parser.add_argument("--new-engine", action="store_true", help="Use new ExecutionEngine (experimental)")
    # EOD analyzer options
    parser.add_argument("--eod-analyze", action="store_true", help="Run End-of-Day analyzer and exit")
    parser.add_argument("--eod-date", type=str, help="EET date (YYYY-MM-DD) to analyze; defaults to today")
    parser.add_argument("--eod-threshold", type=float, default=1.0, help="Threshold percent (default 1.0)")
    parser.add_argument("--eod-timeframe", type=str, default="5Min", help="Bar timeframe (e.g., 5Min)")
    # Dashboard options
    parser.add_argument("--dashboard", action="store_true", help="Display strategy performance dashboard")
    parser.add_argument("--ticker", type=str, help="Ticker symbol to analyze with dashboard")
    parser.add_argument("--strategy", type=str, help="Strategy name for detailed dashboard backtest")
    parser.add_argument("--days", type=int, default=30, help="Number of days of historical data for dashboard")
    parser.add_argument("--conditions", action="store_true", help="Show market conditions analysis in dashboard")
    args = parser.parse_args()

    try:
        # Run the dashboard and exit if requested
        if args.dashboard:
            logger.info("Running Strategy Performance Dashboard")
            dashboard_command(
                ticker=args.ticker,
                strategy=args.strategy,
                days=args.days,
                conditions=args.conditions,
            )
            return

        # Run the EOD analyzer and exit if requested
        if args.eod_analyze:
            logger.info("Running End-of-Day Performance Analyzer")
            target_date = None
            if args.eod_date:
                try:
                    target_date = datetime.strptime(args.eod_date, "%Y-%m-%d").date()
                except ValueError:
                    logger.error("Invalid --eod-date format. Use YYYY-MM-DD.")
                    return
            analyzer = EODPerformanceAnalyzer(
                threshold_pct=args.eod_threshold,
                timeframe=args.eod_timeframe,
            )
            report_path = analyzer.run(target_date)
            logger.info(f"EOD analysis complete: {report_path}")
            return

        if args.analyze:
            logger.info("ANALYZE MODE: Trading actions are disabled")

        # Parse tickers if provided
        direct_tickers = []
        if args.tickers:
            direct_tickers = [ticker.strip().upper() for ticker in args.tickers.split(",")]
            logger.info(f"Analyzing provided tickers: {', '.join(direct_tickers)}")

        trader = Trader(
            analyze_mode=args.analyze,
            direct_tickers=direct_tickers,
            agents=args.agents,
            ignore_market_status=args.ignore_market_status,
        )

        # Schedule daily liquidation
        safe_execute(schedule_daily_liquidation)

        if not direct_tickers:
            # Run insight scanner every 4 hours
            safe_execute(trader.scan_for_insight_opportunities)
            schedule.every(4).hours.do(lambda: safe_execute(trader.scan_for_insight_opportunities))

            # Run momentum scanner every 4 minutes
            safe_execute(trader.scan_for_technical_opportunities)
            schedule.every(4).minutes.do(lambda: safe_execute(trader.scan_for_technical_opportunities))

        # Choose between old Trader and new ExecutionEngine
        if args.new_engine:
            logger.info("Using new ExecutionEngine for trade execution")
            from alpacalyzer.execution.engine import ExecutionConfig, ExecutionEngine
            from alpacalyzer.strategies.momentum import MomentumStrategy

            # Create strategy and engine
            strategy_instance = MomentumStrategy()
            engine_config = ExecutionConfig(analyze_mode=args.analyze)
            execution_engine = ExecutionEngine(strategy_instance, engine_config)

            # Create a function that feeds signals from trader to engine
            def run_hedge_fund_with_signals():
                """Run hedge fund and feed signals to execution engine."""
                trader.run_hedge_fund()
                signals = trader.get_signals_from_strategies()
                for signal in signals:
                    execution_engine.add_signal(signal)

            # Schedule hedge fund with signal feeding (only once)
            safe_execute(run_hedge_fund_with_signals)
            schedule.every(5).minutes.do(lambda: safe_execute(run_hedge_fund_with_signals))

            # Schedule engine cycles every 2 minutes
            safe_execute(execution_engine.run_cycle)
            schedule.every(2).minutes.do(lambda: safe_execute(execution_engine.run_cycle))
        else:
            # Original Trader behavior
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
