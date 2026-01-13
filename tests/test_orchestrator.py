"""Tests for TradingOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest

from alpacalyzer.data.models import TopTicker, TradingStrategy
from alpacalyzer.execution.engine import ExecutionEngine
from alpacalyzer.execution.signal_queue import PendingSignal
from alpacalyzer.orchestrator import TradingOrchestrator
from alpacalyzer.pipeline.aggregator import OpportunityAggregator


@pytest.fixture
def mock_aggregator():
    """Mock OpportunityAggregator."""
    return MagicMock(spec=OpportunityAggregator)


@pytest.fixture
def mock_execution_engine():
    """Mock ExecutionEngine."""
    return MagicMock(spec=ExecutionEngine)


@pytest.fixture
def mock_strategy():
    """Mock Strategy."""
    return MagicMock()


@pytest.fixture
def orchestrator(mock_aggregator, mock_execution_engine, mock_strategy):
    """Create a TradingOrchestrator with mocked dependencies."""
    with (
        patch("alpacalyzer.orchestrator.OpportunityAggregator", return_value=mock_aggregator),
        patch("alpacalyzer.orchestrator.ExecutionEngine", return_value=mock_execution_engine),
        patch("alpacalyzer.orchestrator.get_market_status", return_value="open"),
    ):
        return TradingOrchestrator(
            strategy=mock_strategy,
            analyze_mode=False,
            direct_tickers=None,
            agents="ALL",
            ignore_market_status=False,
        )


class TestTradingOrchestratorInit:
    """Tests for TradingOrchestrator initialization."""

    def test_init_with_defaults(self, mock_aggregator, mock_execution_engine, mock_strategy):
        """Test initialization with default parameters."""
        with patch("alpacalyzer.orchestrator.OpportunityAggregator", return_value=mock_aggregator), patch("alpacalyzer.orchestrator.ExecutionEngine", return_value=mock_execution_engine):
            orchestrator = TradingOrchestrator(strategy=mock_strategy)

            assert orchestrator.analyze_mode is False
            assert orchestrator.direct_tickers == []
            assert orchestrator.agents == "ALL"
            assert orchestrator.ignore_market_status is False
            assert orchestrator.aggregator == mock_aggregator
            assert orchestrator.execution_engine == mock_execution_engine

    def test_init_with_analyze_mode(self, mock_aggregator, mock_execution_engine, mock_strategy):
        """Test initialization with analyze_mode enabled."""
        with patch("alpacalyzer.orchestrator.OpportunityAggregator", return_value=mock_aggregator), patch("alpacalyzer.orchestrator.ExecutionEngine") as mock_engine_class:
            mock_engine_class.return_value = mock_execution_engine
            orchestrator = TradingOrchestrator(strategy=mock_strategy, analyze_mode=True)

            assert orchestrator.analyze_mode is True
            # Verify ExecutionEngine was created with ExecutionConfig(analyze_mode=True)
            mock_engine_class.assert_called_once()
            call_kwargs = mock_engine_class.call_args[1]
            assert call_kwargs["config"].analyze_mode is True
            assert call_kwargs["strategy"] is mock_strategy

    def test_init_with_direct_tickers(self, mock_aggregator, mock_execution_engine, mock_strategy):
        """Test initialization with direct tickers."""
        tickers = ["AAPL", "MSFT"]
        with patch("alpacalyzer.orchestrator.OpportunityAggregator", return_value=mock_aggregator), patch("alpacalyzer.orchestrator.ExecutionEngine", return_value=mock_execution_engine):
            orchestrator = TradingOrchestrator(strategy=mock_strategy, direct_tickers=tickers)

            assert orchestrator.direct_tickers == tickers

    def test_init_with_agent_selection(self, mock_aggregator, mock_execution_engine, mock_strategy):
        """Test initialization with agent selection."""
        with patch("alpacalyzer.orchestrator.OpportunityAggregator", return_value=mock_aggregator), patch("alpacalyzer.orchestrator.ExecutionEngine", return_value=mock_execution_engine):
            orchestrator = TradingOrchestrator(strategy=mock_strategy, agents="TRADE")

            assert orchestrator.agents == "TRADE"

    def test_init_with_ignore_market_status(self, mock_aggregator, mock_execution_engine, mock_strategy):
        """Test initialization with ignore_market_status enabled."""
        with patch("alpacalyzer.orchestrator.OpportunityAggregator", return_value=mock_aggregator), patch("alpacalyzer.orchestrator.ExecutionEngine", return_value=mock_execution_engine):
            orchestrator = TradingOrchestrator(strategy=mock_strategy, ignore_market_status=True)

            assert orchestrator.ignore_market_status is True


class TestTradingOrchestratorScan:
    """Tests for TradingOrchestrator.scan() method."""

    def test_scan_calls_aggregator(self, orchestrator, mock_aggregator):
        """Test that scan() calls the aggregator."""
        orchestrator.scan()

        mock_aggregator.aggregate.assert_called_once()

    def test_scan_with_direct_tickers_skips_scanning(self, orchestrator, mock_aggregator):
        """Test that scan() skips scanning when direct_tickers provided."""
        orchestrator.direct_tickers = ["AAPL", "MSFT"]

        orchestrator.scan()

        mock_aggregator.aggregate.assert_not_called()

    def test_scan_returns_opportunities(self, orchestrator, mock_aggregator):
        """Test that scan() returns opportunities from aggregator."""
        # The scan method creates TopTicker objects from aggregator output
        mock_opportunity = MagicMock(ticker="AAPL", score=100.0, sources=["test"])
        mock_aggregator.top.return_value = [mock_opportunity]

        result = orchestrator.scan()

        # Result should be TopTicker objects
        assert len(result) == 1
        assert result[0].ticker == "AAPL"
        mock_aggregator.top.assert_called_once()

    def test_scan_with_direct_tickers_returns_mock_opportunities(self, orchestrator):
        """Test that scan() creates opportunities from direct tickers."""
        orchestrator.direct_tickers = ["AAPL", "MSFT"]
        orchestrator.aggregator.aggregate = MagicMock()

        result = orchestrator.scan()

        assert len(result) == 2
        assert result[0].ticker == "AAPL"
        assert result[1].ticker == "MSFT"
        orchestrator.aggregator.aggregate.assert_not_called()

    def test_scan_returns_empty_when_market_closed(self, orchestrator):
        """Test that scan returns empty list when market is closed."""
        orchestrator.is_market_open = False

        result = orchestrator.scan()

        assert result == []
        orchestrator.aggregator.aggregate.assert_not_called()


class TestTradingOrchestratorAnalyze:
    """Tests for TradingOrchestrator.analyze() method."""

    def test_analyze_returns_empty_when_market_closed(self, orchestrator):
        """Test that analyze returns empty list when market is closed."""
        orchestrator.is_market_open = False
        opportunities = [
            TopTicker(ticker="AAPL", confidence=75, signal="bullish", reasoning="Strong momentum"),
        ]

        with patch("alpacalyzer.orchestrator.call_hedge_fund_agents") as mock_hedge_fund:
            result = orchestrator.analyze(opportunities)

            assert result == []
            mock_hedge_fund.assert_not_called()

    def test_analyze_calls_hedge_fund(self, orchestrator):
        """Test that analyze() calls hedge fund agents."""
        opportunities = [
            TopTicker(ticker="AAPL", confidence=75, signal="bullish", reasoning="Strong momentum"),
        ]

        with patch("alpacalyzer.orchestrator.call_hedge_fund_agents") as mock_hedge_fund:
            mock_hedge_fund.return_value = {"decisions": {}, "analyst_signals": {}}
            orchestrator.analyze(opportunities)

            mock_hedge_fund.assert_called_once()

    def test_analyze_returns_strategies(self, orchestrator):
        """Test that analyze() returns trading strategies."""
        opportunities = [
            TopTicker(ticker="AAPL", confidence=75, signal="bullish", reasoning="Strong momentum"),
        ]

        strategy_dict = {
            "trade_type": "LONG",
            "entry_point": 150.0,
            "target_price": 165.0,
            "stop_loss": 145.0,
            "quantity": 100,
            "risk_reward_ratio": 3.0,
            "strategy_notes": "Strong bullish setup",
            "entry_criteria": [],
            "ticker": "AAPL",
        }

        with patch("alpacalyzer.orchestrator.call_hedge_fund_agents") as mock_hedge_fund:
            mock_hedge_fund.return_value = {
                "decisions": {"AAPL": {"strategies": [strategy_dict]}},
                "analyst_signals": {},
            }

            strategies = orchestrator.analyze(opportunities)

            assert len(strategies) == 1
            assert strategies[0].ticker == "AAPL"

    def test_analyze_with_no_opportunities(self, orchestrator):
        """Test that analyze() handles empty opportunities."""
        with patch("alpacalyzer.orchestrator.call_hedge_fund_agents") as mock_hedge_fund:
            strategies = orchestrator.analyze([])

            mock_hedge_fund.assert_not_called()
            assert strategies == []

    def test_analyze_filters_active_positions(self, orchestrator):
        """Test that analyze() filters out already active positions."""
        opportunities = [
            TopTicker(ticker="AAPL", confidence=75, signal="bullish", reasoning="Strong momentum"),
            TopTicker(ticker="MSFT", confidence=80, signal="bullish", reasoning="Strong momentum"),
        ]

        with patch("alpacalyzer.orchestrator.get_positions") as mock_get_positions, patch("alpacalyzer.orchestrator.call_hedge_fund_agents") as mock_hedge_fund:
            # Mock AAPL as already active
            mock_position = MagicMock()
            mock_position.symbol = "AAPL"
            mock_get_positions.return_value = [mock_position]

            mock_hedge_fund.return_value = {"decisions": {}, "analyst_signals": {}}

            orchestrator.analyze(opportunities)

            # Should only call with MSFT (not AAPL which is active)
            call_args = mock_hedge_fund.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0].ticker == "MSFT"

    def test_analyze_with_cooldown(self, orchestrator):
        """Test that analyze() filters out tickers in cooldown."""
        from datetime import UTC, datetime, timedelta

        opportunities = [
            TopTicker(ticker="AAPL", confidence=75, signal="bullish", reasoning="Strong momentum"),
            TopTicker(ticker="MSFT", confidence=80, signal="bullish", reasoning="Strong momentum"),
        ]

        # Add AAPL to cooldown
        orchestrator.recently_exited_tickers = {"AAPL": datetime.now(UTC) - timedelta(hours=1)}

        with patch("alpacalyzer.orchestrator.call_hedge_fund_agents") as mock_hedge_fund:
            mock_hedge_fund.return_value = {"decisions": {}, "analyst_signals": {}}

            orchestrator.analyze(opportunities)

            # Should only call with MSFT (not AAPL which is in cooldown)
            call_args = mock_hedge_fund.call_args[0][0]
            assert len(call_args) == 1
            assert call_args[0].ticker == "MSFT"


class TestTradingOrchestratorExecute:
    """Tests for TradingOrchestrator.execute() method."""

    def test_execute_adds_signals_to_engine(self, orchestrator, mock_execution_engine):
        """Test that execute() adds signals to execution engine."""
        strategy = TradingStrategy(
            ticker="AAPL",
            trade_type="LONG",
            entry_point=150.0,
            target_price=165.0,
            stop_loss=145.0,
            quantity=100,
            risk_reward_ratio=3.0,
            strategy_notes="Strong bullish setup",
            entry_criteria=[],
        )

        orchestrator.execute([strategy])

        mock_execution_engine.add_signal.assert_called_once()
        signal_arg = mock_execution_engine.add_signal.call_args[0][0]
        assert isinstance(signal_arg, PendingSignal)
        assert signal_arg.ticker == "AAPL"

    def test_execute_runs_engine_cycle(self, orchestrator, mock_execution_engine):
        """Test that execute() runs the execution engine cycle."""
        strategy = TradingStrategy(
            ticker="AAPL",
            trade_type="LONG",
            entry_point=150.0,
            target_price=165.0,
            stop_loss=145.0,
            quantity=100,
            risk_reward_ratio=3.0,
            strategy_notes="Strong bullish setup",
            entry_criteria=[],
        )

        orchestrator.execute([strategy])

        mock_execution_engine.run_cycle.assert_called_once()


class TestTradingOrchestratorRunCycle:
    """Tests for TradingOrchestrator.run_cycle() method."""

    def test_run_cycle_full_pipeline(self, orchestrator):
        """Test that run_cycle() executes full pipeline when strategies exist."""
        from alpacalyzer.orchestrator import TradingOrchestrator

        with patch.object(TradingOrchestrator, "scan") as mock_scan, patch.object(TradingOrchestrator, "analyze") as mock_analyze, patch.object(TradingOrchestrator, "execute") as mock_execute:
            mock_opportunities = [MagicMock(ticker="AAPL")]
            strategy = TradingStrategy(
                ticker="AAPL",
                trade_type="LONG",
                entry_point=150.0,
                target_price=165.0,
                stop_loss=145.0,
                quantity=100,
                risk_reward_ratio=3.0,
                strategy_notes="Test",
                entry_criteria=[],
            )
            mock_scan.return_value = mock_opportunities
            mock_analyze.return_value = [strategy]

            orchestrator.run_cycle()

            mock_scan.assert_called_once()
            mock_analyze.assert_called_once_with(mock_opportunities)
            mock_execute.assert_called_once_with([strategy])

    def test_run_cycle_with_no_opportunities(self, orchestrator):
        """Test that run_cycle() handles no opportunities gracefully."""
        from alpacalyzer.orchestrator import TradingOrchestrator

        with patch.object(TradingOrchestrator, "scan") as mock_scan, patch.object(TradingOrchestrator, "analyze") as mock_analyze, patch.object(TradingOrchestrator, "execute") as mock_execute:
            mock_scan.return_value = []

            orchestrator.run_cycle()

            # With no opportunities, analyze and execute should not be called
            mock_analyze.assert_not_called()
            mock_execute.assert_not_called()

    def test_run_cycle_with_direct_tickers(self, orchestrator):
        """Test that run_cycle() works with direct tickers when strategies exist."""
        from alpacalyzer.orchestrator import TradingOrchestrator

        orchestrator.direct_tickers = ["AAPL"]

        with patch.object(TradingOrchestrator, "scan") as mock_scan, patch.object(TradingOrchestrator, "analyze") as mock_analyze, patch.object(TradingOrchestrator, "execute") as mock_execute:
            mock_opportunities = [MagicMock(ticker="AAPL")]
            strategy = TradingStrategy(
                ticker="AAPL",
                trade_type="LONG",
                entry_point=150.0,
                target_price=165.0,
                stop_loss=145.0,
                quantity=100,
                risk_reward_ratio=3.0,
                strategy_notes="Test",
                entry_criteria=[],
            )
            mock_scan.return_value = mock_opportunities
            mock_analyze.return_value = [strategy]

            orchestrator.run_cycle()

            mock_scan.assert_called_once()
            mock_analyze.assert_called_once_with(mock_opportunities)
            mock_execute.assert_called_once_with([strategy])

    def test_run_cycle_with_strategies(self, orchestrator, mock_execution_engine):
        """Test that run_cycle() passes strategies to execute."""
        strategy = TradingStrategy(
            ticker="AAPL",
            trade_type="LONG",
            entry_point=150.0,
            target_price=165.0,
            stop_loss=145.0,
            quantity=100,
            risk_reward_ratio=3.0,
            strategy_notes="Strong bullish setup",
            entry_criteria=[],
        )

        with patch.object(orchestrator, "scan") as mock_scan, patch.object(orchestrator, "analyze") as mock_analyze, patch.object(orchestrator, "execute") as mock_execute:
            mock_opportunities = [MagicMock(ticker="AAPL")]
            mock_scan.return_value = mock_opportunities
            mock_analyze.return_value = [strategy]

            orchestrator.run_cycle()

            mock_execute.assert_called_once_with([strategy])


class TestTradingOrchestratorCooldowns:
    """Tests for TradingOrchestrator cooldown management."""

    def test_cleanup_expired_cooldowns(self, orchestrator):
        """Test that expired cooldowns are cleaned up."""
        from datetime import UTC, datetime, timedelta

        # Add an expired cooldown
        orchestrator.recently_exited_tickers = {
            "AAPL": datetime.now(UTC) - timedelta(hours=4)  # Past 3 hour cooldown
        }

        with patch("alpacalyzer.events.emit_event") as mock_emit:
            orchestrator._cleanup_cooldowns()

            assert "AAPL" not in orchestrator.recently_exited_tickers
            mock_emit.assert_called_once()

    def test_active_cooldowns_not_cleaned(self, orchestrator):
        """Test that active cooldowns are not cleaned up."""
        from datetime import UTC, datetime, timedelta

        # Add an active cooldown
        orchestrator.recently_exited_tickers = {
            "AAPL": datetime.now(UTC) - timedelta(hours=1)  # Within 3 hour cooldown
        }

        with patch("alpacalyzer.events.emit_event") as mock_emit:
            orchestrator._cleanup_cooldowns()

            assert "AAPL" in orchestrator.recently_exited_tickers
            mock_emit.assert_not_called()
