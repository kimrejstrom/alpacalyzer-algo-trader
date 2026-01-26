"""Tests for ExecutionEngine."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

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
            return []

        monkeypatch.setattr(engine.positions, "sync_from_broker", mock_sync)

        # Mock Alpaca API calls used by _build_market_context
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_status",
            lambda: "open",
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_account_info",
            lambda: {"equity": 10000.0, "buying_power": 8000.0},
        )

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
        engine.cooldowns.add_cooldown("MSFT", "test reason", "test_strategy")

        context = engine._build_market_context()

        assert context.market_status == "open"
        assert context.account_equity == 10000.0
        assert context.buying_power == 8000.0
        assert "AAPL" in context.existing_positions
        assert "MSFT" in context.cooldown_tickers

    def test_execute_exit_adds_cooldown(self, monkeypatch):
        """Test that _execute_exit adds cooldown after closing position."""
        from unittest.mock import MagicMock, patch

        config = ExecutionConfig(analyze_mode=True)
        strategy = MockStrategy()
        engine = ExecutionEngine(strategy, config)

        mock_position = MagicMock()
        mock_position.ticker = "AAPL"
        mock_position.side = "long"
        mock_position.quantity = 10
        mock_position.avg_entry_price = 150.0
        mock_position.unrealized_pnl = 50.0
        mock_position.unrealized_pnl_pct = 0.033

        mock_decision = ExitDecision(should_exit=True, reason="stop_loss_hit", urgency="urgent")

        mock_order = MagicMock()
        mock_order.filled_avg_price = 155.0
        monkeypatch.setattr(engine.orders, "close_position", lambda ticker: mock_order)

        with patch("alpacalyzer.execution.engine.emit_event") as mock_emit:
            engine._execute_exit(mock_position, mock_decision)

        mock_emit.assert_called_once()
        call_args = mock_emit.call_args[0][0]
        assert call_args.event_type == "EXIT_TRIGGERED"
        assert call_args.ticker == "AAPL"
        assert call_args.side == "long"
        assert call_args.quantity == 10
        assert call_args.entry_price == 150.0
        assert call_args.exit_price == 155.0
        assert call_args.pnl == 50.0
        assert call_args.pnl_pct == 0.033
        assert call_args.reason == "stop_loss_hit"
        assert call_args.urgency == "urgent"

        assert engine.cooldowns.is_in_cooldown("AAPL")
        entry = engine.cooldowns.get_cooldown("AAPL")
        assert entry is not None
        assert entry.reason == "stop_loss_hit"
        assert entry.strategy_name == "execution_engine"

    def test_build_market_context_uses_real_vix(self, monkeypatch):
        """Test that MarketContext contains actual VIX value from API."""

        from alpacalyzer.data.api import _vix_cache
        from alpacalyzer.execution.engine import ExecutionEngine

        strategy = MockStrategy()
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_status",
            lambda: "open",
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_account_info",
            lambda: {"equity": 10000.0, "buying_power": 8000.0},
        )

        def mock_sync():
            pass

        _vix_cache.clear()
        monkeypatch.setattr(
            "alpacalyzer.data.api.get_vix",
            lambda use_cache=True: 28.5,
        )

        engine = ExecutionEngine(strategy)
        monkeypatch.setattr(engine.positions, "sync_from_broker", mock_sync)

        context = engine._build_market_context()

        assert context.vix == 28.5
        assert 10.0 < context.vix < 50.0

    def test_build_market_context_logs_elevated_vix(self, monkeypatch):
        """Test that warning is logged when VIX > 30."""
        from alpacalyzer.execution.engine import ExecutionEngine
        from alpacalyzer.utils.logger import get_logger

        strategy = MockStrategy()
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_status",
            lambda: "open",
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_account_info",
            lambda: {"equity": 10000.0, "buying_power": 8000.0},
        )

        def mock_sync():
            pass

        monkeypatch.setattr(
            "alpacalyzer.data.api.get_vix",
            lambda use_cache=True: 35.0,
        )

        engine = ExecutionEngine(strategy)
        monkeypatch.setattr(engine.positions, "sync_from_broker", mock_sync)

        logger = get_logger()
        with patch.object(logger, "warning") as mock_warning:
            engine._build_market_context()

            assert mock_warning.called
            call_args = str(mock_warning.call_args)
            assert "Elevated VIX" in call_args

    def test_build_market_context_fallback_vix_on_error(self, monkeypatch):
        """Test that fallback VIX (25.0) is used when API returns default."""
        from alpacalyzer.execution.engine import ExecutionEngine

        strategy = MockStrategy()
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_status",
            lambda: "open",
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_account_info",
            lambda: {"equity": 10000.0, "buying_power": 8000.0},
        )

        def mock_sync():
            pass

        monkeypatch.setattr(
            "alpacalyzer.data.api.get_vix",
            lambda use_cache=True: 25.0,
        )

        engine = ExecutionEngine(strategy)
        monkeypatch.setattr(engine.positions, "sync_from_broker", mock_sync)

        context = engine._build_market_context()

        assert context.vix == 25.0
