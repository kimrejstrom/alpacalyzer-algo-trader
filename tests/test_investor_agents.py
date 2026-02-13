import json

from alpacalyzer.agents.ben_graham_agent import serialize_graham_analysis
from alpacalyzer.agents.bill_ackman_agent import serialize_ackman_analysis
from alpacalyzer.agents.cathie_wood_agent import serialize_cathie_wood_analysis
from alpacalyzer.agents.charlie_munger import serialize_munger_analysis
from alpacalyzer.agents.warren_buffet_agent import serialize_buffett_analysis


def add_confidence_units(data):
    """Recursively add % suffix to confidence values (from technicals_agent)."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key == "confidence" and isinstance(value, int | float):
                result[key] = f"{value}%"
            else:
                result[key] = add_confidence_units(value)
        return result
    if isinstance(data, list):
        return [add_confidence_units(item) for item in data]
    return data


class TestAddConfidenceUnits:
    """Tests for the add_confidence_units function used in technicals_agent."""

    def test_add_confidence_units_simple_dict(self):
        """Test that add_confidence_units adds % suffix to confidence in a simple dict."""
        data = {"signal": "bullish", "confidence": 75, "reasoning": "test"}
        result = add_confidence_units(data)

        assert result["signal"] == "bullish"
        assert result["confidence"] == "75%"
        assert result["reasoning"] == "test"

    def test_add_confidence_units_nested_dict(self):
        """Test that add_confidence_units adds % suffix to confidence in nested dicts."""
        data = {
            "AAPL": {
                "signal": "bullish",
                "confidence": 80,
                "strategy_signals": {
                    "trend": {"signal": "bullish", "confidence": 75},
                    "momentum": {"signal": "neutral", "confidence": 50},
                },
            }
        }
        result = add_confidence_units(data)

        assert result["AAPL"]["confidence"] == "80%"
        assert result["AAPL"]["strategy_signals"]["trend"]["confidence"] == "75%"
        assert result["AAPL"]["strategy_signals"]["momentum"]["confidence"] == "50%"

    def test_add_confidence_units_list(self):
        """Test that add_confidence_units handles lists correctly."""
        data = [
            {"signal": "bullish", "confidence": 80},
            {"signal": "bearish", "confidence": 60},
        ]
        result = add_confidence_units(data)

        assert result[0]["confidence"] == "80%"
        assert result[1]["confidence"] == "60%"

    def test_add_confidence_units_preserves_non_confidence_keys(self):
        """Test that add_confidence_units doesn't modify non-confidence keys."""
        data = {
            "signal": "bullish",
            "confidence": 75,
            "score": 8.5,
            "reasoning": "Some reasoning",
        }
        result = add_confidence_units(data)

        assert result["signal"] == "bullish"
        assert result["confidence"] == "75%"
        assert result["score"] == 8.5
        assert result["reasoning"] == "Some reasoning"


class TestInvestorAgentSerializeFunctions:
    """Tests for investor agent serialize functions that add explicit units."""

    def test_serialize_buffett_analysis_with_explicit_units(self):
        """Test that Buffett analysis serialize function adds explicit units."""
        analysis_data = {
            "AAPL": {
                "signal": "bullish",
                "score": 8.0,
                "max_score": 10,
                "market_cap": 3000000000000,
                "margin_of_safety": 0.35,
                "intrinsic_value_analysis": {
                    "intrinsic_value": 180.0,
                    "owner_earnings": 15000000000,
                },
            }
        }

        result = serialize_buffett_analysis("AAPL", analysis_data)
        parsed = json.loads(result)

        assert parsed["ticker"] == "AAPL"
        assert parsed["signal"] == "bullish"
        assert parsed["score"] == "8.0/10"
        assert "$" in parsed["market_cap"]
        assert "%" in parsed["margin_of_safety"]
        assert "$" in parsed["intrinsic_value"]
        assert "$" in parsed["owner_earnings"]

    def test_serialize_munger_analysis_with_explicit_units(self):
        """Test that Munger analysis serialize function adds explicit units."""
        analysis_data = {
            "MSFT": {
                "signal": "bullish",
                "score": 9.0,
                "max_score": 10,
                "valuation_analysis": {
                    "fcf_yield": 0.08,
                    "normalized_fcf": 15000000000,
                    "intrinsic_value_range": {
                        "conservative": 250.0,
                        "reasonable": 300.0,
                        "optimistic": 350.0,
                    },
                },
            }
        }

        result = serialize_munger_analysis("MSFT", analysis_data)
        parsed = json.loads(result)

        assert parsed["ticker"] == "MSFT"
        assert parsed["signal"] == "bullish"
        assert "%" in parsed["fcf_yield"]
        assert "$" in parsed["normalized_fcf"]
        assert "$" in parsed["intrinsic_value_conservative"]

    def test_serialize_cathie_wood_analysis_with_explicit_units(self):
        """Test that Cathie Wood analysis serialize function adds explicit units."""
        analysis_data = {
            "TSLA": {
                "signal": "bullish",
                "score": 8.5,
                "max_score": 10,
                "valuation_analysis": {
                    "intrinsic_value": 250.0,
                    "margin_of_safety": 0.35,
                },
            }
        }

        result = serialize_cathie_wood_analysis("TSLA", analysis_data)
        parsed = json.loads(result)

        assert parsed["ticker"] == "TSLA"
        assert parsed["signal"] == "bullish"
        assert "$" in parsed["intrinsic_value"]
        assert "%" in parsed["margin_of_safety"]

    def test_serialize_ackman_analysis_with_explicit_units(self):
        """Test that Ackman analysis serialize function adds explicit units."""
        analysis_data = {
            "JPM": {
                "signal": "bullish",
                "score": 8.0,
                "max_score": 10,
                "valuation_analysis": {
                    "intrinsic_value": 180.0,
                    "margin_of_safety": 0.30,
                },
            }
        }

        result = serialize_ackman_analysis("JPM", analysis_data)
        parsed = json.loads(result)

        assert parsed["ticker"] == "JPM"
        assert parsed["signal"] == "bullish"
        assert "$" in parsed["intrinsic_value"]
        assert "%" in parsed["margin_of_safety"]

    def test_serialize_graham_analysis_with_explicit_units(self):
        """Test that Ben Graham analysis serialize function adds explicit units."""
        analysis_data = {
            "AAPL": {
                "signal": "bullish",
                "score": 10.0,
                "max_score": 15,
                "earnings_analysis": {"score": 4},
                "strength_analysis": {"score": 4},
                "valuation_analysis": {
                    "score": 6,
                    "details": "Net Current Asset Value = 500000000000, NCAV Per Share = 150.00, Price Per Share = 180.00, Graham Number = 160.00, Margin of Safety (Graham Number) = 12%",
                },
            }
        }

        result = serialize_graham_analysis("AAPL", analysis_data)
        parsed = json.loads(result)

        assert parsed["ticker"] == "AAPL"
        assert parsed["signal"] == "bullish"
        assert parsed["score"] == "10.0/15"
        assert "$" in parsed["net_current_asset_value"]
        assert "$" in parsed["ncav_per_share"]
        assert "$" in parsed["price_per_share"]
        assert "$" in parsed["graham_number"]
        assert "%" in parsed["margin_of_safety"]
