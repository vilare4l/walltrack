"""Autonomous wallet profiling background worker.

This worker runs continuously in the background, processing wallets
based on their status in the database:

Workflow:
    discovered (Story 3.1)
    → profiled (Story 3.2 + 3.3 analysis)
    → watchlisted/ignored (Story 3.5 auto-evaluation)

The worker:
- Starts automatically with the FastAPI app
- Polls database every 60 seconds for wallets with status='discovered'
- Processes each wallet: performance analysis + behavioral profiling
- Updates wallet status to 'profiled' and triggers watchlist evaluation
- Handles errors gracefully (1 wallet failure doesn't stop the worker)
- Respects RPC rate limits (2 req/sec with exponential backoff)
- Shuts down gracefully on app shutdown

Example:
    # FastAPI app startup (automatic)
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = WalletProfilingWorker()
        task = asyncio.create_task(worker.run())
        yield
        await worker.stop()
        task.cancel()
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog

from walltrack.core.analysis.performance_orchestrator import PerformanceOrchestrator
from walltrack.core.behavioral.profiler import BehavioralProfiler
from walltrack.core.wallets.watchlist import WatchlistEvaluator
from walltrack.data.models.wallet import WalletStatus
from walltrack.data.neo4j.client import get_neo4j_client
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.solana.rpc_client import SolanaRPCClient

log = structlog.get_logger(__name__)


class WalletProfilingWorker:
    """Autonomous background worker for wallet profiling.

    Continuously processes wallets with status='discovered':
    1. Performance analysis (win_rate, pnl_total, timing)
    2. Behavioral profiling (position_size, hold_duration)
    3. Status update to 'profiled'
    4. Auto watchlist evaluation (→ 'watchlisted' or 'ignored')

    Attributes:
        running: Worker running state (True = active).
        poll_interval: Seconds between database polls (default: 60s).
        performance_orchestrator: Story 3.2 performance analysis.
        behavioral_profiler: Story 3.3 behavioral profiling.
        watchlist_evaluator: Story 3.5 watchlist evaluation.
        wallet_repo: Database access for wallet status updates.
    """

    def __init__(
        self,
        poll_interval: int = 60,
    ):
        """Initialize worker with dependencies.

        Args:
            poll_interval: Seconds between database polls (default: 60).
                          Increase for lower DB load, decrease for faster processing.
        """
        self.running = False
        self.poll_interval = poll_interval

        # Dependencies (lazy-initialized in run())
        self.performance_orchestrator: PerformanceOrchestrator | None = None
        self.behavioral_profiler: BehavioralProfiler | None = None
        self.watchlist_evaluator: WatchlistEvaluator | None = None
        self.wallet_repo: WalletRepository | None = None
        self.rpc_client: SolanaRPCClient | None = None
        self.supabase_client = None
        self.neo4j_client = None

        # Status tracking (Story 3.5.6)
        self._last_run: datetime | None = None
        self._processed_last_run: int = 0
        self._errors_last_run: int = 0
        self._current_state: str = "idle"  # idle | processing | stopped | error

        log.info(
            "wallet_profiling_worker_initialized",
            poll_interval_seconds=poll_interval,
        )

    async def _initialize_dependencies(self):
        """Initialize all dependencies (lazy - called once on first run)."""
        log.info("initializing_worker_dependencies")

        # Database clients
        log.debug("profiling_worker_init_supabase")
        self.supabase_client = await get_supabase_client()
        log.debug("profiling_worker_init_neo4j")
        self.neo4j_client = await get_neo4j_client()

        # Repositories
        log.debug("profiling_worker_init_repos")
        config_repo = ConfigRepository(self.supabase_client)
        self.wallet_repo = WalletRepository(client=self.supabase_client)

        # RPC client
        log.debug("profiling_worker_init_rpc")
        self.rpc_client = SolanaRPCClient()

        # Story 3.2: Performance orchestrator
        log.debug("profiling_worker_init_performance_orchestrator")
        self.performance_orchestrator = PerformanceOrchestrator(
            rpc_client=self.rpc_client,
            config_repo=config_repo,
            wallet_repo=self.wallet_repo,
        )

        # Story 3.3: Behavioral profiler
        log.debug("profiling_worker_init_behavioral_profiler")
        self.behavioral_profiler = BehavioralProfiler(
            rpc_client=self.rpc_client,
            config=config_repo,
        )

        # Story 3.5: Watchlist evaluator
        log.debug("profiling_worker_init_watchlist_evaluator")
        self.watchlist_evaluator = WatchlistEvaluator(
            config_repo=config_repo,
        )

        log.info("worker_dependencies_initialized")

    def get_status(self) -> dict:
        """Get worker status for monitoring (Story 3.5.6).

        Returns:
            Status dict with:
                - running: Worker running state
                - last_run: Last successful processing time (or None)
                - processed_count: Items processed in last run
                - error_count: Errors in last run
                - current_state: 'idle' | 'processing' | 'stopped' | 'error'
        """
        return {
            "running": self.running,
            "last_run": self._last_run,
            "processed_count": self._processed_last_run,
            "error_count": self._errors_last_run,
            "current_state": self._current_state,
        }

    async def run(self):
        """Main worker loop - runs until stopped.

        Polls database every {poll_interval} seconds for wallets with
        status='discovered', processes them, and updates status.

        This method runs indefinitely and should be started as a background task:
            asyncio.create_task(worker.run())
        """
        log.info("wallet_profiling_worker_starting")
        self.running = True

        # Lazy initialization
        await self._initialize_dependencies()

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # Update state to processing (Story 3.5.6)
                self._current_state = "processing"

                # Load RPC rate limiting config (Story 3.5.5)
                config_repo = ConfigRepository(self.supabase_client)

                batch_size_value = await config_repo.get_value("profiling_batch_size")
                batch_size = int(batch_size_value) if batch_size_value else 10

                wallet_delay_value = await config_repo.get_value("profiling_wallet_delay_seconds")
                wallet_delay = int(wallet_delay_value) if wallet_delay_value else 10

                # Fetch wallets needing profiling (limit to batch_size)
                all_wallets = await self.wallet_repo.get_wallets_by_status(
                    status=WalletStatus.DISCOVERED
                )
                wallets = all_wallets[:batch_size] if all_wallets else []

                if not wallets:
                    log.debug(
                        "no_wallets_to_profile",
                        status="discovered",
                        next_check_seconds=self.poll_interval,
                    )
                    # No work - reset counters but keep last_run time
                    self._processed_last_run = 0
                    self._errors_last_run = 0
                else:
                    log.info(
                        "wallets_found_for_profiling",
                        count=len(wallets),
                        total_discovered=len(all_wallets),
                        batch_size=batch_size,
                        wallet_delay_seconds=wallet_delay,
                        status="discovered",
                    )

                    # Reset counters for this batch (Story 3.5.6)
                    self._processed_last_run = 0
                    self._errors_last_run = 0

                    # Process each wallet
                    for i, wallet in enumerate(wallets):
                        if not self.running:
                            log.info("worker_stopping_mid_batch")
                            break

                        try:
                            await self._process_wallet(wallet.wallet_address)
                            self._processed_last_run += 1  # Track successful processing

                            # Rate limit: Add configurable delay between wallets (Story 3.5.5)
                            # (except after the last wallet)
                            if i < len(wallets) - 1:
                                log.debug(
                                    "rate_limit_delay_between_wallets",
                                    processed=i + 1,
                                    total=len(wallets),
                                    delay_seconds=wallet_delay,
                                )
                                await asyncio.sleep(wallet_delay)

                        except Exception as wallet_error:
                            log.error(
                                "wallet_processing_error_in_batch",
                                wallet_address=wallet.wallet_address[:8] + "...",
                                error=str(wallet_error),
                            )
                            self._errors_last_run += 1  # Track wallet-level errors

                            # Add delay even on error to avoid hammering RPC
                            if i < len(wallets) - 1:
                                await asyncio.sleep(wallet_delay)

                # Update status tracking (Story 3.5.6)
                self._last_run = datetime.now(UTC)
                self._current_state = "idle"

                # Reset error counter on successful batch
                consecutive_errors = 0

                # Sleep before next poll
                await asyncio.sleep(self.poll_interval)

            except Exception as e:
                consecutive_errors += 1
                self._current_state = "error"  # Update status tracking (Story 3.5.6)
                self._errors_last_run += 1

                log.error(
                    "worker_poll_error",
                    error=str(e),
                    consecutive_errors=consecutive_errors,
                    max_consecutive_errors=max_consecutive_errors,
                )

                # Circuit breaker: Stop if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    log.critical(
                        "worker_stopping_max_errors",
                        consecutive_errors=consecutive_errors,
                    )
                    self.running = False
                    self._current_state = "stopped"  # Update status tracking
                    break

                # Exponential backoff on errors
                backoff = min(2 ** consecutive_errors, 300)  # Max 5 minutes
                log.warning(
                    "worker_error_backoff",
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)

        log.info("wallet_profiling_worker_stopped")

    async def _process_wallet(self, wallet_address: str):
        """Process a single wallet: analyze + profile + watchlist evaluate.

        Args:
            wallet_address: Wallet address to process.

        Handles errors gracefully - a single wallet failure doesn't stop the worker.
        """
        log.info(
            "processing_wallet",
            wallet_address=wallet_address[:8] + "...",
        )

        try:
            # Step 1: Performance Analysis (Story 3.2)
            log.debug("running_performance_analysis", wallet_address=wallet_address[:8] + "...")
            try:
                performance_metrics = await self.performance_orchestrator.analyze_wallet_performance(
                    wallet_address=wallet_address
                )
                log.info(
                    "performance_analysis_complete",
                    wallet_address=wallet_address[:8] + "...",
                    win_rate=performance_metrics.win_rate,
                    pnl_total=performance_metrics.pnl_total,
                )
            except Exception as e:
                log.error(
                    "performance_analysis_failed",
                    wallet_address=wallet_address[:8] + "...",
                    error=str(e),
                )
                # Continue to behavioral profiling even if performance fails
                performance_metrics = None

            # Step 2: Behavioral Profiling (Story 3.3)
            log.debug("running_behavioral_profiling", wallet_address=wallet_address[:8] + "...")
            try:
                behavioral_metrics = await self.behavioral_profiler.analyze(
                    wallet_address=wallet_address
                )
                log.info(
                    "behavioral_profiling_complete",
                    wallet_address=wallet_address[:8] + "...",
                    position_size_style=behavioral_metrics.position_size_style,
                    hold_duration_style=behavioral_metrics.hold_duration_style,
                )
            except Exception as e:
                log.error(
                    "behavioral_profiling_failed",
                    wallet_address=wallet_address[:8] + "...",
                    error=str(e),
                )
                behavioral_metrics = None

            # Step 3: Update status to 'profiled'
            log.debug("updating_wallet_status_profiled", wallet_address=wallet_address[:8] + "...")
            await self.wallet_repo.update_status(
                wallet_address=wallet_address,
                status=WalletStatus.PROFILED,
            )

            # Step 4: Auto Watchlist Evaluation (Story 3.5)
            log.debug("running_watchlist_evaluation", wallet_address=wallet_address[:8] + "...")
            try:
                # Fetch updated wallet with all metrics
                wallet = await self.wallet_repo.get_by_address(wallet_address)

                if wallet:
                    decision = await self.watchlist_evaluator.evaluate_wallet(wallet)

                    # Update wallet with watchlist decision
                    await self.wallet_repo.update_watchlist_status(
                        wallet_address=wallet_address,
                        decision=decision,
                        manual=False,  # Automatic evaluation
                    )

                    log.info(
                        "watchlist_evaluation_complete",
                        wallet_address=wallet_address[:8] + "...",
                        decision_status=decision.status,
                        decision_score=decision.score,
                    )
                else:
                    log.warning(
                        "wallet_not_found_for_watchlist",
                        wallet_address=wallet_address[:8] + "...",
                    )

            except Exception as e:
                log.error(
                    "watchlist_evaluation_failed",
                    wallet_address=wallet_address[:8] + "...",
                    error=str(e),
                )
                # Wallet stays as 'profiled' if watchlist evaluation fails

            log.info(
                "wallet_processing_complete",
                wallet_address=wallet_address[:8] + "...",
            )

        except Exception as e:
            # Catch-all for unexpected errors
            log.error(
                "wallet_processing_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't re-raise - continue to next wallet

    async def stop(self):
        """Stop the worker gracefully.

        Sets running flag to False and waits for current wallet processing to complete.
        """
        log.info("wallet_profiling_worker_stopping")
        self.running = False
        self._current_state = "stopped"  # Update status tracking (Story 3.5.6)

        # Close RPC client
        if self.rpc_client:
            await self.rpc_client.close()

        # Close database clients
        if self.supabase_client:
            await self.supabase_client.close()

        if self.neo4j_client:
            await self.neo4j_client.close()

        log.info("wallet_profiling_worker_stopped")


@asynccontextmanager
async def wallet_profiling_lifespan():
    """Context manager for wallet profiling worker lifecycle.

    Usage in FastAPI app:
        from walltrack.workers.wallet_profiling_worker import wallet_profiling_lifespan

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with wallet_profiling_lifespan():
                yield

        app = FastAPI(lifespan=lifespan)
    """
    worker = WalletProfilingWorker(poll_interval=60)
    task = asyncio.create_task(worker.run())

    log.info("wallet_profiling_worker_started")

    try:
        yield worker
    finally:
        await worker.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        log.info("wallet_profiling_worker_shutdown_complete")
