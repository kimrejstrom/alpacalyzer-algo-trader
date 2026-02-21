"""Trading orchestrator that coordinates scanning, analysis, and execution."""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

from alpacalyzer.data.models import TopTicker, TradingStrategy
from alpacalyzer.execution.engine import ExecutionConfig, ExecutionEngine
from alpacalyzer.execution.signal_queue import PendingSignal
from alpacalyzer.hedge_fund import call_hedge_fund_agents
from alpacalyzer.pipeline.aggregator import OpportunityAggregator
from alpacalyzer.trading.alpaca_client import get_market_status, get_positions
from alpacalyzer.utils.logger import get_logger

if TYPE_CHECKING:
    from alpacalyzer.strategies.base import Strategy

logger = get_logger(__name__)


class TradingOrchestrator:
    """
    Orchestrates the trading pipeline: scan → analyze → execute.

    This class replaces the monolithic Trader class by coordinating:
    - Opportunity scanning via OpportunityAggregator
    - Hedge fund agent analysis
    - Trade execution via ExecutionEngine

    The orchestrator does not execute trades directly; it delegates all
    execution to the ExecutionEngine.

    Attributes:
        analyze_mode: If True, skip order submission
        direct_tickers: Optional list of tickers to analyze (skips scanning)
        agents: Which agents to run (ALL, TRADE, or INVEST)
        ignore_market_status: If True, run regardless of market status
        aggregator: OpportunityAggregator instance for scanning
        execution_engine: ExecutionEngine instance for trade execution
        recently_exited_tickers: Dict tracking exited tickers for cooldown
        cooldown_period: Time period for ticker cooldown after exit
    """

    def __init__(
        self,
        strategy: "Strategy",
        analyze_mode: bool = False,
        direct_tickers: list[str] | None = None,
        agents: Literal["ALL", "TRADE", "INVEST"] = "ALL",
        ignore_market_status: bool = False,
        reset_state: bool = False,
    ):
        """
        Initialize the TradingOrchestrator.

        Args:
            strategy: Trading strategy for execution
            analyze_mode: If True, skip order submission
            direct_tickers: Optional list of tickers to analyze directly
            agents: Which hedge fund agents to run
            ignore_market_status: If True, run regardless of market status
            reset_state: If True, reset execution engine state on startup
        """
        self.analyze_mode = analyze_mode
        self.direct_tickers = direct_tickers or []
        self.agents = agents
        self.ignore_market_status = ignore_market_status

        # Initialize components
        self.aggregator = OpportunityAggregator()
        self.execution_engine = ExecutionEngine(
            strategy=strategy,
            config=ExecutionConfig(analyze_mode=analyze_mode),
            reset_state=reset_state,
        )

        # Track market status
        self.market_status = get_market_status()
        if self.ignore_market_status:
            self.is_market_open = True
            logger.info("market status checks disabled")
        else:
            self.is_market_open = self.market_status == "open"

        # Cooldown tracking
        self.recently_exited_tickers: dict[str, datetime] = {}
        self.cooldown_period = timedelta(hours=3)

    def scan(self) -> list[TopTicker]:
        """
        Scan for trading opportunities.

        If direct_tickers is provided, creates TopTicker objects directly
        instead of running the aggregator.

        Returns:
            List of TopTicker opportunities
        """
        if not self.is_market_open:
            logger.info(f"scanner paused | market_status={self.market_status}")
            return []

        # If direct tickers provided, skip scanning
        if self.direct_tickers:
            logger.info(f"using direct tickers | tickers={', '.join(self.direct_tickers)}")
            return [
                TopTicker(
                    ticker=ticker,
                    confidence=50.0,
                    signal="neutral",
                    reasoning="Ticker is of interest to the user.",
                )
                for ticker in self.direct_tickers
            ]

        # Run aggregator
        logger.info(f"scanner starting | market_status={self.market_status}")
        self.aggregator.aggregate()
        opportunities = self.aggregator.top(10)

        # Convert Opportunity to TopTicker, preserving scanner signals
        return [
            TopTicker(
                ticker=opp.ticker,
                confidence=min(max(opp.confidence, opp.score), 100),
                signal=opp.signal,
                reasoning=" | ".join(opp.reasoning) if opp.reasoning else f"Score: {opp.score:.2f}, Sources: {', '.join(opp.sources)}",
            )
            for opp in opportunities
        ]

    def analyze(self, opportunities: list[TopTicker]) -> list[TradingStrategy]:
        """
        Analyze opportunities using hedge fund agents.

        Args:
            opportunities: List of TopTicker opportunities to analyze

        Returns:
            List of TradingStrategy objects from hedge fund analysis
        """
        if not self.is_market_open:
            logger.info(f"analysis paused | market_status={self.market_status}")
            return []

        if not opportunities:
            logger.info("no opportunities to analyze")
            return []

        logger.info(f"hedge fund analysis starting | market_status={self.market_status}")

        # Clean up expired cooldowns
        self._cleanup_cooldowns()

        # Get active positions to filter out
        try:
            positions = get_positions()
            active_tickers = [p.symbol for p in positions]
        except Exception as e:
            logger.error(f"fetch positions failed | error={e}")
            active_tickers = []
        cooldown_tickers = list(self.recently_exited_tickers.keys())

        # Filter out already active or in-cooldown tickers
        filtered_opportunities = [opp for opp in opportunities if opp.ticker not in active_tickers and opp.ticker not in cooldown_tickers]

        if not filtered_opportunities:
            logger.info("no new opportunities | reason=all tickers active or in cooldown")
            return []

        # Call hedge fund agents
        hedge_fund_response = call_hedge_fund_agents(filtered_opportunities, self.agents, show_reasoning=True)

        decisions = hedge_fund_response.get("decisions") or {}
        if not decisions:
            logger.info("no trade decisions from hedge fund")
            return []

        # Convert to TradingStrategy objects
        strategies: list[TradingStrategy] = []
        for data in decisions.values():
            strategy_dicts = data.get("strategies", [])
            for strategy_dict in strategy_dicts:
                strategy = TradingStrategy.model_validate(strategy_dict)
                strategies.append(strategy)

        logger.info(f"hedge fund generated strategies | count={len(strategies)}")
        return strategies

    def execute(self, strategies: list[TradingStrategy]) -> None:
        """
        Execute trading strategies via ExecutionEngine.

        Args:
            strategies: List of TradingStrategy objects to execute
        """
        if not strategies:
            logger.info("no strategies to execute")
            return

        logger.info(f"executing strategies | count={len(strategies)}")

        # Convert strategies to signals and add to engine
        for strategy in strategies:
            signal = PendingSignal.from_strategy(strategy, source="hedge_fund")
            self.execution_engine.add_signal(signal)

        # Run execution cycle
        self.execution_engine.run_cycle()

    def run_cycle(self) -> None:
        """Run one full trading cycle: scan → analyze → execute."""
        logger.info("trading cycle starting")

        # Scan
        opportunities = self.scan()
        if not opportunities:
            logger.info("no opportunities found, ending cycle")
            return

        logger.info(f"opportunities found | count={len(opportunities)}")

        # Analyze
        strategies = self.analyze(opportunities)
        if not strategies:
            logger.info("no strategies generated, ending cycle")
            return

        logger.info(f"strategies generated | count={len(strategies)}")

        # Execute
        self.execute(strategies)

        logger.info("trading cycle complete")

    def _cleanup_cooldowns(self) -> None:
        """
        Remove tickers from cooldown if the period has passed.

        Emits CooldownEndedEvent for each ticker that exits cooldown.
        """
        from alpacalyzer.events import CooldownEndedEvent, emit_event

        now = datetime.now(UTC)
        expired_tickers = []

        for ticker, exit_time in list(self.recently_exited_tickers.items()):
            if now > exit_time + self.cooldown_period:
                emit_event(CooldownEndedEvent(timestamp=now, ticker=ticker))
                logger.info(f"cooldown finished | ticker={ticker}")
                expired_tickers.append(ticker)

        # Remove expired entries
        for ticker in expired_tickers:
            del self.recently_exited_tickers[ticker]

    def execute_cycles(self) -> None:
        """Run execution cycles for the execution engine."""
        self.execution_engine.run_cycle()
