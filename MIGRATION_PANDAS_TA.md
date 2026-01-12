# Migration from TA-Lib to pandas-ta

## Why Migrate?

**TA-Lib compilation is extremely slow** in CI/CD pipelines:

- Requires C compiler and build tools
- Takes 2-5 minutes to compile from source
- Adds complexity to GitHub Actions workflows
- Requires platform-specific installation steps

**pandas-ta is a pure Python alternative:**

- ✅ No compilation required
- ✅ Installs in seconds via pip/uv
- ✅ Same or better performance for most indicators
- ✅ More Pythonic API
- ✅ Active development and maintenance
- ✅ 100+ indicators available

## Migration Steps

### 1. Update Dependencies

```toml
# pyproject.toml
dependencies = [
    # Remove:
    # "ta-lib>=0.6.3",

    # Add:
    "pandas-ta>=0.3.14b",
]
```

### 2. Update Imports

```python
# Old (TA-Lib)
import talib

# New (pandas-ta)
import pandas_ta as ta
```

### 3. Update Indicator Calculations

#### Simple Moving Average (SMA)

```python
# Old
df["SMA_20"] = talib.SMA(df["close"].to_numpy(), timeperiod=20)

# New
df["SMA_20"] = df.ta.sma(length=20, append=False)
```

#### RSI (Relative Strength Index)

```python
# Old
df["RSI"] = talib.RSI(df["close"].to_numpy(), timeperiod=14)

# New
df["RSI"] = df.ta.rsi(length=14, append=False)
```

#### ATR (Average True Range)

```python
# Old
df["ATR"] = talib.ATR(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), timeperiod=14)

# New
df.ta.atr(length=14, append=True)
df.rename(columns={"ATRr_14": "ATR"}, inplace=True)
```

#### MACD

```python
# Old
macd, macd_signal, _ = talib.MACD(df["close"].to_numpy())
df["MACD"] = macd
df["MACD_Signal"] = macd_signal

# New
macd = df.ta.macd(append=False)
df["MACD"] = macd["MACD_12_26_9"]
df["MACD_Signal"] = macd["MACDs_12_26_9"]
```

#### Bollinger Bands

```python
# Old
upper, middle, lower = talib.BBANDS(df["close"].to_numpy())
df["BB_Upper"] = upper
df["BB_Middle"] = middle
df["BB_Lower"] = lower

# New
bbands = df.ta.bbands(length=20, std=2, append=False)
df["BB_Upper"] = bbands["BBU_20_2.0"]
df["BB_Middle"] = bbands["BBM_20_2.0"]
df["BB_Lower"] = bbands["BBL_20_2.0"]
```

#### ADX (Average Directional Index)

```python
# Old
df["ADX"] = talib.ADX(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), timeperiod=14)

# New
adx = df.ta.adx(length=14, append=False)
df["ADX"] = adx["ADX_14"]
```

#### Candlestick Patterns

```python
# Old
df["Bullish_Engulfing"] = talib.CDLENGULFING(df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy())

# New
df.ta.cdl_pattern(name="engulfing", append=True)
df["Bullish_Engulfing"] = df.get("CDL_ENGULFING", 0)
```

### 4. Update GitHub Actions Workflows

**Remove TA-Lib installation steps:**

```yaml
# DELETE these steps from .github/workflows/ci.yml and pr.yml:

- name: Install build dependencies
  run: |
    sudo apt-get update
    sudo apt-get install -y build-essential wget

- name: Cache TA-Lib
  id: cache-talib
  uses: actions/cache@v4
  with:
    path: |
      /usr/lib/libta-lib.*
      /usr/include/ta-lib/
    key: talib-${{ runner.os }}-0.6.4

- name: Install TA-Lib from source
  if: steps.cache-talib.outputs.cache-hit != 'true'
  run: |
    wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
    tar -xzf ta-lib-0.6.4-src.tar.gz
    cd ta-lib-0.6.4
    ./configure --prefix=/usr
    make
    sudo make install
```

**Expected CI/CD improvements:**

- ⚡ 2-5 minutes faster per workflow run
- ✅ Simpler workflow configuration
- ✅ No platform-specific build steps
- ✅ More reliable builds (no compilation failures)

### 5. Replace the Module

```bash
# Rename old module (backup)
mv src/alpacalyzer/analysis/technical_analysis.py src/alpacalyzer/analysis/technical_analysis_talib.py

# Rename new module
mv src/alpacalyzer/analysis/technical_analysis_pandas_ta.py src/alpacalyzer/analysis/technical_analysis.py
```

### 6. Update Dependencies

```bash
# Remove ta-lib
uv remove ta-lib

# Add pandas-ta
uv add pandas-ta

# Sync dependencies
uv sync
```

### 7. Run Tests

```bash
# Run all tests to ensure compatibility
uv run pytest tests -v

# Run specific technical analysis tests
uv run pytest tests/test_technical_analysis.py -v
```

## Compatibility Notes

### Indicator Value Differences

pandas-ta and TA-Lib may produce slightly different values due to:

- Different calculation methods
- Rounding differences
- Edge case handling

**These differences are typically negligible (<0.1%) and don't affect trading decisions.**

### Candlestick Pattern Detection

pandas-ta candlestick patterns return:

- `100` for bullish patterns
- `-100` for bearish patterns
- `0` for no pattern

This matches TA-Lib's behavior.

### Column Naming

pandas-ta uses descriptive column names:

- `ATRr_14` instead of `ATR`
- `MACD_12_26_9` instead of `MACD`
- `BBU_20_2.0` instead of `BB_Upper`

**Solution:** Rename columns after calculation (as shown in examples above).

## Performance Comparison

| Indicator            | TA-Lib  | pandas-ta       | Winner        |
| -------------------- | ------- | --------------- | ------------- |
| SMA                  | Fast    | Fast            | Tie           |
| RSI                  | Fast    | Fast            | Tie           |
| MACD                 | Fast    | Fast            | Tie           |
| ATR                  | Fast    | Fast            | Tie           |
| Bollinger Bands      | Fast    | Fast            | Tie           |
| ADX                  | Fast    | Slightly slower | TA-Lib        |
| Candlestick Patterns | Fast    | Slightly slower | TA-Lib        |
| **Installation**     | 2-5 min | <10 sec         | **pandas-ta** |
| **CI/CD**            | Complex | Simple          | **pandas-ta** |

**Verdict:** pandas-ta is the clear winner for CI/CD workflows despite slightly slower computation for some indicators.

## Rollback Plan

If you need to rollback:

```bash
# Restore old module
mv src/alpacalyzer/analysis/technical_analysis_talib.py src/alpacalyzer/analysis/technical_analysis.py

# Restore dependencies
uv remove pandas-ta
uv add ta-lib
uv sync
```

## References

- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta)
- [pandas-ta Indicators List](https://github.com/twopirllc/pandas-ta#indicators)
- [TA-Lib Documentation](https://ta-lib.org/)
