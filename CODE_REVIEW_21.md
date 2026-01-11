# Code Review for Implement ScannerRegistry for Phase 4 of migration

**PR**: https://github.com/kimrejstrom/alpacalyzer-algo-trader/pull/47
**Issue**: #21

## Overview

This PR implements `ScannerRegistry` for centralized scanner management as part of Phase 4 (Opportunity Pipeline) of the migration roadmap. The implementation includes:

- `ScannerRegistry` class with singleton pattern for global access
- Registry methods: `register()`, `unregister()`, `get()`, `list()`, `list_enabled()`, `enable()`, `disable()`
- `run_all()` and `run()` methods for scanner execution
- Four adapter classes wrapping existing scanners (WSB, Stocktwits, Finviz, Social)
- Unit tests (17 tests, all passing)

## Suggestions

### 🐛 StocktwitsScannerAdapter has redundant confidence value

- **Priority**: Medium
- **File**: `src/alpacalyzer/pipeline/scanner_adapters.py:83`
- **Details**: The `confidence` value is always 0.7 with `min(0.7, 1.0)` which is redundant - it will always be 0.7.
- **Suggested Change**:

```python
tickers.append(
    TopTicker(
        ticker=ticker,
        signal="neutral",
        confidence=0.7,  # Just 0.7 directly
        reasoning=f"Watchers: {watchers} - {title[:50] if title else 'No description'}",
    )
)
```

### ℹ️ FinvizScannerAdapter uses hardcoded column name

- **Priority**: Low
- **File**: `src/alpacalyzer/pipeline/scanner_adapters.py:125`
- **Details**: The adapter uses `row.get("Ticker")` with capital T, which works for Finviz but could be more defensive if column names vary.
- **Suggested Change**: The current implementation already handles both cases with `row.get("Ticker") or row.get("ticker")`, which is good practice. No change needed - this is actually well done.

### 🔍 WSBScannerAdapter signal logic is simplistic

- **Priority**: Low
- **File**: `src/alpacalyzer/pipeline/scanner_adapters.py:36`
- **Details**: The signal is determined by `mentions > 10` which is a very low threshold. Most trending stocks will have >10 mentions, making almost everything "bullish".
- **Suggested Change**: Consider using a percentile-based approach or configurable threshold:

```python
# In __init__, could add config
self.high_mentions_threshold = high_mentions_threshold  # e.g., 50

# In _df_to_tickers
signal = "bullish" if mentions >= self.high_mentions_threshold else "neutral"
```

### ⚠️ FinvizScannerAdapter signal logic uses RSI < 70

- **Priority**: Medium
- **File**: `src/alpacalyzer/pipeline/scanner_adapters.py:132`
- **Details**: Using `float(rsi) < 70` as the bullish threshold means RSI of 69.9 is bullish but 70.1 is neutral. This is an odd boundary - typically RSI > 70 is overbought (bearish), RSI < 30 is oversold (bullish), and 30-70 is neutral.
- **Suggested Change**:

```python
# More conventional RSI interpretation
if float(rsi) < 30:
    signal = "bullish"  # Oversold
elif float(rsi) > 70:
    signal = "bearish"  # Overbought
else:
    signal = "neutral"
```

### 🔒 Singleton pattern has no reset mechanism

- **Priority**: Medium
- **File**: `src/alpacalyzer/pipeline/registry.py:29-36`
- **Details**: The `ScannerRegistry` singleton has no way to reset or clear the instance, which can cause issues in tests or when reconfiguring scanners.
- **Suggested Change**: Add a class method for testing:

```python
@classmethod
def _reset(cls) -> None:
    """Reset singleton instance (for testing)."""
    cls._instance = None
```

### 📝 FinvizScannerAdapter RSI handling could fail on non-numeric

- **Priority**: High
- **File**: `src/alpacalyzer/pipeline/scanner_adapters.py:126-132`
- **Details**: The code does `float(rsi)` without checking if RSI is None or non-numeric. Finviz returns "-" for missing data. The FinvizScanner handles this in `get_stock_ranks()` by converting "-" to None, but in the adapter's `_df_to_tickers()`, there's no such handling.
- **Suggested Change**:

