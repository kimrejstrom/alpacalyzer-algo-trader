import json

import pytest
from pydantic import ValidationError

from alpacalyzer.sync.models import (
    AgentSignalRecord,
    DecisionContext,
    TradeDecisionRecord,
)


class TestAgentSignalRecord:
    def test_create_with_all_fields(self):
        record = AgentSignalRecord(
            agent="technical_analyst",
            signal="bullish",
            confidence=85.0,
            reasoning={"analysis": "RSI oversold, bullish divergence", "action": "buy"},
        )
        assert record.agent == "technical_analyst"
        assert record.signal == "bullish"
        assert record.confidence == 85.0

    def test_create_with_minimal_fields(self):
        record = AgentSignalRecord(agent="warren_buffett")
        assert record.agent == "warren_buffett"
        assert record.signal is None
        assert record.confidence is None
        assert record.reasoning is None

    def test_create_with_string_reasoning(self):
        record = AgentSignalRecord(
            agent="sentiment_agent",
            signal="bearish",
            reasoning="Negative news sentiment",
        )
        assert record.reasoning == "Negative news sentiment"

    def test_serialization_to_json(self):
        record = AgentSignalRecord(
            agent="momentum_strategy",
            signal="neutral",
            confidence=50.0,
            reasoning={"trend": "sideways", "recommendation": "hold"},
        )
        json_str = record.model_dump_json()
        data = json.loads(json_str)
        assert data["agent"] == "momentum_strategy"
        assert data["signal"] == "neutral"

    def test_deserialization_from_json(self):
        json_str = '{"agent": "breakout_scanner", "signal": "bullish", "confidence": 75.0}'
        record = AgentSignalRecord.model_validate_json(json_str)
        assert record.agent == "breakout_scanner"
        assert record.signal == "bullish"
        assert record.confidence == 75.0

    def test_confidence_negative_raises_error(self):
        with pytest.raises(ValidationError):
            AgentSignalRecord(agent="test", confidence=-5.0)

    def test_confidence_over_100_raises_error(self):
        with pytest.raises(ValidationError):
            AgentSignalRecord(agent="test", confidence=150.0)


class TestDecisionContext:
    def test_create_with_agent_signals(self):
        signals = [
            AgentSignalRecord(agent="technical_analyst", signal="bullish", confidence=80.0),
            AgentSignalRecord(agent="sentiment_agent", signal="neutral", confidence=60.0),
        ]
        context = DecisionContext(agent_signals=signals)
        assert len(context.agent_signals) == 2
        assert context.agent_signals[0].agent == "technical_analyst"

    def test_create_with_all_fields(self):
        context = DecisionContext(
            agent_signals=[AgentSignalRecord(agent="technical_analyst", signal="bullish", confidence=85.0)],
            portfolio_decision={"action": "buy", "quantity": 100},
            risk_assessment={"risk_level": "low", "max_loss": 500.0},
            strategy_params={"entry_criteria": ["rsi_oversold"], "risk_reward_ratio": 2.0},
            scanner_source="reddit",
            scanner_reasoning="High mention volume with positive sentiment",
            llm_costs=[
                {"agent": "technical_analyst", "cost_usd": 0.02},
                {"agent": "sentiment_agent", "cost_usd": 0.01},
            ],
        )
        assert context.scanner_source == "reddit"
        assert context.portfolio_decision == {"action": "buy", "quantity": 100}

    def test_default_values(self):
        context = DecisionContext()
        assert context.agent_signals == []
        assert context.portfolio_decision is None
        assert context.risk_assessment is None
        assert context.strategy_params is None
        assert context.scanner_source is None
        assert context.scanner_reasoning is None
        assert context.llm_costs is None

    def test_serialization_roundtrip(self):
        context = DecisionContext(
            agent_signals=[AgentSignalRecord(agent="analyst", signal="bullish", confidence=90.0)],
            scanner_source="finviz",
        )
        json_str = context.model_dump_json()
        restored = DecisionContext.model_validate_json(json_str)
        assert restored.agent_signals[0].agent == "analyst"
        assert restored.scanner_source == "finviz"


