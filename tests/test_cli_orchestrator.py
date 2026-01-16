"""Tests for CLI integration with TradingOrchestrator."""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestCLIOrchestratorImports:
    """Test CLI imports and structure use TradingOrchestrator instead of Trader."""

    def test_cli_no_trader_import(self):
        """Test that CLI no longer imports or uses Trader."""
        from alpacalyzer import cli as cli_module

        assert not hasattr(cli_module, "Trader"), "cli.py should not import Trader"

    def test_cli_imports_trading_orchestrator(self):
        """Test that CLI imports TradingOrchestrator."""
        from alpacalyzer import cli as cli_module

        assert hasattr(cli_module, "TradingOrchestrator"), "cli.py should import TradingOrchestrator"

    def test_cli_imports_strategy_registry(self):
        """Test that CLI imports StrategyRegistry."""
        from alpacalyzer import cli as cli_module

        assert hasattr(cli_module, "StrategyRegistry"), "cli.py should import StrategyRegistry"


class TestCLIArgumentParsing:
    """Test CLI argument parsing for TradingOrchestrator."""

    def test_cli_no_new_engine_flag(self):
        """Test that --new-engine flag is removed."""
        from alpacalyzer.cli import main

        with patch.object(sys, "argv", ["alpacalyzer", "--new-engine"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 2


class TestCLIEODAndDashboard:
    """Test that EOD analyzer and dashboard still work unchanged."""

    def test_cli_eod_analyze_runs_EODPerformanceAnalyzer(self):
        """Test --eod-analyze runs EODPerformanceAnalyzer and exits."""
        mock_analyzer_instance = MagicMock()
        mock_analyzer_instance.run.return_value = "/path/to/report"

        with patch("sys.argv", ["alpacalyzer", "--eod-analyze"]):
            with patch("alpacalyzer.cli.EODPerformanceAnalyzer") as MockAnalyzer:
                MockAnalyzer.return_value = mock_analyzer_instance

                from alpacalyzer.cli import main

                main()

                MockAnalyzer.assert_called_once()
                mock_analyzer_instance.run.assert_called_once()

    def test_cli_dashboard_runs_dashboard_command(self):
        """Test --dashboard runs dashboard_command and exits."""
        with patch("sys.argv", ["alpacalyzer", "--dashboard"]):
            with patch("alpacalyzer.cli.dashboard_command") as mock_dashboard:
                from alpacalyzer.cli import main

                main()

                mock_dashboard.assert_called_once()
