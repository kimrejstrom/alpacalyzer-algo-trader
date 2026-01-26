"""Tests for Risk Management Agent."""

from unittest.mock import MagicMock

from alpacalyzer.graph.state import AgentState
from alpacalyzer.trading.risk_manager import risk_management_agent


class TestShortPositionMarginCalculation:
    """Test that short positions use correct margin calculation (divide, not multiply)."""

    def test_short_position_margin_calculation(self, monkeypatch):
        """Test that short positions use division for margin calculation."""
        state = AgentState(
            messages=[],
            data={
                "tickers": ["AAPL"],
                "portfolio": {},
                "AAPL": {"signal": "bearish"},
                "analyst_signals": {
                    "potential_candidates_agent": {
                        "AAPL": {
                            "signal": "bearish",
                            "confidence": 80.0,
                            "reasoning": "Test bearish signal",
                        }
                    }
                },
            },
            metadata={"show_reasoning": False},
        )

        mock_position = MagicMock()
        mock_position.symbol = "AAPL"
        mock_position.qty = "0"
        mock_position.cost_basis = "0"
        mock_position.current_price = "150.00"
        mock_position.side = "long"
        mock_position.unrealized_pl = "0"

        mock_account = {
            "equity": 100000.0,
            "buying_power": 50000.0,
            "daytrading_buying_power": 200000.0,
            "maintenance_margin": 2500.0,
        }

        def mock_get_all_positions():
            return [mock_position]

        def mock_get_account_info():
            return mock_account

        def mock_get_current_price(ticker):
            return 150.0

        monkeypatch.setattr(
            "alpacalyzer.trading.risk_manager.trading_client.get_all_positions",
            mock_get_all_positions,
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.risk_manager.get_account_info",
            mock_get_account_info,
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.risk_manager.get_current_price",
            mock_get_current_price,
        )

        result = risk_management_agent(state)

        risk_data = result["data"]["analyst_signals"]["risk_management_agent"]["AAPL"]

        expected_adjusted_buying_power = mock_account["daytrading_buying_power"] / 0.5 * 0.9

        actual_adjusted_buying_power = risk_data["reasoning"]["adjusted_buying_power"]

        assert actual_adjusted_buying_power == expected_adjusted_buying_power, (
            f"Expected adjusted_buying_power {expected_adjusted_buying_power}, got {actual_adjusted_buying_power}. Short positions should DIVIDE by margin requirement, not multiply."
        )
