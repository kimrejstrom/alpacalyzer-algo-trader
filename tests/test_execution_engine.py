"""Tests for ExecutionEngine."""

from dataclasses import dataclass
from unittest.mock import MagicMock

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.data.models import TradingStrategy
from alpacalyzer.execution.engine import ExecutionConfig, ExecutionEngine
from alpacalyzer.execution.signal_queue import PendingSignal
from alpacalyzer.strategies.base import EntryDecision, ExitDecision, MarketContext, Strategy


@dataclass
class MockStrategy(Strategy):
    """Mock strategy for testing."""

    def evaluate_entry(
        self,
        signal: TradingSignals,
        context: MarketContext,
        agent_recommendation: "TradingStrategy | None" = None,
    ) -> EntryDecision:
        """Mock entry decision."""
        if signal.get("symbol") == "REJECT":
            return EntryDecision(should_enter=False, reason="Test rejection")
        return EntryDecision(
            should_enter=True,
            reason="Test acceptance",
            suggested_size=10,
            entry_price=signal.get("price", 100.0),
            stop_loss=95.0,
            target=110.0,
        )

    def evaluate_exit(
        self,
        position,
        signal: TradingSignals,
        context: MarketContext,
    ) -> ExitDecision:
        """Mock exit decision."""
        pnl: float = 0.0
        if isinstance(position.unrealized_pl, int | float):
            pnl = float(position.unrealized_pl)

        if pnl < -100:
            return ExitDecision(should_exit=True, reason="Stop loss hit", urgency="urgent")
        if pnl > 100:
            return ExitDecision(should_exit=True, reason="Target hit", urgency="normal")
        return ExitDecision(should_exit=False, reason="Hold position")

    def calculate_position_size(
        self,
        signal: TradingSignals,
        context: MarketContext,
        max_amount: float,
    ) -> int:
        """Mock position sizing."""
        return 10


class TestExecutionConfig:
    def test_default_config(self):
        """Create config with defaults."""
        config = ExecutionConfig()
        assert config.check_interval_seconds == 120
        assert config.max_positions == 10
        assert config.daily_loss_limit_pct == 0.05
        assert config.analyze_mode is False


class TestExecutionEngine:
    def test_initial_state(self):
        """Engine starts with no running state."""
        config = ExecutionConfig(analyze_mode=True)
        strategy = MockStrategy()

        engine = ExecutionEngine(strategy, config)

        assert engine._running is False
        assert engine.strategy == strategy
        assert engine.config == config

    def test_run_cycle_in_analyze_mode(self, monkeypatch):
        """Analyze mode skips order submission."""
        config = ExecutionConfig(analyze_mode=True)
        strategy = MockStrategy()

        engine = ExecutionEngine(strategy, config)

        # Mock position sync to not do anything in analyze mode
        def mock_sync():
            pass

        monkeypatch.setattr(engine.positions, "sync_from_broker", mock_sync)

        # Run cycle should not raise
        engine.run_cycle()

    def test_add_signal(self):
        """Can add signals to the engine."""
        engine = ExecutionEngine(MockStrategy())
        signal = PendingSignal(
            priority=50,
            ticker="AAPL",
            action="buy",
            confidence=75.0,
            source="test",
        )

        engine.add_signal(signal)

        assert engine.signal_queue.size() == 1

    def test_start_stop(self):
        """Can start and stop the engine."""
        engine = ExecutionEngine(MockStrategy())

        assert engine._running is False

        engine.start()
        assert engine._running is True

        engine.stop()
        assert engine._running is False

    def test_build_market_context(self, monkeypatch):
        """Builds market context from current state."""
        strategy = MockStrategy()

        # Mock get_market_status - it's used inside the function
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_status",
            lambda: "open",
        )

        # Mock get_account_info
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_account_info",
            lambda: {"equity": 10000.0, "buying_power": 8000.0},
        )

        def mock_sync():
            pass

        engine = ExecutionEngine(strategy)
        monkeypatch.setattr(engine.positions, "sync_from_broker", mock_sync)

        # Add position and cooldown
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.qty = "10"
        mock_pos.unrealized_pl = "50"

        engine.positions._positions["AAPL"] = MagicMock()
        engine.cooldowns.add("MSFT", minutes=5)

        context = engine._build_market_context()

        assert context.market_status == "open"
        assert context.account_equity == 10000.0
        assert context.buying_power == 8000.0
        assert "AAPL" in context.existing_positions
        assert "MSFT" in context.cooldown_tickers
