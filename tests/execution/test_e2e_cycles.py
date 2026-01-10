"""End-to-end execution cycle tests."""

from unittest.mock import patch

import pytest

from alpacalyzer.execution.engine import ExecutionEngine


@pytest.mark.skip(reason="Mock broker doesn't fully integrate with ExecutionEngine's real trading_client paths")
def test_full_entry_cycle(mock_broker, mock_strategy, sample_signals, sample_market_context, execution_config):
    """Test complete entry from signal to order."""
    engine = ExecutionEngine(strategy=mock_strategy, config=execution_config)

    signal = sample_signals[0]
    engine.signal_queue.add(signal)

    mock_ta_signals = {"symbol": "AAPL", "price": 150.0, "rsi": 65.0}

    with patch("alpacalyzer.analysis.technical_analysis.TechnicalAnalyzer") as mock_ta:
        mock_ta.return_value.analyze_stock.return_value = mock_ta_signals

        with patch("alpacalyzer.trading.alpaca_client.get_account_info") as mock_account:
            mock_account.return_value = {
                "equity": 100000.0,
                "buying_power": 50000.0,
            }

            with patch("alpacalyzer.trading.alpaca_client.get_market_status") as mock_market:
                mock_market.return_value = "open"

                engine.run_cycle()

    assert len(mock_broker.submitted_orders) >= 1
    assert mock_broker.submitted_orders[0].symbol == "AAPL"
    assert engine.signal_queue.is_empty()


@pytest.mark.skip(reason="Mock broker doesn't fully integrate with ExecutionEngine's real trading_client paths")
def test_full_exit_cycle(mock_broker, mock_strategy, sample_positions, sample_market_context, execution_config):
    """Test complete exit from position to close."""
    from alpacalyzer.execution.position_tracker import PositionTracker

    mock_broker.positions = sample_positions
    tracker = PositionTracker()
    tracker.sync_from_broker()

    engine = ExecutionEngine(strategy=mock_strategy, config=execution_config)
    engine.positions = tracker

    mock_ta_signals = {"symbol": "AAPL", "price": 148.0, "rsi": 75.0}

    with patch("alpacalyzer.analysis.technical_analysis.TechnicalAnalyzer") as mock_ta:
        mock_ta.return_value.analyze_stock.return_value = mock_ta_signals

        with patch("alpacalyzer.trading.alpaca_client.get_account_info") as mock_account:
            mock_account.return_value = {
                "equity": 100000.0,
                "buying_power": 50000.0,
            }

            with patch("alpacalyzer.trading.alpaca_client.get_market_status") as mock_market:
                mock_market.return_value = "open"

                with patch.object(mock_strategy, "evaluate_exit") as mock_exit:
                    from alpacalyzer.strategies.base import ExitDecision

                    mock_exit.return_value = ExitDecision(
                        should_exit=True,
                        reason="Stop loss hit",
                        urgency="urgent",
                    )

                    engine.run_cycle()

    submitted_orders = [o for o in mock_broker.submitted_orders if "close" in o.id.lower()]
    assert len(submitted_orders) > 0


@pytest.mark.skip(reason="Mock broker doesn't fully integrate with ExecutionEngine's real trading_client paths")
def test_mixed_entry_exit_cycle(mock_broker, mock_strategy, sample_signals, sample_positions, execution_config):
    """Test cycle with both entries and exits."""
    from alpacalyzer.execution.position_tracker import PositionTracker

    mock_broker.positions = sample_positions
    tracker = PositionTracker()
    tracker.sync_from_broker()

    engine = ExecutionEngine(strategy=mock_strategy, config=execution_config)
    engine.positions = tracker

    for signal in sample_signals:
        engine.signal_queue.add(signal)

    mock_ta_signals = {"symbol": "TEST", "price": 150.0, "rsi": 65.0}

    with patch("alpacalyzer.analysis.technical_analysis.TechnicalAnalyzer") as mock_ta:
        mock_ta.return_value.analyze_stock.return_value = mock_ta_signals

        with patch("alpacalyzer.trading.alpaca_client.get_account_info") as mock_account:
            mock_account.return_value = {
                "equity": 100000.0,
                "buying_power": 50000.0,
            }

            with patch("alpacalyzer.trading.alpaca_client.get_market_status") as mock_market:
                mock_market.return_value = "open"

                with patch.object(mock_strategy, "evaluate_exit") as mock_exit:
                    from alpacalyzer.strategies.base import ExitDecision

                    mock_exit.return_value = ExitDecision(
                        should_exit=True,
                        reason="Stop loss hit",
                        urgency="urgent",
                    )

                    engine.run_cycle()

    assert len(mock_broker.submitted_orders) > 0
