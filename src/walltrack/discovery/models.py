"""Discovery management models."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Discovery run status."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TriggerType(str, Enum):
    """How the run was triggered."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    API = "api"


class DiscoveryRunParams(BaseModel):
    """Parameters for a discovery run."""

    min_price_change_pct: float = 100.0
    min_volume_usd: float = 50000.0
    max_token_age_hours: int = 72
    early_window_minutes: int = 30
    min_profit_pct: float = 50.0
    max_tokens: int = 20


class DiscoveryRun(BaseModel):
    """A single discovery run record."""

    id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    status: RunStatus = RunStatus.RUNNING

    trigger_type: TriggerType
    triggered_by: str | None = None

    # Parameters
    params: DiscoveryRunParams = Field(default_factory=DiscoveryRunParams)

    # Results
    tokens_analyzed: int = 0
    new_wallets: int = 0
    updated_wallets: int = 0
    profiled_wallets: int = 0
    duration_seconds: float = 0.0

    errors: list[str] = Field(default_factory=list)


class DiscoveryRunWallet(BaseModel):
    """Wallet discovered in a run."""

    id: UUID
    run_id: UUID
    wallet_address: str
    source_token: str
    is_new: bool = True
    initial_score: float | None = None
    created_at: datetime | None = None


class DiscoveryStats(BaseModel):
    """Aggregated discovery statistics."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_wallets_discovered: int = 0
    total_wallets_updated: int = 0
    avg_wallets_per_run: float = 0.0
    avg_duration_seconds: float = 0.0
    last_run_at: datetime | None = None


class DiscoveryRunCreate(BaseModel):
    """Input for creating a discovery run."""

    trigger_type: TriggerType
    triggered_by: str | None = None
    params: DiscoveryRunParams = Field(default_factory=DiscoveryRunParams)


class DiscoveryRunUpdate(BaseModel):
    """Input for updating a discovery run."""

    status: RunStatus | None = None
    completed_at: datetime | None = None
    tokens_analyzed: int | None = None
    new_wallets: int | None = None
    updated_wallets: int | None = None
    profiled_wallets: int | None = None
    duration_seconds: float | None = None
    errors: list[str] | None = None
