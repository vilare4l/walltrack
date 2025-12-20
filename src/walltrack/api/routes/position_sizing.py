"""API routes for position sizing configuration and calculation."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from walltrack.models.position_sizing import (
    ConvictionTier,
    PositionSizeRequest,
    PositionSizingConfig,
    SizingDecision,
)
from walltrack.services.trade.position_sizer import PositionSizer, get_position_sizer

router = APIRouter(prefix="/position-sizing", tags=["position-sizing"])


class CalculateSizeRequest(BaseModel):
    """API request to calculate position size."""

    signal_score: float = Field(..., ge=0.0, le=1.0)
    available_balance_sol: float = Field(..., ge=0)
    current_position_count: int = Field(default=0, ge=0)
    current_allocated_sol: float = Field(default=0, ge=0)


class CalculateSizeResponse(BaseModel):
    """API response for position size calculation."""

    should_trade: bool
    decision: SizingDecision
    conviction_tier: ConvictionTier
    final_size_sol: float
    multiplier: float
    reason: str | None


class ConfigUpdateRequest(BaseModel):
    """Request to update position sizing config."""

    base_position_pct: float | None = None
    min_position_sol: float | None = None
    max_position_sol: float | None = None
    high_conviction_multiplier: float | None = None
    standard_conviction_multiplier: float | None = None
    high_conviction_threshold: float | None = None
    min_conviction_threshold: float | None = None
    max_concurrent_positions: int | None = None
    max_capital_allocation_pct: float | None = None
    reserve_sol: float | None = None


@router.get("/config", response_model=PositionSizingConfig)
async def get_config(
    sizer: PositionSizer = Depends(get_position_sizer),
) -> PositionSizingConfig:
    """Get current position sizing configuration."""
    return await sizer.get_config()


@router.put("/config", response_model=PositionSizingConfig)
async def update_config(
    request: ConfigUpdateRequest,
    sizer: PositionSizer = Depends(get_position_sizer),
) -> PositionSizingConfig:
    """Update position sizing configuration."""
    current = await sizer.get_config()
    update_data = request.model_dump(exclude_unset=True)
    updated_config = current.model_copy(update=update_data)
    return await sizer.update_config(updated_config)


@router.post("/calculate", response_model=CalculateSizeResponse)
async def calculate_position_size(
    request: CalculateSizeRequest,
    sizer: PositionSizer = Depends(get_position_sizer),
) -> CalculateSizeResponse:
    """Calculate position size for given parameters."""
    size_request = PositionSizeRequest(
        signal_score=request.signal_score,
        available_balance_sol=request.available_balance_sol,
        current_position_count=request.current_position_count,
        current_allocated_sol=request.current_allocated_sol,
    )
    result = await sizer.calculate_size(size_request, audit=False)
    return CalculateSizeResponse(
        should_trade=result.should_trade,
        decision=result.decision,
        conviction_tier=result.conviction_tier,
        final_size_sol=result.final_size_sol,
        multiplier=result.multiplier,
        reason=result.reason,
    )


@router.get("/preview")
async def preview_sizes(
    available_balance_sol: float,
    current_position_count: int = 0,
    current_allocated_sol: float = 0,
    sizer: PositionSizer = Depends(get_position_sizer),
) -> dict:
    """Preview position sizes for different score levels."""
    config = await sizer.get_config()
    previews = []
    for score in [0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        request = PositionSizeRequest(
            signal_score=score,
            available_balance_sol=available_balance_sol,
            current_position_count=current_position_count,
            current_allocated_sol=current_allocated_sol,
        )
        result = await sizer.calculate_size(request, audit=False)
        previews.append({
            "score": score,
            "tier": result.conviction_tier.value,
            "multiplier": result.multiplier,
            "size_sol": round(result.final_size_sol, 4),
            "decision": result.decision.value,
        })
    return {"config": config.model_dump(), "previews": previews}
