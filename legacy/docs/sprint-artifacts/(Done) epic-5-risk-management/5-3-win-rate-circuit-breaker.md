# Story 5.3: Win Rate Circuit Breaker

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: Done
- **Priority**: Medium
- **FR**: FR30

## User Story

**As an** operator,
**I want** trading to halt when win rate drops too low,
**So that** a broken strategy doesn't continue losing.

## Acceptance Criteria

### AC 1: Win Rate Calculation
**Given** trade history exists
**When** win rate is calculated
**Then** calculation uses rolling window of N trades (default 50)
**And** win_rate = winning_trades / total_trades in window

### AC 2: Threshold Breach
**Given** win rate falls below threshold (default 40%)
**When** threshold is breached
**Then** circuit breaker triggers
**And** all new trades are blocked
**And** system status changes to "paused_win_rate"
**And** current win rate and threshold are logged

### AC 3: Review and Reset
**Given** win rate circuit breaker active
**When** operator reviews
**Then** recent trade analysis is available
**And** losing patterns can be investigated
**And** manual reset or recalibration is required

### AC 4: Insufficient History
**Given** insufficient trade history (< N trades)
**When** win rate is checked
**Then** circuit breaker does not apply yet
**And** system continues with caution flag

## Technical Notes

- FR30: Halt trading when win rate falls below threshold over N trades
- Implement in `src/walltrack/core/risk/circuit_breaker.py`
- Window size and threshold configurable

## Implementation Tasks

- [x] Implement rolling window win rate calculation
- [x] Trigger circuit breaker on threshold breach
- [x] Change system status to "paused_win_rate"
- [x] Handle insufficient trade history
- [x] Require manual reset to resume
- [x] Make window size and threshold configurable

## Definition of Done

- [x] Win rate calculated over rolling window
- [x] Circuit breaker triggers at threshold
- [x] Insufficient history handled gracefully
- [x] Manual reset required to resume

## Implementation Summary

**Completed:** 2024-12-20

**Files Created/Modified:**
- `src/walltrack/core/risk/win_rate_breaker.py` - WinRateCircuitBreaker class
- `src/walltrack/models/risk.py` - Models (WinRateConfig, WinRateSnapshot, WinRateBreachResult, TradeAnalysis)
- `src/walltrack/data/supabase/migrations/010_risk_management.sql` - win_rate_snapshots table
- `tests/unit/risk/test_win_rate_breaker.py` - 20 unit tests

**Test Coverage:** 20 tests passing

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


class WinRateConfig(BaseModel):
    """Configuration for win rate circuit breaker."""
    threshold_percent: Decimal = Field(
        default=Decimal("40.0"),
        ge=Decimal("10.0"),
        le=Decimal("60.0"),
        description="Win rate threshold below which circuit breaker triggers"
    )
    window_size: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of trades in rolling window"
    )
    minimum_trades: int = Field(
        default=20,
        ge=5,
        le=50,
        description="Minimum trades required before circuit breaker applies"
    )
    enable_caution_flag: bool = Field(
        default=True,
        description="Show caution flag when below minimum trades"
    )

    class Config:
        json_encoders = {Decimal: str}


class TradeRecord(BaseModel):
    """Minimal trade record for win rate calculation."""
    trade_id: str
    closed_at: datetime
    is_win: bool
    pnl_percent: Decimal


class WinRateSnapshot(BaseModel):
    """Point-in-time win rate calculation."""
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    window_size: int
    trades_in_window: int
    winning_trades: int
    losing_trades: int

    @computed_field
    @property
    def win_rate_percent(self) -> Decimal:
        """Win rate as percentage."""
        if self.trades_in_window == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.trades_in_window)) * Decimal("100")

    @computed_field
    @property
    def has_sufficient_history(self) -> bool:
        """Whether enough trades exist for reliable calculation."""
        return self.trades_in_window >= 20  # Will be checked against config

    @computed_field
    @property
    def loss_rate_percent(self) -> Decimal:
        """Loss rate as percentage."""
        return Decimal("100") - self.win_rate_percent


class WinRateCheckResult(BaseModel):
    """Result of win rate circuit breaker check."""
    snapshot: WinRateSnapshot
    threshold_percent: Decimal
    is_breached: bool
    is_caution: bool  # True if below minimum trades
    trigger: Optional["CircuitBreakerTrigger"] = None
    message: str


