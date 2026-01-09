"""Test fixtures for execution engine integration tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpacalyzer.data.models import EntryCriteria, EntryType, TradingStrategy
from alpacalyzer.execution.cooldown import CooldownManager
from alpacalyzer.execution.position_tracker import PositionTracker, TrackedPosition
from alpacalyzer.execution.signal_queue import PendingSignal, SignalQueue
from alpacalyzer.strategies.base import EntryDecision, MarketContext
from tests.execution.mock_broker import MockAlpacaClient, MockPosition, mock_alpaca_client


@pytest.fixture
def mock_broker(monkeypatch) -> MockAlpacaClient:
    """Fixture that patches alpaca_client with mock."""
    return mock_alpaca_client(monkeypatch)


@pytest.fixture
def sample_trading_strategy():
    """Sample TradingStrategy for testing."""
    return TradingStrategy(
        ticker="AAPL",
        quantity=10,
        entry_point=150.0,
        stop_loss=145.0,
        target_price=160.0,
        risk_reward_ratio=2.0,
        strategy_notes="Strong momentum breakout",
        trade_type="long",
        entry_criteria=[
            EntryCriteria(entry_type=EntryType.BREAKOUT_ABOVE, value=148.0),
            EntryCriteria(entry_type=EntryType.RSI_OVERBOUGHT, value=70.0),
        ],
    )


@pytest.fixture
def sample_signals(sample_trading_strategy):
    """Sample trading signals for testing."""
    return [
        PendingSignal.from_strategy(sample_trading_strategy, source="agent"),
        PendingSignal(
            priority=50,
            ticker="MSFT",
            action="buy",
            confidence=80.0,
            source="technical",
            expires_at=datetime.now(UTC) + timedelta(hours=4),
        ),
        PendingSignal(
            priority=60,
            ticker="TSLA",
            action="short",
            confidence=70.0,
            source="manual",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        ),
    ]


@pytest.fixture
def sample_positions(mock_broker):
    """Sample positions for testing."""
    mock_broker.positions = [
        MockPosition(
            symbol="AAPL",
            side="long",
            qty="10",
            avg_entry_price="150.0",
            current_price="152.0",
            market_value="1520.0",
            unrealized_pl="20.0",
            unrealized_plpc="0.0133",
        ),
        MockPosition(
            symbol="MSFT",
            side="long",
            qty="5",
            avg_entry_price="300.0",
            current_price="295.0",
            market_value="1475.0",
            unrealized_pl="-25.0",
            unrealized_plpc="-0.0167",
        ),
    ]
    return mock_broker.positions


@pytest.fixture
def signal_queue():
    """SignalQueue instance for testing."""
    return SignalQueue(max_signals=50, default_ttl_hours=4)


@pytest.fixture
def position_tracker():
    """PositionTracker instance for testing."""
    return PositionTracker()


@pytest.fixture
def cooldown_manager():
    """CooldownManager instance for testing."""
    return CooldownManager(default_hours=3)


@pytest.fixture
def sample_market_context():
    """Sample market context for testing."""
    return MarketContext(
        vix=20.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=["AAPL", "MSFT"],
        cooldown_tickers=["TSLA"],
    )


@pytest.fixture
def execution_config():
    """Default ExecutionConfig for testing."""
    from alpacalyzer.execution.engine import ExecutionConfig

    return ExecutionConfig(
        check_interval_seconds=120,
        max_positions=10,
        daily_loss_limit_pct=0.05,
        analyze_mode=False,
    )


@pytest.fixture
def analyze_mode_config():
    """ExecutionConfig in analyze mode for testing."""
    from alpacalyzer.execution.engine import ExecutionConfig

    return ExecutionConfig(
        check_interval_seconds=120,
        max_positions=10,
        daily_loss_limit_pct=0.05,
        analyze_mode=True,
    )


@pytest.fixture
def mock_strategy():
    """Mock strategy for testing."""
    from alpacalyzer.strategies.base import BaseStrategy, ExitDecision

    class TestStrategy(BaseStrategy):
        def evaluate_entry(self, signal, context, agent_recommendation=None) -> EntryDecision:
            return EntryDecision(
                should_enter=True,
                reason="Test entry",
                suggested_size=10,
                entry_price=150.0,
                stop_loss=145.0,
                target=160.0,
            )

        def evaluate_exit(self, position, signal, context) -> ExitDecision:
            return ExitDecision(
                should_exit=False,
                reason="Hold position",
                urgency="normal",
            )

    return TestStrategy()


@pytest.fixture
def tracked_position():
    """Sample TrackedPosition for testing."""
    return TrackedPosition(
        ticker="AAPL",
        side="long",
        quantity=10,
        avg_entry_price=150.0,
        current_price=152.0,
        market_value=1520.0,
        unrealized_pnl=20.0,
        unrealized_pnl_pct=0.0133,
        strategy_name="test_strategy",
        opened_at=datetime.now(UTC),
        stop_loss=145.0,
        target=160.0,
    )
