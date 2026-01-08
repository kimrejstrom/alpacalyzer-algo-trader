"""Tests for OrderManager class."""

from unittest.mock import Mock, patch

import pytest
from alpaca.trading.enums import OrderSide
from alpaca.trading.models import Asset, Order

from alpacalyzer.execution.order_manager import OrderManager, OrderParams


class TestOrderParams:
    """Test OrderParams dataclass."""

    def test_order_params_creation(self):
        """Test creating OrderParams with all fields."""
        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )

        assert params.ticker == "AAPL"
        assert params.side == "buy"
        assert params.quantity == 100
        assert params.entry_price == 150.00
        assert params.stop_loss == 145.50
        assert params.target == 163.50
        assert params.strategy_name == "momentum"
        assert params.time_in_force == "gtc"

    def test_order_side_property_buy(self):
        """Test order_side property for buy side."""
        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )
        assert params.order_side == OrderSide.BUY

    def test_order_side_property_cover(self):
        """Test order_side property for cover side."""
        params = OrderParams(
            ticker="AAPL",
            side="cover",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )
        assert params.order_side == OrderSide.BUY

    def test_order_side_property_sell(self):
        """Test order_side property for sell side."""
        params = OrderParams(
            ticker="AAPL",
            side="sell",
            quantity=100,
            entry_price=150.00,
            stop_loss=155.50,
            target=140.50,
            strategy_name="momentum",
        )
        assert params.order_side == OrderSide.SELL

    def test_order_side_property_short(self):
        """Test order_side property for short side."""
        params = OrderParams(
            ticker="AAPL",
            side="short",
            quantity=100,
            entry_price=150.00,
            stop_loss=155.50,
            target=140.50,
            strategy_name="momentum",
        )
        assert params.order_side == OrderSide.SELL

    def test_client_order_id_generation(self):
        """Test client_order_id property generates unique IDs."""
        params1 = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )
        params2 = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )

        # IDs should be unique
        assert params1.client_order_id != params2.client_order_id

        # IDs should follow format
        assert params1.client_order_id.startswith("momentum_AAPL_buy_")
        assert len(params1.client_order_id.split("_")) == 4


