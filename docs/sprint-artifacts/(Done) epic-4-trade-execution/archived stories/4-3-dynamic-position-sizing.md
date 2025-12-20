# Story 4.3: Dynamic Position Sizing

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR20

## User Story

**As an** operator,
**I want** position size to vary based on signal conviction,
**So that** higher-quality signals get larger allocations.

## Acceptance Criteria

### AC 1: Size Calculation
**Given** a trade-eligible signal with score
**When** position size is calculated
**Then** base position size is retrieved from config (e.g., 2% of capital)
**And** multiplier is applied based on score tier:
- Score >= 0.85: 1.5x multiplier
- Score 0.70-0.84: 1.0x multiplier

### AC 2: Validation
**Given** calculated position size
**When** validation is performed
**Then** size does not exceed max position limit (configurable)
**And** size does not exceed available balance
**And** size respects concurrent position limits (FR33)

### AC 3: Insufficient Balance
**Given** insufficient balance for calculated size
**When** trade is attempted
**Then** size is reduced to available amount (if above minimum)
**Or** trade is skipped if below minimum threshold
**And** decision is logged

### AC 4: Config Adjustment
**Given** position sizing config
**When** operator adjusts via dashboard
**Then** new base size and multipliers take effect immediately

## Technical Notes

- FR20: Apply dynamic position sizing based on signal score
- Implement in `src/walltrack/core/execution/position_manager.py`
- Config stored in Supabase, editable via dashboard

---

## Technical Specification

### 1. Data Models

```python
# src/walltrack/models/position_sizing.py
from __future__ import annotations
from enum import Enum
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator


class ConvictionTier(str, Enum):
    """Signal conviction tiers with associated multipliers."""
    HIGH = "high"        # >= 0.85, 1.5x multiplier
    STANDARD = "standard"  # 0.70-0.84, 1.0x multiplier
    NONE = "none"        # < 0.70, no trade


class SizingDecision(str, Enum):
    """Decision made by position sizer."""
    APPROVED = "approved"
    REDUCED = "reduced"           # Reduced due to balance/limits
    SKIPPED_MIN_SIZE = "skipped_min_size"
    SKIPPED_NO_BALANCE = "skipped_no_balance"
    SKIPPED_MAX_POSITIONS = "skipped_max_positions"
    SKIPPED_LOW_SCORE = "skipped_low_score"


class PositionSizingConfig(BaseModel):
    """Configuration for dynamic position sizing.

    Stored in Supabase, editable via dashboard.
    """

    # Base sizing
    base_position_pct: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Base position size as % of capital"
    )
    min_position_sol: float = Field(
        default=0.01,
        ge=0.001,
        description="Minimum position size in SOL"
    )
    max_position_sol: float = Field(
        default=1.0,
        ge=0.01,
        description="Maximum position size in SOL"
    )

    # Conviction multipliers
    high_conviction_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=3.0,
        description="Multiplier for high conviction signals (>=0.85)"
    )
    standard_conviction_multiplier: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Multiplier for standard conviction signals (0.70-0.84)"
    )

    # Thresholds
    high_conviction_threshold: float = Field(
        default=0.85,
        ge=0.5,
        le=1.0,
        description="Score threshold for high conviction"
    )
    min_conviction_threshold: float = Field(
        default=0.70,
        ge=0.3,
        le=0.9,
        description="Minimum score to trade"
    )

    # Limits
    max_concurrent_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum open positions at once"
    )
    max_capital_allocation_pct: float = Field(
        default=50.0,
        ge=10.0,
        le=100.0,
        description="Maximum % of capital allocated across all positions"
    )

    # Safety
    reserve_sol: float = Field(
        default=0.05,
        ge=0.01,
        description="SOL to keep in reserve for fees"
    )

    # Metadata
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str | None = Field(None)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "PositionSizingConfig":
        """Ensure threshold ordering is valid."""
        if self.high_conviction_threshold <= self.min_conviction_threshold:
            raise ValueError(
                "high_conviction_threshold must be > min_conviction_threshold"
            )
        return self

    @model_validator(mode="after")
    def validate_position_limits(self) -> "PositionSizingConfig":
        """Ensure position limits are valid."""
        if self.max_position_sol < self.min_position_sol:
            raise ValueError(
                "max_position_sol must be >= min_position_sol"
            )
        return self


class PositionSizeRequest(BaseModel):
    """Request to calculate position size."""

    signal_score: float = Field(..., ge=0.0, le=1.0, description="Signal composite score")
    available_balance_sol: float = Field(..., ge=0, description="Available SOL balance")
    current_position_count: int = Field(default=0, ge=0, description="Current open positions")
    current_allocated_sol: float = Field(default=0, ge=0, description="SOL already in positions")
    token_address: str | None = Field(None, description="Token for logging")
    signal_id: str | None = Field(None, description="Signal ID for tracking")


class PositionSizeResult(BaseModel):
    """Result of position size calculation."""

    decision: SizingDecision
    conviction_tier: ConvictionTier
    base_size_sol: float = Field(..., ge=0)
    multiplier: float = Field(..., ge=0)
    calculated_size_sol: float = Field(..., ge=0)
    final_size_sol: float = Field(..., ge=0)
    reason: str | None = Field(None)

    # Calculation breakdown
    capital_used_for_base: float = Field(..., ge=0)
    reduction_applied: bool = Field(default=False)
    reduction_reason: str | None = Field(None)

    @property
    def should_trade(self) -> bool:
        """Check if trade should proceed."""
        return self.decision == SizingDecision.APPROVED or self.decision == SizingDecision.REDUCED


class PositionSizeAudit(BaseModel):
    """Audit entry for position sizing decisions."""

    id: str | None = Field(None)
    signal_id: str | None = Field(None)
    token_address: str | None = Field(None)

    # Input
    signal_score: float
    available_balance_sol: float
    current_position_count: int
    current_allocated_sol: float

    # Config snapshot
    config_snapshot: dict

    # Result
    result: PositionSizeResult

    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Configuration

```python
# src/walltrack/config/position_settings.py
from pydantic import Field
from pydantic_settings import BaseSettings


