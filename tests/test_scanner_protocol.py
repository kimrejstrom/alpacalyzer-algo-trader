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
