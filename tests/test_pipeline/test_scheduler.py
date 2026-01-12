"""Tests for PipelineScheduler."""

from datetime import UTC, datetime, timedelta

import pytest

from alpacalyzer.pipeline.scheduler import PipelineScheduler, PipelineStage


class TestPipelineStage:
    """Test PipelineStage dataclass."""

    def test_should_run_when_disabled(self):
        """Test that should_run returns False when disabled."""
        stage = PipelineStage(
            name="test",
            handler=lambda: None,
            interval_minutes=5,
            enabled=False,
        )
        assert stage.should_run() is False

    def test_should_run_when_never_run(self):
        """Test that should_run returns True when last_run is None."""
        stage = PipelineStage(
            name="test",
            handler=lambda: None,
            interval_minutes=5,
            enabled=True,
            last_run=None,
        )
        assert stage.should_run() is True

    def test_should_run_when_interval_elapsed(self):
        """Test that should_run returns True when interval has elapsed."""
        stage = PipelineStage(
            name="test",
            handler=lambda: None,
            interval_minutes=5,
            enabled=True,
            last_run=datetime.now(UTC) - timedelta(minutes=10),
        )
        assert stage.should_run() is True

    def test_should_run_when_interval_not_elapsed(self):
        """Test that should_run returns False when interval has not elapsed."""
        stage = PipelineStage(
            name="test",
            handler=lambda: None,
            interval_minutes=5,
            enabled=True,
            last_run=datetime.now(UTC) - timedelta(minutes=2),
        )
        assert stage.should_run() is False

    def test_should_run_at_interval_boundary(self):
        """Test that should_run returns True when exactly at interval."""
        stage = PipelineStage(
            name="test",
            handler=lambda: None,
            interval_minutes=5,
            enabled=True,
            last_run=datetime.now(UTC) - timedelta(minutes=5),
        )
        assert stage.should_run() is True


def make_sync_handler():
    """Factory for sync handler with state."""
    state = {"count": 0}

    def handler():
        state["count"] += 1

    return handler, state


def make_async_handler():
    """Factory for async handler with state."""
    state = {"count": 0}

    async def handler():
        state["count"] += 1

    return handler, state


