# Story 5.6: Manual Pause and Resume Controls

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: ready
- **Priority**: High
- **FR**: FR32

## User Story

**As an** operator,
**I want** to manually pause and resume trading,
**So that** I have ultimate control over the system.

## Acceptance Criteria

### AC 1: Pause Trading
**Given** dashboard control panel
**When** operator clicks "Pause Trading"
**Then** confirmation dialog appears
**And** on confirm, system status changes to "paused_manual"
**And** all new trades are blocked
**And** pause timestamp and reason are recorded

### AC 2: Resume Trading
**Given** system is paused (any reason)
**When** operator clicks "Resume Trading"
**Then** confirmation dialog appears with current status
**And** if paused due to circuit breaker, warning is shown
**And** on confirm, system status changes to "running"
**And** resume timestamp is recorded

### AC 3: Exit Management During Pause
**Given** system is paused
**When** existing positions need management
**Then** exit logic continues to function (stop-loss, take-profit)
**And** only new entries are blocked

### AC 4: Pause Reason
**Given** manual pause
**When** operator provides reason
**Then** reason is stored with pause record
**And** reason is visible in system history

## Technical Notes

- FR32: Operator can manually pause and resume trading
- Implement in `src/walltrack/core/risk/system_state.py`
- System state stored in Supabase config table

## Implementation Tasks

- [ ] Create `src/walltrack/core/risk/system_state.py`
- [ ] Implement pause with confirmation dialog
- [ ] Implement resume with warning for circuit breakers
- [ ] Ensure exits continue during pause
- [ ] Store pause/resume history with reasons
- [ ] Add controls to dashboard

## Definition of Done

- [ ] Manual pause blocks new trades
- [ ] Resume restores normal operation
- [ ] Exits continue during pause
- [ ] Pause reasons recorded

---

## Technical Specifications

### Pydantic Models

```python
# src/walltrack/core/risk/system_state.py (models)
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from datetime import datetime
from typing import Optional, List


class SystemStatus(str, Enum):
    """System trading status."""
    RUNNING = "running"
    PAUSED_DRAWDOWN = "paused_drawdown"
    PAUSED_WIN_RATE = "paused_win_rate"
    PAUSED_CONSECUTIVE_LOSS = "paused_consecutive_loss"
    PAUSED_MANUAL = "paused_manual"


class PauseReason(str, Enum):
    """Reason for manual pause."""
    MAINTENANCE = "maintenance"
    INVESTIGATION = "investigation"
    MARKET_CONDITIONS = "market_conditions"
    SYSTEM_ISSUE = "system_issue"
    OTHER = "other"


class SystemState(BaseModel):
    """Current system state."""
    status: SystemStatus = Field(default=SystemStatus.RUNNING)
    paused_at: Optional[datetime] = None
    paused_by: Optional[str] = None
    pause_reason: Optional[PauseReason] = None
    pause_note: Optional[str] = None
    resumed_at: Optional[datetime] = None
    resumed_by: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def is_paused(self) -> bool:
        """Whether system is currently paused."""
        return self.status != SystemStatus.RUNNING

    @computed_field
    @property
    def is_circuit_breaker_pause(self) -> bool:
        """Whether pause is due to circuit breaker."""
        return self.status in [
            SystemStatus.PAUSED_DRAWDOWN,
            SystemStatus.PAUSED_WIN_RATE,
            SystemStatus.PAUSED_CONSECUTIVE_LOSS
        ]

    @computed_field
    @property
    def pause_duration_seconds(self) -> Optional[int]:
        """Duration of current pause in seconds."""
        if self.paused_at and self.is_paused:
            return int((datetime.utcnow() - self.paused_at).total_seconds())
        return None


class PauseRequest(BaseModel):
    """Request to pause the system."""
    operator_id: str
    reason: PauseReason
    note: Optional[str] = None


class ResumeRequest(BaseModel):
    """Request to resume the system."""
    operator_id: str
    acknowledge_warning: bool = False  # Required if resuming from circuit breaker


class PauseResumeEvent(BaseModel):
    """Historical record of pause/resume event."""
    id: Optional[str] = None
    event_type: str  # "pause" or "resume"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    operator_id: str
    previous_status: SystemStatus
    new_status: SystemStatus
    reason: Optional[PauseReason] = None
    note: Optional[str] = None


class SystemStateResponse(BaseModel):
    """API response for system state."""
    state: SystemState
    can_trade: bool
    can_exit: bool  # Always True - exits work during pause
    active_circuit_breakers: List[str]
    recent_events: List[PauseResumeEvent]
```

