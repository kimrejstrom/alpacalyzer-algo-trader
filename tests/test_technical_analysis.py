from datetime import datetime

import pandas as pd
import pytest

# Import after patching and reloading; disable E402 for this import line
from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer


@pytest.fixture
def analyzer():
    return TechnicalAnalyzer()


@pytest.fixture
def daily_df():
    data = {
        "timestamp": [datetime(2023, 10, 1), datetime(2023, 10, 2), datetime(2023, 10, 3)],
        "close": [100, 105, 110],
        "high": [101, 106, 111],
        "low": [99, 104, 109],
        "open": [100, 105, 110],
        "volume": [1000, 1500, 2000],
        "Volume_MA": [1000, 1200, 1500],
        "SMA_20": [95, 96, 97],
        "SMA_50": [90, 91, 92],
        "RSI": [50, 55, 60],
        "ATR": [1, 1.5, 2],
        "RVOL": [1, 1.2, 1.5],
        "ADX": [20, 25, 30],
        "Bullish_Engulfing": [0, 0, 100],
        "Bearish_Engulfing": [0, 0, -100],
        "Hammer": [0, 0, 100],
        "Shooting_Star": [0, 0, -100],
    }
    return pd.DataFrame(data)


@pytest.fixture
def intraday_df():
    data = {
        "timestamp": [datetime(2023, 10, 3, 9, 30), datetime(2023, 10, 3, 10, 30), datetime(2023, 10, 3, 11, 30)],
        "close": [108, 109, 110],
        "high": [109, 110, 111],
        "low": [107, 108, 109],
        "open": [108, 109, 110],
        "volume": [500, 600, 700],
        "vwap": [108, 109, 110],
        "MACD": [0.5, 0.6, 0.7],
        "RVOL": [1, 1.2, 1.5],
        "MACD_Signal": [0.4, 0.5, 0.6],
        "BB_Lower": [107, 108, 109],
        "BB_Upper": [109, 110, 111],
        "Bullish_Engulfing": [0, 0, 100],
        "Bearish_Engulfing": [0, 0, -100],
        "Hammer": [0, 0, 100],
        "Shooting_Star": [0, 0, -100],
    }
    return pd.DataFrame(data)


def test_calculate_technical_analysis_score(analyzer, daily_df, intraday_df):
    symbol = "AAPL"
    result = analyzer.calculate_technical_analysis_score(symbol, daily_df, intraday_df)

    assert result is not None
    assert result["symbol"] == symbol
    assert result["price"] == 110
    assert result["atr"] == 1.5
    assert result["rvol"] == 1.2
    assert isinstance(result["signals"], list)
    assert isinstance(result["raw_score"], int)
    assert 0 <= result["score"] <= 1
    assert isinstance(result["momentum"], float)


def test_calculate_technical_analysis_score_with_side(analyzer, daily_df, intraday_df):
    symbol = "AAPL"
    result = analyzer.calculate_technical_analysis_score(symbol, daily_df, intraday_df)

    assert result is not None
    assert result["symbol"] == symbol
    assert result["price"] == 110
    assert result["atr"] == 1.5
    assert result["rvol"] == 1.2
    assert isinstance(result["signals"], list)
    assert isinstance(result["raw_score"], int)
    assert 0 <= result["score"] <= 1
    assert isinstance(result["momentum"], float)


def test_calculate_technical_analysis_score_short_side(analyzer, daily_df, intraday_df):
    symbol = "AAPL"
    bearish_daily_df = daily_df.copy()
    bearish_daily_df.loc[:, "SMA_20"] = 120
    bearish_daily_df.loc[:, "SMA_50"] = 125
    bearish_daily_df.loc[:, "RSI"] = 75
    bearish_daily_df.loc[:, "Bullish_Engulfing"] = 0
    bearish_daily_df.loc[:, "Bearish_Engulfing"] = -100

    bearish_intraday_df = intraday_df.copy()
    bearish_intraday_df.loc[:, "Bullish_Engulfing"] = 0
    bearish_intraday_df.loc[:, "Bearish_Engulfing"] = -100
    bearish_intraday_df.loc[:, "vwap"] = 115

    result_long = analyzer.calculate_technical_analysis_score(symbol, daily_df, intraday_df, target_side="long")
    result_short = analyzer.calculate_technical_analysis_score(symbol, bearish_daily_df, bearish_intraday_df, target_side="short")

    assert result_long is not None
    assert result_short is not None
    assert result_short["score"] > result_long["score"]
    assert any("Price below both MAs" in s for s in result_short["signals"])
    assert any("Overbought RSI" in s for s in result_short["signals"])


def test_calculate_short_candidate_score(analyzer, daily_df, intraday_df):
    symbol = "AAPL"
    result = analyzer.calculate_short_candidate_score(symbol, daily_df, intraday_df)

    assert result is not None
    assert result["symbol"] == symbol
    assert result["price"] == 110
    assert 0 <= result["score"] <= 1