class TestPipelineScheduler:
    """Test PipelineScheduler functionality."""

    @pytest.fixture
    def scheduler(self):
        """Create a fresh PipelineScheduler instance."""
        return PipelineScheduler()

    def test_add_stage(self, scheduler):
        """Test adding a stage to the scheduler."""
        handler, _ = make_sync_handler()
        scheduler.add_stage("test", handler, interval_minutes=5, enabled=True)

        assert "test" in scheduler._stages
        stage = scheduler._stages["test"]
        assert stage.name == "test"
        assert stage.handler is handler
        assert stage.interval_minutes == 5
        assert stage.enabled is True

    def test_configure_scan(self, scheduler):
        """Test configuring the scan stage."""
        handler, _ = make_sync_handler()
        scheduler.configure_scan(handler, interval_minutes=15)

        assert "scan" in scheduler._stages
        stage = scheduler._stages["scan"]
        assert stage.interval_minutes == 15

    def test_configure_analyze(self, scheduler):
        """Test configuring the analyze stage."""
        handler, _ = make_sync_handler()
        scheduler.configure_analyze(handler, interval_minutes=5)

        assert "analyze" in scheduler._stages
        stage = scheduler._stages["analyze"]
        assert stage.interval_minutes == 5

    def test_configure_execute(self, scheduler):
        """Test configuring the execute stage."""
        handler, _ = make_sync_handler()
        scheduler.configure_execute(handler, interval_minutes=1)

        assert "execute" in scheduler._stages
        stage = scheduler._stages["execute"]
        assert stage.interval_minutes == 1

    def test_enable_stage(self, scheduler):
        """Test enabling a stage."""
        handler, _ = make_sync_handler()
        scheduler.add_stage("test", handler, interval_minutes=5, enabled=False)
        scheduler.enable_stage("test")

        assert scheduler._stages["test"].enabled is True

    def test_enable_nonexistent_stage(self, scheduler):
        """Test enabling a nonexistent stage does not crash."""
        scheduler.enable_stage("nonexistent")
        assert "nonexistent" not in scheduler._stages

    def test_disable_stage(self, scheduler):
        """Test disabling a stage."""
        handler, _ = make_sync_handler()
        scheduler.add_stage("test", handler, interval_minutes=5, enabled=True)
        scheduler.disable_stage("test")

        assert scheduler._stages["test"].enabled is False

    def test_disable_nonexistent_stage(self, scheduler):
        """Test disabling a nonexistent stage does not crash."""
        scheduler.disable_stage("nonexistent")
        assert "nonexistent" not in scheduler._stages

    @pytest.mark.asyncio
    async def test_run_stage_sync_handler(self, scheduler):
        """Test running a stage with a sync handler."""
        handler, state = make_sync_handler()
        scheduler.add_stage("test", handler, interval_minutes=5, enabled=True)
        await scheduler.run_stage("test")

        assert state["count"] == 1
        assert scheduler._stages["test"].run_count == 1
        assert scheduler._stages["test"].last_run is not None

    @pytest.mark.asyncio
    async def test_run_stage_async_handler(self, scheduler):
        """Test running a stage with an async handler."""
        handler, state = make_async_handler()
        scheduler.add_stage("test", handler, interval_minutes=5, enabled=True)
        await scheduler.run_stage("test")

        assert state["count"] == 1
        assert scheduler._stages["test"].run_count == 1

    @pytest.mark.asyncio
    async def test_run_stage_disabled(self, scheduler):
        """Test running a disabled stage does nothing."""
        handler, state = make_sync_handler()
        scheduler.add_stage("test", handler, interval_minutes=5, enabled=False)
        await scheduler.run_stage("test")

        assert state["count"] == 0
        assert scheduler._stages["test"].run_count == 0

    @pytest.mark.asyncio
    async def test_run_stage_unknown(self, scheduler):
        """Test running an unknown stage logs a warning but doesn't crash."""
        await scheduler.run_stage("nonexistent")

    @pytest.mark.asyncio
    async def test_run_stage_error_handling(self, scheduler):
        """Test that stage errors are caught and logged."""

        def failing_handler():
            raise ValueError("Test error")

        scheduler.add_stage("failing", failing_handler, interval_minutes=5, enabled=True)
        await scheduler.run_stage("failing")

        assert scheduler._stages["failing"].run_count == 0

    @pytest.mark.asyncio
    async def test_run_cycle(self, scheduler):
        """Test running one complete pipeline cycle."""
        handler, state = make_sync_handler()
        scheduler.add_stage("scan", handler, interval_minutes=15, enabled=True)
        scheduler.add_stage("analyze", handler, interval_minutes=5, enabled=True)
        scheduler.add_stage("execute", handler, interval_minutes=1, enabled=True)

        await scheduler.run_cycle()

        assert state["count"] == 3
        assert scheduler._stages["scan"].run_count == 1
        assert scheduler._stages["analyze"].run_count == 1
        assert scheduler._stages["execute"].run_count == 1

    @pytest.mark.asyncio
    async def test_run_cycle_skips_disabled_stages(self, scheduler):
        """Test that disabled stages are skipped in run_cycle."""
        handler, state = make_sync_handler()
        scheduler.add_stage("scan", handler, interval_minutes=15, enabled=True)
        scheduler.add_stage("analyze", handler, interval_minutes=5, enabled=False)
        scheduler.add_stage("execute", handler, interval_minutes=1, enabled=True)

        await scheduler.run_cycle()

        assert state["count"] == 2

    @pytest.mark.asyncio
    async def test_run_cycle_respects_intervals(self, scheduler):
        """Test that stages are only run if their interval has elapsed."""
        handler, state = make_sync_handler()
        scheduler.add_stage("scan", handler, interval_minutes=15, enabled=True)
        scheduler.add_stage("analyze", handler, interval_minutes=5, enabled=True)
        scheduler.add_stage("execute", handler, interval_minutes=1, enabled=True)

        scheduler._stages["scan"].last_run = datetime.now(UTC)
        scheduler._stages["analyze"].last_run = datetime.now(UTC)
        scheduler._stages["execute"].last_run = datetime.now(UTC)

        await scheduler.run_cycle()

        assert state["count"] == 0

    @pytest.mark.asyncio
    async def test_stop(self, scheduler):
        """Test stopping the scheduler."""
        scheduler._running = True
        scheduler.stop()

        assert scheduler._running is False

    def test_status(self, scheduler):
        """Test getting scheduler status."""
        handler, _ = make_sync_handler()
        scheduler.add_stage("scan", handler, interval_minutes=15, enabled=True)
        scheduler.add_stage("analyze", handler, interval_minutes=5, enabled=False)
        scheduler._running = True

        status = scheduler.status()

        assert status["running"] is True
        assert "scan" in status["stages"]
        assert status["stages"]["scan"]["enabled"] is True
        assert status["stages"]["scan"]["interval_minutes"] == 15
        assert "analyze" in status["stages"]
        assert status["stages"]["analyze"]["enabled"] is False

    def test_status_with_last_run(self, scheduler):
        """Test status includes last_run timestamps."""
        last_run = datetime.now(UTC)
        scheduler.add_stage("test", lambda: None, interval_minutes=5, enabled=True)
        scheduler._stages["test"].last_run = last_run

        status = scheduler.status()

        assert status["stages"]["test"]["last_run"] is not None
