"""Tests for CLI integration with ExecutionEngine."""

from alpacalyzer.data.models import TopTicker
from alpacalyzer.execution.signal_queue import PendingSignal
from alpacalyzer.orchestrator import TradingOrchestrator
from alpacalyzer.strategies.registry import StrategyRegistry
from tests.execution.mock_broker import mock_alpaca_client

hedge_fund_response = {
    "analyst_signals": {
        "portfolio_management_agent": {
            "AAPL": {
                "signal": "bullish",
                "confidence": 80,
            }
        }
    },
    "decisions": {
        "AAPL": {
            "strategies": [
                {
                    "ticker": "AAPL",
                    "quantity": 10,
                    "entry_point": 150.0,
                    "stop_loss": 145.0,
                    "target_price": 160.0,
                    "risk_reward_ratio": 2.0,
                    "strategy_notes": "Technical breakout",
                    "trade_type": "long",
                    "entry_criteria": [
                        {
                            "entry_type": "rsi_oversold",
                            "value": 25.0,
                        }
                    ],
                }
            ],
            "reasoning": "Strong momentum",
        }
    },
}


class TestHedgeFundToSignalBridge:
    """Test hedge fund output conversion to signals."""

    def test_convert_hedge_fund_strategies_to_signals(self, monkeypatch):
        """Convert hedge fund TradingStrategy objects to PendingSignal objects."""

        mock_alpaca_client(monkeypatch)

        monkeypatch.setattr(
            "alpacalyzer.orchestrator.call_hedge_fund_agents",
            lambda x, y, show_reasoning=False: hedge_fund_response,
        )

        strategy = StrategyRegistry.get("momentum")

        orchestrator = TradingOrchestrator(
            strategy=strategy,
            analyze_mode=True,
            direct_tickers=[],
            ignore_market_status=True,
        )

        opportunities = [TopTicker(ticker="AAPL", confidence=80, signal="bullish", reasoning="Test")]

        strategies = orchestrator.analyze(opportunities)

        assert len(strategies) == 1

        signals = []
        for strategy_obj in strategies:
            signal = PendingSignal.from_strategy(strategy_obj, source="hedge_fund")
            signals.append(signal)

        assert len(signals) == 1
        signal = signals[0]
        assert signal.ticker == "AAPL"
        assert signal.action == "buy"
        assert signal.source == "hedge_fund"
        assert signal.agent_recommendation is not None
        assert signal.agent_recommendation.ticker == "AAPL"

    def test_empty_strategies_returns_empty_signals(self, monkeypatch):
        """Test that empty strategies list returns empty signals."""
        mock_alpaca_client(monkeypatch)

        monkeypatch.setattr(
            "alpacalyzer.hedge_fund.call_hedge_fund_agents",
            lambda x, y, show_reasoning=False: hedge_fund_response,
        )

        strategy = StrategyRegistry.get("momentum")

        orchestrator = TradingOrchestrator(
            strategy=strategy,
            analyze_mode=True,
            direct_tickers=[],
            ignore_market_status=True,
        )

        strategies = orchestrator.analyze([])

        assert len(strategies) == 0
        assert isinstance(strategies, list)
