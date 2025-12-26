# Story 9.1: Discovery Runs History

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: Story 1.4 (Wallet Discovery Engine)

## User Story

**As an** operator,
**I want** to track the history of all discovery runs,
**So that** I can monitor system performance and see discovered wallets over time.

## Acceptance Criteria

### AC 1: Discovery Run Storage
**Given** a discovery run completes (manual or scheduled)
**When** results are available
**Then** run metadata is stored in database
**And** includes: timestamp, duration, tokens analyzed, wallets found
**And** includes: parameters used, errors encountered

### AC 2: Run Details Storage
**Given** a discovery run finds wallets
**When** the run completes
**Then** each discovered wallet is linked to the run
**And** wallet discovery source (which token) is recorded
**And** initial profile data is stored

### AC 3: History Retrieval
**Given** history query request
**When** API is called with date range
**Then** runs for that period are returned
**And** summary stats are calculated
**And** pagination is supported

### AC 4: Run Statistics
**Given** history data exists
**When** stats are requested
**Then** total runs count is returned
**And** success rate is calculated
**And** average wallets per run is calculated
**And** trend data (week over week) is available

## Technical Specifications

### Database Schema

```sql
-- Discovery runs table
CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',

    -- Trigger type
    trigger_type VARCHAR(20) NOT NULL, -- 'manual', 'scheduled', 'api'
    triggered_by VARCHAR(100), -- user/system identifier

    -- Parameters used
    min_price_change_pct DECIMAL(5,2),
    min_volume_usd DECIMAL(15,2),
    max_token_age_hours INTEGER,
    early_window_minutes INTEGER,
    min_profit_pct DECIMAL(5,2),
    max_tokens INTEGER,

    -- Results
    tokens_analyzed INTEGER DEFAULT 0,
    new_wallets INTEGER DEFAULT 0,
    updated_wallets INTEGER DEFAULT 0,
    profiled_wallets INTEGER DEFAULT 0,
    duration_seconds DECIMAL(10,2),

    -- Errors
    errors JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_discovery_runs_started ON discovery_runs(started_at DESC);
CREATE INDEX idx_discovery_runs_status ON discovery_runs(status);

-- Discovery run wallets (link table)
CREATE TABLE IF NOT EXISTS discovery_run_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES discovery_runs(id),
    wallet_address VARCHAR(44) NOT NULL,
    source_token VARCHAR(44) NOT NULL,
    is_new BOOLEAN DEFAULT TRUE,
    initial_score DECIMAL(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_drw_run ON discovery_run_wallets(run_id);
CREATE INDEX idx_drw_wallet ON discovery_run_wallets(wallet_address);
```

### Discovery Run Model

**src/walltrack/discovery/models.py:**
```python
"""Discovery management models."""

from datetime import datetime
from enum import Enum
from typing import Optional
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
    completed_at: Optional[datetime] = None
    status: RunStatus = RunStatus.RUNNING

    trigger_type: TriggerType
    triggered_by: Optional[str] = None

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
    initial_score: Optional[float] = None


class DiscoveryStats(BaseModel):
    """Aggregated discovery statistics."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_wallets_discovered: int = 0
    total_wallets_updated: int = 0
    avg_wallets_per_run: float = 0.0
    avg_duration_seconds: float = 0.0
    last_run_at: Optional[datetime] = None
```

### Discovery Run Repository

