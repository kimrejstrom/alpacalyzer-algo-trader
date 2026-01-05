import json

from langchain_core.messages import HumanMessage

from alpacalyzer.data.api import get_financial_metrics
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.utils.logger import get_logger
from alpacalyzer.utils.progress import progress

logger = get_logger()


##### Fundamental Agent #####
def fundamentals_agent(state: AgentState):
    """Analyzes fundamental data and generates trading signals for multiple tickers."""
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    # Initialize fundamental analysis for each ticker
    fundamental_analysis = {}

    for ticker in tickers:
        progress.update_status("fundamentals_agent", ticker, "Fetching financial metrics")

        # Get the financial metrics
        financial_metrics = get_financial_metrics(
            ticker=ticker,
            end_date=end_date,
            period="ttm",
            limit=10,
        )

        if not financial_metrics:
            progress.update_status("fundamentals_agent", ticker, "Failed: No financial metrics found")
            continue

        # Pull the most recent financial metrics
        metrics = financial_metrics[0]
        logger.debug(f"Metrics for {ticker}: {metrics}")

        # Initialize signals list for different fundamental aspects
        signals = []
        reasoning = {}

        progress.update_status("fundamentals_agent", ticker, "Analyzing profitability")
        # 1. Profitability Analysis
        return_on_equity = metrics.return_on_equity
        net_margin = metrics.net_margin
        operating_margin = metrics.operating_margin

        profitability_score = 0
        if return_on_equity is not None and return_on_equity > 0.15:
            profitability_score += 1
        if net_margin is not None and net_margin > 0.20:
            profitability_score += 1
        if operating_margin is not None and operating_margin > 0.15:
            profitability_score += 1

        signals.append("bullish" if profitability_score >= 2 else "bearish" if profitability_score == 0 else "neutral")
        reasoning["profitability_signal"] = {
            "signal": signals[0],
            "details": (f"ROE: {return_on_equity:.2%}" if return_on_equity is not None else "ROE: N/A")
            + ", "
            + (f"Net Margin: {net_margin:.2%}" if net_margin is not None else "Net Margin: N/A")
            + ", "
            + (f"Op Margin: {operating_margin:.2%}" if operating_margin is not None else "Op Margin: N/A"),
        }

        progress.update_status("fundamentals_agent", ticker, "Analyzing growth")
        # 2. Growth Analysis
        revenue_growth = metrics.revenue_growth
        earnings_growth = metrics.earnings_growth
        book_value_growth = metrics.book_value_growth

        growth_score = 0
        if revenue_growth is not None and revenue_growth > 0.10:
            growth_score += 1
        if earnings_growth is not None and earnings_growth > 0.10:
            growth_score += 1
        if book_value_growth is not None and book_value_growth > 0.10:
            growth_score += 1

        signals.append("bullish" if growth_score >= 2 else "bearish" if growth_score == 0 else "neutral")
        reasoning["growth_signal"] = {
            "signal": signals[1],
            "details": (f"Revenue Growth: {revenue_growth:.2%}" if revenue_growth is not None else "Revenue Growth: N/A")
            + ", "
            + (f"Earnings Growth: {earnings_growth:.2%}" if earnings_growth is not None else "Earnings Growth: N/A"),
        }

        progress.update_status("fundamentals_agent", ticker, "Analyzing financial health")
        # 3. Financial Health
        current_ratio = metrics.current_ratio
        debt_to_equity = metrics.debt_to_equity
        free_cash_flow_per_share = metrics.free_cash_flow_per_share
        earnings_per_share = metrics.earnings_per_share

        health_score = 0
        if current_ratio is not None and current_ratio > 1.5:  # Strong liquidity
            health_score += 1
        if debt_to_equity is not None and debt_to_equity < 0.5:  # Conservative debt levels
            health_score += 1
        if free_cash_flow_per_share is not None and earnings_per_share is not None and free_cash_flow_per_share > earnings_per_share * 0.8:  # Strong FCF conversion
            health_score += 1

        signals.append("bullish" if health_score >= 2 else "bearish" if health_score == 0 else "neutral")
        reasoning["financial_health_signal"] = {
            "signal": signals[2],
            "details": (f"Current Ratio: {current_ratio:.2f}" if current_ratio is not None else "Current Ratio: N/A")
            + ", "
            + (f"D/E: {debt_to_equity:.2f}" if debt_to_equity is not None else "D/E: N/A"),
        }

        progress.update_status("fundamentals_agent", ticker, "Analyzing valuation ratios")
        # 4. Price to X ratios
        pe_ratio = metrics.price_to_earnings_ratio
        pb_ratio = metrics.price_to_book_ratio
        ps_ratio = metrics.price_to_sales_ratio

        # Note: Higher P/E, P/B, P/S ratios are generally considered more expensive/bearish
        # Lower ratios suggest better value
        price_ratio_score = 0
        if pe_ratio is not None and pe_ratio < 25:  # Reasonable P/E ratio
            price_ratio_score += 1
        if pb_ratio is not None and pb_ratio < 3:  # Reasonable P/B ratio
            price_ratio_score += 1
        if ps_ratio is not None and ps_ratio < 5:  # Reasonable P/S ratio
            price_ratio_score += 1

        # For valuation ratios, lower is better (bullish), higher is worse (bearish)
        signals.append("bullish" if price_ratio_score >= 2 else "bearish" if price_ratio_score == 0 else "neutral")
        reasoning["price_ratios_signal"] = {
            "signal": signals[3],
            "details": (f"P/E: {pe_ratio:.2f}" if pe_ratio is not None else "P/E: N/A")
            + ", "
            + (f"P/B: {pb_ratio:.2f}" if pb_ratio is not None else "P/B: N/A")
            + ", "
            + (f"P/S: {ps_ratio:.2f}" if ps_ratio is not None else "P/S: N/A"),
        }

        progress.update_status("fundamentals_agent", ticker, "Calculating final signal")
        # Determine overall signal
        bullish_signals = signals.count("bullish")
        bearish_signals = signals.count("bearish")

        if bullish_signals > bearish_signals:
            overall_signal = "bullish"
        elif bearish_signals > bullish_signals:
            overall_signal = "bearish"
        else:
            overall_signal = "neutral"

        # Calculate confidence level
        total_signals = len(signals)
        confidence = round(max(bullish_signals, bearish_signals) / total_signals, 2) * 100

        fundamental_analysis[ticker] = {
            "signal": overall_signal,
            "confidence": confidence,
            "reasoning": reasoning,
        }

        progress.update_status("fundamentals_agent", ticker, "Done")

    # Create the fundamental analysis message
    message = HumanMessage(
        content=json.dumps(fundamental_analysis),
        name="fundamentals_agent",
    )

    # Print the reasoning if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(fundamental_analysis, "Fundamental Analysis Agent")

    # Add the signal to the analyst_signals list
    state["data"]["analyst_signals"]["fundamentals_agent"] = fundamental_analysis

    return {
        "messages": [message],
        "data": data,
    }
