"""Tests for technical signal caching in ExecutionEngine."""

from time import time as time_func
from unittest.mock import MagicMock

import pytest

from alpacalyzer.analysis.technical_analysis import TradingSignals
from alpacalyzer.execution.engine import CachedSignal, ExecutionConfig, ExecutionEngine
from alpacalyzer.strategies.momentum import MomentumStrategy


def create_mock_signal(symbol: str = "AAPL", price: float = 150.0) -> TradingSignals:
    """Create a mock TradingSignals for testing."""
    return TradingSignals(
        symbol=symbol,
        price=price,
        atr=2.5,
        rvol=1.5,
        signals=["Test signal"],
        raw_score=50,
        score=0.5,
        momentum=0.5,
        raw_data_daily=MagicMock(),
        raw_data_intraday=MagicMock(),
    )


@pytest.fixture
def strategy():
    """Create a momentum strategy for testing."""
    return MomentumStrategy()


@pytest.fixture
def engine(strategy, mock_broker):
    """Create an execution engine for testing."""
    config = ExecutionConfig(analyze_mode=True, signal_cache_ttl=300.0)
    return ExecutionEngine(strategy=strategy, config=config)


class TestCacheHit:
    """Tests for cache hit functionality."""

    def test_cache_hit_returns_cached_signal(self, engine):
        """Test that cache returns cached signal within TTL."""
        mock_signal = create_mock_signal()
        engine._cache_signal("AAPL", mock_signal)
        cached = engine._get_cached_signal("AAPL")

        assert cached is not None
        assert cached["symbol"] == "AAPL"
        assert cached["price"] == 150.0
        assert cached["atr"] == 2.5

    def test_cache_hit_within_ttl(self, engine):
        """Test that cache returns signal within TTL."""
        mock_signal = create_mock_signal()
        engine._cache_signal("AAPL", mock_signal, ttl=300)
        cached = engine._get_cached_signal("AAPL")

        assert cached is not None
        assert cached["symbol"] == "AAPL"
        assert cached["price"] == 150.0


class TestCacheMiss:
    """Tests for cache miss functionality."""

    def test_cache_miss_no_entry(self, engine):
        """Test that None is returned for uncached ticker."""
        cached = engine._get_cached_signal("MSFT")
        assert cached is None

    def test_cache_miss_expired(self, engine):
        """Test that expired cache entries are not returned."""
        mock_signal = create_mock_signal()

        engine._signal_cache["AAPL"] = CachedSignal(
            signal=mock_signal,
            timestamp=0.0,
            ttl=300.0,
        )

        cached = engine._get_cached_signal("AAPL")

        assert cached is None

    def test_cache_miss_calls_analyzer(self, engine):
        """Test that cache miss in _process_exit triggers analyzer call."""
        mock_signal = create_mock_signal()
        engine._ta.analyze_stock = MagicMock(return_value=mock_signal)
        engine.strategy.evaluate_exit = MagicMock(return_value=MagicMock(should_exit=False))
        engine._build_market_context = MagicMock(return_value=MagicMock())

        mock_position = MagicMock()
        mock_position.ticker = "AAPL"
        mock_position.side = "long"
        mock_position.quantity = 100
        mock_position.has_bracket_order = False

        engine._process_exit(mock_position)

        engine._ta.analyze_stock.assert_called_once_with("AAPL")


class TestClearExpiredCache:
    """Tests for cache expiration cleanup."""

    def test_clear_expired_cache(self, engine):
        """Test that expired entries are removed."""
        aapl_signal = create_mock_signal("AAPL")
        msft_signal = create_mock_signal("MSFT")

        current_time = time_func()
        engine._signal_cache["AAPL"] = CachedSignal(
            signal=aapl_signal,
            timestamp=current_time - 200,
            ttl=100.0,
        )
        engine._signal_cache["MSFT"] = CachedSignal(
            signal=msft_signal,
            timestamp=current_time - 50,
            ttl=300.0,
        )

        engine._clear_expired_cache()

        assert engine._get_cached_signal("AAPL") is None
        assert engine._get_cached_signal("MSFT") is not None
        assert len(engine._signal_cache) == 1

    def test_clear_expired_cache_no_effect_if_none_expired(self, engine):
        """Test that clearing has no effect if nothing expired."""
        aapl_signal = create_mock_signal("AAPL")
        msft_signal = create_mock_signal("MSFT")

        current_time = time_func()
        engine._signal_cache["AAPL"] = CachedSignal(
            signal=aapl_signal,
            timestamp=current_time - 50,
            ttl=300.0,
        )
        engine._signal_cache["MSFT"] = CachedSignal(
            signal=msft_signal,
            timestamp=current_time - 100,
            ttl=300.0,
        )

        engine._clear_expired_cache()

        assert engine._get_cached_signal("AAPL") is not None
        assert engine._get_cached_signal("MSFT") is not None
        assert len(engine._signal_cache) == 2


class TestCacheRespectsTTL:
    """Tests for TTL behavior."""

    def test_ttl_respected_per_entry(self, engine):
        """Test that TTL is respected per entry."""
        mock_signal = create_mock_signal()

        current_time = time_func()
        engine._signal_cache["AAPL"] = CachedSignal(
            signal=mock_signal,
            timestamp=current_time - 50,
            ttl=200.0,
        )

        cached = engine._get_cached_signal("AAPL")
        assert cached is not None

        engine._signal_cache["AAPL"] = CachedSignal(
            signal=mock_signal,
            timestamp=current_time - 300,
            ttl=200.0,
        )
        cached = engine._get_cached_signal("AAPL")
        assert cached is None


