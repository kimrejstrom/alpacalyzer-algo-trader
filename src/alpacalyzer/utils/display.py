import json
from typing import Any

from colorama import Fore, Style
from tabulate import tabulate

from alpacalyzer.agents.agents import ANALYST_ORDER
from alpacalyzer.data.models import TradingStrategy
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


def sort_agent_signals(signals):
    """Sort agent signals in a consistent order."""
    # Create order mapping from ANALYST_ORDER
    analyst_order = {display: idx for idx, (display, _) in enumerate(ANALYST_ORDER)}
    analyst_order["Risk Management"] = len(ANALYST_ORDER)  # Add Risk Management at the end

    return sorted(signals, key=lambda x: analyst_order.get(x[0], 999))


def wrap_text(text: Any, width: int = 60) -> str:
    # Handle different types of reasoning (string, dict, etc.)
    if isinstance(text, str):
        text_str = text
    elif isinstance(text, dict):
        # Convert dict to string representation
        text_str = json.dumps(text, indent=2)
    else:
        # Convert any other type to string
        text_str = str(text)

    # Wrap long reasoning text to make it more readable
    wrapped_text = ""
    current_line = ""
    # Use a fixed width of 60 characters to match the table column width
    max_line_length = width
    for word in text_str.split():
        if len(current_line) + len(word) + 1 > max_line_length:
            wrapped_text += current_line + "\n"
            current_line = word
        else:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
    if current_line:
        wrapped_text += current_line

    return wrapped_text


# Correct rounding for prices
def round_price(price):
    return round(price, 2) if price > 1 else round(price, 4)


def print_strategy_output(strategy: TradingStrategy) -> None:
    strategy_data = []
    action_color = {
        "BUY": Fore.GREEN,
        "SELL": Fore.RED,
        "HOLD": Fore.YELLOW,
        "COVER": Fore.GREEN,
        "SHORT": Fore.RED,
    }.get(strategy.trade_type.upper(), Fore.WHITE)

    wrapped_strategy_notes = wrap_text(strategy.strategy_notes)

    strategy_data.append(
        [
            f"{Fore.CYAN}{strategy.ticker}{Style.RESET_ALL}",
            f"{action_color}{strategy.trade_type}{Style.RESET_ALL}",
            f"{action_color}{strategy.quantity}{Style.RESET_ALL}",
            f"{Fore.WHITE}{round_price(strategy.entry_point)} | {round_price(strategy.target_price)}{Style.RESET_ALL}",
            f"{Fore.WHITE}{round_price(strategy.stop_loss)}{Style.RESET_ALL}",
            f"{Fore.GREEN}{strategy.risk_reward_ratio}{Style.RESET_ALL}",
            f"{Fore.WHITE}{wrapped_strategy_notes}{Style.RESET_ALL}",
        ]
    )
    print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING STRATEGY:{Style.RESET_ALL}")
    print(
        tabulate(
            strategy_data,
            headers=[
                f"{Fore.WHITE}Ticker",
                "Trade Type",
                "Quantity",
                "Entry | Target",
                "Stop Loss",
                "Risk/Reward Ratio",
                "Notes",
            ],
            tablefmt="grid",
            colalign=("left", "center", "right", "right", "right", "right", "left"),
        )
    )


