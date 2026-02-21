import json
import operator
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


def merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {**a, **b}


# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, Any], merge_dicts]
    metadata: Annotated[dict[str, Any], merge_dicts]


def show_agent_reasoning(output, agent_name):
    def convert_to_serializable(obj):
        if hasattr(obj, "to_dict"):  # Handle Pandas Series/DataFrame
            return obj.to_dict()
        if hasattr(obj, "__dict__"):  # Handle custom objects
            return obj.__dict__
        if isinstance(obj, int | float | bool | str):
            return obj
        if isinstance(obj, list | tuple):
            return [convert_to_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {key: convert_to_serializable(value) for key, value in obj.items()}
        return str(obj)  # Fallback to string representation

    if isinstance(output, dict | list):
        serializable_output = convert_to_serializable(output)
    else:
        try:
            serializable_output = json.loads(output)
        except json.JSONDecodeError:
            serializable_output = {"raw": str(output)}

    # Route summaries through the Rich Live display (progress) so they don't
    # get overwritten by the agent status table re-renders.
    from alpacalyzer.utils.progress import progress

    if isinstance(serializable_output, dict):
        for ticker, data in serializable_output.items():
            if isinstance(data, dict):
                signal = str(data.get("signal", data.get("action", "?")))
                confidence = data.get("confidence", "?")
                reasoning = data.get("reasoning", "")
                if isinstance(reasoning, dict):
                    reasoning = ", ".join(f"{k}: {v}" for k, v in reasoning.items() if isinstance(v, str))
                reasoning_str = str(reasoning)[:120]
                if progress.started:
                    progress.add_reasoning(agent_name, ticker, signal, confidence, reasoning_str)
                else:
                    logger.info(f"[{agent_name}] {ticker} | {signal} | confidence={confidence} | {reasoning_str}")
            else:
                if progress.started:
                    progress.add_reasoning(agent_name, ticker, str(data), "?", "")
                else:
                    logger.info(f"[{agent_name}] {ticker} | {data}")
    else:
        if not progress.started:
            logger.info(f"[{agent_name}] {serializable_output}")

    # Emit structured event for observability tooling (full detail goes to events.jsonl)
    try:
        from alpacalyzer.events import AgentReasoningEvent, emit_event

        reasoning_dict = serializable_output if isinstance(serializable_output, dict) else {"data": serializable_output}

        # Extract tickers from reasoning if available
        tickers: list[str] = []
        if isinstance(reasoning_dict, dict):
            tickers = [k for k in reasoning_dict if isinstance(k, str) and k.isupper() and len(k) <= 5]

        emit_event(
            AgentReasoningEvent(
                timestamp=datetime.now(tz=UTC),
                agent=agent_name,
                tickers=tickers,
                reasoning=reasoning_dict,
            )
        )
    except Exception:
        logger.debug("Failed to emit agent reasoning event", exc_info=True)