### SystemStateManager Service

```python
# src/walltrack/core/risk/system_state.py
import structlog
from datetime import datetime
from typing import Optional, List
from supabase import AsyncClient

from walltrack.core.risk.models import (
    SystemStatus,
    PauseReason,
    SystemState,
    PauseRequest,
    ResumeRequest,
    PauseResumeEvent,
    SystemStateResponse,
    CircuitBreakerType
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


class SystemStateManager:
    """
    Manages system trading state (running/paused).

    Handles manual pause/resume and integrates with circuit breakers.
    """

    def __init__(self):
        self._supabase: Optional[AsyncClient] = None
        self._state = SystemState()

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load state from database on startup."""
        db = await self._get_db()

        result = await db.table("system_config").select("value").eq(
            "key", "system_state"
        ).single().execute()

        if result.data:
            self._state = SystemState(**result.data["value"])

        logger.info(
            "system_state_initialized",
            status=self._state.status.value,
            is_paused=self._state.is_paused
        )

    async def get_state(self) -> SystemStateResponse:
        """Get current system state with details."""
        db = await self._get_db()

        # Get active circuit breakers
        cb_result = await db.table("circuit_breaker_triggers").select(
            "breaker_type"
        ).is_("reset_at", "null").execute()

        active_breakers = [row["breaker_type"] for row in cb_result.data]

        # Get recent events
        events_result = await db.table("pause_resume_events").select("*").order(
            "occurred_at", desc=True
        ).limit(10).execute()

        recent_events = [PauseResumeEvent(**row) for row in events_result.data]

        return SystemStateResponse(
            state=self._state,
            can_trade=not self._state.is_paused,
            can_exit=True,  # Exits always work
            active_circuit_breakers=active_breakers,
            recent_events=recent_events
        )

    async def pause(self, request: PauseRequest) -> SystemState:
        """
        Manually pause the system.

        Args:
            request: Pause request with operator and reason

        Returns:
            Updated system state
        """
        db = await self._get_db()

        if self._state.is_paused:
            logger.warning(
                "pause_request_already_paused",
                current_status=self._state.status.value
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
            note=request.note
        )

        logger.warning(
            "system_paused_manual",
            operator=request.operator_id,
            reason=request.reason.value
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
        db = await self._get_db()

        if not self._state.is_paused:
            logger.warning("resume_request_not_paused")
            return self._state

        # Check if circuit breaker pause requires acknowledgement
        if self._state.is_circuit_breaker_pause and not request.acknowledge_warning:
            raise ValueError(
                f"Resuming from {self._state.status.value} requires explicit acknowledgement. "
                "Set acknowledge_warning=True to confirm."
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
            new_status=self._state.status
        )

        logger.info(
            "system_resumed",
            operator=request.operator_id,
            previous_status=previous_status.value
        )

        return self._state

    async def _clear_active_triggers(self, operator_id: str) -> None:
        """Clear active circuit breaker triggers."""
        db = await self._get_db()

        await db.table("circuit_breaker_triggers").update({
            "reset_at": datetime.utcnow().isoformat(),
            "reset_by": operator_id
        }).is_("reset_at", "null").execute()

    async def _save_state(self) -> None:
        """Persist current state to database."""
        db = await self._get_db()

        await db.table("system_config").upsert({
            "key": "system_state",
            "value": self._state.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        # Also update legacy system_status key for backward compatibility
        await db.table("system_config").upsert({
            "key": "system_status",
            "value": self._state.status.value,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    async def _record_event(
        self,
        event_type: str,
        operator_id: str,
        previous_status: SystemStatus,
        new_status: SystemStatus,
        reason: Optional[PauseReason] = None,
        note: Optional[str] = None
    ) -> None:
        """Record pause/resume event to history."""
        db = await self._get_db()

        event = PauseResumeEvent(
            event_type=event_type,
            operator_id=operator_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            note=note
        )

        await db.table("pause_resume_events").insert(
            event.model_dump(exclude={"id"}, mode="json")
        ).execute()

    async def set_circuit_breaker_pause(
        self,
        breaker_type: CircuitBreakerType
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
            note=f"Circuit breaker triggered: {breaker_type.value}"
        )

        return self._state

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
_state_manager: Optional[SystemStateManager] = None


async def get_system_state_manager() -> SystemStateManager:
    """Get or create system state manager singleton."""
    global _state_manager

    if _state_manager is None:
        _state_manager = SystemStateManager()
        await _state_manager.initialize()

    return _state_manager
```

