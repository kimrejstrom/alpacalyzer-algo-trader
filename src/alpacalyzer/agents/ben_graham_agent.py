import json
import math
from typing import Any, Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from alpacalyzer.data.api import get_financial_metrics, get_market_cap, search_line_items
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.llm import LLMTier, get_llm_client
from alpacalyzer.prompts import load_prompt
from alpacalyzer.utils.progress import progress


class BenGrahamSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


def ben_graham_agent(state: AgentState):
    """
    Analyzes stocks using Benjamin Graham's classic value-investing principles.

    1. Earnings stability over multiple years.
    2. Solid financial strength (low debt, adequate liquidity).
    3. Discount to intrinsic value (e.g. Graham Number or net-net).
    4. Adequate margin of safety.
    """
    data = state["data"]
    end_date = data["end_date"]
    tickers = data["tickers"]

    analysis_data = {}
    graham_analysis = {}

    for ticker in tickers:
        progress.update_status("ben_graham_agent", ticker, "Fetching financial metrics")
        metrics = get_financial_metrics(ticker, end_date, period="annual", limit=10)

        progress.update_status("ben_graham_agent", ticker, "Gathering financial line items")
        financial_line_items = search_line_items(
            ticker,
            [
                "earnings_per_share",
                "revenue",
                "net_income",
                "book_value_per_share",
                "total_assets",
                "total_liabilities",
                "current_assets",
                "current_liabilities",
                "dividends_and_other_cash_distributions",
                "outstanding_shares",
            ],
            end_date,
            period="annual",
            limit=10,
        )

        progress.update_status("ben_graham_agent", ticker, "Getting market cap")
        market_cap = get_market_cap(ticker, end_date) or 0.0

        # Perform sub-analyses
        progress.update_status("ben_graham_agent", ticker, "Analyzing earnings stability")
        earnings_analysis = analyze_earnings_stability(metrics, financial_line_items)

        progress.update_status("ben_graham_agent", ticker, "Analyzing financial strength")
        strength_analysis = analyze_financial_strength(financial_line_items)

        progress.update_status("ben_graham_agent", ticker, "Analyzing Graham valuation")
        valuation_analysis = analyze_valuation_graham(financial_line_items, market_cap)

        # Aggregate scoring
        total_score = earnings_analysis["score"] + strength_analysis["score"] + valuation_analysis["score"]
        max_possible_score = 15  # total possible from the three analysis functions

        # Map total_score to signal
        if total_score >= 0.7 * max_possible_score:
            signal = "bullish"
        elif total_score <= 0.3 * max_possible_score:
            signal = "bearish"
        else:
            signal = "neutral"

        analysis_data[ticker] = {
            "signal": signal,
            "score": total_score,
            "max_score": max_possible_score,
            "earnings_analysis": earnings_analysis,
            "strength_analysis": strength_analysis,
            "valuation_analysis": valuation_analysis,
        }

        progress.update_status("ben_graham_agent", ticker, "Generating Ben Graham analysis")
        graham_output = generate_graham_output(
            ticker=ticker,
            analysis_data=analysis_data,
        )

        if graham_output is None:
            progress.update_status("ben_graham_agent", ticker, "Failed: No output from LLM")
            # Still create an entry with neutral sentiment when no sentiment data
            graham_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "Ben Graham analysis failed or returned no data",
            }
            continue

        graham_analysis[ticker] = {
            "signal": graham_output.signal,
            "confidence": graham_output.confidence,
            "reasoning": graham_output.reasoning,
        }

        progress.update_status("ben_graham_agent", ticker, "Done")

    # Wrap results in a single message for the chain
    message = HumanMessage(content=json.dumps(graham_analysis), name="ben_graham_agent")

    # Optionally display reasoning
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(graham_analysis, "Ben Graham Agent")

    # Store signals in the overall state
    state["data"]["analyst_signals"]["ben_graham_agent"] = graham_analysis

    return {"messages": [message], "data": state["data"]}


def analyze_earnings_stability(metrics: list[Any], financial_line_items: list[Any]) -> dict[str, Any]:
    """
    Graham wants at least several years of consistently positive earnings (ideally 5+).

    We'll check:
    1. Number of years with positive EPS.
    2. Growth in EPS from first to last period.
    """
    score = 0
    details = []

    if not metrics or not financial_line_items:
        return {"score": score, "details": "Insufficient data for earnings stability analysis"}

    eps_vals = [item.earnings_per_share for item in financial_line_items if item.earnings_per_share is not None]

    if len(eps_vals) < 2:
        details.append("Not enough multi-year EPS data.")
        return {"score": score, "details": "; ".join(details)}

    # 1. Consistently positive EPS
    positive_eps_years = sum(1 for e in eps_vals if e > 0)
    total_eps_years = len(eps_vals)
    if positive_eps_years == total_eps_years:
        score += 3
        details.append("EPS was positive in all available periods.")
    elif positive_eps_years >= (total_eps_years * 0.8):
        score += 2
        details.append("EPS was positive in most periods.")
    else:
        details.append("EPS was negative in multiple periods.")

    # 2. EPS growth from earliest to latest
    if eps_vals[0] > eps_vals[-1]:
        score += 1
        details.append("EPS grew from earliest to latest period.")
    else:
        details.append("EPS did not grow from earliest to latest period.")

    return {"score": score, "details": "; ".join(details)}


