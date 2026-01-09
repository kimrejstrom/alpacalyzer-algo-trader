"""Cooldown management for ticker trading restrictions."""

from datetime import UTC, datetime, timedelta


def _get_current_time() -> datetime:
    """Get current time (wrapper for mocking in tests)."""
    return datetime.now(UTC)


class CooldownManager:
    """
    Track cooldown periods for tickers to prevent overtrading.

    After a trade (or failed entry), a ticker is put in cooldown
    to prevent rapid-fire trading of the same symbol.

    Features:
    - Add/retrieve cooldowns
    - Check if cooldown is active
    - Get remaining time
    - Cleanup expired cooldowns
    """

    def __init__(self):
        # ticker -> expiration_time (datetime)
        self._cooldowns: dict[str, datetime] = {}

    def add(self, ticker: str, minutes: int = 5) -> None:
        """
        Add a cooldown for a ticker.

        If ticker already has a cooldown, it is extended to the new expiration time.

        Args:
            ticker: Stock ticker symbol
            minutes: Length of cooldown in minutes (default: 5)
        """
        expiration = _get_current_time() + timedelta(minutes=minutes)
        self._cooldowns[ticker] = expiration

    def is_active(self, ticker: str) -> bool:
        """
        Check if a ticker has an active cooldown.

        This does NOT automatically clean up expired cooldowns.
        Use cleanup_expired() for that.

        Args:
            ticker: Stock ticker symbol

        Returns:
            True if cooldown exists and has not expired
        """
        if ticker not in self._cooldowns:
            return False

        return _get_current_time() < self._cooldowns[ticker]

    def get_remaining_seconds(self, ticker: str) -> int:
        """
        Get remaining seconds in cooldown.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Remaining seconds (0 if no cooldown or expired)
        """
        if ticker not in self._cooldowns:
            return 0

        remaining = self._cooldowns[ticker] - _get_current_time()
        return max(0, int(remaining.total_seconds()))

    def remove(self, ticker: str) -> None:
        """
        Remove a cooldown for a ticker.

        Safe to call even if ticker doesn't have a cooldown.
        """
        self._cooldowns.pop(ticker, None)

    def clear(self) -> None:
        """Clear all cooldowns."""
        self._cooldowns.clear()

    def count(self) -> int:
        """Get number of active cooldowns (includes expired until cleanup)."""
        return len(self._cooldowns)

    def get_active_tickers(self) -> list[str]:
        """
        Get list of tickers with cooldowns.

        Note: This includes expired cooldowns until cleanup_expired() is called.
        """
        return list(self._cooldowns.keys())

    def cleanup_expired(self) -> int:
        """
        Remove expired cooldowns.

        Returns:
            Number of cooldowns removed
        """
        now = _get_current_time()
        expired = [ticker for ticker, expiration in self._cooldowns.items() if expiration <= now]

        for ticker in expired:
            del self._cooldowns[ticker]

        return len(expired)

    def has(self, ticker: str) -> bool:
        """
        Alias for is_active().

        Check if ticker has an active cooldown.
        """
        return self.is_active(ticker)
