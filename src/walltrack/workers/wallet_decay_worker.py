"""Autonomous wallet decay detection background worker.

This worker runs continuously in the background, checking wallets for performance
degradation (decay):

Workflow:
    Wallet profiled (Story 3.2+3.3)
    → wallet_status='profiled' or 'watchlisted'
    → WORKER PROCESSES (autonomous, every 4 hours)
    → Decay detected (Story 3.4 logic)
    → decay_status updated (ok/flagged/downgraded/dormant)
    → decay_events logged

The worker:
- Starts automatically with the FastAPI app
- Polls database every 4 hours (14400 seconds) for profiled/watchlisted wallets
- Processes each wallet: checks decay (Story 3.4 logic)
- Updates wallet decay_status and logs events
- Handles errors gracefully (1 wallet failure doesn't stop the worker)
- Circuit breaker stops worker after 5 consecutive errors
- Shuts down gracefully on app shutdown

Example:
    # FastAPI app startup (automatic)
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = WalletDecayWorker(poll_interval=14400)  # 4 hours
        task = asyncio.create_task(worker.run())
        yield
        await worker.stop()
        task.cancel()

Story: 3.4 - Wallet Decay Detection (autonomous worker)
"""

import asyncio
from datetime import UTC, datetime

import structlog

from walltrack.core.wallets.decay_detector import DecayDetector
from walltrack.data.models.wallet import WalletStatus
from walltrack.data.neo4j.client import get_neo4j_client
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.solana.rpc_client import SolanaRPCClient

log = structlog.get_logger(__name__)


