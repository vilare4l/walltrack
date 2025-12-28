"""Risk management API routes."""

from collections import deque
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from walltrack.core.risk.circuit_breaker import (
    DrawdownCircuitBreaker,
    get_drawdown_circuit_breaker,
)
from walltrack.core.risk.consecutive_loss import (
    ConsecutiveLossManager,
    get_consecutive_loss_manager,
)
from walltrack.core.risk.position_limits import (
    PositionLimitManager,
    get_position_limit_manager,
)
from walltrack.core.risk.win_rate_breaker import (
    WinRateCircuitBreaker,
    get_win_rate_circuit_breaker,
)
from walltrack.models.risk import (
    BlockedTradeResponse,
    CircuitBreakerTrigger,
    ConsecutiveLossConfig,
    ConsecutiveLossState,
    DrawdownCheckResult,
    DrawdownConfig,
    PositionLimitCheckResult,
    PositionLimitConfig,
    QueuedSignal,
    SizeAdjustmentResult,
    TradeRecord,
    TradeResult,
    WinRateAnalysis,
    WinRateCheckResult,
    WinRateConfig,
    WinRateSnapshot,
)

router = APIRouter(prefix="/risk", tags=["risk"])


class DrawdownStatusResponse(BaseModel):
    """Response for drawdown status endpoint."""

    current_capital: Decimal
    peak_capital: Decimal
    drawdown_percent: Decimal
    threshold_percent: Decimal
    is_breached: bool
    active_trigger: CircuitBreakerTrigger | None = None


class ResetRequest(BaseModel):
    """Request to reset circuit breaker."""

    operator_id: str
    reset_peak: bool = False
    new_peak: Decimal | None = None


class CheckDrawdownRequest(BaseModel):
    """Request to check drawdown."""

    current_capital: Decimal


@router.get("/drawdown/status", response_model=DrawdownStatusResponse)
async def get_drawdown_status(
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker),
) -> DrawdownStatusResponse:
    """Get current drawdown status."""
    # Get active trigger if any
    db = await breaker._get_db()
    try:
        trigger_result = (
            await db.table("circuit_breaker_triggers")
            .select("*")
            .eq("breaker_type", "drawdown")
            .is_("reset_at", "null")
            .limit(1)
            .execute()
        )

        active_trigger = None
        if trigger_result.data:
            active_trigger = CircuitBreakerTrigger(**trigger_result.data[0])
    except Exception:
        active_trigger = None

    return DrawdownStatusResponse(
        current_capital=breaker._current_capital,
        peak_capital=breaker._peak_capital,
        drawdown_percent=breaker.current_drawdown_percent,
        threshold_percent=breaker.config.threshold_percent,
        is_breached=active_trigger is not None,
        active_trigger=active_trigger,
    )


@router.post("/drawdown/check", response_model=DrawdownCheckResult)
async def check_drawdown(
    request: CheckDrawdownRequest,
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker),
) -> DrawdownCheckResult:
    """Check drawdown and trigger circuit breaker if needed."""
    return await breaker.check_drawdown(request.current_capital)


@router.post("/drawdown/reset")
async def reset_drawdown_breaker(
    request: ResetRequest,
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker),
) -> dict:
    """Reset drawdown circuit breaker (manual action required)."""
    new_peak = request.new_peak if request.reset_peak else None
    await breaker.reset(request.operator_id, new_peak)
    return {"status": "reset", "operator_id": request.operator_id}


@router.put("/drawdown/config")
async def update_drawdown_config(
    config: DrawdownConfig,
    breaker: DrawdownCircuitBreaker = Depends(get_drawdown_circuit_breaker),
) -> dict:
    """Update drawdown threshold configuration."""
    db = await breaker._get_db()

    await db.table("system_config").upsert(
        {"key": "drawdown_config", "value": config.model_dump(mode="json")}
    ).execute()

    breaker.config = config
    return {"status": "updated", "config": config.model_dump()}


# Story 5-2: Consecutive Loss Position Reduction Routes


class SizeCalculationRequest(BaseModel):
    """Request to calculate adjusted size."""

    base_size: Decimal


class ConsecutiveLossResetRequest(BaseModel):
    """Request to reset consecutive loss counter."""

    operator_id: str


@router.get("/consecutive-loss/state", response_model=ConsecutiveLossState)
async def get_consecutive_loss_state(
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager),
) -> ConsecutiveLossState:
    """Get current consecutive loss state."""
    return manager.state


@router.post("/consecutive-loss/record", response_model=ConsecutiveLossState)
async def record_trade_outcome(
    result: TradeResult,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager),
) -> ConsecutiveLossState:
    """Record a trade outcome and update loss streak."""
    return await manager.record_trade_outcome(result)


@router.post("/consecutive-loss/calculate-size", response_model=SizeAdjustmentResult)
async def calculate_adjusted_size(
    request: SizeCalculationRequest,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager),
) -> SizeAdjustmentResult:
    """Calculate adjusted position size based on current streak."""
    return manager.calculate_adjusted_size(request.base_size)