### Database Schema (Supabase)

```sql
-- Pause/resume events history
CREATE TABLE pause_resume_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator_id VARCHAR(100) NOT NULL,
    previous_status VARCHAR(50) NOT NULL,
    new_status VARCHAR(50) NOT NULL,
    reason VARCHAR(50),
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pause_resume_events_date ON pause_resume_events(occurred_at DESC);
CREATE INDEX idx_pause_resume_events_type ON pause_resume_events(event_type);

-- Insert default system state
INSERT INTO system_config (key, value) VALUES
('system_state', '{
    "status": "running",
    "paused_at": null,
    "paused_by": null,
    "pause_reason": null,
    "pause_note": null,
    "resumed_at": null,
    "resumed_by": null
}')
ON CONFLICT (key) DO NOTHING;
```

### Gradio Dashboard Controls

```python
# src/walltrack/ui/components/system_controls.py
import gradio as gr
from datetime import datetime

from walltrack.core.risk.system_state import (
    get_system_state_manager,
    SystemStateManager
)
from walltrack.core.risk.models import (
    SystemStatus,
    PauseReason,
    PauseRequest,
    ResumeRequest
)


async def get_system_status() -> tuple[str, str, str]:
    """Get current system status for display."""
    manager = await get_system_state_manager()
    response = await manager.get_state()
    state = response.state

    # Status badge
    status_map = {
        SystemStatus.RUNNING: ("🟢 RUNNING", "System is actively trading"),
        SystemStatus.PAUSED_MANUAL: ("🟡 PAUSED (Manual)", f"Paused by {state.paused_by}"),
        SystemStatus.PAUSED_DRAWDOWN: ("🔴 PAUSED (Drawdown)", "Circuit breaker triggered"),
        SystemStatus.PAUSED_WIN_RATE: ("🔴 PAUSED (Win Rate)", "Circuit breaker triggered"),
        SystemStatus.PAUSED_CONSECUTIVE_LOSS: ("🔴 PAUSED (Loss Streak)", "Circuit breaker triggered"),
    }

    badge, desc = status_map.get(state.status, ("❓ UNKNOWN", "Unknown state"))

    # Details
    if state.is_paused:
        duration = state.pause_duration_seconds or 0
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        details = f"""
**Status:** {badge}
**Description:** {desc}

**Paused At:** {state.paused_at.strftime("%Y-%m-%d %H:%M:%S") if state.paused_at else "N/A"}
**Duration:** {hours}h {minutes}m
**Reason:** {state.pause_reason.value if state.pause_reason else "Circuit Breaker"}
**Note:** {state.pause_note or "None"}

**Exits Still Active:** Yes (existing positions can be managed)
"""
    else:
        details = f"""
**Status:** {badge}
**Description:** {desc}

**Trading:** Active
**Exits:** Active
"""

    # Active circuit breakers
    cb_list = "\n".join([f"- {cb}" for cb in response.active_circuit_breakers]) or "None"

    return badge, details, cb_list


async def pause_trading(
    reason: str,
    note: str,
    operator_id: str
) -> str:
    """Pause trading."""
    if not operator_id:
        return "Error: Operator ID required"

    manager = await get_system_state_manager()

    try:
        request = PauseRequest(
            operator_id=operator_id,
            reason=PauseReason(reason),
            note=note if note else None
        )
        state = await manager.pause(request)
        return f"System paused successfully by {operator_id}"
    except Exception as e:
        return f"Error: {str(e)}"


async def resume_trading(
    acknowledge: bool,
    operator_id: str
) -> str:
    """Resume trading."""
    if not operator_id:
        return "Error: Operator ID required"

    manager = await get_system_state_manager()

    try:
        request = ResumeRequest(
            operator_id=operator_id,
            acknowledge_warning=acknowledge
        )
        state = await manager.resume(request)
        return f"System resumed successfully by {operator_id}"
    except ValueError as e:
        return f"Warning: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


def create_system_controls_panel() -> gr.Blocks:
    """Create the system controls panel for the dashboard."""

    with gr.Blocks() as controls_panel:
        gr.Markdown("## System Controls")

        with gr.Row():
            with gr.Column(scale=2):
                status_badge = gr.Markdown("Loading...")
                status_details = gr.Markdown("Loading status...")

            with gr.Column(scale=1):
                gr.Markdown("### Active Circuit Breakers")
                circuit_breakers = gr.Markdown("Loading...")

        gr.Markdown("---")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Pause Trading")

                pause_reason = gr.Dropdown(
                    choices=[r.value for r in PauseReason],
                    value="maintenance",
                    label="Reason"
                )
                pause_note = gr.Textbox(
                    label="Note (optional)",
                    placeholder="Additional context..."
                )
                pause_operator = gr.Textbox(
                    label="Operator ID",
                    value="operator-1"
                )
                pause_btn = gr.Button("⏸️ Pause Trading", variant="stop")

            with gr.Column():
                gr.Markdown("### Resume Trading")

                resume_ack = gr.Checkbox(
                    label="I acknowledge resuming may be risky if circuit breaker was triggered",
                    value=False
                )
                resume_operator = gr.Textbox(
                    label="Operator ID",
                    value="operator-1"
                )
                resume_btn = gr.Button("▶️ Resume Trading", variant="primary")

        action_result = gr.Textbox(label="Result", interactive=False)

        refresh_btn = gr.Button("🔄 Refresh Status")

        # Event handlers
        refresh_btn.click(
            fn=get_system_status,
            outputs=[status_badge, status_details, circuit_breakers]
        )

        pause_btn.click(
            fn=pause_trading,
            inputs=[pause_reason, pause_note, pause_operator],
            outputs=[action_result]
        ).then(
            fn=get_system_status,
            outputs=[status_badge, status_details, circuit_breakers]
        )

        resume_btn.click(
            fn=resume_trading,
            inputs=[resume_ack, resume_operator],
            outputs=[action_result]
        ).then(
            fn=get_system_status,
            outputs=[status_badge, status_details, circuit_breakers]
        )

        # Initial load
        controls_panel.load(
            fn=get_system_status,
            outputs=[status_badge, status_details, circuit_breakers]
        )

    return controls_panel
```