def analyze_financial_strength(financial_line_items: list[Any]) -> dict[str, Any]:
    """
    Graham checks liquidity (current ratio >= 2), manageable debt.

    And dividend record (preferably some history of dividends).
    """
    score = 0
    details = []

    if not financial_line_items:
        return {"score": score, "details": "No data for financial strength analysis"}

    latest_item = financial_line_items[0]
    total_assets = latest_item.total_assets or 0
    total_liabilities = latest_item.total_liabilities or 0
    current_assets = latest_item.current_assets or 0
    current_liabilities = latest_item.current_liabilities or 0

    # 1. Current ratio
    if current_liabilities > 0:
        current_ratio = current_assets / current_liabilities
        if current_ratio >= 2.0:
            score += 2
            details.append(f"Current ratio = {current_ratio:.2f} (>=2.0: solid).")
        elif current_ratio >= 1.5:
            score += 1
            details.append(f"Current ratio = {current_ratio:.2f} (moderately strong).")
        else:
            details.append(f"Current ratio = {current_ratio:.2f} (<1.5: weaker liquidity).")
    else:
        details.append("Cannot compute current ratio (missing or zero current_liabilities).")

    # 2. Debt vs. Assets
    if total_assets > 0:
        debt_ratio = total_liabilities / total_assets
        if debt_ratio < 0.5:
            score += 2
            details.append(f"Debt ratio = {debt_ratio:.2f}, under 0.50 (conservative).")
        elif debt_ratio < 0.8:
            score += 1
            details.append(f"Debt ratio = {debt_ratio:.2f}, somewhat high but could be acceptable.")
        else:
            details.append(f"Debt ratio = {debt_ratio:.2f}, quite high by Graham standards.")
    else:
        details.append("Cannot compute debt ratio (missing total_assets).")

    # 3. Dividend track record
    div_periods = [item.dividends_and_other_cash_distributions for item in financial_line_items if item.dividends_and_other_cash_distributions is not None]
    if div_periods:
        # In many data feeds, dividend outflow is shown as a negative number
        # (money going out to shareholders). We'll consider any negative as 'paid a dividend'.
        div_paid_years = sum(1 for d in div_periods if d < 0)
        if div_paid_years > 0:
            # e.g. if at least half the periods had dividends
            if div_paid_years >= (len(div_periods) // 2 + 1):
                score += 1
                details.append("Company paid dividends in the majority of the reported years.")
            else:
                details.append("Company has some dividend payments, but not most years.")
        else:
            details.append("Company did not pay dividends in these periods.")
    else:
        details.append("No dividend data available to assess payout consistency.")

    return {"score": score, "details": "; ".join(details)}


def analyze_valuation_graham(financial_line_items: list[Any], market_cap: float) -> dict[str, Any]:
    """
    Core Graham approach to valuation.

    1. Net-Net Check: (Current Assets - Total Liabilities) vs. Market Cap
    2. Graham Number: sqrt(22.5 * EPS * Book Value per Share)
    3. Compare per-share price to Graham Number => margin of safety
    """
    if not financial_line_items or not market_cap or market_cap <= 0:
        return {"score": 0, "details": "Insufficient data to perform valuation"}

    latest = financial_line_items[0]
    current_assets = latest.current_assets or 0
    total_liabilities = latest.total_liabilities or 0
    book_value_ps = latest.book_value_per_share or 0
    eps = latest.earnings_per_share or 0
    shares_outstanding = latest.outstanding_shares or 0

    details = []
    score = 0

    # 1. Net-Net Check
    #   NCAV = Current Assets - Total Liabilities
    #   If NCAV > Market Cap => historically a strong buy signal
    net_current_asset_value = current_assets - total_liabilities
    if net_current_asset_value > 0 and shares_outstanding > 0:
        net_current_asset_value_per_share = net_current_asset_value / shares_outstanding
        price_per_share = market_cap / shares_outstanding if shares_outstanding else 0

        details.append(f"Net Current Asset Value = {net_current_asset_value:,.2f}")
        details.append(f"NCAV Per Share = {net_current_asset_value_per_share:,.2f}")
        details.append(f"Price Per Share = {price_per_share:,.2f}")

        if net_current_asset_value > market_cap:
            score += 4  # Very strong Graham signal
            details.append("Net-Net: NCAV > Market Cap (classic Graham deep value).")
        else:
            # For partial net-net discount
            if net_current_asset_value_per_share >= (price_per_share * 0.67):
                score += 2
                details.append("NCAV Per Share >= 2/3 of Price Per Share (moderate net-net discount).")
    else:
        details.append("NCAV not exceeding market cap or insufficient data for net-net approach.")

    # 2. Graham Number
    #   GrahamNumber = sqrt(22.5 * EPS * BVPS).
    #   Compare the result to the current price_per_share
    #   If GrahamNumber >> price, indicates undervaluation
    graham_number = None
    if eps > 0 and book_value_ps > 0:
        graham_number = math.sqrt(22.5 * eps * book_value_ps)
        details.append(f"Graham Number = {graham_number:.2f}")
    else:
        details.append("Unable to compute Graham Number (EPS or Book Value missing/<=0).")

    # 3. Margin of Safety relative to Graham Number
    if graham_number and shares_outstanding > 0:
        current_price = market_cap / shares_outstanding
        if current_price > 0:
            margin_of_safety = (graham_number - current_price) / current_price
            details.append(f"Margin of Safety (Graham Number) = {margin_of_safety:.2%}")
            if margin_of_safety > 0.5:
                score += 3
                details.append("Price is well below Graham Number (>=50% margin).")
            elif margin_of_safety > 0.2:
                score += 1
                details.append("Some margin of safety relative to Graham Number.")
            else:
                details.append("Price close to or above Graham Number, low margin of safety.")
        else:
            details.append("Current price is zero or invalid; can't compute margin of safety.")
    # else: already appended details for missing graham_number

    return {"score": score, "details": "; ".join(details)}


def serialize_graham_analysis(ticker: str, analysis_data: dict[str, Any]) -> str:
    """Serialize Ben Graham analysis data with explicit units for LLM consumption."""

    data = analysis_data[ticker]

    valuation = data.get("valuation_analysis", {})
    valuation_details = valuation.get("details", "")

    import re

    net_current_asset_value = None
    ncav_per_share = None
    price_per_share = None
    graham_number = None
    margin_of_safety = None

    if valuation_details:
        match = re.search(r"Net Current Asset Value = ([0-9,.-]+)", valuation_details)
        if match:
            net_current_asset_value = float(match.group(1).replace(",", ""))

        match = re.search(r"NCAV Per Share = ([0-9,.-]+)", valuation_details)
        if match:
            ncav_per_share = float(match.group(1).replace(",", ""))

        match = re.search(r"Price Per Share = ([0-9,.-]+)", valuation_details)
        if match:
            price_per_share = float(match.group(1).replace(",", ""))

        match = re.search(r"Graham Number = ([0-9,.-]+)", valuation_details)
        if match:
            graham_number = float(match.group(1).replace(",", ""))

        match = re.search(r"Margin of Safety \(Graham Number\) = ([0-9.-]+)%", valuation_details)
        if match:
            margin_of_safety = float(match.group(1)) / 100

    json_ready_data = {
        "ticker": ticker,
        "signal": data.get("signal"),
        "score": f"{data.get('score', 0):.1f}/{data.get('max_score', 15)}",
        "earnings_stability_score": f"{data.get('earnings_analysis', {}).get('score', 0)}/5",
        "financial_strength_score": f"{data.get('strength_analysis', {}).get('score', 0)}/5",
        "valuation_score": f"{valuation.get('score', 0)}/7",
        "net_current_asset_value": f"${net_current_asset_value:,.2f}" if net_current_asset_value is not None else "N/A",
        "ncav_per_share": f"${ncav_per_share:,.2f}" if ncav_per_share is not None else "N/A",
        "price_per_share": f"${price_per_share:,.2f}" if price_per_share is not None else "N/A",
        "graham_number": f"${graham_number:,.2f}" if graham_number is not None else "N/A",
        "margin_of_safety": f"{margin_of_safety:.1%}" if margin_of_safety is not None else "N/A",
    }

    return json.dumps(json_ready_data, indent=2)


def generate_graham_output(
    ticker: str,
    analysis_data: dict[str, Any],
) -> BenGrahamSignal | None:
    """
    Generates an investment decision in the style of Benjamin Graham.

    - Value emphasis, margin of safety, net-nets, conservative balance sheet, stable earnings.
    - Return the result in a JSON structure: { signal, confidence, reasoning }.
    """

    system_message = {
        "role": "system",
        "content": load_prompt("ben_graham_agent"),
    }

    # Define template for the human message
    human_template = """Based on the following data, create the investment signal as Ben Graham would.

        Analysis Data for {ticker}:
        {analysis_data}

        Return the trading signal in the following JSON format:
        {{
          "signal": "bullish/bearish/neutral",
          "confidence": float (0-100),
          "reasoning": "string"
        }}
    """

    # Format the human message with the ticker and analysis data
    human_message = {
        "role": "user",
        "content": human_template.format(
            ticker=ticker,
            analysis_data=serialize_graham_analysis(ticker, analysis_data),
        ),
    }

    # Combine messages into a list
    messages = [system_message, human_message]

    client = get_llm_client()
    return client.complete_structured(messages, BenGrahamSignal, tier=LLMTier.STANDARD)