def print_trading_output(result: dict[str, Any]) -> None:
    """
    Print formatted trading results with colored tables for multiple tickers.

    Args:
        result (dict): Dictionary containing decisions and analyst signals for multiple tickers
    """
    analyst_signals = result.get("analyst_signals", {})
    decisions = analyst_signals["portfolio_management_agent"]
    if not decisions:
        print(f"{Fore.RED}No trading decisions available{Style.RESET_ALL}")
        return

    # Print decisions for each ticker
    for ticker, decision in decisions.items():
        print(f"\n{Fore.WHITE}{Style.BRIGHT}Analysis for {Fore.CYAN}{ticker}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}{Style.BRIGHT}{'=' * 50}{Style.RESET_ALL}")

        # Prepare analyst signals table for this ticker
        table_data = []
        for agent, signals in result.get("analyst_signals", {}).items():
            if ticker not in signals:
                continue

            # Skip Risk Management and Portfolio Management agents in the signals section
            if agent == "risk_management_agent" or agent == "portfolio_management_agent":
                continue

            signal = signals[ticker]
            agent_name = agent.replace("_agent", "").replace("_", " ").title()
            signal_type = signal.get("signal", "").upper()
            confidence = signal.get("confidence", 0)

            signal_color = {
                "BULLISH": Fore.GREEN,
                "BEARISH": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }.get(signal_type, Fore.WHITE)

            # Get reasoning if available
            reasoning_str = ""
            if "reasoning" in signal and signal["reasoning"]:
                reasoning = signal["reasoning"]
                reasoning_str = wrap_text(reasoning)

            table_data.append(
                [
                    f"{Fore.CYAN}{agent_name}{Style.RESET_ALL}",
                    f"{signal_color}{signal_type}{Style.RESET_ALL}",
                    f"{Fore.WHITE}{confidence:.1f}%{Style.RESET_ALL}",
                    f"{Fore.WHITE}{reasoning_str}{Style.RESET_ALL}",
                ]
            )

        # Sort the signals according to the predefined order
        table_data = sort_agent_signals(table_data)

        print(f"\n{Fore.WHITE}{Style.BRIGHT}AGENT ANALYSIS:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(
            tabulate(
                table_data,
                headers=[f"{Fore.WHITE}Agent", "Signal", "Confidence", "Reasoning"],
                tablefmt="grid",
                colalign=("left", "center", "right", "left"),
            )
        )

        # Print Trading Decision Table
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)

        # Get reasoning and format it
        reasoning = decision.get("reasoning", "")
        # Wrap long reasoning text to make it more readable
        wrapped_reasoning = ""
        if reasoning:
            wrapped_reasoning = wrap_text(reasoning)

        decision_data = [
            ["Action", f"{action_color}{action}{Style.RESET_ALL}"],
            ["Quantity", f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}"],
            [
                "Confidence",
                f"{Fore.WHITE}{decision.get('confidence'):.1f}%{Style.RESET_ALL}",
            ],
            ["Reasoning", f"{Fore.WHITE}{wrapped_reasoning}{Style.RESET_ALL}"],
        ]

        print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING DECISION:{Style.RESET_ALL} [{Fore.CYAN}{ticker}{Style.RESET_ALL}]")
        print(tabulate(decision_data, tablefmt="grid", colalign=("left", "left")))
        logger.info(f"Ticker: {ticker}, Action: {action}, Quantity: {decision.get('quantity')}, Confidence: {decision.get('confidence'):.1f}%, Reasoning: {reasoning}")

    # Print Portfolio Summary
    print(f"\n{Fore.WHITE}{Style.BRIGHT}PORTFOLIO SUMMARY:{Style.RESET_ALL}")
    portfolio_data = []

    for ticker, decision in decisions.items():
        action = decision.get("action", "").upper()
        action_color = {
            "BUY": Fore.GREEN,
            "SELL": Fore.RED,
            "HOLD": Fore.YELLOW,
            "COVER": Fore.GREEN,
            "SHORT": Fore.RED,
        }.get(action, Fore.WHITE)
        portfolio_data.append(
            [
                f"{Fore.CYAN}{ticker}{Style.RESET_ALL}",
                f"{action_color}{action}{Style.RESET_ALL}",
                f"{action_color}{decision.get('quantity')}{Style.RESET_ALL}",
                f"{Fore.WHITE}{decision.get('confidence')}%{Style.RESET_ALL}",
            ]
        )

    headers = [f"{Fore.WHITE}Ticker", "Action", "Quantity", "Confidence"]

    # Print the portfolio summary table
    print(
        tabulate(
            portfolio_data,
            headers=headers,
            tablefmt="grid",
            colalign=("left", "center", "right", "right"),
        )
    )

    # Print the trading strategy
    decisions = result.get("decisions", {})
    if not decisions:
        print(f"{Fore.RED}No trading strategies available{Style.RESET_ALL}")
        return
    strategy_data = []

    for ticker, ticker_data in decisions.items():
        strategies = ticker_data.get("strategies", [])
        for strategy_dict in strategies:
            try:
                strategy = TradingStrategy.model_validate(strategy_dict)

                action_color = {
                    "BUY": Fore.GREEN,
                    "SELL": Fore.RED,
                    "HOLD": Fore.YELLOW,
                    "COVER": Fore.GREEN,
                    "SHORT": Fore.RED,
                }.get(strategy.trade_type.upper(), Fore.WHITE)

                wrapped_strategy_notes = wrap_text(strategy.strategy_notes)

                strategy_data.append(
                    [
                        f"{Fore.CYAN}{strategy.ticker}{Style.RESET_ALL}",
                        f"{action_color}{strategy.trade_type}{Style.RESET_ALL}",
                        f"{action_color}{strategy.quantity}{Style.RESET_ALL}",
                        f"{Fore.WHITE}{strategy.entry_point} | {strategy.target_price}{Style.RESET_ALL}",
                        f"{Fore.GREEN}{strategy.risk_reward_ratio}{Style.RESET_ALL}",
                        f"{Fore.WHITE}{wrapped_strategy_notes}{Style.RESET_ALL}",
                    ]
                )
            except Exception as e:
                logger.warning(f"Error processing strategy for {ticker}: {e}")
                continue

    if not strategy_data:
        print(f"{Fore.RED}No valid trading strategies found{Style.RESET_ALL}")
        return

    print(f"\n{Fore.WHITE}{Style.BRIGHT}TRADING STRATEGY:{Style.RESET_ALL}")
    print(
        tabulate(
            strategy_data,
            headers=[
                f"{Fore.WHITE}Ticker",
                "Trade Type",
                "Quantity",
                "Entry | Target",
                "Risk/Reward Ratio",
                "Notes",
            ],
            tablefmt="grid",
            colalign=("left", "center", "right", "right", "right", "left"),
        )
    )