class PositionSettings(BaseSettings):
    """Position sizing settings from environment."""

    # Default values (can be overridden in DB)
    default_base_position_pct: float = Field(default=2.0)
    default_min_position_sol: float = Field(default=0.01)
    default_max_position_sol: float = Field(default=1.0)
    default_max_concurrent_positions: int = Field(default=5)

    # Cache settings
    config_cache_ttl_seconds: int = Field(default=60)

    model_config = {
        "env_prefix": "POSITION_",
        "env_file": ".env",
        "extra": "ignore"
    }


def get_position_settings() -> PositionSettings:
    """Get position settings singleton."""
    return PositionSettings()
```

### 3. Position Sizing Service

```python
# src/walltrack/services/execution/position_sizer.py
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional

import structlog

from walltrack.models.position_sizing import (
    PositionSizingConfig,
    PositionSizeRequest,
    PositionSizeResult,
    PositionSizeAudit,
    ConvictionTier,
    SizingDecision,
)
from walltrack.config.position_settings import PositionSettings, get_position_settings
from walltrack.repositories.position_config_repository import (
    PositionConfigRepository,
    get_position_config_repository,
)

logger = structlog.get_logger()


class PositionSizer:
    """Calculates dynamic position sizes based on signal conviction.

    Features:
    - Score-based multipliers (1.5x for high conviction, 1.0x standard)
    - Validation against balance and limits
    - Graceful handling of insufficient balance
    - Hot-reload config from database
    """

    def __init__(
        self,
        settings: PositionSettings | None = None,
        config_repo: PositionConfigRepository | None = None,
    ):
        self._settings = settings or get_position_settings()
        self._config_repo = config_repo
        self._config_cache: PositionSizingConfig | None = None
        self._cache_lock = asyncio.Lock()
        self._cache_updated: datetime | None = None

    async def initialize(self) -> None:
        """Initialize with config repository."""
        if self._config_repo is None:
            self._config_repo = await get_position_config_repository()

        # Load initial config
        await self._refresh_config()
        logger.info("position_sizer_initialized")

    async def _refresh_config(self) -> PositionSizingConfig:
        """Refresh config from database with caching."""
        async with self._cache_lock:
            now = datetime.utcnow()

            # Check if cache is still valid
            if (
                self._config_cache is not None
                and self._cache_updated is not None
                and (now - self._cache_updated).total_seconds() < self._settings.config_cache_ttl_seconds
            ):
                return self._config_cache

            # Fetch from database
            try:
                self._config_cache = await self._config_repo.get_config()
                self._cache_updated = now
                logger.debug("position_config_refreshed")
            except Exception as e:
                logger.warning("position_config_refresh_failed", error=str(e))
                # Use defaults if DB fails
                if self._config_cache is None:
                    self._config_cache = PositionSizingConfig()

            return self._config_cache

    async def get_config(self) -> PositionSizingConfig:
        """Get current position sizing config."""
        return await self._refresh_config()

    def _determine_conviction_tier(
        self,
        score: float,
        config: PositionSizingConfig,
    ) -> ConvictionTier:
        """Determine conviction tier from score."""
        if score >= config.high_conviction_threshold:
            return ConvictionTier.HIGH
        elif score >= config.min_conviction_threshold:
            return ConvictionTier.STANDARD
        else:
            return ConvictionTier.NONE

    def _get_multiplier(
        self,
        tier: ConvictionTier,
        config: PositionSizingConfig,
    ) -> float:
        """Get multiplier for conviction tier."""
        if tier == ConvictionTier.HIGH:
            return config.high_conviction_multiplier
        elif tier == ConvictionTier.STANDARD:
            return config.standard_conviction_multiplier
        else:
            return 0.0

    async def calculate_size(
        self,
        request: PositionSizeRequest,
    ) -> PositionSizeResult:
        """Calculate position size for a signal.

        Args:
            request: Position size request with score and balance info

        Returns:
            PositionSizeResult with final size and decision
        """
        config = await self._refresh_config()

        # Step 1: Determine conviction tier
        tier = self._determine_conviction_tier(request.signal_score, config)

        # Skip if score too low
        if tier == ConvictionTier.NONE:
            logger.info(
                "position_skipped_low_score",
                score=request.signal_score,
                threshold=config.min_conviction_threshold,
            )
            return PositionSizeResult(
                decision=SizingDecision.SKIPPED_LOW_SCORE,
                conviction_tier=tier,
                base_size_sol=0,
                multiplier=0,
                calculated_size_sol=0,
                final_size_sol=0,
                capital_used_for_base=0,
                reason=f"Score {request.signal_score:.2f} below threshold {config.min_conviction_threshold}",
            )

        # Step 2: Check concurrent position limit
        if request.current_position_count >= config.max_concurrent_positions:
            logger.info(
                "position_skipped_max_positions",
                current=request.current_position_count,
                max=config.max_concurrent_positions,
            )
            return PositionSizeResult(
                decision=SizingDecision.SKIPPED_MAX_POSITIONS,
                conviction_tier=tier,
                base_size_sol=0,
                multiplier=self._get_multiplier(tier, config),
                calculated_size_sol=0,
                final_size_sol=0,
                capital_used_for_base=0,
                reason=f"Max positions reached ({config.max_concurrent_positions})",
            )

        # Step 3: Calculate base size
        # Available capital = balance - reserve - already allocated
        usable_balance = max(0, request.available_balance_sol - config.reserve_sol)
        available_for_new = max(0, usable_balance - request.current_allocated_sol)

        # Check max capital allocation
        total_capital = request.available_balance_sol + request.current_allocated_sol
        max_allocation = total_capital * (config.max_capital_allocation_pct / 100)
        remaining_allocation = max(0, max_allocation - request.current_allocated_sol)

        # Capital to use for base calculation
        capital_for_base = min(available_for_new, remaining_allocation)

        # Base size as % of capital
        base_size = capital_for_base * (config.base_position_pct / 100)

        # Step 4: Apply conviction multiplier
        multiplier = self._get_multiplier(tier, config)
        calculated_size = base_size * multiplier

        # Step 5: Apply limits
        final_size = calculated_size
        reduction_applied = False
        reduction_reason = None

        # Max position limit
        if final_size > config.max_position_sol:
            final_size = config.max_position_sol
            reduction_applied = True
            reduction_reason = f"Capped at max_position_sol ({config.max_position_sol})"

        # Available balance limit
        if final_size > available_for_new:
            final_size = available_for_new
            reduction_applied = True
            reduction_reason = f"Limited by available balance ({available_for_new:.4f})"

        # Step 6: Check minimum
        if final_size < config.min_position_sol:
            if available_for_new < config.min_position_sol:
                logger.info(
                    "position_skipped_no_balance",
                    final_size=final_size,
                    min_size=config.min_position_sol,
                    available=available_for_new,
                )
                return PositionSizeResult(
                    decision=SizingDecision.SKIPPED_NO_BALANCE,
                    conviction_tier=tier,
                    base_size_sol=base_size,
                    multiplier=multiplier,
                    calculated_size_sol=calculated_size,
                    final_size_sol=0,
                    capital_used_for_base=capital_for_base,
                    reason=f"Insufficient balance ({available_for_new:.4f} SOL)",
                )
            else:
                logger.info(
                    "position_skipped_min_size",
                    final_size=final_size,
                    min_size=config.min_position_sol,
                )
                return PositionSizeResult(
                    decision=SizingDecision.SKIPPED_MIN_SIZE,
                    conviction_tier=tier,
                    base_size_sol=base_size,
                    multiplier=multiplier,
                    calculated_size_sol=calculated_size,
                    final_size_sol=0,
                    capital_used_for_base=capital_for_base,
                    reason=f"Size {final_size:.4f} below minimum {config.min_position_sol}",
                )

        # Step 7: Determine final decision
        decision = SizingDecision.REDUCED if reduction_applied else SizingDecision.APPROVED

        logger.info(
            "position_size_calculated",
            decision=decision.value,
            tier=tier.value,
            score=request.signal_score,
            base_size=round(base_size, 4),
            multiplier=multiplier,
            final_size=round(final_size, 4),
        )

        return PositionSizeResult(
            decision=decision,
            conviction_tier=tier,
            base_size_sol=base_size,
            multiplier=multiplier,
            calculated_size_sol=calculated_size,
            final_size_sol=final_size,
            capital_used_for_base=capital_for_base,
            reduction_applied=reduction_applied,
            reduction_reason=reduction_reason,
        )

    async def update_config(self, config: PositionSizingConfig) -> PositionSizingConfig:
        """Update position sizing configuration.

        Args:
            config: New configuration

        Returns:
            Updated configuration
        """
        config.updated_at = datetime.utcnow()
        updated = await self._config_repo.save_config(config)

        # Invalidate cache
        async with self._cache_lock:
            self._config_cache = updated
            self._cache_updated = datetime.utcnow()

        logger.info(
            "position_config_updated",
            base_pct=config.base_position_pct,
            high_mult=config.high_conviction_multiplier,
        )

        return updated


