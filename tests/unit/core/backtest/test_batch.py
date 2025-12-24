"""Tests for batch backtest models."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest


class TestBatchStatus:
    """Tests for BatchStatus enum."""

    def test_status_values(self) -> None:
        """Test all status enum values exist."""
        from walltrack.core.backtest.batch import BatchStatus

        assert BatchStatus.PENDING.value == "pending"
        assert BatchStatus.RUNNING.value == "running"
        assert BatchStatus.COMPLETED.value == "completed"
        assert BatchStatus.CANCELLED.value == "cancelled"
        assert BatchStatus.FAILED.value == "failed"


class TestScenarioExecution:
    """Tests for ScenarioExecution model."""

    def test_execution_creation(self) -> None:
        """Test creating a scenario execution."""
        from walltrack.core.backtest.batch import BatchStatus, ScenarioExecution

        execution = ScenarioExecution(
            scenario_id=uuid4(),
            scenario_name="Test Scenario",
        )

        assert execution.scenario_name == "Test Scenario"
        assert execution.status == BatchStatus.PENDING
        assert execution.result is None
        assert execution.error is None


class TestBatchProgress:
    """Tests for BatchProgress model."""

    def test_progress_calculation(self) -> None:
        """Test progress percentage calculation."""
        from walltrack.core.backtest.batch import BatchProgress

        progress = BatchProgress(
            batch_id=uuid4(),
            total_scenarios=10,
            completed=3,
            failed=1,
            running=2,
            pending=4,
        )

        # (3 + 1) / 10 = 40%
        assert progress.progress_pct == 40.0

    def test_progress_empty_batch(self) -> None:
        """Test progress with no scenarios."""
        from walltrack.core.backtest.batch import BatchProgress

        progress = BatchProgress(
            batch_id=uuid4(),
            total_scenarios=0,
        )

        assert progress.progress_pct == 100.0


class TestBatchRun:
    """Tests for BatchRun model."""

    def test_batch_creation(self) -> None:
        """Test creating a batch run."""
        from walltrack.core.backtest.batch import BatchRun, BatchStatus

        scenario_ids = [uuid4(), uuid4()]
        batch = BatchRun(
            name="Test Batch",
            scenario_ids=scenario_ids,
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
        )

        assert batch.name == "Test Batch"
        assert len(batch.scenario_ids) == 2
        assert batch.status == BatchStatus.PENDING
        assert batch.max_workers == 3

    def test_get_progress(self) -> None:
        """Test getting batch progress."""
        from walltrack.core.backtest.batch import (
            BatchRun,
            BatchStatus,
            ScenarioExecution,
        )

        batch = BatchRun(
            name="Test",
            scenario_ids=[uuid4(), uuid4(), uuid4()],
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
        )

        # Add executions with different statuses
        batch.executions = [
            ScenarioExecution(
                scenario_id=uuid4(),
                scenario_name="S1",
                status=BatchStatus.COMPLETED,
            ),
            ScenarioExecution(
                scenario_id=uuid4(),
                scenario_name="S2",
                status=BatchStatus.RUNNING,
            ),
            ScenarioExecution(
                scenario_id=uuid4(),
                scenario_name="S3",
                status=BatchStatus.PENDING,
            ),
        ]

        progress = batch.get_progress()

        assert progress.total_scenarios == 3
        assert progress.completed == 1
        assert progress.running == 1
        assert progress.pending == 1

    def test_get_successful_results(self) -> None:
        """Test getting successful results from batch."""
        from decimal import Decimal
        from uuid import uuid4

        from walltrack.core.backtest.batch import (
            BatchRun,
            BatchStatus,
            ScenarioExecution,
        )
        from walltrack.core.backtest.results import BacktestMetrics, BacktestResult

        batch = BatchRun(
            name="Test",
            scenario_ids=[uuid4(), uuid4()],
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
        )

        now = datetime.now(UTC)
        result = BacktestResult(
            id=uuid4(),
            name="Test Result",
            parameters={},
            started_at=now,
            completed_at=now,
            duration_seconds=1.0,
            trades=[],
            metrics=BacktestMetrics(),
        )

        batch.executions = [
            ScenarioExecution(
                scenario_id=uuid4(),
                scenario_name="S1",
                status=BatchStatus.COMPLETED,
                result=result,
            ),
            ScenarioExecution(
                scenario_id=uuid4(),
                scenario_name="S2",
                status=BatchStatus.FAILED,
                error="Test error",
            ),
        ]

        successful = batch.get_successful_results()

        assert len(successful) == 1
        assert successful[0].name == "Test Result"
