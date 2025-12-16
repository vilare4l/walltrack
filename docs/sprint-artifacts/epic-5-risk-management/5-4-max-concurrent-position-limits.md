# Story 5.4: Maximum Concurrent Position Limits

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: ready
- **Priority**: High
- **FR**: FR33

## User Story

**As an** operator,
**I want** limits on concurrent open positions,
**So that** capital isn't over-concentrated.

## Acceptance Criteria

### AC 1: Limit Check
**Given** max_concurrent_positions config (default 5)
**When** new trade is about to execute
**Then** current open position count is checked

### AC 2: Below Limit
**Given** open positions < max limit
**When** trade execution proceeds
**Then** trade executes normally
**And** position count increments

### AC 3: At Limit
**Given** open positions >= max limit
**When** new trade-eligible signal arrives
**Then** trade is blocked with reason "max_positions_reached"
**And** signal is logged but not executed
**And** operator can see queued/blocked signals

### AC 4: Position Close
**Given** a position closes
**When** position count decreases
**Then** next eligible signal can execute (if any pending)
**And** FIFO order for pending signals (oldest first)

### AC 5: Config Adjustment
**Given** position limit config
**When** operator adjusts via dashboard
**Then** new limit takes effect immediately
**And** existing positions are not affected

## Technical Notes

- FR33: Enforce maximum concurrent position limits
- Implement in `src/walltrack/core/risk/position_limits.py`
- Consider per-token limits as future enhancement

## Implementation Tasks

- [ ] Implement position count tracking
- [ ] Check limit before trade execution
- [ ] Block trades at max limit
- [ ] Queue signals when limit reached
- [ ] Execute pending signals on position close (FIFO)
- [ ] Make limit configurable via dashboard

## Definition of Done

- [ ] Position limit enforced correctly
- [ ] Trades blocked at max limit
- [ ] Pending signals execute on close
- [ ] Limit adjustable via dashboard

---

## Technical Specifications

### Pydantic Models

```python
# src/walltrack/core/risk/models.py (additions)
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from collections import deque


class PositionLimitConfig(BaseModel):
    """Configuration for maximum concurrent positions."""
    max_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent open positions"
    )
    enable_queue: bool = Field(
        default=True,
        description="Queue blocked signals for later execution"
    )
    max_queue_size: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum signals to queue (0 = unlimited)"
    )
    queue_expiry_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Minutes after which queued signals expire"
    )


class QueuedSignal(BaseModel):
    """Signal queued for later execution."""
    id: Optional[str] = None
    signal_id: str
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    signal_data: dict
    priority: int = Field(default=0)  # Higher = more priority
    status: str = Field(default="pending")  # pending, executed, expired, cancelled

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if signal has expired."""
        return datetime.utcnow() > self.expires_at

    @computed_field
    @property
    def time_remaining_seconds(self) -> int:
        """Seconds until expiry."""
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))


class PositionLimitCheckResult(BaseModel):
    """Result of position limit check."""
    current_positions: int
    max_positions: int
    can_open: bool
    slots_available: int
    queued_signals_count: int
    message: str


class PositionSlotEvent(BaseModel):
    """Event when position slot becomes available."""
    id: Optional[str] = None
    event_type: str  # "slot_freed", "signal_executed", "signal_expired"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    position_id: Optional[str] = None  # Position that closed
    signal_id: Optional[str] = None  # Signal that was processed
    queue_length_before: int
    queue_length_after: int


class BlockedTradeResponse(BaseModel):
    """Response when trade is blocked due to position limit."""
    blocked: bool = True
    reason: str
    current_positions: int
    max_positions: int
    queued: bool = False
    queue_position: Optional[int] = None
    signal_id: str
```

### PositionLimitManager Service

