"""Circuit breaker implementation for risk management."""

from datetime import datetime
from decimal import Decimal

import structlog

from walltrack.data.supabase import SupabaseClient, get_supabase_client
from walltrack.models.risk import (
    BlockedSignal,
    CapitalSnapshot,
    CircuitBreakerTrigger,
    CircuitBreakerType,
    DrawdownCheckResult,
    DrawdownConfig,
    SystemStatus,
)

logger = structlog.get_logger(__name__)


class DrawdownCircuitBreaker:
    """
    Manages drawdown-based circuit breaker logic.

    Tracks peak capital and triggers pause when drawdown exceeds threshold.
    """

    def __init__(self, config: DrawdownConfig) -> None:
        """Initialize with configuration."""
        self.config = config
        self._supabase: SupabaseClient | None = None
        self._current_capital: Decimal = config.initial_capital
        self._peak_capital: Decimal = config.initial_capital

    async def _get_db(self) -> SupabaseClient:
        """Get database client."""
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load state from database on startup."""
        db = await self._get_db()

        # Load latest capital snapshot
        result = (
            await db.table("capital_snapshots")
            .select("*")
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            snapshot = result.data[0]
            self._current_capital = Decimal(str(snapshot["capital"]))
            self._peak_capital = Decimal(str(snapshot["peak_capital"]))

        logger.info(
            "drawdown_circuit_breaker_initialized",
            current_capital=str(self._current_capital),
            peak_capital=str(self._peak_capital),
            threshold=str(self.config.threshold_percent),
        )

    def calculate_drawdown(self, current_capital: Decimal) -> CapitalSnapshot:
        """
        Calculate current drawdown.

        Updates peak capital if current is higher (never decreases).
        """
        # Update peak if new high
        self._peak_capital = max(self._peak_capital, current_capital)

        self._current_capital = current_capital

        return CapitalSnapshot(
            capital=current_capital,
            peak_capital=self._peak_capital,
        )

    async def check_drawdown(self, current_capital: Decimal) -> DrawdownCheckResult:
        """
        Check if drawdown exceeds threshold.

        Returns check result with breach status and optional trigger.
        """
        snapshot = self.calculate_drawdown(current_capital)

        is_breached = snapshot.drawdown_percent >= self.config.threshold_percent

        result = DrawdownCheckResult(
            current_capital=snapshot.capital,
            peak_capital=snapshot.peak_capital,
            drawdown_percent=snapshot.drawdown_percent,
            threshold_percent=self.config.threshold_percent,
            is_breached=is_breached,
        )

        if is_breached:
            trigger = await self._create_trigger(snapshot)
            result.trigger = trigger

            logger.warning(
                "drawdown_circuit_breaker_triggered",
                drawdown_percent=str(snapshot.drawdown_percent),
                threshold=str(self.config.threshold_percent),
                capital=str(snapshot.capital),
                peak=str(snapshot.peak_capital),
            )

        return result

    async def _create_trigger(
        self, snapshot: CapitalSnapshot
    ) -> CircuitBreakerTrigger:
        """Create and persist circuit breaker trigger record."""
        db = await self._get_db()

        trigger = CircuitBreakerTrigger(
            breaker_type=CircuitBreakerType.DRAWDOWN,
            threshold_value=self.config.threshold_percent,
            actual_value=snapshot.drawdown_percent,
            capital_at_trigger=snapshot.capital,
            peak_capital_at_trigger=snapshot.peak_capital,
        )

        result = await db.table("circuit_breaker_triggers").insert(
            trigger.model_dump(exclude={"id", "is_active"}, mode="json")
        ).execute()

        trigger.id = result.data[0]["id"]

        # Update system status
        await self._update_system_status(SystemStatus.PAUSED_DRAWDOWN)

        return trigger

    async def _update_system_status(self, status: SystemStatus) -> None:
        """Update system status in database."""
        db = await self._get_db()

        await db.table("system_config").upsert(
            {
                "key": "system_status",
                "value": status.value,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).execute()

    async def record_capital_snapshot(self, capital: Decimal) -> CapitalSnapshot:
        """Record capital snapshot to database."""
        db = await self._get_db()
        snapshot = self.calculate_drawdown(capital)

        await db.table("capital_snapshots").insert(
            {
                "timestamp": snapshot.timestamp.isoformat(),
                "capital": str(snapshot.capital),
                "peak_capital": str(snapshot.peak_capital),
                "drawdown_percent": str(snapshot.drawdown_percent),
            }
        ).execute()

        return snapshot

    async def reset(
        self, operator_id: str, new_peak: Decimal | None = None
    ) -> None:
        """
        Reset circuit breaker (requires manual action).

        Args:
            operator_id: ID of operator performing reset
            new_peak: Optional new peak capital (defaults to current)
        """
        db = await self._get_db()

        # Mark active trigger as reset
        await (
            db.table("circuit_breaker_triggers")
            .update(
                {
                    "reset_at": datetime.utcnow().isoformat(),
                    "reset_by": operator_id,
                }
            )
            .eq("breaker_type", CircuitBreakerType.DRAWDOWN.value)
            .is_("reset_at", "null")
            .execute()
        )

        # Optionally reset peak capital
        if new_peak is not None:
            self._peak_capital = new_peak
        else:
            self._peak_capital = self._current_capital

        # Update system status
        await self._update_system_status(SystemStatus.RUNNING)

        logger.info(
            "drawdown_circuit_breaker_reset",
            operator_id=operator_id,
            new_peak=str(self._peak_capital),
        )

    async def block_signal(
        self,
        signal_id: str,
        signal_data: dict,
    ) -> BlockedSignal:
        """Record a signal blocked due to circuit breaker."""
        db = await self._get_db()

        blocked = BlockedSignal(
            signal_id=signal_id,
            breaker_type=CircuitBreakerType.DRAWDOWN,
            reason=f"Drawdown circuit breaker active (threshold: {self.config.threshold_percent}%)",
            signal_data=signal_data,
        )

        await db.table("blocked_signals").insert(
            blocked.model_dump(mode="json")
        ).execute()

        logger.info(
            "signal_blocked_drawdown",
            signal_id=signal_id,
        )

        return blocked

    @property
    def current_drawdown_percent(self) -> Decimal:
        """Current drawdown percentage."""
        if self._peak_capital == Decimal("0"):
            return Decimal("0")
        return (
            (self._peak_capital - self._current_capital) / self._peak_capital
        ) * Decimal("100")


# Singleton instance
_drawdown_breaker: DrawdownCircuitBreaker | None = None


async def get_drawdown_circuit_breaker(
    config: DrawdownConfig | None = None,
) -> DrawdownCircuitBreaker:
    """Get or create drawdown circuit breaker singleton."""
    global _drawdown_breaker

    if _drawdown_breaker is None:
        if config is None:
            # Load from database
            db = await get_supabase_client()
            result = (
                await db.table("system_config")
                .select("value")
                .eq("key", "drawdown_config")
                .single()
                .execute()
            )
            config = DrawdownConfig(**result.data["value"])

        _drawdown_breaker = DrawdownCircuitBreaker(config)
        await _drawdown_breaker.initialize()

    return _drawdown_breaker


def reset_drawdown_circuit_breaker() -> None:
    """Reset the singleton for testing."""
    global _drawdown_breaker
    _drawdown_breaker = None
