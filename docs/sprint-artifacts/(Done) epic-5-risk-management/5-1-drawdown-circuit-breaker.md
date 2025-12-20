# Story 5.1: Drawdown Circuit Breaker

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: Done
- **Priority**: High
- **FR**: FR28

## User Story

**As an** operator,
**I want** trading to pause automatically when drawdown exceeds threshold,
**So that** catastrophic losses are prevented.

## Acceptance Criteria

### AC 1: Drawdown Calculation
**Given** trading is active
**When** drawdown calculation runs
**Then** current drawdown = (peak_capital - current_capital) / peak_capital
**And** peak_capital is the highest value since system start or last reset

### AC 2: Circuit Breaker Trigger
**Given** drawdown exceeds threshold (default 20%)
**When** circuit breaker triggers
**Then** all new trades are blocked immediately
**And** existing positions continue to be managed (exits still work)
**And** system status changes to "paused_drawdown"
**And** timestamp and drawdown value are recorded

### AC 3: Signal Blocking
**Given** circuit breaker is active
**When** new trade-eligible signal arrives
**Then** signal is logged with status "blocked_circuit_breaker"
**And** signal is NOT executed
**And** operator is notified

### AC 4: Manual Reset
**Given** drawdown circuit breaker triggered
**When** operator reviews situation
**Then** manual reset is required to resume trading
**And** reset requires confirmation

## Technical Notes

- FR28: Pause all trading when drawdown exceeds threshold (20%)
- Implement in `src/walltrack/core/risk/circuit_breaker.py`
- Track peak_capital in Supabase
- Drawdown threshold configurable via dashboard

## Implementation Tasks

- [x] Create `src/walltrack/core/risk/circuit_breaker.py`
- [x] Implement drawdown calculation
- [x] Track peak_capital
- [x] Implement circuit breaker trigger
- [x] Block new trades while keeping exits active
- [x] Require manual reset to resume
- [x] Make threshold configurable

## Definition of Done

- [x] Drawdown calculated correctly
- [x] Circuit breaker triggers at threshold
- [x] New trades blocked, exits continue
- [x] Manual reset required to resume

## Implementation Summary

**Completed:** 2024-12-20

**Files Created/Modified:**
- `src/walltrack/core/risk/circuit_breaker.py` - DrawdownCircuitBreaker class
- `src/walltrack/models/risk.py` - Pydantic models (CircuitBreakerType, SystemStatus, DrawdownConfig, etc.)
- `src/walltrack/data/supabase/migrations/010_risk_management.sql` - Database schema
- `tests/unit/risk/test_drawdown_circuit_breaker.py` - 17 unit tests

**Test Coverage:** 17 tests passing

---

## Technical Specifications

### Pydantic Models

