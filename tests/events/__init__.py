"""Tests for event models."""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from alpacalyzer.events.models import (
    CooldownEndedEvent,
    CooldownStartedEvent,
    CycleCompleteEvent,
    EntryBlockedEvent,
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    OrderCanceledEvent,
    OrderFilledEvent,
    OrderRejectedEvent,
    OrderSubmittedEvent,
    PositionClosedEvent,
    PositionOpenedEvent,
    ScanCompleteEvent,
    SignalExpiredEvent,
    SignalGeneratedEvent,
    TradingEvent,
)


def test_scan_complete_event():
    """Test ScanCompleteEvent creation and serialization."""
    event = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        source="reddit",
        tickers_found=["AAPL", "TSLA", "NVDA"],
        duration_seconds=15.5,
    )

    assert event.event_type == "SCAN_COMPLETE"
    assert event.source == "reddit"
    assert len(event.tickers_found) == 3
    assert event.duration_seconds == 15.5


def test_signal_generated_event():
    """Test SignalGeneratedEvent creation and serialization."""
    event = SignalGeneratedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        action="buy",
        confidence=0.85,
        source="hedge_fund",
        strategy="momentum",
        reasoning="Strong bullish momentum with RSI oversold bounce",
    )

    assert event.event_type == "SIGNAL_GENERATED"
    assert event.ticker == "AAPL"
    assert event.action == "buy"
    assert event.confidence == 0.85


def test_signal_expired_event():
    """Test SignalExpiredEvent creation and serialization."""
    created_at = datetime(2024, 1, 1, 10, 0, 0)
    expired_at = datetime(2024, 1, 1, 12, 0, 0)

    event = SignalExpiredEvent(
        timestamp=expired_at,
        ticker="AAPL",
        created_at=created_at,
        reason="Market moved against signal before execution",
    )

    assert event.event_type == "SIGNAL_EXPIRED"
    assert event.ticker == "AAPL"
    assert event.created_at == created_at


def test_entry_triggered_event():
    """Test EntryTriggeredEvent creation and serialization."""
    event = EntryTriggeredEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=165.0,
        reason="Golden cross confirmed with volume surge",
    )

    assert event.event_type == "ENTRY_TRIGGERED"
    assert event.ticker == "AAPL"
    assert event.side == "long"
    assert event.quantity == 100
    assert event.entry_price == 150.0
    assert event.stop_loss == 145.0
    assert event.target == 165.0


def test_entry_blocked_event():
    """Test EntryBlockedEvent creation and serialization."""
    event = EntryBlockedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        strategy="momentum",
        reason="Risk limits exceeded - insufficient buying power",
        conditions_met=2,
        conditions_total=3,
    )

    assert event.event_type == "ENTRY_BLOCKED"
    assert event.conditions_met == 2
    assert event.conditions_total == 3


def test_exit_triggered_event():
    """Test ExitTriggeredEvent creation and serialization."""
    event = ExitTriggeredEvent(
        timestamp=datetime(2024, 1, 2, 12, 0, 0),
        ticker="AAPL",
        strategy="momentum",
        side="long",
        quantity=100,
        entry_price=150.0,
        exit_price=162.0,
        pnl=1200.0,
        pnl_pct=8.0,
        hold_duration_hours=24.0,
        reason="Target price reached",
        urgency="normal",
    )

    assert event.event_type == "EXIT_TRIGGERED"
    assert event.pnl == 1200.0
    assert event.pnl_pct == 8.0
    assert event.urgency == "normal"


def test_order_submitted_event():
    """Test OrderSubmittedEvent creation and serialization."""
    event = OrderSubmittedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        order_id="12345",
        client_order_id="client_123",
        side="buy",
        quantity=100,
        order_type="limit",
        limit_price=150.0,
        strategy="momentum",
    )

    assert event.event_type == "ORDER_SUBMITTED"
    assert event.order_id == "12345"
    assert event.limit_price == 150.0
    assert event.stop_price is None


def test_order_filled_event():
    """Test OrderFilledEvent creation and serialization."""
    event = OrderFilledEvent(
        timestamp=datetime(2024, 1, 1, 12, 1, 0),
        ticker="AAPL",
        order_id="12345",
        client_order_id="client_123",
        side="buy",
        quantity=100,
        filled_qty=100,
        avg_price=150.25,
        strategy="momentum",
    )

    assert event.event_type == "ORDER_FILLED"
    assert event.filled_qty == 100
    assert event.avg_price == 150.25


def test_order_canceled_event():
    """Test OrderCanceledEvent creation and serialization."""
    event = OrderCanceledEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        order_id="12345",
        client_order_id="client_123",
        reason="User cancellation",
    )

    assert event.event_type == "ORDER_CANCELED"
    assert event.reason == "User cancellation"


def test_order_rejected_event():
    """Test OrderRejectedEvent creation and serialization."""
    event = OrderRejectedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        order_id=None,
        client_order_id="client_123",
        reason="Insufficient buying power",
    )

    assert event.event_type == "ORDER_REJECTED"
    assert event.order_id is None


def test_position_opened_event():
    """Test PositionOpenedEvent creation and serialization."""
    event = PositionOpenedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        side="long",
        quantity=100,
        entry_price=150.25,
        strategy="momentum",
        order_id="12345",
    )

    assert event.event_type == "POSITION_OPENED"
    assert event.entry_price == 150.25


