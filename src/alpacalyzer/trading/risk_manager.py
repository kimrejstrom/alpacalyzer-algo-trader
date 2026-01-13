import json
from typing import cast

from alpaca.trading.models import Position
from langchain_core.messages import HumanMessage

from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.trading.alpaca_client import get_account_info, get_current_price, trading_client
from alpacalyzer.utils.progress import progress


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Controls position sizing based on real-world risk factors for multiple tickers."""
    data = state["data"]
    tickers = data["tickers"]

    # Initialize risk analysis for each ticker
    risk_analysis = {}
    alpaca_positions = []
    account = {}

    try:
        # Get fresh positions from Alpaca
        alpaca_positions_response = trading_client.get_all_positions()
        alpaca_positions = cast(list[Position], alpaca_positions_response)
        account = get_account_info()
        state["data"]["portfolio"]["cash"] = account["equity"]
        state["data"]["portfolio"]["margin_requirement"] = account["maintenance_margin"]

    except Exception as e:
        progress.update_status("risk_management_agent", None, f"{str(e)}")

    for ticker in tickers:
        progress.update_status("risk_management_agent", ticker, "Analyzing position data")

        position = next((p for p in alpaca_positions if p.symbol == ticker), None)

        if position is not None:
            positions = state["data"]["portfolio"].get("positions", {})
            positions[ticker] = {
                "quantity": float(position.qty),  # Number of shares held long
                "cost_basis": float(position.cost_basis),  # Average cost basis for long positions
                "current_price": float(position.current_price) if position.current_price else 0,  # Current price
                "side": position.side,  # Position side (long or short)
                "unrealized_pl": float(position.unrealized_pl) if position.unrealized_pl else 0,
            }

        # Get the current price and ensure it's a float
        if position and position.current_price:
            current_price = float(position.current_price)
        else:
            price_value = get_current_price(ticker)
            current_price = float(price_value) if price_value is not None else 0.0

        progress.update_status("risk_management_agent", ticker, "Calculating position limits")

        # Calculate current position value for this ticker
        if position:
            # Calculate position value correctly for both long and short positions
            if position.side == "long":
                current_position_value = float(position.qty) * current_price
            else:  # short position
                current_position_value = -1 * float(position.qty) * current_price
        else:
            current_position_value = 0

        # Calculate total portfolio value using stored prices
        total_portfolio_value = account["equity"]

        # Base limit is 5% of portfolio for any single position
        position_limit = total_portfolio_value * 0.05

        # For existing positions, calculate remaining limit correctly
        remaining_position_limit = position_limit - abs(current_position_value)

        # Account for margin requirements for short positions
        short_margin_requirement = 0.5  # 50% is typical for initial margin

        # Get both regular and day trading buying power
        regular_buying_power = float(account["buying_power"])
        day_trading_buying_power = float(account.get("daytrading_buying_power", regular_buying_power))

        # Use day trading buying power for short positions with a safety factor
        safety_factor = 0.9  # Use 90% of available buying power to account for price movements

        ticker_data = data.get(ticker, {})
        is_bearish = ticker_data.get("suggested_side") == "bearish" or ticker_data.get("signal") == "bearish"

        if remaining_position_limit > 0:  # Only if we have remaining limit
            if is_bearish:
                # For short positions:
                # 1. Use day trading buying power instead of regular buying power
                # 2. Apply margin requirement as a restricting factor (multiply, not divide)
                # 3. Apply safety factor
                adjusted_buying_power = day_trading_buying_power * short_margin_requirement * safety_factor
            else:
                # For long positions, use regular buying power with safety factor
                adjusted_buying_power = regular_buying_power * safety_factor
        else:
            adjusted_buying_power = 0  # No buying power if position limit exceeded

        # Ensure we don't exceed available cash or position limits
        max_position_size = min(remaining_position_limit, adjusted_buying_power)

        # Prevent negative position sizes
        if max_position_size < 0:
            max_position_size = 0

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
            },
        }

        progress.update_status("risk_management_agent", ticker, "Done")

    message = HumanMessage(
        content=json.dumps(risk_analysis),
        name="risk_management_agent",
    )

    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(risk_analysis, "Risk Management Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["risk_management_agent"] = risk_analysis

    return {
        "messages": list(state["messages"]) + [message],
        "data": data,
    }
