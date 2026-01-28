"""Integration tests for state persistence save/load cycle."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from alpacalyzer.execution.engine import ExecutionConfig, ExecutionEngine
from alpacalyzer.execution.signal_queue import PendingSignal
from alpacalyzer.strategies.base import EntryDecision, ExitDecision, Strategy


class DummyStrategy(Strategy):
    """Dummy strategy for testing."""

    def evaluate_entry(self, signal, context, agent_recommendation=None):
        return EntryDecision(
            should_enter=False,
            reason="No entry",
            suggested_size=0,
            entry_price=0.0,
            stop_loss=0.0,
            target=0.0,
        )

    def evaluate_exit(self, position, signal, context):
        return ExitDecision(should_exit=False, reason="Hold", urgency="normal")

    def calculate_position_size(self, signal, context, max_amount):
        return 0


class TestStatePersistenceIntegration:
    """Integration tests for state save/load cycle."""

    def test_state_save_creates_file(self):
        """Test that save_state creates a state file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_state_file = Path(temp_dir) / ".alpacalyzer-state.json"

            with patch("alpacalyzer.execution.engine.STATE_FILE", temp_state_file):
                engine = ExecutionEngine(strategy=DummyStrategy(), config=ExecutionConfig(analyze_mode=True))

                signal = PendingSignal(
                    priority=50,
                    ticker="AAPL",
                    action="buy",
                    confidence=85.0,
                    source="test",
                )
                engine.add_signal(signal)

                engine.save_state()

                assert temp_state_file.exists()

                import json

                content = json.loads(temp_state_file.read_text())
                assert "version" in content
                assert "signal_queue" in content
                assert content["signal_queue"]["signals"][0]["ticker"] == "AAPL"

    def test_state_load_restores_signals(self):
        """Test that load_state restores signals from file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_state_file = Path(temp_dir) / ".alpacalyzer-state.json"
            state_json = (
                '{"version": "1.0.0", "timestamp": "2026-01-01T00:00:00+00:00", '
                '"signal_queue": {"signals": [{"priority": 50, "ticker": "AAPL", "action": "buy", '
                '"confidence": 85.0, "source": "test", "created_at": "2026-01-01T00:00:00+00:00", '
                '"expires_at": null, "agent_recommendation": null}]}, "positions": {"positions": {}, '
                '"closed_positions": [], "last_sync": null}, "cooldowns": {"cooldowns": {}, '
                '"default_hours": 3}, "orders": {"analyze_mode": true, "pending_orders_count": 0}}'
            )

            temp_state_file.write_text(state_json, encoding="utf-8")

            with patch("alpacalyzer.execution.engine.STATE_FILE", temp_state_file):
                engine = ExecutionEngine(strategy=DummyStrategy(), config=ExecutionConfig(analyze_mode=True))

                assert engine.signal_queue.size() == 1
                assert engine.signal_queue.peek().ticker == "AAPL"

    def test_state_reset_clears_state(self):
        """Test that reset_state=True ignores saved state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_state_file = Path(temp_dir) / ".alpacalyzer-state.json"
            state_json = (
                '{"version": "1.0.0", "timestamp": "2026-01-01T00:00:00+00:00", '
                '"signal_queue": {"signals": [{"priority": 50, "ticker": "AAPL", "action": "buy", '
                '"confidence": 85.0, "source": "test", "created_at": "2026-01-01T00:00:00+00:00", '
                '"expires_at": null, "agent_recommendation": null}]}, "positions": {"positions": {}, '
                '"closed_positions": [], "last_sync": null}, "cooldowns": {"cooldowns": {}, '
                '"default_hours": 3}, "orders": {"analyze_mode": true, "pending_orders_count": 0}}'
            )

            temp_state_file.write_text(state_json, encoding="utf-8")

            with patch("alpacalyzer.execution.engine.STATE_FILE", temp_state_file):
                engine = ExecutionEngine(
                    strategy=DummyStrategy(),
                    config=ExecutionConfig(analyze_mode=True),
                    reset_state=True,
                )

                assert engine.signal_queue.is_empty()

    def test_version_mismatch_uses_fresh_state(self):
        """Test that version mismatch ignores saved state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_state_file = Path(temp_dir) / ".alpacalyzer-state.json"
            state_json = (
                '{"version": "0.9.0", "timestamp": "2026-01-01T00:00:00+00:00", '
                '"signal_queue": {"signals": [{"priority": 50, "ticker": "AAPL", "action": "buy", '
                '"confidence": 85.0, "source": "test", "created_at": "2026-01-01T00:00:00+00:00", '
                '"expires_at": null, "agent_recommendation": null}]}, "positions": {"positions": {}, '
                '"closed_positions": [], "last_sync": null}, "cooldowns": {"cooldowns": {}, '
                '"default_hours": 3}, "orders": {"analyze_mode": true, "pending_orders_count": 0}}'
            )

            temp_state_file.write_text(state_json, encoding="utf-8")

            with patch("alpacalyzer.execution.engine.STATE_FILE", temp_state_file):
                engine = ExecutionEngine(strategy=DummyStrategy(), config=ExecutionConfig(analyze_mode=True))

                assert engine.signal_queue.is_empty()

    def test_full_save_load_cycle(self):
        """Test complete save and load cycle preserves all state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_state_file = Path(temp_dir) / ".alpacalyzer-state.json"

            with patch("alpacalyzer.execution.engine.STATE_FILE", temp_state_file):
                engine1 = ExecutionEngine(strategy=DummyStrategy(), config=ExecutionConfig(analyze_mode=True))

                signal = PendingSignal(
                    priority=50,
                    ticker="AAPL",
                    action="buy",
                    confidence=85.0,
                    source="test",
                )
                engine1.add_signal(signal)

                engine1.positions.add_position(
                    ticker="MSFT",
                    side="long",
                    quantity=100,
                    entry_price=150.0,
                    strategy_name="test",
                )

                engine1.cooldowns.add_cooldown("GOOGL", "test_reason", "test_strategy")

                engine1.save_state()

                engine2 = ExecutionEngine(strategy=DummyStrategy(), config=ExecutionConfig(analyze_mode=True))

                assert engine2.signal_queue.size() == 1
                assert engine2.signal_queue.peek().ticker == "AAPL"
                assert engine2.positions.has_position("MSFT")
                assert engine2.cooldowns.is_in_cooldown("GOOGL")
