# Story 8.4: Batch Backtest Runner

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: Medium
- **FR**: FR64

## User Story

**As an** operator,
**I want** to run multiple backtest scenarios in batch,
**So that** I can compare different configurations efficiently.

## Acceptance Criteria

### AC 1: Batch Execution
**Given** multiple scenarios are selected
**When** batch backtest is started
**Then** all scenarios are queued for execution
**And** progress indicator shows current/total
**And** scenarios run in parallel (configurable workers)

### AC 2: Progress Tracking
**Given** batch backtest is running
**When** a scenario completes
**Then** results are stored immediately
**And** progress updates in real-time
**And** failed scenarios are logged and skipped

### AC 3: Completion Handling
**Given** batch backtest completes
**When** all scenarios finish
**Then** summary of all results is available
**And** comparison view is generated
**And** notification is sent to operator

### AC 4: Cancellation
**Given** long-running batch
**When** operator wants to cancel
**Then** cancel button stops remaining scenarios
**And** completed results are preserved
**And** partial batch can be resumed

## Technical Specifications

### Batch Runner Models

**src/walltrack/core/backtest/batch.py:**
```python
"""Batch backtest execution."""

import asyncio
from datetime import datetime, UTC
from enum import Enum
from typing import Callable, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from walltrack.core.backtest.results import BacktestResult


class BatchStatus(str, Enum):
    """Status of a batch execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ScenarioExecution(BaseModel):
    """Status of a single scenario in batch."""

    scenario_id: UUID
    scenario_name: str
    status: BatchStatus = BatchStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[BacktestResult] = None
    error: Optional[str] = None


class BatchProgress(BaseModel):
    """Progress of batch execution."""

    batch_id: UUID
    total_scenarios: int
    completed: int = 0
    failed: int = 0
    running: int = 0
    pending: int = 0
    cancelled: int = 0

    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        if self.total_scenarios == 0:
            return 100.0
        return (self.completed + self.failed) / self.total_scenarios * 100


class BatchRun(BaseModel):
    """A complete batch backtest run."""

    id: UUID = Field(default_factory=uuid4)
    name: str

    # Configuration
    scenario_ids: list[UUID]
    start_date: datetime
    end_date: datetime
    max_workers: int = 3

    # Execution state
    status: BatchStatus = BatchStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Results
    executions: list[ScenarioExecution] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: Optional[str] = None

    def get_progress(self) -> BatchProgress:
        """Get current progress."""
        return BatchProgress(
            batch_id=self.id,
            total_scenarios=len(self.scenario_ids),
            completed=len([e for e in self.executions if e.status == BatchStatus.COMPLETED]),
            failed=len([e for e in self.executions if e.status == BatchStatus.FAILED]),
            running=len([e for e in self.executions if e.status == BatchStatus.RUNNING]),
            pending=len([e for e in self.executions if e.status == BatchStatus.PENDING]),
            cancelled=len([e for e in self.executions if e.status == BatchStatus.CANCELLED]),
        )

    def get_successful_results(self) -> list[BacktestResult]:
        """Get all successful backtest results."""
        return [
            e.result
            for e in self.executions
            if e.status == BatchStatus.COMPLETED and e.result
        ]
```

### Batch Runner Service

