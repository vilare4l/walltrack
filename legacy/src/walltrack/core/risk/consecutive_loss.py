"""Consecutive loss position reduction manager."""

from datetime import datetime
from decimal import Decimal

import structlog

from walltrack.data.supabase import SupabaseClient, get_supabase_client
from walltrack.models.risk import (
    CircuitBreakerType,
    ConsecutiveLossConfig,
    ConsecutiveLossState,
    LossStreakEvent,
    SizeAdjustmentResult,
    SizingMode,
    SystemStatus,
    TradeOutcome,
    TradeResult,
)

logger = structlog.get_logger(__name__)


class ConsecutiveLossManager:
    """
    Manages position size reduction based on consecutive losses.

    Tracks loss streaks and adjusts position sizing to protect capital.
    """

    def __init__(self, config: ConsecutiveLossConfig) -> None:
        """Initialize with configuration."""
        self.config = config
        self._supabase: SupabaseClient | None = None
        self._state = ConsecutiveLossState()

    async def _get_db(self) -> SupabaseClient:
        """Get database client."""
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load state from database on startup."""
        db = await self._get_db()

        result = (
            await db.table("system_config")
            .select("value")
            .eq("key", "consecutive_loss_state")
            .single()
            .execute()
        )

        if result.data:
            self._state = ConsecutiveLossState(**result.data["value"])

        logger.info(
            "consecutive_loss_manager_initialized",
            loss_count=self._state.consecutive_loss_count,
            sizing_mode=self._state.sizing_mode.value,
            size_factor=str(self._state.current_size_factor),
        )

    async def record_trade_outcome(self, result: TradeResult) -> ConsecutiveLossState:
        """
        Record a trade outcome and update loss streak.

        Args:
            result: The trade result to record

        Returns:
            Updated consecutive loss state
        """
        previous_state = self._state.model_copy()

        if result.outcome == TradeOutcome.LOSS:
            await self._handle_loss(result)
        elif result.outcome == TradeOutcome.WIN:
            await self._handle_win(result)
        # BREAKEVEN doesn't affect streak

        self._state.last_trade_outcome = result.outcome
        self._state.last_updated = datetime.utcnow()

        # Persist state
        await self._save_state()

        # Log state change if mode changed
        if previous_state.sizing_mode != self._state.sizing_mode:
            await self._record_event(
                event_type="mode_change",
                previous_state=previous_state,
                triggering_trade_id=result.trade_id,
            )

        return self._state

    async def _handle_loss(self, result: TradeResult) -> None:
        """Handle a losing trade."""
        self._state.consecutive_loss_count += 1

        # Start streak tracking if first loss
        if self._state.streak_started_at is None:
            self._state.streak_started_at = datetime.utcnow()

        logger.info(
            "consecutive_loss_recorded",
            count=self._state.consecutive_loss_count,
            trade_id=result.trade_id,
        )

        # Check critical threshold first
        if self._state.consecutive_loss_count >= self.config.critical_threshold:
            await self._enter_critical_mode(result)

        # Check reduction threshold
        elif self._state.consecutive_loss_count >= self.config.reduction_threshold:
            await self._enter_reduced_mode(result)

    async def _handle_win(self, result: TradeResult) -> None:
        """Handle a winning trade - resets streak."""
        if self._state.consecutive_loss_count > 0:
            logger.info(
                "loss_streak_broken",
                previous_count=self._state.consecutive_loss_count,
                trade_id=result.trade_id,
            )

            previous_state = self._state.model_copy()

            # Reset to normal
            self._state.consecutive_loss_count = 0
            self._state.sizing_mode = SizingMode.NORMAL
            self._state.current_size_factor = Decimal("1.0")
            self._state.streak_started_at = None

            # Record recovery event
            await self._record_event(
                event_type="recovery",
                previous_state=previous_state,
                triggering_trade_id=result.trade_id,
            )

    async def _enter_reduced_mode(self, result: TradeResult) -> None:  # noqa: ARG002
        """Enter reduced position sizing mode."""
        if self._state.sizing_mode == SizingMode.NORMAL:
            self._state.sizing_mode = SizingMode.REDUCED
            self._state.current_size_factor = self.config.reduction_factor

            logger.warning(
                "consecutive_loss_reduction_triggered",
                count=self._state.consecutive_loss_count,
                factor=str(self.config.reduction_factor),
            )

    async def _enter_critical_mode(self, result: TradeResult) -> None:  # noqa: ARG002
        """Enter critical mode at critical threshold."""
        db = await self._get_db()

        if self.config.critical_action == "pause":
            self._state.sizing_mode = SizingMode.PAUSED
            self._state.current_size_factor = Decimal("0")

            # Update system status
            await db.table("system_config").upsert(
                {
                    "key": "system_status",
                    "value": SystemStatus.PAUSED_CONSECUTIVE_LOSS.value,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).execute()

            logger.error(
                "consecutive_loss_critical_pause",
                count=self._state.consecutive_loss_count,
                threshold=self.config.critical_threshold,
            )

        else:  # further_reduce
            self._state.sizing_mode = SizingMode.CRITICAL
            self._state.current_size_factor = self.config.further_reduction_factor

            logger.error(
                "consecutive_loss_critical_reduction",
                count=self._state.consecutive_loss_count,
                factor=str(self.config.further_reduction_factor),
            )

        # Create circuit breaker trigger record
        await db.table("circuit_breaker_triggers").insert(
            {
                "breaker_type": CircuitBreakerType.CONSECUTIVE_LOSS.value,
                "threshold_value": str(self.config.critical_threshold),
                "actual_value": str(self._state.consecutive_loss_count),
                "capital_at_trigger": "0",  # Will be updated by caller
                "peak_capital_at_trigger": "0",
            }
        ).execute()

    async def _save_state(self) -> None:
        """Persist current state to database."""
        db = await self._get_db()

        await db.table("system_config").upsert(
            {
                "key": "consecutive_loss_state",
                "value": self._state.model_dump(mode="json"),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).execute()

    async def _record_event(
        self,
        event_type: str,
        previous_state: ConsecutiveLossState,
        triggering_trade_id: str | None = None,
    ) -> None:
        """Record a loss streak event."""
        db = await self._get_db()

        event = LossStreakEvent(
            event_type=event_type,
            consecutive_losses=self._state.consecutive_loss_count,
            previous_mode=previous_state.sizing_mode,
            new_mode=self._state.sizing_mode,
            previous_factor=previous_state.current_size_factor,
            new_factor=self._state.current_size_factor,
            triggering_trade_id=triggering_trade_id,
        )

        await db.table("loss_streak_events").insert(
            event.model_dump(exclude={"id"}, mode="json")
        ).execute()

    def calculate_adjusted_size(self, base_size: Decimal) -> SizeAdjustmentResult:
        """
        Calculate adjusted position size based on current state.

        Args:
            base_size: The base position size before adjustment

        Returns:
            Size adjustment result with adjusted size and reason
        """
        adjusted = base_size * self._state.current_size_factor

        # Determine reason
        if self._state.sizing_mode == SizingMode.PAUSED:
            reason = (
                f"Trading paused after {self._state.consecutive_loss_count} "
                "consecutive losses"
            )
        elif self._state.sizing_mode == SizingMode.CRITICAL:
            reason = (
                f"Critical reduction ({self._state.consecutive_loss_count} losses): "
                f"{self._state.reduction_percent}% smaller"
            )
        elif self._state.sizing_mode == SizingMode.REDUCED:
            reason = (
                f"Reduced sizing ({self._state.consecutive_loss_count} losses): "
                f"{self._state.reduction_percent}% smaller"
            )
        else:
            reason = "Normal sizing"

        return SizeAdjustmentResult(
            original_size=base_size,
            adjusted_size=adjusted,
            size_factor=self._state.current_size_factor,
            sizing_mode=self._state.sizing_mode,
            consecutive_losses=self._state.consecutive_loss_count,
            reason=reason,
        )

    async def manual_reset(self, operator_id: str) -> ConsecutiveLossState:
        """
        Manually reset the consecutive loss counter.

        Args:
            operator_id: ID of operator performing reset

        Returns:
            Reset state
        """
        db = await self._get_db()

        previous_state = self._state.model_copy()

        self._state.consecutive_loss_count = 0
        self._state.sizing_mode = SizingMode.NORMAL
        self._state.current_size_factor = Decimal("1.0")
        self._state.streak_started_at = None
        self._state.last_updated = datetime.utcnow()

        await self._save_state()

        # Reset system status if paused
        await db.table("system_config").upsert(
            {
                "key": "system_status",
                "value": SystemStatus.RUNNING.value,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).execute()

        # Mark circuit breaker as reset
        await (
            db.table("circuit_breaker_triggers")
            .update(
                {
                    "reset_at": datetime.utcnow().isoformat(),
                    "reset_by": operator_id,
                }
            )
            .eq("breaker_type", CircuitBreakerType.CONSECUTIVE_LOSS.value)
            .is_("reset_at", "null")
            .execute()
        )

        await self._record_event(
            event_type="manual_reset",
            previous_state=previous_state,
        )

        logger.info(
            "consecutive_loss_manual_reset",
            operator_id=operator_id,
            previous_count=previous_state.consecutive_loss_count,
        )

        return self._state

    @property
    def state(self) -> ConsecutiveLossState:
        """Get current state."""
        return self._state

    @property
    def can_trade(self) -> bool:
        """Whether trading is currently allowed."""
        return self._state.sizing_mode != SizingMode.PAUSED


# Singleton instance
_loss_manager: ConsecutiveLossManager | None = None


async def get_consecutive_loss_manager(
    config: ConsecutiveLossConfig | None = None,
) -> ConsecutiveLossManager:
    """Get or create consecutive loss manager singleton."""
    global _loss_manager

    if _loss_manager is None:
        if config is None:
            db = await get_supabase_client()
            result = (
                await db.table("system_config")
                .select("value")
                .eq("key", "consecutive_loss_config")
                .single()
                .execute()
            )
            config = ConsecutiveLossConfig(**result.data["value"])

        _loss_manager = ConsecutiveLossManager(config)
        await _loss_manager.initialize()

    return _loss_manager


def reset_consecutive_loss_manager() -> None:
    """Reset the singleton for testing."""
    global _loss_manager
    _loss_manager = None
