from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from alpaca.data.enums import Adjustment
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.requests import GetCalendarRequest

from alpacalyzer.trading.alpaca_client import history_client, trading_client

EET = ZoneInfo("Europe/Helsinki")  # Server timezone (Finland)
ET = ZoneInfo("America/New_York")  # US market timezone


@dataclass
class PlanInfo:
    side: str | None = None  # "Long" or "Short"
    entry_point: float | None = None
    target_price: float | None = None
    stop_price: float | None = None  # Attempted parse if present
    raw: str | None = None


@dataclass
class DecisionRecord:
    ticker: str
    action: str  # BUY, SELL, SHORT, HOLD, EXIT_LONG, EXIT_SHORT
    quantity: int
    confidence: float | None
    decision_time_eet: datetime
    decision_time_et: datetime
    decision_time_utc: datetime
    plan: PlanInfo | None = None
    exit_pl_pct: float | None = None  # Parsed from "P/L: -0.30%" as decimal (-0.003)
    raw: str = ""


@dataclass
class DecisionOutcome:
    ticker: str
    action: str
    decision_time_eet: datetime
    ref_price: float | None
    eod_close: float | None
    pnl_long_close_pct: float | None
    pnl_short_close_pct: float | None
    mfe_long_pct: float | None
    mae_long_pct: float | None
    mfe_short_pct: float | None
    mae_short_pct: float | None
    exit_pl_pct: float | None = None
    suggested_action: str = "N/A"
    rationale: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecEvent:
    ticker: str
    side: str  # BUY or SELL
    status: str  # fill, partial_fill, canceled, rejected, etc.
    filled: int | None
    order_qty: int | None
    price: float | None
    order_id: str | None
    client_order_id: str | None
    time_eet: datetime
    time_et: datetime
    time_utc: datetime


@dataclass
class CompletedTradeExec:
    ticker: str
    side: str  # LONG or SHORT
    shares: int
    entry_avg: float
    exit_avg: float
    realized_pl: float
    realized_pl_per_share: float
    entry_time_eet: datetime
    exit_time_eet: datetime


@dataclass
class OpenPositionExec:
    ticker: str
    side: str  # LONG or SHORT
    shares: int
    avg_entry_price: float
    entry_time_eet: datetime


