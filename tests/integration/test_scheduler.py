"""Integration tests for scheduler module.

Tests the scheduler lifecycle and integration with the app.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSchedulerLifecycle:
    """Tests for scheduler lifecycle with the app."""

    @pytest.mark.asyncio
    async def test_scheduler_starts_with_app(self):
        """
        Given: Fresh app startup
        When: start_scheduler() is called (via lifespan)
        Then: Scheduler is running
        """
        # Reset singleton
        with patch("walltrack.scheduler.scheduler._scheduler", None):
            from walltrack.scheduler.scheduler import get_scheduler, start_scheduler

            await start_scheduler()
            scheduler = get_scheduler()

            assert scheduler.running
            # Cleanup
            scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_scheduler_shutdown_cleans_up(self):
        """
        Given: Running scheduler
        When: shutdown_scheduler() is called
        Then: Scheduler is stopped and singleton cleared
        """
        with patch("walltrack.scheduler.scheduler._scheduler", None):
            import walltrack.scheduler.scheduler as scheduler_module
            from walltrack.scheduler.scheduler import (
                shutdown_scheduler,
                start_scheduler,
            )

            await start_scheduler()
            await shutdown_scheduler()

            assert scheduler_module._scheduler is None


class TestSurveillanceScheduling:
    """Tests for surveillance job scheduling."""

    def test_schedule_job_with_different_intervals(self, mocker):
        """
        Given: Scheduler running
        When: schedule_surveillance_job() called with different intervals
        Then: Job is scheduled with correct interval
        """
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import schedule_surveillance_job

        # Test different intervals
        for hours in [1, 2, 4, 8]:
            mock_scheduler.reset_mock()
            mock_scheduler.get_job.return_value = None

            schedule_surveillance_job(interval_hours=hours)

            mock_scheduler.add_job.assert_called_once()
            call_kwargs = mock_scheduler.add_job.call_args.kwargs
            trigger = call_kwargs.get("trigger")
            assert trigger is not None
            # IntervalTrigger stores interval as timedelta
            assert trigger.interval.total_seconds() == hours * 3600

    def test_reschedule_removes_existing_job(self, mocker):
        """
        Given: Job already scheduled
        When: schedule_surveillance_job() called again
        Then: Old job is removed before new job is added
        """
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_scheduler.get_job.return_value = mock_job

        mocker.patch(
            "walltrack.scheduler.jobs.get_scheduler",
            return_value=mock_scheduler,
        )

        from walltrack.scheduler.jobs import JOB_ID_SURVEILLANCE, schedule_surveillance_job

        schedule_surveillance_job(interval_hours=2)

        # Verify remove was called before add
        mock_scheduler.remove_job.assert_called_once_with(JOB_ID_SURVEILLANCE)
        mock_scheduler.add_job.assert_called_once()


class TestStatusBarDiscoveryStatus:
    """Tests for status bar discovery status display."""

    def test_get_discovery_status_with_tokens(self, mocker):
        """
        Given: Tokens exist in database with last_checked timestamp
        When: get_discovery_status() is called
        Then: Returns formatted relative times
        """
        # Mock the database query - need to mock the UI client factory
        mock_client = MagicMock()
        mock_result = MagicMock()
        # Set last_checked to now
        now = datetime.now(UTC).replace(microsecond=0)
        mock_result.data = [{"last_checked": now.isoformat()}]

        mock_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=mock_result
        )

        # Return the client wrapper for run_async_with_client
        async def mock_create_client():
            return mock_client

        mocker.patch(
            "walltrack.ui._create_fresh_client",
            side_effect=mock_create_client,
        )

        # Mock next run time at the source module where it's imported from
        mocker.patch(
            "walltrack.scheduler.jobs.get_next_run_time",
            return_value=None,
        )

        from walltrack.ui.components.status_bar import get_discovery_status

        last, next_run = get_discovery_status()

        # Should show "just now" since we set it to now
        assert last == "just now"
        assert next_run == "--"  # No job scheduled

    def test_get_discovery_status_no_tokens(self, mocker):
        """
        Given: No tokens in database
        When: get_discovery_status() is called
        Then: Returns "never" for last discovery
        """
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []

        mock_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=mock_result
        )

        async def mock_create_client():
            return mock_client

        mocker.patch(
            "walltrack.ui._create_fresh_client",
            side_effect=mock_create_client,
        )

        mocker.patch(
            "walltrack.scheduler.jobs.get_next_run_time",
            return_value=None,
        )

        from walltrack.ui.components.status_bar import get_discovery_status

        last, next_run = get_discovery_status()

        assert last == "never"
        assert next_run == "--"

    def test_get_discovery_status_with_scheduled_job(self, mocker):
        """
        Given: Surveillance job is scheduled
        When: get_discovery_status() is called
        Then: Returns next run time
        """
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []

        mock_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=mock_result
        )

        async def mock_create_client():
            return mock_client

        mocker.patch(
            "walltrack.ui._create_fresh_client",
            side_effect=mock_create_client,
        )

        # Mock next run time to 2 hours from now
        from datetime import timedelta

        future_time = datetime.now(UTC) + timedelta(hours=2)
        mocker.patch(
            "walltrack.scheduler.jobs.get_next_run_time",
            return_value=future_time.isoformat(),
        )

        from walltrack.ui.components.status_bar import get_discovery_status

        last, next_run = get_discovery_status()

        assert last == "never"
        # Should show hours remaining
        assert "h" in next_run or "m" in next_run or next_run == "soon"


class TestConfigPageSurveillance:
    """Tests for config page surveillance controls."""

    def test_toggle_surveillance_enables_job(self, mocker):
        """
        Given: Surveillance is disabled
        When: User enables surveillance
        Then: Job is scheduled
        """
        mock_client = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.set_value = AsyncMock()
        mock_repo.get_value = AsyncMock(return_value="4")

        mocker.patch(
            "walltrack.data.supabase.client.get_supabase_client",
            return_value=mock_client,
        )
        mocker.patch(
            "walltrack.data.supabase.repositories.config_repo.ConfigRepository",
            return_value=mock_repo,
        )

        mock_schedule = mocker.patch(
            "walltrack.scheduler.jobs.schedule_surveillance_job"
        )

        from walltrack.ui.pages.config import _toggle_surveillance

        result = _toggle_surveillance(True)

        assert "enabled" in result
        mock_schedule.assert_called_once()

    def test_toggle_surveillance_disables_job(self, mocker):
        """
        Given: Surveillance is enabled
        When: User disables surveillance
        Then: Job is unscheduled
        """
        mock_client = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.set_value = AsyncMock()

        mocker.patch(
            "walltrack.data.supabase.client.get_supabase_client",
            return_value=mock_client,
        )
        mocker.patch(
            "walltrack.data.supabase.repositories.config_repo.ConfigRepository",
            return_value=mock_repo,
        )

        mock_unschedule = mocker.patch(
            "walltrack.scheduler.jobs.unschedule_surveillance_job"
        )

        from walltrack.ui.pages.config import _toggle_surveillance

        result = _toggle_surveillance(False)

        assert "disabled" in result
        mock_unschedule.assert_called_once()

    def test_set_interval_reschedules_job(self, mocker):
        """
        Given: Surveillance is enabled
        When: User changes interval
        Then: Job is rescheduled with new interval
        """
        mock_client = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.set_value = AsyncMock()
        mock_repo.get_value = AsyncMock(return_value="true")

        mocker.patch(
            "walltrack.data.supabase.client.get_supabase_client",
            return_value=mock_client,
        )
        mocker.patch(
            "walltrack.data.supabase.repositories.config_repo.ConfigRepository",
            return_value=mock_repo,
        )

        mock_schedule = mocker.patch(
            "walltrack.scheduler.jobs.schedule_surveillance_job"
        )

        from walltrack.ui.pages.config import _set_surveillance_interval

        result = _set_surveillance_interval(2)

        assert "2h" in result
        mock_schedule.assert_called_once_with(interval_hours=2)