```python
# src/walltrack/core/risk/models.py
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional


class CircuitBreakerType(str, Enum):
    """Type of circuit breaker."""
    DRAWDOWN = "drawdown"
    WIN_RATE = "win_rate"
    CONSECUTIVE_LOSS = "consecutive_loss"
    MANUAL = "manual"


class SystemStatus(str, Enum):
    """System trading status."""
    RUNNING = "running"
    PAUSED_DRAWDOWN = "paused_drawdown"
    PAUSED_WIN_RATE = "paused_win_rate"
    PAUSED_CONSECUTIVE_LOSS = "paused_consecutive_loss"
    PAUSED_MANUAL = "paused_manual"


class DrawdownConfig(BaseModel):
    """Configuration for drawdown circuit breaker."""
    threshold_percent: Decimal = Field(
        default=Decimal("20.0"),
        ge=Decimal("5.0"),
        le=Decimal("50.0"),
        description="Drawdown threshold to trigger circuit breaker"
    )
    initial_capital: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Initial capital at system start"
    )

    class Config:
        json_encoders = {Decimal: str}


class CapitalSnapshot(BaseModel):
    """Point-in-time capital snapshot."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    capital: Decimal = Field(..., description="Current capital value")
    peak_capital: Decimal = Field(..., description="Peak capital since start/reset")

    @computed_field
    @property
    def drawdown_amount(self) -> Decimal:
        """Absolute drawdown amount."""
        return self.peak_capital - self.capital

    @computed_field
    @property
    def drawdown_percent(self) -> Decimal:
        """Drawdown as percentage of peak."""
        if self.peak_capital == Decimal("0"):
            return Decimal("0")
        return (self.drawdown_amount / self.peak_capital) * Decimal("100")


class CircuitBreakerTrigger(BaseModel):
    """Record of circuit breaker trigger event."""
    id: Optional[str] = None
    breaker_type: CircuitBreakerType
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    threshold_value: Decimal = Field(..., description="Threshold that was exceeded")
    actual_value: Decimal = Field(..., description="Actual value that triggered")
    capital_at_trigger: Decimal = Field(..., description="Capital when triggered")
    peak_capital_at_trigger: Decimal = Field(..., description="Peak capital when triggered")
    reset_at: Optional[datetime] = None
    reset_by: Optional[str] = None  # operator ID or "system"

    @computed_field
    @property
    def is_active(self) -> bool:
        """Whether this circuit breaker is still active."""
        return self.reset_at is None


class DrawdownCheckResult(BaseModel):
    """Result of drawdown check."""
    current_capital: Decimal
    peak_capital: Decimal
    drawdown_percent: Decimal
    threshold_percent: Decimal
    is_breached: bool
    trigger: Optional[CircuitBreakerTrigger] = None


class BlockedSignal(BaseModel):
    """Record of a signal blocked by circuit breaker."""
    signal_id: str
    blocked_at: datetime = Field(default_factory=datetime.utcnow)
    breaker_type: CircuitBreakerType
    reason: str
    signal_data: dict = Field(default_factory=dict)
```

### DrawdownCircuitBreaker Service

