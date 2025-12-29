"""Unit tests for scheduler module.

Tests the APScheduler singleton pattern, startup, and shutdown.
"""

from unittest.mock import patch

import pytest


class TestSchedulerSingleton:
    """Tests for scheduler singleton pattern."""

    def test_get_scheduler_returns_instance(self):
        """Get scheduler should return an AsyncIOScheduler instance."""
        from walltrack.scheduler.scheduler import get_scheduler

        scheduler = get_scheduler()
        assert scheduler is not None

    def test_get_scheduler_singleton(self):
        """Scheduler should be a singleton - same instance returned."""
        from walltrack.scheduler.scheduler import get_scheduler

        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2


class TestSchedulerLifecycle:
    """Tests for scheduler start/shutdown."""

    @pytest.mark.asyncio
    async def test_start_scheduler_starts_scheduler(self):
        """Start scheduler should start the scheduler."""
        # Reset singleton for clean test
        with patch("walltrack.scheduler.scheduler._scheduler", None):
            from walltrack.scheduler.scheduler import get_scheduler, start_scheduler

            await start_scheduler()
            scheduler = get_scheduler()
            assert scheduler.running
            # Cleanup
            scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_start_scheduler_idempotent(self):
        """Start scheduler should be safe to call multiple times."""
        with patch("walltrack.scheduler.scheduler._scheduler", None):
            from walltrack.scheduler.scheduler import get_scheduler, start_scheduler

            await start_scheduler()
            await start_scheduler()  # Should not raise
            scheduler = get_scheduler()
            assert scheduler.running
            # Cleanup
            scheduler.shutdown(wait=False)

    @pytest.mark.asyncio
    async def test_shutdown_scheduler_stops_scheduler(self):
        """Shutdown scheduler should stop and clear the scheduler."""
        with patch("walltrack.scheduler.scheduler._scheduler", None):
            import walltrack.scheduler.scheduler as scheduler_module
            from walltrack.scheduler.scheduler import (
                shutdown_scheduler,
                start_scheduler,
            )

            await start_scheduler()
            await shutdown_scheduler()

            # Singleton should be cleared
            assert scheduler_module._scheduler is None

    @pytest.mark.asyncio
    async def test_shutdown_scheduler_when_not_running(self):
        """Shutdown should be safe when scheduler not running."""
        with patch("walltrack.scheduler.scheduler._scheduler", None):
            from walltrack.scheduler.scheduler import shutdown_scheduler

            # Should not raise
            await shutdown_scheduler()
