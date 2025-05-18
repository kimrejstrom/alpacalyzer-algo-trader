import json
import operator
from collections.abc import Sequence
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

from alpacalyzer.utils.logger import logger


def merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {**a, **b}


# Define agent state
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    data: Annotated[dict[str, Any], merge_dicts]
    metadata: Annotated[dict[str, Any], merge_dicts]


def show_agent_reasoning(output, agent_name):
    logger.debug(f"\n{'=' * 10} {agent_name.center(28)} {'=' * 10}")

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
        # Convert the output to JSON-serializable format
        serializable_output = convert_to_serializable(output)
        logger.debug(json.dumps(serializable_output, indent=2))
    else:
        try:
            # Parse the string as JSON and pretty logger.debug it
            parsed_output = json.loads(output)
            logger.debug(json.dumps(parsed_output, indent=2))
        except json.JSONDecodeError:
            # Fallback to original string if not valid JSON
            logger.debug(output)

    logger.debug("=" * 48)