**src/walltrack/core/backtest/batch_runner.py:**
```python
"""Batch backtest runner service."""

import asyncio
from datetime import datetime, UTC
from typing import Callable, Optional
from uuid import UUID

import structlog

from walltrack.core.backtest.batch import (
    BatchRun,
    BatchStatus,
    ScenarioExecution,
    BatchProgress,
)
from walltrack.core.backtest.engine import BacktestEngine
from walltrack.core.backtest.scenario_service import get_scenario_service
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


class BatchBacktestRunner:
    """Runs multiple backtests in parallel."""

    def __init__(self, max_workers: int = 3) -> None:
        self._max_workers = max_workers
        self._active_batches: dict[UUID, BatchRun] = {}
        self._cancel_flags: dict[UUID, bool] = {}
        self._progress_callbacks: dict[UUID, Callable[[BatchProgress], None]] = {}

    async def start_batch(
        self,
        name: str,
        scenario_ids: list[UUID],
        start_date: datetime,
        end_date: datetime,
        on_progress: Optional[Callable[[BatchProgress], None]] = None,
    ) -> BatchRun:
        """Start a new batch backtest."""
        scenario_service = await get_scenario_service()

        # Initialize batch
        batch = BatchRun(
            name=name,
            scenario_ids=scenario_ids,
            start_date=start_date,
            end_date=end_date,
            max_workers=self._max_workers,
            status=BatchStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        # Initialize executions
        for scenario_id in scenario_ids:
            scenario = await scenario_service.get_scenario(scenario_id)
            if scenario:
                batch.executions.append(
                    ScenarioExecution(
                        scenario_id=scenario_id,
                        scenario_name=scenario.name,
                    )
                )

        self._active_batches[batch.id] = batch
        self._cancel_flags[batch.id] = False

        if on_progress:
            self._progress_callbacks[batch.id] = on_progress

        # Store batch in database
        await self._store_batch(batch)

        # Run batch asynchronously
        asyncio.create_task(self._execute_batch(batch))

        log.info(
            "batch_started",
            batch_id=str(batch.id),
            scenarios=len(scenario_ids),
        )

        return batch

    async def _execute_batch(self, batch: BatchRun) -> None:
        """Execute all scenarios in the batch."""
        semaphore = asyncio.Semaphore(self._max_workers)

        async def run_scenario(execution: ScenarioExecution) -> None:
            async with semaphore:
                if self._cancel_flags.get(batch.id, False):
                    execution.status = BatchStatus.CANCELLED
                    return

                try:
                    execution.status = BatchStatus.RUNNING
                    execution.started_at = datetime.now(UTC)
                    self._notify_progress(batch)

                    # Get scenario and run backtest
                    scenario_service = await get_scenario_service()
                    scenario = await scenario_service.get_scenario(execution.scenario_id)

                    if not scenario:
                        raise ValueError(f"Scenario not found: {execution.scenario_id}")

                    params = scenario.to_backtest_params(
                        start_date=batch.start_date,
                        end_date=batch.end_date,
                    )

                    engine = BacktestEngine(params)
                    result = await engine.run(name=scenario.name)

                    execution.result = result
                    execution.status = BatchStatus.COMPLETED
                    execution.completed_at = datetime.now(UTC)

                    log.info(
                        "scenario_completed",
                        batch_id=str(batch.id),
                        scenario=scenario.name,
                        pnl=float(result.metrics.total_pnl),
                    )

                except Exception as e:
                    execution.status = BatchStatus.FAILED
                    execution.error = str(e)
                    execution.completed_at = datetime.now(UTC)

                    log.error(
                        "scenario_failed",
                        batch_id=str(batch.id),
                        scenario_id=str(execution.scenario_id),
                        error=str(e),
                    )

                finally:
                    self._notify_progress(batch)
                    await self._update_batch(batch)

        # Run all scenarios
        tasks = [run_scenario(e) for e in batch.executions]
        await asyncio.gather(*tasks)

        # Finalize batch
        if self._cancel_flags.get(batch.id, False):
            batch.status = BatchStatus.CANCELLED
        elif all(e.status in (BatchStatus.COMPLETED, BatchStatus.FAILED) for e in batch.executions):
            batch.status = BatchStatus.COMPLETED
        else:
            batch.status = BatchStatus.FAILED

        batch.completed_at = datetime.now(UTC)

        await self._update_batch(batch)
        self._notify_progress(batch)

        # Cleanup
        self._active_batches.pop(batch.id, None)
        self._cancel_flags.pop(batch.id, None)
        self._progress_callbacks.pop(batch.id, None)

        log.info(
            "batch_completed",
            batch_id=str(batch.id),
            status=batch.status.value,
            completed=len([e for e in batch.executions if e.status == BatchStatus.COMPLETED]),
            failed=len([e for e in batch.executions if e.status == BatchStatus.FAILED]),
        )

    async def cancel_batch(self, batch_id: UUID) -> bool:
        """Cancel a running batch."""
        if batch_id in self._active_batches:
            self._cancel_flags[batch_id] = True
            log.info("batch_cancellation_requested", batch_id=str(batch_id))
            return True
        return False

    def get_progress(self, batch_id: UUID) -> Optional[BatchProgress]:
        """Get current progress of a batch."""
        batch = self._active_batches.get(batch_id)
        if batch:
            return batch.get_progress()
        return None

    def _notify_progress(self, batch: BatchRun) -> None:
        """Notify progress callback if registered."""
        callback = self._progress_callbacks.get(batch.id)
        if callback:
            try:
                callback(batch.get_progress())
            except Exception as e:
                log.warning("progress_callback_failed", error=str(e))

    async def _store_batch(self, batch: BatchRun) -> None:
        """Store batch in database."""
        supabase = await get_supabase_client()

        record = {
            "id": str(batch.id),
            "name": batch.name,
            "scenario_ids": [str(s) for s in batch.scenario_ids],
            "start_date": batch.start_date.isoformat(),
            "end_date": batch.end_date.isoformat(),
            "status": batch.status.value,
            "started_at": batch.started_at.isoformat() if batch.started_at else None,
            "created_at": batch.created_at.isoformat(),
        }

        await supabase.insert("batch_backtests", record)

    async def _update_batch(self, batch: BatchRun) -> None:
        """Update batch in database."""
        supabase = await get_supabase_client()

        # Store results separately for completed executions
        for execution in batch.executions:
            if execution.result:
                result_record = {
                    "id": str(execution.result.id),
                    "batch_id": str(batch.id),
                    "scenario_id": str(execution.scenario_id),
                    "scenario_name": execution.scenario_name,
                    "status": execution.status.value,
                    "metrics": execution.result.metrics.model_dump(mode="json"),
                    "parameters": execution.result.parameters,
                    "started_at": execution.started_at.isoformat() if execution.started_at else None,
                    "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                    "error": execution.error,
                }
                await supabase.upsert("backtest_results", result_record)

        # Update batch status
        await supabase.update(
            "batch_backtests",
            {"id": str(batch.id)},
            {
                "status": batch.status.value,
                "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
            },
        )

    async def get_batch(self, batch_id: UUID) -> Optional[BatchRun]:
        """Get a batch by ID."""
        # Check active batches first
        if batch_id in self._active_batches:
            return self._active_batches[batch_id]

        # Load from database
        supabase = await get_supabase_client()
        records = await supabase.select(
            "batch_backtests",
            filters={"id": str(batch_id)},
        )

        if not records:
            return None

        # Load associated results
        results = await supabase.select(
            "backtest_results",
            filters={"batch_id": str(batch_id)},
        )

        # Reconstruct batch
        record = records[0]
        batch = BatchRun(
            id=UUID(record["id"]),
            name=record["name"],
            scenario_ids=[UUID(s) for s in record["scenario_ids"]],
            start_date=datetime.fromisoformat(record["start_date"]),
            end_date=datetime.fromisoformat(record["end_date"]),
            status=BatchStatus(record["status"]),
            started_at=datetime.fromisoformat(record["started_at"]) if record.get("started_at") else None,
            completed_at=datetime.fromisoformat(record["completed_at"]) if record.get("completed_at") else None,
            created_at=datetime.fromisoformat(record["created_at"]),
        )

        # Add executions from results
        for result in results:
            batch.executions.append(
                ScenarioExecution(
                    scenario_id=UUID(result["scenario_id"]),
                    scenario_name=result["scenario_name"],
                    status=BatchStatus(result["status"]),
                    started_at=datetime.fromisoformat(result["started_at"]) if result.get("started_at") else None,
                    completed_at=datetime.fromisoformat(result["completed_at"]) if result.get("completed_at") else None,
                    error=result.get("error"),
                )
            )

        return batch

    async def list_batches(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[BatchRun]:
        """List recent batch runs."""
        supabase = await get_supabase_client()

        records = await supabase.select(
            "batch_backtests",
            order_by="created_at DESC",
            limit=limit,
            offset=offset,
        )

        batches = []
        for record in records:
            batch = await self.get_batch(UUID(record["id"]))
            if batch:
                batches.append(batch)

        return batches


# Singleton
_batch_runner: Optional[BatchBacktestRunner] = None


async def get_batch_runner() -> BatchBacktestRunner:
    """Get batch runner singleton."""
    global _batch_runner
    if _batch_runner is None:
        _batch_runner = BatchBacktestRunner()
    return _batch_runner
```

