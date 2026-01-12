"""Backtesting framework for strategy validation against historical data."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

import pandas as pd

from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer, TradingSignals
from alpacalyzer.data.api import get_price_data
from alpacalyzer.strategies.base import (
    EntryDecision,
    ExitDecision,
    MarketContext,
    Strategy,
)
from alpacalyzer.utils.logger import get_logger

if TYPE_CHECKING:
    from alpaca.trading.models import Position

logger = get_logger()


@dataclass
class BacktestTrade:
    """A single backtest trade."""

    ticker: str
    side: str
    entry_time: datetime
    entry_price: float
    exit_time: datetime | None = None
    exit_price: float | None = None
    quantity: int = 1
    strategy: str = ""

    @property
    def closed(self) -> bool:
        return self.exit_time is not None

    @property
    def pnl(self) -> float:
        if not self.closed or self.exit_price is None:
            return 0.0
        if self.side == "long":
            return (self.exit_price - self.entry_price) * self.quantity
        return (self.entry_price - self.exit_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        if not self.closed or self.exit_price is None:
            return 0.0
        if self.side == "long":
            return (self.exit_price - self.entry_price) / self.entry_price
        return (self.entry_price - self.exit_price) / self.entry_price

    @property
    def hold_duration(self) -> timedelta:
        if not self.closed or self.exit_time is None:
            return timedelta(0)
        assert self.exit_time is not None
        return self.exit_time - self.entry_time


@dataclass
class BacktestResult:
    """Results from a backtest run."""

    strategy: str
    ticker: str
    start_date: datetime
    end_date: datetime
    trades: list[BacktestTrade] = field(default_factory=list)

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def closed_trades(self) -> list[BacktestTrade]:
        return [t for t in self.trades if t.closed]

    @property
    def winning_trades(self) -> list[BacktestTrade]:
        return [t for t in self.closed_trades if t.pnl > 0]

    @property
    def losing_trades(self) -> list[BacktestTrade]:
        return [t for t in self.closed_trades if t.pnl <= 0]

    @property
    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        return len(self.winning_trades) / len(self.closed_trades)

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.closed_trades)

    @property
    def average_pnl(self) -> float:
        if not self.closed_trades:
            return 0.0
        return self.total_pnl / len(self.closed_trades)

    @property
    def average_win(self) -> float:
        if not self.winning_trades:
            return 0.0
        return sum(t.pnl for t in self.winning_trades) / len(self.winning_trades)

    @property
    def average_loss(self) -> float:
        if not self.losing_trades:
            return 0.0
        return sum(t.pnl for t in self.losing_trades) / len(self.losing_trades)

    @property
    def profit_factor(self) -> float:
        total_wins = sum(t.pnl for t in self.winning_trades)
        total_losses = abs(sum(t.pnl for t in self.losing_trades))
        if total_losses == 0:
            return float("inf") if total_wins > 0 else 0.0
        return total_wins / total_losses

    @property
    def sharpe_ratio(self) -> float:
        if len(self.closed_trades) < 2:
            return 0.0
        returns = [t.pnl_pct for t in self.closed_trades]
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance**0.5
        if std_dev == 0:
            return 0.0
        return (mean_return / std_dev) * (252**0.5)

    @property
    def max_drawdown(self) -> float:
        if not self.closed_trades:
            return 0.0

        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0

        for trade in self.closed_trades:
            cumulative += trade.pnl
            peak = max(peak, cumulative)
            drawdown = (peak - cumulative) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

        return max_dd

    def summary(self) -> str:
        """Generate a text summary of results."""
        return f"""Backtest Results: {self.strategy} on {self.ticker}
{"=" * 50}
Period: {self.start_date.date()} to {self.end_date.date()}
Total Trades: {self.total_trades}
Closed Trades: {len(self.closed_trades)}
Win Rate: {self.win_rate:.1%}
Total P/L: ${self.total_pnl:.2f}
Average P/L: ${self.average_pnl:.2f}
Average Win: ${self.average_win:.2f}
Average Loss: ${self.average_loss:.2f}
Profit Factor: {self.profit_factor:.2f}
Sharpe Ratio: {self.sharpe_ratio:.2f}
Max Drawdown: {self.max_drawdown:.1%}
"""


class Backtester:
    """
    Strategy backtesting engine.

    Usage:
        from alpacalyzer.strategies.momentum import MomentumStrategy

        strategy = MomentumStrategy()
        backtester = Backtester(strategy)

        result = backtester.run(
            ticker="AAPL",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
        )

        print(result.summary())
    """

    def __init__(self, strategy: Strategy):
        self.strategy = strategy
        self._ta = TechnicalAnalyzer()

    def run(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0,
    ) -> BacktestResult:
        """
        Run a backtest for a single ticker.

        Args:
            ticker: Stock symbol to backtest
            start_date: Start of backtest period
            end_date: End of backtest period
            initial_capital: Starting capital for position sizing

        Returns:
            BacktestResult with trade history and metrics
        """
        df = get_price_data(
            ticker,
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        if df.empty:
            logger.warning(f"No data available for {ticker}")
            return BacktestResult(
                strategy=getattr(self.strategy, "name", str(self.strategy)),
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
            )

        df = self._ta.calculate_daily_indicators(df)

        strategy_name = getattr(self.strategy, "name", str(self.strategy))
        result = BacktestResult(
            strategy=strategy_name,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
        )

        position: BacktestTrade | None = None

        for i, row in df.iterrows():
            timestamp = pd.Timestamp(row.name).to_pydatetime()  # type: ignore[arg-type]
            price = float(row["close"])

            if position and not position.closed:
                exit_decision = self._evaluate_exit(position, df.loc[:timestamp], price)
                if exit_decision.should_exit:
                    position.exit_time = timestamp
                    position.exit_price = price
                    result.trades.append(position)
                    position = None

            if position is None:
                entry_decision = self._evaluate_entry(ticker, df.loc[:timestamp], price)
                if entry_decision.should_enter:
                    quantity = int(initial_capital / price)
                    if quantity > 0:
                        side = "long"
                        if entry_decision.suggested_size > 0:
                            quantity = min(quantity, entry_decision.suggested_size)
                        position = BacktestTrade(
                            ticker=ticker,
                            side=side,
                            entry_time=timestamp,
                            entry_price=price,
                            quantity=quantity,
                            strategy=strategy_name,
                        )

        if position and not position.closed:
            position.exit_time = df.index[-1].to_pydatetime()
            position.exit_price = float(df.iloc[-1]["close"])
            result.trades.append(position)

        return result

    def _evaluate_entry(
        self,
        ticker: str,
        df: pd.DataFrame,
        price: float,
    ) -> EntryDecision:
        """Evaluate entry conditions using the strategy's evaluate_entry method."""
        latest = df.iloc[-1] if not df.empty else None
        if latest is None:
            return EntryDecision(should_enter=False, reason="No data available")

        signal: TradingSignals = {
            "symbol": ticker,
            "price": price,
            "atr": float(latest.get("ATR", 0)),
            "rvol": float(latest.get("RVOL", 1)),
            "signals": [],
            "raw_score": 0,
            "score": 0.5,
            "momentum": 0,
            "raw_data_daily": df,
            "raw_data_intraday": df,
        }

        context = MarketContext(
            vix=20.0,
            market_status="open",
            account_equity=10000.0,
            buying_power=10000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        try:
            decision = self.strategy.evaluate_entry(signal, context)
            if decision is None:
                return EntryDecision(should_enter=False, reason="Strategy returned None")
            return decision
        except Exception as e:
            logger.debug(f"Entry evaluation error: {e}")
            return EntryDecision(should_enter=False, reason=f"Evaluation error: {e}")

    def _evaluate_exit(
        self,
        position: BacktestTrade,
        df: pd.DataFrame,
        current_price: float,
    ) -> ExitDecision:
        """Evaluate exit conditions using the strategy's evaluate_exit method."""
        latest = df.iloc[-1] if not df.empty else None
        if latest is None:
            return ExitDecision(should_exit=False, reason="No data available")

        signal: TradingSignals = {
            "symbol": position.ticker,
            "price": current_price,
            "atr": float(latest.get("ATR", 0)),
            "rvol": float(latest.get("RVOL", 1)),
            "signals": [],
            "raw_score": 0,
            "score": 0.5,
            "momentum": 0,
            "raw_data_daily": df,
            "raw_data_intraday": df,
        }

        context = MarketContext(
            vix=20.0,
            market_status="open",
            account_equity=10000.0,
            buying_power=10000.0,
            existing_positions=[],
            cooldown_tickers=[],
        )

        mock_position = self._create_mock_position(position, current_price)

        try:
            decision = self.strategy.evaluate_exit(mock_position, signal, context)
            if decision is None:
                return ExitDecision(should_exit=False, reason="Strategy returned None")
            return decision
        except Exception as e:
            logger.debug(f"Exit evaluation error: {e}")
            return ExitDecision(should_exit=False, reason=f"Evaluation error: {e}")

    def _create_mock_position(
        self,
        trade: BacktestTrade,
        current_price: float,
    ) -> "Position":
        """Create a mock position object for strategy evaluation."""
        side = "long" if trade.side == "long" else "short"
        market_value = trade.quantity * current_price
        avg_entry_price = trade.entry_price
        unrealized_pl = (current_price - trade.entry_price) * trade.quantity if side == "long" else (trade.entry_price - current_price) * trade.quantity
        unrealized_plpc = unrealized_pl / market_value if market_value > 0 else 0

        return cast(
            "Position",
            {
                "symbol": trade.ticker,
                "side": side,
                "qty": trade.quantity,
                "avg_entry_price": avg_entry_price,
                "market_value": market_value,
                "unrealized_pl": unrealized_pl,
                "unrealized_plpc": unrealized_plpc,
            },
        )

    def run_multi(
        self,
        tickers: list[str],
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0,
    ) -> dict[str, BacktestResult]:
        """
        Run backtest for multiple tickers.

        Args:
            tickers: List of stock symbols
            start_date: Start of backtest period
            end_date: End of backtest period
            initial_capital: Starting capital per ticker

        Returns:
            Dictionary mapping ticker to BacktestResult
        """
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.run(ticker, start_date, end_date, initial_capital)
            except Exception as e:
                logger.error(f"Backtest failed for {ticker}: {e}")
        return results


def compare_strategies(
    strategies: list[Strategy],
    ticker: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = 10000.0,
) -> pd.DataFrame:
    """
    Compare multiple strategies on the same ticker.

    Args:
        strategies: List of strategy instances to compare
        ticker: Stock symbol to backtest
        start_date: Start of backtest period
        end_date: End of backtest period
        initial_capital: Starting capital

    Returns:
        DataFrame with comparison metrics for each strategy
    """
    results = []

    for strategy in strategies:
        try:
            backtester = Backtester(strategy)
            result = backtester.run(ticker, start_date, end_date, initial_capital)

            results.append(
                {
                    "Strategy": result.strategy,
                    "Trades": result.total_trades,
                    "Win Rate": f"{result.win_rate:.1%}",
                    "Total P/L": f"${result.total_pnl:.2f}",
                    "Sharpe": f"{result.sharpe_ratio:.2f}",
                    "Max DD": f"{result.max_drawdown:.1%}",
                    "Profit Factor": f"{result.profit_factor:.2f}",
                }
            )
        except Exception as e:
            logger.error(f"Backtest failed for {getattr(strategy, 'name', strategy)}: {e}")

    return pd.DataFrame(results)