```python
# src/walltrack/core/risk/circuit_breaker.py
import structlog
from decimal import Decimal
from datetime import datetime
from typing import Optional
from supabase import AsyncClient

from walltrack.core.risk.models import (
    CircuitBreakerType,
    SystemStatus,
    DrawdownConfig,
    CapitalSnapshot,
    CircuitBreakerTrigger,
    DrawdownCheckResult,
    BlockedSignal
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


class DrawdownCircuitBreaker:
    """
    Manages drawdown-based circuit breaker logic.

    Tracks peak capital and triggers pause when drawdown exceeds threshold.
    """

    def __init__(self, config: DrawdownConfig):
        self.config = config
        self._supabase: Optional[AsyncClient] = None
        self._current_capital: Decimal = config.initial_capital
        self._peak_capital: Decimal = config.initial_capital

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load state from database on startup."""
        db = await self._get_db()

        # Load latest capital snapshot
        result = await db.table("capital_snapshots").select("*").order(
            "timestamp", desc=True
        ).limit(1).execute()

        if result.data:
            snapshot = result.data[0]
            self._current_capital = Decimal(str(snapshot["capital"]))
            self._peak_capital = Decimal(str(snapshot["peak_capital"]))

        logger.info(
            "drawdown_circuit_breaker_initialized",
            current_capital=str(self._current_capital),
            peak_capital=str(self._peak_capital),
            threshold=str(self.config.threshold_percent)
        )

    def calculate_drawdown(self, current_capital: Decimal) -> CapitalSnapshot:
        """
        Calculate current drawdown.

        Updates peak capital if current is higher (never decreases).
        """
        # Update peak if new high
        if current_capital > self._peak_capital:
            self._peak_capital = current_capital

        self._current_capital = current_capital

        return CapitalSnapshot(
            capital=current_capital,
            peak_capital=self._peak_capital
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
            is_breached=is_breached
        )

        if is_breached:
            trigger = await self._create_trigger(snapshot)
            result.trigger = trigger

            logger.warning(
                "drawdown_circuit_breaker_triggered",
                drawdown_percent=str(snapshot.drawdown_percent),
                threshold=str(self.config.threshold_percent),
                capital=str(snapshot.capital),
                peak=str(snapshot.peak_capital)
            )

        return result

    async def _create_trigger(self, snapshot: CapitalSnapshot) -> CircuitBreakerTrigger:
        """Create and persist circuit breaker trigger record."""
        db = await self._get_db()

        trigger = CircuitBreakerTrigger(
            breaker_type=CircuitBreakerType.DRAWDOWN,
            threshold_value=self.config.threshold_percent,
            actual_value=snapshot.drawdown_percent,
            capital_at_trigger=snapshot.capital,
            peak_capital_at_trigger=snapshot.peak_capital
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

        await db.table("system_config").upsert({
            "key": "system_status",
            "value": status.value,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    async def record_capital_snapshot(self, capital: Decimal) -> CapitalSnapshot:
        """Record capital snapshot to database."""
        db = await self._get_db()
        snapshot = self.calculate_drawdown(capital)

        await db.table("capital_snapshots").insert({
            "timestamp": snapshot.timestamp.isoformat(),
            "capital": str(snapshot.capital),
            "peak_capital": str(snapshot.peak_capital),
            "drawdown_percent": str(snapshot.drawdown_percent)
        }).execute()

        return snapshot

    async def reset(self, operator_id: str, new_peak: Optional[Decimal] = None) -> None:
        """
        Reset circuit breaker (requires manual action).

        Args:
            operator_id: ID of operator performing reset
            new_peak: Optional new peak capital (defaults to current)
        """
        db = await self._get_db()

        # Mark active trigger as reset
        await db.table("circuit_breaker_triggers").update({
            "reset_at": datetime.utcnow().isoformat(),
            "reset_by": operator_id
        }).eq("breaker_type", CircuitBreakerType.DRAWDOWN.value).is_(
            "reset_at", "null"
        ).execute()

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
            new_peak=str(self._peak_capital)
        )

    async def block_signal(
        self,
        signal_id: str,
        signal_data: dict
    ) -> BlockedSignal:
        """Record a signal blocked due to circuit breaker."""
        db = await self._get_db()

        blocked = BlockedSignal(
            signal_id=signal_id,
            breaker_type=CircuitBreakerType.DRAWDOWN,
            reason=f"Drawdown circuit breaker active (threshold: {self.config.threshold_percent}%)",
            signal_data=signal_data
        )

        await db.table("blocked_signals").insert(
            blocked.model_dump(mode="json")
        ).execute()

        logger.info(
            "signal_blocked_drawdown",
            signal_id=signal_id
        )

        return blocked

    @property
    def current_drawdown_percent(self) -> Decimal:
        """Current drawdown percentage."""
        if self._peak_capital == Decimal("0"):
            return Decimal("0")
        return ((self._peak_capital - self._current_capital) / self._peak_capital) * Decimal("100")


# Singleton instance
_drawdown_breaker: Optional[DrawdownCircuitBreaker] = None


async def get_drawdown_circuit_breaker(
    config: Optional[DrawdownConfig] = None
) -> DrawdownCircuitBreaker:
    """Get or create drawdown circuit breaker singleton."""
    global _drawdown_breaker

    if _drawdown_breaker is None:
        if config is None:
            # Load from database
            db = await get_supabase_client()
            result = await db.table("system_config").select("value").eq(
                "key", "drawdown_config"
            ).single().execute()
            config = DrawdownConfig(**result.data["value"])

        _drawdown_breaker = DrawdownCircuitBreaker(config)
        await _drawdown_breaker.initialize()

    return _drawdown_breaker
```

### Database Schema (Supabase)

```sql
-- Capital snapshots for tracking peak and drawdown
CREATE TABLE capital_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    capital DECIMAL(20, 8) NOT NULL,
    peak_capital DECIMAL(20, 8) NOT NULL,
    drawdown_percent DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_capital_snapshots_timestamp ON capital_snapshots(timestamp DESC);

-- Circuit breaker trigger history
CREATE TABLE circuit_breaker_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    breaker_type VARCHAR(50) NOT NULL,
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    threshold_value DECIMAL(10, 4) NOT NULL,
    actual_value DECIMAL(10, 4) NOT NULL,
    capital_at_trigger DECIMAL(20, 8) NOT NULL,
    peak_capital_at_trigger DECIMAL(20, 8) NOT NULL,
    reset_at TIMESTAMPTZ,
    reset_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_circuit_breaker_type ON circuit_breaker_triggers(breaker_type);
CREATE INDEX idx_circuit_breaker_active ON circuit_breaker_triggers(breaker_type)
    WHERE reset_at IS NULL;

-- Blocked signals due to circuit breakers
CREATE TABLE blocked_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id VARCHAR(100) NOT NULL,
    blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    breaker_type VARCHAR(50) NOT NULL,
    reason TEXT NOT NULL,
    signal_data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_blocked_signals_date ON blocked_signals(blocked_at DESC);

-- System configuration (key-value store)
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default drawdown config
INSERT INTO system_config (key, value) VALUES
('drawdown_config', '{"threshold_percent": "20.0", "initial_capital": "1000.0"}'),
('system_status', '"running"')
ON CONFLICT (key) DO NOTHING;
```

