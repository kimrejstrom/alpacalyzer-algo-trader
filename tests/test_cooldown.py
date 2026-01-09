"""Tests for CooldownManager."""

from datetime import UTC, datetime, timedelta

from alpacalyzer.execution.cooldown import CooldownManager


class TestCooldownManager:
    def test_initial_state_empty(self):
        """Manager starts with no cooldowns."""
        manager = CooldownManager()
        assert manager.is_active("AAPL") is False
        assert manager.get_remaining_seconds("AAPL") == 0
        assert manager.count() == 0

    def test_add_cooldown(self):
        """Can add a cooldown for a ticker."""
        manager = CooldownManager()
        manager.add("AAPL", minutes=10)

        assert manager.is_active("AAPL") is True
        assert manager.count() == 1

    def test_cooldown_expires(self, monkeypatch):
        """Cooldown expires after specified time."""
        # Freeze time at 2026-01-09 12:00:00 UTC
        frozen_time = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)

        def mock_now():
            return frozen_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now)

        manager = CooldownManager()
        manager.add("AAPL", minutes=5)

        # Cooldown should be active
        assert manager.is_active("AAPL") is True
        remaining = manager.get_remaining_seconds("AAPL")
        assert remaining > 0

        # Advance time by 6 minutes (cooldown should expire)
        future_time = frozen_time + timedelta(minutes=6)

        def mock_now_future():
            return future_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now_future)

        # Cooldown should be expired
        assert manager.is_active("AAPL") is False
        assert manager.get_remaining_seconds("AAPL") == 0

    def test_multiple_tickers(self):
        """Can track multiple tickers in cooldown."""
        manager = CooldownManager()
        manager.add("AAPL", minutes=5)
        manager.add("MSFT", minutes=10)
        manager.add("TSLA", minutes=15)

        assert manager.count() == 3
        assert manager.is_active("AAPL") is True
        assert manager.is_active("MSFT") is True
        assert manager.is_active("TSLA") is True
        assert manager.is_active("GOOG") is False

    def test_remove_cooldown(self):
        """Can manually remove a cooldown."""
        manager = CooldownManager()
        manager.add("AAPL", minutes=10)

        assert manager.is_active("AAPL") is True

        manager.remove("AAPL")

        assert manager.is_active("AAPL") is False
        assert manager.count() == 0

    def test_remove_nonexistent_cooldown(self):
        """Removing nonexistent cooldown is safe."""
        manager = CooldownManager()
        manager.remove("NONEXISTENT")
        assert manager.count() == 0

    def test_clear_all(self):
        """Can clear all cooldowns."""
        manager = CooldownManager()
        manager.add("AAPL", minutes=5)
        manager.add("MSFT", minutes=10)

        assert manager.count() == 2

        manager.clear()

        assert manager.count() == 0
        assert manager.is_active("AAPL") is False
        assert manager.is_active("MSFT") is False

    def test_cleanup_expired(self, monkeypatch):
        """Expired cooldowns are cleaned up."""
        frozen_time = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)

        def mock_now():
            return frozen_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now)

        manager = CooldownManager()
        manager.add("AAPL", minutes=1)  # Expires soon
        manager.add("MSFT", minutes=10)  # Still active

        # Advance time by 2 minutes
        future_time = frozen_time + timedelta(minutes=2)

        def mock_now_future():
            return future_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now_future)

        # Cleanup should remove expired cooldowns
        manager.cleanup_expired()

        assert manager.count() == 1
        assert manager.is_active("AAPL") is False
        assert manager.is_active("MSFT") is True

    def test_get_active_tickers(self):
        """Get list of tickers with active cooldowns."""
        manager = CooldownManager()
        manager.add("AAPL", minutes=5)
        manager.add("MSFT", minutes=10)

        tickers = manager.get_active_tickers()
        assert sorted(tickers) == ["AAPL", "MSFT"]

    def test_get_remaining_seconds(self, monkeypatch):
        """Get accurate remaining time for cooldown."""
        frozen_time = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)

        def mock_now():
            return frozen_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now)

        manager = CooldownManager()
        manager.add("AAPL", minutes=10)

        remaining = manager.get_remaining_seconds("AAPL")
        assert remaining == 600  # 10 minutes in seconds

        # Advance time by 3 minutes
        future_time = frozen_time + timedelta(minutes=3)

        def mock_now_future():
            return future_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now_future)

        remaining = manager.get_remaining_seconds("AAPL")
        assert remaining == 420  # 7 minutes remaining (10 - 3)

    def test_get_remaining_seconds_nonexistent(self):
        """Nonexistent ticker returns 0."""
        manager = CooldownManager()
        remaining = manager.get_remaining_seconds("NONEXISTENT")
        assert remaining == 0

    def test_extend_existing_cooldown(self, monkeypatch):
        """Can extend an existing cooldown."""
        frozen_time = datetime(2026, 1, 9, 12, 0, 0, tzinfo=UTC)

        def mock_now():
            return frozen_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now)

        manager = CooldownManager()
        manager.add("AAPL", minutes=5)

        # Position expiration 5 minutes away
        assert manager.get_remaining_seconds("AAPL") == 300

        # Advance time by 1 minute
        future_time = frozen_time + timedelta(minutes=1)

        def mock_now_future():
            return future_time

        monkeypatch.setattr("alpacalyzer.execution.cooldown._get_current_time", mock_now_future)

        # Original cooldown has 4 minutes remaining
        assert manager.get_remaining_seconds("AAPL") == 240

        # Extend cooldown by 5 minutes from now
        manager.add("AAPL", minutes=5)

        # Now has 5 minutes remaining (new expiration from current time)
        assert manager.get_remaining_seconds("AAPL") == 300

    def test_has_cooldown(self):
        """Check if ticker has cooldown (alias for is_active)."""
        manager = CooldownManager()
        assert manager.has("AAPL") is False

        manager.add("AAPL", minutes=10)
        assert manager.has("AAPL") is True
