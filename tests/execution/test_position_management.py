"""Position management tests."""


def test_position_sync_adds_new(mock_broker, position_tracker):
    """New broker positions added to tracker."""
    from tests.execution.mock_broker import MockPosition

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
        )
    ]

    changes = position_tracker.sync_from_broker()

    assert len(changes) == 1
    assert "AAPL" in changes
    assert position_tracker.has_position("AAPL")
    assert position_tracker.count() == 1


def test_position_sync_removes_closed(mock_broker, position_tracker):
    """Closed positions removed from tracker."""
    from tests.execution.mock_broker import MockPosition

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

    position_tracker.sync_from_broker()
    assert position_tracker.count() == 2

    mock_broker.positions = [mock_broker.positions[0]]
    changes = position_tracker.sync_from_broker()

    assert "MSFT" in changes
    assert not position_tracker.has_position("MSFT")
    assert position_tracker.count() == 1


def test_position_exit_adds_cooldown(position_tracker, cooldown_manager):
    """Exited position triggers cooldown."""
    position_tracker.add_position(
        ticker="AAPL",
        side="long",
        quantity=10,
        entry_price=150.0,
        strategy_name="test_strategy",
    )

    position_tracker.remove_position("AAPL")
    cooldown_manager.add_cooldown("AAPL", "exit_filled", "test_strategy")

    assert cooldown_manager.is_in_cooldown("AAPL")
    assert position_tracker.count() == 0
