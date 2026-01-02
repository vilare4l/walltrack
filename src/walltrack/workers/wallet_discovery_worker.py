"""Autonomous wallet discovery background worker.

This worker runs continuously in the background, discovering wallets from tokens
that haven't been processed yet:

Workflow:
    Token created (Story 2.1-2.2)
    → wallets_discovered=false
    → WORKER PROCESSES (autonomous)
    → Wallets discovered (Story 3.1)
    → wallets_discovered=true
    → Profiling worker processes next (Story 3.2+3.3)

The worker:
- Starts automatically with the FastAPI app
- Polls database every 120 seconds for tokens with wallets_discovered=false
- Processes each token: discovers smart money wallets (Story 3.1 logic)
- Updates token to wallets_discovered=true
- Handles errors gracefully (1 token failure doesn't stop the worker)
- Circuit breaker stops worker after 5 consecutive errors
- Respects RPC rate limits (2 req/sec global rate limiter)
- Shuts down gracefully on app shutdown

Example:
    # FastAPI app startup (automatic)
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        worker = WalletDiscoveryWorker(poll_interval=120)
        task = asyncio.create_task(worker.run())
        yield
        await worker.stop()
        task.cancel()

Story: 3.5.5 - Global RPC Rate Limiter + Wallet Discovery Worker
"""

import asyncio
from datetime import UTC, datetime

import structlog

from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.data.supabase.repositories.token_repo import TokenRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.solana.rpc_client import SolanaRPCClient

log = structlog.get_logger(__name__)


class WalletDiscoveryWorker:
    """Autonomous background worker for wallet discovery from tokens.

    Continuously processes tokens with wallets_discovered=false:
    1. Fetch undiscovered tokens from database
    2. For each token: discover smart money wallets (RPC analysis)
    3. Update token: wallets_discovered=true
    4. Circuit breaker: stop after 5 consecutive errors
    5. Exponential backoff on errors

    Attributes:
        running: Worker running state (True = active).
        poll_interval: Seconds between database polls (default: 120s = 2 minutes).
        discovery_service: Story 3.1 wallet discovery service.
        token_repo: Database access for token status updates.
    """

    def __init__(self, poll_interval: int = 120):
        """Initialize worker with dependencies.

        Args:
            poll_interval: Seconds between database polls (default: 120).
                          Increase for lower DB load, decrease for faster processing.
        """
        self.running = False
        self.poll_interval = poll_interval

        # Dependencies (lazy-initialized in run())
        self.discovery_service: WalletDiscoveryService | None = None
        self.token_repo: TokenRepository | None = None
        self.supabase_client = None

        # Status tracking (Story 3.5.6)
        self._last_run: datetime | None = None
        self._processed_last_run: int = 0
        self._errors_last_run: int = 0
        self._current_state: str = "idle"  # idle | processing | stopped | error

        log.info(
            "wallet_discovery_worker_initialized",
            poll_interval_seconds=poll_interval,
        )

    async def _initialize_dependencies(self):
        """Initialize all dependencies (lazy - called once on first run)."""
        log.info("initializing_worker_dependencies")

        # Database clients
        self.supabase_client = await get_supabase_client()

        # Repositories
        self.token_repo = TokenRepository(self.supabase_client)
        wallet_repo = WalletRepository(self.supabase_client)
        config_repo = ConfigRepository(self.supabase_client)

        # RPC client (shared global rate limiter via Story 3.5.5)
        rpc_client = SolanaRPCClient()

        # Discovery service (Story 3.1)
        self.discovery_service = WalletDiscoveryService(
            rpc_client=rpc_client,
            wallet_repository=wallet_repo,
            config_repository=config_repo,
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

        Polls database every {poll_interval} seconds for tokens with
        wallets_discovered=false, processes them, and updates status.

        This method runs indefinitely and should be started as a background task:
            asyncio.create_task(worker.run())
        """
        log.info("wallet_discovery_worker_starting")
        self.running = True

        # Lazy initialization
        await self._initialize_dependencies()

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self.running:
            try:
                # Update state to processing (Story 3.5.6)
                self._current_state = "processing"

                # Fetch tokens needing discovery
                tokens = await self.token_repo.get_undiscovered_tokens()

                if not tokens:
                    log.debug(
                        "no_tokens_needing_discovery",
                        next_check_seconds=self.poll_interval,
                    )
                    # No work - reset counters but keep last_run time
                    self._processed_last_run = 0
                    self._errors_last_run = 0
                else:
                    log.info(
                        "tokens_found_for_discovery",
                        count=len(tokens),
                    )

                    # Reset counters for this batch (Story 3.5.6)
                    self._processed_last_run = 0
                    self._errors_last_run = 0

                    # Process each token
                    for token in tokens:
                        if not self.running:
                            log.info("worker_stopping_mid_batch")
                            break

                        try:
                            await self._process_token(token.mint)
                            self._processed_last_run += 1  # Track successful processing
                        except Exception as token_error:
                            log.error(
                                "token_processing_error_in_batch",
                                mint=token.mint[:8] + "...",
                                error=str(token_error),
                            )
                            self._errors_last_run += 1  # Track token-level errors

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
                backoff = min(2**consecutive_errors, 300)  # Max 5 minutes
                log.warning(
                    "worker_error_backoff",
                    backoff_seconds=backoff,
                )
                await asyncio.sleep(backoff)

        log.info("wallet_discovery_worker_stopped")

    async def _process_token(self, token_mint: str):
        """Process a single token: discover wallets and update status.

        Args:
            token_mint: Solana token mint address.

        Error handling:
            - Logs errors but doesn't raise (1 token failure ≠ worker crash)
            - Token stays wallets_discovered=false if discovery fails
            - Will be retried on next worker poll
        """
        try:
            log.info("processing_token", mint=token_mint[:8] + "...")

            # Discover wallets from token (Story 3.1 logic)
            result = await self.discovery_service.discover_wallets_from_token(
                token_address=token_mint
            )

            wallets_discovered = result.get("wallets_discovered", 0)
            wallets_stored = result.get("wallets_stored", 0)

            log.info(
                "token_discovery_complete",
                mint=token_mint[:8] + "...",
                wallets_discovered=wallets_discovered,
                wallets_stored=wallets_stored,
            )

            # Mark token as processed
            await self.token_repo.mark_wallets_discovered(token_mint)

        except Exception as e:
            log.error(
                "token_discovery_failed",
                mint=token_mint[:8] + "...",
                error=str(e),
            )
            # Don't re-raise - continue to next token

    async def stop(self):
        """Stop the worker gracefully.

        Sets running flag to False and waits for current token processing to complete.
        """
        log.info("wallet_discovery_worker_stopping")
        self.running = False
        self._current_state = "stopped"  # Update status tracking (Story 3.5.6)

        # Close RPC client (if discovery service has one)
        if self.discovery_service and self.discovery_service.rpc_client:
            await self.discovery_service.rpc_client.close()

        # Close database client
        if self.supabase_client:
            await self.supabase_client.disconnect()

        log.info("wallet_discovery_worker_stopped")