class WalletDecayWorker:
    """Autonomous background worker for wallet decay detection.

    Continuously processes profiled/watchlisted wallets:
    1. Fetch profiled/watchlisted wallets from database
    2. For each wallet: check decay (rolling win rate, consecutive losses, dormancy)
    3. Update wallet decay_status and log events
    4. Circuit breaker: stop after 5 consecutive errors
    5. Exponential backoff on errors

    Attributes:
        running: Worker running state (True = active).
        poll_interval: Seconds between database polls (default: 14400s = 4 hours).
        decay_detector: Story 3.4 decay detection service.
        wallet_repo: Database access for wallet status updates.
    """

    def __init__(self, poll_interval: int = 14400):
        """Initialize worker with dependencies.

        Args:
            poll_interval: Seconds between database polls (default: 14400 = 4 hours).
                          Increase for lower DB load, decrease for faster detection.
        """
        self.running = False
        self.poll_interval = poll_interval

        # Dependencies (lazy-initialized in run())
        self.decay_detector: DecayDetector | None = None
        self.wallet_repo: WalletRepository | None = None
        self.decay_event_repo: DecayEventRepository | None = None
        self.supabase_client = None
        self.neo4j_client = None

        # Status tracking (Story 3.5.6)
        self._last_run: datetime | None = None
        self._processed_last_run: int = 0
        self._errors_last_run: int = 0
        self._current_state: str = "idle"  # idle | processing | stopped | error

        log.info(
            "wallet_decay_worker_initialized",
            poll_interval_seconds=poll_interval,
        )

    async def _initialize_dependencies(self):
        """Initialize all dependencies (lazy - called once on first run)."""
        log.info("decay_worker_initializing_dependencies")

        # Database clients
        self.supabase_client = await get_supabase_client()
        self.neo4j_client = await get_neo4j_client()

        # Repositories
        config_repo = ConfigRepository(self.supabase_client)
        self.wallet_repo = WalletRepository(client=self.supabase_client)
        self.decay_event_repo = DecayEventRepository(self.supabase_client)

        # RPC client
        rpc_client = SolanaRPCClient()

        # Story 3.4: Decay detector - load config from DB
        from walltrack.core.wallets.decay_detector import DecayConfig  # noqa: PLC0415

        decay_config = await DecayConfig.from_db(config_repo)
        self.decay_detector = DecayDetector(
            config=decay_config,
            wallet_repo=self.wallet_repo,
            rpc_client=rpc_client,
        )

        log.info("decay_worker_dependencies_initialized")

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

        Polls database every {poll_interval} seconds for wallets needing decay check,
        processes them, and updates status.

        This method runs indefinitely and should be started as a background task:
            asyncio.create_task(worker.run())
        """
        log.info("wallet_decay_worker_starting")
        self.running = True

        # Lazy initialization
        await self._initialize_dependencies()

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # Update state to processing (Story 3.5.6)
                self._current_state = "processing"

                # Fetch wallets needing decay check (profiled + watchlisted)
                profiled_wallets = await self.wallet_repo.get_wallets_by_status(
                    status=WalletStatus.PROFILED
                )
                watchlisted_wallets = await self.wallet_repo.get_wallets_by_status(
                    status=WalletStatus.WATCHLISTED
                )
                wallets = profiled_wallets + watchlisted_wallets

                if not wallets:
                    log.debug(
                        "no_wallets_for_decay_check",
                        next_check_seconds=self.poll_interval,
                    )
                    # No work - reset counters but keep last_run time
                    self._processed_last_run = 0
                    self._errors_last_run = 0
                else:
                    log.info(
                        "wallets_found_for_decay_check",
                        count=len(wallets),
                    )

                    # Reset counters for this batch (Story 3.5.6)
                    self._processed_last_run = 0
                    self._errors_last_run = 0

                    # Process each wallet
                    for wallet in wallets:
                        if not self.running:
                            log.info("worker_stopping_mid_batch")
                            break

                        try:
                            await self._process_wallet(wallet.wallet_address)
                            self._processed_last_run += 1  # Track successful processing
                        except Exception as wallet_error:
                            log.error(
                                "wallet_decay_check_error",
                                wallet_address=wallet.wallet_address[:8] + "...",
                                error=str(wallet_error),
                            )
                            self._errors_last_run += 1  # Track wallet-level errors

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
                    "decay_worker_poll_error",
                    error=str(e),
                    consecutive_errors=consecutive_errors,
                    max_consecutive_errors=max_consecutive_errors,
                )

                # Circuit breaker: Stop if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    log.critical(
                        "decay_worker_stopping_max_errors",
                        consecutive_errors=consecutive_errors,
                    )
                    self.running = False
                    self._current_state = "stopped"  # Update status tracking
                    break

                # Exponential backoff on errors
                backoff = min(2**consecutive_errors, 300)  # Max 5 minutes
                log.warning(
                    "decay_worker_error_backoff",
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)

        log.info("wallet_decay_worker_stopped")

    async def _process_wallet(self, wallet_address: str):
        """Process a single wallet: check decay and update status.

        Args:
            wallet_address: Wallet address to check.

        Error handling:
            - Logs errors but doesn't raise (1 wallet failure ≠ worker crash)
            - Wallet keeps current decay_status if check fails
            - Will be retried on next worker poll
        """
        try:
            log.debug("checking_wallet_decay", wallet_address=wallet_address[:8] + "...")

            # Check wallet decay (Story 3.4 logic)
            decay_event = await self.decay_detector.check_wallet_decay(wallet_address)

            if decay_event:
                log.info(
                    "decay_event_detected",
                    wallet_address=wallet_address[:8] + "...",
                    event_type=decay_event.event_type.value,
                    rolling_win_rate=decay_event.rolling_win_rate,
                )
            else:
                log.debug(
                    "no_decay_event",
                    wallet_address=wallet_address[:8] + "...",
                )

        except Exception as e:
            log.error(
                "wallet_decay_check_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            # Don't re-raise - continue to next wallet

    async def stop(self):
        """Stop the worker gracefully."""
        log.info("wallet_decay_worker_stopping")
        self.running = False
        self._current_state = "stopped"  # Update status tracking (Story 3.5.6)
