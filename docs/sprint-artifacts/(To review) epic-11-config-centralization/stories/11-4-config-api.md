# Story 11.4: Config Management API Endpoints

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 5
- **Depends on**: Story 11-2 (ConfigService)

## User Story

**As a** system operator,
**I want** des endpoints REST pour gérer les configurations,
**So that** je peux lire, modifier et versionner les configs via API.

## Acceptance Criteria

### AC 1: Get Active Config
**Given** je call GET `/api/config/trading`
**When** la requête est traitée
**Then** je reçois la config active pour trading
**And** response: `{status: "active", version: 3, data: {...}}`

### AC 2: Get All Versions
**Given** je call GET `/api/config/trading/all`
**When** la requête est traitée
**Then** je reçois toutes les versions (default, active, drafts, archived)
**And** response: `[{status: "default", ...}, {status: "active", ...}]`

### AC 3: Create Draft
**Given** je call POST `/api/config/trading/draft`
**When** la requête est traitée
**Then** un draft est créé à partir de la config active
**And** response: `{status: "draft", id: "...", data: {...}}`

### AC 4: Update Draft
**Given** un draft existe
**When** je call PATCH `/api/config/trading/draft` avec des modifications
**Then** le draft est mis à jour
**And** response: `{status: "draft", version: 2, data: {...}}`

### AC 5: Activate Draft
**Given** un draft existe
**When** je call POST `/api/config/trading/activate`
**Then** le draft devient active
**And** l'ancien active devient archived
**And** response: `{status: "active", version: 4}`

### AC 6: Restore Archived
**Given** une config archived existe
**When** je call POST `/api/config/trading/{id}/restore`
**Then** un nouveau draft est créé avec les valeurs archived
**And** response: `{status: "draft", source: "archived-v2"}`

### AC 7: Audit Log
**Given** des modifications ont été faites
**When** je call GET `/api/config/audit`
**Then** je reçois l'historique des changements
**And** je peux filtrer par `table`, `from_date`, `to_date`

## Technical Specifications

### API Routes

