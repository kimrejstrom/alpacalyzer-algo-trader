import json
import os
from unittest.mock import MagicMock, patch

import pytest

from alpacalyzer.sync.client import SYNC_FAILURES_LOG, JournalSyncClient
from alpacalyzer.sync.models import TradeDecisionRecord


@pytest.fixture
def mock_trade_record():
    """Create a test TradeDecisionRecord."""
    return TradeDecisionRecord(
        ticker="AAPL",
        side="LONG",
        shares=100,
        entry_price="150.00",
        entry_date="2026-01-15T10:00:00Z",
        status="OPEN",
    )


@pytest.fixture
def client():
    """Create a JournalSyncClient for testing."""
    return JournalSyncClient(
        base_url="http://localhost:3000",
        api_key="test-api-key",
    )


class TestJournalSyncClient:
    def test_successful_sync(self, client, mock_trade_record):
        """Test that successful sync returns response JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "trade-123", "status": "synced"}

        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            result = client.sync_trade(mock_trade_record)

            assert result == {"id": "trade-123", "status": "synced"}
            mock_post.assert_called_once()

    def test_5xx_error_retries(self, client, mock_trade_record):
        """Test that 5xx errors trigger retries with exponential backoff."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            with patch("alpacalyzer.sync.client.time.sleep") as mock_sleep:
                result = client.sync_trade(mock_trade_record)

                assert result is None
                assert mock_post.call_count == 3
                assert mock_sleep.call_count == 2

    def test_4xx_error_no_retry(self, client, mock_trade_record):
        """Test that 4xx errors don't trigger retries."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            with patch("alpacalyzer.sync.client.logger") as mock_logger:
                result = client.sync_trade(mock_trade_record)

                assert result is None
                assert mock_post.call_count == 1
                mock_logger.warning.assert_called()

    def test_timeout_handling(self, client, mock_trade_record):
        """Test that timeouts are handled and retried."""
        import requests

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        def side_effect(*args, **kwargs):
            raise requests.Timeout()

        with patch.object(client._session, "post", side_effect=side_effect) as mock_post:
            with patch("alpacalyzer.sync.client.time.sleep"):
                result = client.sync_trade(mock_trade_record)

                assert result is None
                assert mock_post.call_count == 3

    def test_connection_error_retries(self, client, mock_trade_record):
        """Test that connection errors trigger retries."""
        import requests

        def side_effect(*args, **kwargs):
            raise requests.ConnectionError("Connection failed")

        with patch.object(client._session, "post", side_effect=side_effect) as mock_post:
            with patch("alpacalyzer.sync.client.time.sleep"):
                result = client.sync_trade(mock_trade_record)

                assert result is None
                assert mock_post.call_count == 3

    def test_failure_logged_to_file(self, client, mock_trade_record):
        """Test that failed syncs are logged to sync_failures.jsonl."""
        import requests

        if os.path.exists(SYNC_FAILURES_LOG):
            os.remove(SYNC_FAILURES_LOG)

        with patch.object(client._session, "post", side_effect=requests.ConnectionError()):
            with patch("alpacalyzer.sync.client.time.sleep"):
                client.sync_trade(mock_trade_record)

        assert os.path.exists(SYNC_FAILURES_LOG)
        with open(SYNC_FAILURES_LOG) as f:
            lines = f.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["ticker"] == "AAPL"
            assert "error" in entry
            assert "payload" in entry

        os.remove(SYNC_FAILURES_LOG)

    def test_none_return_on_all_failures(self, client, mock_trade_record):
        """Test that all failure paths return None, never raise."""
        import requests

        with patch.object(client._session, "post", side_effect=requests.ConnectionError()):
            with patch("alpacalyzer.sync.client.time.sleep"):
                result = client.sync_trade(mock_trade_record)

        assert result is None

    def test_header_includes_api_key(self):
        """Test that X-API-Key header is set on requests."""
        client = JournalSyncClient(base_url="http://localhost:3000", api_key="test-api-key")
        assert client._session.headers.get("X-API-Key") == "test-api-key"

    def test_content_type_header(self):
        """Test that Content-Type header is set."""
        client = JournalSyncClient(base_url="http://localhost:3000", api_key="test-api-key")
        assert client._session.headers.get("Content-Type") == "application/json"

    def test_base_url_trailing_slash(self, client, mock_trade_record):
        """Test that trailing slashes are removed from base_url."""
        client_trailing = JournalSyncClient(
            base_url="http://localhost:3000/",
            api_key="test-key",
        )
        assert client_trailing.base_url == "http://localhost:3000"
