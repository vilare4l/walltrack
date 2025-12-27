"""Event handlers for config page API interactions."""

import asyncio
from typing import Any

import httpx
import structlog

from walltrack.config.settings import get_settings

logger = structlog.get_logger(__name__)


def get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    return f"http://localhost:{settings.port}"


async def load_config(table: str) -> dict[str, Any]:
    """Load active configuration for a table.

    Args:
        table: Config table name (trading, scoring, discovery, etc.)

    Returns:
        Config data dict or empty dict on error
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{get_api_base_url()}/api/config/{table}"
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "config_load_failed",
                table=table,
                status=response.status_code
            )
    except Exception as e:
        logger.error("config_load_error", table=table, error=str(e))
    return {}


async def load_all_configs(table: str) -> list[dict[str, Any]]:
    """Load all configuration versions for a table.

    Args:
        table: Config table name

    Returns:
        List of config versions
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{get_api_base_url()}/api/config/{table}/all"
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("configs", [])
    except Exception as e:
        logger.error("config_load_all_error", table=table, error=str(e))
    return []


async def create_draft(table: str, name: str = "Draft") -> dict[str, Any] | None:
    """Create a draft from active config.

    Args:
        table: Config table name
        name: Optional name for the draft

    Returns:
        Created draft config or None on error
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{get_api_base_url()}/api/config/{table}/draft",
                json={"name": name}
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "draft_create_failed",
                table=table,
                status=response.status_code,
                detail=response.text
            )
    except Exception as e:
        logger.error("draft_create_error", table=table, error=str(e))
    return None


async def update_draft(
    table: str,
    data: dict[str, Any],
    reason: str | None = None
) -> dict[str, Any] | None:
    """Update draft with new values.

    Args:
        table: Config table name
        data: New config data
        reason: Optional reason for the change

    Returns:
        Updated draft config or None on error
    """
    try:
        payload = {"data": data}
        if reason:
            payload["reason"] = reason

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.patch(
                f"{get_api_base_url()}/api/config/{table}/draft",
                json=payload
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "draft_update_failed",
                table=table,
                status=response.status_code,
                detail=response.text
            )
    except Exception as e:
        logger.error("draft_update_error", table=table, error=str(e))
    return None


async def activate_draft(table: str, reason: str | None = None) -> dict[str, Any] | None:
    """Activate the current draft.

    Args:
        table: Config table name
        reason: Optional reason for activation

    Returns:
        Activation result or None on error
    """
    try:
        payload = {}
        if reason:
            payload["reason"] = reason

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{get_api_base_url()}/api/config/{table}/activate",
                json=payload
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "draft_activate_failed",
                table=table,
                status=response.status_code,
                detail=response.text
            )
    except Exception as e:
        logger.error("draft_activate_error", table=table, error=str(e))
    return None


async def delete_draft(table: str) -> bool:
    """Delete/discard the current draft.

    Args:
        table: Config table name

    Returns:
        True if deleted successfully
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{get_api_base_url()}/api/config/{table}/draft"
            )
            if response.status_code == 200:
                return True
            logger.warning(
                "draft_delete_failed",
                table=table,
                status=response.status_code
            )
    except Exception as e:
        logger.error("draft_delete_error", table=table, error=str(e))
    return False


async def restore_archived(table: str, version: int) -> dict[str, Any] | None:
    """Restore an archived config version.

    Args:
        table: Config table name
        version: Version number to restore

    Returns:
        Restored config as draft or None on error
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{get_api_base_url()}/api/config/{table}/restore/{version}"
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(
                "config_restore_failed",
                table=table,
                version=version,
                status=response.status_code
            )
    except Exception as e:
        logger.error("config_restore_error", table=table, error=str(e))
    return None


async def get_audit_log(
    table: str,
    limit: int = 50,
    offset: int = 0
) -> list[dict[str, Any]]:
    """Get audit log for a config table.

    Args:
        table: Config table name
        limit: Max entries to return
        offset: Pagination offset

    Returns:
        List of audit log entries
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{get_api_base_url()}/api/config/{table}/audit",
                params={"limit": limit, "offset": offset}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("entries", [])
    except Exception as e:
        logger.error("audit_log_error", table=table, error=str(e))
    return []


# Synchronous wrappers for Gradio event handlers
def load_config_sync(table: str) -> dict[str, Any]:
    """Synchronous wrapper for load_config."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(load_config(table))


def create_draft_sync(table: str, name: str = "Draft") -> dict[str, Any] | None:
    """Synchronous wrapper for create_draft."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(create_draft(table, name))


def update_draft_sync(
    table: str,
    data: dict[str, Any],
    reason: str | None = None
) -> dict[str, Any] | None:
    """Synchronous wrapper for update_draft."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(update_draft(table, data, reason))


def activate_draft_sync(table: str, reason: str | None = None) -> dict[str, Any] | None:
    """Synchronous wrapper for activate_draft."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(activate_draft(table, reason))


def delete_draft_sync(table: str) -> bool:
    """Synchronous wrapper for delete_draft."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(delete_draft(table))
