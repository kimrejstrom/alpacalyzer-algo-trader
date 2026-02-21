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

Key patterns: scanners return lists of ticker symbols, handle API failures gracefully (return `[]`), deduplicate results, and filter invalid symbols.

## 2. Create scanner file

Copy `src/alpacalyzer/scanners/reddit_scanner.py` → `src/alpacalyzer/scanners/<scanner>_scanner.py` and modify:

- API client initialization (use env vars for keys, never hardcode)
- `scan()` method — fetch data, extract tickers, deduplicate, filter
- Error handling — always return `[]` on failure, never crash

## 3. Register scanner

Edit `src/alpacalyzer/scanners/__init__.py` to export the new scanner class.

For pipeline integration, create an adapter in `src/alpacalyzer/scanners/adapters.py` following the existing `RedditScannerAdapter` pattern.

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

| Purpose              | File                                         |
| -------------------- | -------------------------------------------- |
| Reference scanner    | `src/alpacalyzer/scanners/reddit_scanner.py` |
| Web scraping example | `src/alpacalyzer/scanners/finviz_scanner.py` |
| Adapters             | `src/alpacalyzer/scanners/adapters.py`       |
| Pipeline integration | `src/alpacalyzer/pipeline/`                  |