class TestOrderManager:
    """Test OrderManager class."""

    @pytest.fixture
    def order_manager(self):
        """Create OrderManager instance for testing."""
        return OrderManager(analyze_mode=False)

    @pytest.fixture
    def analyze_order_manager(self):
        """Create OrderManager in analyze mode."""
        return OrderManager(analyze_mode=True)

    @pytest.fixture
    def mock_trading_client(self):
        """Mock trading client."""
        with patch("alpacalyzer.execution.order_manager.trading_client") as mock:
            yield mock

    def test_init(self, order_manager):
        """Test OrderManager initialization."""
        assert order_manager.analyze_mode is False
        assert order_manager._pending_orders == {}

    def test_init_analyze_mode(self, analyze_order_manager):
        """Test OrderManager initialization in analyze mode."""
        assert analyze_order_manager.analyze_mode is True

    def test_validate_asset_success(self, order_manager, mock_trading_client):
        """Test successful asset validation."""
        # Mock asset response
        mock_asset = Mock(spec=Asset)
        mock_asset.tradable = True
        mock_asset.shortable = True
        mock_trading_client.get_asset.return_value = mock_asset

        is_valid, reason = order_manager.validate_asset("AAPL", "buy")

        assert is_valid is True
        assert reason == "Asset validated"
        mock_trading_client.get_asset.assert_called_once_with("AAPL")

    def test_validate_asset_not_tradable(self, order_manager, mock_trading_client):
        """Test asset validation for non-tradable asset."""
        mock_asset = Mock(spec=Asset)
        mock_asset.tradable = False
        mock_trading_client.get_asset.return_value = mock_asset

        is_valid, reason = order_manager.validate_asset("AAPL", "buy")

        assert is_valid is False
        assert "not tradable" in reason

    def test_validate_asset_not_shortable(self, order_manager, mock_trading_client):
        """Test asset validation for non-shortable asset on short side."""
        mock_asset = Mock(spec=Asset)
        mock_asset.tradable = True
        mock_asset.shortable = False
        mock_trading_client.get_asset.return_value = mock_asset

        is_valid, reason = order_manager.validate_asset("AAPL", "short")

        assert is_valid is False
        assert "cannot be shorted" in reason

    def test_validate_asset_api_error(self, order_manager, mock_trading_client):
        """Test asset validation with API error."""
        mock_trading_client.get_asset.side_effect = Exception("API Error")

        is_valid, reason = order_manager.validate_asset("AAPL", "buy")

        assert is_valid is False
        assert "Failed to validate asset" in reason

    def test_submit_bracket_order_analyze_mode(self, analyze_order_manager, mock_trading_client):
        """Test bracket order submission in analyze mode."""
        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )

        result = analyze_order_manager.submit_bracket_order(params)

        assert result is None
        mock_trading_client.submit_order.assert_not_called()

    def test_submit_bracket_order_success(self, order_manager, mock_trading_client):
        """Test successful bracket order submission."""
        # Mock asset validation
        mock_asset = Mock(spec=Asset)
        mock_asset.tradable = True
        mock_asset.shortable = True
        mock_trading_client.get_asset.return_value = mock_asset

        # Mock order response
        mock_order = Mock(spec=Order)
        mock_order.id = "order123"
        mock_order.client_order_id = "momentum_AAPL_buy_12345678"
        mock_order.symbol = "AAPL"
        mock_trading_client.submit_order.return_value = mock_order

        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )

        with patch("alpacalyzer.execution.order_manager.log_order"):
            result = order_manager.submit_bracket_order(params)

        assert result == mock_order
        assert mock_order.client_order_id in order_manager._pending_orders
        mock_trading_client.submit_order.assert_called_once()

    def test_submit_bracket_order_asset_validation_failure(self, order_manager, mock_trading_client):
        """Test bracket order submission with asset validation failure."""
        # Mock asset validation failure
        mock_asset = Mock(spec=Asset)
        mock_asset.tradable = False
        mock_trading_client.get_asset.return_value = mock_asset

        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )

        result = order_manager.submit_bracket_order(params)

        assert result is None
        mock_trading_client.submit_order.assert_not_called()

    def test_submit_bracket_order_api_error(self, order_manager, mock_trading_client):
        """Test bracket order submission with API error."""
        # Mock asset validation success
        mock_asset = Mock(spec=Asset)
        mock_asset.tradable = True
        mock_asset.shortable = True
        mock_trading_client.get_asset.return_value = mock_asset

        # Mock order submission failure
        mock_trading_client.submit_order.side_effect = Exception("API Error")

        params = OrderParams(
            ticker="AAPL",
            side="buy",
            quantity=100,
            entry_price=150.00,
            stop_loss=145.50,
            target=163.50,
            strategy_name="momentum",
        )

        result = order_manager.submit_bracket_order(params)

        assert result is None

    def test_close_position_analyze_mode(self, analyze_order_manager, mock_trading_client):
        """Test position closing in analyze mode."""
        result = analyze_order_manager.close_position("AAPL")

        assert result is None
        mock_trading_client.close_position.assert_not_called()

    def test_close_position_success(self, order_manager, mock_trading_client):
        """Test successful position closing."""
        # Mock order cancellation
        mock_trading_client.get_orders.return_value = []

        # Mock position close
        mock_order = Mock(spec=Order)
        mock_order.id = "close_order123"
        mock_trading_client.close_position.return_value = mock_order

        with patch("alpacalyzer.execution.order_manager.log_order"):
            result = order_manager.close_position("AAPL", cancel_orders=True)

        assert result == mock_order
        mock_trading_client.close_position.assert_called_once_with("AAPL")

    def test_close_position_without_cancel(self, order_manager, mock_trading_client):
        """Test position closing without canceling orders."""
        # Mock position close
        mock_order = Mock(spec=Order)
        mock_order.id = "close_order123"
        mock_trading_client.close_position.return_value = mock_order

        with patch("alpacalyzer.execution.order_manager.log_order"):
            result = order_manager.close_position("AAPL", cancel_orders=False)

        assert result == mock_order
        # Should not call get_orders if cancel_orders=False
        mock_trading_client.get_orders.assert_not_called()

    def test_close_position_api_error(self, order_manager, mock_trading_client):
        """Test position closing with API error."""
        mock_trading_client.get_orders.return_value = []
        mock_trading_client.close_position.side_effect = Exception("API Error")

        result = order_manager.close_position("AAPL")

        assert result is None

    def test_cancel_orders_for_ticker_no_orders(self, order_manager, mock_trading_client):
        """Test canceling orders when no orders exist."""
        mock_trading_client.get_orders.return_value = []

        result = order_manager._cancel_orders_for_ticker("AAPL", timeout_seconds=10)

        assert result is True

    def test_cancel_orders_for_ticker_success(self, order_manager, mock_trading_client):
        """Test successful order cancellation."""
        # Mock open orders
        mock_order1 = Mock(spec=Order)
        mock_order1.id = "order1"
        mock_order2 = Mock(spec=Order)
        mock_order2.id = "order2"

        # First call returns open orders, second call returns empty (canceled)
        mock_trading_client.get_orders.side_effect = [
            [mock_order1, mock_order2],  # Initial open orders
            [],  # After cancellation
        ]

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = order_manager._cancel_orders_for_ticker("AAPL", timeout_seconds=10)

        assert result is True
        assert mock_trading_client.cancel_order_by_id.call_count == 2

    def test_cancel_orders_for_ticker_timeout(self, order_manager, mock_trading_client):
        """Test order cancellation timeout."""
        # Mock open orders that never get canceled
        mock_order = Mock(spec=Order)
        mock_order.id = "order1"
        mock_trading_client.get_orders.return_value = [mock_order]

        with patch("time.sleep"):  # Mock sleep to speed up test
            result = order_manager._cancel_orders_for_ticker("AAPL", timeout_seconds=4)

        assert result is False

    def test_cancel_orders_for_ticker_api_error(self, order_manager, mock_trading_client):
        """Test order cancellation with API error."""
        mock_trading_client.get_orders.side_effect = Exception("API Error")

        result = order_manager._cancel_orders_for_ticker("AAPL", timeout_seconds=10)

        assert result is False

    def test_get_pending_orders(self, order_manager):
        """Test getting pending orders."""
        # Add some mock orders
        mock_order1 = Mock(spec=Order)
        mock_order1.client_order_id = "order1"
        mock_order2 = Mock(spec=Order)
        mock_order2.client_order_id = "order2"

        order_manager._pending_orders["order1"] = mock_order1
        order_manager._pending_orders["order2"] = mock_order2

        pending = order_manager.get_pending_orders()

        assert len(pending) == 2
        assert mock_order1 in pending
        assert mock_order2 in pending

    def test_round_price_above_one(self, order_manager):
        """Test price rounding for prices above $1."""
        assert order_manager._round_price(150.123456) == 150.12
        assert order_manager._round_price(10.999) == 11.00

    def test_round_price_below_one(self, order_manager):
        """Test price rounding for prices below $1."""
        assert order_manager._round_price(0.123456) == 0.1235
        assert order_manager._round_price(0.99999) == 1.0000
