"""Configuration management API routes.

Provides endpoints for:
- Risk configuration (legacy endpoints)
- Configuration lifecycle management (draft, activate, restore)
- Audit log queries
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

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
from walltrack.data.supabase.client import get_supabase_client
from walltrack.services.config.config_service import get_config_service

router = APIRouter(prefix="/config", tags=["config"])


# ============================================
# Response Models for Lifecycle Endpoints
# ============================================


class ConfigResponse(BaseModel):
    """Response for config endpoints."""

    id: str
    name: str
    status: str
    version: int
    data: dict
    created_at: datetime
    updated_at: datetime


class ConfigListResponse(BaseModel):
    """Response for listing configs."""

    configs: list[ConfigResponse]
    total: int


class ActivateResponse(BaseModel):
    """Response for activation."""

    status: str
    version: int
    previous_version: int
    message: str


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    id: int
    config_table: str
    config_key: str
    old_value: str | None
    new_value: str
    changed_by: str
    changed_at: datetime
    reason: str | None


class AuditLogResponse(BaseModel):
    """Response for audit log."""

    entries: list[AuditLogEntry]
    total: int


class CreateDraftRequest(BaseModel):
    """Request to create a draft."""

    name: str | None = None
    description: str | None = None


class UpdateDraftRequest(BaseModel):
    """Request to update draft values."""

    data: dict
    reason: str | None = None


class ActivateRequest(BaseModel):
    """Request to activate draft."""

    reason: str | None = None


# ============================================
# Dependency for Risk Config Service
# ============================================


async def get_service() -> RiskConfigService:
    """Dependency to get config service."""
    return await get_risk_config_service()


# ============================================
# Legacy Risk Config Endpoints
# ============================================


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


# ============================================
# Configuration Lifecycle Endpoints
# ============================================

VALID_CONFIG_TABLES = [
    "trading",
    "scoring",
    "discovery",
    "cluster",
    "risk",
    "exit",
    "api",
]


def _validate_table(table: str) -> None:
    """Validate table name."""
    if table not in VALID_CONFIG_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table. Must be one of: {VALID_CONFIG_TABLES}",
        )


def _extract_config_data(row: dict) -> dict:
    """Extract config data fields, excluding metadata."""
    metadata_fields = {
        "id",
        "name",
        "status",
        "version",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "description",
    }
    return {k: v for k, v in row.items() if k not in metadata_fields}


async def _log_audit(
    client,
    config_table: str,
    config_key: str,
    old_value: str | None,
    new_value: str,
    changed_by: str = "system",
    reason: str | None = None,
) -> None:
    """Log to config audit table."""
    await client.table("config_audit_log").insert(
        {
            "config_table": config_table,
            "config_key": config_key,
            "old_value": old_value,
            "new_value": new_value,
            "changed_by": changed_by,
            "reason": reason,
        }
    ).execute()


@router.get("/lifecycle/{table}", response_model=ConfigResponse)
async def get_active_config(table: str):
    """Get the active configuration for a table."""
    _validate_table(table)

    client = await get_supabase_client()

    result = (
        await client.table(f"{table}_config")
        .select("*")
        .eq("status", "active")
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="No active config found")

    return ConfigResponse(
        id=str(result.data["id"]),
        name=result.data["name"],
        status=result.data["status"],
        version=result.data["version"],
        data=_extract_config_data(result.data),
        created_at=result.data["created_at"],
        updated_at=result.data["updated_at"],
    )


@router.get("/lifecycle/{table}/all", response_model=ConfigListResponse)
async def get_all_configs(
    table: str,
    status: str | None = Query(None, description="Filter by status"),
):
    """Get all configurations for a table."""
    _validate_table(table)

    client = await get_supabase_client()

    query = client.table(f"{table}_config").select("*")

    if status:
        query = query.eq("status", status)

    result = await query.order("version", desc=True).execute()

    configs = [
        ConfigResponse(
            id=str(row["id"]),
            name=row["name"],
            status=row["status"],
            version=row["version"],
            data=_extract_config_data(row),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in result.data
    ]

    return ConfigListResponse(configs=configs, total=len(configs))


@router.post("/lifecycle/{table}/draft", response_model=ConfigResponse)
async def create_draft(
    table: str,
    request: CreateDraftRequest,
    updated_by: str = Query("user", description="Who is making the change"),
):
    """Create a new draft from the active configuration."""
    _validate_table(table)

    client = await get_supabase_client()

    # Get active config
    active_result = (
        await client.table(f"{table}_config")
        .select("*")
        .eq("status", "active")
        .single()
        .execute()
    )

    if not active_result.data:
        raise HTTPException(status_code=404, detail="No active config to clone")

    # Check if draft already exists
    existing_draft = (
        await client.table(f"{table}_config")
        .select("id")
        .eq("status", "draft")
        .execute()
    )

    if existing_draft.data:
        raise HTTPException(
            status_code=409, detail="Draft already exists. Update or delete it first."
        )

    # Create draft (copy active config values)
    active_data = active_result.data
    draft_data = _extract_config_data(active_data)

    draft_name = request.name or f"Draft from v{active_data['version']}"

    insert_data = {
        **draft_data,
        "name": draft_name,
        "status": "draft",
        "version": 1,
        "description": request.description
        or f"Draft based on {active_data['name']}",
        "created_by": updated_by,
        "updated_by": updated_by,
    }

    result = await client.table(f"{table}_config").insert(insert_data).execute()

    # Log to audit
    await _log_audit(
        client,
        table,
        "lifecycle",
        None,
        f"draft created from v{active_data['version']}",
        changed_by=updated_by,
        reason="Created draft from active config",
    )

    return ConfigResponse(
        id=str(result.data[0]["id"]),
        name=result.data[0]["name"],
        status="draft",
        version=1,
        data=draft_data,
        created_at=result.data[0]["created_at"],
        updated_at=result.data[0]["updated_at"],
    )


@router.patch("/lifecycle/{table}/draft", response_model=ConfigResponse)
async def update_draft(
    table: str,
    request: UpdateDraftRequest,
    updated_by: str = Query("user"),
):
    """Update the draft configuration."""
    _validate_table(table)

    client = await get_supabase_client()

    # Get existing draft
    draft_result = (
        await client.table(f"{table}_config")
        .select("*")
        .eq("status", "draft")
        .single()
        .execute()
    )

    if not draft_result.data:
        raise HTTPException(status_code=404, detail="No draft found")

    old_data = _extract_config_data(draft_result.data)

    # Merge updates
    update_data = {
        **request.data,
        "updated_by": updated_by,
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = (
        await client.table(f"{table}_config")
        .update(update_data)
        .eq("id", draft_result.data["id"])
        .execute()
    )

    # Log changes
    changed_fields = [k for k, v in request.data.items() if old_data.get(k) != v]

    await _log_audit(
        client,
        table,
        "draft_update",
        str(old_data),
        str(request.data),
        changed_by=updated_by,
        reason=request.reason or f"Updated fields: {', '.join(changed_fields)}",
    )

    return ConfigResponse(
        id=str(result.data[0]["id"]),
        name=result.data[0]["name"],
        status="draft",
        version=result.data[0]["version"],
        data=_extract_config_data(result.data[0]),
        created_at=result.data[0]["created_at"],
        updated_at=result.data[0]["updated_at"],
    )


@router.post("/lifecycle/{table}/activate", response_model=ActivateResponse)
async def activate_draft(
    table: str,
    request: ActivateRequest,
    updated_by: str = Query("user"),
):
    """Activate the draft configuration."""
    _validate_table(table)

    client = await get_supabase_client()

    # Get draft
    draft_result = (
        await client.table(f"{table}_config")
        .select("*")
        .eq("status", "draft")
        .single()
        .execute()
    )

    if not draft_result.data:
        raise HTTPException(status_code=404, detail="No draft to activate")

    # Get current active
    active_result = (
        await client.table(f"{table}_config")
        .select("id, version")
        .eq("status", "active")
        .single()
        .execute()
    )

    previous_version = active_result.data["version"] if active_result.data else 0

    # Archive current active
    if active_result.data:
        await (
            client.table(f"{table}_config")
            .update({"status": "archived", "updated_by": updated_by})
            .eq("id", active_result.data["id"])
            .execute()
        )

        await _log_audit(
            client,
            table,
            "status",
            "active",
            "archived",
            changed_by=updated_by,
            reason="Replaced by new active config",
        )

    # Activate draft
    new_version = previous_version + 1
    await (
        client.table(f"{table}_config")
        .update(
            {
                "status": "active",
                "version": new_version,
                "updated_by": updated_by,
            }
        )
        .eq("id", draft_result.data["id"])
        .execute()
    )

    await _log_audit(
        client,
        table,
        "status",
        "draft",
        "active",
        changed_by=updated_by,
        reason=request.reason or f"Draft activated as v{new_version}",
    )

    # Refresh config service cache
    config_service = await get_config_service()
    await config_service.refresh(table)

    return ActivateResponse(
        status="active",
        version=new_version,
        previous_version=previous_version,
        message="Configuration activated successfully",
    )


@router.post("/lifecycle/{table}/{config_id}/restore", response_model=ConfigResponse)
async def restore_archived(
    table: str,
    config_id: UUID,
    updated_by: str = Query("user"),
):
    """Restore an archived configuration as a new draft."""
    _validate_table(table)

    client = await get_supabase_client()

    # Get archived config
    archived_result = (
        await client.table(f"{table}_config")
        .select("*")
        .eq("id", str(config_id))
        .eq("status", "archived")
        .single()
        .execute()
    )

    if not archived_result.data:
        raise HTTPException(status_code=404, detail="Archived config not found")

    # Check for existing draft
    existing_draft = (
        await client.table(f"{table}_config")
        .select("id")
        .eq("status", "draft")
        .execute()
    )

    if existing_draft.data:
        raise HTTPException(
            status_code=409, detail="Draft already exists. Delete it first."
        )

    # Create new draft from archived
    archived_data = _extract_config_data(archived_result.data)

    insert_data = {
        **archived_data,
        "name": f"Restored from v{archived_result.data['version']}",
        "status": "draft",
        "version": 1,
        "description": f"Restored from archived config v{archived_result.data['version']}",
        "created_by": updated_by,
        "updated_by": updated_by,
    }

    result = await client.table(f"{table}_config").insert(insert_data).execute()

    await _log_audit(
        client,
        table,
        "restore",
        f"archived-v{archived_result.data['version']}",
        "draft",
        changed_by=updated_by,
        reason=f"Restored from archived config {config_id}",
    )

    return ConfigResponse(
        id=str(result.data[0]["id"]),
        name=result.data[0]["name"],
        status="draft",
        version=1,
        data=archived_data,
        created_at=result.data[0]["created_at"],
        updated_at=result.data[0]["updated_at"],
    )


@router.delete("/lifecycle/{table}/draft")
async def delete_draft(
    table: str,
    updated_by: str = Query("user"),
):
    """Delete the current draft configuration."""
    _validate_table(table)

    client = await get_supabase_client()

    # Get draft
    draft_result = (
        await client.table(f"{table}_config")
        .select("id, name, version")
        .eq("status", "draft")
        .single()
        .execute()
    )

    if not draft_result.data:
        raise HTTPException(status_code=404, detail="No draft to delete")

    # Delete draft
    await (
        client.table(f"{table}_config").delete().eq("id", draft_result.data["id"]).execute()
    )

    await _log_audit(
        client,
        table,
        "delete",
        f"draft-{draft_result.data['name']}",
        "deleted",
        changed_by=updated_by,
        reason="Draft deleted",
    )

    return {"message": "Draft deleted successfully"}


# ============================================
# Audit Log Endpoint
# ============================================


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    table: str | None = Query(None, description="Filter by config table"),
    from_date: datetime | None = Query(None, description="Start date filter"),
    to_date: datetime | None = Query(None, description="End date filter"),
    limit: int = Query(100, le=500, description="Max entries to return"),
):
    """Get configuration audit log."""
    client = await get_supabase_client()

    query = client.table("config_audit_log").select("*")

    if table:
        query = query.eq("config_table", table)
    if from_date:
        query = query.gte("changed_at", from_date.isoformat())
    if to_date:
        query = query.lte("changed_at", to_date.isoformat())

    result = await query.order("changed_at", desc=True).limit(limit).execute()

    entries = [
        AuditLogEntry(
            id=row["id"],
            config_table=row["config_table"],
            config_key=row["config_key"],
            old_value=row.get("old_value"),
            new_value=row["new_value"],
            changed_by=row["changed_by"],
            changed_at=row["changed_at"],
            reason=row.get("reason"),
        )
        for row in result.data
    ]

    return AuditLogResponse(entries=entries, total=len(entries))
