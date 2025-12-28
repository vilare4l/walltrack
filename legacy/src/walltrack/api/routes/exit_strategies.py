"""API routes for exit strategy management."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.data.supabase.repositories.exit_strategy_repo import ExitStrategyRepository
from walltrack.models.exit_strategy import (
    ExitStrategy,
    MoonbagConfig,
    StrategyPreset,
    TakeProfitLevel,
    TimeRulesConfig,
    TrailingStopConfig,
)

router = APIRouter(prefix="/exit-strategies", tags=["exit-strategies"])


class TakeProfitInput(BaseModel):
    """Take profit level input."""

    trigger_multiplier: float
    sell_percentage: float


class TrailingStopInput(BaseModel):
    """Trailing stop input."""

    enabled: bool = False
    activation_multiplier: float = 2.0
    distance_percentage: float = 30.0


class TimeRulesInput(BaseModel):
    """Time rules input."""

    max_hold_hours: int | None = None
    stagnation_exit_enabled: bool = False
    stagnation_threshold_pct: float = 5.0
    stagnation_hours: int = 24


class MoonbagInput(BaseModel):
    """Moonbag input."""

    percentage: float = 0.0
    stop_loss: float | None = None


class CreateStrategyRequest(BaseModel):
    """Request to create exit strategy."""

    name: str
    description: str | None = None
    take_profit_levels: list[TakeProfitInput]
    stop_loss: float = 0.5
    trailing_stop: TrailingStopInput | None = None
    time_rules: TimeRulesInput | None = None
    moonbag: MoonbagInput | None = None


class AssignTierRequest(BaseModel):
    """Request to assign strategy to tier."""

    strategy_id: str
    tier: str


async def get_repo(client: SupabaseClient = Depends(get_supabase_client)) -> ExitStrategyRepository:
    """Get exit strategy repository."""
    return ExitStrategyRepository(client)


@router.get("/", response_model=list[ExitStrategy])
async def list_strategies(
    include_defaults: bool = True,
    repo: ExitStrategyRepository = Depends(get_repo),
) -> list[ExitStrategy]:
    """List all exit strategies."""
    return await repo.list_all(include_defaults)


@router.get("/presets", response_model=list[ExitStrategy])
async def list_presets(
    repo: ExitStrategyRepository = Depends(get_repo),
) -> list[ExitStrategy]:
    """List only preset (default) strategies."""
    return await repo.list_presets()


@router.get("/{strategy_id}", response_model=ExitStrategy)
async def get_strategy(
    strategy_id: str,
    repo: ExitStrategyRepository = Depends(get_repo),
) -> ExitStrategy:
    """Get strategy by ID."""
    strategy = await repo.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )
    return strategy


@router.post("/", response_model=ExitStrategy, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    request: CreateStrategyRequest,
    repo: ExitStrategyRepository = Depends(get_repo),
) -> ExitStrategy:
    """Create custom exit strategy."""
    existing = await repo.get_by_name(request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Strategy '{request.name}' already exists",
        )

    trailing = request.trailing_stop.model_dump() if request.trailing_stop else {}
    time_rules = request.time_rules.model_dump() if request.time_rules else {}
    moonbag = request.moonbag.model_dump() if request.moonbag else {}

    strategy = ExitStrategy(
        name=request.name,
        description=request.description,
        preset=StrategyPreset.CUSTOM,
        is_default=False,
        take_profit_levels=[
            TakeProfitLevel(**tp.model_dump()) for tp in request.take_profit_levels
        ],
        stop_loss=request.stop_loss,
        trailing_stop=TrailingStopConfig(**trailing),
        time_rules=TimeRulesConfig(**time_rules),
        moonbag=MoonbagConfig(**moonbag),
    )

    return await repo.create(strategy)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: str,
    repo: ExitStrategyRepository = Depends(get_repo),
) -> None:
    """Delete custom exit strategy."""
    success = await repo.delete(strategy_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default preset strategies",
        )


@router.post("/assign-tier")
async def assign_to_tier(
    request: AssignTierRequest,
    repo: ExitStrategyRepository = Depends(get_repo),
) -> dict:
    """Assign exit strategy to conviction tier."""
    if request.tier not in ["high", "standard"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier must be 'high' or 'standard'",
        )

    strategy = await repo.get_by_id(request.strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found",
        )

    assignment = await repo.assign_to_tier(request.strategy_id, request.tier)

    return {
        "assignment_id": assignment.id,
        "strategy_id": assignment.strategy_id,
        "strategy_name": strategy.name,
        "tier": request.tier,
    }


@router.get("/tier/{tier}", response_model=ExitStrategy | None)
async def get_tier_strategy(
    tier: str,
    repo: ExitStrategyRepository = Depends(get_repo),
) -> ExitStrategy | None:
    """Get exit strategy assigned to conviction tier."""
    if tier not in ["high", "standard"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier must be 'high' or 'standard'",
        )

    return await repo.get_assignment_for_tier(tier)