```python
# src/walltrack/core/risk/position_limits.py
import structlog
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Callable, Awaitable
from collections import deque
from supabase import AsyncClient

from walltrack.core.risk.models import (
    PositionLimitConfig,
    QueuedSignal,
    PositionLimitCheckResult,
    PositionSlotEvent,
    BlockedTradeResponse,
    BlockedSignal,
    CircuitBreakerType
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


class PositionLimitManager:
    """
    Manages maximum concurrent position limits.

    Enforces position limits and queues signals when limit reached.
    """

    def __init__(self, config: PositionLimitConfig):
        self.config = config
        self._supabase: Optional[AsyncClient] = None
        self._signal_queue: deque[QueuedSignal] = deque()
        self._execute_callback: Optional[Callable[[dict], Awaitable[bool]]] = None

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    def set_execute_callback(
        self,
        callback: Callable[[dict], Awaitable[bool]]
    ) -> None:
        """Set callback for executing queued signals."""
        self._execute_callback = callback

    async def initialize(self) -> None:
        """Load queued signals from database on startup."""
        db = await self._get_db()

        # Load pending queued signals
        result = await db.table("queued_signals").select("*").eq(
            "status", "pending"
        ).order("queued_at").execute()

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
            queued_signals=len(self._signal_queue)
        )

    async def get_open_position_count(self) -> int:
        """Get current number of open positions."""
        db = await self._get_db()

        result = await db.table("positions").select(
            "id", count="exact"
        ).eq("status", "open").execute()

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
            message=message
        )

    async def request_position(
        self,
        signal_id: str,
        signal_data: dict
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
                max=check.max_positions
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
                signal_id=signal_id
            )
        else:
            # Just block without queuing
            await self._record_blocked_signal(signal_id, signal_data)
            return BlockedTradeResponse(
                reason="max_positions_reached",
                current_positions=check.current_positions,
                max_positions=check.max_positions,
                queued=False,
                signal_id=signal_id
            )

    async def _queue_signal(
        self,
        signal_id: str,
        signal_data: dict
    ) -> int:
        """Add signal to queue for later execution."""
        db = await self._get_db()

        # Check queue limit
        if self.config.max_queue_size > 0:
            if len(self._signal_queue) >= self.config.max_queue_size:
                # Queue full - remove oldest
                oldest = self._signal_queue.popleft()
                await self._mark_signal_expired(oldest.id)
                logger.warning(
                    "queue_full_removed_oldest",
                    removed_signal=oldest.signal_id
                )

        expires_at = datetime.utcnow() + timedelta(
            minutes=self.config.queue_expiry_minutes
        )

        signal = QueuedSignal(
            signal_id=signal_id,
            expires_at=expires_at,
            signal_data=signal_data
        )

        result = await db.table("queued_signals").insert(
            signal.model_dump(exclude={"id", "is_expired", "time_remaining_seconds"}, mode="json")
        ).execute()

        signal.id = result.data[0]["id"]
        self._signal_queue.append(signal)

        logger.info(
            "signal_queued",
            signal_id=signal_id,
            queue_position=len(self._signal_queue),
            expires_in_minutes=self.config.queue_expiry_minutes
        )

        return len(self._signal_queue)

    async def _record_blocked_signal(
        self,
        signal_id: str,
        signal_data: dict
    ) -> None:
        """Record blocked signal (not queued)."""
        db = await self._get_db()

        blocked = BlockedSignal(
            signal_id=signal_id,
            breaker_type=CircuitBreakerType.MANUAL,  # Using MANUAL for position limit
            reason="max_positions_reached",
            signal_data=signal_data
        )

        await db.table("blocked_signals").insert(
            blocked.model_dump(mode="json")
        ).execute()

    async def _mark_signal_expired(self, signal_db_id: str) -> None:
        """Mark a signal as expired in database."""
        db = await self._get_db()
        await db.table("queued_signals").update({
            "status": "expired"
        }).eq("id", signal_db_id).execute()

    async def on_position_closed(self, position_id: str) -> Optional[QueuedSignal]:
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
                position_id=position_id
            )
            return None

        # Get next signal (FIFO)
        next_signal = self._signal_queue.popleft()

        # Record event
        await db.table("position_slot_events").insert({
            "event_type": "signal_executed",
            "position_id": position_id,
            "signal_id": next_signal.signal_id,
            "queue_length_before": queue_length_before,
            "queue_length_after": len(self._signal_queue)
        }).execute()

        # Mark signal as executed
        await db.table("queued_signals").update({
            "status": "executed"
        }).eq("id", next_signal.id).execute()

        logger.info(
            "queued_signal_executing",
            signal_id=next_signal.signal_id,
            queue_remaining=len(self._signal_queue)
        )

        # Execute via callback if set
        if self._execute_callback:
            try:
                await self._execute_callback(next_signal.signal_data)
            except Exception as e:
                logger.error(
                    "queued_signal_execution_failed",
                    signal_id=next_signal.signal_id,
                    error=str(e)
                )

        return next_signal

    async def _clean_expired_signals(self) -> int:
        """Remove expired signals from queue."""
        db = await self._get_db()
        removed = 0

        while self._signal_queue:
            signal = self._signal_queue[0]
            if signal.is_expired:
                self._signal_queue.popleft()
                await self._mark_signal_expired(signal.id)
                removed += 1
                logger.info(
                    "queued_signal_expired",
                    signal_id=signal.signal_id
                )
            else:
                break

        return removed

    async def get_queue_status(self) -> List[QueuedSignal]:
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
                await db.table("queued_signals").update({
                    "status": "cancelled"
                }).eq("signal_id", signal_id).execute()

                logger.info(
                    "queued_signal_cancelled",
                    signal_id=signal_id
                )
                return True

        return False

    async def update_config(self, config: PositionLimitConfig) -> None:
        """Update configuration."""
        db = await self._get_db()

        await db.table("system_config").upsert({
            "key": "position_limit_config",
            "value": config.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        self.config = config

        logger.info(
            "position_limit_config_updated",
            max_positions=config.max_positions
        )


# Singleton instance
_position_limit_manager: Optional[PositionLimitManager] = None


async def get_position_limit_manager(
    config: Optional[PositionLimitConfig] = None
) -> PositionLimitManager:
    """Get or create position limit manager singleton."""
    global _position_limit_manager

    if _position_limit_manager is None:
        if config is None:
            db = await get_supabase_client()
            result = await db.table("system_config").select("value").eq(
                "key", "position_limit_config"
            ).single().execute()
            config = PositionLimitConfig(**result.data["value"])

        _position_limit_manager = PositionLimitManager(config)
        await _position_limit_manager.initialize()

    return _position_limit_manager
```