@router.post("/consecutive-loss/reset")
async def reset_consecutive_loss(
    request: ConsecutiveLossResetRequest,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager),
) -> dict:
    """Manually reset consecutive loss counter."""
    state = await manager.manual_reset(request.operator_id)
    return {"status": "reset", "state": state.model_dump()}


@router.put("/consecutive-loss/config")
async def update_consecutive_loss_config(
    config: ConsecutiveLossConfig,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager),
) -> dict:
    """Update consecutive loss configuration."""
    db = await manager._get_db()

    await db.table("system_config").upsert(
        {"key": "consecutive_loss_config", "value": config.model_dump(mode="json")}
    ).execute()

    manager.config = config
    return {"status": "updated", "config": config.model_dump()}


# Story 5-3: Win Rate Circuit Breaker Routes


class WinRateResetRequest(BaseModel):
    """Request to reset win rate circuit breaker."""

    operator_id: str
    clear_history: bool = False


@router.get("/win-rate/snapshot", response_model=WinRateSnapshot)
async def get_win_rate_snapshot(
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker),
) -> WinRateSnapshot:
    """Get current win rate snapshot."""
    return breaker.calculate_snapshot()


@router.get("/win-rate/check", response_model=WinRateCheckResult)
async def check_win_rate(
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker),
) -> WinRateCheckResult:
    """Check win rate and trigger circuit breaker if needed."""
    return await breaker.check_win_rate()


@router.get("/win-rate/analysis", response_model=WinRateAnalysis)
async def analyze_win_rate(
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker),
) -> WinRateAnalysis:
    """Get detailed analysis of recent trades."""
    return await breaker.analyze_recent_trades()


@router.post("/win-rate/add-trade")
async def add_trade_to_window(
    trade: TradeRecord,
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker),
) -> dict:
    """Add a completed trade to the rolling window."""
    breaker.add_trade(trade)
    return {"status": "added", "trades_in_window": len(breaker._trade_window)}


@router.post("/win-rate/reset")
async def reset_win_rate_breaker(
    request: WinRateResetRequest,
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker),
) -> dict:
    """Reset win rate circuit breaker (manual action required)."""
    await breaker.reset(request.operator_id, request.clear_history)
    return {"status": "reset", "operator_id": request.operator_id}


@router.put("/win-rate/config")
async def update_win_rate_config(
    config: WinRateConfig,
    breaker: WinRateCircuitBreaker = Depends(get_win_rate_circuit_breaker),
) -> dict:
    """Update win rate configuration."""
    db = await breaker._get_db()

    await db.table("system_config").upsert(
        {"key": "win_rate_config", "value": config.model_dump(mode="json")}
    ).execute()

    # Update breaker config and resize window if needed
    old_window_size = breaker.config.window_size
    breaker.config = config

    if config.window_size != old_window_size:
        # Resize the deque
        old_trades = list(breaker._trade_window)
        breaker._trade_window = deque(maxlen=config.window_size)
        for trade in old_trades[-config.window_size :]:
            breaker._trade_window.append(trade)

    return {"status": "updated", "config": config.model_dump()}


# Story 5-4: Max Concurrent Position Limits Routes


class PositionRequestPayload(BaseModel):
    """Request to open a position."""

    signal_id: str
    signal_data: dict


class CancelQueuedRequest(BaseModel):
    """Request to cancel a queued signal."""

    signal_id: str


@router.get("/position-limit/status", response_model=PositionLimitCheckResult)
async def get_position_limit_status(
    manager: PositionLimitManager = Depends(get_position_limit_manager),
) -> PositionLimitCheckResult:
    """Get current position limit status."""
    return await manager.check_can_open()


@router.post("/position-limit/request")
async def request_position(
    request: PositionRequestPayload,
    manager: PositionLimitManager = Depends(get_position_limit_manager),
) -> bool | BlockedTradeResponse:
    """Request to open a new position."""
    return await manager.request_position(request.signal_id, request.signal_data)


@router.get("/position-limit/queue", response_model=list[QueuedSignal])
async def get_signal_queue(
    manager: PositionLimitManager = Depends(get_position_limit_manager),
) -> list[QueuedSignal]:
    """Get current signal queue status."""
    return await manager.get_queue_status()


@router.post("/position-limit/cancel")
async def cancel_queued_signal(
    request: CancelQueuedRequest,
    manager: PositionLimitManager = Depends(get_position_limit_manager),
) -> dict:
    """Cancel a queued signal."""
    success = await manager.cancel_queued_signal(request.signal_id)
    return {"success": success, "signal_id": request.signal_id}


@router.post("/position-limit/on-close/{position_id}")
async def notify_position_closed(
    position_id: str,
    manager: PositionLimitManager = Depends(get_position_limit_manager),
) -> dict:
    """Notify that a position was closed (triggers queue execution)."""
    executed = await manager.on_position_closed(position_id)
    return {
        "position_id": position_id,
        "executed_signal": executed.signal_id if executed else None,
    }


@router.put("/position-limit/config")
async def update_position_limit_config(
    config: PositionLimitConfig,
    manager: PositionLimitManager = Depends(get_position_limit_manager),
) -> dict:
    """Update position limit configuration."""
    await manager.update_config(config)
    return {"status": "updated", "config": config.model_dump()}
