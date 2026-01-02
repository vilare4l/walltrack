"""Integration tests for workers status monitoring (Story 3.5.6).

Tests that Status Bar can correctly fetch and display workers status
from the global worker instances in main.py.
"""

from datetime import UTC, datetime

import pytest

from walltrack.ui.components.status_bar import (
    format_worker_status,
    get_worker_health_icon,
    get_workers_status,
)


@pytest.mark.integration
def test_get_workers_status_when_workers_not_started():
    """Test get_workers_status() when workers haven't been started yet (Story 3.5.6).

    Scenario: Application just started, workers not yet initialized.
    Expected: Returns default states (not_implemented for Discovery, stopped for Profiling).
    """
    # Call get_workers_status (workers may not exist yet)
    status = get_workers_status()

    # Should return dict with 3 workers
    assert "discovery" in status
    assert "profiling" in status
    assert "decay" in status

    # Discovery worker may not exist yet (depends on 3.5.5 implementation)
    assert status["discovery"]["current_state"] in ("not_implemented", "stopped", "unknown")

    # Profiling worker should be stopped or unknown
    assert status["profiling"]["current_state"] in ("stopped", "unknown")

    # Decay scheduler (not implemented as scheduled job yet)
    assert status["decay"]["current_state"] == "not_implemented"


@pytest.mark.integration
def test_worker_health_icon_integration():
    """Test worker health icon logic with realistic status data (Story 3.5.6).

    Scenario: Worker has been running, last run was recent.
    Expected: Green icon for healthy worker.
    """
    # Simulate healthy worker status
    status = {
        "running": True,
        "last_run": datetime.now(UTC),
        "processed_count": 5,
        "error_count": 0,
        "current_state": "idle",
    }

    # Discovery worker polls every 120s
    icon = get_worker_health_icon(status, poll_interval_seconds=120)
    assert icon == "🟢"  # Recent run = green

    # Format should show time and count
    text = format_worker_status(status, "Discovery")
    assert "just now" in text or "0m ago" in text
    assert "(5)" in text


@pytest.mark.integration
def test_worker_degraded_state_integration():
    """Test worker in degraded state (errors in last run) (Story 3.5.6).

    Scenario: Worker ran but encountered errors.
    Expected: Red icon and error message.
    """
    status = {
        "running": True,
        "last_run": datetime.now(UTC),
        "processed_count": 3,
        "error_count": 2,
        "current_state": "idle",
    }

    # Should show red icon due to errors
    icon = get_worker_health_icon(status, poll_interval_seconds=60)
    assert icon == "🔴"


@pytest.mark.integration
def test_decay_scheduler_status_integration():
    """Test decay scheduler status formatting (Story 3.5.6).

    Scenario: Decay scheduler is not yet implemented as scheduled job.
    Expected: Shows "not_implemented" state.
    """
    # Import decay scheduler status helper
    from walltrack.scheduler.jobs import get_decay_scheduler_status

    # Get decay status
    status = get_decay_scheduler_status()

    # Currently not implemented (manual trigger only)
    assert status["running"] is False
    assert status["next_run"] is None
    assert status["current_state"] == "not_implemented"

    # Format for display
    text = format_worker_status(status, "Decay")
    assert text == "not scheduled"


@pytest.mark.integration
def test_status_bar_render_with_workers():
    """Test that render_status_html() includes workers status (Story 3.5.6).

    Scenario: Status bar is rendered for display.
    Expected: HTML includes Discovery Worker, Profiling Worker, and Decay sections.
    """
    from walltrack.ui.components.status_bar import render_status_html

    # Render status bar HTML
    html = render_status_html()

    # Should contain workers sections
    assert "Discovery Worker:" in html
    assert "Profiling Worker:" in html
    assert "Decay:" in html

    # Should contain health icons (at least one of each type possible)
    assert "🟢" in html or "🟡" in html or "🔴" in html
