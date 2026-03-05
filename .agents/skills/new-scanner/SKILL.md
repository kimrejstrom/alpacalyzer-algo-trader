---
name: "new-scanner"
description: "Use this skill ONLY when creating a new data scanner (e.g., Twitter scanner, Bloomberg scanner). Do not use for agents or strategies."
---

# Scope Constraint

- Scanner files go in `src/alpacalyzer/scanners/{name}_scanner.py`
- Tests go in `tests/test_{name}_scanner.py`
- Scanners discover trading opportunities from external data sources

# Placeholders

- `<scanner>` — lowercase with underscores (e.g., `twitter`)
- `<Scanner>` — PascalCase (e.g., `Twitter`)

# Steps

## 1. Study the reference implementations

Read these files:

1. `src/alpacalyzer/scanners/reddit_scanner.py` — Reddit API integration (PRAW)
2. `src/alpacalyzer/scanners/finviz_scanner.py` — web scraping + fundamental filters
3. `src/alpacalyzer/scanners/adapters.py` — scanner adapter pattern for pipeline integration

Key patterns: scanners implement the `Scanner` protocol (or extend `BaseScanner` ABC) from `src/alpacalyzer/pipeline/scanner_protocol.py`. They return `ScanResult` objects containing lists of `TopTicker`, handle API failures gracefully (return empty results), deduplicate results, and filter invalid symbols.

## 2. Create scanner file

Create `src/alpacalyzer/scanners/<scanner>_scanner.py`. Extend `BaseScanner` from `src/alpacalyzer/pipeline/scanner_protocol.py`:

```python
from alpacalyzer.pipeline.scanner_protocol import BaseScanner
from alpacalyzer.data.models import TopTicker

class <Scanner>Scanner(BaseScanner):
    def __init__(self):
        super().__init__(name="<scanner>", enabled=True, cache_ttl_seconds=300)

    def _execute_scan(self) -> list[TopTicker]:
        # Fetch data, extract tickers, deduplicate, filter
        # Return [] on failure, never crash
        ...
```

- API client initialization (use env vars for keys, never hardcode)
- `_execute_scan()` method — fetch data, extract tickers, deduplicate, filter
- Error handling — `BaseScanner.scan()` wraps `_execute_scan()` with timing and error handling automatically

## 3. Register scanner in pipeline

Create an adapter in `src/alpacalyzer/pipeline/scanner_adapters.py` following the existing `RedditScannerAdapter` or `SocialScannerAdapter` pattern.

Then register the adapter in `src/alpacalyzer/pipeline/registry.py` via `ScannerRegistry`. The CLI registers scanners at startup in `src/alpacalyzer/cli.py`.

## 4. Add env vars

If the scanner needs API keys, add to `.env.example` with a descriptive comment.

## 5. Write tests

Follow the pattern in existing scanner tests:

- Test successful scan returns ticker list
- Test API failure returns empty list (not exception)
- Test deduplication removes duplicates
- Test invalid ticker filtering (single letters, common words like "CEO", "WSB")
- Test result count is capped (max 20)

## 6. Run and verify

```bash
uv run pytest tests/test_<scanner>_scanner.py -v
```

# Reference files

| Purpose              | File                                           |
| -------------------- | ---------------------------------------------- |
| Scanner protocol     | `src/alpacalyzer/pipeline/scanner_protocol.py` |
| Reference scanner    | `src/alpacalyzer/scanners/reddit_scanner.py`   |
| Web scraping example | `src/alpacalyzer/scanners/finviz_scanner.py`   |
| Pipeline adapters    | `src/alpacalyzer/pipeline/scanner_adapters.py` |
| Scanner adapters     | `src/alpacalyzer/scanners/adapters.py`         |
| Scanner registry     | `src/alpacalyzer/pipeline/registry.py`         |
| CLI registration     | `src/alpacalyzer/cli.py`                       |
