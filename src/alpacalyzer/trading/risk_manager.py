import json
from typing import cast

from alpaca.trading.models import Position
from langchain_core.messages import HumanMessage

from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.trading.alpaca_client import get_account_info, get_current_price, trading_client
from alpacalyzer.utils.logger import get_logger
from alpacalyzer.utils.progress import progress

logger = get_logger()


"""Risk Management Agent.

Calculates position limits and buying power adjustments for trading decisions.

Position Sizing Rules:
- DYNAMIC SIZING (primary): Based on ATR and VIX
  * Base risk: 2% of portfolio equity
  * VIX scaling: VIX=20 (no reduction), VIX=30 (33% reduction), VIX=40 (50% reduction)
  * Shares = Risk Amount / (2 * ATR)  // ATR determines stop loss distance
  * Capped at 5% max position size
- FIXED SIZING (fallback): 5% of portfolio equity
  * Used when ATR unavailable or calculation fails

Margin Calculation:
- Margin requirement derived from Alpaca account multiplier
- Reg-T accounts: multiplier=2 → requirement=0.5 (50%)
- Portfolio margin: multiplier=4 → requirement=0.25 (25%)
- Short capacity = day_trading_BP / margin_requirement
- Example: $10k / 0.5 = $20k short capacity (Reg-T)
- Example: $10k / 0.25 = $40k short capacity (Portfolio margin)

Safety Factor:
- 90% of available buying power used
- Accounts for price movements between analysis and execution
"""

DEFAULT_MARGIN_REQUIREMENT = 0.5  # Fallback for Reg-T accounts


def get_margin_requirement(account: dict[str, float | int]) -> float:
    """
    Derive margin requirement from Alpaca account multiplier.

    Args:
        account: Account info dict containing margin_multiplier

    Returns:
        Margin requirement as decimal (e.g., 0.5 for 50%)

    Examples:
        - Reg-T (2x multiplier): 1/2 = 0.5 (50% requirement)
        - Portfolio margin (4x): 1/4 = 0.25 (25% requirement)
        - Portfolio margin (6x): 1/6 ≈ 0.167 (16.7% requirement)
    """
    multiplier = account.get("margin_multiplier", 0)
    if multiplier and multiplier > 0:
        return 1.0 / float(multiplier)
    return DEFAULT_MARGIN_REQUIREMENT


def get_stock_atr(ticker: str, period: int = 14) -> float | None:
    """
    Fetch ATR for a stock.

    Args:
        ticker: Stock symbol
        period: ATR period (default 14)

    Returns:
        ATR value or None if unavailable
    """
    try:
        from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer

        ta = TechnicalAnalyzer()
        signals = ta.analyze_stock(ticker)
        if signals is not None and "atr" in signals:
            return float(signals["atr"])
        return None
    except Exception as e:
        logger.warning(f"Failed to fetch ATR for {ticker}: {e}")
        return None


def calculate_dynamic_position_size(
    ticker: str,
    portfolio_equity: float,
    vix: float | None = None,
    base_risk_pct: float = 0.02,
    max_position_pct: float = 0.05,
) -> float:
    """
    Calculate position size based on volatility.

    Args:
        ticker: Stock symbol
        portfolio_equity: Total portfolio value
        vix: Current VIX (optional)
        base_risk_pct: Base risk per trade (default 2%)
        max_position_pct: Maximum position size (default 5%)

    Returns:
        Position dollar amount

    Formula:
        1. Calculate base risk amount (equity * base_risk_pct)
        2. Adjust for VIX (divide by 1 + vix_factor)
        3. Get ATR for stock
        4. Calculate shares = risk / (2 * ATR)
        5. Position size = shares * price
        6. Cap at max_position_pct
    """
    risk_amount = portfolio_equity * base_risk_pct

    if vix is not None:
        vix_factor = max(0, (vix - 20) / 20)
        risk_amount = risk_amount / (1 + vix_factor)

    atr = get_stock_atr(ticker)
    if atr is None or atr == 0:
        logger.warning(f"ATR unavailable for {ticker}, using fixed position size")
        return portfolio_equity * max_position_pct

    price = get_current_price(ticker)
    if price is None or price == 0:
        logger.warning(f"Price unavailable for {ticker}, using fixed position size")
        return portfolio_equity * max_position_pct

    risk_per_share = 2 * atr
    if risk_amount < risk_per_share:
        logger.warning(f"Risk amount ${risk_amount:.2f} less than risk per share ${risk_per_share:.2f} for {ticker}, using minimum 1 share")
        shares = 1
    else:
        shares = int(risk_amount / risk_per_share)

    position_size = shares * price

    max_size = portfolio_equity * max_position_pct
    position_size = min(position_size, max_size)

    logger.debug(f"Dynamic sizing for {ticker}: risk=${risk_amount:.0f}, ATR={atr:.2f}, shares={shares}, size=${position_size:.0f}")

    return position_size