# Singleton
_position_sizer: PositionSizer | None = None


async def get_position_sizer() -> PositionSizer:
    """Get or create position sizer singleton."""
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()
        await _position_sizer.initialize()
    return _position_sizer
```

### 4. Repository

```python
# src/walltrack/repositories/position_config_repository.py
from __future__ import annotations
from datetime import datetime
from typing import Optional

import structlog
from supabase import AsyncClient

from walltrack.models.position_sizing import PositionSizingConfig, PositionSizeAudit
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger()

# Fixed ID for singleton config row
CONFIG_ID = "00000000-0000-0000-0000-000000000001"


class PositionConfigRepository:
    """Repository for position sizing configuration."""

    def __init__(self, client: AsyncClient):
        self._client = client

    async def get_config(self) -> PositionSizingConfig:
        """Get current position sizing configuration."""
        result = await (
            self._client.table("position_sizing_config")
            .select("*")
            .eq("id", CONFIG_ID)
            .single()
            .execute()
        )

        if result.data:
            return PositionSizingConfig(**result.data)

        # Return defaults if no config exists
        return PositionSizingConfig()

    async def save_config(self, config: PositionSizingConfig) -> PositionSizingConfig:
        """Save position sizing configuration."""
        data = config.model_dump()
        data["id"] = CONFIG_ID
        data["updated_at"] = datetime.utcnow().isoformat()

        result = await (
            self._client.table("position_sizing_config")
            .upsert(data)
            .execute()
        )

        logger.info("position_config_saved")
        return PositionSizingConfig(**result.data[0])

    async def save_audit(self, audit: PositionSizeAudit) -> None:
        """Save position sizing audit entry."""
        data = {
            "signal_id": audit.signal_id,
            "token_address": audit.token_address,
            "signal_score": audit.signal_score,
            "available_balance_sol": audit.available_balance_sol,
            "current_position_count": audit.current_position_count,
            "current_allocated_sol": audit.current_allocated_sol,
            "config_snapshot": audit.config_snapshot,
            "decision": audit.result.decision.value,
            "conviction_tier": audit.result.conviction_tier.value,
            "base_size_sol": audit.result.base_size_sol,
            "multiplier": audit.result.multiplier,
            "final_size_sol": audit.result.final_size_sol,
            "reason": audit.result.reason,
            "created_at": audit.created_at.isoformat(),
        }

        await (
            self._client.table("position_sizing_audit")
            .insert(data)
            .execute()
        )

    async def get_recent_audits(
        self,
        limit: int = 50,
        signal_id: str | None = None,
    ) -> list[dict]:
        """Get recent position sizing audit entries."""
        query = (
            self._client.table("position_sizing_audit")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )

        if signal_id:
            query = query.eq("signal_id", signal_id)

        result = await query.execute()
        return result.data


