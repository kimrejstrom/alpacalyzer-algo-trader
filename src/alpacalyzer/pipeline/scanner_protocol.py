from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from alpacalyzer.data.models import TopTicker
from alpacalyzer.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScanResult:
    """Result from a scanner run."""

    source: str
    tickers: list[TopTicker]
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_seconds: float = 0.0
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None

    @property
    def count(self) -> int:
        return len(self.tickers)

    def symbols(self) -> list[str]:
        """Get list of ticker symbols."""
        return [t.ticker for t in self.tickers]


@runtime_checkable
class Scanner(Protocol):
    """Protocol for all scanners."""

    @property
    def name(self) -> str:
        """Scanner identifier."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether scanner is currently enabled."""
        ...

    def scan(self) -> ScanResult:
        """Run the scanner and return results."""
        ...


class BaseScanner(ABC):
    """
    Base class for scanners with common functionality.

    Subclasses must implement:
    - _execute_scan() - the actual scanning logic
    """

    def __init__(self, name: str, enabled: bool = True, cache_ttl_seconds: int = 0):
        self._name = name
        self._enabled = enabled
        self._cache_ttl_seconds = cache_ttl_seconds
        self._last_scan: ScanResult | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def last_scan(self) -> ScanResult | None:
        return self._last_scan

    def scan(self) -> ScanResult:
        """Run the scanner with timing, error handling, and optional caching."""
        if self._cache_ttl_seconds > 0 and self._last_scan is not None and self._last_scan.success:
            age = (datetime.now(UTC) - self._last_scan.scanned_at).total_seconds()
            if age < self._cache_ttl_seconds:
                remaining = self._cache_ttl_seconds - age
                logger.debug(f"returning cached result | scanner={self.name} age={age:.0f}s ttl_remaining={remaining:.0f}s")
                return self._last_scan

        start_time = datetime.now(UTC)

        try:
            tickers = self._execute_scan()
            result = ScanResult(
                source=self.name,
                tickers=tickers,
                duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
            )
        except Exception as e:
            result = ScanResult(
                source=self.name,
                tickers=[],
                duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
                error=str(e),
            )

        self._last_scan = result
        return result

    @abstractmethod
    def _execute_scan(self) -> list[TopTicker]:
        """Execute the scan and return tickers."""
        pass
