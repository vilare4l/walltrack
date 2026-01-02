"""Unit tests for Status Bar workers status monitoring (Story 3.5.6)."""

from datetime import UTC, datetime, timedelta

import pytest

from walltrack.ui.components.status_bar import (
    format_worker_status,
    get_worker_health_icon,
)


class TestGetWorkerHealthIcon:
    """Test get_worker_health_icon() function (Story 3.5.6)."""

    def test_red_icon_for_stopped_state(self):
        """Red icon when worker is stopped."""
        status = {"current_state": "stopped"}
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🔴"

    def test_red_icon_for_error_state(self):
        """Red icon when worker is in error state."""
        status = {"current_state": "error"}
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🔴"

    def test_red_icon_for_unknown_state(self):
        """Red icon when worker state is unknown."""
        status = {"current_state": "unknown"}
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🔴"

    def test_red_icon_for_not_implemented_state(self):
        """Red icon when worker is not implemented."""
        status = {"current_state": "not_implemented"}
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🔴"

    def test_red_icon_when_has_errors(self):
        """Red icon when worker has errors in last run."""
        status = {
            "current_state": "idle",
            "error_count": 3,
            "last_run": datetime.now(UTC),
        }
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🔴"

    def test_green_icon_for_recent_run(self):
        """Green icon when last run is within 2× poll interval."""
        # Last run 90 seconds ago (< 2× 60s)
        last_run = datetime.now(UTC) - timedelta(seconds=90)
        status = {
            "current_state": "idle",
            "error_count": 0,
            "last_run": last_run,
        }
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🟢"

    def test_yellow_icon_for_stale_run(self):
        """Yellow icon when last run is between 2× and 5× poll interval."""
        # Last run 200 seconds ago (> 2× 60s, < 5× 60s)
        last_run = datetime.now(UTC) - timedelta(seconds=200)
        status = {
            "current_state": "idle",
            "error_count": 0,
            "last_run": last_run,
        }
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🟡"

    def test_red_icon_for_very_stale_run(self):
        """Red icon when last run is > 5× poll interval (likely crashed)."""
        # Last run 400 seconds ago (> 5× 60s)
        last_run = datetime.now(UTC) - timedelta(seconds=400)
        status = {
            "current_state": "idle",
            "error_count": 0,
            "last_run": last_run,
        }
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🔴"

    def test_yellow_icon_for_no_last_run(self):
        """Yellow icon when worker has no last_run yet (starting or idle)."""
        status = {
            "current_state": "idle",
            "error_count": 0,
            "last_run": None,
        }
        icon = get_worker_health_icon(status, poll_interval_seconds=60)
        assert icon == "🟡"


class TestFormatWorkerStatus:
    """Test format_worker_status() function (Story 3.5.6)."""

    def test_stopped_state(self):
        """Format stopped state."""
        status = {"current_state": "stopped"}
        text = format_worker_status(status, "Discovery")
        assert text == "stopped"

    def test_not_implemented_state(self):
        """Format not_implemented state."""
        status = {"current_state": "not_implemented"}
        text = format_worker_status(status, "Discovery")
        assert text == "n/a"

    def test_error_state(self):
        """Format error state with error count."""
        status = {"current_state": "error", "error_count": 3}
        text = format_worker_status(status, "Discovery")
        assert text == "error (3 failures)"

    def test_unknown_state(self):
        """Format unknown state."""
        status = {"current_state": "unknown"}
        text = format_worker_status(status, "Discovery")
        assert text == "unavailable"

    def test_processing_state(self):
        """Format processing state."""
        status = {"current_state": "processing"}
        text = format_worker_status(status, "Discovery")
        assert text == "running..."

    def test_decay_worker_next_run(self):
        """Format Decay worker with next_run time."""
        # Next run in 3 hours
        next_run = datetime.now(UTC) + timedelta(hours=3)
        status = {
            "current_state": "scheduled",
            "next_run": next_run,
        }
        text = format_worker_status(status, "Decay")
        assert text == "next 3h"

    def test_decay_worker_next_run_minutes(self):
        """Format Decay worker with next_run in minutes."""
        # Next run in 45 minutes
        next_run = datetime.now(UTC) + timedelta(minutes=45)
        status = {
            "current_state": "scheduled",
            "next_run": next_run,
        }
        text = format_worker_status(status, "Decay")
        assert text == "next 45m"

    def test_decay_worker_no_next_run(self):
        """Format Decay worker without next_run."""
        status = {
            "current_state": "scheduled",
            "next_run": None,
        }
        text = format_worker_status(status, "Decay")
        assert text == "not scheduled"

    def test_discovery_worker_with_processed_count(self):
        """Format Discovery/Profiling worker with processed count."""
        # Last run 5 minutes ago, 12 items processed
        last_run = datetime.now(UTC) - timedelta(minutes=5)
        status = {
            "current_state": "idle",
            "last_run": last_run,
            "processed_count": 12,
        }
        text = format_worker_status(status, "Discovery")
        assert "5m ago" in text
        assert "(12)" in text

    def test_discovery_worker_idle_no_processed(self):
        """Format Discovery/Profiling worker with no processed items."""
        # Last run 2 minutes ago, 0 items processed
        last_run = datetime.now(UTC) - timedelta(minutes=2)
        status = {
            "current_state": "idle",
            "last_run": last_run,
            "processed_count": 0,
        }
        text = format_worker_status(status, "Discovery")
        assert "2m ago" in text
        assert "(idle)" in text

    def test_worker_no_last_run(self):
        """Format worker with no last_run yet."""
        status = {
            "current_state": "idle",
            "last_run": None,
        }
        text = format_worker_status(status, "Discovery")
        assert text == "idle"
