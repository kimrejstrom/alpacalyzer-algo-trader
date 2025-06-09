import json
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from alpacalyzer.gpt.call_gpt import call_gpt_web
from alpacalyzer.graph.state import AgentState, show_agent_reasoning
from alpacalyzer.utils.progress import progress


class WebSignal(BaseModel):
    signal: Literal["bullish", "bearish", "neutral"]
    confidence: float
    reasoning: str


##### Web Agent #####
def web_agent(state: AgentState):
    """Web analysis for selected tickers"""

    # Get the tickers
    data = state["data"]
    tickers = data["tickers"]

    web_analysis = {}

    # Get position limits, current prices, and signals for every ticker
    for ticker in tickers:
        progress.update_status("web_agent", ticker, "Analyzing web signals")

        web_output = get_web_analysis(ticker)

        if web_output is None:
            progress.update_status("web_agent", ticker, "Failed to generate web analysis")
            web_analysis[ticker] = {
                "signal": "neutral",
                "confidence": 0,
                "reasoning": "Web analysis failed or returned no data",
            }
            continue

        web_analysis[ticker] = {
            "signal": web_output.signal,
            "confidence": web_output.confidence,
            "reasoning": web_output.reasoning,
        }

        progress.update_status("web_agent", ticker, "Done")

    # Create the web agent message
    message = HumanMessage(
        content=json.dumps(web_analysis),
        name="web_agent",
    )

    # Print the decision if the flag is set
    if state["metadata"]["show_reasoning"]:
        show_agent_reasoning(web_analysis, "Web Agent")

    # Add signals to the overall state
    state["data"]["analyst_signals"]["web_agent"] = web_analysis

    return {"messages": [message], "data": state["data"]}


def get_web_analysis(
    ticker: str,
) -> WebSignal | None:
    """Generate web analysis for the given tickers."""
    system_message = {
        "role": "system",
        "content": """
        You are a financial analysis expert and trading strategist specializing in
        finding high value day and swing trading opportunities.

        ## Role & Expertise
        - You are to analyze the web to evaluate market sentiment and indicate a bullish, bearish, or neutral signal.
        - You apply technical analysis (candlesticks, trendlines, support/resistance, indicators, volume)
        and propose a confidence level between 0-100 and a concise reasoning for your analysis.

        ## Reference / Core Principles

        ## Response Style & Format
        - **Mandatory JSON Output:** Conclude with a valid JSON object that adheres to the JSON schema.
        - **Relevant entries:** Input data includes latest price, and candles have the same information,
            make sure your suggestions are relevant with respect to current price.

        ## TIPS & BEST PRACTICES
        1. **Always Keep It Clear & Actionable**
        - Focus on the data (candles, volume, indicators) and connect them to possible trading decisions.
        2. **Highlight Both Bullish & Bearish Scenarios**
        - Show where the setup might fail, so the user understands downside risks.
        3. **Stay Consistent**
        - Use the same structure for each ticker, making it easy for users to compare.
        4. **DO NOT INCLUDE LINKS IN RESPONSE**
        """,
    }

    human_template = """Based on the following analysis, create a research backed investment signal.

            Ticker to research: {ticker}:

            Return the trading signal in this JSON format:
            {{
              "signal": "bullish/bearish/neutral",
              "confidence": float (0-100),
              "reasoning": "string"
            }}
            """

    human_message = {
        "role": "user",
        "content": human_template.format(
            ticker=ticker,
        ),
    }

    # Combine the messages into a list that you can send to your API
    messages = [system_message, human_message]

    return call_gpt_web(messages=messages, function_schema=WebSignal)
