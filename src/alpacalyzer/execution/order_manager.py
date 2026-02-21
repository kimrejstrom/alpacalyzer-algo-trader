"""Order management for trade execution."""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.models import Asset, Order
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest

from alpacalyzer.events import OrderSubmittedEvent, PositionClosedEvent, emit_event
from alpacalyzer.trading.alpaca_client import log_order, trading_client
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OrderParams:
    """Parameters for order creation."""

    ticker: str
    side: str  # "buy", "sell", "short", "cover"
    quantity: int
    entry_price: float
    stop_loss: float
    target: float
    strategy_name: str
    time_in_force: str = "gtc"
    _client_order_id: str | None = None  # Cached client order ID

    @property
    def order_side(self) -> OrderSide:
        """Get Alpaca OrderSide enum."""
        if self.side in ("buy", "cover"):
            return OrderSide.BUY
        return OrderSide.SELL

    @property
    def client_order_id(self) -> str:
        """Generate unique client order ID (cached on first access)."""
        if self._client_order_id is None:
            object.__setattr__(
                self,
                "_client_order_id",
                f"{self.strategy_name}_{self.ticker}_{self.side}_{uuid.uuid4().hex[:8]}",
            )
        return self._client_order_id  # type: ignore[return-value]


class OrderManager:
    """
    Manages order submission and lifecycle.

    Features:
    - Bracket order creation
    - Order cancellation with confirmation
    - Position closing
    - Asset validation
    """

    def __init__(self, analyze_mode: bool = False):
        self.analyze_mode = analyze_mode
        self._pending_orders: dict[str, Order] = {}  # client_order_id -> Order

    def validate_asset(self, ticker: str, side: str) -> tuple[bool, str]:
        """
        Validate that the asset can be traded.

        Returns (is_valid, reason).
        """
        try:
            asset_response = trading_client.get_asset(ticker)
            asset = cast(Asset, asset_response)

            if not asset.tradable:
                return False, f"{ticker} is not tradable"

            # Only "short" requires shortability - "sell" is selling an existing long position
            if side == "short" and not asset.shortable:
                return False, f"{ticker} cannot be shorted"

            return True, "Asset validated"

        except Exception as e:
            return False, f"Failed to validate asset: {str(e)}"

    def submit_bracket_order(self, params: OrderParams) -> Order | None:
        """
        Submit a bracket order with entry, stop loss, and take profit.

        Bracket Order Exit Mechanism (Issue #73):
        -----------------------------------------
        This creates the PRIMARY exit mechanism for the position.
        The bracket order includes:
        - Entry: Limit order at params.entry_price
        - Stop Loss: Stop order at params.stop_loss (OCO leg)
        - Take Profit: Limit order at params.target (OCO leg)

        The stop_loss and take_profit legs are One-Cancels-Other (OCO),
        meaning when one triggers, the other is automatically canceled.

        Precedence: Bracket orders take precedence over dynamic exits.
        When a position has an active bracket order, the ExecutionEngine
        will skip strategy.evaluate_exit() calls for that position.

        Returns the Order object if successful, None otherwise.
        """
        if self.analyze_mode:
            logger.info(f"analyze mode, skipping bracket order | ticker={params.ticker} side={params.side} qty={params.quantity}")
            return None

        # Validate asset first
        is_valid, reason = self.validate_asset(params.ticker, params.side)
        if not is_valid:
            logger.warning(f"order rejected | ticker={params.ticker} reason={reason}")
            return None

        # Round prices appropriately
        entry = self._round_price(params.entry_price)
        stop = self._round_price(params.stop_loss)
        target = self._round_price(params.target)

        try:
            bracket_order = LimitOrderRequest(
                symbol=params.ticker,
                qty=params.quantity,
                side=params.order_side,
                type="limit",
                time_in_force=TimeInForce.GTC,
                limit_price=entry,
                order_class="bracket",
                stop_loss={"stop_price": stop},
                take_profit={"limit_price": target},
                client_order_id=params.client_order_id,
            )

            logger.debug(f"Submitting bracket order: {bracket_order}")
            order_response = trading_client.submit_order(bracket_order)
            order = cast(Order, order_response)

            log_order(order)
            self._pending_orders[order.client_order_id] = order

            try:
                emit_event(
                    OrderSubmittedEvent(
                        timestamp=datetime.now(UTC),
                        ticker=str(order.symbol) if order.symbol else params.ticker,
                        order_id=str(order.id),
                        client_order_id=str(order.client_order_id),
                        side=params.side,
                        quantity=int(order.qty) if order.qty else 0,
                        order_type="limit",
                        limit_price=float(order.limit_price) if order.limit_price else None,
                        stop_price=float(order.stop_price) if order.stop_price else None,
                        strategy=params.strategy_name,
                    )
                )
            except Exception:
                pass  # Event emission should not block order return

            return order

        except Exception as e:
            logger.error(f"order submission failed | ticker={params.ticker} error={e}", exc_info=True)
            return None

    def close_position(
        self,
        ticker: str,
        cancel_orders: bool = True,
        timeout_seconds: int = 30,
    ) -> Order | None:
        """
        Close a position, optionally canceling open orders first.

        Dynamic Exit Mechanism (Issue #73):
        -----------------------------------
        This method is used by the SECONDARY exit mechanism (dynamic exits).
        It is called by ExecutionEngine._execute_exit() when:
        - Position has no active bracket order (has_bracket_order=False)
        - Strategy.evaluate_exit() returned should_exit=True

        The method will:
        1. Cancel any remaining open orders for the ticker (if cancel_orders=True)
        2. Wait for cancellation confirmation (up to timeout_seconds)
        3. Submit a market order to close the position

        Note: If the position still has bracket order legs active, they will
        be canceled before closing to prevent conflicts.

        Returns the close order if successful.
        """
        if self.analyze_mode:
            logger.info(f"analyze mode, skipping close | ticker={ticker}")
            return None

        try:
            if cancel_orders:
                self._cancel_orders_for_ticker(ticker, timeout_seconds)

            logger.info(f"closing position | ticker={ticker}")
            order_response = trading_client.close_position(ticker)
            order = cast(Order, order_response)

            log_order(order)

            exit_price = float(order.filled_avg_price) if order.filled_avg_price else 0.0

            try:
                emit_event(
                    PositionClosedEvent(
                        timestamp=datetime.now(UTC),
                        ticker=ticker,
                        side="long",
                        quantity=int(order.filled_qty) if order.filled_qty else 0,
                        entry_price=0.0,
                        exit_price=exit_price,
                        pnl=0.0,
                        pnl_pct=0.0,
                        hold_duration_hours=0.0,
                        strategy="order_manager",
                        exit_reason="manual_close",
                    )
                )
            except Exception:
                pass  # Event emission should not block order return

            return order

        except Exception as e:
            logger.error(f"close position failed | ticker={ticker} error={e}", exc_info=True)
            return None

    def _cancel_orders_for_ticker(self, ticker: str, timeout_seconds: int) -> bool:
        """
        Cancel all open orders for a ticker and wait for confirmation.

        Returns True if all orders canceled successfully.
        """
        try:
            # Get open orders for ticker
            orders_response = trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[ticker]))
            open_orders = cast(list[Order], orders_response)

            if not open_orders:
                return True

            logger.info(f"canceling open orders | ticker={ticker} count={len(open_orders)}")

            # Request cancellation for each order
            for order in open_orders:
                try:
                    trading_client.cancel_order_by_id(order.id)
                    logger.debug(f"Requested cancellation for order {order.id}")
                except APIError as e:
                    if e.code == 42210000:  # PENDING_CANCEL
                        logger.debug(f"Order {order.id} already pending cancel")
                    elif e.code == 40410000:  # ORDER_NOT_FOUND
                        logger.debug(f"Order {order.id} not found")
                    else:
                        raise

            # Poll for confirmation
            poll_interval = 2
            max_polls = timeout_seconds // poll_interval

            for _ in range(max_polls):
                time.sleep(poll_interval)

                remaining = trading_client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[ticker]))

                if not cast(list[Order], remaining):
                    logger.debug(f"all orders canceled | ticker={ticker}")
                    return True

                logger.debug(f"waiting for order cancellation | ticker={ticker}")

            logger.error(f"order cancellation timed out | ticker={ticker}")
            return False

        except Exception as e:
            logger.error(f"cancel orders failed | ticker={ticker} error={e}", exc_info=True)
            return False

    def get_pending_orders(self) -> list[Order]:
        """Get list of pending orders we submitted."""
        return list(self._pending_orders.values())

    def remove_pending_order(self, client_order_id: str) -> bool:
        """
        Remove an order from pending orders tracking.

        Returns True if order was found and removed.
        """
        if client_order_id in self._pending_orders:
            del self._pending_orders[client_order_id]
            return True
        return False

    def clear_pending_orders(self) -> None:
        """Clear all pending orders from tracking."""
        self._pending_orders.clear()

    def _round_price(self, price: float) -> float:
        """Round price appropriately based on magnitude."""
        if price > 1:
            return round(price, 2)
        return round(price, 4)

    def to_dict(self) -> dict[str, Any]:
        """Serialize orders to dictionary."""
        pending_orders = []
        for client_order_id, order in self._pending_orders.items():
            order_data = {
                "client_order_id": client_order_id,
                "order_id": str(order.id),
                "symbol": order.symbol,
                "side": str(order.side) if order.side else None,
                "qty": order.qty,
                "filled_qty": order.filled_qty,
                "status": str(order.status) if order.status else None,
            }
            pending_orders.append(order_data)

        return {
            "analyze_mode": self.analyze_mode,
            "pending_orders": pending_orders,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OrderManager":
        """Deserialize orders from dictionary."""
        manager = cls(analyze_mode=data.get("analyze_mode", False))

        for order_data in data.get("pending_orders", []):
            from alpaca.trading.models import Order

            order_id = order_data.get("order_id", "")
            client_order_id = order_data.get("client_order_id", "")

            fake_order = Order(
                id=order_id,
                client_order_id=client_order_id,
                symbol=order_data.get("symbol"),
                side=order_data.get("side"),
                qty=order_data.get("qty"),
                filled_qty=order_data.get("filled_qty"),
                status=order_data.get("status"),
            )
            manager._pending_orders[client_order_id] = fake_order

        return manager
