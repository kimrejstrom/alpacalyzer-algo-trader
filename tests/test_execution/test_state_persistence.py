"""Tests for state persistence model."""

from datetime import UTC, datetime

from alpacalyzer.execution.state import STATE_VERSION, EngineState, create_empty_state


def test_create_empty_state():
    """Test that empty state has correct structure."""
    state = create_empty_state()

    assert state.version == STATE_VERSION
    assert isinstance(state.timestamp, datetime)
    assert state.signal_queue == {}
    assert state.positions == {}
    assert state.cooldowns == {}
    assert state.orders == {}


def test_state_to_json():
    """Test that state can be serialized to JSON."""
    state = create_empty_state()

    json_str = state.to_json()

    import json

    parsed = json.loads(json_str)
    assert parsed["version"] == STATE_VERSION
    assert "timestamp" in parsed


def test_state_from_json():
    """Test that state can be deserialized from JSON."""
    state = create_empty_state()
    json_str = state.to_json()

    restored = EngineState.from_json(json_str)

    assert restored.version == state.version
    assert restored.timestamp == state.timestamp


def test_state_version_mismatch():
    """Test version mismatch handling."""
    state = create_empty_state()
    state.version = "0.0.0"
    json_str = state.to_json()

    restored = EngineState.from_json(json_str)
    assert restored.version == "0.0.0"
    assert restored.version != STATE_VERSION


def test_state_with_data():
    """Test state serialization with actual data."""
    state = EngineState(
        version=STATE_VERSION,
        timestamp=datetime.now(UTC),
        signal_queue={"signals": [{"ticker": "AAPL", "priority": 50}]},
        positions={"positions": {"AAPL": {"ticker": "AAPL", "quantity": 100}}},
        cooldowns={"cooldowns": {"AAPL": {"ticker": "AAPL", "reason": "test"}}},
        orders={"analyze_mode": False},
    )

    json_str = state.to_json()
    restored = EngineState.from_json(json_str)

    assert restored.version == STATE_VERSION
    assert restored.signal_queue["signals"][0]["ticker"] == "AAPL"
    assert restored.positions["positions"]["AAPL"]["quantity"] == 100
