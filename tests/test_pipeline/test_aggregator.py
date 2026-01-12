"""Tests for OpportunityAggregator."""

from datetime import UTC, datetime, timedelta

import pytest

from alpacalyzer.data.models import TopTicker
from alpacalyzer.pipeline.aggregator import Opportunity, OpportunityAggregator
from alpacalyzer.pipeline.scanner_protocol import ScanResult


class TestOpportunity:
    """Test Opportunity dataclass."""

    def test_opportunity_creation(self):
        """Test creating an opportunity."""
        opp = Opportunity(
            ticker="AAPL",
            score=100.0,
            sources=["reddit"],
            mentions=10,
            upvotes=50,
            best_rank=5,
        )

        assert opp.ticker == "AAPL"
        assert opp.score == 100.0
        assert opp.sources == ["reddit"]
        assert opp.mentions == 10
        assert opp.upvotes == 50
        assert opp.best_rank == 5
        assert opp.technical_match is False

    def test_opportunity_age_hours(self):
        """Test age_hours property."""
        now = datetime.now(UTC)
        opp = Opportunity(
            ticker="AAPL",
            score=0.0,
            sources=["reddit"],
            first_seen=now - timedelta(hours=2),
            last_seen=now,
        )

        assert 1.9 <= opp.age_hours <= 2.1

    def test_opportunity_source_count(self):
        """Test source_count property."""
        opp = Opportunity(
            ticker="AAPL",
            score=0.0,
            sources=["reddit", "stocktwits", "finviz"],
        )

        assert opp.source_count == 3

    def test_opportunity_defaults(self):
        """Test default values."""
        opp = Opportunity(ticker="AAPL", score=0.0)

        assert opp.sources == []
        assert opp.mentions == 0
        assert opp.upvotes == 0
        assert opp.best_rank == 999
        assert opp.technical_match is False
        assert isinstance(opp.first_seen, datetime)
        assert isinstance(opp.last_seen, datetime)


