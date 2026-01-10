"""Event emitter for structured logging."""

from alpacalyzer.events.models import TradingEvent
from alpacalyzer.utils.logger import get_logger

logger = get_logger()


def emit_event(event: TradingEvent) -> None:
    """
    Emit a trading event to the logger.

    Format events for analytics and human readers. Analytics logs use the
    analyze() method for EOD processing, while also logging to info() for
    console output.
    """
    event_type = event.model_dump().get("event_type", "UNKNOWN")

    data = event.model_dump()

    if event_type == "ENTRY_TRIGGERED":
        reason = f"{data.get('reason')} (Strategy: {data.get('strategy')}, Side: {data.get('side')}, Qty: {data.get('quantity')})"
        logger.analyze(
            f"[ENTRY] Ticker: {data.get('ticker')}, Action: {data.get('side')}, Entry: ${data.get('entry_price'):.2f}, "
            f"Stop: ${data.get('stop_loss'):.2f}, Target: ${data.get('target'):.2f}, Reason: {reason}"
        )
        logger.info(f"Entry triggered for {data.get('ticker')}: {reason}")

    elif event_type == "ENTRY_BLOCKED":
        logger.debug(f"Entry blocked for {data.get('ticker')}: {data.get('reason')} ({data.get('conditions_met')}/{data.get('conditions_total')} criteria met)")

    elif event_type == "EXIT_TRIGGERED":
        logger.analyze(
            f"[EXIT] Ticker: {data.get('ticker')}, Side: {data.get('side')}, Reason: {data.get('reason')}, "
            f"Entry: ${data.get('entry_price'):.2f}, Exit: ${data.get('exit_price'):.2f}, P/L: {data.get('pnl_pct'):.2%}"
        )
        logger.info(f"Exit triggered for {data.get('ticker')}: {data.get('reason')} (P/L: {data.get('pnl_pct'):.2%})")

    elif event_type == "ORDER_SUBMITTED":
        logger.info(f"Order submitted: {data.get('ticker')} {data.get('side')} {data.get('quantity')} @ {data.get('limit_price') or 'market'} (ID: {data.get('order_id')})")

    elif event_type == "ORDER_FILLED":
        logger.analyze(
            f"[EXECUTION] Ticker: {data.get('ticker')}, Side: {data.get('side')}, OrderId: {data.get('order_id')}, "
            f"ClientOrderId: {data.get('client_order_id')}, Qty: {data.get('filled_qty')}/{data.get('quantity')}, "
            f"AvgPrice: ${data.get('avg_price'):.2f}, Strategy: {data.get('strategy')}, Status: fill"
        )
        logger.info(f"Order filled: {data.get('ticker')} {data.get('side')} {data.get('filled_qty')} shares @ ${data.get('avg_price'):.2f}")

    elif event_type == "ORDER_CANCELED":
        logger.info(f"Order canceled: {data.get('ticker')} {data.get('order_id')}")
        if data.get("reason"):
            logger.debug(f"Cancel reason: {data.get('reason')}")

    elif event_type == "ORDER_REJECTED":
        logger.warning(f"Order rejected: {data.get('ticker')} - Reason: {data.get('reason')}")

    elif event_type == "POSITION_OPENED":
        logger.info(f"Position opened: {data.get('ticker')} {data.get('side')} {data.get('quantity')} @ ${data.get('entry_price'):.2f}")

    elif event_type == "POSITION_CLOSED":
        logger.analyze(
            f"[EXIT] Ticker: {data.get('ticker')}, Side: {data.get('side')}, Exit Reason: {data.get('exit_reason')}, "
            f"Entry: ${data.get('entry_price'):.2f}, Exit: ${data.get('exit_price'):.2f}, P/L: {data.get('pnl_pct'):.2%}, "
            f"Held: {data.get('hold_duration_hours'):.1f}h"
        )
        logger.info(f"Position closed: {data.get('ticker')} (P/L: {data.get('pnl_pct'):.2%})")

    elif event_type == "SCAN_COMPLETE":
        logger.debug(f"Scan complete ({data.get('source')}): {len(data.get('tickers_found', []))} tickers in {data.get('duration_seconds'):.1f}s")

    elif event_type == "SIGNAL_GENERATED":
        logger.info(f"Signal generated: {data.get('ticker')} {data.get('action')} (confidence: {data.get('confidence'):.0%})")
        if data.get("reasoning"):
            logger.debug(f"Reasoning: {data.get('reasoning')}")

    elif event_type == "COOLDOWN_STARTED":
        logger.debug(f"Cooldown started for {data.get('ticker')}: {data.get('duration_hours')}h - {data.get('reason')}")

    elif event_type == "COOLDOWN_ENDED":
        logger.info(f"Cooldown ended for {data.get('ticker')}")

    elif event_type == "CYCLE_COMPLETE":
        logger.debug(f"Cycle complete: {data.get('entries_triggered')} entries, {data.get('exits_triggered')} exits, {data.get('positions_open')} positions in {data.get('duration_seconds'):.1f}s")

    else:
        logger.debug(f"Event emitted: {event_type} - {event.model_dump_json()}")