# Singleton
_repo: PositionConfigRepository | None = None


async def get_position_config_repository() -> PositionConfigRepository:
    """Get or create position config repository singleton."""
    global _repo
    if _repo is None:
        client = await get_supabase_client()
        _repo = PositionConfigRepository(client)
    return _repo
```

### 5. API Routes

```python
# src/walltrack/api/routes/position_sizing.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from walltrack.models.position_sizing import (
    PositionSizingConfig,
    PositionSizeRequest,
    PositionSizeResult,
    SizingDecision,
    ConvictionTier,
)
from walltrack.services.execution.position_sizer import (
    PositionSizer,
    get_position_sizer,
)

router = APIRouter(prefix="/position-sizing", tags=["position-sizing"])


class CalculateSizeRequest(BaseModel):
    """API request to calculate position size."""
    signal_score: float
    available_balance_sol: float
    current_position_count: int = 0
    current_allocated_sol: float = 0


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
    # Get current config
    current = await sizer.get_config()

    # Apply updates
    update_data = request.model_dump(exclude_unset=True)
    updated_config = current.model_copy(update=update_data)

    # Save and return
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

    result = await sizer.calculate_size(size_request)

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
        result = await sizer.calculate_size(request)
        previews.append({
            "score": score,
            "tier": result.conviction_tier.value,
            "multiplier": result.multiplier,
            "size_sol": round(result.final_size_sol, 4),
            "decision": result.decision.value,
        })

    return {
        "config": config.model_dump(),
        "previews": previews,
    }
