"""Tests for ScannerRegistry."""

import pytest

from alpacalyzer.pipeline.registry import ScannerRegistry, get_scanner_registry
from alpacalyzer.pipeline.scanner_protocol import BaseScanner, TopTicker


class MockScanner(BaseScanner):
    """Mock scanner for testing."""

    def __init__(self, name: str, enabled: bool = True):
        super().__init__(name=name, enabled=enabled)
        self.scan_count = 0

    def _execute_scan(self) -> list[TopTicker]:
        self.scan_count += 1
        return [
            TopTicker(
                ticker="AAPL",
                signal="bullish",
                confidence=0.8,
                reasoning="Test reasoning",
            )
        ]


@pytest.fixture
def registry():
    """Get a fresh registry instance for each test."""
    return ScannerRegistry()


@pytest.fixture
def mock_scanner():
    """Create a mock scanner."""
    return MockScanner("test_scanner", enabled=True)


class TestScannerRegistry:
    """Test ScannerRegistry functionality."""

    def test_singleton_behavior(self):
        """Test that get_scanner_registry returns the same instance."""
        reg1 = get_scanner_registry()
        reg2 = get_scanner_registry()
        assert reg1 is reg2

    def test_register_scanner(self, registry, mock_scanner):
        """Test registering a scanner."""
        registry.register(mock_scanner)
        assert "test_scanner" in registry.list()
        assert registry.get("test_scanner") is mock_scanner

    def test_register_overwrites_existing(self, registry, mock_scanner):
        """Test that registering with same name overwrites."""
        scanner1 = MockScanner("test_scanner", enabled=True)
        scanner2 = MockScanner("test_scanner", enabled=False)
        scanner2.scan_count = 5

        registry.register(scanner1)
        registry.register(scanner2)

        assert registry.get("test_scanner") is scanner2
        assert registry.get("test_scanner").scan_count == 5

    def test_unregister_scanner(self, registry, mock_scanner):
        """Test unregistering a scanner."""
        registry.register(mock_scanner)
        registry.unregister("test_scanner")
        assert "test_scanner" not in registry.list()
        assert registry.get("test_scanner") is None

    def test_get_nonexistent_scanner(self, registry):
        """Test getting a scanner that doesn't exist."""
        assert registry.get("nonexistent") is None

    def test_list_scanners(self, registry):
        """Test listing all registered scanners."""
        registry.register(MockScanner("scanner1"))
        registry.register(MockScanner("scanner2"))
        registry.register(MockScanner("scanner3"))

        scanner_names = registry.list()
        assert set(scanner_names) == {"scanner1", "scanner2", "scanner3"}

    def test_list_enabled_scanners(self, registry):
        """Test listing only enabled scanners."""
        registry.register(MockScanner("scanner1", enabled=True))
        registry.register(MockScanner("scanner2", enabled=False))
        registry.register(MockScanner("scanner3", enabled=True))

        enabled_names = registry.list_enabled()
        assert set(enabled_names) == {"scanner1", "scanner3"}

    def test_enable_scanner(self, registry):
        """Test enabling a scanner."""
        scanner = MockScanner("scanner1", enabled=False)
        registry.register(scanner)
        assert not scanner.enabled

        registry.enable("scanner1")
        assert scanner.enabled

    def test_enable_nonexistent_scanner(self, registry):
        """Test enabling a scanner that doesn't exist (should not crash)."""
        registry.enable("nonexistent")
        pass

    def test_disable_scanner(self, registry):
        """Test disabling a scanner."""
        scanner = MockScanner("scanner1", enabled=True)
        registry.register(scanner)
        assert scanner.enabled

        registry.disable("scanner1")
        assert not scanner.enabled

    def test_disable_nonexistent_scanner(self, registry):
        """Test disabling a scanner that doesn't exist (should not crash)."""
        registry.disable("nonexistent")
        pass

    def test_run_single_scanner(self, registry, mock_scanner):
        """Test running a single scanner."""
        registry.register(mock_scanner)
        result = registry.run("test_scanner")

        assert result is not None
        assert result.source == "test_scanner"
        assert result.success
        assert result.count == 1
        assert result.tickers[0].ticker == "AAPL"

    def test_run_nonexistent_scanner(self, registry):
        """Test running a scanner that doesn't exist."""
        result = registry.run("nonexistent")
        assert result is None

    def test_run_all_enabled_only(self, registry):
        """Test running all enabled scanners only."""
        scanner1 = MockScanner("scanner1", enabled=True)
        scanner2 = MockScanner("scanner2", enabled=False)
        scanner3 = MockScanner("scanner3", enabled=True)

        registry.register(scanner1)
        registry.register(scanner2)
        registry.register(scanner3)

        results = list(registry.run_all(enabled_only=True))
        assert len(results) == 2
        assert scanner1.scan_count == 1
        assert scanner2.scan_count == 0
        assert scanner3.scan_count == 1

    def test_run_all_including_disabled(self, registry):
        """Test running all scanners including disabled ones."""
        scanner1 = MockScanner("scanner1", enabled=True)
        scanner2 = MockScanner("scanner2", enabled=False)

        registry.register(scanner1)
        registry.register(scanner2)

        results = list(registry.run_all(enabled_only=False))
        assert len(results) == 2
        assert scanner1.scan_count == 1
        assert scanner2.scan_count == 1

    def test_scan_result_error_handling(self, registry):
        """Test that scanner errors are captured in ScanResult."""

        class FailingScanner(BaseScanner):
            def _execute_scan(self) -> list[TopTicker]:
                raise ValueError("Test error")

        registry.register(FailingScanner("failing_scanner"))
        result = registry.run("failing_scanner")

        assert result is not None
        assert not result.success
        assert result.error == "Test error"
        assert result.count == 0

    def test_scan_result_timing(self, registry, mock_scanner):
        """Test that scan duration is recorded."""
        registry.register(mock_scanner)
        result = registry.run("test_scanner")

        assert result.duration_seconds >= 0