**src/walltrack/api/routes/config.py:**
```python
"""Configuration management API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from walltrack.services.config.config_service import (
    ConfigService,
    get_config_service,
    TradingConfig,
    ScoringConfig,
)

router = APIRouter(prefix="/config", tags=["configuration"])


# ============================================
# Response Models
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
    config_id: str
    action: str
    changed_fields: Optional[list[str]]
    performed_by: str
    performed_at: datetime
    reason: Optional[str]


class AuditLogResponse(BaseModel):
    """Response for audit log."""
    entries: list[AuditLogEntry]
    total: int


# ============================================
# GET Endpoints
# ============================================

@router.get("/{table}", response_model=ConfigResponse)
async def get_active_config(
    table: str,
    config_service: ConfigService = Depends(get_config_service),
):
    """Get the active configuration for a table."""
    valid_tables = ["trading", "scoring", "discovery", "cluster", "risk", "exit", "api"]

    if table not in valid_tables:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table. Must be one of: {valid_tables}"
        )

    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    result = await client.table(f"{table}_config") \
        .select("*") \
        .eq("status", "active") \
        .single() \
        .execute()

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


@router.get("/{table}/all", response_model=ConfigListResponse)
async def get_all_configs(
    table: str,
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Get all configurations for a table."""
    from walltrack.data.supabase.client import get_supabase_client
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


# ============================================
# Draft Management
# ============================================

class CreateDraftRequest(BaseModel):
    """Request to create a draft."""
    name: Optional[str] = None
    description: Optional[str] = None


@router.post("/{table}/draft", response_model=ConfigResponse)
async def create_draft(
    table: str,
    request: CreateDraftRequest,
    updated_by: str = Query("user", description="Who is making the change"),
):
    """Create a new draft from the active configuration."""
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    # Get active config
    active_result = await client.table(f"{table}_config") \
        .select("*") \
        .eq("status", "active") \
        .single() \
        .execute()

    if not active_result.data:
        raise HTTPException(status_code=404, detail="No active config to clone")

    # Check if draft already exists
    existing_draft = await client.table(f"{table}_config") \
        .select("id") \
        .eq("status", "draft") \
        .execute()

    if existing_draft.data:
        raise HTTPException(
            status_code=409,
            detail="Draft already exists. Update or delete it first."
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
        "description": request.description or f"Draft based on {active_data['name']}",
        "created_by": updated_by,
        "updated_by": updated_by,
    }

    result = await client.table(f"{table}_config").insert(insert_data).execute()

    # Log to audit
    await _log_audit(
        client, table, result.data[0]["id"], "create",
        performed_by=updated_by,
        reason="Created draft from active config"
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


class UpdateDraftRequest(BaseModel):
    """Request to update draft values."""
    data: dict
    reason: Optional[str] = None


@router.patch("/{table}/draft", response_model=ConfigResponse)
async def update_draft(
    table: str,
    request: UpdateDraftRequest,
    updated_by: str = Query("user"),
):
    """Update the draft configuration."""
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    # Get existing draft
    draft_result = await client.table(f"{table}_config") \
        .select("*") \
        .eq("status", "draft") \
        .single() \
        .execute()

    if not draft_result.data:
        raise HTTPException(status_code=404, detail="No draft found")

    old_data = _extract_config_data(draft_result.data)

    # Merge updates
    update_data = {
        **request.data,
        "updated_by": updated_by,
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = await client.table(f"{table}_config") \
        .update(update_data) \
        .eq("id", draft_result.data["id"]) \
        .execute()

    # Log changes
    changed_fields = [k for k, v in request.data.items() if old_data.get(k) != v]

    await _log_audit(
        client, table, draft_result.data["id"], "update",
        old_values=old_data,
        new_values=request.data,
        changed_fields=changed_fields,
        performed_by=updated_by,
        reason=request.reason
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


# ============================================
# Activation
# ============================================

class ActivateRequest(BaseModel):
    """Request to activate draft."""
    reason: Optional[str] = None


@router.post("/{table}/activate", response_model=ActivateResponse)
async def activate_draft(
    table: str,
    request: ActivateRequest,
    updated_by: str = Query("user"),
):
    """Activate the draft configuration."""
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    # Get draft
    draft_result = await client.table(f"{table}_config") \
        .select("*") \
        .eq("status", "draft") \
        .single() \
        .execute()

    if not draft_result.data:
        raise HTTPException(status_code=404, detail="No draft to activate")

    # Get current active
    active_result = await client.table(f"{table}_config") \
        .select("id, version") \
        .eq("status", "active") \
        .single() \
        .execute()

    previous_version = active_result.data["version"] if active_result.data else 0

    # Archive current active
    if active_result.data:
        await client.table(f"{table}_config") \
            .update({"status": "archived", "updated_by": updated_by}) \
            .eq("id", active_result.data["id"]) \
            .execute()

        await _log_audit(
            client, table, active_result.data["id"], "archive",
            performed_by=updated_by,
            reason="Replaced by new active config"
        )

    # Activate draft
    new_version = previous_version + 1
    await client.table(f"{table}_config") \
        .update({
            "status": "active",
            "version": new_version,
            "updated_by": updated_by,
        }) \
        .eq("id", draft_result.data["id"]) \
        .execute()

    await _log_audit(
        client, table, draft_result.data["id"], "activate",
        performed_by=updated_by,
        reason=request.reason or "Draft activated"
    )

    # Refresh config service cache
    from walltrack.services.config.config_service import get_config_service
    config_service = await get_config_service()
    await config_service.refresh(table)

    return ActivateResponse(
        status="active",
        version=new_version,
        previous_version=previous_version,
        message="Configuration activated successfully",
    )


# ============================================
# Restore from Archive
# ============================================

@router.post("/{table}/{config_id}/restore", response_model=ConfigResponse)
async def restore_archived(
    table: str,
    config_id: UUID,
    updated_by: str = Query("user"),
):
    """Restore an archived configuration as a new draft."""
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    # Get archived config
    archived_result = await client.table(f"{table}_config") \
        .select("*") \
        .eq("id", str(config_id)) \
        .eq("status", "archived") \
        .single() \
        .execute()

    if not archived_result.data:
        raise HTTPException(status_code=404, detail="Archived config not found")

    # Check for existing draft
    existing_draft = await client.table(f"{table}_config") \
        .select("id") \
        .eq("status", "draft") \
        .execute()

    if existing_draft.data:
        raise HTTPException(
            status_code=409,
            detail="Draft already exists. Delete it first."
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
        client, table, result.data[0]["id"], "restore",
        performed_by=updated_by,
        reason=f"Restored from archived config {config_id}"
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


# ============================================
# Audit Log
# ============================================

@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    table: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=500),
):
    """Get configuration audit log."""
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    query = client.table("config_audit_log").select("*")

    if table:
        query = query.eq("config_table", table)
    if from_date:
        query = query.gte("performed_at", from_date.isoformat())
    if to_date:
        query = query.lte("performed_at", to_date.isoformat())

    result = await query.order("performed_at", desc=True).limit(limit).execute()

    entries = [
        AuditLogEntry(
            id=row["id"],
            config_table=row["config_table"],
            config_id=str(row["config_id"]),
            action=row["action"],
            changed_fields=row.get("changed_fields"),
            performed_by=row["performed_by"],
            performed_at=row["performed_at"],
            reason=row.get("reason"),
        )
        for row in result.data
    ]

    return AuditLogResponse(entries=entries, total=len(entries))


# ============================================
# Helper Functions
# ============================================

def _extract_config_data(row: dict) -> dict:
    """Extract config data fields, excluding metadata."""
    metadata_fields = {
        "id", "name", "status", "version",
        "created_at", "updated_at", "created_by", "updated_by",
        "description"
    }
    return {k: v for k, v in row.items() if k not in metadata_fields}


async def _log_audit(
    client,
    config_table: str,
    config_id: str,
    action: str,
    old_values: dict = None,
    new_values: dict = None,
    changed_fields: list = None,
    performed_by: str = "system",
    reason: str = None,
):
    """Log to config audit table."""
    await client.table("config_audit_log").insert({
        "config_table": config_table,
        "config_id": config_id,
        "action": action,
        "old_values": old_values,
        "new_values": new_values,
        "changed_fields": changed_fields,
        "performed_by": performed_by,
        "reason": reason,
    }).execute()
```

## Implementation Tasks

- [x] Create response models
- [x] Implement GET /{table} endpoint
- [x] Implement GET /{table}/all endpoint
- [x] Implement POST /{table}/draft endpoint
- [x] Implement PATCH /{table}/draft endpoint
- [x] Implement POST /{table}/activate endpoint
- [x] Implement POST /{table}/{id}/restore endpoint
- [x] Implement GET /audit endpoint
- [x] Add audit logging helper
- [x] Wire router to FastAPI app
- [x] Write API tests

## Definition of Done

- [x] All 7 endpoints implemented
- [x] Proper HTTP status codes
- [x] Audit logging on all mutations
- [x] Cache refresh on activate
- [x] Input validation
- [x] Full test coverage

## File List

### New Files
- `src/walltrack/api/routes/config.py` - Config API routes
- `tests/api/test_config_endpoints.py` - API tests

### Modified Files
- `src/walltrack/api/main.py` - Register router