```

### 6. Dashboard Component

```python
# src/walltrack/dashboard/components/position_sizing.py
import gradio as gr
import httpx
import plotly.graph_objects as go
from typing import Callable


def create_position_sizing_component(api_base_url: str = "http://localhost:8000") -> gr.Blocks:
    """Create position sizing configuration dashboard component."""

    async def fetch_config() -> dict:
        """Fetch current configuration."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_base_url}/api/v1/position-sizing/config")
            return response.json()

    async def update_config(**kwargs) -> tuple[str, dict]:
        """Update configuration."""
        # Filter out None values
        data = {k: v for k, v in kwargs.items() if v is not None}

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{api_base_url}/api/v1/position-sizing/config",
                json=data,
            )
            if response.status_code == 200:
                return "✅ Configuration updated successfully!", response.json()
            else:
                return f"❌ Error: {response.text}", {}

    async def preview_sizes(balance: float, positions: int, allocated: float) -> tuple[str, any]:
        """Preview position sizes for different scores."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base_url}/api/v1/position-sizing/preview",
                params={
                    "available_balance_sol": balance,
                    "current_position_count": positions,
                    "current_allocated_sol": allocated,
                },
            )
            data = response.json()

        # Create preview table
        previews = data.get("previews", [])
        table_data = [
            [p["score"], p["tier"], p["multiplier"], p["size_sol"], p["decision"]]
            for p in previews
        ]

        # Create bar chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=[p["score"] for p in previews],
            y=[p["size_sol"] for p in previews],
            text=[p["tier"] for p in previews],
            marker_color=[
                "#22c55e" if p["tier"] == "high" else
                "#3b82f6" if p["tier"] == "standard" else
                "#ef4444"
                for p in previews
            ],
        ))
        fig.update_layout(
            title="Position Size by Score",
            xaxis_title="Signal Score",
            yaxis_title="Position Size (SOL)",
            height=300,
        )

        return table_data, fig

    with gr.Blocks() as component:
        gr.Markdown("## 📊 Position Sizing Configuration")

        with gr.Tabs():
            # Configuration Tab
            with gr.TabItem("Configuration"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Base Sizing")
                        base_pct = gr.Slider(
                            minimum=0.1,
                            maximum=10.0,
                            step=0.1,
                            value=2.0,
                            label="Base Position Size (%)",
                        )
                        min_sol = gr.Number(
                            value=0.01,
                            label="Minimum Position (SOL)",
                            minimum=0.001,
                        )
                        max_sol = gr.Number(
                            value=1.0,
                            label="Maximum Position (SOL)",
                            minimum=0.01,
                        )

                    with gr.Column():
                        gr.Markdown("### Conviction Multipliers")
                        high_mult = gr.Slider(
                            minimum=1.0,
                            maximum=3.0,
                            step=0.1,
                            value=1.5,
                            label="High Conviction Multiplier (≥0.85)",
                        )
                        std_mult = gr.Slider(
                            minimum=0.5,
                            maximum=2.0,
                            step=0.1,
                            value=1.0,
                            label="Standard Conviction Multiplier (0.70-0.84)",
                        )

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Thresholds")
                        high_thresh = gr.Slider(
                            minimum=0.5,
                            maximum=1.0,
                            step=0.01,
                            value=0.85,
                            label="High Conviction Threshold",
                        )
                        min_thresh = gr.Slider(
                            minimum=0.3,
                            maximum=0.9,
                            step=0.01,
                            value=0.70,
                            label="Minimum Trade Threshold",
                        )

                    with gr.Column():
                        gr.Markdown("### Limits")
                        max_positions = gr.Slider(
                            minimum=1,
                            maximum=20,
                            step=1,
                            value=5,
                            label="Max Concurrent Positions",
                        )
                        max_alloc = gr.Slider(
                            minimum=10,
                            maximum=100,
                            step=5,
                            value=50,
                            label="Max Capital Allocation (%)",
                        )
                        reserve = gr.Number(
                            value=0.05,
                            label="Reserve SOL (for fees)",
                            minimum=0.01,
                        )

                with gr.Row():
                    save_btn = gr.Button("💾 Save Configuration", variant="primary")
                    refresh_btn = gr.Button("🔄 Refresh", variant="secondary")

                status_msg = gr.Markdown("")

            # Preview Tab
            with gr.TabItem("Size Preview"):
                gr.Markdown("### Preview Position Sizes")
                gr.Markdown("See how position sizes change based on signal score.")

                with gr.Row():
                    preview_balance = gr.Number(
                        value=5.0,
                        label="Available Balance (SOL)",
                        minimum=0,
                    )
                    preview_positions = gr.Number(
                        value=0,
                        label="Current Positions",
                        minimum=0,
                        precision=0,
                    )
                    preview_allocated = gr.Number(
                        value=0,
                        label="Already Allocated (SOL)",
                        minimum=0,
                    )

                preview_btn = gr.Button("🔍 Preview Sizes")

                preview_table = gr.Dataframe(
                    headers=["Score", "Tier", "Multiplier", "Size (SOL)", "Decision"],
                    datatype=["number", "str", "number", "number", "str"],
                    interactive=False,
                )
                preview_chart = gr.Plot(label="Size Distribution")

        # Event handlers
        async def load_config():
            """Load current config into form fields."""
            config = await fetch_config()
            return (
                config.get("base_position_pct", 2.0),
                config.get("min_position_sol", 0.01),
                config.get("max_position_sol", 1.0),
                config.get("high_conviction_multiplier", 1.5),
                config.get("standard_conviction_multiplier", 1.0),
                config.get("high_conviction_threshold", 0.85),
                config.get("min_conviction_threshold", 0.70),
                config.get("max_concurrent_positions", 5),
                config.get("max_capital_allocation_pct", 50),
                config.get("reserve_sol", 0.05),
            )

        async def save_config_handler(
            base_pct, min_sol, max_sol, high_mult, std_mult,
            high_thresh, min_thresh, max_pos, max_alloc, reserve
        ):
            """Save configuration."""
            msg, _ = await update_config(
                base_position_pct=base_pct,
                min_position_sol=min_sol,
                max_position_sol=max_sol,
                high_conviction_multiplier=high_mult,
                standard_conviction_multiplier=std_mult,
                high_conviction_threshold=high_thresh,
                min_conviction_threshold=min_thresh,
                max_concurrent_positions=int(max_pos),
                max_capital_allocation_pct=max_alloc,
                reserve_sol=reserve,
            )
            return msg

        # Wire events
        refresh_btn.click(
            fn=load_config,
            outputs=[
                base_pct, min_sol, max_sol, high_mult, std_mult,
                high_thresh, min_thresh, max_positions, max_alloc, reserve
            ],
        )

        save_btn.click(
            fn=save_config_handler,
            inputs=[
                base_pct, min_sol, max_sol, high_mult, std_mult,
                high_thresh, min_thresh, max_positions, max_alloc, reserve
            ],
            outputs=[status_msg],
        )

        preview_btn.click(
            fn=preview_sizes,
            inputs=[preview_balance, preview_positions, preview_allocated],
            outputs=[preview_table, preview_chart],
        )

        # Load config on component load
        component.load(
            fn=load_config,
            outputs=[
                base_pct, min_sol, max_sol, high_mult, std_mult,
                high_thresh, min_thresh, max_positions, max_alloc, reserve
            ],
        )

    return component
```

### 7. Unit Tests

```python
# tests/unit/services/execution/test_position_sizer.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from walltrack.services.execution.position_sizer import PositionSizer
from walltrack.models.position_sizing import (
    PositionSizingConfig,
    PositionSizeRequest,
    ConvictionTier,
    SizingDecision,
)


@pytest.fixture
def default_config():
    """Create default position sizing config."""
    return PositionSizingConfig(
        base_position_pct=2.0,
        min_position_sol=0.01,
        max_position_sol=1.0,
        high_conviction_multiplier=1.5,
        standard_conviction_multiplier=1.0,
        high_conviction_threshold=0.85,
        min_conviction_threshold=0.70,
        max_concurrent_positions=5,
        max_capital_allocation_pct=50.0,
        reserve_sol=0.05,
    )


@pytest.fixture
def position_sizer(default_config):
    """Create position sizer with mock repo."""
    mock_repo = MagicMock()
    mock_repo.get_config = AsyncMock(return_value=default_config)

    sizer = PositionSizer(config_repo=mock_repo)
    sizer._config_cache = default_config
    return sizer


class TestConvictionTiers:
    """Tests for conviction tier determination."""

    @pytest.mark.asyncio
    async def test_high_conviction_score(self, position_sizer):
        """Test high conviction for score >= 0.85."""
        request = PositionSizeRequest(
            signal_score=0.90,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        assert result.conviction_tier == ConvictionTier.HIGH
        assert result.multiplier == 1.5

    @pytest.mark.asyncio
    async def test_standard_conviction_score(self, position_sizer):
        """Test standard conviction for score 0.70-0.84."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        assert result.conviction_tier == ConvictionTier.STANDARD
        assert result.multiplier == 1.0

    @pytest.mark.asyncio
    async def test_low_score_skipped(self, position_sizer):
        """Test scores below threshold are skipped."""
        request = PositionSizeRequest(
            signal_score=0.65,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        assert result.conviction_tier == ConvictionTier.NONE
        assert result.decision == SizingDecision.SKIPPED_LOW_SCORE
        assert result.final_size_sol == 0


class TestSizeCalculation:
    """Tests for position size calculation."""

    @pytest.mark.asyncio
    async def test_base_size_calculation(self, position_sizer):
        """Test base size is 2% of available capital."""
        request = PositionSizeRequest(
            signal_score=0.75,  # Standard conviction
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        # Usable = 10.0 - 0.05 reserve = 9.95
        # Base = 9.95 * 2% = 0.199
        # With 1.0x multiplier = 0.199
        assert result.base_size_sol == pytest.approx(0.199, rel=0.01)
        assert result.final_size_sol == pytest.approx(0.199, rel=0.01)

    @pytest.mark.asyncio
    async def test_high_conviction_multiplier_applied(self, position_sizer):
        """Test 1.5x multiplier for high conviction."""
        request = PositionSizeRequest(
            signal_score=0.90,  # High conviction
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        # Base = 9.95 * 2% = 0.199
        # With 1.5x multiplier = 0.2985
        assert result.multiplier == 1.5
        assert result.calculated_size_sol == pytest.approx(0.2985, rel=0.01)


class TestLimitsAndValidation:
    """Tests for limit enforcement."""

    @pytest.mark.asyncio
    async def test_max_position_limit(self, position_sizer):
        """Test position capped at max_position_sol."""
        # Large balance that would exceed max
        request = PositionSizeRequest(
            signal_score=0.95,
            available_balance_sol=100.0,  # 2% * 1.5 = 3 SOL, but max is 1.0
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        assert result.final_size_sol == 1.0  # Capped at max
        assert result.reduction_applied is True
        assert result.decision == SizingDecision.REDUCED

    @pytest.mark.asyncio
    async def test_max_concurrent_positions_blocks(self, position_sizer):
        """Test trade blocked when max positions reached."""
        request = PositionSizeRequest(
            signal_score=0.90,
            available_balance_sol=10.0,
            current_position_count=5,  # At max
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        assert result.decision == SizingDecision.SKIPPED_MAX_POSITIONS
        assert result.final_size_sol == 0

    @pytest.mark.asyncio
    async def test_insufficient_balance_reduces(self, position_sizer):
        """Test size reduced when balance is low."""
        request = PositionSizeRequest(
            signal_score=0.90,
            available_balance_sol=0.1,  # Very low
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        # Usable = 0.1 - 0.05 = 0.05
        # Base would be 0.001 (2% of 0.05)
        # With multiplier = 0.0015, which is above min 0.01
        # But limited by available 0.05
        assert result.final_size_sol <= 0.05

    @pytest.mark.asyncio
    async def test_below_minimum_skipped(self, position_sizer):
        """Test trade skipped when below minimum size."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=0.06,  # Just above reserve
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request)

        # Usable = 0.06 - 0.05 = 0.01
        # Base = 0.01 * 2% = 0.0002, below min 0.01
        assert result.decision in [
            SizingDecision.SKIPPED_MIN_SIZE,
            SizingDecision.SKIPPED_NO_BALANCE,
        ]


class TestConfigValidation:
    """Tests for config model validation."""

    def test_threshold_ordering_validated(self):
        """Test high threshold must be > min threshold."""
        with pytest.raises(ValueError, match="high_conviction_threshold must be"):
            PositionSizingConfig(
                high_conviction_threshold=0.70,
                min_conviction_threshold=0.75,  # Invalid: min > high
            )

    def test_position_limits_validated(self):
        """Test max must be >= min."""
        with pytest.raises(ValueError, match="max_position_sol must be"):
            PositionSizingConfig(
                min_position_sol=1.0,
                max_position_sol=0.5,  # Invalid: max < min
            )
```

### 8. Database Schema

```sql
-- migrations/006_position_sizing.sql

-- Position sizing configuration (singleton)
CREATE TABLE IF NOT EXISTS position_sizing_config (
    id UUID PRIMARY KEY DEFAULT '00000000-0000-0000-0000-000000000001',

    -- Base sizing
    base_position_pct DECIMAL(5, 2) NOT NULL DEFAULT 2.0,
    min_position_sol DECIMAL(20, 9) NOT NULL DEFAULT 0.01,
    max_position_sol DECIMAL(20, 9) NOT NULL DEFAULT 1.0,

    -- Conviction multipliers
    high_conviction_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.5,
    standard_conviction_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.0,

    -- Thresholds
    high_conviction_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.85,
    min_conviction_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.70,

    -- Limits
    max_concurrent_positions INTEGER NOT NULL DEFAULT 5,
    max_capital_allocation_pct DECIMAL(5, 2) NOT NULL DEFAULT 50.0,
    reserve_sol DECIMAL(20, 9) NOT NULL DEFAULT 0.05,

    -- Metadata
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,

    -- Constraints
    CONSTRAINT valid_base_pct CHECK (base_position_pct > 0 AND base_position_pct <= 100),
    CONSTRAINT valid_multipliers CHECK (
        high_conviction_multiplier >= 1.0 AND
        standard_conviction_multiplier >= 0.5
    ),
    CONSTRAINT valid_thresholds CHECK (
        high_conviction_threshold > min_conviction_threshold AND
        min_conviction_threshold >= 0.3
    ),
    CONSTRAINT valid_limits CHECK (
        max_position_sol >= min_position_sol AND
        max_concurrent_positions >= 1
    )
);

-- Position sizing audit log
CREATE TABLE IF NOT EXISTS position_sizing_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID,
    token_address TEXT,

    -- Input parameters
    signal_score DECIMAL(5, 4) NOT NULL,
    available_balance_sol DECIMAL(20, 9) NOT NULL,
    current_position_count INTEGER NOT NULL,
    current_allocated_sol DECIMAL(20, 9) NOT NULL,

    -- Config snapshot (for reproducibility)
    config_snapshot JSONB NOT NULL,

    -- Result
    decision TEXT NOT NULL,
    conviction_tier TEXT NOT NULL,
    base_size_sol DECIMAL(20, 9) NOT NULL,
    multiplier DECIMAL(5, 2) NOT NULL,
    final_size_sol DECIMAL(20, 9) NOT NULL,
    reason TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_position_audit_signal ON position_sizing_audit(signal_id);
CREATE INDEX IF NOT EXISTS idx_position_audit_created ON position_sizing_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_position_audit_decision ON position_sizing_audit(decision);

-- Initialize default config
INSERT INTO position_sizing_config (id)
VALUES ('00000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

-- RLS Policies
ALTER TABLE position_sizing_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE position_sizing_audit ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on position_sizing_config"
ON position_sizing_config FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on position_sizing_audit"
ON position_sizing_audit FOR ALL TO service_role USING (true);
```

## Implementation Tasks

- [ ] Create `src/walltrack/models/position_sizing.py` with all models
- [ ] Create `src/walltrack/config/position_settings.py`
- [ ] Create `src/walltrack/services/execution/position_sizer.py`
- [ ] Implement base size calculation with % of capital
- [ ] Implement score-based conviction tier determination
- [ ] Apply multipliers (1.5x high, 1.0x standard)
- [ ] Validate against max limits and balance
- [ ] Handle insufficient balance gracefully
- [ ] Create `src/walltrack/repositories/position_config_repository.py`
- [ ] Create `src/walltrack/api/routes/position_sizing.py`
- [ ] Create `src/walltrack/dashboard/components/position_sizing.py`
- [ ] Add database migrations
- [ ] Write comprehensive unit tests

## Definition of Done

- [ ] Position size varies by signal score (1.5x for ≥0.85, 1.0x for 0.70-0.84)
- [ ] Base size configurable as % of capital
- [ ] Validation prevents oversized positions
- [ ] Max concurrent positions enforced
- [ ] Insufficient balance handled gracefully (reduce or skip)
- [ ] Configuration adjustable via dashboard with immediate effect
- [ ] All sizing decisions audited
- [ ] Unit tests pass with >90% coverage