class WinRateAnalysis(BaseModel):
    """Detailed analysis of recent trades for investigation."""
    snapshot: WinRateSnapshot
    recent_trades: List[TradeRecord]
    losing_streak_current: int
    winning_streak_current: int
    avg_win_pnl_percent: Decimal
    avg_loss_pnl_percent: Decimal
    profit_factor: Decimal  # total_wins / total_losses
    largest_win_percent: Decimal
    largest_loss_percent: Decimal
```

### WinRateCircuitBreaker Service

```python
# src/walltrack/core/risk/win_rate_breaker.py
import structlog
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from collections import deque
from supabase import AsyncClient

from walltrack.core.risk.models import (
    CircuitBreakerType,
    SystemStatus,
    WinRateConfig,
    TradeRecord,
    WinRateSnapshot,
    WinRateCheckResult,
    WinRateAnalysis,
    CircuitBreakerTrigger
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


class WinRateCircuitBreaker:
    """
    Manages win rate-based circuit breaker logic.

    Uses rolling window to calculate win rate and triggers pause
    when it falls below threshold.
    """

    def __init__(self, config: WinRateConfig):
        self.config = config
        self._supabase: Optional[AsyncClient] = None
        self._trade_window: deque[TradeRecord] = deque(maxlen=config.window_size)

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load recent trades from database on startup."""
        db = await self._get_db()

        # Load last N trades
        result = await db.table("trades").select(
            "id, closed_at, pnl_percent"
        ).not_("closed_at", "is", "null").order(
            "closed_at", desc=True
        ).limit(self.config.window_size).execute()

        if result.data:
            # Oldest first for deque
            for row in reversed(result.data):
                record = TradeRecord(
                    trade_id=row["id"],
                    closed_at=datetime.fromisoformat(row["closed_at"]),
                    is_win=Decimal(str(row["pnl_percent"])) > Decimal("0"),
                    pnl_percent=Decimal(str(row["pnl_percent"]))
                )
                self._trade_window.append(record)

        logger.info(
            "win_rate_circuit_breaker_initialized",
            trades_loaded=len(self._trade_window),
            window_size=self.config.window_size
        )

    def add_trade(self, trade: TradeRecord) -> None:
        """Add a completed trade to the rolling window."""
        self._trade_window.append(trade)

    def calculate_snapshot(self) -> WinRateSnapshot:
        """Calculate current win rate snapshot."""
        trades = list(self._trade_window)
        winning = sum(1 for t in trades if t.is_win)
        losing = len(trades) - winning

        return WinRateSnapshot(
            window_size=self.config.window_size,
            trades_in_window=len(trades),
            winning_trades=winning,
            losing_trades=losing
        )

    async def check_win_rate(self) -> WinRateCheckResult:
        """
        Check if win rate is below threshold.

        Returns check result with breach status and optional trigger.
        """
        snapshot = self.calculate_snapshot()

        # Check if we have sufficient history
        has_sufficient = snapshot.trades_in_window >= self.config.minimum_trades
        is_caution = not has_sufficient and self.config.enable_caution_flag

        # Only check threshold if sufficient history
        is_breached = False
        trigger = None

        if has_sufficient:
            is_breached = snapshot.win_rate_percent < self.config.threshold_percent

            if is_breached:
                trigger = await self._create_trigger(snapshot)

        # Build message
        if is_caution:
            message = f"Caution: Only {snapshot.trades_in_window} trades (need {self.config.minimum_trades} for circuit breaker)"
        elif is_breached:
            message = f"Win rate {snapshot.win_rate_percent:.1f}% below threshold {self.config.threshold_percent}%"
        else:
            message = f"Win rate {snapshot.win_rate_percent:.1f}% (threshold: {self.config.threshold_percent}%)"

        return WinRateCheckResult(
            snapshot=snapshot,
            threshold_percent=self.config.threshold_percent,
            is_breached=is_breached,
            is_caution=is_caution,
            trigger=trigger,
            message=message
        )

    async def _create_trigger(self, snapshot: WinRateSnapshot) -> CircuitBreakerTrigger:
        """Create and persist circuit breaker trigger record."""
        db = await self._get_db()

        trigger = CircuitBreakerTrigger(
            breaker_type=CircuitBreakerType.WIN_RATE,
            threshold_value=self.config.threshold_percent,
            actual_value=snapshot.win_rate_percent,
            capital_at_trigger=Decimal("0"),  # Not applicable
            peak_capital_at_trigger=Decimal("0")
        )

        result = await db.table("circuit_breaker_triggers").insert(
            trigger.model_dump(exclude={"id", "is_active"}, mode="json")
        ).execute()

        trigger.id = result.data[0]["id"]

        # Update system status
        await db.table("system_config").upsert({
            "key": "system_status",
            "value": SystemStatus.PAUSED_WIN_RATE.value,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        logger.warning(
            "win_rate_circuit_breaker_triggered",
            win_rate=str(snapshot.win_rate_percent),
            threshold=str(self.config.threshold_percent),
            trades_in_window=snapshot.trades_in_window
        )

        return trigger

    async def analyze_recent_trades(self) -> WinRateAnalysis:
        """
        Provide detailed analysis of recent trades.

        Useful for investigating why win rate dropped.
        """
        snapshot = self.calculate_snapshot()
        trades = list(self._trade_window)

        if not trades:
            return WinRateAnalysis(
                snapshot=snapshot,
                recent_trades=[],
                losing_streak_current=0,
                winning_streak_current=0,
                avg_win_pnl_percent=Decimal("0"),
                avg_loss_pnl_percent=Decimal("0"),
                profit_factor=Decimal("0"),
                largest_win_percent=Decimal("0"),
                largest_loss_percent=Decimal("0")
            )

        # Calculate streaks (from most recent)
        losing_streak = 0
        winning_streak = 0
        for trade in reversed(trades):
            if trade.is_win:
                if losing_streak == 0:
                    winning_streak += 1
                else:
                    break
            else:
                if winning_streak == 0:
                    losing_streak += 1
                else:
                    break

        # Calculate averages
        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        avg_win = sum(t.pnl_percent for t in wins) / len(wins) if wins else Decimal("0")
        avg_loss = sum(t.pnl_percent for t in losses) / len(losses) if losses else Decimal("0")

        # Profit factor
        total_wins = sum(t.pnl_percent for t in wins)
        total_losses = abs(sum(t.pnl_percent for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else Decimal("999")

        return WinRateAnalysis(
            snapshot=snapshot,
            recent_trades=trades[-20:],  # Last 20 for display
            losing_streak_current=losing_streak,
            winning_streak_current=winning_streak,
            avg_win_pnl_percent=avg_win,
            avg_loss_pnl_percent=avg_loss,
            profit_factor=profit_factor,
            largest_win_percent=max((t.pnl_percent for t in wins), default=Decimal("0")),
            largest_loss_percent=min((t.pnl_percent for t in losses), default=Decimal("0"))
        )

    async def reset(self, operator_id: str, clear_history: bool = False) -> None:
        """
        Reset circuit breaker (requires manual action).

        Args:
            operator_id: ID of operator performing reset
            clear_history: If True, clears the trade window
        """
        db = await self._get_db()

        # Mark active trigger as reset
        await db.table("circuit_breaker_triggers").update({
            "reset_at": datetime.utcnow().isoformat(),
            "reset_by": operator_id
        }).eq("breaker_type", CircuitBreakerType.WIN_RATE.value).is_(
            "reset_at", "null"
        ).execute()

        if clear_history:
            self._trade_window.clear()

        # Update system status
        await db.table("system_config").upsert({
            "key": "system_status",
            "value": SystemStatus.RUNNING.value,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        logger.info(
            "win_rate_circuit_breaker_reset",
            operator_id=operator_id,
            history_cleared=clear_history
        )

    async def record_trade_snapshot(self) -> None:
        """Record current win rate to history for tracking."""
        db = await self._get_db()
        snapshot = self.calculate_snapshot()

        await db.table("win_rate_snapshots").insert({
            "timestamp": datetime.utcnow().isoformat(),
            "window_size": snapshot.window_size,
            "trades_in_window": snapshot.trades_in_window,
            "winning_trades": snapshot.winning_trades,
            "win_rate_percent": str(snapshot.win_rate_percent)
        }).execute()


# Singleton instance
_win_rate_breaker: Optional[WinRateCircuitBreaker] = None


async def get_win_rate_circuit_breaker(
    config: Optional[WinRateConfig] = None
) -> WinRateCircuitBreaker:
    """Get or create win rate circuit breaker singleton."""
    global _win_rate_breaker

    if _win_rate_breaker is None:
        if config is None:
            db = await get_supabase_client()
            result = await db.table("system_config").select("value").eq(
                "key", "win_rate_config"
            ).single().execute()
            config = WinRateConfig(**result.data["value"])

        _win_rate_breaker = WinRateCircuitBreaker(config)
        await _win_rate_breaker.initialize()

    return _win_rate_breaker
```

### Database Schema (Supabase)

```sql
-- Win rate snapshots for historical tracking
CREATE TABLE win_rate_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_size INTEGER NOT NULL,
    trades_in_window INTEGER NOT NULL,
    winning_trades INTEGER NOT NULL,
    win_rate_percent DECIMAL(6, 2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_win_rate_snapshots_timestamp ON win_rate_snapshots(timestamp DESC);

-- Insert default win rate config
INSERT INTO system_config (key, value) VALUES
('win_rate_config', '{
    "threshold_percent": "40.0",
    "window_size": 50,
    "minimum_trades": 20,
    "enable_caution_flag": true
}')
ON CONFLICT (key) DO NOTHING;
```

### FastAPI Routes

```python
# src/walltrack/api/routes/risk.py (additions)
from walltrack.core.risk.win_rate_breaker import (
    get_win_rate_circuit_breaker,
    WinRateCircuitBreaker
)
from walltrack.core.risk.models import (
    WinRateConfig,
    WinRateSnapshot,
    WinRateCheckResult,
    WinRateAnalysis,
    TradeRecord
)


class WinRateResetRequest(BaseModel):
    operator_id: str
    clear_history: bool = False


@router.get("/win-rate/snapshot", response_model=WinRateSnapshot)
async def get_win_rate_snapshot(
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker)
):
    """Get current win rate snapshot."""
    return breaker.calculate_snapshot()


@router.get("/win-rate/check", response_model=WinRateCheckResult)
async def check_win_rate(
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker)
):
    """Check win rate and trigger circuit breaker if needed."""
    return await breaker.check_win_rate()


@router.get("/win-rate/analysis", response_model=WinRateAnalysis)
async def analyze_win_rate(
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker)
):
    """Get detailed analysis of recent trades."""
    return await breaker.analyze_recent_trades()


@router.post("/win-rate/add-trade")
async def add_trade_to_window(
    trade: TradeRecord,
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker)
):
    """Add a completed trade to the rolling window."""
    breaker.add_trade(trade)
    return {"status": "added", "trades_in_window": len(breaker._trade_window)}


@router.post("/win-rate/reset")
async def reset_win_rate_breaker(
    request: WinRateResetRequest,
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker)
):
    """Reset win rate circuit breaker (manual action required)."""
    await breaker.reset(request.operator_id, request.clear_history)
    return {"status": "reset", "operator_id": request.operator_id}


@router.put("/win-rate/config")
async def update_win_rate_config(
    config: WinRateConfig,
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker)
):
    """Update win rate configuration."""
    db = await breaker._get_db()

    await db.table("system_config").upsert({
        "key": "win_rate_config",
        "value": config.model_dump(mode="json")
    }).execute()

    # Update breaker config and resize window if needed
    old_window_size = breaker.config.window_size
    breaker.config = config

    if config.window_size != old_window_size:
        # Resize the deque
        old_trades = list(breaker._trade_window)
        breaker._trade_window = deque(maxlen=config.window_size)
        for trade in old_trades[-config.window_size:]:
            breaker._trade_window.append(trade)

    return {"status": "updated", "config": config}
```

### Unit Tests

```python
# tests/unit/risk/test_win_rate_breaker.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from walltrack.core.risk.models import (
    CircuitBreakerType,
    WinRateConfig,
    TradeRecord,
    WinRateSnapshot
)
from walltrack.core.risk.win_rate_breaker import WinRateCircuitBreaker


@pytest.fixture
def win_rate_config():
    return WinRateConfig(
        threshold_percent=Decimal("40.0"),
        window_size=50,
        minimum_trades=20,
        enable_caution_flag=True
    )


@pytest.fixture
def breaker(win_rate_config):
    return WinRateCircuitBreaker(win_rate_config)


def make_trade(trade_id: str, is_win: bool, pnl: Decimal) -> TradeRecord:
    """Helper to create trade records."""
    return TradeRecord(
        trade_id=trade_id,
        closed_at=datetime.utcnow(),
        is_win=is_win,
        pnl_percent=pnl
    )


class TestWinRateCalculation:
    """Test win rate calculation logic."""

    def test_empty_window_zero_rate(self, breaker):
        """Empty window returns zero win rate."""
        snapshot = breaker.calculate_snapshot()

        assert snapshot.trades_in_window == 0
        assert snapshot.win_rate_percent == Decimal("0")

    def test_all_wins_100_percent(self, breaker):
        """All winning trades gives 100% win rate."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        snapshot = breaker.calculate_snapshot()

        assert snapshot.win_rate_percent == Decimal("100")
        assert snapshot.winning_trades == 10

    def test_mixed_results_correct_rate(self, breaker):
        """Mixed results calculate correct win rate."""
        # 6 wins, 4 losses = 60% win rate
        for i in range(6):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(4):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        snapshot = breaker.calculate_snapshot()

        assert snapshot.trades_in_window == 10
        assert snapshot.winning_trades == 6
        assert snapshot.win_rate_percent == Decimal("60")

    def test_window_size_respected(self, breaker):
        """Window size limits number of trades."""
        # Add more than window size
        for i in range(60):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        assert len(breaker._trade_window) == 50


class TestInsufficientHistory:
    """Test handling of insufficient trade history."""

    @pytest.mark.asyncio
    async def test_caution_flag_below_minimum(self, breaker):
        """Caution flag when below minimum trades."""
        # Add 10 trades (below minimum of 20)
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        result = await breaker.check_win_rate()

        assert result.is_caution is True
        assert result.is_breached is False
        assert "Caution" in result.message

    @pytest.mark.asyncio
    async def test_no_trigger_below_minimum(self, breaker):
        """No circuit breaker trigger below minimum trades."""
        # Add losing trades below minimum
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", False, Decimal("-10")))

        result = await breaker.check_win_rate()

        # Even with 0% win rate, no trigger
        assert result.is_breached is False
        assert result.trigger is None


class TestCircuitBreakerTrigger:
    """Test circuit breaker trigger logic."""

    @pytest.mark.asyncio
    async def test_no_trigger_above_threshold(self, breaker):
        """No trigger when win rate above threshold."""
        # 50% win rate (above 40% threshold)
        for i in range(15):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(15):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        with patch.object(breaker, '_get_db', new_callable=AsyncMock):
            result = await breaker.check_win_rate()

            assert result.is_breached is False
            assert result.trigger is None

    @pytest.mark.asyncio
    async def test_trigger_below_threshold(self, breaker):
        """Trigger when win rate below threshold."""
        # 30% win rate (below 40% threshold)
        for i in range(6):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(14):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "trigger-123"}
        ]
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            result = await breaker.check_win_rate()

            assert result.is_breached is True
            assert result.trigger is not None
            assert result.trigger.breaker_type == CircuitBreakerType.WIN_RATE


class TestTradeAnalysis:
    """Test trade analysis functionality."""

    @pytest.mark.asyncio
    async def test_analysis_calculates_streaks(self, breaker):
        """Analysis calculates current streaks correctly."""
        # Add trades: WWWLLL (current losing streak of 3)
        for i in range(3):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(3):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.losing_streak_current == 3
        assert analysis.winning_streak_current == 0

    @pytest.mark.asyncio
    async def test_analysis_profit_factor(self, breaker):
        """Analysis calculates profit factor correctly."""
        # +60 from wins, -30 from losses = profit factor 2.0
        for i in range(3):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(3):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.profit_factor == Decimal("2")


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_trigger(self, breaker):
        """Reset marks trigger as reset in database."""
        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            await breaker.reset("operator-1")

            mock_db.table.assert_any_call("circuit_breaker_triggers")

    @pytest.mark.asyncio
    async def test_reset_with_clear_history(self, breaker):
        """Reset can clear trade history."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(breaker, '_get_db', return_value=mock_db):
            await breaker.reset("operator-1", clear_history=True)

            assert len(breaker._trade_window) == 0
```
