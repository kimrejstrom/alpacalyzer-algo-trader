"""
Tests for strategy state persistence (Issue #98).

Tests that strategy-specific state (position data, false breakout counts,
entry times) survives restart via to_dict/from_dict serialization.
"""

from datetime import UTC, datetime

from alpacalyzer.strategies.breakout import BreakoutPositionData, BreakoutStrategy
from alpacalyzer.strategies.mean_reversion import MeanReversionStrategy


class TestBreakoutStrategyStatePersistence:
    """Tests for BreakoutStrategy state persistence."""

    def test_to_dict_empty_state(self):
        """Test serialization of empty state."""
        strategy = BreakoutStrategy()

        state = strategy.to_dict()

        assert state == {
            "position_data": {},
            "false_breakout_count": {},
        }

    def test_to_dict_with_position_data(self):
        """Test serialization with position data."""
        strategy = BreakoutStrategy()
        strategy._position_data["AAPL"] = BreakoutPositionData(
            entry_price=150.0,
            stop_loss=145.0,
            target=165.0,
            side="long",
        )
        strategy._position_data["TSLA"] = BreakoutPositionData(
            entry_price=200.0,
            stop_loss=210.0,
            target=180.0,
            side="short",
        )

        state = strategy.to_dict()

        assert "position_data" in state
        assert "AAPL" in state["position_data"]
        assert state["position_data"]["AAPL"]["entry_price"] == 150.0
        assert state["position_data"]["AAPL"]["stop_loss"] == 145.0
        assert state["position_data"]["AAPL"]["target"] == 165.0
        assert state["position_data"]["AAPL"]["side"] == "long"
        assert "TSLA" in state["position_data"]
        assert state["position_data"]["TSLA"]["side"] == "short"

    def test_to_dict_with_false_breakout_counts(self):
        """Test serialization with false breakout counts."""
        strategy = BreakoutStrategy()
        strategy._false_breakout_count["AAPL"] = 2
        strategy._false_breakout_count["MSFT"] = 1

        state = strategy.to_dict()

        assert "false_breakout_count" in state
        assert state["false_breakout_count"]["AAPL"] == 2
        assert state["false_breakout_count"]["MSFT"] == 1

    def test_from_dict_empty_state(self):
        """Test deserialization of empty state."""
        strategy = BreakoutStrategy()
        strategy._position_data["OLD"] = BreakoutPositionData(
            entry_price=100.0,
            stop_loss=95.0,
            target=110.0,
            side="long",
        )
        strategy._false_breakout_count["OLD"] = 5

        strategy.from_dict({})

        # Empty dict should clear existing state
        assert strategy._position_data == {}
        assert strategy._false_breakout_count == {}

    def test_from_dict_restores_position_data(self):
        """Test deserialization restores position data."""
        strategy = BreakoutStrategy()
        state = {
            "position_data": {
                "AAPL": {
                    "entry_price": 150.0,
                    "stop_loss": 145.0,
                    "target": 165.0,
                    "side": "long",
                },
                "TSLA": {
                    "entry_price": 200.0,
                    "stop_loss": 210.0,
                    "target": 180.0,
                    "side": "short",
                },
            },
            "false_breakout_count": {},
        }

        strategy.from_dict(state)

        assert "AAPL" in strategy._position_data
        assert strategy._position_data["AAPL"].entry_price == 150.0
        assert strategy._position_data["AAPL"].stop_loss == 145.0
        assert strategy._position_data["AAPL"].target == 165.0
        assert strategy._position_data["AAPL"].side == "long"
        assert "TSLA" in strategy._position_data
        assert strategy._position_data["TSLA"].side == "short"

    def test_from_dict_restores_false_breakout_counts(self):
        """Test deserialization restores false breakout counts."""
        strategy = BreakoutStrategy()
        state = {
            "position_data": {},
            "false_breakout_count": {
                "AAPL": 2,
                "MSFT": 1,
            },
        }

        strategy.from_dict(state)

        assert strategy._false_breakout_count["AAPL"] == 2
        assert strategy._false_breakout_count["MSFT"] == 1

    def test_roundtrip_serialization(self):
        """Test full roundtrip: to_dict -> from_dict preserves state."""
        original = BreakoutStrategy()
        original._position_data["AAPL"] = BreakoutPositionData(
            entry_price=150.0,
            stop_loss=145.0,
            target=165.0,
            side="long",
        )
        original._false_breakout_count["MSFT"] = 2

        state = original.to_dict()

        restored = BreakoutStrategy()
        restored.from_dict(state)

        assert restored._position_data["AAPL"].entry_price == 150.0
        assert restored._position_data["AAPL"].stop_loss == 145.0
        assert restored._position_data["AAPL"].target == 165.0
        assert restored._position_data["AAPL"].side == "long"
        assert restored._false_breakout_count["MSFT"] == 2


