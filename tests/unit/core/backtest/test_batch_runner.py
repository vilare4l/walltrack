"""Tests for batch backtest runner."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestBatchBacktestRunner:
    """Tests for BatchBacktestRunner class."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create mock Supabase client."""
        mock = MagicMock()
        mock.select = AsyncMock(return_value=[])
        mock.insert = AsyncMock(return_value=None)
        mock.update = AsyncMock(return_value=None)
        mock.upsert = AsyncMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_scenario(self) -> MagicMock:
        """Create a mock scenario."""
        from walltrack.core.backtest.parameters import BacktestParameters

        mock = MagicMock()
        mock.id = uuid4()
        mock.name = "Test Scenario"
        mock.to_backtest_params = MagicMock(
            return_value=BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
            )
        )
        return mock


class TestStartBatch(TestBatchBacktestRunner):
    """Tests for start_batch method."""

    async def test_start_batch_creates_batch(
        self,
        mock_supabase: MagicMock,
        mock_scenario: MagicMock,
    ) -> None:
        """Test starting a batch creates a batch run."""
        mock_scenario_service = MagicMock()
        mock_scenario_service.get_scenario = AsyncMock(return_value=mock_scenario)

        with (
            patch(
                "walltrack.core.backtest.batch_runner.get_supabase_client",
                return_value=mock_supabase,
            ),
            patch(
                "walltrack.core.backtest.batch_runner.get_scenario_service",
                return_value=mock_scenario_service,
            ),
        ):
            from walltrack.core.backtest.batch import BatchStatus
            from walltrack.core.backtest.batch_runner import BatchBacktestRunner

            runner = BatchBacktestRunner(max_workers=2)

            batch = await runner.start_batch(
                name="Test Batch",
                scenario_ids=[mock_scenario.id],
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 6, 30, tzinfo=UTC),
            )

            assert batch.name == "Test Batch"
            assert batch.status == BatchStatus.RUNNING
            assert len(batch.executions) == 1
            mock_supabase.insert.assert_called_once()


class TestCancelBatch(TestBatchBacktestRunner):
    """Tests for cancel_batch method."""

    async def test_cancel_sets_flag(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test cancelling batch sets cancel flag."""
        with patch(
            "walltrack.core.backtest.batch_runner.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.batch import BatchRun, BatchStatus
            from walltrack.core.backtest.batch_runner import BatchBacktestRunner

            runner = BatchBacktestRunner()

            # Simulate active batch
            batch_id = uuid4()
            batch = BatchRun(
                id=batch_id,
                name="Test",
                scenario_ids=[uuid4()],
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 6, 30, tzinfo=UTC),
                status=BatchStatus.RUNNING,
            )
            runner._active_batches[batch_id] = batch
            runner._cancel_flags[batch_id] = False

            result = await runner.cancel_batch(batch_id)

            assert result is True
            assert runner._cancel_flags[batch_id] is True

    async def test_cancel_nonexistent_returns_false(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test cancelling nonexistent batch returns False."""
        with patch(
            "walltrack.core.backtest.batch_runner.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.batch_runner import BatchBacktestRunner

            runner = BatchBacktestRunner()

            result = await runner.cancel_batch(uuid4())

            assert result is False


class TestGetProgress(TestBatchBacktestRunner):
    """Tests for get_progress method."""

    def test_get_progress_active_batch(self) -> None:
        """Test getting progress for active batch."""
        from walltrack.core.backtest.batch import BatchRun, BatchStatus
        from walltrack.core.backtest.batch_runner import BatchBacktestRunner

        runner = BatchBacktestRunner()

        batch_id = uuid4()
        batch = BatchRun(
            id=batch_id,
            name="Test",
            scenario_ids=[uuid4(), uuid4()],
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
        )
        runner._active_batches[batch_id] = batch

        progress = runner.get_progress(batch_id)

        assert progress is not None
        assert progress.total_scenarios == 2

    def test_get_progress_nonexistent(self) -> None:
        """Test getting progress for nonexistent batch."""
        from walltrack.core.backtest.batch_runner import BatchBacktestRunner

        runner = BatchBacktestRunner()

        progress = runner.get_progress(uuid4())

        assert progress is None


class TestGetBatch(TestBatchBacktestRunner):
    """Tests for get_batch method."""

    async def test_get_active_batch(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test getting an active batch."""
        with patch(
            "walltrack.core.backtest.batch_runner.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.batch import BatchRun
            from walltrack.core.backtest.batch_runner import BatchBacktestRunner

            runner = BatchBacktestRunner()

            batch_id = uuid4()
            batch = BatchRun(
                id=batch_id,
                name="Active Batch",
                scenario_ids=[uuid4()],
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 6, 30, tzinfo=UTC),
            )
            runner._active_batches[batch_id] = batch

            result = await runner.get_batch(batch_id)

            assert result is not None
            assert result.name == "Active Batch"

    async def test_get_nonexistent_batch(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test getting nonexistent batch returns None."""
        with patch(
            "walltrack.core.backtest.batch_runner.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.batch_runner import BatchBacktestRunner

            runner = BatchBacktestRunner()

            result = await runner.get_batch(uuid4())

            assert result is None


class TestListBatches(TestBatchBacktestRunner):
    """Tests for list_batches method."""

    async def test_list_returns_batches(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test listing batches."""
        batch_id = uuid4()
        mock_supabase.select = AsyncMock(
            side_effect=[
                # First call for list
                [
                    {
                        "id": str(batch_id),
                        "name": "Listed Batch",
                        "scenario_ids": [],
                        "start_date": "2024-01-01T00:00:00+00:00",
                        "end_date": "2024-06-30T00:00:00+00:00",
                        "status": "completed",
                        "started_at": "2024-01-01T00:00:00+00:00",
                        "completed_at": "2024-01-01T01:00:00+00:00",
                        "created_at": "2024-01-01T00:00:00+00:00",
                    }
                ],
                # Second call for get_batch
                [
                    {
                        "id": str(batch_id),
                        "name": "Listed Batch",
                        "scenario_ids": [],
                        "start_date": "2024-01-01T00:00:00+00:00",
                        "end_date": "2024-06-30T00:00:00+00:00",
                        "status": "completed",
                        "started_at": "2024-01-01T00:00:00+00:00",
                        "completed_at": "2024-01-01T01:00:00+00:00",
                        "created_at": "2024-01-01T00:00:00+00:00",
                    }
                ],
                # Third call for results
                [],
            ]
        )

        with patch(
            "walltrack.core.backtest.batch_runner.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.batch_runner import BatchBacktestRunner

            runner = BatchBacktestRunner()

            batches = await runner.list_batches(limit=10)

            assert len(batches) == 1
            assert batches[0].name == "Listed Batch"


class TestGetBatchRunner:
    """Tests for singleton accessor."""

    async def test_returns_singleton(self) -> None:
        """Test get_batch_runner returns singleton."""
        from walltrack.core.backtest.batch_runner import get_batch_runner

        runner1 = await get_batch_runner()
        runner2 = await get_batch_runner()

        assert runner1 is runner2
