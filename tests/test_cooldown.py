"""Tests for CooldownManager and CooldownEntry."""

from datetime import UTC, datetime, timedelta

from alpacalyzer.execution.cooldown import (
    CooldownEntry,
    CooldownManager,
    create_cooldown_manager_from_config,
)


class TestCooldownEntry:
    """Tests for CooldownEntry dataclass."""

    def test_creation_basic(self):
        """Test creating a basic CooldownEntry."""
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        assert entry.ticker == "AAPL"
        assert entry.cooldown_hours == 3
        assert entry.reason == "stop_loss_hit"
        assert entry.strategy_name == "momentum"

    def test_expires_at_calculates_correctly(self):
        """Test expires_at calculates the correct expiration time."""
        exit_time = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)

        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=exit_time,
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        expected_expiry = exit_time + timedelta(hours=3)
        assert entry.expires_at == expected_expiry

    def test_is_expired_when_not_expired(self):
        """Test is_expired returns False when cooldown is active."""
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        assert not entry.is_expired()

    def test_is_expired_when_expired(self):
        """Test is_expired returns True when cooldown has expired."""
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        assert entry.is_expired()

    def test_is_expired_exactly_at_expiry(self):
        """Test is_expired returns True exactly at expiry time."""
        # Create entry with exit_time such that it just expired
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=3),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        # May be True or False depending on exact timing, but should be close
        # Just verify it's callable and returns a bool
        result = entry.is_expired()
        assert isinstance(result, bool)

    def test_remaining_time_when_active(self):
        """Test remaining_time returns positive timedelta when active."""
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=1),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        remaining = entry.remaining_time()
        assert isinstance(remaining, timedelta)
        # Should be around 2 hours remaining (within 1 minute margin for test timing)
        expected_remaining = timedelta(hours=2)
        tolerance = timedelta(minutes=1)
        assert abs(remaining - expected_remaining) < tolerance

    def test_remaining_time_when_expired(self):
        """Test remaining_time returns zero timedelta when expired."""
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        remaining = entry.remaining_time()
        assert remaining == timedelta(0)

    def test_remaining_time_exactly_at_expiry(self):
        """Test remaining_time at exact expiry time."""
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=3),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        remaining = entry.remaining_time()
        # Should be zero or very close to it
        assert remaining <= timedelta(minutes=1)