### FastAPI Routes

```python
# src/walltrack/api/routes/system.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from walltrack.core.risk.system_state import (
    get_system_state_manager,
    SystemStateManager
)
from walltrack.core.risk.models import (
    SystemState,
    SystemStateResponse,
    PauseRequest,
    ResumeRequest
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/state", response_model=SystemStateResponse)
async def get_system_state(
    manager: SystemStateManager = Depends(get_system_state_manager)
):
    """Get current system state."""
    return await manager.get_state()


@router.get("/can-trade")
async def can_trade(
    manager: SystemStateManager = Depends(get_system_state_manager)
):
    """Check if trading is allowed."""
    return {"can_trade": manager.can_trade()}


@router.post("/pause", response_model=SystemState)
async def pause_system(
    request: PauseRequest,
    manager: SystemStateManager = Depends(get_system_state_manager)
):
    """Pause the trading system."""
    return await manager.pause(request)


@router.post("/resume", response_model=SystemState)
async def resume_system(
    request: ResumeRequest,
    manager: SystemStateManager = Depends(get_system_state_manager)
):
    """Resume the trading system."""
    try:
        return await manager.resume(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Unit Tests

```python
# tests/unit/risk/test_system_state.py
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from walltrack.core.risk.models import (
    SystemStatus,
    PauseReason,
    PauseRequest,
    ResumeRequest
)
from walltrack.core.risk.system_state import SystemStateManager