class TestCacheInAnalyzeMode:
    """Tests for cache behavior in analyze mode."""

    def test_cache_attributes_exist_in_analyze_mode(self, engine):
        """Test that cache attributes exist even in analyze mode."""
        assert hasattr(engine, "_signal_cache")
        assert hasattr(engine, "_cache_ttl")
        assert hasattr(engine, "_ta")

    def test_cache_works_in_analyze_mode(self, engine):
        """Test that caching works in analyze mode."""
        mock_signal = create_mock_signal()
        engine._cache_signal("AAPL", mock_signal)
        cached = engine._get_cached_signal("AAPL")

        assert cached is not None
        assert cached["symbol"] == "AAPL"
        assert cached["price"] == 150.0


class TestTechnicalAnalyzerReuse:
    """Tests for TechnicalAnalyzer instance reuse."""

    def test_single_ta_instance(self, engine):
        """Test that a single TechnicalAnalyzer instance is used."""
        assert hasattr(engine, "_ta")
        from alpacalyzer.analysis.technical_analysis import TechnicalAnalyzer

        assert isinstance(engine._ta, TechnicalAnalyzer)

    def test_ta_instance_reused_across_calls(self, engine):
        """Test that the same TA instance is used in processing."""
        mock_signal = create_mock_signal()
        engine._ta.analyze_stock = MagicMock(return_value=mock_signal)
        engine.strategy.evaluate_exit = MagicMock(return_value=MagicMock(should_exit=False))
        engine._build_market_context = MagicMock(return_value=MagicMock())

        mock_position = MagicMock()
        mock_position.ticker = "AAPL"
        mock_position.side = "long"
        mock_position.quantity = 100
        mock_position.has_bracket_order = False

        engine._process_exit(mock_position)

        assert engine._ta.analyze_stock.call_count == 1


class TestPerformanceBenchmark:
    """Performance benchmark tests for caching."""

    def test_cache_prevents_redundant_calls(self, engine):
        """Test that cache prevents redundant analyzer calls across multiple positions."""
        mock_signal = create_mock_signal()
        engine._ta.analyze_stock = MagicMock(return_value=mock_signal)

        engine._cache_signal("AAPL", mock_signal)

        for _ in range(5):
            cached = engine._get_cached_signal("AAPL")
            assert cached is not None

        assert engine._ta.analyze_stock.call_count == 0

    def test_cache_hit_avoids_analyzer_call_in_process_exit(self, engine):
        """Test that cache hit in _process_exit avoids analyzer call."""
        mock_signal = create_mock_signal()
        engine._ta.analyze_stock = MagicMock(return_value=mock_signal)
        engine.strategy.evaluate_exit = MagicMock(return_value=MagicMock(should_exit=False))
        engine._build_market_context = MagicMock(return_value=MagicMock())

        engine._cache_signal("AAPL", mock_signal)

        mock_position = MagicMock()
        mock_position.ticker = "AAPL"
        mock_position.side = "long"
        mock_position.quantity = 100
        mock_position.has_bracket_order = False

        engine._process_exit(mock_position)

        engine._ta.analyze_stock.assert_not_called()


class TestCacheIntegration:
    """Integration tests for cache with engine cycle."""

    def test_cache_cleared_in_run_cycle(self, engine):
        """Test that cache is cleared at start of run_cycle."""
        engine.config.analyze_mode = False
        engine.positions.sync_from_broker = MagicMock()
        engine._build_market_context = MagicMock(return_value=MagicMock())

        aapl_signal = create_mock_signal("AAPL")
        engine._signal_cache["AAPL"] = CachedSignal(
            signal=aapl_signal,
            timestamp=0.0,
            ttl=100.0,
        )

        engine.run_cycle()

        assert len(engine._signal_cache) == 0

    def test_cache_cleared_in_analyze_cycle(self, engine):
        """Test that cache is cleared at start of analyze cycle."""
        engine.positions.sync_from_broker = MagicMock()
        engine._build_market_context = MagicMock(return_value=MagicMock())

        aapl_signal = create_mock_signal("AAPL")
        engine._signal_cache["AAPL"] = CachedSignal(
            signal=aapl_signal,
            timestamp=0.0,
            ttl=100.0,
        )

        engine._run_analyze_cycle()

        assert len(engine._signal_cache) == 0


class TestCacheEntryBehavior:
    """Tests for specific cache entry behaviors."""

    def test_cache_signal_stores_correct_ttl(self, engine):
        """Test that _cache_signal stores the correct TTL."""
        mock_signal = create_mock_signal()
        engine._cache_signal("AAPL", mock_signal, ttl=600.0)

        cached = engine._signal_cache["AAPL"]
        assert cached.ttl == 600.0

    def test_cache_signal_uses_default_ttl(self, engine):
        """Test that _cache_signal uses default TTL when not specified."""
        mock_signal = create_mock_signal()
        engine._cache_signal("AAPL", mock_signal)

        cached = engine._signal_cache["AAPL"]
        assert cached.ttl == engine._cache_ttl

    def test_get_cached_signal_returns_none_for_empty_cache(self, engine):
        """Test that get_cached_signal returns None for empty cache."""
        result = engine._get_cached_signal("NONEXISTENT")
        assert result is None

    def test_expired_entry_removed_on_access(self, engine):
        """Test that expired entries are removed when accessed."""
        mock_signal = create_mock_signal()
        engine._signal_cache["AAPL"] = CachedSignal(
            signal=mock_signal,
            timestamp=0.0,
            ttl=100.0,
        )

        result = engine._get_cached_signal("AAPL")
        assert result is None
        assert "AAPL" not in engine._signal_cache
