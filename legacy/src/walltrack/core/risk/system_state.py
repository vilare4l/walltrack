"""System state management for trading controls."""

from datetime import datetime

import structlog

from walltrack.data.supabase import SupabaseClient, get_supabase_client
from walltrack.models.risk import (
    CircuitBreakerType,
    PauseReason,
    PauseRequest,
    PauseResumeEvent,
    ResumeRequest,
    SystemState,
    SystemStateResponse,
    SystemStatus,
)

logger = structlog.get_logger(__name__)


class SystemStateManager:
    """
    Manages system trading state (running/paused).

    Handles manual pause/resume and integrates with circuit breakers.
    """

    def __init__(self) -> None:
        """Initialize system state manager."""
        self._supabase: SupabaseClient | None = None
        self._state = SystemState()

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
            .eq("key", "system_state")
            .single()
            .execute()
        )

        if result.data:
            self._state = SystemState(**result.data["value"])

        logger.info(
            "system_state_initialized",
            status=self._state.status.value,
            is_paused=self._state.is_paused,
        )

    async def get_state(self) -> SystemStateResponse:
        """Get current system state with details."""
        db = await self._get_db()

        # Get active circuit breakers
        cb_result = (
            await db.table("circuit_breaker_triggers")
            .select("breaker_type")
            .is_("reset_at", "null")
            .execute()
        )

        active_breakers = [row["breaker_type"] for row in cb_result.data]

        # Get recent events
        events_result = (
            await db.table("pause_resume_events")
            .select("*")
            .order("occurred_at", desc=True)
            .limit(10)
            .execute()
        )

        recent_events = [PauseResumeEvent(**row) for row in events_result.data]

        return SystemStateResponse(
            state=self._state,
            can_trade=not self._state.is_paused,
            can_exit=True,  # Exits always work
            active_circuit_breakers=active_breakers,
            recent_events=recent_events,
        )

    async def pause(self, request: PauseRequest) -> SystemState:
        """
        Manually pause the system.

        Args:
            request: Pause request with operator and reason

        Returns:
            Updated system state
        """
        if self._state.is_paused:
            logger.warning(
                "pause_request_already_paused",
                current_status=self._state.status.value,
            )
            return self._state

        previous_status = self._state.status

        # Update state
        self._state.status = SystemStatus.PAUSED_MANUAL
        self._state.paused_at = datetime.utcnow()
        self._state.paused_by = request.operator_id
        self._state.pause_reason = request.reason
        self._state.pause_note = request.note
        self._state.resumed_at = None
        self._state.resumed_by = None
        self._state.last_updated = datetime.utcnow()

        # Persist state
        await self._save_state()

        # Record event
        await self._record_event(
            event_type="pause",
            operator_id=request.operator_id,
            previous_status=previous_status,
            new_status=self._state.status,
            reason=request.reason,
            note=request.note,
        )

        logger.warning(
            "system_paused_manual",
            operator=request.operator_id,
            reason=request.reason.value,
        )

        return self._state

    async def resume(self, request: ResumeRequest) -> SystemState:
        """
        Resume the system (restore to running state).

        Args:
            request: Resume request with operator acknowledgement

        Returns:
            Updated system state

        Raises:
            ValueError: If resuming from circuit breaker without acknowledgement
        """
        if not self._state.is_paused:
            logger.warning("resume_request_not_paused")
            return self._state

        # Check if circuit breaker pause requires acknowledgement
        if self._state.is_circuit_breaker_pause and not request.acknowledge_warning:
            raise ValueError(
                f"Resuming from {self._state.status.value} requires explicit "
                "acknowledgement. Set acknowledge_warning=True to confirm."
            )

        previous_status = self._state.status

        # Clear any active circuit breaker triggers if resuming from CB
        if self._state.is_circuit_breaker_pause:
            await self._clear_active_triggers(request.operator_id)

        # Update state
        self._state.status = SystemStatus.RUNNING
        self._state.resumed_at = datetime.utcnow()
        self._state.resumed_by = request.operator_id
        self._state.last_updated = datetime.utcnow()

        # Keep pause info for history
        # (paused_at, paused_by, pause_reason remain for audit)

        # Persist state
        await self._save_state()

        # Record event
        await self._record_event(
            event_type="resume",
            operator_id=request.operator_id,
            previous_status=previous_status,
            new_status=self._state.status,
        )

        logger.info(
            "system_resumed",
            operator=request.operator_id,
            previous_status=previous_status.value,
        )

        return self._state

    async def set_circuit_breaker_pause(
        self,
        breaker_type: CircuitBreakerType,
    ) -> SystemState:
        """
        Set pause due to circuit breaker (called by circuit breaker services).

        Args:
            breaker_type: Type of circuit breaker that triggered

        Returns:
            Updated system state
        """
        status_map = {
            CircuitBreakerType.DRAWDOWN: SystemStatus.PAUSED_DRAWDOWN,
            CircuitBreakerType.WIN_RATE: SystemStatus.PAUSED_WIN_RATE,
            CircuitBreakerType.CONSECUTIVE_LOSS: SystemStatus.PAUSED_CONSECUTIVE_LOSS,
        }

        new_status = status_map.get(breaker_type, SystemStatus.PAUSED_MANUAL)
        previous_status = self._state.status

        self._state.status = new_status
        self._state.paused_at = datetime.utcnow()
        self._state.paused_by = "system"
        self._state.pause_reason = None
        self._state.pause_note = f"Circuit breaker: {breaker_type.value}"
        self._state.last_updated = datetime.utcnow()

        await self._save_state()

        await self._record_event(
            event_type="pause",
            operator_id="system",
            previous_status=previous_status,
            new_status=new_status,
            note=f"Circuit breaker triggered: {breaker_type.value}",
        )

        logger.warning(
            "system_paused_circuit_breaker",
            breaker_type=breaker_type.value,
        )

        return self._state

    async def _clear_active_triggers(self, operator_id: str) -> None:
        """Clear active circuit breaker triggers."""
        db = await self._get_db()

        await (
            db.table("circuit_breaker_triggers")
            .update(
                {
                    "reset_at": datetime.utcnow().isoformat(),
                    "reset_by": operator_id,
                }
            )
            .is_("reset_at", "null")
            .execute()
        )

    async def _save_state(self) -> None:
        """Persist current state to database."""
        db = await self._get_db()

        await (
            db.table("system_config")
            .upsert(
                {
                    "key": "system_state",
                    "value": self._state.model_dump(mode="json"),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .execute()
        )

        # Also update legacy system_status key for backward compatibility
        await (
            db.table("system_config")
            .upsert(
                {
                    "key": "system_status",
                    "value": self._state.status.value,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .execute()
        )

    async def _record_event(
        self,
        event_type: str,
        operator_id: str,
        previous_status: SystemStatus,
        new_status: SystemStatus,
        reason: PauseReason | None = None,
        note: str | None = None,
    ) -> None:
        """Record pause/resume event to history."""
        db = await self._get_db()

        event = PauseResumeEvent(
            event_type=event_type,
            operator_id=operator_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            note=note,
        )

        await (
            db.table("pause_resume_events")
            .insert(event.model_dump(exclude={"id"}, mode="json"))
            .execute()
        )

    def can_trade(self) -> bool:
        """Check if new trades are allowed."""
        return not self._state.is_paused

    def can_exit(self) -> bool:
        """Check if exits are allowed (always True)."""
        return True

    @property
    def state(self) -> SystemState:
        """Get current state."""
        return self._state


# Singleton instance
_state_manager: SystemStateManager | None = None


async def get_system_state_manager() -> SystemStateManager:
    """Get or create system state manager singleton."""
    global _state_manager

    if _state_manager is None:
        _state_manager = SystemStateManager()
        await _state_manager.initialize()

    return _state_manager


def reset_system_state_manager() -> None:
    """Reset the singleton for testing."""
    global _state_manager
    _state_manager = None
