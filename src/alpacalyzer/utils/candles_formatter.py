from typing import Literal

import pandas as pd


def format_candles_to_markdown(
    df: pd.DataFrame,
    max_rows: int,
    granularity: Literal["day", "minute"] = "minute",
) -> str:
    """
    Convert a DataFrame of candle data to a markdown table format.

    Args:
        df: DataFrame with candle data (must have timestamp, open, high, low, close, volume)
        max_rows: Maximum number of rows to include (most recent candles)
        granularity: "day" for date-only, "minute" for full timestamp

    Returns:
        Markdown table string with formatted prices ($) and volumes (commas)
    """
    if df is None or df.empty:
        header = "| Date | Open | High | Low | Close | Volume |"
        separator = "|------|------|------|-----|-------|--------|"
        return f"{header}\n{separator}"

    df = df.tail(max_rows).copy()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if granularity == "day":
            df["Date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
        elif granularity == "minute":
            df["Date"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

    required_cols = ["Date", "open", "high", "low", "close", "volume"]
    df = df[[col for col in required_cols if col in df.columns]]

    df["Open"] = df["open"].apply(lambda x: f"${x:.2f}")
    df["High"] = df["high"].apply(lambda x: f"${x:.2f}")
    df["Low"] = df["low"].apply(lambda x: f"${x:.2f}")
    df["Close"] = df["close"].apply(lambda x: f"${x:.2f}")
    df["Volume"] = df["volume"].apply(lambda x: f"{int(x):,}")

    df = df.drop(columns=["open", "high", "low", "close", "volume"], errors="ignore")

    header = "| " + " | ".join(df.columns) + " |"
    separator = "|" + "|".join([" --- " for _ in df.columns]) + "|"

    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(v) for v in row.values) + " |")

    return "\n".join([header, separator] + rows)
