"""Technical analysis using pandas-ta (pure Python alternative to TA-Lib)."""

from datetime import UTC, datetime, timedelta
from typing import TypedDict, cast

import pandas as pd
from alpaca.data.enums import Adjustment
from alpaca.data.models import Bar, BarSet
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.enums import OrderSide

from alpacalyzer.trading.alpaca_client import get_market_status, history_client
from alpacalyzer.utils.cache_utils import timed_lru_cache
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


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
            now_utc = datetime.now(UTC)
            end = now_utc - timedelta(seconds=930)

            if request_type == "minute":
                start = end - timedelta(minutes=1440)
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame(5, TimeFrameUnit.Minute),  # type: ignore[arg-type]
                    start=start,
                    end=end,
                    adjustment=Adjustment.ALL,
                )
            else:
                start = end - timedelta(days=100)
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

                if get_market_status() == "open":
                    latest_bar_response = history_client.get_stock_latest_bar(StockLatestBarRequest(symbol_or_symbols=symbol))
                    latest_bar = cast(dict[str, Bar], latest_bar_response).get(symbol)
                    candles.append(latest_bar if latest_bar else candles[-1])
                else:
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
        """Calculate intraday technical indicators using pandas-ta."""
        # ATR
        df.ta.atr(length=30, append=True)
        df.rename(columns={"ATRr_30": "ATR"}, inplace=True)

        # MACD
        macd = df.ta.macd(append=False)
        df["MACD"] = macd["MACD_12_26_9"]
        df["MACD_Signal"] = macd["MACDs_12_26_9"]

        # Volume
        df["Volume_MA"] = df.ta.sma(close="volume", length=30, append=False)
        df["RVOL"] = df["volume"] / df["Volume_MA"]

        # Bollinger Bands
        bbands = df.ta.bbands(length=20, std=2, append=False)
        df["BB_Upper"] = bbands["BBU_20_2.0"]
        df["BB_Middle"] = bbands["BBM_20_2.0"]
        df["BB_Lower"] = bbands["BBL_20_2.0"]

        # Candlestick patterns using pandas-ta
        df.ta.cdl_pattern(name="engulfing", append=True)
        df.ta.cdl_pattern(name="shootingstar", append=True)
        df.ta.cdl_pattern(name="hammer", append=True)
        df.ta.cdl_pattern(name="doji", append=True)

        # Rename to match TA-Lib naming
        df["Bullish_Engulfing"] = df.get("CDL_ENGULFING", 0)
        df["Bearish_Engulfing"] = df.get("CDL_ENGULFING", 0)  # Same pattern, sign indicates direction
        df["Shooting_Star"] = df.get("CDL_SHOOTINGSTAR", 0)
        df["Hammer"] = df.get("CDL_HAMMER", 0)
        df["Doji"] = df.get("CDL_DOJI", 0)

        return df

    def calculate_daily_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate daily technical indicators using pandas-ta."""
        # Basic indicators
        df["SMA_20"] = df.ta.sma(length=20, append=False)
        df["SMA_50"] = df.ta.sma(length=50, append=False)
        df["RSI"] = df.ta.rsi(length=14, append=False)

        # ATR
        df.ta.atr(length=14, append=True)
        df.rename(columns={"ATRr_14": "ATR"}, inplace=True)

        # Volume
        df["Volume_MA"] = df.ta.sma(close="volume", length=20, append=False)
        df["RVOL"] = df["volume"] / df["Volume_MA"]

        # ADX (Trend Strength)
        adx = df.ta.adx(length=14, append=False)
        df["ADX"] = adx["ADX_14"]

        # Candlestick patterns
        df.ta.cdl_pattern(name="engulfing", append=True)
        df.ta.cdl_pattern(name="shootingstar", append=True)
        df.ta.cdl_pattern(name="hammer", append=True)
        df.ta.cdl_pattern(name="doji", append=True)

        # Rename to match TA-Lib naming
        df["Bullish_Engulfing"] = df.get("CDL_ENGULFING", 0)
        df["Bearish_Engulfing"] = df.get("CDL_ENGULFING", 0)
        df["Shooting_Star"] = df.get("CDL_SHOOTINGSTAR", 0)
        df["Hammer"] = df.get("CDL_HAMMER", 0)
        df["Doji"] = df.get("CDL_DOJI", 0)

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

    def calculate_technical_analysis_score(self, symbol: str, daily_df: pd.DataFrame, intraday_df: pd.DataFrame, target_side: str = "long") -> TradingSignals | None:
        """
        Calculate a technical analysis score using daily and intraday indicators.

        Incorporates RVOL, ATR, VWAP, and standard indicators like SMA, RSI, MACD, and
        Bollinger Bands.

        Args:
            symbol: The stock ticker symbol
            daily_df: DataFrame with daily candles and indicators
            intraday_df: DataFrame with intraday candles and indicators
            target_side: Either "long" or "short" - determines scoring direction
        """
        latest_intraday = intraday_df.iloc[-2]
        latest_daily = daily_df.iloc[-2]
        prev_daily = daily_df.iloc[-2]

        if latest_intraday is None or latest_daily is None or prev_daily is None:
            return None

        price = intraday_df["close"].iloc[-1]

        # Initialize signals structure
        signals = TradingSignals(
            {
                "symbol": symbol,
                "price": price,
                "atr": latest_daily["ATR"],
                "rvol": latest_intraday["RVOL"],
                "signals": [],
                "raw_score": 0,
                "score": 0,
                "momentum": 0,
                "raw_data_daily": daily_df,
                "raw_data_intraday": intraday_df,
            }
        )

        ### --- DAILY INDICATORS --- ###
        # 1. Price vs. Daily Moving Averages
        sma20_daily = latest_daily["SMA_20"]
        sma50_daily = latest_daily["SMA_50"]

        if target_side == "long":
            if price > sma20_daily and price > sma50_daily:
                if sma20_daily > sma50_daily:
                    signals["raw_score"] += 40
                    signals["signals"].append(f"TA: Price above both MAs ({price} > {round(sma20_daily, 2)} & {round(sma50_daily, 2)})")
                else:
                    signals["raw_score"] += 10
            else:
                if price < sma20_daily and price < sma50_daily:
                    signals["raw_score"] -= 30
                    signals["signals"].append(f"TA: Price below both MAs ({price} < {round(sma20_daily, 2)} & {round(sma50_daily, 2)})")
                else:
                    signals["raw_score"] -= 10
        else:
            if price < sma20_daily and price < sma50_daily:
                if sma20_daily < sma50_daily:
                    signals["raw_score"] += 40
                    signals["signals"].append(f"TA: Price below both MAs ({price} < {round(sma20_daily, 2)} & {round(sma50_daily, 2)})")
                else:
                    signals["raw_score"] += 10
            else:
                if price > sma20_daily and price > sma50_daily:
                    signals["raw_score"] -= 30
                    signals["signals"].append(f"TA: Price above both MAs ({price} > {round(sma20_daily, 2)} & {round(sma50_daily, 2)})")
                else:
                    signals["raw_score"] -= 10

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
        if target_side == "long":
            if rsi_daily < 30:
                signals["raw_score"] += 30
                signals["signals"].append(f"TA: Oversold RSI ({rsi_daily:.1f}) < 30")
            elif rsi_daily > 70:
                signals["raw_score"] -= 30
                signals["signals"].append(f"TA: Overbought RSI ({rsi_daily:.1f}) > 70")
        else:
            if rsi_daily > 70:
                signals["raw_score"] += 30
                signals["signals"].append(f"TA: Overbought RSI ({rsi_daily:.1f}) > 70")
            elif rsi_daily < 30:
                signals["raw_score"] -= 30
                signals["signals"].append(f"TA: Oversold RSI ({rsi_daily:.1f}) < 30")

        # 3. Daily ATR (Volatility Assessment)
        atr = latest_daily["ATR"]
        if (atr / price) * 100 > 3:
            signals["raw_score"] += 10

        # 4. Relative Volume (RVOL)
        rvol_daily = latest_daily["RVOL"]
        if rvol_daily > 5:
            signals["raw_score"] += 40
        elif rvol_daily > 2:
            signals["raw_score"] += 25
        elif rvol_daily < 1.5:
            signals["raw_score"] -= 10
        elif rvol_daily < 0.7:
            signals["raw_score"] -= 20

        # 5. ADX Analysis (Trend Strength)
        adx = latest_daily["ADX"]
        if adx > 30:
            signals["raw_score"] += 30
        elif adx > 25:
            signals["raw_score"] += 20
        elif adx < 20:
            signals["raw_score"] -= 20

        # 6. Daily Candlestick Patterns
        if target_side == "long":
            if latest_daily["Bullish_Engulfing"] == 100 and adx > 25:
                signals["raw_score"] += 40
                signals["signals"].append("TA: Bullish Engulfing (Daily)")
            elif latest_daily["Bearish_Engulfing"] == -100 and adx > 25:
                signals["raw_score"] -= 30
                signals["signals"].append("TA: Bearish Engulfing (Daily)")

            if latest_daily["Hammer"] == 100 and rsi_daily < 30:
                signals["raw_score"] += 25
                signals["signals"].append("TA: Hammer (Daily)")
            elif latest_daily["Shooting_Star"] == -100 and rsi_daily > 70:
                signals["raw_score"] -= 25
                signals["signals"].append("TA: Shooting Star (Daily)")
        else:
            if latest_daily["Bearish_Engulfing"] == -100 and adx > 25:
                signals["raw_score"] += 40
                signals["signals"].append("TA: Bearish Engulfing (Daily)")
            elif latest_daily["Bullish_Engulfing"] == 100 and adx > 25:
                signals["raw_score"] -= 30
                signals["signals"].append("TA: Bullish Engulfing (Daily)")

            if latest_daily["Shooting_Star"] == -100 and rsi_daily > 70:
                signals["raw_score"] += 25
                signals["signals"].append("TA: Shooting Star (Daily)")
            elif latest_daily["Hammer"] == 100 and rsi_daily < 30:
                signals["raw_score"] -= 25
                signals["signals"].append("TA: Hammer (Daily)")

        ### --- INTRADAY INDICATORS --- ###
        if latest_intraday is not None:
            # 1. Price vs. Intraday VWAP
            vwap = latest_intraday["vwap"]
            if target_side == "long":
                if price > vwap:
                    signals["raw_score"] += 20
                    signals["signals"].append(f"TA: Price above VWAP ({price} > {vwap:.2f})")
                else:
                    signals["raw_score"] -= 10
            else:
                if price < vwap:
                    signals["raw_score"] += 20
                    signals["signals"].append(f"TA: Price below VWAP ({price} < {vwap:.2f})")
                else:
                    signals["raw_score"] -= 10

            # 2. Intraday Candlestick Patterns
            if target_side == "long":
                if latest_intraday["Bullish_Engulfing"] == 100:
                    signals["raw_score"] += 40
                    signals["signals"].append("TA: Bullish Engulfing (Intraday)")
                elif latest_intraday["Bearish_Engulfing"] == -100:
                    signals["raw_score"] -= 15
                    signals["signals"].append("TA: Bearish Engulfing (Intraday)")
                if latest_intraday["Hammer"] == 100 and rsi_daily < 30:
                    signals["raw_score"] += 25
                    signals["signals"].append("TA: Hammer (Intraday)")
                elif latest_intraday["Shooting_Star"] == -100 and rsi_daily > 70:
                    signals["raw_score"] -= 25
                    signals["signals"].append("TA: Shooting Star (Intraday)")
            else:
                if latest_intraday["Bearish_Engulfing"] == -100:
                    signals["raw_score"] += 40
                    signals["signals"].append("TA: Bearish Engulfing (Intraday)")
                elif latest_intraday["Bullish_Engulfing"] == 100:
                    signals["raw_score"] -= 15
                    signals["signals"].append("TA: Bullish Engulfing (Intraday)")
                if latest_intraday["Shooting_Star"] == -100 and rsi_daily > 70:
                    signals["raw_score"] += 25
                    signals["signals"].append("TA: Shooting Star (Intraday)")
                elif latest_intraday["Hammer"] == 100 and rsi_daily < 30:
                    signals["raw_score"] -= 25
                    signals["signals"].append("TA: Hammer (Intraday)")

            # 3. MACD Analysis (Intraday)
            macd = latest_intraday["MACD"]
            macd_signal = latest_intraday["MACD_Signal"]
            macd_diff = macd - macd_signal

            if abs(macd_diff) < 0.1:
                signals["raw_score"] -= 10
            elif target_side == "long":
                if macd > macd_signal:
                    if macd_diff > 0.5:
                        signals["raw_score"] += 30
                        signals["signals"].append(f"TA: Strong bullish MACD ({macd_diff:.2f} > 0.5)")
                    else:
                        signals["raw_score"] += 10
                else:
                    if macd_diff < -0.2:
                        signals["raw_score"] -= 30
                        signals["signals"].append(f"TA: Strong bearish MACD ({macd_diff:.2f} < -0.2)")
                    else:
                        signals["raw_score"] -= 10
            else:
                if macd < macd_signal:
                    if macd_diff < -0.5:
                        signals["raw_score"] += 30
                        signals["signals"].append(f"TA: Strong bearish MACD ({macd_diff:.2f} < -0.5)")
                    else:
                        signals["raw_score"] += 10
                else:
                    if macd_diff > 0.2:
                        signals["raw_score"] -= 30
                        signals["signals"].append(f"TA: Strong bullish MACD ({macd_diff:.2f} > 0.2)")
                    else:
                        signals["raw_score"] -= 10

            # 4. Bollinger Bands (Intraday)
            bb_lower = latest_intraday["BB_Lower"]
            bb_upper = latest_intraday["BB_Upper"]

            if target_side == "long":
                if price < bb_lower:
                    signals["raw_score"] += 30
                    signals["signals"].append(f"TA: Price below Lower BB ({price} < {bb_lower:.2f})")
                elif price > bb_upper:
                    signals["raw_score"] -= 30
            else:
                if price > bb_upper:
                    signals["raw_score"] += 30
                    signals["signals"].append(f"TA: Price above Upper BB ({price} > {bb_upper:.2f})")
                elif price < bb_lower:
                    signals["raw_score"] -= 30

            # 5. Volume spike based breakout/breakdown
            if target_side == "long":
                if price > latest_daily["SMA_50"] and latest_intraday["volume"] > 2 * latest_daily["Volume_MA"]:
                    signals["raw_score"] += 40
                    signals["signals"].append(f"TA: Breakout (Volume spike {latest_intraday['volume']:.0f} > 2 * {latest_daily['Volume_MA']:.0f})")
            else:
                if price < latest_daily["SMA_50"] and latest_intraday["volume"] > 2 * latest_daily["Volume_MA"]:
                    signals["raw_score"] += 40
                    signals["signals"].append(f"TA: Breakdown (Volume spike {latest_intraday['volume']:.0f} > 2 * {latest_daily['Volume_MA']:.0f})")

            # 4. Relative Volume (RVOL)
            rvol_intraday = latest_intraday["RVOL"]
            if rvol_intraday > 5:
                signals["raw_score"] += 40
            elif rvol_intraday > 2:
                signals["raw_score"] += 25
            elif rvol_intraday < 1.5:
                signals["raw_score"] -= 10
                signals["signals"].append(f"TA: High RVOL missing ({rvol_intraday:.1f} < 1.5)")
            elif rvol_intraday < 0.7:
                signals["raw_score"] -= 20

            # 5. Trade Count Confirmation (high trade count = high conviction)
            # Compare current trade_count to average over lookback period
            trade_count = latest_intraday.get("trade_count")
            if trade_count is not None and intraday_df is not None and len(intraday_df) >= 20:
                avg_trade_count = intraday_df["trade_count"].iloc[-20:].mean()
                if avg_trade_count > 0:
                    trade_count_ratio = trade_count / avg_trade_count
                    if trade_count_ratio > 1.5:
                        # High trade count indicates strong conviction
                        signals["raw_score"] += 15
                        signals["signals"].append(f"TA: High trade count confirmation ({trade_count:.0f} > 1.5x avg {avg_trade_count:.0f})")

        ### --- NORMALIZATION --- ###
        min_raw_score, max_raw_score = -130, 180
        signals["score"] = (signals["raw_score"] - min_raw_score) / (max_raw_score - min_raw_score)
        signals["score"] = max(0, min(1, signals["score"]))

        logger.debug(
            f"\n{symbol} - Technical Analysis:\nATR: {signals['atr']:1f}, Score: {signals['score']}, Raw: {signals['raw_score']}, Momentum: {signals['momentum']:1f}, Signals: {signals['signals']}"
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
        else:  # OrderSide.SELL
            weak_signal_checks = {
                "Price above both MAs",
                "Oversold RSI",
                "Bullish Engulfing (Daily)",
                "Hammer (Daily)",
                "Price above VWAP",
                "Bullish Engulfing (Intraday)",
                "Hammer (Intraday)",
                "Strong bullish MACD",
                "Price below Lower BB",
            }

        weak_tech_signals = [signal for signal in signals if any(key in signal for key in weak_signal_checks)]

        if weak_tech_signals:
            return f"Unfavorable technicals: {', '.join(weak_tech_signals)}"
        return None

    def calculate_ta_threshold(self, vix_close, rel_vol, atr_pct):
        """
        Dynamically adjust technical score threshold based on VIX, volume, and volatility.

        Updated thresholds (reduced by 0.1-0.15 points) to increase entry conversion rate.
        """
        logger.debug(f"VIX: {vix_close:.1f}, Rel Vol: {rel_vol:.1f}, ATR %: {atr_pct:.2f}")
        if vix_close > 35:
            if rel_vol >= 3 and atr_pct < 0.08:
                return 0.65
            return 0.75

        if vix_close >= 30:
            if rel_vol >= 2 and atr_pct < 0.10:
                return 0.55
            return 0.6

        if vix_close >= 20:
            if rel_vol >= 1.5 and atr_pct < 0.12:
                return 0.45
            return 0.5

        # VIX < 20 (Calm market)
        return 0.35

    def calculate_short_candidate_score(self, symbol: str, daily_df: pd.DataFrame, intraday_df: pd.DataFrame) -> TradingSignals | None:
        """
        Calculate a technical analysis score specifically for short candidates.

        This is a convenience method that calls calculate_technical_analysis_score
        with target_side="short".
        """
        return self.calculate_technical_analysis_score(symbol, daily_df, intraday_df, target_side="short")