def risk_management_agent(state: AgentState):
    """Controls position sizing based on real-world risk factors for multiple tickers."""
    data = state["data"]
    tickers = data["tickers"]

    risk_analysis = {}
    alpaca_positions = []
    account = {}

    try:
        alpaca_positions_response = trading_client.get_all_positions()
        alpaca_positions = cast(list[Position], alpaca_positions_response)
        account = get_account_info()
        state["data"]["portfolio"]["cash"] = account["equity"]
        state["data"]["portfolio"]["margin_requirement"] = account["maintenance_margin"]

    except Exception as e:
        progress.update_status("risk_management_agent", None, f"{str(e)}")

    vix = data.get("vix")

    for ticker in tickers:
        progress.update_status("risk_management_agent", ticker, "Analyzing position data")

        position = next((p for p in alpaca_positions if p.symbol == ticker), None)

        if position is not None:
            positions = state["data"]["portfolio"].get("positions", {})
            positions[ticker] = {
                "quantity": float(position.qty),
                "cost_basis": float(position.cost_basis),
                "current_price": float(position.current_price) if position.current_price else 0,
                "side": position.side,
                "unrealized_pl": float(position.unrealized_pl) if position.unrealized_pl else 0,
            }

        if position and position.current_price:
            current_price = float(position.current_price)
        else:
            price_value = get_current_price(ticker)
            current_price = float(price_value) if price_value is not None else 0.0

        progress.update_status("risk_management_agent", ticker, "Calculating position limits")

        if position:
            if position.side == "long":
                current_position_value = float(position.qty) * current_price
            else:
                current_position_value = -1 * float(position.qty) * current_price
        else:
            current_position_value = 0

        total_portfolio_value = account["equity"]

        position_limit = calculate_dynamic_position_size(
            ticker=ticker,
            portfolio_equity=total_portfolio_value,
            vix=vix,
            base_risk_pct=0.02,
            max_position_pct=0.05,
        )

        remaining_position_limit = position_limit - abs(current_position_value)

        # Get margin requirement from account multiplier (dynamic based on account type)
        short_margin_requirement = get_margin_requirement(account)
        margin_multiplier = account.get("margin_multiplier", 0)

        regular_buying_power = float(account["buying_power"])
        day_trading_buying_power = float(account.get("daytrading_buying_power", regular_buying_power))

        safety_factor = 0.9

        ticker_data = data.get(ticker, {})
        is_bearish = ticker_data.get("suggested_side") == "bearish" or ticker_data.get("signal") == "bearish"

        if remaining_position_limit > 0:
            if is_bearish:
                adjusted_buying_power = day_trading_buying_power / short_margin_requirement * safety_factor
            else:
                adjusted_buying_power = regular_buying_power * safety_factor
        else:
            adjusted_buying_power = 0

        max_position_size = min(remaining_position_limit, adjusted_buying_power)

        if max_position_size < 0:
            max_position_size = 0

        if position_limit > 0:
            position_usage_pct = abs(current_position_value) / position_limit
            if position_usage_pct > 0.8:
                logger.warning(f"{ticker}: Position limit usage at {position_usage_pct:.1%} (${abs(current_position_value):,.2f} / ${position_limit:,.2f})")

        risk_analysis[ticker] = {
            "remaining_position_limit": float(max_position_size),
            "current_price": current_price if current_price else 0,
            "reasoning": {
                "portfolio_value": float(total_portfolio_value),
                "current_position": float(current_position_value),
                "position_limit": float(position_limit),
                "remaining_limit": float(remaining_position_limit),
                "available_cash": float(account["buying_power"]),
                "day_trading_buying_power": float(account.get("daytrading_buying_power", 0)),
                "adjusted_buying_power": float(adjusted_buying_power),
                "trade_type": "short" if is_bearish else "long",
                "sizing_method": "dynamic" if position_limit <= total_portfolio_value * 0.05 else "fixed",
                "margin_multiplier": float(margin_multiplier) if margin_multiplier else 0,
                "margin_requirement": float(short_margin_requirement),
            },
        }

        progress.update_status("risk_management_agent", ticker, "Done")

    message = HumanMessage(
        content=json.dumps(risk_analysis),
        name="risk_management_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(risk_analysis, "Risk Management Agent")

    state["data"]["analyst_signals"]["risk_management_agent"] = risk_analysis

    return {
        "messages": list(state["messages"]) + [message],
        "data": data,
    }
