"""
Strategy Performance Dashboard.

This module provides a CLI dashboard for comparing trading strategies,
viewing backtest results, and analyzing market conditions.
"""

from datetime import datetime, timedelta

import pandas as pd
from colorama import Fore, Style
from tabulate import tabulate

from alpacalyzer.backtesting.backtester import Backtester, compare_strategies
from alpacalyzer.data.api import get_price_data
from alpacalyzer.strategies.registry import StrategyRegistry
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


def print_header(title: str) -> None:
    """Print a formatted header."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 60}{Style.RESET_ALL}\n")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{Fore.YELLOW}{message}{Style.RESET_ALL}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{Fore.RED}{message}{Style.RESET_ALL}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"{Fore.WHITE}{message}{Style.RESET_ALL}")


def print_table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    """Print a formatted table."""
    if not rows:
        print_warning(f"No data for {title}")
        return

    print(f"{Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}")
    # Calculate colalign based on number of columns
    num_cols = len(headers) if headers else (len(rows[0]) if rows else 0)
    if num_cols == 0:
        return

    # Default to left alignment for all columns
    colalign = tuple(["left"] * num_cols)
    print(
        tabulate(
            rows,
            headers=headers,
            tablefmt="grid",
            colalign=colalign,
        )
    )


class StrategyDashboard:
    """
    Performance dashboard for strategy analysis.

    Usage:
        dashboard = StrategyDashboard()
        dashboard.show_overview()
        dashboard.compare_on_ticker("AAPL", days=30)
    """

    def __init__(self):
        """Initialize the dashboard with strategy registry."""
        self.registry = StrategyRegistry()

    def show_overview(self) -> None:
        """Show overview of all registered strategies."""
        strategies = self.registry.list_strategies()

        if not strategies:
            print_warning("No strategies registered in the registry.")
            return

        headers = ["Name", "Type", "Risk/Trade", "Status"]
        rows = []

        for name in strategies:
            try:
                strategy = self.registry.get(name)
                config = strategy.config

                strategy_type = type(strategy).__name__
                risk_pct = f"{config.risk_pct_per_trade:.1%}" if config.risk_pct_per_trade else "N/A"
                status = "Active" if getattr(strategy, "enabled", True) else "Disabled"

                rows.append([name, strategy_type, risk_pct, status])
            except Exception as e:
                logger.debug(f"Error getting strategy info for {name}: {e}")
                rows.append([name, "Error", "N/A", "Error"])

        print_table(f"Registered Strategies ({len(strategies)})", headers, rows)

    def compare_on_ticker(
        self,
        ticker: str,
        days: int = 30,
    ) -> None:
        """
        Compare all strategies on a single ticker.

        Args:
            ticker: Stock symbol to compare strategies on
            days: Number of days of historical data to use
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        ticker_upper = ticker.upper()

        print_header(f"Comparing strategies on {ticker_upper}")
        print_info(f"Period: {start_date.date()} to {end_date.date()}")

        strategies = []
        strategy_names = self.registry.list_strategies()

        if not strategy_names:
            print_warning("No strategies registered in the registry.")
            return

        for name in strategy_names:
            try:
                strategy = self.registry.get(name)
                strategies.append(strategy)
            except Exception as e:
                logger.debug(f"Error loading strategy {name}: {e}")

        if not strategies:
            print_warning("No strategies could be loaded.")
            return

        try:
            comparison = compare_strategies(
                strategies=strategies,
                ticker=ticker_upper,
                start_date=start_date,
                end_date=end_date,
            )

            if comparison.empty:
                print_warning(f"No backtest results available for {ticker_upper}")
                return

            # Convert DataFrame to list of lists for display
            headers = list(comparison.columns)
            rows = comparison.values.tolist()

            print_table(f"Strategy Performance: {ticker.upper()}", headers, rows)

            # Show recommendation
            if "Win Rate" in comparison.columns:
                win_rates = comparison["Win Rate"].astype(str).str.rstrip("%")
                win_rates = pd.to_numeric(win_rates, errors="coerce")
                if not win_rates.empty and not win_rates.isna().all():
                    best_idx = win_rates.idxmax()
                    best = comparison.loc[best_idx]
                    best_strategy = best.get("Strategy", "Unknown")
                    best_win_rate = best.get("Win Rate", "N/A")
                    print_success(f"\nRecommended: {best_strategy} ({best_win_rate} win rate)")

        except Exception as e:
            print_error(f"Error running strategy comparison: {e}")
            logger.debug(f"Comparison error details: {e}")

    def show_backtest_detail(
        self,
        strategy_name: str,
        ticker: str,
        days: int = 30,
    ) -> None:
        """
        Show detailed backtest results for a strategy.

        Args:
            strategy_name: Name of the strategy to backtest
            ticker: Stock symbol to backtest on
            days: Number of days of historical data to use
        """
        try:
            strategy = self.registry.get(strategy_name)
        except ValueError:
            print_error(f"Strategy not found: {strategy_name}")
            return

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            backtester = Backtester(strategy)
            result = backtester.run(ticker.upper(), start_date, end_date)

            # Show summary
            summary = result.summary()
            print_header(f"Backtest: {strategy_name} on {ticker.upper()}")
            print_info(summary)

            # Show trade list
            if result.closed_trades:
                headers = ["Entry Time", "Exit Time", "Side", "Entry", "Exit", "P/L", "P/L %"]
                rows = []

                for trade in result.closed_trades:
                    entry_str = trade.entry_time.strftime("%Y-%m-%d %H:%M") if trade.entry_time else "N/A"
                    exit_str = trade.exit_time.strftime("%Y-%m-%d %H:%M") if trade.exit_time else "N/A"
                    entry_price = f"${trade.entry_price:.2f}" if trade.entry_price else "N/A"
                    exit_price = f"${trade.exit_price:.2f}" if trade.exit_price else "N/A"
                    pnl = f"${trade.pnl:.2f}" if trade.pnl is not None else "N/A"
                    pnl_pct = f"{trade.pnl_pct:.2%}" if trade.pnl_pct is not None else "N/A"

                    rows.append([entry_str, exit_str, trade.side.upper(), entry_price, exit_price, pnl, pnl_pct])

                print_table("Trade History", headers, rows)
            else:
                print_info("No closed trades in this backtest period.")

        except Exception as e:
            print_error(f"Error running backtest: {e}")
            logger.debug(f"Backtest error details: {e}")

    def show_market_conditions(self) -> None:
        """Show current market conditions and recommended strategies."""
        print_header("Market Conditions Analysis")

        try:
            # Analyze SPY for market regime
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            spy_df = get_price_data("SPY", start_date, end_date)

            if spy_df.empty or "close" not in spy_df.columns:
                print_warning("Unable to fetch market data (SPY)")
                return

            # Calculate metrics
            close_prices = spy_df["close"]
            sma_20 = close_prices.tail(20).mean() if len(close_prices) >= 20 else close_prices.iloc[-1]
            sma_50 = close_prices.tail(50).mean() if len(close_prices) >= 50 else sma_20
            current = close_prices.iloc[-1]

            # Calculate volatility (standard deviation as % of price)
            returns = close_prices.pct_change().dropna()
            volatility = returns.std() * 100 if len(returns) > 0 else 0

            # Determine regime based on price relative to SMAs and volatility
            # Volatility threshold of 2% indicates elevated market uncertainty
            if current > sma_20 > sma_50:
                regime = "Uptrend"
                recommended = ["momentum", "breakout"]
            elif current < sma_20 < sma_50:
                regime = "Downtrend"
                recommended = ["mean_reversion"]
            elif volatility > 2:
                # >2% daily std dev suggests choppy/uncertain market
                regime = "High Volatility"
                recommended = ["mean_reversion"]
            else:
                regime = "Sideways/Ranging"
                recommended = ["mean_reversion", "breakout"]

            print_info(f"Market Regime: {regime}")
            print_info(f"SPY: ${current:.2f} (SMA20: ${sma_20:.2f}, SMA50: ${sma_50:.2f})")
            print_info(f"Volatility: {volatility:.2f}%")
            print_success(f"Recommended Strategies: {', '.join(recommended)}")

        except Exception as e:
            print_error(f"Error analyzing market conditions: {e}")
            logger.debug(f"Market conditions error details: {e}")


def dashboard_command(
    ticker: str | None = None,
    strategy: str | None = None,
    days: int = 30,
    conditions: bool = False,
) -> None:
    """
    Display strategy performance dashboard.

    Usage:
        alpacalyzer dashboard                    # Show overview
        alpacalyzer dashboard --ticker AAPL      # Compare strategies on AAPL
        alpacalyzer dashboard --strategy momentum --ticker AAPL  # Detailed backtest
        alpacalyzer dashboard --conditions       # Market conditions

    Args:
        ticker: Optional ticker symbol to analyze
        strategy: Optional strategy name for detailed backtest
        days: Number of days of historical data (default: 30)
        conditions: If True, show market conditions analysis
    """
    dashboard = StrategyDashboard()

    if conditions:
        dashboard.show_market_conditions()
    elif strategy and ticker:
        dashboard.show_backtest_detail(strategy, ticker, days)
    elif ticker:
        dashboard.compare_on_ticker(ticker, days)
    else:
        dashboard.show_overview()
