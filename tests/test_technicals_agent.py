from unittest.mock import patch

import pandas as pd
import pytest

from alpacalyzer.agents.technicals_agent import (
    calculate_mean_reversion_signals,
    calculate_momentum_signals,
    calculate_stat_arb_signals,
    calculate_trend_signals,
    calculate_volatility_signals,
    normalize_pandas,
    technical_analyst_agent,
    weighted_signal_combination,
)


@pytest.fixture
def mock_state():
    return {"data": {"tickers": ["AAPL", "MSFT"], "analyst_signals": {}}, "messages": [], "metadata": {"show_reasoning": False}}


@pytest.fixture
def mock_prices_df():
    data = {"close": [150, 152, 154, 153, 155], "high": [151, 153, 155, 154, 156], "low": [149, 151, 153, 152, 154], "volume": [1000, 1100, 1050, 1200, 1150]}
    return pd.DataFrame(data)


@patch("alpacalyzer.agents.technicals_agent.get_stock_bars")
@patch("alpacalyzer.agents.technicals_agent.progress.update_status")
def test_technical_analyst_agent(mock_update_status, mock_get_stock_bars, mock_state, mock_prices_df):
    mock_get_stock_bars.return_value = mock_prices_df

    result = technical_analyst_agent(mock_state)

    assert "messages" in result
    assert "data" in result
    assert "technical_analyst_agent" in result["data"]["analyst_signals"]
    assert len(result["data"]["analyst_signals"]["technical_analyst_agent"]) == 2  # Two tickers


def test_calculate_trend_signals(mock_prices_df):
    result = calculate_trend_signals(mock_prices_df)
    assert "signal" in result
    assert "confidence" in result
    assert "metrics" in result


def test_calculate_mean_reversion_signals(mock_prices_df):
    result = calculate_mean_reversion_signals(mock_prices_df)
    assert "signal" in result
    assert "confidence" in result
    assert "metrics" in result


def test_calculate_momentum_signals(mock_prices_df):
    result = calculate_momentum_signals(mock_prices_df)
    assert "signal" in result
    assert "confidence" in result
    assert "metrics" in result


def test_calculate_volatility_signals(mock_prices_df):
    result = calculate_volatility_signals(mock_prices_df)
    assert "signal" in result
    assert "confidence" in result
    assert "metrics" in result


def test_calculate_stat_arb_signals(mock_prices_df):
    result = calculate_stat_arb_signals(mock_prices_df)
    assert "signal" in result
    assert "confidence" in result
    assert "metrics" in result


def test_weighted_signal_combination():
    signals = {
        "trend": {"signal": "bullish", "confidence": 0.8},
        "mean_reversion": {"signal": "neutral", "confidence": 0.5},
        "momentum": {"signal": "bearish", "confidence": 0.7},
        "volatility": {"signal": "bullish", "confidence": 0.6},
        "stat_arb": {"signal": "neutral", "confidence": 0.4},
    }
    weights = {
        "trend": 0.25,
        "mean_reversion": 0.20,
        "momentum": 0.25,
        "volatility": 0.15,
        "stat_arb": 0.15,
    }
    result = weighted_signal_combination(signals, weights)
    assert "signal" in result
    assert "confidence" in result


def test_normalize_pandas():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    result = normalize_pandas(df)
    assert isinstance(result, list)
    assert result == [{"a": 1, "b": 3}, {"a": 2, "b": 4}]
