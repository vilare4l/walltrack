"""Signal processing pipeline."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from walltrack.models.position import Position
    from walltrack.services.trade.position_sizer import PositionSizer

from walltrack.data.models.wallet import Wallet
from walltrack.data.supabase.repositories.signal_repo import SignalRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.models.position_sizing import PositionSizeRequest
from walltrack.models.signal_filter import (
    FilterStatus,
    ProcessingResult,
)
from walltrack.models.signal_log import SignalLogEntry, SignalStatus
from walltrack.models.threshold import EligibilityStatus
from walltrack.models.token import TokenCharacteristics, TokenSource
from walltrack.services.helius.models import ParsedSwapEvent
from walltrack.services.position_service import PositionService
from walltrack.services.scoring.signal_scorer import SignalScorer
from walltrack.services.scoring.threshold_checker import ThresholdChecker
from walltrack.services.signal.filter import SignalFilter
from walltrack.services.token.fetcher import TokenFetcher

logger = structlog.get_logger(__name__)


class SignalPipeline:
    """
    Main signal processing pipeline.

    Orchestrates filtering, scoring, and trade eligibility.
    Full flow: Filter -> Score -> Threshold -> (optionally) Queue for execution
    """

    def __init__(
        self,
        signal_filter: SignalFilter,
        signal_scorer: SignalScorer,
        threshold_checker: ThresholdChecker,
        wallet_repo: WalletRepository,
        token_fetcher: TokenFetcher,
        signal_repo: SignalRepository | None = None,
        position_service: PositionService | None = None,
        position_sizer: PositionSizer | None = None,
    ) -> None:
        """Initialize signal pipeline with all components.

        Args:
            signal_filter: Signal filter service (Story 3.2)
            signal_scorer: Signal scorer service (Story 3.4)
            threshold_checker: Threshold checker service (Story 3.5)
            wallet_repo: Wallet repository for loading wallet data
            token_fetcher: Token fetcher for loading token characteristics
            signal_repo: Signal repository for logging (optional, Story 9.9)
            position_service: Position service for creating positions (Epic 4)
            position_sizer: Position sizer for calculating trade sizes (Epic 4)
        """
        self.signal_filter = signal_filter
        self.signal_scorer = signal_scorer
        self.threshold_checker = threshold_checker
        self.wallet_repo = wallet_repo
        self.token_fetcher = token_fetcher
        self.signal_repo = signal_repo
        self.position_service = position_service
        self.position_sizer = position_sizer

        # Simple wallet cache (address -> Wallet)
        self._wallet_cache: dict[str, tuple[Wallet, float]] = {}
        self._wallet_cache_ttl = 300.0  # 5 minutes

        # Default exit strategy ID
        self._default_exit_strategy_id = "default-exit-strategy"

    async def process_swap_event(
        self, event: ParsedSwapEvent
    ) -> ProcessingResult:
        """
        Process swap event through the full pipeline.

        Pipeline stages:
        1. Filter: Check if wallet is monitored and not blacklisted
        2. Load: Fetch wallet data and token characteristics
        3. Score: Calculate multi-factor score
        4. Threshold: Check if score meets trade eligibility

        Args:
            event: Parsed swap event from Helius webhook

        Returns:
            ProcessingResult with full pipeline outcome
        """
        start_time = time.perf_counter()

        # Step 1: Filter signal
        filter_result = await self.signal_filter.filter_signal(event)

        if filter_result.status != FilterStatus.PASSED:
            processing_time = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "signal_filtered_out",
                status=filter_result.status.value,
                wallet=event.wallet_address[:8] + "...",
            )
            result = ProcessingResult(
                passed=False,
                reason=filter_result.status.value,
                tx_signature=event.tx_signature,
                wallet_address=event.wallet_address,
                token_address=event.token_address,
                processing_time_ms=processing_time,
            )
            await self._log_signal(event, result)
            return result

        # Create enriched signal context
        signal_context = self.signal_filter.create_signal_context(
            event, filter_result
        )

        logger.debug(
            "signal_passed_filter",
            wallet=event.wallet_address[:8] + "...",
            token=event.token_address[:8] + "...",
            direction=event.direction.value,
        )

        # Step 2: Load enrichment data
        wallet = await self._load_wallet_data(event.wallet_address)
        token = await self._load_token_data(event.token_address)

        # Step 3: Score signal
        try:
            scored_signal = await self.signal_scorer.score(
                signal=signal_context,
                wallet=wallet,
                token=token,
            )
        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                "signal_scoring_failed",
                wallet=event.wallet_address[:8] + "...",
                error=str(e),
            )
            result = ProcessingResult(
                passed=False,
                reason=f"scoring_error: {e!s}",
                tx_signature=event.tx_signature,
                wallet_address=event.wallet_address,
                token_address=event.token_address,
                processing_time_ms=processing_time,
            )
            await self._log_signal(event, result)
            return result

        # Step 4: Apply threshold
        threshold_result = self.threshold_checker.check(
            scored_signal=scored_signal,
            token=token,
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Build result based on threshold outcome
        if threshold_result.eligibility_status == EligibilityStatus.BELOW_THRESHOLD:
            logger.info(
                "signal_below_threshold",
                wallet=event.wallet_address[:8] + "...",
                token=event.token_address[:8] + "...",
                score=f"{scored_signal.final_score:.3f}",
                threshold=threshold_result.threshold_used,
                failures=threshold_result.filter_failures,
            )
            result = ProcessingResult(
                passed=False,
                reason="below_threshold",
                tx_signature=event.tx_signature,
                wallet_address=event.wallet_address,
                token_address=event.token_address,
                score=scored_signal.final_score,
                wallet_score=scored_signal.wallet_score.score,
                token_score=scored_signal.token_score.score,
                cluster_score=scored_signal.cluster_score.score,
                context_score=scored_signal.context_score.score,
                processing_time_ms=processing_time,
            )
            await self._log_signal(event, result)
            return result

        # Signal passed threshold - eligible for trading
        logger.info(
            "signal_trade_eligible",
            wallet=event.wallet_address[:8] + "...",
            token=event.token_address[:8] + "...",
            direction=event.direction.value,
            score=f"{scored_signal.final_score:.3f}",
            conviction=threshold_result.conviction_tier.value,
            multiplier=threshold_result.position_multiplier,
        )

        result = ProcessingResult(
            passed=True,
            reason="trade_eligible",
            tx_signature=event.tx_signature,
            wallet_address=event.wallet_address,
            token_address=event.token_address,
            score=scored_signal.final_score,
            wallet_score=scored_signal.wallet_score.score,
            token_score=scored_signal.token_score.score,
            cluster_score=scored_signal.cluster_score.score,
            context_score=scored_signal.context_score.score,
            conviction_tier=threshold_result.conviction_tier.value,
            position_multiplier=threshold_result.position_multiplier,
            trade_queued=False,
            processing_time_ms=processing_time,
        )

        # Log signal and store ID
        signal_id = await self._log_signal(event, result)
        if signal_id:
            result.signal_id = signal_id

        # Create position for BUY signals if position service is available
        if (
            self.position_service is not None
            and event.direction.value == "buy"
            and signal_id
        ):
            position = await self._create_position_from_signal(
                event=event,
                signal_id=signal_id,
                final_score=scored_signal.final_score,
                conviction_tier=threshold_result.conviction_tier.value,
                token=token,
            )
            if position:
                result.trade_queued = True
                result.position_id = position.id
                logger.info(
                    "position_created_from_signal",
                    signal_id=signal_id,
                    position_id=position.id,
                    simulated=position.simulated,
                    entry_sol=position.entry_amount_sol,
                )

        return result

    async def _log_signal(
        self,
        event: ParsedSwapEvent,
        result: ProcessingResult,
    ) -> str | None:
        """Log processed signal to repository.

        Args:
            event: Original swap event
            result: Processing result

        Returns:
            Signal ID if logged, None if repo not configured or error
        """
        if self.signal_repo is None:
            return None

        try:
            # Determine status and eligibility
            if not result.passed:
                if result.reason.startswith("scoring_error"):
                    status = SignalStatus.FAILED
                elif result.reason == "below_threshold":
                    status = SignalStatus.BELOW_THRESHOLD
                else:
                    status = SignalStatus.FILTERED_OUT
            else:
                status = SignalStatus.TRADE_ELIGIBLE

            entry = SignalLogEntry(
                tx_signature=event.tx_signature,
                wallet_address=event.wallet_address,
                token_address=event.token_address,
                direction=event.direction.value,
                amount_token=event.amount_token,
                amount_sol=event.amount_sol,
                slot=event.slot,
                final_score=result.score,
                wallet_score=result.wallet_score,
                cluster_score=result.cluster_score,
                token_score=result.token_score,
                context_score=result.context_score,
                status=status,
                eligibility_status=result.reason,
                conviction_tier=result.conviction_tier,
                filter_status=result.reason if not result.passed else "passed",
                filter_reason=result.reason if not result.passed else None,
                timestamp=event.timestamp,
                received_at=datetime.now(UTC),
                processing_time_ms=result.processing_time_ms,
            )

            signal_id = await self.signal_repo.save(entry)
            return signal_id

        except Exception as e:
            logger.warning(
                "signal_logging_failed",
                tx=event.tx_signature[:8] + "...",
                error=str(e),
            )
            return None

    async def _create_position_from_signal(
        self,
        event: ParsedSwapEvent,
        signal_id: str,
        final_score: float,
        conviction_tier: str,
        token: TokenCharacteristics,
    ) -> Position | None:
        """Create a position from a trade-eligible signal.

        Uses PositionSizer to calculate proper position size based on:
        - Signal score and conviction tier
        - Available balance and current allocations
        - Configured multipliers and limits

        Args:
            event: Swap event that triggered the signal
            signal_id: ID of the logged signal
            final_score: Signal final score for sizing calculation
            conviction_tier: "high" or "standard"
            token: Token characteristics for symbol

        Returns:
            Position if created, None if sizing fails or limits exceeded
        """
        if self.position_service is None:
            return None

        try:
            # Calculate entry price (SOL per token)
            if event.amount_token > 0:
                entry_price = event.amount_sol / event.amount_token
            else:
                logger.warning(
                    "invalid_token_amount",
                    signal_id=signal_id,
                    amount_token=event.amount_token,
                )
                return None

            # Calculate position size using PositionSizer
            if self.position_sizer is not None:
                # Get current positions to check limits
                active_positions = await self.position_service.get_active_positions()
                current_allocated = sum(p.entry_amount_sol for p in active_positions)

                # TODO: Get actual wallet balance in production
                # For simulation, use a reasonable default balance
                simulated_balance = 10.0  # 10 SOL simulated balance

                size_request = PositionSizeRequest(
                    signal_score=final_score,
                    available_balance_sol=simulated_balance,
                    current_position_count=len(active_positions),
                    current_allocated_sol=current_allocated,
                    token_address=event.token_address,
                    signal_id=signal_id,
                )

                size_result = await self.position_sizer.calculate_size(size_request)

                if not size_result.should_trade:
                    logger.info(
                        "position_sizing_rejected",
                        signal_id=signal_id,
                        decision=size_result.decision.value,
                        reason=size_result.reason,
                    )
                    return None

                entry_amount_sol = size_result.final_size_sol
                entry_amount_tokens = entry_amount_sol / entry_price

                logger.info(
                    "position_size_calculated",
                    signal_id=signal_id,
                    base_size=size_result.base_size_sol,
                    multiplier=size_result.multiplier,
                    final_size=size_result.final_size_sol,
                    conviction=size_result.conviction_tier.value,
                )
            else:
                # Fallback: use event amounts if no sizer available
                entry_amount_sol = event.amount_sol
                entry_amount_tokens = event.amount_token
                logger.warning(
                    "position_sizer_not_available",
                    signal_id=signal_id,
                    using_event_amounts=True,
                )

            # Get token symbol if available
            token_symbol = getattr(token, "symbol", None)

            # Create position (simulated flag set automatically by PositionService)
            position = await self.position_service.create_position(
                signal_id=signal_id,
                token_address=event.token_address,
                entry_price=entry_price,
                entry_amount_sol=entry_amount_sol,
                entry_amount_tokens=entry_amount_tokens,
                exit_strategy_id=self._default_exit_strategy_id,
                conviction_tier=conviction_tier,
                token_symbol=token_symbol,
            )

            return position

        except Exception as e:
            logger.error(
                "position_creation_failed",
                signal_id=signal_id,
                error=str(e),
            )
            return None

    async def _load_wallet_data(self, address: str) -> Wallet:
        """Load wallet data for scoring with caching.

        Args:
            address: Wallet address

        Returns:
            Wallet with profile data, or default wallet if not found
        """
        # Check cache
        now = time.time()
        if address in self._wallet_cache:
            wallet, cached_at = self._wallet_cache[address]
            if now - cached_at < self._wallet_cache_ttl:
                return wallet

        # Load from repository
        wallet_data = await self.wallet_repo.get_by_address(address)

        if wallet_data is None:
            # Return default wallet for unknown addresses
            from walltrack.data.models.wallet import (  # noqa: PLC0415
                WalletProfile,
                WalletStatus,
            )

            wallet_data = Wallet(
                address=address,
                status=WalletStatus.ACTIVE,
                score=0.3,  # Conservative default
                profile=WalletProfile(),
            )
            logger.debug(
                "wallet_not_found_using_defaults",
                address=address[:8] + "...",
            )

        # Cache result
        self._wallet_cache[address] = (wallet_data, now)

        # Cleanup old entries if cache is large
        if len(self._wallet_cache) > 1000:
            self._cleanup_wallet_cache()

        return wallet_data

    async def _load_token_data(self, mint: str) -> TokenCharacteristics:
        """Load token characteristics for scoring.

        Args:
            mint: Token mint address

        Returns:
            TokenCharacteristics with liquidity, market cap, etc.
        """
        try:
            result = await self.token_fetcher.fetch(mint)
            if result.success and result.token:
                return result.token
        except Exception as e:
            logger.warning(
                "token_fetch_failed",
                mint=mint[:8] + "...",
                error=str(e),
            )

        # Return conservative defaults
        return TokenCharacteristics(
            token_address=mint,
            source=TokenSource.FALLBACK_NEUTRAL,
            is_honeypot=True,  # Assume worst case
            is_new_token=True,
        )

    def _cleanup_wallet_cache(self) -> None:
        """Remove expired entries from wallet cache."""
        now = time.time()
        expired = [
            addr
            for addr, (_, cached_at) in self._wallet_cache.items()
            if now - cached_at > self._wallet_cache_ttl
        ]
        for addr in expired:
            del self._wallet_cache[addr]


# Singleton pipeline instance
_pipeline: SignalPipeline | None = None


async def get_pipeline() -> SignalPipeline:
    """Get or create signal pipeline singleton."""
    global _pipeline

    if _pipeline is None:
        # Lazy imports to avoid circular dependencies
        from walltrack.data.supabase.client import (  # noqa: PLC0415
            get_supabase_client,
        )
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )
        from walltrack.services.position_service import (  # noqa: PLC0415
            get_position_service,
        )
        from walltrack.services.scoring.signal_scorer import (  # noqa: PLC0415
            SignalScorer,
        )
        from walltrack.services.scoring.threshold_checker import (  # noqa: PLC0415
            ThresholdChecker,
        )
        from walltrack.services.signal.wallet_cache import (  # noqa: PLC0415
            WalletCache,
        )
        from walltrack.services.token.fetcher import (  # noqa: PLC0415
            get_token_fetcher,
        )
        from walltrack.services.trade.position_sizer import (  # noqa: PLC0415
            get_position_sizer,
        )

        # Initialize Supabase client and repositories
        client = await get_supabase_client()
        wallet_repo = WalletRepository(client)
        signal_repo = SignalRepository(client)

        # Initialize wallet cache for filter
        wallet_cache = WalletCache(wallet_repo)
        await wallet_cache.initialize()

        # Create all pipeline components
        signal_filter = SignalFilter(wallet_cache)
        signal_scorer = SignalScorer()
        threshold_checker = ThresholdChecker()
        token_fetcher = await get_token_fetcher()
        position_service = await get_position_service()
        position_sizer = await get_position_sizer()

        _pipeline = SignalPipeline(
            signal_filter=signal_filter,
            signal_scorer=signal_scorer,
            threshold_checker=threshold_checker,
            wallet_repo=wallet_repo,
            token_fetcher=token_fetcher,
            signal_repo=signal_repo,
            position_service=position_service,
            position_sizer=position_sizer,
        )

        logger.info("signal_pipeline_initialized")

    return _pipeline


async def reset_pipeline() -> None:
    """Reset pipeline singleton (for testing)."""
    global _pipeline
    _pipeline = None