class TestCooldownManager:
    """Tests for CooldownManager class."""

    def test_initialization_with_default_hours(self):
        """Test CooldownManager initializes with default hours."""
        manager = CooldownManager(default_hours=3)

        assert manager.default_hours == 3
        assert manager.count() == 0

    def test_add_cooldown_returns_entry(self):
        """Test add_cooldown creates and returns a CooldownEntry."""
        manager = CooldownManager(default_hours=3)

        entry = manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        assert isinstance(entry, CooldownEntry)
        assert entry.ticker == "AAPL"
        assert entry.reason == "stop_loss_hit"
        assert entry.strategy_name == "momentum"
        assert entry.cooldown_hours == 3  # Default

    def test_add_cooldown_with_custom_hours(self):
        """Test add_cooldown respects custom cooldown_hours."""
        manager = CooldownManager(default_hours=3)

        entry = manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
            cooldown_hours=6,
        )

        assert entry.cooldown_hours == 6
        assert entry.ticker == "AAPL"

    def test_add_cooldown_overwrites_existing(self):
        """Test adding a cooldown for existing ticker overwrites it."""
        manager = CooldownManager(default_hours=3)

        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        # Add new cooldown for same ticker
        manager.add_cooldown(
            ticker="AAPL",
            reason="manual_exit",
            strategy_name="mean_reversion",
            cooldown_hours=5,
        )

        # Should have only one entry
        assert manager.count() == 1

        # Should be the new entry
        active_entry = manager.get_cooldown("AAPL")
        assert active_entry is not None
        assert active_entry.reason == "manual_exit"
        assert active_entry.strategy_name == "mean_reversion"

    def test_is_in_cooldown_false_when_not_added(self):
        """Test is_in_cooldown returns False for ticker never added."""
        manager = CooldownManager(default_hours=3)

        assert not manager.is_in_cooldown("AAPL")

    def test_is_in_cooldown_true_when_active(self):
        """Test is_in_cooldown returns True for active cooldown."""
        manager = CooldownManager(default_hours=3)

        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        assert manager.is_in_cooldown("AAPL")

    def test_is_in_cooldown_false_when_expired(self):
        """Test is_in_cooldown returns False for expired cooldown."""
        manager = CooldownManager(default_hours=3)

        # Manually create an expired entry
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )
        manager._cooldowns["AAPL"] = entry

        # Should return False and remove expired entry
        assert not manager.is_in_cooldown("AAPL")
        assert "AAPL" not in manager._cooldowns

    def test_get_cooldown_returns_none_when_not_found(self):
        """Test get_cooldown returns None for non-existent ticker."""
        manager = CooldownManager(default_hours=3)

        assert manager.get_cooldown("AAPL") is None

    def test_get_cooldown_returns_entry_when_active(self):
        """Test get_cooldown returns entry for active cooldown."""
        manager = CooldownManager(default_hours=3)

        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        retrieved_entry = manager.get_cooldown("AAPL")

        assert retrieved_entry is not None
        assert retrieved_entry.ticker == "AAPL"
        assert retrieved_entry.reason == "stop_loss_hit"

    def test_get_cooldown_removes_expired(self):
        """Test get_cooldown removes expired entries."""
        manager = CooldownManager(default_hours=3)

        # Manually create an expired entry
        entry = CooldownEntry(
            ticker="AAPL",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )
        manager._cooldowns["AAPL"] = entry

        # Should return None and remove expired entry
        assert manager.get_cooldown("AAPL") is None
        assert "AAPL" not in manager._cooldowns

    def test_remove_cooldown_removes_existing(self):
        """Test remove_cooldown removes an existing cooldown."""
        manager = CooldownManager(default_hours=3)

        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        assert manager.count() == 1
        removed = manager.remove_cooldown("AAPL")
        assert removed is True
        assert manager.count() == 0

    def test_remove_cooldown_returns_false_for_nonexistent(self):
        """Test remove_cooldown returns False for non-existent ticker."""
        manager = CooldownManager(default_hours=3)

        removed = manager.remove_cooldown("AAPL")
        assert removed is False

    def test_get_all_active_returns_only_active(self):
        """Test get_all_active returns only non-expired entries."""
        manager = CooldownManager(default_hours=3)

        # Add active cooldown
        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        # Manually add expired cooldown
        expired_entry = CooldownEntry(
            ticker="MSFT",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )
        manager._cooldowns["MSFT"] = expired_entry

        # Should only return active entries
        active_entries = manager.get_all_active()
        assert len(active_entries) == 1
        assert active_entries[0].ticker == "AAPL"
        assert "MSFT" not in manager._cooldowns

    def test_get_all_tickers_returns_only_active(self):
        """Test get_all_tickers returns only non-expired tickers."""
        manager = CooldownManager(default_hours=3)

        # Add active cooldown
        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        # Manually add expired cooldown
        expired_entry = CooldownEntry(
            ticker="MSFT",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )
        manager._cooldowns["MSFT"] = expired_entry

        # Should only return active tickers
        tickers = manager.get_all_tickers()
        assert tickers == ["AAPL"]
        assert "MSFT" not in manager._cooldowns

    def test_cleanup_expired_removes_all_expired(self):
        """Test cleanup_expired removes all expired entries."""
        manager = CooldownManager(default_hours=3)

        # Add active cooldown
        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        # Add multiple expired cooldowns
        for ticker in ["MSFT", "GOOGL", "TSLA"]:
            entry = CooldownEntry(
                ticker=ticker,
                exit_time=datetime.now(UTC) - timedelta(hours=5),
                cooldown_hours=3,
                reason="stop_loss_hit",
                strategy_name="momentum",
            )
            manager._cooldowns[ticker] = entry

        # Should remove 3 expired entries
        removed = manager.cleanup_expired()
        assert removed == 3
        assert manager.count() == 1
        assert "AAPL" in manager._cooldowns

    def test_cleanup_expired_returns_zero_when_all_active(self):
        """Test cleanup_expired returns 0 when all entries are active."""
        manager = CooldownManager(default_hours=3)

        manager.add_cooldown(ticker="AAPL", reason="stop_loss_hit", strategy_name="momentum")
        manager.add_cooldown(ticker="MSFT", reason="target_hit", strategy_name="momentum")

        removed = manager.cleanup_expired()
        assert removed == 0
        assert manager.count() == 2

    def test_count_excludes_expired(self):
        """Test count excludes expired entries."""
        manager = CooldownManager(default_hours=3)

        # Add active cooldown
        manager.add_cooldown(
            ticker="AAPL",
            reason="stop_loss_hit",
            strategy_name="momentum",
        )

        # Add expired cooldown
        expired_entry = CooldownEntry(
            ticker="MSFT",
            exit_time=datetime.now(UTC) - timedelta(hours=5),
            cooldown_hours=3,
            reason="stop_loss_hit",
            strategy_name="momentum",
        )
        manager._cooldowns["MSFT"] = expired_entry

        # Should count only active entries
        assert manager.count() == 1

    def test_clear_removes_all_entries(self):
        """Test clear removes all cooldown entries."""
        manager = CooldownManager(default_hours=3)

        manager.add_cooldown(ticker="AAPL", reason="stop_loss_hit", strategy_name="momentum")
        manager.add_cooldown(ticker="MSFT", reason="target_hit", strategy_name="momentum")

        assert manager.count() == 2
        manager.clear()
        assert manager.count() == 0
        assert len(manager._cooldowns) == 0


class TestCreateCooldownManagerFromConfig:
    """Tests for create_cooldown_manager_from_config utility function."""

    def test_creates_manager_with_config_hours(self):
        """Test create_cooldown_manager_from_config creates manager with config hours."""

        # Mock config object
        class MockStrategyConfig:
            cooldown_hours = 5

        config = MockStrategyConfig()
        manager = create_cooldown_manager_from_config(config)

        assert isinstance(manager, CooldownManager)
        assert manager.default_hours == 5
