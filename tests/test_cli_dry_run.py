"""Tests for CLI --dry-run --json functionality."""

import json
from argparse import Namespace
from io import StringIO
from unittest.mock import MagicMock, patch

from alpacalyzer.cli import _run_dry_run
from alpacalyzer.data.models import TopTicker


def _make_args(tickers=None, strategy="momentum", json_output=False, ignore_market_status=True):
    return Namespace(
        tickers=tickers,
        strategy=strategy,
        agents="ALL",
        ignore_market_status=ignore_market_status,
        json_output=json_output,
    )


class TestRunDryRun:
    @patch("alpacalyzer.cli.TradingOrchestrator")
    @patch("alpacalyzer.cli.get_scanner_registry")
    def test_returns_structured_result_with_opportunities(self, mock_registry, mock_orch_cls):
        mock_orch = MagicMock()
        mock_orch.scan.return_value = [
            TopTicker(ticker="AAPL", confidence=80.0, signal="bullish", reasoning="test"),
            TopTicker(ticker="TSLA", confidence=70.0, signal="bullish", reasoning="test"),
        ]
        mock_orch.analyze.return_value = [MagicMock(), MagicMock()]
        mock_orch_cls.return_value = mock_orch

        args = _make_args(tickers="AAPL,TSLA", json_output=True)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            _run_dry_run(args)
            output = json.loads(mock_stdout.getvalue())

        assert output["status"] == "ok"
        assert output["mode"] == "dry_run"
        assert output["tickers_scanned"] == ["AAPL", "TSLA"]
        assert output["opportunities"] == 2
        assert output["strategies_generated"] == 2
        assert output["errors"] == []

    @patch("alpacalyzer.cli.TradingOrchestrator")
    @patch("alpacalyzer.cli.get_scanner_registry")
    def test_returns_empty_when_no_opportunities(self, mock_registry, mock_orch_cls):
        mock_orch = MagicMock()
        mock_orch.scan.return_value = []
        mock_orch_cls.return_value = mock_orch

        args = _make_args(json_output=True)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            _run_dry_run(args)
            output = json.loads(mock_stdout.getvalue())

        assert output["status"] == "ok"
        assert output["opportunities"] == 0
        assert output["strategies_generated"] == 0
        mock_orch.analyze.assert_not_called()

    @patch("alpacalyzer.cli.TradingOrchestrator")
    @patch("alpacalyzer.cli.get_scanner_registry")
    def test_captures_errors_in_result(self, mock_registry, mock_orch_cls):
        mock_orch_cls.side_effect = RuntimeError("API key missing")

        args = _make_args(json_output=True)

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            _run_dry_run(args)
            output = json.loads(mock_stdout.getvalue())

        assert output["status"] == "error"
        assert "API key missing" in output["errors"][0]

    @patch("alpacalyzer.cli.TradingOrchestrator")
    @patch("alpacalyzer.cli.get_scanner_registry")
    def test_non_json_mode_logs_instead(self, mock_registry, mock_orch_cls):
        mock_orch = MagicMock()
        mock_orch.scan.return_value = []
        mock_orch_cls.return_value = mock_orch

        args = _make_args(json_output=False)

        # Should not raise, just log
        _run_dry_run(args)
