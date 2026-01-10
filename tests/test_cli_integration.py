"""Tests for CLI integration with ExecutionEngine."""

from alpacalyzer.trading.trader import Trader


class TestHedgeFundToSignalBridge:
    """Test hedge fund output conversion to signals."""

    def test_convert_hedge_fund_strategies_to_signals(self, monkeypatch):
        """Convert hedge fund TradingStrategy objects to PendingSignal objects."""

        # Mock market status BEFORE creating trader
        monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_market_status", lambda: "open")

        # Mock get_positions
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_positions",
            list,
        )

        # Mock print_trading_output to avoid display issues
        monkeypatch.setattr(
            "alpacalyzer.trading.trader.print_trading_output",
            lambda x: None,
        )

        # Create trader with ignore_market_status to bypass market checks
        trader = Trader(analyze_mode=True, direct_tickers=[], ignore_market_status=True)

        # Mock hedge fund response with proper structure
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

        # Add opportunities directly
        from alpacalyzer.data.models import TopTicker

        trader.opportunities = [TopTicker(ticker="AAPL", confidence=80, signal="bullish", reasoning="Test")]

        # Mock hedge fund agents to return our response
        monkeypatch.setattr(
            "alpacalyzer.trading.trader.call_hedge_fund_agents",
            lambda x, y, show_reasoning=False: hedge_fund_response,
        )

        # Run hedge fund
        trader.run_hedge_fund()

        # Verify strategies were added
        assert len(trader.latest_strategies) == 1

        # Call new method to get signals
        signals = trader.get_signals_from_strategies()

        assert len(signals) == 1
        signal = signals[0]
        assert signal.ticker == "AAPL"
        assert signal.action == "buy"
        assert signal.source == "hedge_fund"
        assert signal.agent_recommendation is not None
        assert signal.agent_recommendation.ticker == "AAPL"

        # Verify strategies were cleared after conversion
        assert len(trader.latest_strategies) == 0

    def test_empty_strategies_returns_empty_signals(self):
        """Test that empty strategies list returns empty signals."""
        trader = Trader(analyze_mode=True, direct_tickers=[])

        signals = trader.get_signals_from_strategies()

        assert len(signals) == 0
        assert isinstance(signals, list)
