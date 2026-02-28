"""Analyze agent confidence patterns from events.jsonl."""

import json
from collections import defaultdict
from pathlib import Path


def main():
    events_path = Path("logs/events.jsonl")
    if not events_path.exists():
        print("No events.jsonl found")
        return

    # Collect all agent reasoning events
    agent_confidences: dict[str, list[float]] = defaultdict(list)
    agent_signals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    ticker_decisions: dict[str, list[dict]] = defaultdict(list)
    portfolio_actions: dict[str, int] = defaultdict(int)
    strategist_actions: int = 0
    strategist_holds: int = 0

    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("event_type") != "AGENT_REASONING":
            continue

        agent = event.get("agent", "")
        reasoning = event.get("reasoning", {})

        if not isinstance(reasoning, dict):
            continue

        for ticker, data in reasoning.items():
            if not isinstance(data, dict):
                continue

            signal = data.get("signal", data.get("action", ""))
            confidence = data.get("confidence")

            if confidence is None:
                continue

            # Parse confidence - handle string percentages
            try:
                if isinstance(confidence, str):
                    confidence = float(confidence.replace("%", ""))
                else:
                    confidence = float(confidence)
            except (ValueError, TypeError):
                continue

            agent_confidences[agent].append(confidence)
            if signal:
                agent_signals[agent][signal.lower()] += 1

            if agent == "Portfolio Management Agent":
                action = data.get("action", "hold")
                portfolio_actions[action] += 1
                ticker_decisions[ticker].append(
                    {
                        "action": action,
                        "confidence": confidence,
                        "reasoning": str(data.get("reasoning", ""))[:100],
                    }
                )

            if agent == "Trading Strategist Agent":
                strategist_actions += 1
                if data.get("signal") == "hold" or not data.get("strategies"):
                    strategist_holds += 1

    # Print analysis
    print("=" * 80)
    print("AGENT CONFIDENCE ANALYSIS")
    print("=" * 80)

    for agent in sorted(agent_confidences.keys()):
        confs = agent_confidences[agent]
        if not confs:
            continue
        avg = sum(confs) / len(confs)
        low = min(confs)
        high = max(confs)
        median = sorted(confs)[len(confs) // 2]

        # Count confidence buckets
        below_50 = sum(1 for c in confs if c < 50)
        between_50_70 = sum(1 for c in confs if 50 <= c < 70)
        above_70 = sum(1 for c in confs if c >= 70)

        print(f"\n{agent} (n={len(confs)})")
        print(f"  avg={avg:.1f}  median={median:.1f}  min={low:.1f}  max={high:.1f}")
        print(f"  <50: {below_50} ({below_50 / len(confs) * 100:.0f}%)  50-70: {between_50_70} ({between_50_70 / len(confs) * 100:.0f}%)  >=70: {above_70} ({above_70 / len(confs) * 100:.0f}%)")

        signals = agent_signals[agent]
        if signals:
            total = sum(signals.values())
            parts = [f"{s}: {c} ({c / total * 100:.0f}%)" for s, c in sorted(signals.items())]
            print(f"  signals: {', '.join(parts)}")

    print("\n" + "=" * 80)
    print("PORTFOLIO MANAGER ACTIONS")
    print("=" * 80)
    total_pm = sum(portfolio_actions.values())
    for action, count in sorted(portfolio_actions.items()):
        print(f"  {action}: {count} ({count / total_pm * 100:.0f}%)")

    print(f"\n  Total decisions: {total_pm}")
    if strategist_actions:
        print(f"  Trading Strategist: {strategist_actions} total, {strategist_holds} holds ({strategist_holds / strategist_actions * 100:.0f}%)")

    # Show which tickers got non-hold decisions
    print("\n" + "=" * 80)
    print("NON-HOLD DECISIONS")
    print("=" * 80)
    for ticker, decisions in sorted(ticker_decisions.items()):
        non_holds = [d for d in decisions if d["action"] != "hold"]
        if non_holds:
            for d in non_holds:
                print(f"  {ticker}: {d['action']} (conf={d['confidence']:.1f}%) - {d['reasoning']}")

    # Analyze the "hold trap" - cases where majority bearish but still hold
    print("\n" + "=" * 80)
    print("SIGNAL CONSENSUS ANALYSIS (per cycle)")
    print("=" * 80)

    # Re-parse to group by timestamp proximity
    cycle_signals: dict[str, dict[str, list[tuple[str, str, float]]]] = defaultdict(lambda: defaultdict(list))

    for line in events_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("event_type") != "AGENT_REASONING":
            continue

        agent = event.get("agent", "")
        reasoning = event.get("reasoning", {})
        ts = event.get("timestamp", "")[:16]  # group by minute

        if agent in ("Risk Management Agent", "Portfolio Management Agent", "Trading Strategist Agent"):
            continue

        if not isinstance(reasoning, dict):
            continue

        for ticker, data in reasoning.items():
            if not isinstance(data, dict):
                continue
            signal = data.get("signal", "")
            confidence = data.get("confidence", 0)
            try:
                if isinstance(confidence, str):
                    confidence = float(confidence.replace("%", ""))
                else:
                    confidence = float(confidence)
            except (ValueError, TypeError):
                continue
            if signal:
                cycle_signals[ts][ticker].append((agent, signal.lower(), confidence))

    # Find cases with strong consensus
    strong_bearish = 0
    strong_bullish = 0
    mixed = 0
    for ts, tickers in cycle_signals.items():
        for ticker, signals in tickers.items():
            bearish = [(a, c) for a, s, c in signals if s == "bearish"]
            bullish = [(a, c) for a, s, c in signals if s == "bullish"]
            total = len(signals)
            if total < 2:
                continue
            if len(bearish) >= total * 0.6:
                strong_bearish += 1
                avg_conf = sum(c for _, c in bearish) / len(bearish)
                if avg_conf > 60:
                    print(f"  {ts} {ticker}: {len(bearish)}/{total} bearish (avg conf {avg_conf:.0f}%) - ACTIONABLE?")
            elif len(bullish) >= total * 0.6:
                strong_bullish += 1
            else:
                mixed += 1

    print(f"\n  Strong bearish consensus: {strong_bearish}")
    print(f"  Strong bullish consensus: {strong_bullish}")
    print(f"  Mixed/no consensus: {mixed}")


if __name__ == "__main__":
    main()
