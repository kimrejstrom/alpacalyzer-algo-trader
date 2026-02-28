import json
import os
import time
from datetime import UTC, datetime
from typing import Any

import requests

from alpacalyzer.sync.models import TradeDecisionRecord
from alpacalyzer.utils.logger import get_logger

logger = get_logger("sync")

LOGS_DIR = os.path.join(os.getcwd(), "logs")
SYNC_FAILURES_LOG = os.path.join(LOGS_DIR, "sync_failures.jsonl")

MAX_RETRIES = 3
BASE_DELAY = 1
MAX_DELAY = 10
REQUEST_TIMEOUT = 10


class JournalSyncClient:
    """HTTP client for syncing trades to my-stock-journal app."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            }
        )

    def sync_trade(self, record: TradeDecisionRecord) -> dict[str, Any] | None:
        """
        POST a TradeDecisionRecord to the journal sync endpoint.

        Args:
            record: The trade decision record to sync.

        Returns:
            Parsed response JSON on success, None on failure.
        """
        url = f"{self.base_url}/api/sync/trades"
        payload = record.model_dump_json()

        for attempt in range(MAX_RETRIES):
            try:
                response = self._session.post(
                    url,
                    data=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                if response.status_code >= 500:
                    logger.warning(f"Journal sync received 5xx ({response.status_code}), attempt {attempt + 1}/{MAX_RETRIES}")
                    if attempt < MAX_RETRIES - 1:
                        delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
                        time.sleep(delay)
                    continue

                if response.status_code >= 400:
                    logger.warning(f"Journal sync received 4xx ({response.status_code}), not retrying: {response.text[:200]}")
                    self._log_failure(record, f"Client error: {response.status_code}", payload)
                    return None

                logger.info(f"Successfully synced trade for {record.ticker}")
                return response.json()

            except requests.Timeout:
                logger.warning(f"Journal sync timeout, attempt {attempt + 1}/{MAX_RETRIES}")
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
                    time.sleep(delay)
                continue

            except requests.ConnectionError as e:
                logger.warning(f"Journal sync connection error, attempt {attempt + 1}/{MAX_RETRIES}: {e}")
                if attempt < MAX_RETRIES - 1:
                    delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
                    time.sleep(delay)
                continue

            except Exception as e:
                logger.error(f"Journal sync unexpected error: {e}")
                self._log_failure(record, str(e), payload)
                return None

        self._log_failure(record, f"Max retries ({MAX_RETRIES}) exceeded", payload)
        return None

    def _log_failure(self, record: TradeDecisionRecord, error_message: str, payload: str) -> None:
        """Log failed sync to sync_failures.jsonl for manual replay."""
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
            failure_entry = {
                "timestamp": datetime.now(UTC).isoformat(),
                "ticker": record.ticker,
                "error": error_message,
                "payload": payload,
            }
            with open(SYNC_FAILURES_LOG, "a") as f:
                f.write(json.dumps(failure_entry) + "\n")
            logger.debug(f"Logged sync failure for {record.ticker} to {SYNC_FAILURES_LOG}")
        except Exception as log_err:
            logger.error(f"Failed to write sync failure log: {log_err}")