```python
rsi = row.get("RSI", 50)
try:
    rsi_float = float(rsi) if rsi and rsi != "-" else 50.0
except (ValueError, TypeError):
    rsi_float = 50.0

rel_vol = row.get("Relative Volume") or row.get("rel_volume", 0)
try:
    rel_vol_float = float(rel_vol) if rel_vol and rel_vol != "-" else 0.0
except (ValueError, TypeError):
    rel_vol_float = 0.0

score = (rel_vol_float / 10.0 + (100 - abs(rsi_float - 50)) / 100.0) / 2.0
```

### 🧪 Test for adapter error handling is missing

- **Priority**: Medium
- **File**: `tests/test_pipeline/test_registry.py`
- **Details**: Tests cover registry operations but don't test the actual adapter implementations (WSB, Stocktwits, Finviz, Social) with their real scanner behavior or error scenarios.
- **Suggested Change**: Add integration tests for adapters (with mocked scanners):

```python
def test_wsb_adapter_empty_dataframe(self):
    """Test WSB adapter handles empty results gracefully."""
    # Would need to mock WSBScanner.get_trending_stocks to return empty df
    pass

def test_finviz_adapter_invalid_data(self):
    """Test Finviz adapter handles non-numeric RSI values."""
    # Test with RSI = "-" or None
    pass
```

### 📚 Missing docstring for `get_scanner_registry`

- **Priority**: Low
- **File**: `src/alpacalyzer/pipeline/registry.py:85-87`
- **Details**: The helper function has minimal documentation.
- **Suggested Change**:

```python
def get_scanner_registry() -> ScannerRegistry:
    """
    Get the global scanner registry singleton.
    
    This is the preferred way to access the registry throughout the application.
    
    Returns:
        The global ScannerRegistry instance.
    """
    return ScannerRegistry.get_instance()
```

### ✨ SocialScannerAdapter fetches data from all three sources

- **Positive note**: `src/alpacalyzer/pipeline/scanner_adapters.py:140-158`
- **Details**: The SocialScannerAdapter correctly wraps the existing SocialScanner which combines WSB, Stocktwits, and Finviz data. This is good design - it reuses existing functionality rather than duplicating logic.

### 🧩 Well-structured adapter pattern

- **Positive note**: `src/alpacalyzer/pipeline/scanner_adapters.py`
- **Details**: The adapter pattern implementation is clean and consistent. Each adapter:
  - Inherits from `BaseScanner`
  - Wraps an existing scanner in `__init__`
  - Implements `_execute_scan()` and `_df_to_tickers()`
  - Returns `TopTicker` objects in the expected format

### ✅ Comprehensive test coverage for registry

- **Positive note**: `tests/test_pipeline/test_registry.py`
- **Details**: The test suite covers:
  - Singleton behavior
  - Registration/unregistration
  - Enable/disable functionality
  - Running individual and all scanners
  - Error handling in scan results
  - Scan timing

## Trading Logic Review

This PR does not change any trading logic - it adds infrastructure for scanner management. No trading-specific review needed.

## Summary

**Ready to merge?**: With fixes

**Reasoning**: The implementation is solid and follows the requirements, but there are a few issues that should be addressed before merging, particularly the handling of non-numeric RSI values in the Finviz adapter.

### Strengths

- Clean implementation of the registry pattern with singleton
- Adapter pattern properly implemented for all four existing scanners
- Comprehensive unit tests (17 tests) covering registry operations
- Type-safe implementation with proper return types
- Follows project conventions and architecture

### Issues to Address

**Critical**: None

**High**:
- FinvizAdapter needs better handling of non-numeric RSI/rel_vol values

**Medium**:
- Add singleton reset method for testing
- Consider more sophisticated signal logic for WSB and Finviz adapters
- Add adapter-specific integration tests

**Low**:
- Remove redundant `min(0.7, 1.0)` in StocktwitsAdapter
- Improve docstrings