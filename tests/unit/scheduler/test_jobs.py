"""Unit tests for scheduler jobs module.

Tests the surveillance job and scheduling functions.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestRefreshTokensJob:
    """Tests for refresh_tokens_job function."""

    @pytest.mark.asyncio
    async def test_refresh_tokens_job_calls_discovery_service(self, mocker):
        """Job should call TokenDiscoveryService.run_discovery()."""
        # Mock the discovery service
        mock_result = MagicMock(
            tokens_found=5,
            new_tokens=2,
            updated_tokens=3,
        )
        mock_service = MagicMock()
        mock_service.run_discovery = AsyncMock(return_value=mock_result)

        # Mock clients
        mock_supabase = AsyncMock()
        mock_dex = MagicMock()
        mock_dex.close = AsyncMock()

        # Patch at the module level where they're imported
        mocker.patch(
            "walltrack.data.supabase.client.get_supabase_client",
            return_value=mock_supabase,
        )
        mocker.patch(
            "walltrack.services.dexscreener.client.DexScreenerClient",
            return_value=mock_dex,
        )
        mocker.patch(
            "walltrack.core.discovery.token_discovery.TokenDiscoveryService",
            return_value=mock_service,
        )

        from walltrack.scheduler.jobs import refresh_tokens_job

        await refresh_tokens_job()

        # Verify discovery was called
        mock_service.run_discovery.assert_called_once()
        # Verify client was closed
        mock_dex.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_tokens_job_handles_errors(self, mocker):
        """Job should handle errors gracefully without raising."""
        mocker.patch(
            "walltrack.data.supabase.client.get_supabase_client",
            side_effect=Exception("DB connection failed"),
        )

        from walltrack.scheduler.jobs import refresh_tokens_job

        # Should not raise
        await refresh_tokens_job()


class TestScheduleSurveillanceJob:
    """Tests for schedule_surveillance_job function."""

    def test_schedule_surveillance_job_validates_interval(self):
        """Should raise ValueError for invalid intervals."""
        from walltrack.scheduler.jobs import schedule_surveillance_job

        with pytest.raises(ValueError, match="Invalid interval"):
            schedule_surveillance_job(interval_hours=3)

        with pytest.raises(ValueError, match="Invalid interval"):
            schedule_surveillance_job(interval_hours=0)

        with pytest.raises(ValueError, match="Invalid interval"):
            schedule_surveillance_job(interval_hours=10)

    def test_schedule_surveillance_job_adds_job(self, mocker):
        """Should add job with correct interval."""
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import JOB_ID_SURVEILLANCE, schedule_surveillance_job

        schedule_surveillance_job(interval_hours=2)

        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args.kwargs
        assert call_kwargs["id"] == JOB_ID_SURVEILLANCE

    def test_schedule_surveillance_job_replaces_existing(self, mocker):
        """Should remove existing job before adding new one."""
        mock_job = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = mock_job

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import JOB_ID_SURVEILLANCE, schedule_surveillance_job

        schedule_surveillance_job(interval_hours=4)

        # Should remove existing job first
        mock_scheduler.remove_job.assert_called_once_with(JOB_ID_SURVEILLANCE)
        # Then add new job
        mock_scheduler.add_job.assert_called_once()


class TestUnscheduleSurveillanceJob:
    """Tests for unschedule_surveillance_job function."""

    def test_unschedule_surveillance_job_removes_job(self, mocker):
        """Should remove the surveillance job."""
        mock_job = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = mock_job

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import JOB_ID_SURVEILLANCE, unschedule_surveillance_job

        unschedule_surveillance_job()

        mock_scheduler.remove_job.assert_called_once_with(JOB_ID_SURVEILLANCE)

    def test_unschedule_surveillance_job_no_op_when_not_scheduled(self, mocker):
        """Should do nothing if job not scheduled."""
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import unschedule_surveillance_job

        # Should not raise
        unschedule_surveillance_job()
        mock_scheduler.remove_job.assert_not_called()


class TestGetNextRunTime:
    """Tests for get_next_run_time function."""

    def test_get_next_run_time_returns_iso_string(self, mocker):
        """Should return ISO format datetime string."""
        mock_job = MagicMock()
        mock_job.next_run_time = datetime(2025, 12, 29, 14, 0, 0, tzinfo=UTC)

        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = mock_job

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import get_next_run_time

        result = get_next_run_time()

        assert result is not None
        assert "2025-12-29" in result

    def test_get_next_run_time_returns_none_when_not_scheduled(self, mocker):
        """Should return None if no job scheduled."""
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import get_next_run_time

        result = get_next_run_time()

        assert result is None
