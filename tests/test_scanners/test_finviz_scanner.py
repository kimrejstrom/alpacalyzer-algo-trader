import pandas as pd

from alpacalyzer.scanners.finviz_scanner import FinvizScanner


class TestFinvizScannerScoreStock:
    def test_score_stock_long_side_rsi_oversold(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 25,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row, target_side="long")
        assert score > 0.5
        assert score < 0.75

    def test_score_stock_long_side_rsi_overbought(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 85,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row, target_side="long")
        assert score <= 0.625

    def test_score_stock_short_side_rsi_overbought(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 85,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row, target_side="short")
        assert score > 0.5

    def test_score_stock_short_side_rsi_oversold(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 25,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row, target_side="short")
        assert score < 0.5

    def test_score_stock_long_side_sma_positive(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 50,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row, target_side="long")
        assert score > 0.5

    def test_score_stock_short_side_sma_negative(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 50,
                "sma20": -1.5,
                "sma50": -2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row, target_side="short")
        assert score > 0.5

    def test_score_stock_gap_penalty(self):
        scanner = FinvizScanner()
        row_high_gap = pd.Series(
            {
                "gap": 10,
                "rel volume": 2,
                "rsi": 50,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        row_no_gap = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 50,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score_high_gap = scanner.score_stock(row_high_gap, target_side="long")
        score_no_gap = scanner.score_stock(row_no_gap, target_side="long")
        assert score_high_gap < score_no_gap

    def test_score_stock_volume_bonus(self):
        scanner = FinvizScanner()
        row_high_vol = pd.Series(
            {
                "gap": 0,
                "rel volume": 8,
                "rsi": 50,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        row_low_vol = pd.Series(
            {
                "gap": 0,
                "rel volume": 1,
                "rsi": 50,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score_high_vol = scanner.score_stock(row_high_vol, target_side="long")
        score_low_vol = scanner.score_stock(row_low_vol, target_side="long")
        assert score_high_vol > score_low_vol


class TestFinvizScannerInitialization:
    def test_no_ta_change_u_filter(self):
        scanner = FinvizScanner()
        assert "ta_change_u" not in scanner.filters

    def test_higher_volume_filter(self):
        scanner = FinvizScanner()
        assert "sh_curvol_o100000" in scanner.filters

    def test_default_target_side(self):
        scanner = FinvizScanner()
        row = pd.Series(
            {
                "gap": 0,
                "rel volume": 2,
                "rsi": 50,
                "sma20": 1.5,
                "sma50": 2.0,
                "perf week": 5,
            }
        )
        score = scanner.score_stock(row)
        assert 0 <= score <= 1
