from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from alpacalyzer.events.emitter import EventHandler
from alpacalyzer.events.models import (
    AgentReasoningEvent,
    EntryTriggeredEvent,
    ExitTriggeredEvent,
    LLMCallEvent,
    PositionClosedEvent,
    SignalGeneratedEvent,
)
from alpacalyzer.sync.client import JournalSyncClient
from alpacalyzer.sync.handler import JournalSyncHandler
from alpacalyzer.sync.models import TradeDecisionRecord


@pytest.fixture
def mock_client():
    """Create a mock JournalSyncClient."""
    client = MagicMock(spec=JournalSyncClient)
    client.sync_trade.return_value = {"id": "trade-123", "status": "synced"}
    return client


@pytest.fixture
def handler(mock_client):
    """Create a JournalSyncHandler with mock client."""
    return JournalSyncHandler(mock_client)


class TestJournalSyncHandler:
    """Tests for JournalSyncHandler."""

    def test_inherits_event_handler(self, handler):
        """Test that handler inherits from EventHandler."""
        assert isinstance(handler, EventHandler)

    def test_agent_reasoning_event_accumulates(self, handler):
        """Test that AgentReasoningEvent updates pending context."""
        event = AgentReasoningEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            tickers=["AAPL"],
            reasoning={"signal": "bullish", "confidence": 80},
        )
        handler.handle(event)

        assert "AAPL" in handler._pending_context
        ctx = handler._pending_context["AAPL"]
        assert len(ctx.agent_signals) == 1
        assert ctx.agent_signals[0].agent == "technical_analyst"

    def test_agent_reasoning_multiple_tickers(self, handler):
        """Test that multi-ticker AgentReasoningEvent updates all tickers."""
        event = AgentReasoningEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            tickers=["AAPL", "MSFT"],
            reasoning={"signal": "bullish"},
        )
        handler.handle(event)

        assert "AAPL" in handler._pending_context
        assert "MSFT" in handler._pending_context

    def test_signal_generated_event_accumulates(self, handler):
        """Test that SignalGeneratedEvent stores strategy params."""
        event = SignalGeneratedEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            action="buy",
            confidence=0.75,
            source="hedge_fund",
            strategy="momentum",
            reasoning="Strong upward trend",
        )
        handler.handle(event)

        ctx = handler._pending_context["AAPL"]
        assert ctx.strategy_params is not None
        assert ctx.strategy_params["strategy"] == "momentum"

    def test_signal_generated_captures_scanner_source(self, handler):
        """Test that SignalGeneratedEvent captures scanner source from source field."""
        event = SignalGeneratedEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            action="buy",
            confidence=0.75,
            source="reddit",
            strategy="momentum",
        )
        handler.handle(event)

        ctx = handler._pending_context["AAPL"]
        assert ctx.scanner_source == "reddit"

    def test_llm_call_event_accumulates(self, handler):
        """Test that LLMCallEvent appends to llm_costs."""
        event = LLMCallEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            model="claude-3.5-sonnet",
            tier="standard",
            latency_ms=1500,
            prompt_tokens=500,
            completion_tokens=200,
            total_tokens=700,
            cost_usd=0.02,
        )
        handler.handle(event)

        ctx = handler._pending_context["technical_analyst"]
        assert ctx.llm_costs is not None
        assert len(ctx.llm_costs) == 1
        assert ctx.llm_costs[0]["agent"] == "technical_analyst"

    def test_entry_triggered_event_syncs_and_clears(self, handler, mock_client):
        """Test that EntryTriggeredEvent triggers sync and clears context."""
        reasoning_event = AgentReasoningEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            tickers=["AAPL"],
            reasoning={"signal": "bullish"},
        )
        handler.handle(reasoning_event)

        entry_event = EntryTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Bullish signal",
        )
        handler.handle(entry_event)

        mock_client.sync_trade.assert_called_once()
        call_args = mock_client.sync_trade.call_args[0][0]
        assert isinstance(call_args, TradeDecisionRecord)
        assert call_args.ticker == "AAPL"
        assert call_args.status == "OPEN"
        assert "AAPL" not in handler._pending_context

    def test_exit_triggered_event_syncs_with_win_status(self, handler, mock_client):
        """Test that ExitTriggeredEvent syncs with WIN status when profitable."""
        exit_event = ExitTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            exit_price=160.0,
            pnl=1000.0,
            pnl_pct=10.0,
            hold_duration_hours=24.0,
            reason="Take profit",
            urgency="normal",
        )
        handler.handle(exit_event)

        mock_client.sync_trade.assert_called_once()
        call_args = mock_client.sync_trade.call_args[0][0]
        assert call_args.status == "WIN"
        assert call_args.realized_pnl == 1000.0

    def test_exit_triggered_event_syncs_with_loss_status(self, handler, mock_client):
        """Test that ExitTriggeredEvent syncs with LOSS status when losing."""
        exit_event = ExitTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            exit_price=140.0,
            pnl=-1000.0,
            pnl_pct=-10.0,
            hold_duration_hours=24.0,
            reason="Stop loss",
            urgency="immediate",
        )
        handler.handle(exit_event)

        mock_client.sync_trade.assert_called_once()
        call_args = mock_client.sync_trade.call_args[0][0]
        assert call_args.status == "LOSS"

    def test_position_closed_event_syncs(self, handler, mock_client):
        """Test that PositionClosedEvent triggers sync."""
        position_event = PositionClosedEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            exit_price=155.0,
            pnl=500.0,
            pnl_pct=5.0,
            hold_duration_hours=12.0,
            strategy="momentum",
            exit_reason="Manual close",
        )
        handler.handle(position_event)

        mock_client.sync_trade.assert_called_once()

    def test_error_resilience_does_not_crash(self, handler, mock_client):
        """Test that handler logs warning on error but doesn't crash."""
        mock_client.sync_trade.side_effect = Exception("Network error")

        entry_event = EntryTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Test",
        )

        with patch("alpacalyzer.sync.handler.logger") as mock_logger:
            handler.handle(entry_event)
            mock_logger.warning.assert_called()

    def test_empty_context_on_entry_syncs(self, handler, mock_client):
        """Test that EntryTriggeredEvent without prior context still syncs."""
        entry_event = EntryTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Test",
        )
        handler.handle(entry_event)

        mock_client.sync_trade.assert_called_once()
        call_args = mock_client.sync_trade.call_args[0][0]
        assert isinstance(call_args, TradeDecisionRecord)
        assert call_args.ticker == "AAPL"

    def test_synced_trades_stored_for_exit(self, handler, mock_client):
        """Test that entry sync stores trade ID for exit updates."""
        mock_client.sync_trade.return_value = {"id": "journal-trade-456"}

        reasoning_event = AgentReasoningEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            tickers=["AAPL"],
            reasoning={"signal": "bullish"},
        )
        handler.handle(reasoning_event)

        entry_event = EntryTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Test",
        )
        handler.handle(entry_event)

        assert "AAPL" in handler._synced_trades
        assert handler._synced_trades["AAPL"] == "journal-trade-456"

    def test_context_cleared_after_entry(self, handler, mock_client):
        """Test that pending context is cleared after entry sync."""
        reasoning_event = AgentReasoningEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            tickers=["AAPL"],
            reasoning={"signal": "bullish"},
        )
        handler.handle(reasoning_event)

        assert "AAPL" in handler._pending_context

        entry_event = EntryTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Test",
        )
        handler.handle(entry_event)

        assert "AAPL" not in handler._pending_context

    def test_position_closed_clears_synced_trade(self, handler, mock_client):
        """Test that PositionClosedEvent clears synced trade ID."""
        mock_client.sync_trade.return_value = {"id": "journal-trade-456"}

        reasoning_event = AgentReasoningEvent(
            timestamp=datetime.now(UTC),
            agent="technical_analyst",
            tickers=["AAPL"],
            reasoning={"signal": "bullish"},
        )
        handler.handle(reasoning_event)

        entry_event = EntryTriggeredEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            strategy="momentum",
            side="long",
            quantity=100,
            entry_price=150.0,
            stop_loss=145.0,
            target=160.0,
            reason="Test",
        )
        handler.handle(entry_event)

        assert "AAPL" in handler._synced_trades

        position_event = PositionClosedEvent(
            timestamp=datetime.now(UTC),
            ticker="AAPL",
            side="long",
            quantity=100,
            entry_price=150.0,
            exit_price=155.0,
            pnl=500.0,
            pnl_pct=5.0,
            hold_duration_hours=12.0,
            strategy="momentum",
            exit_reason="Manual close",
        )
        handler.handle(position_event)

        assert "AAPL" not in handler._synced_trades
