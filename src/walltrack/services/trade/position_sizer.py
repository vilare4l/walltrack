"""Position sizing service with conviction-based multipliers.

Implements FR20: Dynamic position sizing based on signal score.
Features:
- Score-based conviction tiers (HIGH >= 0.85, STANDARD 0.70-0.84)
- Configurable multipliers (1.5x high, 1.0x standard)
- Validation against balance and concurrent position limits
- Hot-reload configuration from database
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog

from walltrack.config.position_settings import PositionSettings, get_position_settings
from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.data.supabase.repositories.position_config_repo import (
    PositionConfigRepository,
)
from walltrack.models.position_sizing import (
    ConvictionTier,
    PositionSizeAudit,
    PositionSizeRequest,
    PositionSizeResult,
    PositionSizingConfig,
    SizingDecision,
)

logger = structlog.get_logger(__name__)


class PositionSizer:
    """Calculates dynamic position sizes based on signal conviction.

    Features:
    - Score-based multipliers (1.5x for high conviction, 1.0x standard)
    - Validation against balance and limits
    - Graceful handling of insufficient balance
    - Hot-reload config from database
    """

    def __init__(
        self,
        settings: PositionSettings | None = None,
        config_repo: PositionConfigRepository | None = None,
    ) -> None:
        """Initialize position sizer.

        Args:
            settings: Position settings from environment
            config_repo: Repository for config persistence
        """
        self._settings = settings or get_position_settings()
        self._config_repo = config_repo
        self._config_cache: PositionSizingConfig | None = None
        self._cache_lock = asyncio.Lock()
        self._cache_updated: datetime | None = None

    async def initialize(self, client: SupabaseClient | None = None) -> None:
        """Initialize with database connection.

        Args:
            client: Optional Supabase client (will create if not provided)
        """
        if self._config_repo is None:
            if client is None:
                client = await get_supabase_client()
            self._config_repo = PositionConfigRepository(client)

        # Load initial config
        await self._refresh_config()
        logger.info("position_sizer_initialized")

    async def _refresh_config(self) -> PositionSizingConfig:
        """Refresh config from database with caching.

        Returns:
            Current configuration
        """
        async with self._cache_lock:
            now = datetime.now(UTC)

            # Check if cache is still valid
            if (
                self._config_cache is not None
                and self._cache_updated is not None
                and (now - self._cache_updated).total_seconds()
                < self._settings.config_cache_ttl_seconds
            ):
                return self._config_cache

            # Fetch from database
            try:
                if self._config_repo:
                    self._config_cache = await self._config_repo.get_config()
                    self._cache_updated = now
                    logger.debug("position_config_refreshed")
            except Exception as e:
                logger.warning("position_config_refresh_failed", error=str(e))
                # Use defaults if DB fails
                if self._config_cache is None:
                    self._config_cache = PositionSizingConfig()

            if self._config_cache is None:
                self._config_cache = PositionSizingConfig()

            return self._config_cache

    async def get_config(self) -> PositionSizingConfig:
        """Get current position sizing config.

        Returns:
            Current configuration
        """
        return await self._refresh_config()

    def _determine_conviction_tier(
        self,
        score: float,
        config: PositionSizingConfig,
    ) -> ConvictionTier:
        """Determine conviction tier from score.

        Args:
            score: Signal score (0.0-1.0)
            config: Current configuration

        Returns:
            ConvictionTier based on thresholds
        """
        if score >= config.high_conviction_threshold:
            return ConvictionTier.HIGH
        elif score >= config.min_conviction_threshold:
            return ConvictionTier.STANDARD
        else:
            return ConvictionTier.NONE

    def _get_multiplier(
        self,
        tier: ConvictionTier,
        config: PositionSizingConfig,
    ) -> float:
        """Get multiplier for conviction tier.

        Args:
            tier: Conviction tier
            config: Current configuration

        Returns:
            Position size multiplier
        """
        if tier == ConvictionTier.HIGH:
            return config.high_conviction_multiplier
        elif tier == ConvictionTier.STANDARD:
            return config.standard_conviction_multiplier
        else:
            return 0.0

    async def calculate_size(
        self,
        request: PositionSizeRequest,
        audit: bool = True,
    ) -> PositionSizeResult:
        """Calculate position size for a signal.

        Args:
            request: Position size request with score and balance info
            audit: Whether to save audit entry (default True)

        Returns:
            PositionSizeResult with final size and decision
        """
        config = await self._refresh_config()

        # Step 1: Determine conviction tier
        tier = self._determine_conviction_tier(request.signal_score, config)

        # Skip if score too low
        if tier == ConvictionTier.NONE:
            logger.info(
                "position_skipped_low_score",
                score=request.signal_score,
                threshold=config.min_conviction_threshold,
            )
            result = PositionSizeResult(
                decision=SizingDecision.SKIPPED_LOW_SCORE,
                conviction_tier=tier,
                base_size_sol=0,
                multiplier=0,
                calculated_size_sol=0,
                final_size_sol=0,
                capital_used_for_base=0,
                reason=f"Score {request.signal_score:.2f} below threshold "
                f"{config.min_conviction_threshold}",
            )
            await self._maybe_audit(request, config, result, audit)
            return result

        # Step 2: Check concurrent position limit
        if request.current_position_count >= config.max_concurrent_positions:
            logger.info(
                "position_skipped_max_positions",
                current=request.current_position_count,
                max=config.max_concurrent_positions,
            )
            result = PositionSizeResult(
                decision=SizingDecision.SKIPPED_MAX_POSITIONS,
                conviction_tier=tier,
                base_size_sol=0,
                multiplier=self._get_multiplier(tier, config),
                calculated_size_sol=0,
                final_size_sol=0,
                capital_used_for_base=0,
                reason=f"Max positions reached ({config.max_concurrent_positions})",
            )
            await self._maybe_audit(request, config, result, audit)
            return result

        # Step 3: Calculate base size
        # Available capital = balance - reserve - already allocated
        usable_balance = max(0, request.available_balance_sol - config.reserve_sol)
        available_for_new = max(0, usable_balance - request.current_allocated_sol)

        # Check max capital allocation
        total_capital = request.available_balance_sol + request.current_allocated_sol
        max_allocation = total_capital * (config.max_capital_allocation_pct / 100)
        remaining_allocation = max(0, max_allocation - request.current_allocated_sol)

        # Capital to use for base calculation
        capital_for_base = min(available_for_new, remaining_allocation)

        # Base size as % of capital
        base_size = capital_for_base * (config.base_position_pct / 100)

        # Step 4: Apply conviction multiplier
        multiplier = self._get_multiplier(tier, config)
        calculated_size = base_size * multiplier

        # Step 5: Apply limits
        final_size = calculated_size
        reduction_applied = False
        reduction_reason: str | None = None

        # Max position limit
        if final_size > config.max_position_sol:
            final_size = config.max_position_sol
            reduction_applied = True
            reduction_reason = f"Capped at max_position_sol ({config.max_position_sol})"

        # Available balance limit
        if final_size > available_for_new:
            final_size = available_for_new
            reduction_applied = True
            reduction_reason = f"Limited by available balance ({available_for_new:.4f})"

        # Step 6: Check minimum
        if final_size < config.min_position_sol:
            if available_for_new < config.min_position_sol:
                logger.info(
                    "position_skipped_no_balance",
                    final_size=final_size,
                    min_size=config.min_position_sol,
                    available=available_for_new,
                )
                result = PositionSizeResult(
                    decision=SizingDecision.SKIPPED_NO_BALANCE,
                    conviction_tier=tier,
                    base_size_sol=base_size,
                    multiplier=multiplier,
                    calculated_size_sol=calculated_size,
                    final_size_sol=0,
                    capital_used_for_base=capital_for_base,
                    reason=f"Insufficient balance ({available_for_new:.4f} SOL)",
                )
                await self._maybe_audit(request, config, result, audit)
                return result
            else:
                logger.info(
                    "position_skipped_min_size",
                    final_size=final_size,
                    min_size=config.min_position_sol,
                )
                result = PositionSizeResult(
                    decision=SizingDecision.SKIPPED_MIN_SIZE,
                    conviction_tier=tier,
                    base_size_sol=base_size,
                    multiplier=multiplier,
                    calculated_size_sol=calculated_size,
                    final_size_sol=0,
                    capital_used_for_base=capital_for_base,
                    reason=f"Size {final_size:.4f} below minimum {config.min_position_sol}",
                )
                await self._maybe_audit(request, config, result, audit)
                return result

        # Step 7: Determine final decision
        decision = SizingDecision.REDUCED if reduction_applied else SizingDecision.APPROVED

        logger.info(
            "position_size_calculated",
            decision=decision.value,
            tier=tier.value,
            score=request.signal_score,
            base_size=round(base_size, 4),
            multiplier=multiplier,
            final_size=round(final_size, 4),
        )

        result = PositionSizeResult(
            decision=decision,
            conviction_tier=tier,
            base_size_sol=base_size,
            multiplier=multiplier,
            calculated_size_sol=calculated_size,
            final_size_sol=final_size,
            capital_used_for_base=capital_for_base,
            reduction_applied=reduction_applied,
            reduction_reason=reduction_reason,
        )

        await self._maybe_audit(request, config, result, audit)
        return result

    async def _maybe_audit(
        self,
        request: PositionSizeRequest,
        config: PositionSizingConfig,
        result: PositionSizeResult,
        should_audit: bool,
    ) -> None:
        """Optionally save audit entry.

        Args:
            request: Original request
            config: Config at time of calculation
            result: Calculation result
            should_audit: Whether to save audit
        """
        if not should_audit or not self._config_repo:
            return

        try:
            audit = PositionSizeAudit(
                signal_id=request.signal_id,
                token_address=request.token_address,
                signal_score=request.signal_score,
                available_balance_sol=request.available_balance_sol,
                current_position_count=request.current_position_count,
                current_allocated_sol=request.current_allocated_sol,
                config_snapshot=config.model_dump(),
                result=result,
            )
            await self._config_repo.save_audit(audit)
        except Exception as e:
            logger.warning("position_audit_save_failed", error=str(e))

    async def update_config(self, config: PositionSizingConfig) -> PositionSizingConfig:
        """Update position sizing configuration.

        Args:
            config: New configuration

        Returns:
            Updated configuration
        """
        if not self._config_repo:
            raise ValueError("Config repository not initialized")

        config.updated_at = datetime.now(UTC)
        updated = await self._config_repo.save_config(config)

        # Invalidate cache
        async with self._cache_lock:
            self._config_cache = updated
            self._cache_updated = datetime.now(UTC)

        logger.info(
            "position_config_updated",
            base_pct=config.base_position_pct,
            high_mult=config.high_conviction_multiplier,
        )

        return updated


# Singleton
_position_sizer: PositionSizer | None = None


async def get_position_sizer() -> PositionSizer:
    """Get or create position sizer singleton.

    Returns:
        Initialized PositionSizer instance
    """
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()
        await _position_sizer.initialize()
    return _position_sizer