**src/walltrack/data/supabase/repositories/discovery_repo.py:**
```python
"""Repository for discovery run data."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from walltrack.data.supabase.client import SupabaseClient
from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunWallet,
    DiscoveryStats,
    RunStatus,
    TriggerType,
)


class DiscoveryRepository:
    """Repository for discovery runs."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    async def create_run(
        self,
        trigger_type: TriggerType,
        params: dict,
        triggered_by: Optional[str] = None,
    ) -> DiscoveryRun:
        """Create a new discovery run record."""
        run_id = uuid4()
        now = datetime.utcnow()

        data = {
            "id": str(run_id),
            "started_at": now.isoformat(),
            "status": RunStatus.RUNNING.value,
            "trigger_type": trigger_type.value,
            "triggered_by": triggered_by,
            **params,
        }

        await self.client.insert("discovery_runs", data)
        return DiscoveryRun(id=run_id, started_at=now, trigger_type=trigger_type)

    async def complete_run(
        self,
        run_id: UUID,
        tokens_analyzed: int,
        new_wallets: int,
        updated_wallets: int,
        profiled_wallets: int,
        duration_seconds: float,
        errors: list[str],
    ) -> None:
        """Mark run as completed with results."""
        await self.client.update(
            "discovery_runs",
            {"id": str(run_id)},
            {
                "completed_at": datetime.utcnow().isoformat(),
                "status": RunStatus.COMPLETED.value,
                "tokens_analyzed": tokens_analyzed,
                "new_wallets": new_wallets,
                "updated_wallets": updated_wallets,
                "profiled_wallets": profiled_wallets,
                "duration_seconds": duration_seconds,
                "errors": errors,
            },
        )

    async def fail_run(self, run_id: UUID, error: str) -> None:
        """Mark run as failed."""
        await self.client.update(
            "discovery_runs",
            {"id": str(run_id)},
            {
                "completed_at": datetime.utcnow().isoformat(),
                "status": RunStatus.FAILED.value,
                "errors": [error],
            },
        )

    async def get_run(self, run_id: UUID) -> Optional[DiscoveryRun]:
        """Get a discovery run by ID."""
        # Implementation
        pass

    async def get_runs(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DiscoveryRun]:
        """Get discovery runs with optional filters."""
        # Implementation
        pass

    async def get_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> DiscoveryStats:
        """Get aggregated statistics."""
        # Implementation
        pass

    async def add_wallet_to_run(
        self,
        run_id: UUID,
        wallet_address: str,
        source_token: str,
        is_new: bool,
        initial_score: Optional[float] = None,
    ) -> None:
        """Record a wallet discovered in a run."""
        await self.client.insert(
            "discovery_run_wallets",
            {
                "id": str(uuid4()),
                "run_id": str(run_id),
                "wallet_address": wallet_address,
                "source_token": source_token,
                "is_new": is_new,
                "initial_score": initial_score,
            },
        )
```

## Implementation Tasks

- [x] Create discovery_runs database table
- [x] Create discovery_run_wallets database table
- [x] Create DiscoveryRun and related models
- [x] Create DiscoveryRepository
- [x] Integrate with existing discovery task
- [x] Write unit tests

## Definition of Done

- [x] All discovery runs are persisted to database
- [x] Run parameters and results are stored
- [x] Discovered wallets are linked to runs
- [x] History can be queried by date range
- [x] Statistics are calculated correctly
- [x] Tests cover CRUD operations

## Dev Agent Record

### Implementation Notes (2024-12-24)
- Created migration file `019_discovery_runs.sql` with tables and indexes
- Implemented Pydantic models: `DiscoveryRun`, `DiscoveryRunParams`, `DiscoveryRunWallet`, `DiscoveryStats`, `RunStatus`, `TriggerType`
- Implemented `DiscoveryRepository` with full CRUD operations
- Integrated repository with `discovery_task.py` - runs now tracked automatically
- Added 40 unit tests covering models and repository (100% pass)

## File List

### New Files
- `src/walltrack/discovery/models.py` - Discovery run models (RunStatus, TriggerType, DiscoveryRun, DiscoveryRunParams, DiscoveryRunWallet, DiscoveryStats)
- `src/walltrack/data/supabase/repositories/discovery_repo.py` - Repository with CRUD operations
- `src/walltrack/data/supabase/migrations/019_discovery_runs.sql` - Database schema
- `tests/unit/discovery/test_discovery_models.py` - 21 model tests
- `tests/unit/data/test_discovery_repo.py` - 19 repository tests

### Modified Files
- `src/walltrack/discovery/__init__.py` - Export new models
- `src/walltrack/data/supabase/repositories/__init__.py` - Export DiscoveryRepository
- `src/walltrack/scheduler/tasks/discovery_task.py` - Integrate run tracking
