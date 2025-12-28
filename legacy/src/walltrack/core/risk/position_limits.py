"""Position limit manager for maximum concurrent positions."""

from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import structlog

from walltrack.data.supabase import SupabaseClient, get_supabase_client
from walltrack.models.risk import (
    BlockedSignal,
    BlockedTradeResponse,
    CircuitBreakerType,
    PositionLimitCheckResult,
    PositionLimitConfig,
    QueuedSignal,
)

logger = structlog.get_logger(__name__)


class PositionLimitManager:
    """
    Manages maximum concurrent position limits.

    Enforces position limits and queues signals when limit reached.
    """

    def __init__(self, config: PositionLimitConfig) -> None:
        """Initialize with configuration."""
        self.config = config
        self._supabase: SupabaseClient | None = None
        self._signal_queue: deque[QueuedSignal] = deque()
        self._execute_callback: Callable[[dict], Awaitable[bool]] | None = None

    async def _get_db(self) -> SupabaseClient:
        """Get database client."""
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    def set_execute_callback(
        self,
        callback: Callable[[dict], Awaitable[bool]],
    ) -> None:
        """Set callback for executing queued signals."""
        self._execute_callback = callback

    async def initialize(self) -> None:
        """Load queued signals from database on startup."""
        db = await self._get_db()

        # Load pending queued signals
        result = (
            await db.table("queued_signals")
            .select("*")
            .eq("status", "pending")
            .order("queued_at")
            .execute()
        )

        if result.data:
            for row in result.data:
                signal = QueuedSignal(**row)
                if not signal.is_expired:
                    self._signal_queue.append(signal)
                else:
                    # Mark expired
                    await self._mark_signal_expired(signal.id)

        logger.info(
            "position_limit_manager_initialized",
            max_positions=self.config.max_positions,
            queued_signals=len(self._signal_queue),
        )

    async def get_open_position_count(self) -> int:
        """Get current number of open positions."""
        db = await self._get_db()

        result = (
            await db.table("positions")
            .select("id", count="exact")
            .eq("status", "open")
            .execute()
        )

        return result.count or 0

    async def check_can_open(self) -> PositionLimitCheckResult:
        """Check if a new position can be opened."""
        current = await self.get_open_position_count()
        can_open = current < self.config.max_positions
        slots = max(0, self.config.max_positions - current)

        if can_open:
            message = f"{slots} slot(s) available"
        else:
            message = f"At maximum capacity ({self.config.max_positions} positions)"

        return PositionLimitCheckResult(
            current_positions=current,
            max_positions=self.config.max_positions,
            can_open=can_open,
            slots_available=slots,
            queued_signals_count=len(self._signal_queue),
            message=message,
        )

    async def request_position(
        self,
        signal_id: str,
        signal_data: dict,
    ) -> BlockedTradeResponse | bool:
        """
        Request to open a position.

        Returns True if allowed, or BlockedTradeResponse if blocked.
        """
        check = await self.check_can_open()

        if check.can_open:
            logger.info(
                "position_request_allowed",
                signal_id=signal_id,
                current=check.current_positions,
                max=check.max_positions,
            )
            return True

        # Position limit reached - block or queue
        if self.config.enable_queue:
            queue_position = await self._queue_signal(signal_id, signal_data)
            return BlockedTradeResponse(
                reason="max_positions_reached",
                current_positions=check.current_positions,
                max_positions=check.max_positions,
                queued=True,
                queue_position=queue_position,
                signal_id=signal_id,
            )
        else:
            # Just block without queuing
            await self._record_blocked_signal(signal_id, signal_data)
            return BlockedTradeResponse(
                reason="max_positions_reached",
                current_positions=check.current_positions,
                max_positions=check.max_positions,
                queued=False,
                signal_id=signal_id,
            )

    async def _queue_signal(
        self,
        signal_id: str,
        signal_data: dict,
    ) -> int:
        """Add signal to queue for later execution."""
        db = await self._get_db()

        # Check queue limit
        if self.config.max_queue_size > 0 and len(self._signal_queue) >= self.config.max_queue_size:
            # Queue full - remove oldest
            oldest = self._signal_queue.popleft()
            await self._mark_signal_expired(oldest.id)
            logger.warning(
                "queue_full_removed_oldest",
                removed_signal=oldest.signal_id,
            )

        expires_at = datetime.utcnow() + timedelta(
            minutes=self.config.queue_expiry_minutes
        )

        signal = QueuedSignal(
            signal_id=signal_id,
            expires_at=expires_at,
            signal_data=signal_data,
        )

        result = (
            await db.table("queued_signals")
            .insert(
                signal.model_dump(
                    exclude={"id", "is_expired", "time_remaining_seconds"}, mode="json"
                )
            )
            .execute()
        )

        signal.id = result.data[0]["id"]
        self._signal_queue.append(signal)

        logger.info(
            "signal_queued",
            signal_id=signal_id,
            queue_position=len(self._signal_queue),
            expires_in_minutes=self.config.queue_expiry_minutes,
        )

        return len(self._signal_queue)

    async def _record_blocked_signal(
        self,
        signal_id: str,
        signal_data: dict,
    ) -> None:
        """Record blocked signal (not queued)."""
        db = await self._get_db()

        blocked = BlockedSignal(
            signal_id=signal_id,
            breaker_type=CircuitBreakerType.MANUAL,  # Using MANUAL for position limit
            reason="max_positions_reached",
            signal_data=signal_data,
        )

        await db.table("blocked_signals").insert(
            blocked.model_dump(mode="json")
        ).execute()

    async def _mark_signal_expired(self, signal_db_id: str | None) -> None:
        """Mark a signal as expired in database."""
        if signal_db_id is None:
            return
        db = await self._get_db()
        await (
            db.table("queued_signals")
            .update({"status": "expired"})
            .eq("id", signal_db_id)
            .execute()
        )

    async def on_position_closed(self, position_id: str) -> QueuedSignal | None:
        """
        Handle position close - execute next queued signal.

        Called when a position is closed to free up a slot.
        """
        db = await self._get_db()

        queue_length_before = len(self._signal_queue)

        # Clean expired signals first
        await self._clean_expired_signals()

        if not self._signal_queue:
            logger.info(
                "position_slot_freed_no_queue",
                position_id=position_id,
            )
            return None

        # Get next signal (FIFO)
        next_signal = self._signal_queue.popleft()

        # Record event
        await db.table("position_slot_events").insert(
            {
                "event_type": "signal_executed",
                "position_id": position_id,
                "signal_id": next_signal.signal_id,
                "queue_length_before": queue_length_before,
                "queue_length_after": len(self._signal_queue),
            }
        ).execute()

        # Mark signal as executed
        await (
            db.table("queued_signals")
            .update({"status": "executed"})
            .eq("id", next_signal.id)
            .execute()
        )

        logger.info(
            "queued_signal_executing",
            signal_id=next_signal.signal_id,
            queue_remaining=len(self._signal_queue),
        )

        # Execute via callback if set
        if self._execute_callback:
            try:
                await self._execute_callback(next_signal.signal_data)
            except Exception as e:
                logger.error(
                    "queued_signal_execution_failed",
                    signal_id=next_signal.signal_id,
                    error=str(e),
                )

        return next_signal

    async def _clean_expired_signals(self) -> int:
        """Remove expired signals from queue."""
        removed = 0

        while self._signal_queue:
            signal = self._signal_queue[0]
            if signal.is_expired:
                self._signal_queue.popleft()
                await self._mark_signal_expired(signal.id)
                removed += 1
                logger.info(
                    "queued_signal_expired",
                    signal_id=signal.signal_id,
                )
            else:
                break

        return removed

    async def get_queue_status(self) -> list[QueuedSignal]:
        """Get current queue status."""
        await self._clean_expired_signals()
        return list(self._signal_queue)

    async def cancel_queued_signal(self, signal_id: str) -> bool:
        """Cancel a queued signal."""
        db = await self._get_db()

        # Find in queue
        for i, signal in enumerate(self._signal_queue):
            if signal.signal_id == signal_id:
                del self._signal_queue[i]
                await (
                    db.table("queued_signals")
                    .update({"status": "cancelled"})
                    .eq("signal_id", signal_id)
                    .execute()
                )

                logger.info(
                    "queued_signal_cancelled",
                    signal_id=signal_id,
                )
                return True

        return False

    async def update_config(self, config: PositionLimitConfig) -> None:
        """Update configuration."""
        db = await self._get_db()

        await db.table("system_config").upsert(
            {
                "key": "position_limit_config",
                "value": config.model_dump(mode="json"),
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).execute()

        self.config = config

        logger.info(
            "position_limit_config_updated",
            max_positions=config.max_positions,
        )


# Singleton instance
_position_limit_manager: PositionLimitManager | None = None


async def get_position_limit_manager(
    config: PositionLimitConfig | None = None,
) -> PositionLimitManager:
    """Get or create position limit manager singleton."""
    global _position_limit_manager

    if _position_limit_manager is None:
        if config is None:
            db = await get_supabase_client()
            result = (
                await db.table("system_config")
                .select("value")
                .eq("key", "position_limit_config")
                .single()
                .execute()
            )
            config = PositionLimitConfig(**result.data["value"])

        _position_limit_manager = PositionLimitManager(config)
        await _position_limit_manager.initialize()

    return _position_limit_manager


def reset_position_limit_manager() -> None:
    """Reset the singleton for testing."""
    global _position_limit_manager
    _position_limit_manager = None
