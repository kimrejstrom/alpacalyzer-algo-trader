"""Order flow tests."""

from unittest.mock import MagicMock, patch

from alpacalyzer.execution.order_manager import OrderManager, OrderParams


def test_entry_submits_bracket_order():
    """Valid entry submits bracket order."""
    mock_client = MagicMock()
    mock_asset = MagicMock()
    mock_asset.tradable = True
    mock_asset.shortable = True
    mock_client.get_asset = MagicMock(return_value=mock_asset)

    mock_order = MagicMock()
    mock_order.symbol = "AAPL"
    mock_client.submit_order = MagicMock(return_value=mock_order)

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
    assert order.symbol == "AAPL"


def test_exit_cancels_orders_first():
    """Exit cancels open orders before closing."""
    mock_client = MagicMock()
    mock_client.get_orders = MagicMock(return_value=[])
    mock_client.close_position = MagicMock(return_value=MagicMock())

    with patch("alpacalyzer.execution.order_manager.trading_client", mock_client):
        manager = OrderManager(analyze_mode=False)

        close_order = manager.close_position("AAPL")

    assert close_order is not None


def test_analyze_mode_no_orders():
    """Analyze mode doesn't submit orders."""
    manager = OrderManager(analyze_mode=True)

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