## Database Schema

```sql
-- Batch backtests table
CREATE TABLE IF NOT EXISTS batch_backtests (
    id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    scenario_ids UUID[] NOT NULL,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    max_workers INTEGER DEFAULT 3,
    status VARCHAR(20) DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100)
);

CREATE INDEX idx_batch_status ON batch_backtests(status);
CREATE INDEX idx_batch_created ON batch_backtests(created_at);

-- Backtest results table
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY,
    batch_id UUID REFERENCES batch_backtests(id),
    scenario_id UUID NOT NULL,
    scenario_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    metrics JSONB,
    parameters JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_results_batch ON backtest_results(batch_id);
CREATE INDEX idx_results_scenario ON backtest_results(scenario_id);
```

## Implementation Tasks

- [ ] Create BatchRun and ScenarioExecution models
- [ ] Implement BatchBacktestRunner with parallel execution
- [ ] Implement progress tracking and callbacks
- [ ] Implement cancellation support
- [ ] Create database tables for batch storage
- [ ] Store batch results in database
- [ ] Implement batch retrieval and listing
- [ ] Write unit tests

## Definition of Done

- [ ] Batch execution runs scenarios in parallel
- [ ] Progress is tracked and reported
- [ ] Failed scenarios don't stop batch
- [ ] Cancellation stops remaining scenarios
- [ ] Results are persisted to database
- [ ] Tests cover all execution paths
