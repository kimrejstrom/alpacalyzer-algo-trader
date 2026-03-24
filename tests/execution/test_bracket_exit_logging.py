"""
Tests for bracket order exit event logging.

When bracket orders fill broker-side (stop loss or take profit hit),
positions disappear from the broker. The system must emit ExitTriggeredEvent
with full trade details so users can see what was sold and how the trade went.
"""

from unittest.mock import MagicMock

from alpacalyzer.events.models import ExitTriggeredEvent
from alpacalyzer.execution.engine import ExecutionEngine
from alpacalyzer.strategies.base import EntryDecision, ExitDecision


class MockStrategy:
    """Minimal strategy mock for engine tests."""

    name = "test_strategy"

    def evaluate_entry(self, *args, **kwargs):
        return EntryDecision(should_enter=False, reason="test")

    def evaluate_exit(self, *args, **kwargs):
        return ExitDecision(should_exit=False, reason="test")

    def calculate_position_size(self, *args, **kwargs):
        return 0


def _mock_market_context(monkeypatch):
    """Mock all external dependencies for _build_market_context."""
    monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_market_status", lambda: "open")
    monkeypatch.setattr(
        "alpacalyzer.trading.alpaca_client.get_account_info",
        lambda: {"equity": 10000.0, "buying_power": 8000.0},
    )
    monkeypatch.setattr("alpacalyzer.data.api.get_vix", lambda use_cache=True: 20.0)


class TestBracketExitEventEmission:
    """Test that bracket order exits emit ExitTriggeredEvent with trade details."""

    def test_bracket_exit_emits_exit_event(self, monkeypatch):
        """
        When a position disappears during broker sync (bracket fill).

        An ExitTriggeredEvent should be emitted with the position details.
        """
        engine = ExecutionEngine(MockStrategy())
        engine.config.analyze_mode = False

        engine.positions.add_position(
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            strategy_name="momentum",
            stop_loss=145.0,
            target=160.0,
        )

        emitted_events = []
        monkeypatch.setattr("alpacalyzer.execution.engine.emit_event", lambda e: emitted_events.append(e))
        monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_positions", list)
        _mock_market_context(monkeypatch)

        engine.run_cycle()

        exit_events = [e for e in emitted_events if isinstance(e, ExitTriggeredEvent)]
        assert len(exit_events) == 1

        evt = exit_events[0]
        assert evt.ticker == "AAPL"
        assert evt.side == "long"
        assert evt.quantity == 100
        assert evt.entry_price == 150.0
        assert evt.exit_mechanism == "bracket_fill"
        assert evt.strategy == "momentum"

    def test_bracket_exit_multiple_positions(self, monkeypatch):
        """Multiple bracket fills in one cycle should each emit an event."""
        engine = ExecutionEngine(MockStrategy())
        engine.config.analyze_mode = False

        engine.positions.add_position(
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            strategy_name="momentum",
        )
        engine.positions.add_position(
            ticker="MSFT",
            side="long",
            quantity=50,
            entry_price=300.0,
            strategy_name="breakout",
        )

        emitted_events = []
        monkeypatch.setattr("alpacalyzer.execution.engine.emit_event", lambda e: emitted_events.append(e))
        monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_positions", list)
        _mock_market_context(monkeypatch)

        engine.run_cycle()

        exit_events = [e for e in emitted_events if isinstance(e, ExitTriggeredEvent)]
        assert len(exit_events) == 2
        tickers = {e.ticker for e in exit_events}
        assert tickers == {"AAPL", "MSFT"}

    def test_bracket_exit_no_event_when_no_positions_close(self, monkeypatch):
        """No ExitTriggeredEvent when positions remain unchanged."""
        engine = ExecutionEngine(MockStrategy())
        engine.config.analyze_mode = False

        engine.positions.add_position(
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            strategy_name="momentum",
        )

        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.current_price = 155.0
        mock_pos.qty = "100"
        mock_pos.avg_entry_price = "150.0"
        mock_pos.market_value = "15500.0"
        mock_pos.unrealized_pl = "500.0"
        mock_pos.unrealized_plpc = "0.033"
        mock_pos.side = "long"

        emitted_events = []
        monkeypatch.setattr("alpacalyzer.execution.engine.emit_event", lambda e: emitted_events.append(e))
        monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_positions", lambda: [mock_pos])
        _mock_market_context(monkeypatch)

        engine.run_cycle()

        exit_events = [e for e in emitted_events if isinstance(e, ExitTriggeredEvent)]
        assert len(exit_events) == 0

    def test_bracket_exit_includes_pnl_data(self, monkeypatch):
        """Bracket exit event should include P/L from the tracked position."""
        engine = ExecutionEngine(MockStrategy())
        engine.config.analyze_mode = False

        engine.positions.add_position(
            ticker="TSLA",
            side="long",
            quantity=10,
            entry_price=200.0,
            strategy_name="momentum",
            stop_loss=190.0,
            target=220.0,
        )
        pos = engine.positions.get("TSLA")
        pos.update_price(215.0)

        emitted_events = []
        monkeypatch.setattr("alpacalyzer.execution.engine.emit_event", lambda e: emitted_events.append(e))
        monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_positions", list)
        _mock_market_context(monkeypatch)

        engine.run_cycle()

        exit_events = [e for e in emitted_events if isinstance(e, ExitTriggeredEvent)]
        assert len(exit_events) == 1

        evt = exit_events[0]
        assert evt.entry_price == 200.0
        assert evt.pnl == 150.0  # (215 - 200) * 10
        assert evt.reason == "bracket_fill"

    def test_bracket_exit_in_analyze_mode(self, monkeypatch):
        """Bracket exits should also emit events in analyze mode."""
        engine = ExecutionEngine(MockStrategy())
        engine.config.analyze_mode = True

        engine.positions.add_position(
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            strategy_name="momentum",
        )

        emitted_events = []
        monkeypatch.setattr("alpacalyzer.execution.engine.emit_event", lambda e: emitted_events.append(e))
        monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_positions", list)
        _mock_market_context(monkeypatch)

        engine.run_cycle()

        exit_events = [e for e in emitted_events if isinstance(e, ExitTriggeredEvent)]
        assert len(exit_events) == 1
        assert exit_events[0].ticker == "AAPL"
        assert exit_events[0].exit_mechanism == "bracket_fill"
