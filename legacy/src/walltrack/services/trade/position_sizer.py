"""Position sizing service with conviction-based multipliers.

Implements FR20: Dynamic position sizing based on signal score.
Features:
- Score-based conviction tiers (HIGH >= 0.85, STANDARD 0.70-0.84)
- Configurable multipliers (1.5x high, 1.0x standard)
- Validation against balance and concurrent position limits
- Hot-reload configuration from database
- Story 10.5-9: Drawdown-based size reduction
- Story 10.5-10: Daily loss limit enforcement
- Story 10.5-11: Concentration limits
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
    ConcentrationMetrics,
    ConvictionTier,
    DailyLossMetrics,
    DrawdownMetrics,
    PositionSizeAudit,
    PositionSizeRequest,
    PositionSizeResult,
    PositionSizingConfig,
    SizingDecision,
    SizingMode,
)
from walltrack.services.risk.concentration_checker import ConcentrationChecker
from walltrack.services.risk.daily_loss_tracker import DailyLossTracker
from walltrack.services.risk.drawdown_calculator import DrawdownCalculator

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
        drawdown_calculator: DrawdownCalculator | None = None,
        daily_loss_tracker: DailyLossTracker | None = None,
        concentration_checker: ConcentrationChecker | None = None,
    ) -> None:
        """Initialize position sizer.

        Args:
            settings: Position settings from environment
            config_repo: Repository for config persistence
            drawdown_calculator: Optional drawdown calculator for size reduction
            daily_loss_tracker: Optional daily loss tracker for limit enforcement
            concentration_checker: Optional concentration checker for limit enforcement
        """
        self._settings = settings or get_position_settings()
        self._config_repo = config_repo
        self._drawdown_calculator = drawdown_calculator
        self._daily_loss_tracker = daily_loss_tracker
        self._concentration_checker = concentration_checker
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

    async def _apply_drawdown_reduction(
        self,
        size_sol: float,
        config: PositionSizingConfig,
        current_capital_sol: float | None = None,
    ) -> tuple[float, float, DrawdownMetrics | None, bool]:
        """Apply drawdown-based size reduction.

        Story 10.5-9: Reduces position size based on drawdown tiers.

        Args:
            size_sol: Original position size in SOL
            config: Current configuration
            current_capital_sol: Optional current capital for drawdown calc

        Returns:
            Tuple of (reduced_size, reduction_pct, drawdown_metrics, is_blocked)
        """
        # Check if reduction is enabled
        if not config.drawdown_reduction_enabled:
            return size_sol, 0.0, None, False

        # Get or create drawdown calculator
        if self._drawdown_calculator is None:
            self._drawdown_calculator = DrawdownCalculator(
                lookback_days=config.drawdown_lookback_days,
            )

        # Calculate current drawdown
        metrics = await self._drawdown_calculator.calculate(
            current_capital_sol=current_capital_sol,
        )

        # No reduction needed if at peak
        if metrics.is_at_peak:
            return size_sol, 0.0, metrics, False

        # Find active tier
        active_tier = None
        for tier in config.drawdown_reduction_tiers:
            if metrics.drawdown_pct >= tier.threshold_pct:
                active_tier = tier
            else:
                break

        # No tier applies
        if active_tier is None:
            return size_sol, 0.0, metrics, False

        # Check if trading blocked (100% reduction)
        if active_tier.size_reduction_pct >= 100:
            logger.warning(
                "trading_blocked_by_drawdown",
                drawdown_pct=round(metrics.drawdown_pct, 2),
                threshold_pct=active_tier.threshold_pct,
            )
            return 0.0, 100.0, metrics, True

        # Apply reduction
        reduction_multiplier = (100 - active_tier.size_reduction_pct) / 100
        reduced_size = size_sol * reduction_multiplier

        logger.info(
            "drawdown_reduction_applied",
            original_size=round(size_sol, 4),
            reduced_size=round(reduced_size, 4),
            reduction_pct=active_tier.size_reduction_pct,
            drawdown_pct=round(metrics.drawdown_pct, 2),
            tier_threshold=active_tier.threshold_pct,
        )

        return reduced_size, active_tier.size_reduction_pct, metrics, False

    async def _check_daily_loss_limit(
        self,
        config: PositionSizingConfig,
        starting_capital_sol: float | None = None,
    ) -> tuple[bool, str | None, DailyLossMetrics | None]:
        """Check if daily loss limit allows trading.

        Story 10.5-10: Blocks entries when daily loss limit reached.

        Args:
            config: Current configuration
            starting_capital_sol: Optional starting capital override

        Returns:
            Tuple of (is_allowed, reason, metrics)
        """
        # Check if limit is enabled
        if not config.daily_loss_limit_enabled:
            return True, None, None

        # Get or create daily loss tracker
        if self._daily_loss_tracker is None:
            self._daily_loss_tracker = DailyLossTracker(
                daily_limit_pct=config.daily_loss_limit_pct,
                warning_threshold_pct=config.daily_loss_warning_threshold_pct,
            )

        # Check if entry allowed
        allowed, reason, metrics = await self._daily_loss_tracker.is_entry_allowed(
            starting_capital_sol=starting_capital_sol,
        )

        return allowed, reason, metrics

    async def _check_concentration_limits(
        self,
        config: PositionSizingConfig,
        token_address: str | None,
        requested_size_sol: float,
        cluster_id: str | None = None,
        portfolio_value_sol: float | None = None,
    ) -> ConcentrationMetrics:
        """Check concentration limits and return adjusted size.

        Story 10.5-11: Enforces token and cluster concentration limits.

        Args:
            config: Current configuration
            token_address: Token address for the position
            requested_size_sol: Requested position size
            cluster_id: Optional cluster ID
            portfolio_value_sol: Optional portfolio value override

        Returns:
            ConcentrationMetrics with check results
        """
        # Check if limits are enabled
        if not config.concentration_limits_enabled:
            return ConcentrationMetrics(
                token_address=token_address,
                cluster_id=cluster_id,
                requested_amount_sol=requested_size_sol,
                max_allowed_sol=requested_size_sol,
            )

        # Get or create concentration checker
        if self._concentration_checker is None:
            self._concentration_checker = ConcentrationChecker(config=config)
        else:
            self._concentration_checker.update_config(config)

        # Skip if no token address
        if not token_address:
            return ConcentrationMetrics(
                requested_amount_sol=requested_size_sol,
                max_allowed_sol=requested_size_sol,
            )

        # Check concentration
        return await self._concentration_checker.check_entry(
            token_address=token_address,
            requested_amount_sol=requested_size_sol,
            cluster_id=cluster_id,
            portfolio_value_sol=portfolio_value_sol,
        )

    async def calculate_size(  # noqa: PLR0911, PLR0912, PLR0915
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

        # Determine stop loss to use (from request or config default)
        stop_loss_pct = request.stop_loss_pct or config.default_stop_loss_pct

        # Step 0: Check daily loss limit (Story 10.5-10)
        daily_loss_allowed, daily_loss_reason, daily_loss_metrics = (
            await self._check_daily_loss_limit(config)
        )

        if not daily_loss_allowed:
            logger.info(
                "position_blocked_by_daily_loss",
                reason=daily_loss_reason,
                pnl_pct=round(daily_loss_metrics.pnl_pct, 2) if daily_loss_metrics else 0,
            )
            result = PositionSizeResult(
                decision=SizingDecision.BLOCKED_DAILY_LOSS,
                conviction_tier=ConvictionTier.NONE,
                base_size_sol=0,
                multiplier=0,
                calculated_size_sol=0,
                final_size_sol=0,
                capital_used_for_base=0,
                reason=daily_loss_reason or "Daily loss limit reached",
                sizing_mode=config.sizing_mode,
                stop_loss_pct_used=stop_loss_pct,
                daily_loss_metrics=daily_loss_metrics,
                daily_loss_blocked=True,
            )
            await self._maybe_audit(request, config, result, audit)
            return result

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
                sizing_mode=config.sizing_mode,
                stop_loss_pct_used=stop_loss_pct,
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
                sizing_mode=config.sizing_mode,
                stop_loss_pct_used=stop_loss_pct,
            )
            await self._maybe_audit(request, config, result, audit)
            return result

        # Step 3: Calculate available capital
        usable_balance = max(0, request.available_balance_sol - config.reserve_sol)
        available_for_new = max(0, usable_balance - request.current_allocated_sol)

        # Check max capital allocation
        total_capital = request.available_balance_sol + request.current_allocated_sol
        max_allocation = total_capital * (config.max_capital_allocation_pct / 100)
        remaining_allocation = max(0, max_allocation - request.current_allocated_sol)

        # Capital to use for base calculation
        capital_for_base = min(available_for_new, remaining_allocation)

        # Step 4: Calculate base size based on sizing mode
        if config.sizing_mode == SizingMode.RISK_BASED:
            # Risk-based sizing: position = (capital * risk_pct) / stop_loss_pct
            max_risk_sol = total_capital * (config.risk_per_trade_pct / 100)
            base_size = max_risk_sol / (stop_loss_pct / 100)
            logger.debug(
                "risk_based_sizing",
                total_capital=total_capital,
                risk_pct=config.risk_per_trade_pct,
                max_risk_sol=max_risk_sol,
                stop_loss_pct=stop_loss_pct,
                base_size=base_size,
            )
        else:
            # Fixed percent: base size as % of available capital
            base_size = capital_for_base * (config.base_position_pct / 100)

        # Step 5: Apply conviction multiplier
        multiplier = self._get_multiplier(tier, config)
        calculated_size = base_size * multiplier

        # Step 6: Apply limits
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

        # Step 6.5: Apply drawdown-based reduction (Story 10.5-9)
        pre_drawdown_size = final_size
        drawdown_metrics: DrawdownMetrics | None = None
        drawdown_reduction_pct = 0.0

        (
            final_size,
            drawdown_reduction_pct,
            drawdown_metrics,
            is_blocked,
        ) = await self._apply_drawdown_reduction(
            size_sol=final_size,
            config=config,
            current_capital_sol=total_capital,
        )

        # Check if trading blocked by drawdown
        if is_blocked:
            logger.info(
                "position_blocked_by_drawdown",
                drawdown_pct=round(drawdown_metrics.drawdown_pct, 2) if drawdown_metrics else 0,
            )
            result = PositionSizeResult(
                decision=SizingDecision.BLOCKED_DRAWDOWN,
                conviction_tier=tier,
                base_size_sol=base_size,
                multiplier=multiplier,
                calculated_size_sol=calculated_size,
                final_size_sol=0,
                capital_used_for_base=capital_for_base,
                reason="Trading blocked - drawdown limit reached",
                sizing_mode=config.sizing_mode,
                stop_loss_pct_used=stop_loss_pct,
                drawdown_reduction_pct=100.0,
                drawdown_metrics=drawdown_metrics,
                pre_drawdown_size_sol=pre_drawdown_size,
            )
            await self._maybe_audit(request, config, result, audit)
            return result

        # Track if drawdown reduction was applied
        if drawdown_reduction_pct > 0:
            reduction_applied = True
            reduction_reason = f"Drawdown reduction {drawdown_reduction_pct:.0f}%"

        # Step 6.6: Apply concentration limits (Story 10.5-11)
        pre_concentration_size = final_size
        concentration_metrics = await self._check_concentration_limits(
            config=config,
            token_address=request.token_address,
            requested_size_sol=final_size,
            cluster_id=request.cluster_id,
            portfolio_value_sol=total_capital,
        )

        # Check if blocked by concentration
        if concentration_metrics.is_blocked:
            if concentration_metrics.is_duplicate:
                decision_type = SizingDecision.BLOCKED_DUPLICATE
            else:
                decision_type = SizingDecision.BLOCKED_CONCENTRATION

            logger.info(
                "position_blocked_by_concentration",
                reason=concentration_metrics.block_reason,
                token_pct=round(concentration_metrics.token_current_pct, 2),
                cluster_pct=round(concentration_metrics.cluster_current_pct, 2),
            )
            result = PositionSizeResult(
                decision=decision_type,
                conviction_tier=tier,
                base_size_sol=base_size,
                multiplier=multiplier,
                calculated_size_sol=calculated_size,
                final_size_sol=0,
                capital_used_for_base=capital_for_base,
                reason=concentration_metrics.block_reason or "Concentration limit reached",
                sizing_mode=config.sizing_mode,
                stop_loss_pct_used=stop_loss_pct,
                drawdown_reduction_pct=drawdown_reduction_pct,
                drawdown_metrics=drawdown_metrics,
                pre_drawdown_size_sol=pre_drawdown_size,
                concentration_metrics=concentration_metrics,
                concentration_blocked=True,
                pre_concentration_size_sol=pre_concentration_size,
            )
            await self._maybe_audit(request, config, result, audit)
            return result

        # Apply concentration adjustment if needed
        concentration_adjusted = False
        if concentration_metrics.was_adjusted:
            final_size = concentration_metrics.max_allowed_sol
            concentration_adjusted = True
            reduction_applied = True
            reduction_reason = (
                f"Concentration limit ({concentration_metrics.max_allowed_sol:.4f} SOL max)"
            )
            logger.info(
                "position_size_reduced_by_concentration",
                pre_size=round(pre_concentration_size, 4),
                post_size=round(final_size, 4),
            )

        # Step 7: Check minimum
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
                    sizing_mode=config.sizing_mode,
                    stop_loss_pct_used=stop_loss_pct,
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
                    sizing_mode=config.sizing_mode,
                    stop_loss_pct_used=stop_loss_pct,
                )
                await self._maybe_audit(request, config, result, audit)
                return result

        # Step 8: Calculate risk amount (SOL at risk if stop loss hit)
        risk_amount_sol = final_size * (stop_loss_pct / 100)

        # Step 9: Determine final decision
        decision = SizingDecision.REDUCED if reduction_applied else SizingDecision.APPROVED

        logger.info(
            "position_size_calculated",
            decision=decision.value,
            tier=tier.value,
            score=request.signal_score,
            sizing_mode=config.sizing_mode.value,
            base_size=round(base_size, 4),
            multiplier=multiplier,
            final_size=round(final_size, 4),
            risk_amount=round(risk_amount_sol, 4),
            stop_loss_pct=stop_loss_pct,
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
            sizing_mode=config.sizing_mode,
            risk_amount_sol=risk_amount_sol,
            stop_loss_pct_used=stop_loss_pct,
            # Story 10.5-9: Drawdown reduction fields
            drawdown_reduction_pct=drawdown_reduction_pct,
            drawdown_metrics=drawdown_metrics,
            pre_drawdown_size_sol=pre_drawdown_size,
            # Story 10.5-10: Daily loss limit fields
            daily_loss_metrics=daily_loss_metrics,
            # Story 10.5-11: Concentration limit fields
            concentration_metrics=concentration_metrics,
            concentration_adjusted=concentration_adjusted,
            pre_concentration_size_sol=pre_concentration_size,
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
