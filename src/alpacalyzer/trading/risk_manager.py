import json
from typing import cast

from alpaca.trading.models import Position
from langchain_core.messages import HumanMessage

from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.trading.alpaca_client import get_account_info, trading_client
from alpacalyzer.utils.progress import progress


##### Risk Management Agent #####
def risk_management_agent(state: AgentState):
    """Controls position sizing based on real-world risk factors for multiple tickers."""
    data = state["data"]
    tickers = data["tickers"]

    # Initialize risk analysis for each ticker
    risk_analysis = {}

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
        if position is None:
            continue

        state["data"]["portfolio"]["positions"][ticker] = (
            {
                "quantity": float(position.qty),  # Number of shares held long
                "cost_basis": float(position.cost_basis),  # Average cost basis for long positions
                "current_price": float(position.current_price) if position.current_price else 0,  # Current price
                "side": position.side,  # Position side (long or short)
                "unrealized_pl": float(position.unrealized_pl) if position.unrealized_pl else 0,
            },
        )

        progress.update_status("risk_management_agent", ticker, "Calculating position limits")

        # Calculate current position value for this ticker
        current_position_value = float(position.cost_basis)

        # Calculate total portfolio value using stored prices
        total_portfolio_value = account["equity"]

        # Base limit is 5% of portfolio for any single position
        position_limit = total_portfolio_value * 0.05

        # For existing positions, subtract current position value from limit
        remaining_position_limit = position_limit - current_position_value

        # Ensure we don't exceed available cash
        max_position_size = min(remaining_position_limit, account["buying_power"])

        risk_analysis[ticker] = {
            "remaining_position_limit": float(max_position_size),
            "current_price": float(position.current_price if position.current_price else 0),
            "reasoning": {
                "portfolio_value": float(total_portfolio_value),
                "current_position": float(current_position_value),
                "position_limit": float(position_limit),
                "remaining_limit": float(remaining_position_limit),
                "available_cash": float(account["buying_power"]),
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
