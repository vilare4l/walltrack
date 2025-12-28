"""System API routes for pause/resume controls."""

from fastapi import APIRouter, Depends, HTTPException

from walltrack.core.risk.system_state import (
    SystemStateManager,
    get_system_state_manager,
)
from walltrack.models.risk import (
    PauseRequest,
    ResumeRequest,
    SystemState,
    SystemStateResponse,
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/state", response_model=SystemStateResponse)
async def get_system_state(
    manager: SystemStateManager = Depends(get_system_state_manager),
) -> SystemStateResponse:
    """Get current system state."""
    return await manager.get_state()


@router.get("/can-trade")
async def can_trade(
    manager: SystemStateManager = Depends(get_system_state_manager),
) -> dict[str, bool]:
    """Check if trading is allowed."""
    return {"can_trade": manager.can_trade()}


@router.post("/pause", response_model=SystemState)
async def pause_system(
    request: PauseRequest,
    manager: SystemStateManager = Depends(get_system_state_manager),
) -> SystemState:
    """Pause the trading system."""
    return await manager.pause(request)


@router.post("/resume", response_model=SystemState)
async def resume_system(
    request: ResumeRequest,
    manager: SystemStateManager = Depends(get_system_state_manager),
) -> SystemState:
    """Resume the trading system."""
    try:
        return await manager.resume(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