class EODPerformanceAnalyzer:
    def __init__(
        self,
        log_path: str = "logs/analytics_log.log",
        output_dir: str = "logs/eod",
        threshold_pct: float = 1.0,
        timeframe: str = "5Min",
    ) -> None:
        self.log_path = log_path
        self.output_dir = output_dir
        self.threshold = threshold_pct / 100.0
        self.timeframe_str = timeframe
        os.makedirs(self.output_dir, exist_ok=True)

        # Regex patterns (multiline entries compacted before matching)
        self._action_pat = re.compile(
            r"Ticker:\s*(?P<ticker>[A-Z]+)\s*,\s*Action:\s*(?P<action>BUY|SELL|SHORT|HOLD)\s*,\s*Quantity:\s*(?P<qty>\d+)\s*,\s*Confidence:\s*(?P<conf>[\d\.]+)%.*?\(DEBUG\s*-\s*(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\)",
            re.IGNORECASE,
        )
        self._plan_pat = re.compile(
            (
                r"Ticker:\s*(?P<ticker>[A-Z]+)\s*,\s*Trade Type:\s*(?P<trade_type>Long|Short)\s*,"
                r"\s*Quantity:\s*(?P<qty>\d+)\s*,\s*Entry Point:\s*(?P<entry>[\d\.]+)\s*,\s*Target Price:\s*"
                r"(?P<target>[\d\.]+).*?\(DEBUG\s*-\s*(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\)"
            ),
            re.IGNORECASE | re.DOTALL,
        )
        self._stop_pat = re.compile(r"stop\s+(?:below|at|=)\s*(?P<stop>[\d\.]+)", re.IGNORECASE)
        # Exit lines (positions exited)
        # Example:
        # Ticker: OPEN, Side: PositionSide.LONG, Exit Reason: ..., P/L: -0.30%, ... (DEBUG - 2025-08-25 22:30:12,987)
        self._exit_pat = re.compile(
            r"Ticker:\s*(?P<ticker>[A-Z]+)\s*,\s*Side:\s*(?:PositionSide\.)?(?P<side>LONG|SHORT).*?(?:P\s*/\s*L\s*:\s*(?P<pl>[+-]?\d+(?:[.,]\d+)?)%)?.*?\(DEBUG\s*-\s*(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\)",
            re.IGNORECASE | re.DOTALL,
        )
        # Execution lines from websocket listener
        self._exec_pat = re.compile(
            r"\[EXECUTION\]\s*Ticker:\s*(?P<ticker>[A-Z]+)\s*,\s*Side:\s*(?P<side>BUY|SELL)\s*,\s*(?:Cum:\s*(?P<filled>\d+)(?:/(?P<qty>\d+))?\s*@\s*(?P<price>[\d\.NA]+)|Px:\s*(?P<px_only>[\d\.]+))?\s*,\s*OrderType:\s*(?P<otype>[A-Za-z]+|N/A)\s*,\s*OrderId:\s*(?P<order_id>[^,]+)\s*,\s*ClientOrderId:\s*(?P<client_id>[^,]+)\s*,\s*Status:\s*(?P<status>\w+).*?\(DEBUG\s*-\s*(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\)",
            re.IGNORECASE | re.DOTALL,
        )
        # Storage for last parsed execution events (per parse run)
        self._last_exec_events: list[ExecEvent] = []

    def _parse_ts_eet(self, ts: str) -> datetime:
        # Example: "2025-08-25 21:42:29,208"
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S,%f")
        return dt.replace(tzinfo=EET)

    def _to_et(self, t: datetime) -> datetime:
        return t.astimezone(ET)

    def _to_utc(self, t: datetime) -> datetime:
        return t.astimezone(UTC)

    def parse_event_line(self, line: str) -> dict | None:
        """Parse a JSON event line."""
        if not line.strip().startswith("{"):
            return None

        try:
            event_data = json.loads(line)
            if not isinstance(event_data, dict):
                return None
            if "event_type" not in event_data:
                return None
            return event_data
        except json.JSONDecodeError:
            return None

    def load_events(self, log_path: str) -> list[dict]:
        """Load all events from a log file."""
        events = []
        if not os.path.exists(log_path):
            return events

        with open(log_path) as f:
            for line in f:
                event = self.parse_event_line(line)
                if event:
                    events.append(event)
        return events

    def _detect_log_format(self, log_path: str) -> str:
        """Detect if log file uses JSON events or legacy format."""
        if not os.path.exists(log_path):
            return "legacy"

        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("{"):
                    if '"event_type"' in line:
                        return "json"
                if " (DEBUG - " in line:
                    return "legacy"
        return "legacy"

    def _parse_events_to_decision_records(self, events: list[dict], target_date_eet: date | None = None) -> tuple[list[DecisionRecord], list[ExecEvent]]:
        """Convert JSON events to DecisionRecord and ExecEvent."""
        decisions: list[DecisionRecord] = []
        exec_events: list[ExecEvent] = []

        for event in events:
            event_type = event.get("event_type")
            if not event_type:
                continue

            ts_str = event.get("timestamp", "")
            ticker = event.get("ticker", "").upper()
            side = event.get("side", "").upper()

            try:
                ts_utc = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

            ts_eet = ts_utc.astimezone(EET)
            ts_et = ts_utc.astimezone(ET)

            if target_date_eet and ts_eet.date() != target_date_eet:
                continue

            if event_type == "ENTRY_TRIGGERED":
                action = "BUY" if side == "LONG" or side == "BUY" else "SHORT"
                quantity = event.get("quantity", 0)
                entry_price = event.get("entry_price", 0.0)
                target_price = event.get("target", 0.0)
                stop_loss = event.get("stop_loss", 0.0)
                confidence = 0.8
                plan = PlanInfo(
                    side=action,
                    entry_point=entry_price,
                    target_price=target_price,
                    stop_price=stop_loss if stop_loss > 0 else None,
                    raw=json.dumps(event),
                )
                decisions.append(
                    DecisionRecord(
                        ticker=ticker,
                        action=action,
                        quantity=quantity,
                        confidence=confidence,
                        decision_time_eet=ts_eet,
                        decision_time_et=ts_et,
                        decision_time_utc=ts_utc,
                        plan=plan,
                        raw=json.dumps(event),
                    )
                )

            elif event_type == "EXIT_TRIGGERED":
                exit_side = side
                action = f"EXIT_{exit_side}"
                pnl_pct = event.get("pnl_pct", 0.0)
                decisions.append(
                    DecisionRecord(
                        ticker=ticker,
                        action=action,
                        quantity=0,
                        confidence=None,
                        decision_time_eet=ts_eet,
                        decision_time_et=ts_et,
                        decision_time_utc=ts_utc,
                        plan=None,
                        exit_pl_pct=pnl_pct,
                        raw=json.dumps(event),
                    )
                )

            elif event_type == "ORDER_FILLED":
                quantity = event.get("quantity", 0)
                filled_qty = event.get("filled_qty", 0)
                avg_price = event.get("avg_price", 0.0)
                order_id = event.get("order_id", "")
                client_order_id = event.get("client_order_id", "")
                exec_events.append(
                    ExecEvent(
                        ticker=ticker,
                        side=side,
                        status="fill",
                        filled=filled_qty,
                        order_qty=quantity,
                        price=avg_price,
                        order_id=order_id,
                        client_order_id=client_order_id,
                        time_eet=ts_eet,
                        time_et=ts_et,
                        time_utc=ts_utc,
                    )
                )

            elif event_type == "POSITION_CLOSED":
                exit_side = side.upper()
                action = f"EXIT_{exit_side}"
                pnl_pct = event.get("pnl_pct", 0.0)
                decisions.append(
                    DecisionRecord(
                        ticker=ticker,
                        action=action,
                        quantity=0,
                        confidence=None,
                        decision_time_eet=ts_eet,
                        decision_time_et=ts_et,
                        decision_time_utc=ts_utc,
                        plan=None,
                        exit_pl_pct=pnl_pct,
                        raw=json.dumps(event),
                    )
                )

        return decisions, exec_events

    def parse_log(self, target_date_eet: date | None = None) -> list[DecisionRecord]:
        """
        Parse analytics log into decision records for target_date (EET).

        Supports both JSON event format and legacy regex-based parsing.
        """
        if not os.path.exists(self.log_path):
            return []

        log_format = self._detect_log_format(self.log_path)

        if log_format == "json":
            events = self.load_events(self.log_path)
            decisions, exec_events_out = self._parse_events_to_decision_records(events, target_date_eet)
            self._last_exec_events = exec_events_out
            decisions.sort(key=lambda d: d.decision_time_eet)
            return decisions

        if not os.path.exists(self.log_path):
            return []

        # Read and accumulate entries
        entries: list[str] = []
        buf: list[str] = []
        with open(self.log_path, encoding="utf-8") as f:
            for line in f:
                s = line.rstrip("\n")
                buf.append(s)
                if " (DEBUG - " in s:
                    # flush buffer
                    combined = " ".join(x.strip() for x in buf if x.strip())
                    entries.append(combined)
                    buf = []
        # Flush any dangling buffer if has a DEBUG marker
        if buf and any(" (DEBUG - " in x for x in buf):
            combined = " ".join(x.strip() for x in buf if x.strip())
            entries.append(combined)

        # First collect plan entries by ticker+time to later associate
        plan_by_key: dict[tuple[str, datetime], PlanInfo] = {}
        for e in entries:
            m = self._plan_pat.search(e)
            if not m:
                continue
            ticker = m.group("ticker").upper()
            trade_type = m.group("trade_type")
            qty = int(m.group("qty"))
            entry = float(m.group("entry"))
            target = float(m.group("target"))
            ts_eet = self._parse_ts_eet(m.group("ts"))
            plan = PlanInfo(side=trade_type, entry_point=entry, target_price=target, raw=e)
            if stop_m := self._stop_pat.search(e):
                try:
                    plan.stop_price = float(stop_m.group("stop"))
                except Exception:  # nosec B110 - Silent failure is intentional for malformed data
                    pass
            plan_by_key[(ticker, ts_eet)] = plan

        # Then parse decisions (actions and exits)
        decisions: list[DecisionRecord] = []
        for e in entries:
            # Action decision
            m = self._action_pat.search(e)
            if m:
                ticker = m.group("ticker").upper()
                action = m.group("action").upper()
                qty = int(m.group("qty"))
                conf = float(m.group("conf")) if m.group("conf") else None
                ts_eet = self._parse_ts_eet(m.group("ts"))

                if target_date_eet and ts_eet.date() != target_date_eet:
                    continue

                # Associate the nearest plan within ±2 minutes for same ticker
                associated_plan: PlanInfo | None = None
                if plan_by_key:
                    min_delta: timedelta | None = None
                    for (pticker, pts), plan in plan_by_key.items():
                        if pticker != ticker:
                            continue
                        delta = abs(ts_eet - pts)
                        if delta <= timedelta(minutes=2) and (min_delta is None or delta < min_delta):
                            min_delta = delta
                            associated_plan = plan

                t_et = self._to_et(ts_eet)
                t_utc = self._to_utc(ts_eet)
                decisions.append(
                    DecisionRecord(
                        ticker=ticker,
                        action=action,
                        quantity=qty,
                        confidence=conf,
                        decision_time_eet=ts_eet,
                        decision_time_et=t_et,
                        decision_time_utc=t_utc,
                        plan=associated_plan,
                        raw=e,
                    )
                )
                continue

            # Exit decision
            mx = self._exit_pat.search(e)
            if mx:
                ticker = mx.group("ticker").upper()
                side = mx.group("side").upper()  # LONG or SHORT
                ts_eet = self._parse_ts_eet(mx.group("ts"))
                # Parse optional P/L percent
                exit_pl_pct: float | None = None
                try:
                    pl_str = mx.groupdict().get("pl")
                    if pl_str is not None:
                        exit_pl_pct = float(pl_str.replace(",", ".")) / 100.0
                except Exception:
                    exit_pl_pct = None

                if target_date_eet and ts_eet.date() != target_date_eet:
                    continue

                t_et = self._to_et(ts_eet)
                t_utc = self._to_utc(ts_eet)
                decisions.append(
                    DecisionRecord(
                        ticker=ticker,
                        action=f"EXIT_{side}",
                        quantity=0,
                        confidence=None,
                        decision_time_eet=ts_eet,
                        decision_time_et=t_et,
                        decision_time_utc=t_utc,
                        plan=None,
                        exit_pl_pct=exit_pl_pct,
                        raw=e,
                    )
                )

        # Parse EXECUTION lines from websocket to reconstruct actual fills/cancels
        exec_events: list[ExecEvent] = []
        for e in entries:
            mx = self._exec_pat.search(e)
            if not mx:
                continue
            ticker = mx.group("ticker").upper()
            side = mx.group("side").upper()
            status = (mx.group("status") or "").lower()
            # Parse timestamp in EET
            ts_eet = self._parse_ts_eet(mx.group("ts"))
            if target_date_eet and ts_eet.date() != target_date_eet:
                continue

            # Filled quantities and prices
            def _to_int_safe(val: str | None) -> int | None:
                try:
                    return int(val) if val is not None else None
                except Exception:
                    try:
                        return int(float(val)) if val is not None else None
                    except Exception:
                        return None

            def _to_float_safe(val: str | None) -> float | None:
                try:
                    if val is None:
                        return None
                    if val.upper() == "N/A":
                        return None
                    return float(val)
                except Exception:
                    return None

            filled = _to_int_safe(mx.groupdict().get("filled"))
            order_qty = _to_int_safe(mx.groupdict().get("qty"))
            price = _to_float_safe(mx.groupdict().get("price") or mx.groupdict().get("px_only"))
            order_id = mx.groupdict().get("order_id")
            client_order_id = mx.groupdict().get("client_id")

            exec_events.append(
                ExecEvent(
                    ticker=ticker,
                    side=side,
                    status=status,
                    filled=filled,
                    order_qty=order_qty,
                    price=price,
                    order_id=order_id,
                    client_order_id=client_order_id,
                    time_eet=ts_eet,
                    time_et=self._to_et(ts_eet),
                    time_utc=self._to_utc(ts_eet),
                )
            )

        # Stash for report building
        self._last_exec_events = exec_events

        # Preserve chronological order (already preserved by log scanning); optional sort by time if needed:
        decisions.sort(key=lambda d: d.decision_time_eet)
        return decisions

    def _timeframe_to_tf(self) -> TimeFrame:
        tf = self.timeframe_str.lower()
        if tf in ("1min", "1m", "minute"):
            return TimeFrame(1, TimeFrameUnit.Minute)  # type: ignore[arg-type]
        if tf in ("5min", "5m"):
            return TimeFrame(5, TimeFrameUnit.Minute)  # type: ignore[arg-type]
        if tf in ("15min", "15m"):
            return TimeFrame(15, TimeFrameUnit.Minute)  # type: ignore[arg-type]
        if tf in ("1day", "1d", "day", "daily", "d"):
            return TimeFrame.Day
        # default to 5Min
        return TimeFrame(5, TimeFrameUnit.Minute)  # type: ignore[arg-type]

    def _get_session_close_utc_for_et_date(self, et_dt: datetime) -> datetime | None:
        # Use Alpaca calendar for the ET date
        et_day = et_dt.date()
        req = GetCalendarRequest(start=et_day, end=et_day)
        try:
            calendars = trading_client.get_calendar(req)
            if not calendars:
                return None
            # Alpaca returns naive ET times; attach ET tz then convert to UTC
            close_naive = calendars[0].close
            close_et = close_naive.replace(tzinfo=ET)
            return close_et.astimezone(UTC)
        except Exception:
            return None

    def _fetch_bars_range(self, symbol: str, start_utc: datetime, end_utc: datetime) -> pd.DataFrame | None:
        try:
            tf = self._timeframe_to_tf()
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start_utc,
                end=end_utc,
                adjustment=Adjustment.ALL,
            )
            bars = history_client.get_stock_bars(req)
            data = getattr(bars, "data", None)
            if not data:
                return None
            series = data.get(symbol)
            if not series:
                return None
            df = pd.DataFrame([bar.model_dump() for bar in series])
            if df.empty:
                return None
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
            # Ensure numeric
            for col in ("open", "high", "low", "close", "volume", "trade_count", "vwap"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            return df
        except Exception:
            return None

    def _select_ref_bar(self, df: pd.DataFrame, decision_ts_utc: datetime) -> pd.Timestamp | None:
        # First bar with index >= decision_ts_utc
        idx: pd.Index = df.index  # type: ignore
        pos = idx.searchsorted(pd.Timestamp(decision_ts_utc))
        if pos < len(idx):
            return idx[pos]
        return None

    def evaluate_decision(self, d: DecisionRecord) -> DecisionOutcome:
        warnings: list[str] = []

        close_utc = self._get_session_close_utc_for_et_date(d.decision_time_et)
        if close_utc is None:
            warnings.append("No US session close available for decision date")
            return DecisionOutcome(
                ticker=d.ticker,
                action=d.action,
                decision_time_eet=d.decision_time_eet,
                ref_price=None,
                eod_close=None,
                pnl_long_close_pct=None,
                pnl_short_close_pct=None,
                mfe_long_pct=None,
                mae_long_pct=None,
                mfe_short_pct=None,
                mae_short_pct=None,
                suggested_action="N/A",
                rationale="Market calendar not available",
                warnings=warnings,
            )

        # If the decision occurred after the US regular-session close, skip evaluation to avoid empty bar ranges.
        close_et = close_utc.astimezone(ET)
        if d.decision_time_et >= close_et:
            return DecisionOutcome(
                ticker=d.ticker,
                action=d.action,
                decision_time_eet=d.decision_time_eet,
                ref_price=None,
                eod_close=None,
                pnl_long_close_pct=None,
                pnl_short_close_pct=None,
                mfe_long_pct=None,
                mae_long_pct=None,
                mfe_short_pct=None,
                mae_short_pct=None,
                suggested_action="N/A",
                rationale="Decision occurred after session close; skipping evaluation for same-session horizon.",
                warnings=[],
            )

        # Small guard to include the last bar
        start_utc = d.decision_time_utc - timedelta(seconds=1)
        end_utc = close_utc + timedelta(seconds=1)

        df = self._fetch_bars_range(d.ticker, start_utc, end_utc)
        if df is None or df.empty:
            warnings.append("No bars fetched for decision horizon")
            return DecisionOutcome(
                ticker=d.ticker,
                action=d.action,
                decision_time_eet=d.decision_time_eet,
                ref_price=None,
                eod_close=None,
                pnl_long_close_pct=None,
                pnl_short_close_pct=None,
                mfe_long_pct=None,
                mae_long_pct=None,
                mfe_short_pct=None,
                mae_short_pct=None,
                suggested_action="N/A",
                rationale="No bars available",
                warnings=warnings,
            )

        ref_idx = self._select_ref_bar(df, d.decision_time_utc)
        if ref_idx is None:
            warnings.append("No reference bar at/after decision time")
            return DecisionOutcome(
                ticker=d.ticker,
                action=d.action,
                decision_time_eet=d.decision_time_eet,
                ref_price=None,
                eod_close=None,
                pnl_long_close_pct=None,
                pnl_short_close_pct=None,
                mfe_long_pct=None,
                mae_long_pct=None,
                mfe_short_pct=None,
                mae_short_pct=None,
                suggested_action="N/A",
                rationale="No reference bar",
                warnings=warnings,
            )

        # Slice from ref bar to last available (EOD)
        window = df.loc[ref_idx:]
        if window.empty:
            warnings.append("Empty window after reference bar")
            return DecisionOutcome(
                ticker=d.ticker,
                action=d.action,
                decision_time_eet=d.decision_time_eet,
                ref_price=None,
                eod_close=None,
                pnl_long_close_pct=None,
                pnl_short_close_pct=None,
                mfe_long_pct=None,
                mae_long_pct=None,
                mfe_short_pct=None,
                mae_short_pct=None,
                suggested_action="N/A",
                rationale="Empty evaluation window",
                warnings=warnings,
            )

        ref_price = float(window.iloc[0]["open"])
        eod_close = float(window.iloc[-1]["close"])
        high_max = float(window["high"].max())
        low_min = float(window["low"].min())

        pnl_long_close = (eod_close - ref_price) / ref_price
        pnl_short_close = (ref_price - eod_close) / ref_price

        mfe_long = (high_max - ref_price) / ref_price
        mae_long = (low_min - ref_price) / ref_price  # negative or zero
        mfe_short = (ref_price - low_min) / ref_price
        mae_short = (ref_price - high_max) / ref_price  # negative or zero

        suggested, rationale = self._score(d.action, pnl_long_close, pnl_short_close)

        # Add exit P/L information if present; fallback-parse from raw if missing
        exit_pl = d.exit_pl_pct
        if d.action.startswith("EXIT"):
            if exit_pl is None and d.raw:
                m = re.search(r"P\s*/\s*L\s*:\s*([+-]?\d+(?:[.,]\d+)?)%", d.raw, re.IGNORECASE)
                if m:
                    try:
                        exit_pl = float(m.group(1).replace(",", ".")) / 100.0
                    except Exception:
                        exit_pl = None
            if exit_pl is not None:
                rationale = (rationale + f" Exit P/L at time of exit: {exit_pl * 100:.2f}%.").strip()

        # Enrich rationale if plan suggests target hit within the path
        if d.plan and d.plan.target_price:
            try:
                if (window["high"] >= d.plan.target_price).any() and d.action in ("BUY", "HOLD"):
                    rationale += " Target was reachable based on intraday highs."
                if d.plan.stop_price is not None and (window["low"] <= d.plan.stop_price).any():
                    rationale += " Stop would have been hit intraday."
            except Exception:  # nosec B110 - Silent failure is intentional for missing intraday data
                pass

        return DecisionOutcome(
            ticker=d.ticker,
            action=d.action,
            decision_time_eet=d.decision_time_eet,
            ref_price=ref_price,
            eod_close=eod_close,
            pnl_long_close_pct=pnl_long_close,
            pnl_short_close_pct=pnl_short_close,
            mfe_long_pct=mfe_long,
            mae_long_pct=mae_long,
            mfe_short_pct=mfe_short,
            mae_short_pct=mae_short,
            exit_pl_pct=exit_pl,
            suggested_action=suggested,
            rationale=rationale.strip(),
            warnings=warnings,
        )

    def _build_execution_summary(self, exec_events: list[ExecEvent]) -> tuple[list[CompletedTradeExec], list[OpenPositionExec], float]:
        """
        Build completed round-trips and open position snapshots from execution events.

        Rules:
        - We process only 'fill' events to avoid double counting partials.
        - Long-only flow supported; SHORT flow is handled generically if encountered.
        - FIFO matching for open lots to compute open position snapshot.
        - A 'CompletedTradeExec' is emitted when net position returns to zero.
        """
        completed: list[CompletedTradeExec] = []
        open_positions: list[OpenPositionExec] = []
        realized_total = 0.0

        # Group by ticker and sort by time
        events_by_ticker: dict[str, list[ExecEvent]] = {}
        for ev in exec_events:
            if ev.status not in {"fill", "partial_fill"}:
                continue
            events_by_ticker.setdefault(ev.ticker, []).append(ev)
        for t in events_by_ticker:
            events_by_ticker[t].sort(key=lambda x: x.time_eet)

        for ticker, events in events_by_ticker.items():
            net = 0  # positive = long, negative = short
            side_mode: str | None = None  # "LONG" or "SHORT"
            # Trade accumulators between flat->flat
            first_entry_time: datetime | None = None
            last_exit_time: datetime | None = None
            entry_qty_sum = 0
            entry_val_sum = 0.0
            exit_qty_sum = 0
            exit_val_sum = 0.0

            # FIFO lots for open inventory snapshot
            lots: list[tuple[int, float, datetime]] = []  # (qty, price, time_eet)

            for ev in events:
                qty = ev.filled or ev.order_qty or 0
                px = ev.price
                if qty <= 0 or px is None:
                    continue

                if ev.side == "BUY":
                    if net == 0:
                        side_mode = "LONG"
                        first_entry_time = ev.time_eet
                        # reset accumulators at start of a new trade window
                        entry_qty_sum = 0
                        entry_val_sum = 0.0
                        exit_qty_sum = 0
                        exit_val_sum = 0.0
                    # record entries
                    entry_qty_sum += qty
                    entry_val_sum += qty * px
                    lots.append((qty, px, ev.time_eet))
                    net += qty

                elif ev.side == "SELL":
                    # Short initiation from flat (rare in this system)
                    if net == 0:
                        side_mode = "SHORT"
                        first_entry_time = ev.time_eet
                        entry_qty_sum = 0
                        entry_val_sum = 0.0
                        exit_qty_sum = 0
                        exit_val_sum = 0.0

                    if net > 0:
                        # Closing a long: match against lots FIFO
                        remaining = qty
                        while remaining > 0 and lots:
                            lot_qty, lot_px, lot_time = lots[0]
                            matched = min(lot_qty, remaining)
                            exit_qty_sum += matched
                            exit_val_sum += matched * px
                            lot_qty -= matched
                            remaining -= matched
                            if lot_qty == 0:
                                lots.pop(0)
                            else:
                                lots[0] = (lot_qty, lot_px, lot_time)
                        net -= qty
                        last_exit_time = ev.time_eet

                        if net <= 0:
                            # Trade round-trip complete (flattened or flipped)
                            # Clamp to non-negative
                            net = max(net, 0)
                            shares = max(exit_qty_sum, 0)
                            if shares > 0 and entry_qty_sum > 0:
                                entry_avg = entry_val_sum / entry_qty_sum
                                exit_avg = exit_val_sum / exit_qty_sum if exit_qty_sum > 0 else entry_avg
                                realized = (exit_avg - entry_avg) * shares
                                completed.append(
                                    CompletedTradeExec(
                                        ticker=ticker,
                                        side=side_mode or "LONG",
                                        shares=shares,
                                        entry_avg=entry_avg,
                                        exit_avg=exit_avg,
                                        realized_pl=realized,
                                        realized_pl_per_share=(exit_avg - entry_avg),
                                        entry_time_eet=first_entry_time or ev.time_eet,
                                        exit_time_eet=last_exit_time or ev.time_eet,
                                    )
                                )
                                realized_total += realized
                            # reset accumulators and inventory
                            side_mode = None
                            first_entry_time = None
                            last_exit_time = None
                            entry_qty_sum = 0
                            entry_val_sum = 0.0
                            exit_qty_sum = 0
                            exit_val_sum = 0.0
                            lots = []
                    else:
                        # Increasing a short; not typical here, but maintain state
                        net -= qty
                        # For shorts, treat SELL as "entry" and BUY as "exit" (mirror logic)
                        if side_mode != "SHORT":
                            side_mode = "SHORT"
                            first_entry_time = ev.time_eet
                        entry_qty_sum += qty
                        entry_val_sum += qty * px

            # If any open long position remains (net > 0), capture snapshot
            if net > 0 and lots:
                total_shares = sum(q for q, _, _ in lots)
                total_val = sum(q * p for q, p, _ in lots)
                avg_px = total_val / total_shares if total_shares else 0.0
                open_positions.append(
                    OpenPositionExec(
                        ticker=ticker,
                        side="LONG",
                        shares=total_shares,
                        avg_entry_price=avg_px,
                        entry_time_eet=lots[0][2],
                    )
                )

        return completed, open_positions, realized_total

    def _build_position_timeline(self, events: list[dict]) -> list[tuple[str, list[str]]]:
        """Build position timeline from events."""
        timeline: dict[str, list[str]] = {}
        for event in events:
            ticker = event.get("ticker", "").upper()
            if not ticker:
                continue

            event_type = event.get("event_type", "")
            timestamp = event.get("timestamp", "")
            quantity = event.get("quantity", 0)
            price = event.get("entry_price") or event.get("exit_price") or event.get("avg_price", 0)
            reason = event.get("reason", "")
            strategy = event.get("strategy", "")

            if ticker not in timeline:
                timeline[ticker] = []

            line_parts = [f"{timestamp}", f"{event_type}"]
            if event_type == "ENTRY_TRIGGERED":
                line_parts.extend([f"{quantity} shares @ ${price:.2f}", f"({strategy})"])
            elif event_type == "EXIT_TRIGGERED":
                pnl = event.get("pnl", 0)
                pnl_pct = event.get("pnl_pct", 0)
                line_parts.append(f"{quantity} shares @ ${price:.2f}, P/L: ${pnl:.2f} ({pnl_pct * 100:.2f}%)")
            elif event_type == "ORDER_FILLED":
                line_parts.extend([f"{quantity} shares @ ${price:.2f}"])

            if reason:
                line_parts.append(reason)

            timeline[ticker].append(" | ".join(str(p) for p in line_parts))

        return sorted(timeline.items(), key=lambda x: x[0])

    def _build_strategy_performance(self, events: list[dict]) -> dict[str, dict]:
        """Build strategy performance metrics."""
        strategy_data: dict[str, dict] = {}

        for event in events:
            strategy = event.get("strategy", "unknown")
            event_type = event.get("event_type", "")

            if strategy not in strategy_data:
                strategy_data[strategy] = {
                    "entries": 0,
                    "exits": 0,
                    "wins": 0,
                    "total_pnl": 0.0,
                    "hold_times": [],
                }

            if event_type == "ENTRY_TRIGGERED":
                strategy_data[strategy]["entries"] += 1
            elif event_type == "EXIT_TRIGGERED":
                strategy_data[strategy]["exits"] += 1
                pnl = event.get("pnl", 0)
                strategy_data[strategy]["total_pnl"] += pnl
                if pnl > 0:
                    strategy_data[strategy]["wins"] += 1
                hold_duration = event.get("hold_duration_hours", 0)
                if hold_duration > 0:
                    strategy_data[strategy]["hold_times"].append(hold_duration)

        return strategy_data

    def _build_event_summary(self, events: list[dict]) -> dict[str, int]:
        """Build event type summary."""
        summary: dict[str, int] = {}
        for event in events:
            event_type = event.get("event_type", "UNKNOWN")
            summary[event_type] = summary.get(event_type, 0) + 1
        return summary

    def _score(self, action: str, pnl_long_close: float, pnl_short_close: float) -> tuple[str, str]:
        thr = self.threshold

        # EXIT evaluation
        if action == "EXIT_LONG":
            # If market rose after exit by threshold -> exit too early
            if pnl_long_close >= thr:
                return (
                    "HOLD_LONG",
                    f"Exit too early: additional +{pnl_long_close * 100:.2f}% to close (≥ {thr * 100:.2f}%).",
                )
            # If market fell by threshold after exit -> good exit
            if (-pnl_long_close) >= thr:
                return "EXIT_OK", f"Long exit validated: price fell {(-pnl_long_close) * 100:.2f}% after exit."
            return "EXIT_OK", "Long exit neutral by close (< threshold move)."

        if action == "EXIT_SHORT":
            # If market fell after exit by threshold -> exit too early (should have held short)
            if pnl_short_close >= thr:
                return (
                    "HOLD_SHORT",
                    f"Exit too early: additional +{pnl_short_close * 100:.2f}% to close (≥ {thr * 100:.2f}%).",
                )
            # If market rose by threshold after exit -> good exit
            if (-pnl_short_close) >= thr:
                return "EXIT_OK", f"Short exit validated: price rose {(-pnl_short_close) * 100:.2f}% after exit."
            return "EXIT_OK", "Short exit neutral by close (< threshold move)."

        # HOLD logic: if one side achieves threshold and also outperforms the other side
        if action == "HOLD":
            if pnl_long_close >= thr and pnl_long_close >= pnl_short_close:
                return "BUY", f"HOLD missed long opportunity (+{pnl_long_close * 100:.2f}% >= {thr * 100:.2f}%)."
            if pnl_short_close >= thr and pnl_short_close > pnl_long_close:
                return "SHORT", f"HOLD missed short opportunity (+{pnl_short_close * 100:.2f}% >= {thr * 100:.2f}%)."
            return "HOLD", "HOLD validated (neither side exceeded threshold by close)."

        # BUY/LONG logic
        if action in ("BUY", "LONG"):
            diff = pnl_short_close - pnl_long_close
            if diff >= thr:
                return "SHORT", f"Direction error: short outperformed long by {diff * 100:.2f}% (≥ {thr * 100:.2f}%)."
            if abs(pnl_long_close) < thr:
                return "BUY", "Neutral outcome by close (< threshold)."
            return "BUY", "Buy validated by close."

        # SHORT logic
        if action == "SHORT":
            diff = pnl_long_close - pnl_short_close
            if diff >= thr:
                return "BUY", f"Direction error: long outperformed short by {diff * 100:.2f}% (≥ {thr * 100:.2f}%)."
            if abs(pnl_short_close) < thr:
                return "SHORT", "Neutral outcome by close (< threshold)."
            return "SHORT", "Short validated by close."

        # SELL or unknown: default to neutral
        return action, "Action not evaluated (SELL/unknown)."

    def _today_eet(self) -> date:
        return datetime.now(tz=EET).date()

    def _latest_date_in_log(self) -> date | None:
        """Return the latest EET date that has at least one decision in the log."""
        all_decisions = self.parse_log(None)
        if not all_decisions:
            return None
        return max(d.decision_time_eet.date() for d in all_decisions)

    def run(self, target_date_eet: date | None = None) -> str:
        """
        Run end-of-day analysis for a chosen EET date.

        Behavior:
        - If a date is provided, analyze that date.
        - If no date is provided, analyze the latest date present in the analytics log that has decisions.
          If none found, fall back to today's EET date.
        """
        if target_date_eet is None:
            latest = self._latest_date_in_log()
            target = latest or self._today_eet()
        else:
            target = target_date_eet

        decisions = self.parse_log(target)

        # If no explicit date was provided and nothing found (e.g., early morning), try latest date in the log
        if target_date_eet is None and not decisions:
            latest = self._latest_date_in_log()
            if latest and latest != target:
                target = latest
                decisions = self.parse_log(target)

        outcomes: list[DecisionOutcome] = [self.evaluate_decision(d) for d in decisions]

        report_path = os.path.join(self.output_dir, f"eod_{target.isoformat()}.md")
        self._write_markdown_report(report_path, target, outcomes)
        return report_path

    def _write_markdown_report(self, path: str, target_date_eet: date, outcomes: list[DecisionOutcome]) -> None:
        total = len(outcomes)
        missed_long = sum(1 for o in outcomes if o.suggested_action == "BUY" and "missed long" in o.rationale.lower())
        missed_short = sum(1 for o in outcomes if o.suggested_action == "SHORT" and "missed short" in o.rationale.lower())
        direction_errors = sum(1 for o in outcomes if "direction error" in o.rationale.lower())
        validated = sum(1 for o in outcomes if (o.suggested_action == "HOLD" and "validated" in o.rationale.lower()) or ("validated" in o.rationale.lower() and o.suggested_action in ("BUY", "SHORT")))
        completed_trades = [o for o in outcomes if o.action.startswith("EXIT_")]

        lines: list[str] = []
        lines.append(f"# End-of-Day Performance Report — {target_date_eet.isoformat()} (EET)")
        lines.append("")
        lines.append("## Parameters:")
        lines.append("- Horizon: same US regular-session close (close-to-close from decision time)")
        lines.append(f"- Timeframe: {self.timeframe_str}")
        lines.append(f"- Threshold: {self.threshold * 100:.2f}%")
        lines.append("- Timestamps: parsed from analytics log in Europe/Helsinki; converted to ET/UTC for market data")
        lines.append("")

        # Add enhanced report sections for JSON event format
        log_format = self._detect_log_format(self.log_path)
        if log_format == "json":
            events = self.load_events(self.log_path)
            if events:
                event_summary = self._build_event_summary(events)
                if event_summary:
                    lines.append("## Event Summary:")
                    for event_type, count in sorted(event_summary.items()):
                        lines.append(f"- {event_type}: {count}")
                    lines.append("")

                position_timeline = self._build_position_timeline(events)
                if position_timeline:
                    lines.append("## Position Timeline:")
                    for ticker, timeline_lines in position_timeline:
                        lines.append(f"### {ticker}")
                        lines.extend(f"- {line}" for line in timeline_lines)
                        lines.append("")

                strategy_performance = self._build_strategy_performance(events)
                if strategy_performance:
                    lines.append("## Strategy Performance:")
                    for strategy, metrics in sorted(strategy_performance.items()):
                        lines.append(f"### {strategy}")
                        lines.append(f"- Entries: {metrics['entries']}")
                        lines.append(f"- Exits: {metrics['exits']}")
                        lines.append(f"- Wins: {metrics['wins']}")
                        lines.append(f"- Total PnL: ${metrics['total_pnl']:.2f}")
                        if metrics["hold_times"]:
                            avg_hold = sum(metrics["hold_times"]) / len(metrics["hold_times"])
                            lines.append(f"- Avg Hold Time: {avg_hold:.2f} hours")
                        lines.append("")

        lines.append("## Summary:")
        lines.append(f"- Decisions evaluated: {total}")
        lines.append(f"- Validated: {validated}")
        lines.append(f"- Missed LONG opportunities (HOLD): {missed_long}")
        lines.append(f"- Missed SHORT opportunities (HOLD): {missed_short}")
        lines.append(f"- Direction errors (BUY/SHORT): {direction_errors}")
        lines.append(f"- Completed trades: {len(completed_trades)}")
        # Execution-based trades summary
        completed_exec_trades, open_exec_positions, realized_exec_total = self._build_execution_summary(getattr(self, "_last_exec_events", []))
        lines.append(f"- Completed trades (Executions): {len(completed_exec_trades)}")
        if completed_exec_trades:
            lines.append(f"- Realized PnL (Executions): ${realized_exec_total:.2f}")
        lines.append("")
        # Completed Trades from Executions
        if completed_exec_trades:
            lines.append("## Completed Trades (Executions):")
            lines.append("")
            lines.append("| Exit Time (EET) | Ticker | Side | Shares | Entry Px | Exit Px | Realized $PnL | $/Share |")
            lines.append("|---|---|---|---:|---:|---:|---:|---:|")

            def money(x: float | None) -> str:
                if x is None:
                    return "-"
                return f"${x:,.2f}"

            def fpx(x: float | None) -> str:
                if x is None:
                    return "-"
                return f"{x:.4f}"

            lines.extend(
                "| "
                + " | ".join(
                    [
                        ct.exit_time_eet.strftime("%Y-%m-%d %H:%M:%S"),
                        ct.ticker,
                        ct.side,
                        str(ct.shares),
                        fpx(ct.entry_avg),
                        fpx(ct.exit_avg),
                        money(ct.realized_pl),
                        money(ct.realized_pl_per_share),
                    ]
                )
                + " |"
                for ct in completed_exec_trades
            )
            lines.append("")
        # Open positions snapshot from execution flow
        if open_exec_positions:
            lines.append("## Open Positions from Day (Executions):")
            lines.append("")
            lines.append("| Entry Time (EET) | Ticker | Side | Shares | Avg Entry Px |")
            lines.append("|---|---|---|---:|---:|")

            def fpx2(x: float | None) -> str:
                if x is None:
                    return "-"
                return f"{x:.4f}"

            lines.extend(
                "| "
                + " | ".join(
                    [
                        op.entry_time_eet.strftime("%Y-%m-%d %H:%M:%S"),
                        op.ticker,
                        op.side,
                        str(op.shares),
                        fpx2(op.avg_entry_price),
                    ]
                )
                + " |"
                for op in open_exec_positions
            )
            lines.append("")
        # Intent-based exit quality check (existing)
        if completed_trades:
            lines.append("## Intent Exits (Quality Check):")
            lines.append("")
            lines.append("| Time (EET) | Ticker | Side | Exit P/L | Ref Px | EOD Close | Outcome | Rationale |")
            lines.append("|---|---|---|---:|---:|---:|---|---|")

            def fpx(x: float | None) -> str:
                if x is None:
                    return "-"
                return f"{x:.4f}"

            def pct(x: float | None) -> str:
                if x is None:
                    return "-"
                return f"{x * 100:.2f}%"

            for o in completed_trades:
                side = o.action.replace("EXIT_", "")
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            o.decision_time_eet.strftime("%Y-%m-%d %H:%M:%S"),
                            o.ticker,
                            side,
                            pct(o.exit_pl_pct),
                            fpx(o.ref_price),
                            fpx(o.eod_close),
                            o.suggested_action,
                            o.rationale.replace("|", "/"),
                        ]
                    )
                    + " |"
                )
            lines.append("")

        lines.append("## Details:")
        lines.append("")
        lines.append("| Time (EET) | Ticker | Action | Ref Px | EOD Close | PnL Long% | PnL Short% | MFE L% | MAE L% | Suggestion | Rationale |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")

        def fmt(x: float | None) -> str:
            if x is None:
                return "-"
            return f"{x * 100:.2f}%"

        def fpx(x: float | None) -> str:
            if x is None:
                return "-"
            return f"{x:.4f}"

        lines.extend(
            [
                "| "
                + " | ".join(
                    [
                        o.decision_time_eet.strftime("%Y-%m-%d %H:%M:%S"),
                        o.ticker,
                        o.action,
                        fpx(o.ref_price),
                        fpx(o.eod_close),
                        fmt(o.pnl_long_close_pct),
                        fmt(o.pnl_short_close_pct),
                        fmt(o.mfe_long_pct),
                        fmt(o.mae_long_pct),
                        o.suggested_action,
                        o.rationale.replace("|", "/"),
                    ]
                )
                + " |"
                for o in outcomes
            ]
        )

        # Appendix for warnings
        warnings = [(o.ticker, o.decision_time_eet, w) for o in outcomes for w in o.warnings]
        if warnings:
            lines.append("")
            lines.append("## Appendix — Warnings and Skipped Items:")
            for t, ts, w in warnings:
                lines.append(f"- {ts.strftime('%Y-%m-%d %H:%M:%S')} {t}: {w}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def analyze_today(
    threshold_pct: float = 1.0,
    timeframe: str = "5Min",
    log_path: str = "logs/analytics_log.log",
    output_dir: str = "logs/eod",
) -> str:
    analyzer = EODPerformanceAnalyzer(
        log_path=log_path,
        output_dir=output_dir,
        threshold_pct=threshold_pct,
        timeframe=timeframe,
    )
    return analyzer.run()
