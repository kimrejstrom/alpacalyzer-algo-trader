"""Tests for strategy dataclasses."""

from alpacalyzer.strategies.base import EntryDecision, ExitDecision, MarketContext


def test_entry_decision_defaults():
    """Test EntryDecision has correct default values."""
    decision = EntryDecision(should_enter=False, reason="Test")

    assert decision.should_enter is False
    assert decision.reason == "Test"
    assert decision.suggested_size == 0
    assert decision.entry_price == 0.0
    assert decision.stop_loss == 0.0
    assert decision.target == 0.0


def test_entry_decision_with_values():
    """Test EntryDecision accepts custom values."""
    decision = EntryDecision(
        should_enter=True,
        reason="Bullish signal",
        suggested_size=100,
        entry_price=150.0,
        stop_loss=145.0,
        target=160.0,
    )

    assert decision.should_enter is True
    assert decision.reason == "Bullish signal"
    assert decision.suggested_size == 100
    assert decision.entry_price == 150.0
    assert decision.stop_loss == 145.0
    assert decision.target == 160.0


def test_exit_decision_defaults():
    """Test ExitDecision has correct default values."""

    decision = ExitDecision(should_exit=False, reason="Test")

    assert decision.should_exit is False
    assert decision.reason == "Test"
    assert decision.urgency == "normal"


def test_exit_decision_with_values():
    """Test ExitDecision accepts custom values."""

    decision = ExitDecision(should_exit=True, reason="Stop loss hit", urgency="urgent")

    assert decision.should_exit is True
    assert decision.reason == "Stop loss hit"
    assert decision.urgency == "urgent"


def test_exit_decision_urgency_levels():
    """Test ExitDecision accepts all urgency levels."""

    # Normal
    decision = ExitDecision(should_exit=False, reason="Hold", urgency="normal")
    assert decision.urgency == "normal"

    # Urgent
    decision = ExitDecision(should_exit=True, reason="Exit now", urgency="urgent")
    assert decision.urgency == "urgent"

    # Immediate
    decision = ExitDecision(should_exit=True, reason="Emergency", urgency="immediate")
    assert decision.urgency == "immediate"


def test_market_context_defaults():
    """Test MarketContext can be created with basic values."""
    context = MarketContext(
        vix=15.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=[],
        cooldown_tickers=[],
    )

    assert context.vix == 15.0
    assert context.market_status == "open"
    assert context.account_equity == 100000.0
    assert context.buying_power == 50000.0
    assert context.existing_positions == []
    assert context.cooldown_tickers == []


def test_market_context_with_positions_and_cooldowns():
    """Test MarketContext accepts positions and cooldowns."""
    context = MarketContext(
        vix=20.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=["AAPL", "MSFT"],
        cooldown_tickers=["GOOG", "AMZN"],
    )

    assert context.vix == 20.0
    assert len(context.existing_positions) == 2
    assert "AAPL" in context.existing_positions
    assert "MSFT" in context.existing_positions
    assert len(context.cooldown_tickers) == 2
    assert "GOOG" in context.cooldown_tickers
    assert "AMZN" in context.cooldown_tickers


def test_market_context_mutation():
    """Test MarketContext is mutable (lists can be modified)."""
    context = MarketContext(
        vix=15.0,
        market_status="open",
        account_equity=100000.0,
        buying_power=50000.0,
        existing_positions=[],
        cooldown_tickers=[],
    )

    # Should be able to add to lists
    context.existing_positions.append("AAPL")
    context.cooldown_tickers.append("MSFT")

    assert "AAPL" in context.existing_positions
    assert "MSFT" in context.cooldown_tickers
