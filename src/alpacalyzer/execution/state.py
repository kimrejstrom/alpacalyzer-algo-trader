"""ExecutionEngine state persistence model."""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

STATE_VERSION = "1.1.0"


@dataclass
class EngineState:
    """
    Persisted state for ExecutionEngine.

    Attributes:
        version: State format version for migration
        timestamp: When state was saved
        signal_queue: Pending signals
        positions: Current position data
        cooldowns: Cooldown manager data
        orders: Order manager data
        strategy_state: Strategy-specific state (Issue #98)
    """

    version: str
    timestamp: datetime
    signal_queue: dict[str, Any]
    positions: dict[str, Any]
    cooldowns: dict[str, Any]
    orders: dict[str, Any]
    strategy_state: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert state to JSON string."""
        import json

        state_dict = asdict(self)
        state_dict["timestamp"] = self.timestamp.isoformat()
        return json.dumps(state_dict, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "EngineState":
        """Create state from JSON string."""
        import json

        state_dict = json.loads(json_str)
        state_dict["timestamp"] = datetime.fromisoformat(state_dict["timestamp"])
        # Backward compatibility: default strategy_state to empty dict if missing
        if "strategy_state" not in state_dict:
            state_dict["strategy_state"] = {}
        return cls(**state_dict)


def create_empty_state() -> EngineState:
    """Create an empty state object."""
    return EngineState(
        version=STATE_VERSION,
        timestamp=datetime.now(UTC),
        signal_queue={},
        positions={},
        cooldowns={},
        orders={},
        strategy_state={},
    )
