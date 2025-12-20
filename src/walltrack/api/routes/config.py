"""Risk configuration API routes."""

from fastapi import APIRouter, Depends, Header, Query

from walltrack.core.risk.config_models import (
    ConfigChangeLog,
    DashboardStatus,
    RiskConfig,
    RiskConfigUpdate,
    SystemHealth,
)
from walltrack.core.risk.config_service import (
    RiskConfigService,
    get_risk_config_service,
)

router = APIRouter(prefix="/config", tags=["config"])


async def get_service() -> RiskConfigService:
    """Dependency to get config service."""
    return await get_risk_config_service()


@router.get("/risk", response_model=RiskConfig)
async def get_risk_config(
    service: RiskConfigService = Depends(get_service),
) -> RiskConfig:
    """Get current risk configuration."""
    return await service.get_config()


@router.put("/risk", response_model=RiskConfig)
async def update_risk_config(
    update: RiskConfigUpdate,
    service: RiskConfigService = Depends(get_service),
    x_operator_id: str = Header(default="system"),
) -> RiskConfig:
    """
    Update risk configuration.

    All fields are optional - only provided fields will be updated.
    Changes are logged to the audit trail.
    """
    return await service.update_config(update, x_operator_id)


@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    service: RiskConfigService = Depends(get_service),
) -> SystemHealth:
    """
    Get system health status.

    Checks:
    - Database connection
    - Webhook endpoint status
    - Signal reception (warns if no signals in configured hours)
    """
    return await service.check_system_health()


@router.get("/dashboard", response_model=DashboardStatus)
async def get_dashboard_status(
    service: RiskConfigService = Depends(get_service),
) -> DashboardStatus:
    """
    Get complete dashboard status.

    Includes:
    - System status (running/paused)
    - System health
    - Risk configuration
    - Capital info (current, peak, drawdown)
    - Active alerts count
    - Open positions count
    """
    return await service.get_dashboard_status()


@router.get("/history", response_model=list[ConfigChangeLog])
async def get_config_history(
    service: RiskConfigService = Depends(get_service),
    field_name: str | None = Query(default=None, description="Filter by field name"),
    limit: int = Query(default=50, ge=1, le=100, description="Max records to return"),
) -> list[ConfigChangeLog]:
    """
    Get configuration change history.

    Returns audit trail of all configuration changes.
    Optionally filter by specific field.
    """
    return await service.get_config_history(field_name=field_name, limit=limit)
