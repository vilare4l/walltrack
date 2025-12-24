"""Health check endpoints."""

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter

from walltrack.core.simulation.context import get_execution_mode
from walltrack.data.neo4j.client import get_neo4j_client
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Basic health check."""
    mode = get_execution_mode()
    return {
        "status": "healthy",
        "execution_mode": mode.value,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Detailed health check including database status."""
    mode = get_execution_mode()
    neo4j_client = await get_neo4j_client()
    supabase_client = await get_supabase_client()

    neo4j_health = await neo4j_client.health_check()
    supabase_health = await supabase_client.health_check()

    overall_healthy = neo4j_health["healthy"] and supabase_health["healthy"]

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "execution_mode": mode.value,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "neo4j": neo4j_health,
            "supabase": supabase_health,
        },
    }
