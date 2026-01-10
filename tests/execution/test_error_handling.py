"""Error handling tests."""

from unittest.mock import MagicMock, patch

from alpaca.common.exceptions import APIError

from alpacalyzer.execution.order_manager import OrderManager, OrderParams


def test_broker_error_handled():
    """Broker API errors handled gracefully."""
    mock_client = MagicMock()
    mock_client.submit_order = MagicMock(side_effect=APIError("Rate limit exceeded"))

    with patch("alpacalyzer.execution.order_manager.trading_client", mock_client):
        manager = OrderManager(analyze_mode=False)

        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=10,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            strategy_name="test_strategy",
        )

        order = manager.submit_bracket_order(params)

    assert order is None


def test_invalid_asset_skipped():
    """Non-tradable assets skipped."""
    mock_client = MagicMock()
    mock_asset = MagicMock()
    mock_asset.tradable = False
    mock_client.get_asset = MagicMock(return_value=mock_asset)

    with patch("alpacalyzer.execution.order_manager.trading_client", mock_client):
        manager = OrderManager(analyze_mode=False)

        is_valid, reason = manager.validate_asset("INVALID", "buy")

    assert not is_valid
    assert "not tradable" in reason


def test_insufficient_buying_power():
    """Test order submission with large quantity."""
    mock_client = MagicMock()
    mock_asset = MagicMock()
    mock_asset.tradable = True
    mock_asset.shortable = True
    mock_client.get_asset = MagicMock(return_value=mock_asset)
    mock_client.submit_order = MagicMock(return_value=MagicMock())

    with patch("alpacalyzer.execution.order_manager.trading_client", mock_client):
        manager = OrderManager(analyze_mode=False)

        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=10,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            strategy_name="test_strategy",
        )

        order = manager.submit_bracket_order(params)

    assert order is not None