def test_position_closed_event():
    """Test PositionClosedEvent creation and serialization."""
    event = PositionClosedEvent(
        timestamp=datetime(2024, 1, 2, 12, 0, 0),
        ticker="AAPL",
        side="long",
        quantity=100,
        entry_price=150.25,
        exit_price=162.50,
        pnl=1225.0,
        pnl_pct=8.15,
        hold_duration_hours=24.0,
        strategy="momentum",
        exit_reason="Target price reached",
    )

    assert event.event_type == "POSITION_CLOSED"
    assert event.exit_reason == "Target price reached"


def test_cooldown_started_event():
    """Test CooldownStartedEvent creation and serialization."""
    event = CooldownStartedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        duration_hours=24,
        reason="Stop loss triggered",
        strategy="momentum",
    )

    assert event.event_type == "COOLDOWN_STARTED"
    assert event.duration_hours == 24


def test_cooldown_ended_event():
    """Test CooldownEndedEvent creation and serialization."""
    event = CooldownEndedEvent(
        timestamp=datetime(2024, 1, 2, 12, 0, 0),
        ticker="AAPL",
    )

    assert event.event_type == "COOLDOWN_ENDED"
    assert event.ticker == "AAPL"


def test_cycle_complete_event():
    """Test CycleCompleteEvent creation and serialization."""
    event = CycleCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        entries_evaluated=5,
        entries_triggered=2,
        exits_evaluated=3,
        exits_triggered=1,
        signals_pending=1,
        positions_open=4,
        duration_seconds=5.5,
    )

    assert event.event_type == "CYCLE_COMPLETE"
    assert event.entries_triggered == 2
    assert event.exits_triggered == 1


def test_event_serialization_to_dict():
    """Test event serialization to dictionary."""
    event = ScanCompleteEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        source="reddit",
        tickers_found=["AAPL"],
        duration_seconds=10.0,
    )

    data = event.model_dump()

    assert isinstance(data, dict)
    assert data["event_type"] == "SCAN_COMPLETE"
    assert data["source"] == "reddit"
    assert "timestamp" in data


def test_event_serialization_to_json():
    """Test event serialization to JSON."""
    event = SignalGeneratedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        action="buy",
        confidence=0.85,
        source="hedge_fund",
        strategy="momentum",
    )

    json_str = event.model_dump_json()

    assert isinstance(json_str, str)

    # Parse back to verify structure
    parsed = json.loads(json_str)
    assert parsed["event_type"] == "SIGNAL_GENERATED"
    assert parsed["ticker"] == "AAPL"
    assert "timestamp" in parsed


def test_event_deserialization_from_dict():
    """Test event deserialization from dictionary."""
    data = {
        "event_type": "SCAN_COMPLETE",
        "timestamp": "2024-01-01T12:00:00",
        "source": "reddit",
        "tickers_found": ["AAPL", "TSLA"],
        "duration_seconds": 10.0,
    }

    event = ScanCompleteEvent.model_validate(data)

    assert event.event_type == "SCAN_COMPLETE"
    assert event.source == "reddit"
    assert len(event.tickers_found) == 2


def test_optional_fields():
    """Test optional fields work correctly."""
    # SignalGeneratedEvent with optional reasoning
    event1 = SignalGeneratedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        action="buy",
        confidence=0.85,
        source="hedge_fund",
        strategy="momentum",
    )

    assert event1.reasoning is None

    # With reasoning
    event2 = SignalGeneratedEvent(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        ticker="AAPL",
        action="buy",
        confidence=0.85,
        source="hedge_fund",
        strategy="momentum",
        reasoning="Strong bullish momentum",
    )

    assert event2.reasoning == "Strong bullish momentum"


def test_required_field_validation():
    """Test required fields validation."""
    with pytest.raises(ValidationError) as exc_info:
        # Missing required fields
        ScanCompleteEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            source="reddit",
            # Missing tickers_found and duration_seconds
        )

    errors = exc_info.value.errors()
    assert len(errors) == 2
    error_fields = {e["loc"][0] for e in errors}
    assert "tickers_found" in error_fields
    assert "duration_seconds" in error_fields


def test_field_type_validation():
    """Test field type validation."""
    with pytest.raises(ValidationError) as exc_info:
        # Invalid confidence value (should be float)
        SignalGeneratedEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            ticker="AAPL",
            action="buy",
            confidence="not_a_float",  # Invalid type
            source="hedge_fund",
            strategy="momentum",
        )

    errors = exc_info.value.errors()
    assert len(errors) > 0


def test_union_type():
    """Test TradingEvent union type works."""
    events: list[TradingEvent] = [
        ScanCompleteEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            source="reddit",
            tickers_found=["AAPL"],
            duration_seconds=10.0,
        ),
        SignalGeneratedEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            ticker="AAPL",
            action="buy",
            confidence=0.85,
            source="hedge_fund",
            strategy="momentum",
        ),
        EntryTriggeredEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=165.0,
            reason="Entry conditions met",
        ),
    ]

    assert len(events) == 3
    assert all(isinstance(e, TradingEvent) for e in events)


def test_datetime_iso_format():
    """Test datetime fields serialize to ISO format."""
    dt = datetime(2024, 1, 1, 12, 30, 45)
    event = ScanCompleteEvent(
        timestamp=dt,
        source="reddit",
        tickers_found=["AAPL"],
        duration_seconds=10.0,
    )

    json_str = event.model_dump_json()
    parsed = json.loads(json_str)

    assert parsed["timestamp"] == "2024-01-01T12:30:45"
