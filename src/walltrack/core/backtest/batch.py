"""Batch backtest execution models."""

from datetime import UTC, datetime
from enum import Enum
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
    """Status of a single scenario in batch.

    Tracks the execution state and result of one scenario.
    """

    scenario_id: UUID
    scenario_name: str
    status: BatchStatus = BatchStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: BacktestResult | None = None
    error: str | None = None


class BatchProgress(BaseModel):
    """Progress of batch execution.

    Provides summary statistics for tracking batch progress.
    """

    batch_id: UUID
    total_scenarios: int
    completed: int = 0
    failed: int = 0
    running: int = 0
    pending: int = 0
    cancelled: int = 0

    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage.

        Returns:
            Percentage of scenarios completed (0-100).
        """
        if self.total_scenarios == 0:
            return 100.0
        return (self.completed + self.failed) / self.total_scenarios * 100


class BatchRun(BaseModel):
    """A complete batch backtest run.

    Contains configuration, state, and results for a batch
    of backtest scenarios.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str

    # Configuration
    scenario_ids: list[UUID]
    start_date: datetime
    end_date: datetime
    max_workers: int = 3

    # Execution state
    status: BatchStatus = BatchStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Results
    executions: list[ScenarioExecution] = Field(default_factory=list)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None

    def get_progress(self) -> BatchProgress:
        """Get current progress.

        Returns:
            BatchProgress with execution counts.
        """
        return BatchProgress(
            batch_id=self.id,
            total_scenarios=len(self.scenario_ids),
            completed=len(
                [e for e in self.executions if e.status == BatchStatus.COMPLETED]
            ),
            failed=len([e for e in self.executions if e.status == BatchStatus.FAILED]),
            running=len(
                [e for e in self.executions if e.status == BatchStatus.RUNNING]
            ),
            pending=len(
                [e for e in self.executions if e.status == BatchStatus.PENDING]
            ),
            cancelled=len(
                [e for e in self.executions if e.status == BatchStatus.CANCELLED]
            ),
        )

    def get_successful_results(self) -> list[BacktestResult]:
        """Get all successful backtest results.

        Returns:
            List of BacktestResult for completed scenarios.
        """
        return [
            e.result
            for e in self.executions
            if e.status == BatchStatus.COMPLETED and e.result
        ]
