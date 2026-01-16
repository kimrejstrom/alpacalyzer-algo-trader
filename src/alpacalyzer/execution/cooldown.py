"""Cooldown manager for tracking per-ticker cooldown periods."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from alpacalyzer.events import CooldownEndedEvent, CooldownStartedEvent, emit_event


@dataclass
class CooldownEntry:
    """A cooldown record for a ticker."""

    ticker: str
    exit_time: datetime
    cooldown_hours: int
    reason: str
    strategy_name: str

    @property
    def expires_at(self) -> datetime:
        """When this cooldown expires."""
        return self.exit_time + timedelta(hours=self.cooldown_hours)

    def is_expired(self) -> bool:
        """Check if cooldown has expired."""
        return datetime.now(UTC) > self.expires_at

    def remaining_time(self) -> timedelta:
        """Time remaining in cooldown."""
        remaining = self.expires_at - datetime.now(UTC)
        return remaining if remaining > timedelta(0) else timedelta(0)


class CooldownManager:
    """
    Manages per-ticker cooldown periods.

    Features:
    - Configurable default cooldown
    - Per-ticker/per-strategy cooldowns
    - Automatic expiration
    - Query interface
    """

    def __init__(self, default_hours: int = 3):
        self._cooldowns: dict[str, CooldownEntry] = {}
        self.default_hours = default_hours

    def add_cooldown(
        self,
        ticker: str,
        reason: str,
        strategy_name: str = "unknown",
        cooldown_hours: int | None = None,
    ) -> CooldownEntry:
        """
        Add a ticker to cooldown.

        Args:
            ticker: The ticker symbol
            reason: Why the cooldown was triggered (e.g., "stop_loss_hit")
            strategy_name: Strategy that exited the position
            cooldown_hours: Override default cooldown duration
        """
        entry = CooldownEntry(
            ticker=ticker,
            exit_time=datetime.now(UTC),
            cooldown_hours=cooldown_hours or self.default_hours,
            reason=reason,
            strategy_name=strategy_name,
        )
        self._cooldowns[ticker] = entry

        emit_event(
            CooldownStartedEvent(
                timestamp=entry.exit_time,
                ticker=ticker,
                duration_hours=entry.cooldown_hours,
                reason=reason,
                strategy=strategy_name,
            )
        )

        return entry

    def is_in_cooldown(self, ticker: str) -> bool:
        """Check if a ticker is currently in cooldown."""
        if ticker not in self._cooldowns:
            return False

        entry = self._cooldowns[ticker]
        if entry.is_expired():
            del self._cooldowns[ticker]
            return False

        return True

    def get_cooldown(self, ticker: str) -> CooldownEntry | None:
        """Get the cooldown entry for a ticker."""
        if ticker not in self._cooldowns:
            return None

        entry = self._cooldowns[ticker]
        if entry.is_expired():
            del self._cooldowns[ticker]
            return None

        return entry

    def remove_cooldown(self, ticker: str) -> bool:
        """Manually remove a cooldown (e.g., for manual override)."""
        if ticker in self._cooldowns:
            del self._cooldowns[ticker]
            return True
        return False

    def get_all_active(self) -> list[CooldownEntry]:
        """Get all active cooldown entries."""
        self.cleanup_expired()
        return list(self._cooldowns.values())

    def get_all_tickers(self) -> list[str]:
        """Get all tickers currently in cooldown."""
        self.cleanup_expired()
        return list(self._cooldowns.keys())

    def cleanup_expired(self) -> int:
        """
        Remove all expired cooldowns.

        Returns number of entries removed.
        """
        expired = [ticker for ticker, entry in self._cooldowns.items() if entry.is_expired()]
        for ticker in expired:
            del self._cooldowns[ticker]
            emit_event(
                CooldownEndedEvent(
                    timestamp=datetime.now(UTC),
                    ticker=ticker,
                )
            )
        return len(expired)

    def count(self) -> int:
        """Get number of active cooldowns."""
        self.cleanup_expired()
        return len(self._cooldowns)

    def clear(self) -> None:
        """Clear all cooldowns."""
        self._cooldowns.clear()


def create_cooldown_manager_from_config(strategy_config: Any) -> CooldownManager:
    """Create a CooldownManager with settings from strategy config."""
    return CooldownManager(default_hours=getattr(strategy_config, "cooldown_hours", 3))
