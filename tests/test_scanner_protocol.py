from datetime import UTC, datetime

from alpacalyzer.data.models import TopTicker
from alpacalyzer.pipeline.scanner_protocol import BaseScanner, Scanner, ScanResult


class MockScanner(BaseScanner):
    def __init__(self, name: str = "mock", enabled: bool = True, should_fail: bool = False):
        super().__init__(name=name, enabled=enabled)
        self.should_fail = should_fail

    def _execute_scan(self) -> list[TopTicker]:
        if self.should_fail:
            raise RuntimeError("Scan failed")
        return [TopTicker(ticker="AAPL", signal="bullish", confidence=0.8, reasoning="Strong momentum"), TopTicker(ticker="TSLA", signal="neutral", confidence=0.5, reasoning="Consolidating")]


class TestScanResult:
    def test_success_property(self):
        result = ScanResult(source="test", tickers=[], error=None)
        assert result.success is True

    def test_success_property_with_error(self):
        result = ScanResult(source="test", tickers=[], error="Scan failed")
        assert result.success is False

    def test_count_property(self):
        result = ScanResult(
            source="test", tickers=[TopTicker(ticker="AAPL", signal="bullish", confidence=0.8, reasoning="test"), TopTicker(ticker="TSLA", signal="neutral", confidence=0.5, reasoning="test")]
        )
        assert result.count == 2

    def test_symbols_method(self):
        result = ScanResult(
            source="test", tickers=[TopTicker(ticker="AAPL", signal="bullish", confidence=0.8, reasoning="test"), TopTicker(ticker="TSLA", signal="neutral", confidence=0.5, reasoning="test")]
        )
        assert result.symbols() == ["AAPL", "TSLA"]

    def test_default_scanned_at(self):
        result = ScanResult(source="test", tickers=[])
        assert isinstance(result.scanned_at, datetime)

    def test_default_duration(self):
        result = ScanResult(source="test", tickers=[])
        assert result.duration_seconds == 0.0

    def test_cached_default_false(self):
        result = ScanResult(source="test", tickers=[])
        assert result.cached is False

    def test_cached_can_be_set(self):
        result = ScanResult(source="test", tickers=[], cached=True)
        assert result.cached is True


class TestScannerProtocol:
    def test_protocol_is_runtime_checkable(self):
        mock = MockScanner()
        assert isinstance(mock, Scanner)

    def test_protocol_name_property(self):
        mock = MockScanner(name="test_scanner")
        assert mock.name == "test_scanner"

    def test_protocol_enabled_property(self):
        mock = MockScanner(enabled=True)
        assert mock.enabled is True

    def test_protocol_scan_method(self):
        mock = MockScanner()
        result = mock.scan()
        assert isinstance(result, ScanResult)
        assert result.source == "mock"


class TestBaseScanner:
    def test_initialization(self):
        scanner = MockScanner(name="test", enabled=True)
        assert scanner.name == "test"
        assert scanner.enabled is True
        assert scanner.last_scan is None

    def test_scan_returns_result(self):
        scanner = MockScanner()
        result = scanner.scan()

        assert isinstance(result, ScanResult)
        assert result.source == "mock"
        assert result.count == 2
        assert result.success is True

    def test_scan_updates_last_scan(self):
        scanner = MockScanner()
        result = scanner.scan()

        assert scanner.last_scan is result
        assert scanner.last_scan is not None

    def test_scan_catches_errors(self):
        scanner = MockScanner(should_fail=True)
        result = scanner.scan()

        assert result.success is False
        assert result.error == "Scan failed"
        assert result.count == 0

    def test_scan_sets_duration(self):
        scanner = MockScanner()
        result = scanner.scan()

        assert result.duration_seconds > 0

    def test_enabled_setter(self):
        scanner = MockScanner(enabled=True)
        assert scanner.enabled is True

        scanner.enabled = False
        assert scanner.enabled is False

    def test_scan_timestamp(self):
        scanner = MockScanner()
        result = scanner.scan()

        assert isinstance(result.scanned_at, datetime)
        # Check it's a recent timestamp (within last minute)
        now = datetime.now(UTC)
        assert (now - result.scanned_at).total_seconds() < 60

    def test_multiple_scans_update_last_scan(self):
        scanner = MockScanner()

        result1 = scanner.scan()
        assert scanner.last_scan is result1

        result2 = scanner.scan()
        assert scanner.last_scan is result2
        assert result2.scanned_at > result1.scanned_at


class CachingScanner(BaseScanner):
    """Scanner with cache TTL for testing."""

    def __init__(self, cache_ttl_seconds: int = 60):
        super().__init__(name="caching", enabled=True, cache_ttl_seconds=cache_ttl_seconds)
        self.scan_count = 0

    def _execute_scan(self) -> list[TopTicker]:
        self.scan_count += 1
        return [TopTicker(ticker="AAPL", signal="bullish", confidence=0.8, reasoning="test")]


class TestScannerCaching:
    def test_cache_returns_same_result_within_ttl(self):
        scanner = CachingScanner(cache_ttl_seconds=3600)
        result1 = scanner.scan()
        result2 = scanner.scan()

        assert scanner.scan_count == 1
        assert result1 is result2

    def test_cached_flag_set_on_cache_hit(self):
        scanner = CachingScanner(cache_ttl_seconds=3600)
        result1 = scanner.scan()
        assert result1.cached is False

        result2 = scanner.scan()
        assert result2.cached is True

    def test_cached_flag_false_on_fresh_scan(self):
        scanner = CachingScanner(cache_ttl_seconds=0)
        result = scanner.scan()
        assert result.cached is False

    def test_no_cache_when_ttl_is_zero(self):
        scanner = CachingScanner(cache_ttl_seconds=0)
        scanner.scan()
        scanner.scan()

        assert scanner.scan_count == 2

    def test_cache_expires_after_ttl(self):
        scanner = CachingScanner(cache_ttl_seconds=1)
        result1 = scanner.scan()

        # Backdate the cached result so it appears expired
        from datetime import timedelta

        result1.scanned_at = result1.scanned_at - timedelta(seconds=2)

        result2 = scanner.scan()
        assert scanner.scan_count == 2
        assert result2 is not result1

    def test_cache_skipped_on_error(self):
        """Failed scans should not be cached."""
        scanner = CachingScanner(cache_ttl_seconds=3600)

        # Force an error result into last_scan
        error_result = ScanResult(source="caching", tickers=[], error="boom")
        scanner._last_scan = error_result

        result = scanner.scan()
        assert result.success is True
        assert scanner.scan_count == 1

    def test_default_cache_ttl_is_zero(self):
        scanner = MockScanner()
        assert scanner._cache_ttl_seconds == 0
