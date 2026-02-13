from datetime import datetime

import pandas as pd
import pytest

from alpacalyzer.utils.candles_formatter import format_candles_to_markdown


@pytest.fixture
def daily_df():
    data = {
        "timestamp": [datetime(2026, 2, 10), datetime(2026, 2, 11), datetime(2026, 2, 12)],
        "open": [150.2, 151.5, 152.8],
        "high": [152.1, 153.0, 154.2],
        "low": [149.8, 150.9, 151.5],
        "close": [151.5, 152.8, 153.5],
        "volume": [1234567, 987654, 1500000],
    }
    return pd.DataFrame(data)


@pytest.fixture
def intraday_df():
    data = {
        "timestamp": [
            datetime(2026, 2, 12, 9, 30),
            datetime(2026, 2, 12, 10, 30),
            datetime(2026, 2, 12, 11, 30),
        ],
        "open": [153.5, 154.0, 154.5],
        "high": [154.2, 155.0, 155.5],
        "low": [153.0, 153.5, 154.0],
        "close": [154.0, 154.8, 155.2],
        "volume": [50000, 75000, 60000],
    }
    return pd.DataFrame(data)


class TestFormatCandlesToMarkdown:
    def test_daily_candles_formatted_correctly(self, daily_df):
        result = format_candles_to_markdown(daily_df, max_rows=3, granularity="day")

        assert "| Date | Open | High | Low | Close | Volume |" in result
        assert "| --- | --- | --- | --- | --- | --- |" in result
        assert "| 2026-02-10 | $150.20 | $152.10 | $149.80 | $151.50 | 1,234,567 |" in result
        assert "| 2026-02-11 | $151.50 | $153.00 | $150.90 | $152.80 | 987,654 |" in result
        assert "| 2026-02-12 | $152.80 | $154.20 | $151.50 | $153.50 | 1,500,000 |" in result

    def test_intraday_candles_formatted_correctly(self, intraday_df):
        result = format_candles_to_markdown(intraday_df, max_rows=3, granularity="minute")

        assert "| Date | Open | High | Low | Close | Volume |" in result
        assert "| --- | --- | --- | --- | --- | --- |" in result
        assert "| 2026-02-12 09:30:00 | $153.50 | $154.20 | $153.00 | $154.00 | 50,000 |" in result
        assert "| 2026-02-12 10:30:00 | $154.00 | $155.00 | $153.50 | $154.80 | 75,000 |" in result

    def test_max_rows_limits_output(self, daily_df):
        result = format_candles_to_markdown(daily_df, max_rows=2, granularity="day")

        lines = result.strip().split("\n")
        data_lines = [line for line in lines if line.startswith("|") and "$" in line]
        assert len(data_lines) == 2

    def test_prices_have_dollar_sign(self, daily_df):
        result = format_candles_to_markdown(daily_df, max_rows=1, granularity="day")

        assert "$152.80" in result
        assert "$154.20" in result

    def test_volumes_have_commas(self, daily_df):
        result = format_candles_to_markdown(daily_df, max_rows=1, granularity="day")

        assert "1,500,000" in result

    def test_empty_dataframe_returns_headers_only(self):
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        result = format_candles_to_markdown(df, max_rows=10, granularity="day")

        assert "| Date | Open | High | Low | Close | Volume |" in result
        assert "|------|------|------|-----|-------|--------|" in result

    def test_rounding_to_2_decimal_places(self, daily_df):
        result = format_candles_to_markdown(daily_df, max_rows=1, granularity="day")

        assert "$152.80" in result
        assert "$154.20" in result
        assert "$151.50" in result
        assert "$153.50" in result
