"""Tests for CLI integration with TradingOrchestrator."""

from unittest.mock import MagicMock, patch

import pytest


class TestCLITradingOrchestrator:
    """Test CLI creates and uses TradingOrchestrator instead of Trader."""

    @pytest.fixture
    def mock_dependencies(self, monkeypatch):
        """Mock all external dependencies for CLI testing."""
        mock_logger = MagicMock()
        monkeypatch.setattr("alpacalyzer.utils.logger.get_logger", lambda: mock_logger)

        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.consume_trade_updates",
            MagicMock(),
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_close_time",
            lambda: None,
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.liquidate_all_positions",
            MagicMock(),
        )
        monkeypatch.setattr(
            "alpacalyzer.utils.scheduler.start_scheduler",
            MagicMock(),
        )
        monkeypatch.setattr(
            "schedule.every",
            MagicMock(),
        )

    def test_cli_uses_trading_orchestrator_instead_of_trader(self, monkeypatch, mock_dependencies):
        """Test that CLI creates TradingOrchestrator, not Trader."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--analyze"]):
            with patch.object(cli_module, "TradingOrchestrator") as MockOrchestrator:
                mock_instance = MagicMock()
                MockOrchestrator.return_value = mock_instance
                mock_instance.run_cycle = MagicMock()

                with patch.object(cli_module, "time"):
                    with patch.object(cli_module, "start_scheduler"):
                        with patch.object(cli_module, "schedule"):
                            cli_module.main()

                MockOrchestrator.assert_called_once()
                assert mock_instance.run_cycle.called or mock_instance.analyze.called

    def test_cli_analyze_mode_creates_orchestrator_with_analyze_true(self, monkeypatch, mock_dependencies):
        """Test --analyze flag creates orchestrator with analyze_mode=True."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--analyze"]):
            with patch.object(cli_module, "TradingOrchestrator") as MockOrchestrator:
                mock_instance = MagicMock()
                MockOrchestrator.return_value = mock_instance
                mock_instance.run_cycle = MagicMock()

                with patch.object(cli_module, "time"):
                    with patch.object(cli_module, "start_scheduler"):
                        with patch.object(cli_module, "schedule"):
                            cli_module.main()

                MockOrchestrator.assert_called_once()
                call_kwargs = MockOrchestrator.call_args[1]
                assert call_kwargs["analyze_mode"] is True

    def test_cli_tickers_creates_orchestrator_with_direct_tickers(self, monkeypatch, mock_dependencies):
        """Test --tickers flag creates orchestrator with direct_tickers list."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--tickers", "AAPL,MSFT,GOOG"]):
            with patch.object(cli_module, "TradingOrchestrator") as MockOrchestrator:
                mock_instance = MagicMock()
                MockOrchestrator.return_value = mock_instance
                mock_instance.run_cycle = MagicMock()

                with patch.object(cli_module, "time"):
                    with patch.object(cli_module, "start_scheduler"):
                        with patch.object(cli_module, "schedule"):
                            cli_module.main()

                MockOrchestrator.assert_called_once()
                call_kwargs = MockOrchestrator.call_args[1]
                assert call_kwargs["direct_tickers"] == ["AAPL", "MSFT", "GOOG"]

    def test_cli_strategy_uses_strategy_registry(self, monkeypatch, mock_dependencies):
        """Test --strategy flag creates strategy from registry."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        mock_strategy = MagicMock()

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--strategy", "momentum"]):
            with patch.object(cli_module, "StrategyRegistry") as MockRegistry:
                MockRegistry.get.return_value = mock_strategy
                with patch.object(cli_module, "TradingOrchestrator") as MockOrchestrator:
                    mock_instance = MagicMock()
                    MockOrchestrator.return_value = mock_instance
                    mock_instance.run_cycle = MagicMock()

                    with patch.object(cli_module, "time"):
                        with patch.object(cli_module, "start_scheduler"):
                            with patch.object(cli_module, "schedule"):
                                cli_module.main()

                    MockRegistry.get.assert_called_once_with("momentum")

    def test_cli_agents_passed_to_orchestrator(self, monkeypatch, mock_dependencies):
        """Test --agents flag value is passed to orchestrator."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--agents", "TRADE"]):
            with patch.object(cli_module, "TradingOrchestrator") as MockOrchestrator:
                mock_instance = MagicMock()
                MockOrchestrator.return_value = mock_instance
                mock_instance.run_cycle = MagicMock()

                with patch.object(cli_module, "time"):
                    with patch.object(cli_module, "start_scheduler"):
                        with patch.object(cli_module, "schedule"):
                            cli_module.main()

                MockOrchestrator.assert_called_once()
                call_kwargs = MockOrchestrator.call_args[1]
                assert call_kwargs["agents"] == "TRADE"

    def test_cli_ignore_market_status_passed_to_orchestrator(self, monkeypatch, mock_dependencies):
        """Test --ignore-market-status flag is passed to orchestrator."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--ignore-market-status"]):
            with patch.object(cli_module, "TradingOrchestrator") as MockOrchestrator:
                mock_instance = MagicMock()
                MockOrchestrator.return_value = mock_instance
                mock_instance.run_cycle = MagicMock()

                with patch.object(cli_module, "time"):
                    with patch.object(cli_module, "start_scheduler"):
                        with patch.object(cli_module, "schedule"):
                            cli_module.main()

                MockOrchestrator.assert_called_once()
                call_kwargs = MockOrchestrator.call_args[1]
                assert call_kwargs["ignore_market_status"] is True

    def test_cli_no_trader_import(self, monkeypatch):
        """Test that CLI no longer imports or uses Trader."""
        import alpacalyzer.cli as cli_module

        assert not hasattr(cli_module, "Trader"), "cli.py should not import Trader"

    def test_cli_no_new_engine_flag(self, monkeypatch, mock_dependencies):
        """Test that --new-engine flag is removed."""
        import importlib

        import alpacalyzer.cli as cli_module

        importlib.reload(cli_module)

        with patch.object(cli_module.sys, "argv", ["alpacalyzer", "--new-engine"]):
            with pytest.raises(SystemExit) as exc_info:
                cli_module.main()

            assert exc_info.value.code == 2