### FastAPI Routes

```python
# src/walltrack/api/routes/risk.py
from fastapi import APIRouter, Depends, HTTPException
from decimal import Decimal
from pydantic import BaseModel

from walltrack.core.risk.circuit_breaker import (
    get_drawdown_circuit_breaker,
    DrawdownCircuitBreaker
)
from walltrack.core.risk.models import (
    DrawdownConfig,
    DrawdownCheckResult,
    CapitalSnapshot,
    CircuitBreakerTrigger
)

router = APIRouter(prefix="/risk", tags=["risk"])


class DrawdownStatusResponse(BaseModel):
    current_capital: Decimal
    peak_capital: Decimal
    drawdown_percent: Decimal
    threshold_percent: Decimal
    is_breached: bool
    active_trigger: CircuitBreakerTrigger | None = None


class ResetRequest(BaseModel):
    operator_id: str
    reset_peak: bool = False
    new_peak: Decimal | None = None


@router.get("/drawdown/status", response_model=DrawdownStatusResponse)
async def get_drawdown_status(
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker)
):
    """Get current drawdown status."""
    # Get active trigger if any
    db = await breaker._get_db()
    trigger_result = await db.table("circuit_breaker_triggers").select("*").eq(
        "breaker_type", "drawdown"
    ).is_("reset_at", "null").single().execute()

    active_trigger = None
    if trigger_result.data:
        active_trigger = CircuitBreakerTrigger(**trigger_result.data)

    return DrawdownStatusResponse(
        current_capital=breaker._current_capital,
        peak_capital=breaker._peak_capital,
        drawdown_percent=breaker.current_drawdown_percent,
        threshold_percent=breaker.config.threshold_percent,
        is_breached=active_trigger is not None,
        active_trigger=active_trigger
    )


@router.post("/drawdown/check", response_model=DrawdownCheckResult)
async def check_drawdown(
    current_capital: Decimal,
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker)
):
    """Check drawdown and trigger circuit breaker if needed."""
    return await breaker.check_drawdown(current_capital)


@router.post("/drawdown/reset")
async def reset_drawdown_breaker(
    request: ResetRequest,
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker)
):
    """Reset drawdown circuit breaker (manual action required)."""
    new_peak = request.new_peak if request.reset_peak else None
    await breaker.reset(request.operator_id, new_peak)
    return {"status": "reset", "operator_id": request.operator_id}


@router.put("/drawdown/config")
async def update_drawdown_config(
    config: DrawdownConfig,
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker)
):
    """Update drawdown threshold configuration."""
    db = await breaker._get_db()

    await db.table("system_config").upsert({
        "key": "drawdown_config",
        "value": config.model_dump(mode="json")
    }).execute()

    breaker.config = config
    return {"status": "updated", "config": config}
```

### Unit Tests