@pytest.fixture
def manager():
    return SystemStateManager()


class TestSystemStateInitial:
    """Test initial system state."""

    def test_initial_state_running(self, manager):
        """Initial state is running."""
        assert manager.state.status == SystemStatus.RUNNING
        assert manager.state.is_paused is False
        assert manager.can_trade() is True

    def test_exits_always_allowed(self, manager):
        """Exits are always allowed."""
        assert manager.can_exit() is True


class TestManualPause:
    """Test manual pause functionality."""

    @pytest.mark.asyncio
    async def test_pause_changes_state(self, manager):
        """Pause changes system state."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        request = PauseRequest(
            operator_id="operator-1",
            reason=PauseReason.MAINTENANCE,
            note="Scheduled maintenance"
        )

        with patch.object(manager, '_get_db', return_value=mock_db):
            state = await manager.pause(request)

            assert state.status == SystemStatus.PAUSED_MANUAL
            assert state.paused_by == "operator-1"
            assert state.pause_reason == PauseReason.MAINTENANCE
            assert manager.can_trade() is False

    @pytest.mark.asyncio
    async def test_pause_when_already_paused(self, manager):
        """Pause when already paused returns current state."""
        manager._state.status = SystemStatus.PAUSED_MANUAL

        request = PauseRequest(
            operator_id="operator-2",
            reason=PauseReason.INVESTIGATION
        )

        with patch.object(manager, '_get_db', new_callable=AsyncMock):
            state = await manager.pause(request)

            # State unchanged
            assert state.paused_by != "operator-2"


class TestResume:
    """Test resume functionality."""

    @pytest.mark.asyncio
    async def test_resume_from_manual_pause(self, manager):
        """Resume from manual pause."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        manager._state.paused_at = datetime.utcnow()
        manager._state.paused_by = "operator-1"

        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        request = ResumeRequest(operator_id="operator-1")

        with patch.object(manager, '_get_db', return_value=mock_db):
            state = await manager.resume(request)

            assert state.status == SystemStatus.RUNNING
            assert state.resumed_by == "operator-1"
            assert manager.can_trade() is True

    @pytest.mark.asyncio
    async def test_resume_from_circuit_breaker_requires_ack(self, manager):
        """Resume from circuit breaker requires acknowledgement."""
        manager._state.status = SystemStatus.PAUSED_DRAWDOWN

        request = ResumeRequest(
            operator_id="operator-1",
            acknowledge_warning=False
        )

        with pytest.raises(ValueError) as exc:
            await manager.resume(request)

        assert "acknowledge" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_resume_from_circuit_breaker_with_ack(self, manager):
        """Resume from circuit breaker with acknowledgement."""
        manager._state.status = SystemStatus.PAUSED_DRAWDOWN
        manager._state.paused_at = datetime.utcnow()

        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value.is_.return_value.execute = AsyncMock()

        request = ResumeRequest(
            operator_id="operator-1",
            acknowledge_warning=True
        )

        with patch.object(manager, '_get_db', return_value=mock_db):
            state = await manager.resume(request)

            assert state.status == SystemStatus.RUNNING


class TestCircuitBreakerPause:
    """Test circuit breaker pause."""

    @pytest.mark.asyncio
    async def test_set_circuit_breaker_pause(self, manager):
        """Circuit breaker sets appropriate pause status."""
        from walltrack.core.risk.models import CircuitBreakerType

        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            state = await manager.set_circuit_breaker_pause(
                CircuitBreakerType.DRAWDOWN
            )

            assert state.status == SystemStatus.PAUSED_DRAWDOWN
            assert state.paused_by == "system"
            assert state.is_circuit_breaker_pause is True


class TestExitsDuringPause:
    """Test that exits work during pause."""

    def test_can_exit_when_manual_pause(self, manager):
        """Exits allowed during manual pause."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        assert manager.can_exit() is True

    def test_can_exit_when_circuit_breaker(self, manager):
        """Exits allowed during circuit breaker pause."""
        manager._state.status = SystemStatus.PAUSED_DRAWDOWN
        assert manager.can_exit() is True

    def test_cannot_trade_when_paused(self, manager):
        """Cannot trade when paused."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        assert manager.can_trade() is False
```