class TestTradeDecisionRecord:
    def test_create_with_all_fields(self):
        record = TradeDecisionRecord(
            ticker="AAPL",
            side="LONG",
            shares=100,
            entry_price="150.00",
            exit_price="165.00",
            target_price="170.00",
            stop_price="140.00",
            entry_date="2026-01-15T10:00:00Z",
            exit_date="2026-01-20T14:30:00Z",
            status="WIN",
            realized_pnl=1500.0,
            realized_pnl_pct=10.0,
            hold_duration_hours=124.5,
            exit_reason="target_reached",
            exit_mechanism="dynamic_exit",
            decision_context=DecisionContext(agent_signals=[AgentSignalRecord(agent="analyst", signal="bullish")]),
            strategy_name="momentum_breakout",
            setup_notes="Breakout above $150 with volume",
            tags=["momentum", "earnings"],
        )
        assert record.ticker == "AAPL"
        assert record.side == "LONG"
        assert record.status == "WIN"

    def test_create_open_position(self):
        record = TradeDecisionRecord(
            ticker="TSLA",
            side="SHORT",
            shares=50,
            entry_price="250.00",
            target_price="225.00",
            stop_price="275.00",
            entry_date="2026-02-01T09:30:00Z",
            status="OPEN",
        )
        assert record.status == "OPEN"
        assert record.exit_price is None
        assert record.realized_pnl is None

    def test_prices_are_decimal_strings(self):
        record = TradeDecisionRecord(
            ticker="MSFT",
            side="LONG",
            shares=25,
            entry_price="400.50",
            entry_date="2026-01-01T00:00:00Z",
            status="OPEN",
        )
        json_data = record.model_dump()
        assert isinstance(json_data["entry_price"], str)
        assert json_data["entry_price"] == "400.50"

    def test_dates_are_iso_8601(self):
        record = TradeDecisionRecord(
            ticker="NVDA",
            side="LONG",
            shares=10,
            entry_price="500.00",
            entry_date="2026-01-10T08:00:00Z",
            status="OPEN",
        )
        json_data = record.model_dump()
        assert isinstance(json_data["entry_date"], str)
        assert "T" in json_data["entry_date"]
        assert json_data["entry_date"].endswith("Z")

    def test_serialization_to_json(self):
        record = TradeDecisionRecord(
            ticker="GOOGL",
            side="LONG",
            shares=30,
            entry_price="140.00",
            entry_date="2026-01-05T12:00:00Z",
            status="OPEN",
            strategy_name="mean_reversion",
        )
        json_str = record.model_dump_json()
        data = json.loads(json_str)
        assert data["ticker"] == "GOOGL"
        assert data["strategy_name"] == "mean_reversion"

    def test_deserialization_from_json(self):
        json_str = """{
            "ticker": "META",
            "side": "SHORT",
            "shares": 20,
            "entry_price": "500.00",
            "entry_date": "2026-02-01T10:00:00Z",
            "status": "OPEN"
        }"""
        record = TradeDecisionRecord.model_validate_json(json_str)
        assert record.ticker == "META"
        assert record.side == "SHORT"
        assert record.status == "OPEN"

    def test_default_values(self):
        record = TradeDecisionRecord(
            ticker="AMZN",
            side="LONG",
            shares=15,
            entry_price="175.00",
            entry_date="2026-01-01T00:00:00Z",
            status="OPEN",
        )
        assert record.exit_price is None
        assert record.target_price is None
        assert record.stop_price is None
        assert record.exit_date is None
        assert record.realized_pnl is None
        assert record.realized_pnl_pct is None
        assert record.hold_duration_hours is None
        assert record.exit_reason is None
        assert record.exit_mechanism is None
        assert record.strategy_name is None
        assert record.setup_notes is None
        assert record.tags == []

    def test_decision_context_default(self):
        record = TradeDecisionRecord(
            ticker="AMD",
            side="LONG",
            shares=50,
            entry_price="120.00",
            entry_date="2026-01-01T00:00:00Z",
            status="OPEN",
        )
        assert isinstance(record.decision_context, DecisionContext)
        assert record.decision_context.agent_signals == []

    def test_invalid_side_raises_error(self):
        with pytest.raises(ValidationError):
            TradeDecisionRecord(
                ticker="TEST",
                side="INVALID",
                shares=10,
                entry_price="100.00",
                entry_date="2026-01-01T00:00:00Z",
                status="OPEN",
            )

    def test_invalid_status_raises_error(self):
        with pytest.raises(ValidationError):
            TradeDecisionRecord(
                ticker="TEST",
                side="LONG",
                shares=10,
                entry_price="100.00",
                entry_date="2026-01-01T00:00:00Z",
                status="INVALID_STATUS",
            )

    def test_tags_default_to_empty_list(self):
        record = TradeDecisionRecord(
            ticker="TEST",
            side="LONG",
            shares=10,
            entry_price="100.00",
            entry_date="2026-01-01T00:00:00Z",
            status="OPEN",
        )
        assert record.tags == []
        record.tags.append("test_tag")
        assert record.tags == ["test_tag"]

    def test_negative_shares_raises_error(self):
        with pytest.raises(ValidationError):
            TradeDecisionRecord(
                ticker="TEST",
                side="LONG",
                shares=-10,
                entry_price="100.00",
                entry_date="2026-01-01T00:00:00Z",
                status="OPEN",
            )

    def test_zero_shares_raises_error(self):
        with pytest.raises(ValidationError):
            TradeDecisionRecord(
                ticker="TEST",
                side="LONG",
                shares=0,
                entry_price="100.00",
                entry_date="2026-01-01T00:00:00Z",
                status="OPEN",
            )
