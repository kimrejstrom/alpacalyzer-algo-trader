import json
from typing import Any

from langchain_core.messages import HumanMessage

from alpacalyzer.data.models import PortfolioManagerOutput
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.llm import LLMTier, get_llm_client
from alpacalyzer.prompts import load_prompt
from alpacalyzer.utils.progress import progress


##### Portfolio Management Agent #####
def portfolio_management_agent(state: AgentState):
    """Makes final trading recommendations and generates order indicators for multiple tickers"""

    # Get the portfolio and analyst signals
    portfolio = state["data"]["portfolio"]
    analyst_signals = state["data"]["analyst_signals"]
    tickers = state["data"]["tickers"]

    progress.update_status("portfolio_management_agent", None, "Analyzing signals")

    # Get position limits, current prices, and signals for every ticker
    position_limits = {}
    current_prices = {}
    max_shares = {}
    signals_by_ticker = {}
    for ticker in tickers:
        progress.update_status("portfolio_management_agent", ticker, "Processing analyst signals")

        # Get position limits and current prices for the ticker
        risk_data = analyst_signals.get("risk_management_agent", {}).get(ticker, {})
        position_limits[ticker] = risk_data.get("remaining_position_limit", 0)
        current_prices[ticker] = risk_data.get("current_price", 0)

        # Calculate maximum shares allowed based on position limit and price
        if current_prices[ticker] > 0:
            max_shares[ticker] = int(position_limits[ticker] / current_prices[ticker])
        else:
            max_shares[ticker] = 0

        # Get signals for the ticker
        ticker_signals = {}
        for agent, signals in analyst_signals.items():
            if agent != "risk_management_agent" and ticker in signals:
                ticker_signals[agent] = {
                    "signal": signals[ticker]["signal"],
                    "confidence": signals[ticker]["confidence"],
                }
        signals_by_ticker[ticker] = ticker_signals
        progress.update_status("portfolio_management_agent", ticker, "Done")

    progress.update_status("portfolio_management_agent", None, "Making trading decisions")

    # Generate the trading decision
    result = generate_trading_decision(
        signals_by_ticker=signals_by_ticker,
        current_prices=current_prices,
        max_shares=max_shares,
        portfolio=portfolio,
    )

    if result is None:
        progress.update_status("portfolio_management_agent", None, "Failed to generate trading decision")
        return {
            "messages": state["messages"],
            "data": state["data"],
        }

    portfolio_decisions = {decision.ticker: decision.model_dump() for decision in result.decisions}

    # Create the portfolio management message
    message = HumanMessage(
        content=json.dumps(portfolio_decisions),
        name="portfolio_management",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(
            portfolio_decisions,
            "Portfolio Management Agent",
        )

    progress.update_status("portfolio_management_agent", None, "Done")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["portfolio_management_agent"] = portfolio_decisions

    return {
        "messages": list(state["messages"]) + [message],
        "data": state["data"],
    }


def generate_trading_decision(
    signals_by_ticker: dict[str, dict[Any, Any]],
    current_prices: dict[str, float],
    max_shares: dict[str, int],
    portfolio: dict[str, float],
) -> PortfolioManagerOutput | None:
    """Attempts to get a decision from the LLM with retry logic"""
    system_message = {
        "role": "system",
        "content": load_prompt("portfolio_manager"),
    }

    # Define a template for the user (human) message
    human_template = (
        "Based on the team's analysis, make your trading decisions for each ticker.\n\n"
        "Here are the signals by ticker:\n{signals_by_ticker}\n\n"
        "Current Prices ($):\n{current_prices}\n\n"
        "Maximum Shares Allowed For Purchases:\n{max_shares}\n\n"
        "Portfolio Cash ($): {portfolio_cash}\n"
        "Current Positions: {portfolio_positions}\n"
        "Current Margin Requirement ($): {margin_requirement}\n\n"
        "Output strictly in JSON with the following structure:\n"
        "{{\n"
        '  "decisions": [\n'
        "    {{\n"
        '      "ticker": "TICKER1",\n'
        '      "action": "buy/sell/short/cover/hold",\n'
        '      "quantity": integer (shares),\n'
        '      "confidence": float (0-100%),\n'
        '      "reasoning": "string"\n'
        "    }},\n"
        "    {{\n"
        '      "ticker": "TICKER2",\n'
        "      ...\n"
        "    }}\n"
        "  ]\n"
        "}}"
    )

    # Prepare dynamic input values (assumes these variables are defined)
    signals_by_ticker_str = json.dumps(signals_by_ticker, indent=2)
    current_prices_formatted = {k: f"${v:.2f}" for k, v in current_prices.items()}
    current_prices_str = json.dumps(current_prices_formatted, indent=2)
    max_shares_formatted = {k: f"{v:,} shares" for k, v in max_shares.items()}
    max_shares_str = json.dumps(max_shares_formatted, indent=2)
    portfolio_cash_str = f"${portfolio.get('cash', 0):,.2f}"
    portfolio_positions_str = json.dumps(portfolio.get("positions", {}), indent=2)
    margin_requirement_str = f"${portfolio.get('margin_requirement', 0):,.2f}"

    # Format the human message using the template
    human_message = {
        "role": "user",
        "content": human_template.format(
            signals_by_ticker=signals_by_ticker_str,
            current_prices=current_prices_str,
            max_shares=max_shares_str,
            portfolio_cash=portfolio_cash_str,
            portfolio_positions=portfolio_positions_str,
            margin_requirement=margin_requirement_str,
        ),
    }

    # Combine the messages into a list that you can send to your API
    messages = [system_message, human_message]
    client = get_llm_client()
    return client.complete_structured(messages, PortfolioManagerOutput, tier=LLMTier.STANDARD, caller="portfolio_manager")
