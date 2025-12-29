"""Health check endpoint with database and scheduler status."""

from typing import Any

from fastapi import APIRouter

from walltrack.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint with database and scheduler status.

    Returns:
        dict with overall status, version, database health, and scheduler info.
    """
    settings = get_settings()

    # Get database health status
    supabase_health = await _get_supabase_health()
    neo4j_health = await _get_neo4j_health()

    # Get scheduler status
    scheduler_info = _get_scheduler_status()

    # Determine overall status
    all_healthy = supabase_health["healthy"] and neo4j_health["healthy"]
    overall_status = "ok" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "version": settings.app_version,
        "databases": {
            "supabase": supabase_health,
            "neo4j": neo4j_health,
        },
        "scheduler": scheduler_info,
    }


async def _get_supabase_health() -> dict[str, Any]:
    """Get Supabase health status."""
    # Import here to get the current singleton (intentional late import)
    import walltrack.data.supabase.client as supabase_module  # noqa: PLC0415

    client = supabase_module._supabase_client
    if client is None:
        return {"status": "disconnected", "healthy": False}
    return await client.health_check()


async def _get_neo4j_health() -> dict[str, Any]:
    """Get Neo4j health status."""
    # Import here to get the current singleton (intentional late import)
    import walltrack.data.neo4j.client as neo4j_module  # noqa: PLC0415

    client = neo4j_module._neo4j_client
    if client is None:
        return {"status": "disconnected", "healthy": False}
    return await client.health_check()


def _get_scheduler_status() -> dict[str, Any]:
    """Get scheduler status information.

    Returns:
        dict with scheduler enabled, running, and next_run info.
    """
    # Import here to avoid circular imports and get current state
    from walltrack.config import get_settings  # noqa: PLC0415
    from walltrack.scheduler.jobs import get_next_run_time  # noqa: PLC0415
    from walltrack.scheduler.scheduler import get_scheduler  # noqa: PLC0415

    settings = get_settings()

    # Check if scheduler is enabled via settings
    enabled = settings.discovery_scheduler_enabled

    # Get scheduler instance and check if running
    scheduler = get_scheduler()
    running = scheduler.running if scheduler else False

    # Get next run time
    next_run = get_next_run_time() if running else None

    return {
        "enabled": enabled,
        "running": running,
        "next_run": next_run,
    }
