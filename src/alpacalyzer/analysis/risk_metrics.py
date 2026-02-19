"""Risk-adjusted performance metrics for strategy evaluation."""

TRADING_DAYS_PER_YEAR = 252


def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> float:
    """
    Calculate the Sharpe ratio.

    Args:
        returns: List of periodic returns (e.g., daily returns).
        risk_free_rate: Risk-free rate for the same period as returns.
        annualize: Whether to annualize the ratio (multiply by sqrt(252)).

    Returns:
        Sharpe ratio. Returns 0.0 if volatility is zero or returns list is empty.
    """
    if not returns:
        return 0.0

    import statistics

    mean_return = statistics.mean(returns)
    std_dev = statistics.stdev(returns) if len(returns) > 1 else 0.0

    if std_dev == 0.0:
        return 0.0

    excess_return = mean_return - risk_free_rate
    sharpe = excess_return / std_dev

    if annualize:
        sharpe *= TRADING_DAYS_PER_YEAR**0.5

    return sharpe


def calculate_sortino_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    annualize: bool = True,
) -> float:
    """
    Calculate the Sortino ratio (only penalizes downside volatility).

    Args:
        returns: List of periodic returns (e.g., daily returns).
        risk_free_rate: Risk-free rate for the same period as returns.
        annualize: Whether to annualize the ratio (multiply by sqrt(252)).

    Returns:
        Sortino ratio. Returns 0.0 if returns list is empty.
        Returns a high positive value if no downside deviation but positive excess return.
    """
    if not returns:
        return 0.0

    import math

    mean_return = sum(returns) / len(returns)
    downside_returns = [min(r - risk_free_rate, 0) for r in returns]

    if not downside_returns or all(r == 0 for r in downside_returns):
        excess_return = mean_return - risk_free_rate
        if excess_return > 0:
            return float("inf") if annualize else excess_return
        return 0.0

    downside_variance = sum(r**2 for r in downside_returns) / len(returns)
    downside_deviation = math.sqrt(downside_variance)

    if downside_deviation == 0.0:
        return 0.0

    excess_return = mean_return - risk_free_rate
    sortino = excess_return / downside_deviation

    if annualize:
        sortino *= TRADING_DAYS_PER_YEAR**0.5

    return sortino


def calculate_calmar_ratio(
    returns: list[float],
    max_drawdown: float,
    annualize: bool = True,
) -> float:
    """
    Calculate the Calmar ratio (annual return / max drawdown).

    Args:
        returns: List of periodic returns (e.g., daily returns).
        max_drawdown: Maximum drawdown as a positive decimal (e.g., 0.15 for 15%).
        annualize: Whether to annualize the return (multiply by 252).

    Returns:
        Calmar ratio. Returns 0.0 if max_drawdown is zero or returns list is empty.
    """
    if not returns or max_drawdown <= 0.0:
        return 0.0

    cumulative_return = 1.0
    for r in returns:
        cumulative_return *= 1 + r

    total_return = cumulative_return - 1

    if annualize:
        annualized_return = ((1 + total_return) ** (TRADING_DAYS_PER_YEAR / len(returns))) - 1
    else:
        annualized_return = total_return

    return annualized_return / max_drawdown


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """
    Calculate maximum drawdown from an equity curve.

    Args:
        equity_curve: List of equity values over time.

    Returns:
        Maximum drawdown as a positive decimal (e.g., 0.20 for 20%).
        Returns 0.0 if the list is empty or has one element.
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for value in equity_curve:
        if value > peak:
            peak = value
        drawdown = (peak - value) / peak
        if drawdown > max_dd:
            max_dd = drawdown

    return max_dd