class TestOpportunityAggregator:
    """Test OpportunityAggregator class."""

    @pytest.fixture
    def aggregator(self):
        """Create a fresh aggregator instance."""
        return OpportunityAggregator(max_age_hours=4.0, min_sources=1)

    @pytest.fixture
    def sample_scan_results(self):
        """Create sample scan results for testing."""
        return [
            ScanResult(
                source="reddit",
                tickers=[
                    TopTicker(
                        ticker="AAPL",
                        signal="bullish",
                        confidence=0.8,
                        reasoning="Test reasoning",
                        mentions=10,
                        upvotes=50,
                        rank=5,
                    ),
                    TopTicker(
                        ticker="TSLA",
                        signal="bullish",
                        confidence=0.7,
                        reasoning="Test reasoning",
                        mentions=5,
                        upvotes=25,
                        rank=10,
                    ),
                ],
                duration_seconds=1.0,
            ),
            ScanResult(
                source="stocktwits",
                tickers=[
                    TopTicker(
                        ticker="AAPL",
                        signal="bullish",
                        confidence=0.9,
                        reasoning="Test reasoning",
                        mentions=8,
                        upvotes=40,
                        rank=3,
                    ),
                ],
                duration_seconds=0.5,
            ),
        ]

    def test_init_defaults(self):
        """Test default initialization values."""
        agg = OpportunityAggregator()

        assert agg.max_age_hours == 4.0
        assert agg.min_sources == 1
        assert agg._opportunities == {}
        assert agg._last_aggregation is None

    def test_init_custom_values(self):
        """Test custom initialization values."""
        agg = OpportunityAggregator(max_age_hours=8.0, min_sources=2)

        assert agg.max_age_hours == 8.0
        assert agg.min_sources == 2

    def test_aggregate_with_results(self, aggregator, sample_scan_results):
        """Test aggregation with provided scan results."""
        aggregator.aggregate(sample_scan_results)

        assert len(aggregator._opportunities) == 2
        assert "AAPL" in aggregator._opportunities
        assert "TSLA" in aggregator._opportunities

    def test_aggregate_deduplication(self, aggregator, sample_scan_results):
        """Test that tickers are deduplicated across sources."""
        aggregator.aggregate(sample_scan_results)

        opp = aggregator._opportunities["AAPL"]
        assert len(opp.sources) == 2
        assert "reddit" in opp.sources
        assert "stocktwits" in opp.sources
        assert opp.mentions == 18  # 10 + 8
        assert opp.upvotes == 90  # 50 + 40
        assert opp.best_rank == 3  # min(5, 3)

    def test_aggregate_aggregates_mentions(self, aggregator, sample_scan_results):
        """Test that mentions and upvotes are aggregated."""
        aggregator.aggregate(sample_scan_results)

        opp = aggregator._opportunities["AAPL"]
        assert opp.mentions == 18
        assert opp.upvotes == 90

    def test_aggregate_updates_best_rank(self, aggregator, sample_scan_results):
        """Test that best rank is updated across sources."""
        aggregator.aggregate(sample_scan_results)

        opp = aggregator._opportunities["AAPL"]
        assert opp.best_rank == 3

    def test_aggregate_calculates_scores(self, aggregator, sample_scan_results):
        """Test that scores are calculated after aggregation."""
        aggregator.aggregate(sample_scan_results)

        aapl = aggregator._opportunities["AAPL"]
        tsla = aggregator._opportunities["TSLA"]

        assert aapl.score > 0
        assert tsla.score > 0
        assert aapl.score > tsla.score  # AAPL has more sources/upvotes

    def test_top_returns_sorted(self, aggregator, sample_scan_results):
        """Test that top() returns sorted opportunities."""
        aggregator.aggregate(sample_scan_results)

        top = aggregator.top(10)

        assert len(top) == 2
        assert top[0].score >= top[1].score

    def test_top_respects_limit(self, aggregator, sample_scan_results):
        """Test that top() respects the limit."""
        aggregator.aggregate(sample_scan_results)

        top = aggregator.top(1)

        assert len(top) == 1

    def test_top_filters_by_min_sources(self, aggregator):
        """Test that top() filters by min_sources."""
        results = [
            ScanResult(
                source="reddit",
                tickers=[
                    TopTicker(
                        ticker="AAPL",
                        signal="bullish",
                        confidence=0.8,
                        reasoning="Test",
                        mentions=10,
                        upvotes=50,
                        rank=5,
                    ),
                ],
                duration_seconds=1.0,
            ),
        ]

        agg_min_sources = OpportunityAggregator(min_sources=2)
        agg_min_sources.aggregate(results)

        top = agg_min_sources.top(10)
        assert len(top) == 0

    def test_all_iterates_all(self, aggregator, sample_scan_results):
        """Test that all() iterates all opportunities."""
        aggregator.aggregate(sample_scan_results)

        all_opps = list(aggregator.all())

        assert len(all_opps) == 2

    def test_get_returns_specific(self, aggregator, sample_scan_results):
        """Test get() returns opportunity for specific ticker."""
        aggregator.aggregate(sample_scan_results)

        opp = aggregator.get("AAPL")

        assert opp is not None
        assert opp.ticker == "AAPL"

    def test_get_returns_none_for_missing(self, aggregator):
        """Test get() returns None for missing ticker."""
        opp = aggregator.get("NONE")

        assert opp is None

    def test_symbols_returns_all(self, aggregator, sample_scan_results):
        """Test symbols() returns all ticker symbols."""
        aggregator.aggregate(sample_scan_results)

        symbols = aggregator.symbols()

        assert set(symbols) == {"AAPL", "TSLA"}

    def test_clear_removes_all(self, aggregator, sample_scan_results):
        """Test clear() removes all opportunities."""
        aggregator.aggregate(sample_scan_results)
        assert len(aggregator._opportunities) == 2

        aggregator.clear()

        assert len(aggregator._opportunities) == 0

    def test_mark_technical_match(self, aggregator, sample_scan_results):
        """Test marking a ticker as technical match."""
        aggregator.aggregate(sample_scan_results)

        original_score = aggregator.get("AAPL").score
        aggregator.mark_technical_match("AAPL")

        assert aggregator.get("AAPL").technical_match is True
        assert aggregator.get("AAPL").score > original_score

    def test_mark_technical_match_nonexistent(self, aggregator):
        """Test marking non-existent ticker doesn't crash."""
        aggregator.mark_technical_match("NONE")
        assert len(aggregator._opportunities) == 0

    def test_prune_stale_removes_old(self, aggregator):
        """Test that stale opportunities are pruned."""
        old_time = datetime.now(UTC) - timedelta(hours=5)
        aggregator._opportunities["OLD"] = Opportunity(
            ticker="OLD",
            score=100.0,
            sources=["reddit"],
            first_seen=old_time,
            last_seen=old_time,
        )

        aggregator._prune_stale()

        assert "OLD" not in aggregator._opportunities

    def test_prune_stale_keeps_fresh(self, aggregator):
        """Test that fresh opportunities are kept."""
        now = datetime.now(UTC)
        aggregator._opportunities["FRESH"] = Opportunity(
            ticker="FRESH",
            score=100.0,
            sources=["reddit"],
            first_seen=now,
            last_seen=now,
        )

        aggregator._prune_stale()

        assert "FRESH" in aggregator._opportunities

    def test_score_source_diversity(self):
        """Test that score increases with more sources."""
        agg1 = OpportunityAggregator()
        agg1._opportunities["AAPL"] = Opportunity(
            ticker="AAPL",
            score=0.0,
            sources=["reddit"],
        )

        agg2 = OpportunityAggregator()
        agg2._opportunities["AAPL"] = Opportunity(
            ticker="AAPL",
            score=0.0,
            sources=["reddit", "stocktwits", "finviz"],
        )

        agg1._calculate_scores()
        agg2._calculate_scores()

        assert agg2._opportunities["AAPL"].score > agg1._opportunities["AAPL"].score

    def test_score_freshness(self):
        """Test that fresher opportunities score higher."""
        now = datetime.now(UTC)

        agg1 = OpportunityAggregator()
        agg1._opportunities["RECENT"] = Opportunity(
            ticker="RECENT",
            score=0.0,
            sources=["reddit"],
            first_seen=now - timedelta(minutes=30),
            last_seen=now - timedelta(minutes=30),
        )

        agg2 = OpportunityAggregator()
        agg2._opportunities["OLDER"] = Opportunity(
            ticker="OLDER",
            score=0.0,
            sources=["reddit"],
            first_seen=now - timedelta(hours=1.5),
            last_seen=now - timedelta(hours=1.5),
        )

        agg1._calculate_scores()
        agg2._calculate_scores()

        assert agg1._opportunities["RECENT"].score > agg2._opportunities["OLDER"].score

    def test_score_ranking_bonus(self):
        """Test that better ranks get higher scores."""
        agg1 = OpportunityAggregator()
        agg1._opportunities["TOP"] = Opportunity(
            ticker="TOP",
            score=0.0,
            sources=["reddit"],
            best_rank=5,
        )

        agg2 = OpportunityAggregator()
        agg2._opportunities["LOW"] = Opportunity(
            ticker="LOW",
            score=0.0,
            sources=["reddit"],
            best_rank=100,
        )

        agg1._calculate_scores()
        agg2._calculate_scores()

        assert agg1._opportunities["TOP"].score > agg2._opportunities["LOW"].score

    def test_score_technical_match_bonus(self):
        """Test that technical match adds to score."""
        agg1 = OpportunityAggregator()
        agg1._opportunities["MATCH"] = Opportunity(
            ticker="MATCH",
            score=0.0,
            sources=["reddit"],
            technical_match=True,
        )

        agg2 = OpportunityAggregator()
        agg2._opportunities["NO_MATCH"] = Opportunity(
            ticker="NO_MATCH",
            score=0.0,
            sources=["reddit"],
            technical_match=False,
        )

        agg1._calculate_scores()
        agg2._calculate_scores()

        assert agg1._opportunities["MATCH"].score > agg2._opportunities["NO_MATCH"].score

    def test_aggregate_with_empty_results(self, aggregator):
        """Test aggregation with empty results."""
        aggregator.aggregate([])

        assert len(aggregator._opportunities) == 0

    def test_aggregate_with_failed_scans(self, aggregator):
        """Test that failed scans are skipped."""
        results = [
            ScanResult(
                source="reddit",
                tickers=[],
                duration_seconds=1.0,
                error="Connection error",
            ),
            ScanResult(
                source="stocktwits",
                tickers=[
                    TopTicker(
                        ticker="AAPL",
                        signal="bullish",
                        confidence=0.8,
                        reasoning="Test",
                    ),
                ],
                duration_seconds=0.5,
            ),
        ]

        aggregator.aggregate(results)

        assert "AAPL" in aggregator._opportunities
        assert len(aggregator._opportunities) == 1

    def test_last_aggregation_updated(self, aggregator, sample_scan_results):
        """Test that last_aggregation is updated after aggregation."""
        assert aggregator._last_aggregation is None

        aggregator.aggregate(sample_scan_results)

        assert aggregator._last_aggregation is not None
        assert isinstance(aggregator._last_aggregation, datetime)
