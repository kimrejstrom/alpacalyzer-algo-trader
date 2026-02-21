"""
End-to-end pipeline integration tests.

Verifies that data flows correctly through the full trading pipeline:
  scanner signals → aggregator → orchestrator → hedge fund agents → strategies

These tests mock external boundaries (Alpaca API, LLM) but let the internal
pipeline run with real objects to catch data-loss bugs like:
- Scanner signals being dropped by the aggregator
- Portfolio data not reaching the portfolio manager
- Opportunity reasoning not reaching hedge fund agents
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from alpacalyzer.data.models import TopTicker
from alpacalyzer.pipeline.aggregator import OpportunityAggregator
from alpacalyzer.pipeline.scanner_protocol import ScanResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bullish_tickers():
    """Scanner output with clear bullish signals and reasoning."""
    return [
        TopTicker(
            ticker="NVDA",
            signal="bullish",
            confidence=85.0,
            reasoning="Strong momentum, AI demand catalyst",
            mentions=120,
            upvotes=500,
            rank=1,
        ),
        TopTicker(
            ticker="TSLA",
            signal="bearish",
            confidence=70.0,
            reasoning="Overvalued, delivery miss expected",
            mentions=80,
            upvotes=200,
            rank=3,
        ),
    ]


@pytest.fixture
def scan_results(bullish_tickers):
    """Wrap tickers in ScanResult objects as the aggregator expects."""
    return [
        ScanResult(
            source="reddit",
            tickers=bullish_tickers,
            duration_seconds=1.5,
        ),
    ]


@pytest.fixture
def mock_account():
    """Realistic Alpaca account data."""
    return {
        "equity": 50_000.0,
        "buying_power": 100_000.0,
        "initial_margin": 5_000.0,
        "margin_multiplier": 4.0,
        "daytrading_buying_power": 200_000.0,
        "maintenance_margin": 3_000.0,
    }


# ---------------------------------------------------------------------------
# Test: scanner signals survive the aggregator
# ---------------------------------------------------------------------------


class TestSignalPreservation:
    """Verify scanner signal/reasoning data is not lost in the aggregator."""

    def test_aggregator_preserves_signal(self, scan_results):
        agg = OpportunityAggregator()
        agg.aggregate(scan_results)

        opp = agg.get("NVDA")
        assert opp is not None
        assert opp.signal == "bullish"
        assert opp.confidence == 85.0
        assert any("Strong momentum" in r for r in opp.reasoning)

    def test_aggregator_preserves_bearish_signal(self, scan_results):
        agg = OpportunityAggregator()
        agg.aggregate(scan_results)

        opp = agg.get("TSLA")
        assert opp is not None
        assert opp.signal == "bearish"
        assert opp.confidence == 70.0

    def test_aggregator_multi_source_upgrades_signal(self):
        """When a second source provides a stronger signal, it should upgrade."""
        results = [
            ScanResult(
                source="social",
                tickers=[TopTicker(ticker="AAPL", signal="neutral", confidence=50.0, reasoning="Trending")],
                duration_seconds=1.0,
            ),
            ScanResult(
                source="reddit",
                tickers=[TopTicker(ticker="AAPL", signal="bullish", confidence=90.0, reasoning="Strong buy signal")],
                duration_seconds=1.0,
            ),
        ]
        agg = OpportunityAggregator()
        agg.aggregate(results)

        opp = agg.get("AAPL")
        assert opp is not None
        assert opp.signal == "bullish"
        assert opp.confidence == 90.0
        assert len(opp.reasoning) == 2
        assert any("[social]" in r for r in opp.reasoning)
        assert any("[reddit]" in r for r in opp.reasoning)


# ---------------------------------------------------------------------------
# Test: orchestrator.scan() preserves signals into TopTicker output
# ---------------------------------------------------------------------------


class TestOrchestratorSignalPassthrough:
    """Verify orchestrator.scan() converts Opportunity → TopTicker without losing data."""

    @patch("alpacalyzer.orchestrator.get_market_status", return_value="open")
    @patch("alpacalyzer.orchestrator.get_positions", return_value=[])
    @patch("alpacalyzer.orchestrator.ExecutionEngine")
    def test_scan_preserves_signal_and_reasoning(self, mock_engine, mock_pos, mock_market, scan_results):
        from alpacalyzer.orchestrator import TradingOrchestrator

        strategy = MagicMock()
        orch = TradingOrchestrator(strategy=strategy, analyze_mode=True)

        # Inject scan results directly into the aggregator
        orch.aggregator.aggregate(scan_results)

        # Now call scan — it should use the already-aggregated data
        # We need to prevent it from re-running aggregate
        with patch.object(orch.aggregator, "aggregate"):
            result = orch.scan()

        nvda = next((t for t in result if t.ticker == "NVDA"), None)
        assert nvda is not None
        assert nvda.signal == "bullish"
        assert nvda.confidence > 0
        assert "Strong momentum" in nvda.reasoning

        tsla = next((t for t in result if t.ticker == "TSLA"), None)
        assert tsla is not None
        assert tsla.signal == "bearish"


# ---------------------------------------------------------------------------
# Test: portfolio data reaches the portfolio manager
# ---------------------------------------------------------------------------


class TestPortfolioDataFlow:
    """Verify that real account data is passed to the hedge fund agent graph."""

    @patch("alpacalyzer.hedge_fund.get_positions")
    @patch("alpacalyzer.hedge_fund.get_account_info")
    def test_build_portfolio_populates_cash_and_margin(self, mock_account_info, mock_positions, mock_account):
        from alpacalyzer.hedge_fund import _build_portfolio

        mock_account_info.return_value = mock_account
        mock_positions.return_value = []

        portfolio = _build_portfolio()

        assert portfolio["cash"] == 100_000.0
        assert portfolio["margin_requirement"] == 5_000.0
        assert portfolio["positions"] == {}

    @patch("alpacalyzer.hedge_fund.get_positions")
    @patch("alpacalyzer.hedge_fund.get_account_info")
    def test_build_portfolio_includes_positions(self, mock_account_info, mock_positions, mock_account):
        from alpacalyzer.hedge_fund import _build_portfolio

        mock_account_info.return_value = mock_account

        pos = MagicMock()
        pos.symbol = "NVDA"
        pos.qty = "10"
        pos.avg_entry_price = "130.50"
        pos.side = "long"
        mock_positions.return_value = [pos]

        portfolio = _build_portfolio()

        assert "NVDA" in portfolio["positions"]
        assert portfolio["positions"]["NVDA"]["shares"] == 10
        assert portfolio["positions"]["NVDA"]["avg_price"] == 130.50
        assert portfolio["positions"]["NVDA"]["side"] == "long"

    @patch("alpacalyzer.hedge_fund.get_positions")
    @patch("alpacalyzer.hedge_fund.get_account_info")
    def test_build_portfolio_handles_api_failure(self, mock_account_info, mock_positions):
        from alpacalyzer.hedge_fund import _build_portfolio

        mock_account_info.side_effect = Exception("API down")

        portfolio = _build_portfolio()

        assert portfolio["cash"] == 0
        assert portfolio["positions"] == {}
        assert portfolio["margin_requirement"] == 0


# ---------------------------------------------------------------------------
# Test: full pipeline data integrity (scanner → hedge fund input)
# ---------------------------------------------------------------------------


class TestFullPipelineDataIntegrity:
    """
    End-to-end test: verify scanner signals + portfolio data reach the agent graph.

    Mocks: Alpaca API, LLM, langgraph compile/invoke
    Real:  aggregator, orchestrator.scan(), orchestrator.analyze(), hedge_fund
    """

    @patch("alpacalyzer.orchestrator.get_market_status", return_value="open")
    @patch("alpacalyzer.orchestrator.get_positions", return_value=[])
    @patch("alpacalyzer.orchestrator.ExecutionEngine")
    @patch("alpacalyzer.orchestrator.call_hedge_fund_agents")
    def test_scanner_signals_reach_hedge_fund(self, mock_hedge_fund, mock_engine, mock_pos, mock_market, scan_results):
        """The hedge fund agents must receive the original signal/reasoning from scanners."""
        from alpacalyzer.orchestrator import TradingOrchestrator

        # Set up hedge fund to capture what it receives
        captured_tickers = []

        def capture_call(tickers, agents, show_reasoning):
            captured_tickers.extend(tickers)
            return {"decisions": {}, "analyst_signals": {}}

        mock_hedge_fund.side_effect = capture_call

        strategy = MagicMock()
        orch = TradingOrchestrator(strategy=strategy, analyze_mode=True)

        # Run aggregator with our scan results
        orch.aggregator.aggregate(scan_results)

        # Prevent re-aggregation, just use what we set up
        with patch.object(orch.aggregator, "aggregate"):
            opportunities = orch.scan()

        orch.analyze(opportunities)

        # Verify the hedge fund received tickers with preserved signals
        assert len(captured_tickers) >= 2

        nvda = next((t for t in captured_tickers if t.ticker == "NVDA"), None)
        assert nvda is not None, "NVDA should reach hedge fund agents"
        assert nvda.signal == "bullish", "Bullish signal must survive pipeline"
        assert nvda.confidence > 0, "Confidence must not be zero"
        assert "Strong momentum" in nvda.reasoning, "Reasoning must survive pipeline"

        tsla = next((t for t in captured_tickers if t.ticker == "TSLA"), None)
        assert tsla is not None, "TSLA should reach hedge fund agents"
        assert tsla.signal == "bearish", "Bearish signal must survive pipeline"

    @patch("alpacalyzer.hedge_fund.get_positions")
    @patch("alpacalyzer.hedge_fund.get_account_info")
    @patch("alpacalyzer.hedge_fund.progress")
    def test_portfolio_data_reaches_agent_graph(self, mock_progress, mock_account_info, mock_positions, mock_account, bullish_tickers):
        """The agent graph must receive non-zero portfolio cash and margin."""
        from alpacalyzer.hedge_fund import call_hedge_fund_agents

        mock_account_info.return_value = mock_account
        mock_positions.return_value = []

        # Capture the state passed to agent.invoke
        captured_invoke_args = {}

        with patch("alpacalyzer.hedge_fund.create_workflow") as mock_workflow:
            mock_agent = MagicMock()
            mock_workflow.return_value.compile.return_value = mock_agent

            def capture_invoke(state):
                captured_invoke_args.update(state)
                return {
                    "messages": [HumanMessage(content="{}")],
                    "data": state["data"],
                }

            mock_agent.invoke.side_effect = capture_invoke

            call_hedge_fund_agents(bullish_tickers, agents="TRADE", show_reasoning=False)

        # Portfolio must have real values, not empty/zero
        portfolio = captured_invoke_args["data"]["portfolio"]
        assert portfolio["cash"] > 0, "Portfolio cash must not be zero — LLM needs this to make decisions"
        assert portfolio["cash"] == 100_000.0
        assert portfolio["margin_requirement"] == 5_000.0

        # Scanner signals must be in analyst_signals
        candidates = captured_invoke_args["data"]["analyst_signals"]["potential_candidates_agent"]
        assert "NVDA" in candidates
        assert candidates["NVDA"]["signal"] == "bullish"
        assert candidates["NVDA"]["confidence"] == 85.0
        assert "Strong momentum" in candidates["NVDA"]["reasoning"]