class TestMeanReversionStrategyStatePersistence:
    """Tests for MeanReversionStrategy state persistence."""

    def test_to_dict_empty_state(self):
        """Test serialization of empty state."""
        strategy = MeanReversionStrategy()

        state = strategy.to_dict()

        assert state == {"entry_times": {}}

    def test_to_dict_with_entry_times(self):
        """Test serialization with entry times."""
        strategy = MeanReversionStrategy()
        strategy._entry_times["AAPL"] = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        strategy._entry_times["TSLA"] = datetime(2026, 1, 14, 14, 0, 0, tzinfo=UTC)

        state = strategy.to_dict()

        assert "entry_times" in state
        assert "AAPL" in state["entry_times"]
        assert "TSLA" in state["entry_times"]
        # Should be ISO format strings
        assert state["entry_times"]["AAPL"] == "2026-01-15T10:30:00+00:00"
        assert state["entry_times"]["TSLA"] == "2026-01-14T14:00:00+00:00"

    def test_from_dict_empty_state(self):
        """Test deserialization of empty state."""
        strategy = MeanReversionStrategy()
        strategy._entry_times["OLD"] = datetime.now(UTC)

        strategy.from_dict({})

        assert strategy._entry_times == {}

    def test_from_dict_restores_entry_times(self):
        """Test deserialization restores entry times."""
        strategy = MeanReversionStrategy()
        state = {
            "entry_times": {
                "AAPL": "2026-01-15T10:30:00+00:00",
                "TSLA": "2026-01-14T14:00:00+00:00",
            }
        }

        strategy.from_dict(state)

        assert "AAPL" in strategy._entry_times
        assert strategy._entry_times["AAPL"] == datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        assert "TSLA" in strategy._entry_times
        assert strategy._entry_times["TSLA"] == datetime(2026, 1, 14, 14, 0, 0, tzinfo=UTC)

    def test_roundtrip_serialization(self):
        """Test full roundtrip: to_dict -> from_dict preserves state."""
        original = MeanReversionStrategy()
        original._entry_times["AAPL"] = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)

        state = original.to_dict()

        restored = MeanReversionStrategy()
        restored.from_dict(state)

        assert restored._entry_times["AAPL"] == datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)


class TestBaseStrategyDefaultPersistence:
    """Tests for default persistence behavior in BaseStrategy."""

    def test_momentum_strategy_default_to_dict(self):
        """Test MomentumStrategy (no state) returns empty dict."""
        from alpacalyzer.strategies.momentum import MomentumStrategy

        strategy = MomentumStrategy()

        state = strategy.to_dict()

        assert state == {}

    def test_momentum_strategy_default_from_dict(self):
        """Test MomentumStrategy (no state) handles from_dict gracefully."""
        from alpacalyzer.strategies.momentum import MomentumStrategy

        strategy = MomentumStrategy()

        # Should not raise
        strategy.from_dict({"some": "data"})
        strategy.from_dict({})


class TestEngineStateWithStrategyState:
    """Tests for EngineState with strategy_state field."""

    def test_engine_state_includes_strategy_state(self):
        """Test EngineState has strategy_state field."""
        from alpacalyzer.execution.state import STATE_VERSION, EngineState

        state = EngineState(
            version=STATE_VERSION,
            timestamp=datetime.now(UTC),
            signal_queue={},
            positions={},
            cooldowns={},
            orders={},
            strategy_state={"position_data": {}, "false_breakout_count": {}},
        )

        assert state.strategy_state == {"position_data": {}, "false_breakout_count": {}}

    def test_engine_state_json_roundtrip_with_strategy_state(self):
        """Test EngineState JSON serialization includes strategy_state."""
        from alpacalyzer.execution.state import STATE_VERSION, EngineState

        original = EngineState(
            version=STATE_VERSION,
            timestamp=datetime.now(UTC),
            signal_queue={},
            positions={},
            cooldowns={},
            orders={},
            strategy_state={
                "position_data": {
                    "AAPL": {
                        "entry_price": 150.0,
                        "stop_loss": 145.0,
                        "target": 165.0,
                        "side": "long",
                    }
                },
                "false_breakout_count": {"MSFT": 2},
            },
        )

        json_str = original.to_json()
        restored = EngineState.from_json(json_str)

        assert restored.strategy_state == original.strategy_state

    def test_engine_state_backward_compatible(self):
        """Test loading old state (v1.0.0) without strategy_state field."""
        import json

        from alpacalyzer.execution.state import EngineState

        # Simulate old v1.0.0 state without strategy_state
        old_state_dict = {
            "version": "1.0.0",
            "timestamp": "2026-01-15T10:30:00+00:00",
            "signal_queue": {},
            "positions": {},
            "cooldowns": {},
            "orders": {},
            # No strategy_state field
        }
        old_json = json.dumps(old_state_dict)

        # Should handle missing field gracefully
        state = EngineState.from_json(old_json)

        # Should default to empty dict
        assert state.strategy_state == {}
