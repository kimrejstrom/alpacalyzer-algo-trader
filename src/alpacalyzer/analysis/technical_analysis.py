from datetime import UTC, datetime, timedelta
from typing import TypedDict, cast

import pandas as pd
import talib
from alpaca.data.enums import Adjustment
from alpaca.data.models import Bar, BarSet
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.enums import OrderSide

from alpacalyzer.trading.alpaca_client import get_market_status, history_client
from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import logger


class TradingSignals(TypedDict):
    symbol: str
    price: float
    atr: float
    rvol: float
    signals: list[str]  # List of trading signal descriptions
    raw_score: int
    score: float  # Normalized score (0-1)
    momentum: float  # 24h momentum
    raw_data_daily: pd.DataFrame
    raw_data_intraday: pd.DataFrame


class TechnicalAnalyzer:
    def preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize index and clean up the DataFrame."""
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index(level=1, drop=True)
        return df

    @timed_lru_cache(seconds=60, maxsize=128)
    def get_historical_data(self, symbol, request_type="minute") -> pd.DataFrame | None:
        """Get historical data from Alpaca."""
        try:
            now_utc = datetime.now(UTC)  # Get the current UTC time
            end = now_utc - timedelta(seconds=930)  # 15.5 minutes ago

            # Determine the `start` time based on the `request_type`
            if request_type == "minute":
                start = end - timedelta(minutes=1440)  # Last 24 hours
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame(5, TimeFrameUnit.Minute),
                    start=start,
                    end=end,
                    adjustment=Adjustment.ALL,
                )
            else:
                start = end - timedelta(days=100)  # Last 100 days
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Day,
                    start=start,
                    end=end,
                    adjustment=Adjustment.ALL,
                )
            try:
                bars_response = history_client.get_stock_bars(request)
                candles = cast(BarSet, bars_response).data.get(symbol)
                if not candles or candles is None:
                    return None

                # Check market status
                if get_market_status() == "open":
                    # Fetch the latest bar for fresh data (only available during market hours)
                    latest_bar_response = history_client.get_stock_latest_bar(
                        StockLatestBarRequest(symbol_or_symbols=symbol)
                    )
                    latest_bar = cast(dict[str, Bar], latest_bar_response).get(symbol)

                    # Append the latest bar if available, otherwise duplicate the last candle
                    candles.append(latest_bar if latest_bar else candles[-1])
                else:
                    # Market is closed, duplicate the last candle
                    candles.append(candles[-1])

                return pd.DataFrame(
                    [
                        {
                            "symbol": bar.symbol,
                            "timestamp": bar.timestamp,
                            "open": bar.open,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close,
                            "volume": bar.volume,
                            "trade_count": bar.trade_count,
                            "vwap": bar.vwap,
                        }
                        for bar in candles
                    ]
                )
            except Exception as e:
                logger.error(f"Error fetching stock bars for {symbol}: {str(e)}", exc_info=True)
                return None

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}", exc_info=True)
            return None

    def calculate_intraday_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate intraday technical indicators."""

        df["ATR"] = talib.ATR(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), timeperiod=30)

        # MACD
        macd, macd_signal, _ = talib.MACD(df["close"].to_numpy())
        df["MACD"] = macd
        df["MACD_Signal"] = macd_signal

        # Volume
        df["Volume_MA"] = talib.SMA(df["volume"].to_numpy(), timeperiod=30)  # Average volume
        df["RVOL"] = df["volume"] / df["Volume_MA"]  # Relative Volume
        # Bollinger Bands
        upper, middle, lower = talib.BBANDS(df["close"].to_numpy())
        df["BB_Upper"] = upper
        df["BB_Middle"] = middle
        df["BB_Lower"] = lower

        # Candlestick patterns
        df["Bullish_Engulfing"] = talib.CDLENGULFING(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Bearish_Engulfing"] = talib.CDLENGULFING(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Shooting_Star"] = talib.CDLSHOOTINGSTAR(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Hammer"] = talib.CDLHAMMER(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Doji"] = talib.CDLDOJI(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )

        return df

    def calculate_daily_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate daily technical indicators."""

        # Basic indicators
        df["SMA_20"] = talib.SMA(df["close"].to_numpy(), timeperiod=20)
        df["SMA_50"] = talib.SMA(df["close"].to_numpy(), timeperiod=50)
        df["RSI"] = talib.RSI(df["close"].to_numpy(), timeperiod=14)
        df["ATR"] = talib.ATR(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), timeperiod=14)

        df["Volume_MA"] = talib.SMA(df["volume"].to_numpy(), timeperiod=20)  # Average volume
        df["RVOL"] = df["volume"] / df["Volume_MA"]  # Relative Volume

        # ADX (Trend Strength)
        df["ADX"] = talib.ADX(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), timeperiod=14)

        # Candlestick patterns
        df["Bullish_Engulfing"] = talib.CDLENGULFING(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Bearish_Engulfing"] = talib.CDLENGULFING(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Shooting_Star"] = talib.CDLSHOOTINGSTAR(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Hammer"] = talib.CDLHAMMER(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )
        df["Doji"] = talib.CDLDOJI(
            df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
        )

        return df

    def analyze_stock_intraday(self, symbol) -> pd.DataFrame | None:
        """Analyze a stock and return trading signals."""
        df = self.get_historical_data(symbol, "minute")
        if df is None or df.empty:
            return None
        return self.calculate_intraday_indicators(df)

    def analyze_stock_daily(self, symbol) -> pd.DataFrame | None:
        """Analyze a stock and return trading signals."""
        df = self.get_historical_data(symbol, "day")
        if df is None or df.empty:
            return None
        return self.calculate_daily_indicators(df)

    def calculate_technical_analysis_score(
        self, symbol: str, daily_df: pd.DataFrame, intraday_df: pd.DataFrame, side=None
    ) -> TradingSignals | None:
        """
        Calculate a technical analysis score using daily and intraday indicators.

        Incorporates RVOL, ATR, VWAP, and standard indicators like SMA, RSI, MACD, and
        Bollinger Bands.
        """

        latest_intraday = intraday_df.iloc[-2]
        latest_daily = daily_df.iloc[-2]
        prev_daily = daily_df.iloc[-2]

        if latest_intraday is None or latest_daily is None or prev_daily is None:
            return None

        price = intraday_df["close"].iloc[-1]

        # Initialize signals structure
        signals: TradingSignals = {
            "symbol": symbol,
            "price": price,
            "atr": latest_daily["ATR"],
            "rvol": latest_intraday["RVOL"],
            "signals": [],  # List of trading signals
            "raw_score": 0,  # Raw technical analysis score
            "score": 0,  # Normalized score (0-1)
            "momentum": 0,  # 24h momentum
            "raw_data_daily": daily_df,  # Raw data for debugging
            "raw_data_intraday": intraday_df,  # Raw data for debugging
        }

        ### --- DAILY INDICATORS --- ###
        # 1. Price vs. Daily Moving Averages
        sma20_daily = latest_daily["SMA_20"]
        sma50_daily = latest_daily["SMA_50"]

        if price > sma20_daily and price > sma50_daily:
            if sma20_daily > sma50_daily:
                signals["raw_score"] += 40  # Strong uptrend
            else:
                signals["raw_score"] += 10  # Weak uptrend
        else:
            if price < sma20_daily and price < sma50_daily:
                signals["raw_score"] -= 30  # Strong downtrend
                signals["signals"].append(
                    f"TA: Price below both MAs ({price} < {round(sma20_daily, 2)} & {round(sma50_daily, 2)})"
                )
            else:
                signals["raw_score"] -= 10  # Weak downtrend

        # 1. Momentum Analysis (24h change)
        prev_close = prev_daily["close"]
        price_24h_change = ((latest_daily["close"] / prev_close) - 1) * 100
        signals["momentum"] = price_24h_change

        if price_24h_change > 5:
            signals["raw_score"] += 50
        elif price_24h_change > 2:
            signals["raw_score"] += 30
        elif price_24h_change > 0:
            signals["raw_score"] += 10
        elif price_24h_change > -2:
            signals["raw_score"] -= 15
        else:
            signals["raw_score"] -= 30

        # 2. Daily RSI Analysis
        rsi_daily = latest_daily["RSI"]
        if rsi_daily < 30:  # Oversold
            if side != OrderSide.SELL:
                signals["raw_score"] += 30
            else:
                signals["raw_score"] -= 15
        elif rsi_daily > 70:  # Overbought
            if side != OrderSide.BUY:
                signals["raw_score"] -= 30
                signals["signals"].append(f"TA: Overbought RSI ({rsi_daily:.1f}) > 70")
            else:
                signals["raw_score"] += 15

        # 3. Daily ATR (Volatility Assessment)
        atr = latest_daily["ATR"]
        if (atr / price) * 100 > 3:  #  Threshold for bullish ATR
            signals["raw_score"] += 10  # High volatility = potential opportunities

        # 4. Relative Volume (RVOL)
        rvol_daily = latest_daily["RVOL"]
        if rvol_daily > 5:
            signals["raw_score"] += 40
        elif rvol_daily > 2:
            signals["raw_score"] += 25  # High relative volume = significant activity
        elif rvol_daily < 1.5:
            signals["raw_score"] -= 10
        elif rvol_daily < 0.7:
            signals["raw_score"] -= 20  # Low relative volume = lack of interest

        # 5. ADX Analysis (Trend Strength)
        adx = latest_daily["ADX"]
        if adx > 30:
            signals["raw_score"] += 30
        elif adx > 25:
            signals["raw_score"] += 20  # Strong trend
        elif adx < 20:
            signals["raw_score"] -= 20  # Weak trend

        # 6. Daily Candlestick Patterns
        if latest_daily["Bullish_Engulfing"] == 100 and adx > 25:
            signals["raw_score"] += 40  # Strong confirmation in a trending market
            signals["signals"].append("TA: Bullish Engulfing (Daily)")
        elif latest_daily["Bearish_Engulfing"] == -100 and adx > 25:
            signals["raw_score"] -= 30
            signals["signals"].append("TA: Bearish Engulfing (Daily)")

        if latest_daily["Hammer"] == 100 and rsi_daily < 30:
            signals["raw_score"] += 25  # Hammer confirmed by oversold RSI
            signals["signals"].append("TA: Hammer (Daily)")
        elif latest_daily["Shooting_Star"] == -100 and rsi_daily > 70:
            signals["raw_score"] -= 25  # Shooting Star confirmed by overbought RSI
            signals["signals"].append("TA: Shooting Star (Daily)")

        ### --- INTRADAY INDICATORS --- ###
        if latest_intraday is not None:
            # 1. Price vs. Intraday VWAP
            vwap = latest_intraday["vwap"]
            if price > vwap:
                signals["raw_score"] += 20  # Price above VWAP = bullish
            else:
                signals["raw_score"] -= 10  # Price below VWAP = bearish

            # 2. Intraday Candlestick Patterns
            if latest_intraday["Bullish_Engulfing"] == 100:
                signals["raw_score"] += 40  # Short-term bullish signal
                signals["signals"].append("TA: Bullish Engulfing (Intraday)")
            elif latest_intraday["Bearish_Engulfing"] == -100:
                signals["raw_score"] -= 15  # Short-term bearish signal
                signals["signals"].append("TA: Bearish Engulfing (Intraday)")
            if latest_intraday["Hammer"] == 100 and rsi_daily < 30:
                signals["raw_score"] += 25  # Hammer confirmed by oversold RSI
                signals["signals"].append("TA: Hammer (Intraday)")
            elif latest_intraday["Shooting_Star"] == -100 and rsi_daily > 70:
                signals["raw_score"] -= 25  # Shooting Star confirmed by overbought RSI
                signals["signals"].append("TA: Shooting Star (Intraday)")

            # 3. MACD Analysis (Intraday)
            macd = latest_intraday["MACD"]
            macd_signal = latest_intraday["MACD_Signal"]
            macd_diff = macd - macd_signal

            if abs(macd_diff) < 0.1:
                signals["score"] -= 10
            elif macd > macd_signal:
                if macd_diff > 0.5:
                    signals["score"] += 30
                else:
                    signals["score"] += 10
            else:
                if macd_diff < -0.2:
                    signals["score"] -= 30
                    signals["signals"].append(f"TA: Strong bearish MACD ({macd_diff:.2f} < -0.2)")
                else:
                    signals["score"] -= 10

            # 4. Bollinger Bands (Intraday)
            bb_lower = latest_intraday["BB_Lower"]
            bb_upper = latest_intraday["BB_Upper"]

            if price < bb_lower:
                signals["raw_score"] += 30  # Oversold (Buy signal)
            elif price > bb_upper:
                signals["raw_score"] -= 30  # Overbought (Sell signal)

            # 5. Volume spike based breakout
            if price > latest_daily["SMA_50"] and latest_intraday["volume"] > 2 * latest_daily["Volume_MA"]:
                signals["raw_score"] += 40
                signals["signals"].append(
                    f"TA: Breakout (Volume spike {latest_intraday['volume']:.0f} > 2 * {latest_daily['Volume_MA']:.0f})"
                )

            # 4. Relative Volume (RVOL)
            rvol_intraday = latest_intraday["RVOL"]
            if rvol_intraday > 5:
                signals["raw_score"] += 40
            elif rvol_intraday > 2:
                signals["raw_score"] += 25  # High relative volume = significant activity
            elif rvol_intraday < 1.5:
                signals["raw_score"] -= 10
                signals["signals"].append(f"TA: High RVOL missing ({rvol_intraday:.1f} < 1.5)")
            elif rvol_intraday < 0.7:
                signals["raw_score"] -= 20  # Low relative volume = lack of interest

        ### --- NORMALIZATION --- ###
        # Calculate min-max normalization
        min_raw_score, max_raw_score = -130, 130  # Define expected range
        signals["score"] = (signals["raw_score"] - min_raw_score) / (max_raw_score - min_raw_score)
        signals["score"] = max(0, min(1, signals["score"]))  # Clamp to [0, 1]

        logger.debug(
            f"\n{symbol} - Technical Analysis:\n"
            f"ATR: {signals['atr']:1f}, Score: {signals['score']}, Raw: {signals['raw_score']}, "
            f"Momentum: {signals['momentum']:1f}, Signals: {signals['signals']}"
        )
        return signals

    def analyze_stock(self, symbol: str) -> TradingSignals | None:
        try:
            intraday = self.analyze_stock_intraday(symbol)
            daily = self.analyze_stock_daily(symbol)

            if intraday is None or intraday.empty or daily is None or daily.empty:
                return None

            result = self.calculate_technical_analysis_score(symbol, daily, intraday)
            if result is None:
                return None
            return result

        except Exception as e:
            logger.error(f"Error analyzing stock {symbol}: {str(e)}", exc_info=True)
            return None

    def weak_technicals(self, signals: list[str], side: OrderSide) -> str | None:
        if side == OrderSide.BUY:
            weak_signal_checks = {
                "Price below both MAs",
                "Strong bearish MACD",
                "Shooting Star (Daily)",
                "Bearish Engulfing (Daily)",
                "Shooting Star (Intraday)",
                "Bearish Engulfing (Intraday)",
                "Overbought RSI",
                "High RVOL missing",
            }
        else:
            weak_signal_checks = {
                "Price below both MAs",
                "Strong bearish MACD",
                "Shooting Star (Daily)",
                "Bearish Engulfing (Daily)",
                "Shooting Star (Intraday)",
                "Bearish Engulfing (Intraday)",
                "Overbought RSI",
            }

        # Find signals that match any of the weak_signal_checks substrings
        weak_tech_signals = [signal for signal in signals if any(key in signal for key in weak_signal_checks)]

        if weak_tech_signals:
            return f"Unfavorable technicals: {', '.join(weak_tech_signals)}"
        return None

    def calculate_ta_threshold(self, vix_close, rel_vol, atr_pct):
        """Dynamically adjust technical score threshold based on VIX, volume, and volatility."""

        logger.debug(f"VIX: {vix_close:.1f}, Rel Vol: {rel_vol:.1f}, ATR %: {atr_pct:.2f}")
        if vix_close > 35:
            if rel_vol >= 3 and atr_pct < 0.08:  # Slightly raised ATR limit
                return 0.8  # Allow strong setups
            return 0.9  # Stricter threshold

        if vix_close >= 30:
            if rel_vol >= 2 and atr_pct < 0.10:  # Allow higher ATR in high VIX
                return 0.7
            return 0.75

        if vix_close >= 20:
            if rel_vol >= 1.5 and atr_pct < 0.12:  # More flexibility in calm markets
                return 0.6
            return 0.65

        # VIX < 20 (Calm market)
        return 0.5  # Allow all setups