```python
# tests/unit/risk/test_drawdown_circuit_breaker.py
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, patch

from walltrack.core.risk.models import (
    CircuitBreakerType,
    DrawdownConfig,
    CapitalSnapshot,
    DrawdownCheckResult
)
from walltrack.core.risk.circuit_breaker import DrawdownCircuitBreaker


@pytest.fixture
def drawdown_config():
    return DrawdownConfig(
        threshold_percent=Decimal("20.0"),
        initial_capital=Decimal("1000.0")
    )


@pytest.fixture
def breaker(drawdown_config):
    return DrawdownCircuitBreaker(drawdown_config)


class TestDrawdownCalculation:
    """Test drawdown calculation logic."""

    def test_initial_state_no_drawdown(self, breaker):
        """Initial capital has zero drawdown."""
        snapshot = breaker.calculate_drawdown(Decimal("1000.0"))

        assert snapshot.capital == Decimal("1000.0")
        assert snapshot.peak_capital == Decimal("1000.0")
        assert snapshot.drawdown_percent == Decimal("0")

    def test_capital_increase_updates_peak(self, breaker):
        """Peak capital increases with new highs."""
        snapshot = breaker.calculate_drawdown(Decimal("1500.0"))

        assert snapshot.peak_capital == Decimal("1500.0")
        assert snapshot.drawdown_percent == Decimal("0")

    def test_capital_decrease_creates_drawdown(self, breaker):
        """Capital decrease creates drawdown from peak."""
        # First go up
        breaker.calculate_drawdown(Decimal("1500.0"))

        # Then go down
        snapshot = breaker.calculate_drawdown(Decimal("1200.0"))

        assert snapshot.capital == Decimal("1200.0")
        assert snapshot.peak_capital == Decimal("1500.0")
        # (1500 - 1200) / 1500 = 0.2 = 20%
        assert snapshot.drawdown_percent == Decimal("20.0")

    def test_peak_never_decreases(self, breaker):
        """Peak capital never decreases even with losses."""
        breaker.calculate_drawdown(Decimal("2000.0"))
        breaker.calculate_drawdown(Decimal("1000.0"))
        breaker.calculate_drawdown(Decimal("800.0"))

        assert breaker._peak_capital == Decimal("2000.0")


class TestCircuitBreakerTrigger:
    """Test circuit breaker trigger logic."""

    @pytest.mark.asyncio
    async def test_no_trigger_below_threshold(self, breaker):
        """No trigger when drawdown below threshold."""
        with patch.object(breaker, '_get_db', new_callable=AsyncMock):
            result = await breaker.check_drawdown(Decimal("900.0"))

            # 10% drawdown, threshold is 20%
            assert result.is_breached is False
            assert result.trigger is None

    @pytest.mark.asyncio
    async def test_trigger_at_threshold(self, breaker):
        """Trigger when drawdown equals threshold."""
        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "trigger-123"}
        ]
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            result = await breaker.check_drawdown(Decimal("800.0"))

            # 20% drawdown = threshold
            assert result.is_breached is True
            assert result.trigger is not None
            assert result.trigger.breaker_type == CircuitBreakerType.DRAWDOWN

    @pytest.mark.asyncio
    async def test_trigger_above_threshold(self, breaker):
        """Trigger when drawdown exceeds threshold."""
        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "trigger-456"}
        ]
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            result = await breaker.check_drawdown(Decimal("700.0"))

            # 30% drawdown > 20% threshold
            assert result.is_breached is True
            assert result.drawdown_percent == Decimal("30.0")


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_updates_database(self, breaker):
        """Reset updates database records."""
        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            await breaker.reset("operator-1")

            # Verify trigger was marked as reset
            mock_db.table.assert_any_call("circuit_breaker_triggers")

    @pytest.mark.asyncio
    async def test_reset_with_new_peak(self, breaker):
        """Reset can set new peak capital."""
        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        breaker._current_capital = Decimal("800.0")

        with patch.object(breaker, '_get_db', return_value=mock_db):
            await breaker.reset("operator-1", new_peak=Decimal("800.0"))

            assert breaker._peak_capital == Decimal("800.0")


class TestBlockedSignals:
    """Test signal blocking functionality."""

    @pytest.mark.asyncio
    async def test_block_signal_records_to_db(self, breaker):
        """Blocked signals are recorded to database."""
        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            blocked = await breaker.block_signal(
                "signal-123",
                {"token": "PUMP", "action": "buy"}
            )

            assert blocked.signal_id == "signal-123"
            assert blocked.breaker_type == CircuitBreakerType.DRAWDOWN
            mock_db.table.assert_called_with("blocked_signals")
```
