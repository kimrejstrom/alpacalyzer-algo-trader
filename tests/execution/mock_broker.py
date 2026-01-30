"""Mock Alpaca client for testing execution components."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from alpaca.trading.models import Asset
from alpaca.trading.requests import GetCalendarRequest, GetOrdersRequest


class MockClock:
    def __init__(self):
        self.is_open = True
        self.timestamp = datetime(2024, 1, 1, 14, 30, tzinfo=UTC)
        self.next_open = datetime(2024, 1, 2, 9, 30, tzinfo=UTC)


class MockCalendarEntry:
    def __init__(self):
        self.date = date.today()
        self.open = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
        self.close = datetime(2024, 1, 1, 16, 0, tzinfo=UTC)


@dataclass
class MockPosition:
    """Mock position for testing."""

    symbol: str
    side: str
    qty: str
    avg_entry_price: str
    current_price: str | None = None
    market_value: str | None = None
    unrealized_pl: str | None = None
    unrealized_plpc: str | None = None


@dataclass
class MockOrder:
    """Mock order for testing."""

    id: str
    client_order_id: str
    symbol: str
    side: str
    qty: str = "0"
    type: str = "limit"
    order_type: str = "limit"
    limit_price: float | None = None
    stop_price: float | None = None
    order_class: str | None = None
    status: str = "filled"
    created_at: str | None = None
    updated_at: str | None = None
    filled_qty: str = "0"
    time_in_force: str = "gtc"


class MockAlpacaClient:
    """Mock Alpaca client for testing execution components."""

    def __init__(self):
        self.positions: list[MockPosition] = []
        self.orders: list[MockOrder] = []
        self.submitted_orders: list[MockOrder] = []
        self.assets: dict[str, dict[str, Any]] = {}
        self.buying_power: float = 100000.0
        self.equity: float = 100000.0
        self.market_status: str = "open"

    def get_clock(self) -> MockClock:
        """Get market clock."""
        return MockClock()

    def get_calendar(self, request: GetCalendarRequest) -> list[MockCalendarEntry]:
        """Get calendar."""
        return [MockCalendarEntry()]

    def get_all_positions(self) -> list[MockPosition]:
        """Get all positions."""
        return list(self.positions)

    def submit_order(self, request: Any) -> MockOrder:
        """Submit an order."""
        order = MockOrder(
            id=f"order_{len(self.submitted_orders)}",
            client_order_id=getattr(request, "client_order_id", ""),
            symbol=request.symbol,
            side=str(request.side),
            qty=str(request.qty),
            type=str(getattr(request, "type", "limit")),
            limit_price=getattr(request, "limit_price", None),
            stop_price=getattr(request, "stop_price", None),
            order_class=getattr(request, "order_class", None),
        )
        self.submitted_orders.append(order)
        self.orders.append(order)
        return order

    def close_position(self, ticker: str) -> MockOrder:
        """Close a position."""
        self.positions = [p for p in self.positions if p.symbol != ticker]
        order = MockOrder(
            id=f"close_{ticker}_{time.time()}",
            client_order_id=f"close_{ticker}",
            symbol=ticker,
            qty="0",
            side="sell",
            type="market",
        )
        self.submitted_orders.append(order)
        self.orders.append(order)
        return order

    def get_asset(self, ticker: str) -> Asset:
        """Get asset info."""
        if ticker not in self.assets:
            self.assets[ticker] = {
                "id": str(uuid.uuid4()),
                "class": "us_equity",
                "exchange": "NASDAQ",
                "symbol": ticker,
                "name": f"{ticker} Inc",
                "status": "active",
                "tradable": True,
                "marginable": True,
                "shortable": True,
                "easy_to_borrow": True,
                "fractionable": True,
            }
        from typing import cast

        return cast(Asset, type("MockAsset", (), self.assets[ticker])())

    def get_orders(self, request: GetOrdersRequest) -> list[MockOrder]:
        """Get orders."""
        return self.orders

    def cancel_order_by_id(self, order_id: str) -> None:
        """Cancel an order by ID."""
        self.orders = [o for o in self.orders if o.id != order_id]

    def get_account(self) -> Any:
        """Get account information."""
        return type(
            "MockAccount",
            (),
            {
                "equity": str(self.equity),
                "buying_power": str(self.buying_power),
                "initial_margin": "0",
                "multiplier": "1",
                "daytrading_buying_power": str(self.buying_power),
                "maintenance_margin": "0",
            },
        )()


def create_mock_broker() -> MockAlpacaClient:
    """Create a mock broker with default configuration."""
    return MockAlpacaClient()


def mock_alpaca_client(monkeypatch) -> MockAlpacaClient:
    """
    Fixture that patches alpaca_client with mock.

    Usage in pytest:
        def test_something(mock_alpaca_client):
            mock_broker = mock_alpaca_client
            # Use mock_broker in your test
    """
    mock = create_mock_broker()
    monkeypatch.setattr("alpacalyzer.trading.alpaca_client.trading_client", mock)
    monkeypatch.setattr("alpacalyzer.trading.alpaca_client.get_market_status", lambda: "open")
    return mock