class TestCLIEODAndDashboard:
    """Test that EOD analyzer and dashboard still work unchanged."""

    @pytest.fixture
    def mock_dependencies(self, monkeypatch):
        """Mock dependencies for EOD/dashboard tests."""
        mock_logger = MagicMock()
        monkeypatch.setattr("alpacalyzer.utils.logger.get_logger", lambda: mock_logger)

    def test_cli_eod_analyze_runs_EODPerformanceAnalyzer(self, monkeypatch, mock_dependencies):
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

    def test_cli_dashboard_runs_dashboard_command(self, monkeypatch, mock_dependencies):
        """Test --dashboard runs dashboard_command and exits."""
        with patch("sys.argv", ["alpacalyzer", "--dashboard"]):
            with patch("alpacalyzer.cli.dashboard_command") as mock_dashboard:
                from alpacalyzer.cli import main

                main()

                mock_dashboard.assert_called_once()


class TestCLIScheduling:
    """Test CLI scheduling with TradingOrchestrator."""

    @pytest.fixture
    def mock_dependencies(self, monkeypatch):
        """Mock all external dependencies for scheduling tests."""
        mock_logger = MagicMock()
        monkeypatch.setattr("alpacalyzer.utils.logger.get_logger", lambda: mock_logger)

        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.consume_trade_updates",
            MagicMock(),
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.get_market_close_time",
            lambda: None,
        )
        monkeypatch.setattr(
            "alpacalyzer.trading.alpaca_client.liquidate_all_positions",
            MagicMock(),
        )
        monkeypatch.setattr(
            "alpacalyzer.utils.scheduler.start_scheduler",
            MagicMock(),
        )

    def test_cli_stream_enables_websocket(self, monkeypatch, mock_dependencies):
        """Test --stream flag enables websocket streaming."""
        from alpacalyzer.trading.alpaca_client import consume_trade_updates

        with patch("sys.argv", ["alpacalyzer", "--stream"]):
            with patch("alpacalyzer.cli.TradingOrchestrator") as MockOrchestrator:
                mock_instance = MagicMock()
                MockOrchestrator.return_value = mock_instance
                mock_instance.run_cycle = MagicMock()

                with patch("threading.Thread") as MockThread:
                    from alpacalyzer.cli import main

                    main()

                    MockThread.assert_called_once()
                    args = MockThread.call_args[1]
                    assert args["target"] == consume_trade_updates
                    assert args["daemon"] is True
