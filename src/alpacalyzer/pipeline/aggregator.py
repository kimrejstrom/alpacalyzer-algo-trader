import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from alpacalyzer.data.models import TopTicker
from alpacalyzer.events.emitter import emit_event
from alpacalyzer.events.models import ScanCompleteEvent
from alpacalyzer.pipeline.registry import get_scanner_registry
from alpacalyzer.pipeline.scanner_protocol import ScanResult


@dataclass
class Opportunity:
    """A ranked trading opportunity."""

    ticker: str
    score: float
    sources: list[str] = field(default_factory=list)
    first_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))
    mentions: int = 0
    upvotes: int = 0
    best_rank: int = 999
    technical_match: bool = False

    @property
    def age_hours(self) -> float:
        return (datetime.now(UTC) - self.first_seen).total_seconds() / 3600

    @property
    def source_count(self) -> int:
        return len(self.sources)


class OpportunityAggregator:
    """
    Aggregates scanner results into ranked opportunities.

    Scoring factors:
    - Number of sources mentioning ticker
    - Recency of mentions
    - Social metrics (upvotes, mentions)
    - Technical pattern match
    - Rank in each source

    Usage:
        aggregator = OpportunityAggregator()
        aggregator.aggregate()

        for opp in aggregator.top(10):
            print(f"{opp.ticker}: score={opp.score:.2f}, sources={opp.sources}")
    """

    def __init__(
        self,
        max_age_hours: float = 4.0,
        min_sources: int = 1,
    ):
        self.max_age_hours = max_age_hours
        self.min_sources = min_sources
        self._opportunities: dict[str, Opportunity] = {}
        self._last_aggregation: datetime | None = None

    def aggregate(self, scan_results: list[ScanResult] | None = None) -> None:
        """
        Aggregate scan results into opportunities.

        If scan_results is None, runs all scanners.
        """
        if scan_results is None:
            scan_results = list(get_scanner_registry().run_all())

        for result in scan_results:
            if result.success:
                emit_event(
                    ScanCompleteEvent(
                        timestamp=datetime.now(UTC),
                        source=result.source,
                        tickers_found=result.symbols(),
                        duration_seconds=result.duration_seconds,
                    )
                )

        for result in scan_results:
            if not result.success:
                continue

            for ticker in result.tickers:
                self._update_opportunity(ticker, result.source)

        self._prune_stale()
        self._calculate_scores()

        self._last_aggregation = datetime.now(UTC)

    def _update_opportunity(self, ticker: TopTicker, source: str) -> None:
        """Update or create an opportunity for a ticker."""
        symbol = ticker.ticker
        now = datetime.now(UTC)

        if symbol in self._opportunities:
            opp = self._opportunities[symbol]
            opp.last_seen = now
            if source not in opp.sources:
                opp.sources.append(source)
            opp.mentions += ticker.mentions
            opp.upvotes += ticker.upvotes
            if ticker.rank > 0:
                opp.best_rank = min(opp.best_rank, ticker.rank)
        else:
            self._opportunities[symbol] = Opportunity(
                ticker=symbol,
                score=0.0,
                sources=[source],
                first_seen=now,
                last_seen=now,
                mentions=ticker.mentions,
                upvotes=ticker.upvotes,
                best_rank=ticker.rank if ticker.rank > 0 else 999,
            )

    def _prune_stale(self) -> None:
        """Remove opportunities older than max_age_hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=self.max_age_hours)

        stale = [symbol for symbol, opp in self._opportunities.items() if opp.last_seen < cutoff]

        for symbol in stale:
            del self._opportunities[symbol]

    def _calculate_scores(self) -> None:
        """
        Calculate opportunity scores.

        Score components:
        - Source diversity: +20 per source
        - Freshness: +30 if seen in last hour, +15 if in last 2 hours
        - Social proof: log(upvotes + 1) * 5 + log(mentions + 1) * 3
        - Ranking: +25 for top 10, +15 for top 25, +5 for top 50
        - Technical: +30 if has technical pattern match
        """
        for opp in self._opportunities.values():
            score = 0.0

            score += len(opp.sources) * 20

            age_hours = opp.age_hours
            if age_hours < 1:
                score += 30
            elif age_hours < 2:
                score += 15

            score += math.log(opp.upvotes + 1) * 5
            score += math.log(opp.mentions + 1) * 3

            if opp.best_rank <= 10:
                score += 25
            elif opp.best_rank <= 25:
                score += 15
            elif opp.best_rank <= 50:
                score += 5

            if opp.technical_match:
                score += 30

            opp.score = score

    def mark_technical_match(self, ticker: str) -> None:
        """Mark a ticker as having a technical pattern match."""
        if opp := self._opportunities.get(ticker):
            opp.technical_match = True
            self._calculate_scores()

    def top(self, n: int = 10) -> list[Opportunity]:
        """Get top N opportunities by score."""
        valid = [opp for opp in self._opportunities.values() if len(opp.sources) >= self.min_sources]
        return sorted(valid, key=lambda x: x.score, reverse=True)[:n]

    def all(self) -> Iterator[Opportunity]:
        """Iterate all opportunities."""
        yield from self._opportunities.values()

    def get(self, ticker: str) -> Opportunity | None:
        """Get opportunity for a specific ticker."""
        return self._opportunities.get(ticker)

    def symbols(self) -> list[str]:
        """Get all ticker symbols."""
        return list(self._opportunities.keys())

    def clear(self) -> None:
        """Clear all opportunities."""
        self._opportunities.clear()