### Database Schema (Supabase)

```sql
-- Queued signals waiting for position slot
CREATE TABLE queued_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(100) NOT NULL,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    signal_data JSONB NOT NULL DEFAULT '{}',
    priority INTEGER DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_queued_signals_status ON queued_signals(status);
CREATE INDEX idx_queued_signals_expires ON queued_signals(expires_at)
    WHERE status = 'pending';

-- Position slot events for tracking
CREATE TABLE position_slot_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    position_id VARCHAR(100),
    signal_id VARCHAR(100),
    queue_length_before INTEGER NOT NULL,
    queue_length_after INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_position_slot_events_date ON position_slot_events(occurred_at DESC);

-- Insert default position limit config
INSERT INTO system_config (key, value) VALUES
('position_limit_config', '{
    "max_positions": 5,
    "enable_queue": true,
    "max_queue_size": 10,
    "queue_expiry_minutes": 60
}')
ON CONFLICT (key) DO NOTHING;
```

### FastAPI Routes

```python
# src/walltrack/api/routes/risk.py (additions)
from walltrack.core.risk.position_limits import (
    get_position_limit_manager,
    PositionLimitManager
)
from walltrack.core.risk.models import (
    PositionLimitConfig,
    PositionLimitCheckResult,
    QueuedSignal,
    BlockedTradeResponse
)


class PositionRequestBody(BaseModel):
    signal_id: str
    signal_data: dict


@router.get("/position-limit/check", response_model=PositionLimitCheckResult)
async def check_position_limit(
    manager: PositionLimitManager = Depends(get_position_limit_manager)
):
    """Check if a new position can be opened."""
    return await manager.check_can_open()


@router.post("/position-limit/request")
async def request_position(
    body: PositionRequestBody,
    manager: PositionLimitManager = Depends(get_position_limit_manager)
):
    """Request to open a position."""
    result = await manager.request_position(body.signal_id, body.signal_data)
    if result is True:
        return {"allowed": True}
    return result


@router.get("/position-limit/queue", response_model=List[QueuedSignal])
async def get_signal_queue(
    manager: PositionLimitManager = Depends(get_position_limit_manager)
):
    """Get queued signals waiting for position slots."""
    return await manager.get_queue_status()


@router.delete("/position-limit/queue/{signal_id}")
async def cancel_queued_signal(
    signal_id: str,
    manager: PositionLimitManager = Depends(get_position_limit_manager)
):
    """Cancel a queued signal."""
    success = await manager.cancel_queued_signal(signal_id)
    if success:
        return {"status": "cancelled", "signal_id": signal_id}
    raise HTTPException(status_code=404, detail="Signal not found in queue")


@router.post("/position-limit/position-closed/{position_id}")
async def notify_position_closed(
    position_id: str,
    manager: PositionLimitManager = Depends(get_position_limit_manager)
):
    """Notify that a position was closed (triggers queue processing)."""
    executed = await manager.on_position_closed(position_id)
    return {
        "position_closed": position_id,
        "next_signal_executed": executed.signal_id if executed else None
    }


@router.put("/position-limit/config")
async def update_position_limit_config(
    config: PositionLimitConfig,
    manager: PositionLimitManager = Depends(get_position_limit_manager)
):
    """Update position limit configuration."""
    await manager.update_config(config)
    return {"status": "updated", "config": config}
```

### Unit Tests

