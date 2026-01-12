import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from alpacalyzer.utils.logger import get_logger

logger = get_logger()


@dataclass
class PipelineStage:
    """A stage in the trading pipeline."""

    name: str
    handler: Callable
    interval_minutes: int
    enabled: bool = True
    last_run: datetime | None = None
    run_count: int = 0

    def should_run(self) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        elapsed = (datetime.now(UTC) - self.last_run).total_seconds() / 60
        return elapsed >= self.interval_minutes


class PipelineScheduler:
    """
    Unified pipeline scheduler.

    Pipeline stages:
    1. SCAN: Aggregate opportunities from all sources
    2. ANALYZE: Run hedge fund analysis on top opportunities
    3. EXECUTE: Check entry/exit conditions and manage positions

    Usage:
        scheduler = PipelineScheduler()
        scheduler.configure_scan(interval_minutes=15)
        scheduler.configure_analyze(interval_minutes=5)
        scheduler.configure_execute(interval_minutes=1)

        scheduler.run()
    """

    def __init__(self):
        self._stages: dict[str, PipelineStage] = {}
        self._running = False

    def add_stage(
        self,
        name: str,
        handler: Callable,
        interval_minutes: int,
        enabled: bool = True,
    ) -> None:
        """Add a pipeline stage."""
        self._stages[name] = PipelineStage(
            name=name,
            handler=handler,
            interval_minutes=interval_minutes,
            enabled=enabled,
        )

    def configure_scan(
        self,
        handler: Callable,
        interval_minutes: int = 15,
    ) -> None:
        """Configure the scanning stage."""
        self.add_stage("scan", handler, interval_minutes)

    def configure_analyze(
        self,
        handler: Callable,
        interval_minutes: int = 5,
    ) -> None:
        """Configure the analysis stage."""
        self.add_stage("analyze", handler, interval_minutes)

    def configure_execute(
        self,
        handler: Callable,
        interval_minutes: int = 1,
    ) -> None:
        """Configure the execution stage."""
        self.add_stage("execute", handler, interval_minutes)

    def enable_stage(self, name: str) -> None:
        """Enable a stage."""
        if stage := self._stages.get(name):
            stage.enabled = True

    def disable_stage(self, name: str) -> None:
        """Disable a stage."""
        if stage := self._stages.get(name):
            stage.enabled = False

    async def run_stage(self, name: str) -> None:
        """Run a specific stage."""
        stage = self._stages.get(name)
        if not stage:
            logger.warning(f"Unknown stage: {name}")
            return

        if not stage.enabled:
            logger.debug(f"Stage disabled: {name}")
            return

        logger.info(f"Running pipeline stage: {name}")
        start = datetime.now(UTC)

        try:
            result = stage.handler()
            if asyncio.iscoroutine(result):
                await result

            stage.last_run = datetime.now(UTC)
            stage.run_count += 1

            duration = (datetime.now(UTC) - start).total_seconds()
            logger.info(f"Stage {name} completed in {duration:.2f}s")

        except Exception as e:
            logger.error(f"Stage {name} failed: {e}", exc_info=True)

    async def run_cycle(self) -> None:
        """Run one complete pipeline cycle."""
        for name in ["scan", "analyze", "execute"]:
            if stage := self._stages.get(name):
                if stage.should_run():
                    await self.run_stage(name)

    async def run(self) -> None:
        """Run the pipeline continuously."""
        self._running = True
        logger.info("Pipeline scheduler started")

        await self.run_cycle()

        while self._running:
            await asyncio.sleep(30)
            await self.run_cycle()

    def stop(self) -> None:
        """Stop the pipeline."""
        self._running = False
        logger.info("Pipeline scheduler stopped")

    def status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self._running,
            "stages": {
                name: {
                    "enabled": stage.enabled,
                    "interval_minutes": stage.interval_minutes,
                    "last_run": stage.last_run.isoformat() if stage.last_run else None,
                    "run_count": stage.run_count,
                }
                for name, stage in self._stages.items()
            },
        }
