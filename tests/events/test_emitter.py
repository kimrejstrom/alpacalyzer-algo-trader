"""Tests for event emitter functionality."""

from datetime import UTC, datetime
from unittest.mock import patch

from alpacalyzer.events import (
    EntryBlockedEvent,
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    OrderCanceledEvent,
    OrderFilledEvent,
    OrderRejectedEvent,
    ScanCompleteEvent,
    SignalGeneratedEvent,
    emit_event,
)


def test_emit_event_entry_triggered():
    """Test that EntryTriggeredEvent emits to both analyze and info logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = EntryTriggeredEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=10,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Test reason",
        )

        emit_event(event)

        # Verify analyze() was called with [EXECUTION] prefix
        assert mock_logger.analyze.called
        analyze_call = mock_logger.analyze.call_args[0][0]
        assert "[ENTRY]" in analyze_call
        assert "AAPL" in analyze_call
        assert "150.00" in analyze_call

        # Verify info() was called
        assert mock_logger.info.called
        info_call = mock_logger.info.call_args[0][0]
        assert "Entry triggered for AAPL" in info_call


def test_emit_event_entry_blocked():
    """Test that EntryBlockedEvent emits debug logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = EntryBlockedEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="MSFT",
            strategy="momentum",
            reason="Insufficient conditions",
            conditions_met=2,
            conditions_total=5,
        )

        emit_event(event)

        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "Entry blocked for MSFT" in debug_call
        assert "(2/5 criteria met)" in debug_call


def test_emit_event_exit_triggered():
    """Test that ExitTriggeredEvent emits to both analyze and info logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = ExitTriggeredEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="TSLA",
            strategy="momentum",
            side="short",
            quantity=50,
            entry_price=250.0,
            exit_price=200.0,
            pnl=-2500.0,
            pnl_pct=-0.10,
            hold_duration_hours=4.5,
            reason="Stop loss hit",
            urgency="normal",
        )

        emit_event(event)

        # Verify analyze() was called
        assert mock_logger.analyze.called
        analyze_call = mock_logger.analyze.call_args[0][0]
        assert "[EXIT]" in analyze_call
        assert "TSLA" in analyze_call
        assert "-10.00%" in analyze_call

        # Verify info() was called
        assert mock_logger.info.called
        info_call = mock_logger.info.call_args[0][0]
        assert "Exit triggered for TSLA" in info_call


def test_emit_event_order_filled():
    """Test that OrderFilledEvent emits correct analytics format."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = OrderFilledEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="NVDA",
            order_id="12345",
            client_order_id="client_123",
            side="buy",
            quantity=100,
            filled_qty=100,
            avg_price=500.0,
            strategy="momentum",
        )

        emit_event(event)

        assert mock_logger.analyze.called
        analyze_call = mock_logger.analyze.call_args[0][0]
        assert "[EXECUTION]" in analyze_call
        assert "NVDA" in analyze_call
        assert "Status: fill" in analyze_call

        assert mock_logger.info.called
        info_call = mock_logger.info.call_args[0][0]
        assert "Order filled: NVDA" in info_call


def test_emit_event_order_canceled():
    """Test that OrderCanceledEvent emits proper logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = OrderCanceledEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="AMD",
            order_id="67890",
            client_order_id="client_678",
            reason="User requested",
        )

        emit_event(event)

        assert mock_logger.info.called
        info_call = mock_logger.info.call_args[0][0]
        assert "Order canceled: AMD" in info_call


def test_emit_event_order_rejected():
    """Test that OrderRejectedEvent emits warning logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = OrderRejectedEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="NFLX",
            order_id=None,
            client_order_id="client_nflx",
            reason="Insufficient buying power",
        )

        emit_event(event)

        assert mock_logger.warning.called
        warning_call = mock_logger.warning.call_args[0][0]
        assert "Order rejected: NFLX" in warning_call


def test_emit_event_scan_complete():
    """Test that ScanCompleteEvent emits debug logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = ScanCompleteEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            source="social_scanner",
            tickers_found=["AAPL", "MSFT", "GOOG"],
            duration_seconds=5.2,
        )

        emit_event(event)

        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "Scan complete (social_scanner)" in debug_call
        assert "3 tickers" in debug_call


def test_emit_event_signal_generated():
    """Test that SignalGeneratedEvent emits proper logs."""
    with patch("alpacalyzer.events.emitter.logger") as mock_logger:
        event = SignalGeneratedEvent(
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            ticker="TSLA",
            action="buy",
            confidence=0.80,
            source="hedge_fund",
            strategy="momentum",
            reasoning="Strong bullish momentum",
        )

        emit_event(event)

        assert mock_logger.info.called
        info_call = mock_logger.info.call_args[0][0]
        assert "Signal generated: TSLA" in info_call
        assert "80%" in info_call

        assert mock_logger.debug.called
        debug_call = mock_logger.debug.call_args[0][0]
        assert "Reasoning: Strong bullish momentum" in debug_call
