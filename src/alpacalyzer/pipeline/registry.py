"""ScannerRegistry for managing scanner instances."""

from __future__ import annotations

from collections.abc import Iterator

from alpacalyzer.pipeline.scanner_protocol import BaseScanner, ScanResult
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


class ScannerRegistry:
    """
    Registry for managing scanners.

    Usage:
        registry = ScannerRegistry()
        registry.register(RedditScanner())
        registry.register(FinvizScanner())

        for result in registry.run_all():
            print(f"{result.source}: {result.count} tickers")
    """

    _instance: ScannerRegistry | None = None

    def __init__(self):
        self._scanners: dict[str, BaseScanner] = {}

    @classmethod
    def get_instance(cls) -> ScannerRegistry:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (primarily for testing)."""
        cls._instance = None

    def register(self, scanner: BaseScanner) -> None:
        """Register a scanner."""
        if scanner.name in self._scanners:
            logger.warning(f"Overwriting scanner: {scanner.name}")
        self._scanners[scanner.name] = scanner

    def unregister(self, name: str) -> None:
        """Unregister a scanner."""
        self._scanners.pop(name, None)

    def get(self, name: str) -> BaseScanner | None:
        """Get a scanner by name."""
        return self._scanners.get(name)

    def list(self) -> list[str]:
        """List all registered scanner names."""
        return list(self._scanners.keys())

    def list_enabled(self) -> list[str]:
        """List enabled scanner names."""
        return [name for name, scanner in self._scanners.items() if scanner.enabled]

    def enable(self, name: str) -> None:
        """Enable a scanner."""
        if scanner := self._scanners.get(name):
            scanner.enabled = True

    def disable(self, name: str) -> None:
        """Disable a scanner."""
        if scanner := self._scanners.get(name):
            scanner.enabled = False

    def run_all(self, enabled_only: bool = True) -> Iterator[ScanResult]:
        """Run all scanners and yield results."""
        for name, scanner in self._scanners.items():
            if enabled_only and not scanner.enabled:
                logger.debug(f"Skipping disabled scanner: {name}")
                continue

            logger.info(f"Running scanner: {name}")
            yield scanner.scan()

    def run(self, name: str) -> ScanResult | None:
        """Run a specific scanner by name."""
        if scanner := self._scanners.get(name):
            return scanner.scan()
        return None


def get_scanner_registry() -> ScannerRegistry:
    """
    Get the global scanner registry singleton.

    This is the preferred way to access the registry throughout the application.

    Returns:
        The global ScannerRegistry instance.
    """
    return ScannerRegistry.get_instance()
