---
name: "technical-indicator"
description: "Use this skill ONLY when adding a new technical indicator (e.g., Bollinger Bands, Stochastic, ATR). Do not use for strategies or agents."
---

# Scope Constraint

- Indicators go in `src/alpacalyzer/analysis/technical_analysis.py` (methods on `TechnicalAnalyzer`)
- Tests go in `tests/test_technical_analysis.py`
- Uses TA-Lib where available, pandas/numpy for custom calculations

# Steps

## 1. Study existing indicators

Read `src/alpacalyzer/analysis/technical_analysis.py` — all indicators are methods on `TechnicalAnalyzer`. Each returns `dict` with `value`, `signal` ("bullish"/"bearish"/"neutral"), and `description`.

Also read `tests/test_technical_analysis.py` for the test pattern.

## 2. Check TA-Lib availability

```python
import talib
print(dir(talib))  # See available functions
```

Use TA-Lib if the indicator exists there. Otherwise implement with pandas/numpy.

## 3. Add indicator method

Add `calculate_<indicator>(self, ticker, period)` to `TechnicalAnalyzer`. Follow the pattern:

- Fetch price data with `self.get_price_data(ticker, days=max(period * 2, 30))`
- Handle insufficient data → return `{"value": None, "signal": "neutral", "description": "Insufficient data"}`
- Calculate indicator value
- Interpret signal (be conservative — when in doubt, return neutral)
- Wrap in try/except → return neutral on error

## 4. Integrate with analyze_ticker()

Add your indicator to `analyze_ticker()` method — include in signals list and score calculation if appropriate.

## 5. Write tests

Test: bullish signal, bearish signal, insufficient data handling, error handling, integration in `analyze_ticker()`. Use mock price data (pandas DataFrame with Close/High/Low/Open/Volume columns).

## 6. Run and verify

```bash
uv run pytest tests/test_technical_analysis.py -v
```

# Reference files

| Purpose        | File                                             |
| -------------- | ------------------------------------------------ |
| All indicators | `src/alpacalyzer/analysis/technical_analysis.py` |
| Tests          | `tests/test_technical_analysis.py`               |