```python
# tests/unit/risk/test_position_limits.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from walltrack.core.risk.models import (
    PositionLimitConfig,
    QueuedSignal,
    PositionLimitCheckResult
)
from walltrack.core.risk.position_limits import PositionLimitManager


@pytest.fixture
def limit_config():
    return PositionLimitConfig(
        max_positions=5,
        enable_queue=True,
        max_queue_size=10,
        queue_expiry_minutes=60
    )


@pytest.fixture
def manager(limit_config):
    return PositionLimitManager(limit_config)


class TestPositionLimitCheck:
    """Test position limit check logic."""

    @pytest.mark.asyncio
    async def test_can_open_when_below_limit(self, manager):
        """Can open when below position limit."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 3

        with patch.object(manager, '_get_db', return_value=mock_db):
            result = await manager.check_can_open()

            assert result.can_open is True
            assert result.current_positions == 3
            assert result.slots_available == 2

    @pytest.mark.asyncio
    async def test_cannot_open_at_limit(self, manager):
        """Cannot open when at position limit."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 5

        with patch.object(manager, '_get_db', return_value=mock_db):
            result = await manager.check_can_open()

            assert result.can_open is False
            assert result.slots_available == 0


class TestPositionRequest:
    """Test position request handling."""

    @pytest.mark.asyncio
    async def test_request_allowed_below_limit(self, manager):
        """Request allowed when below limit."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 3

        with patch.object(manager, '_get_db', return_value=mock_db):
            result = await manager.request_position("sig-1", {"token": "PUMP"})

            assert result is True

    @pytest.mark.asyncio
    async def test_request_queued_at_limit(self, manager):
        """Request queued when at limit."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 5
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "queue-1"}
        ]

        with patch.object(manager, '_get_db', return_value=mock_db):
            result = await manager.request_position("sig-1", {"token": "PUMP"})

            assert result.blocked is True
            assert result.queued is True
            assert result.queue_position == 1

    @pytest.mark.asyncio
    async def test_request_blocked_no_queue(self, manager):
        """Request blocked without queue when disabled."""
        manager.config.enable_queue = False

        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 5
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            result = await manager.request_position("sig-1", {"token": "PUMP"})

            assert result.blocked is True
            assert result.queued is False


class TestSignalQueue:
    """Test signal queue management."""

    @pytest.mark.asyncio
    async def test_queue_fifo_order(self, manager):
        """Queue maintains FIFO order."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 5
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "queue-1"}
        ]

        with patch.object(manager, '_get_db', return_value=mock_db):
            await manager.request_position("sig-1", {})
            mock_db.table.return_value.insert.return_value.execute.return_value.data = [
                {"id": "queue-2"}
            ]
            await manager.request_position("sig-2", {})

            queue = await manager.get_queue_status()

            assert len(queue) == 2
            assert queue[0].signal_id == "sig-1"
            assert queue[1].signal_id == "sig-2"

    @pytest.mark.asyncio
    async def test_queue_max_size_removes_oldest(self, manager):
        """Queue removes oldest when max size reached."""
        manager.config.max_queue_size = 2

        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 5
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "queue-x"}
        ]
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            await manager.request_position("sig-1", {})
            await manager.request_position("sig-2", {})
            await manager.request_position("sig-3", {})

            queue = await manager.get_queue_status()

            assert len(queue) == 2
            # sig-1 should have been removed
            assert queue[0].signal_id == "sig-2"


class TestPositionClosed:
    """Test position closed handling."""

    @pytest.mark.asyncio
    async def test_execute_next_on_close(self, manager):
        """Next queued signal executes when position closes."""
        # Pre-populate queue
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={"token": "PUMP"}
        )
        manager._signal_queue.append(signal)

        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            executed = await manager.on_position_closed("pos-1")

            assert executed is not None
            assert executed.signal_id == "sig-1"
            assert len(manager._signal_queue) == 0

    @pytest.mark.asyncio
    async def test_no_execute_empty_queue(self, manager):
        """Nothing executes when queue is empty."""
        mock_db = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            executed = await manager.on_position_closed("pos-1")

            assert executed is None


class TestCancelQueued:
    """Test signal cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_queued_signal(self, manager):
        """Can cancel queued signal."""
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={}
        )
        manager._signal_queue.append(signal)

        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            success = await manager.cancel_queued_signal("sig-1")

            assert success is True
            assert len(manager._signal_queue) == 0

    @pytest.mark.asyncio
    async def test_cancel_not_found(self, manager):
        """Cancel returns False for non-existent signal."""
        mock_db = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            success = await manager.cancel_queued_signal("not-exist")

            assert success is False
```
