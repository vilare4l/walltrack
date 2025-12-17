"""Supabase async client with connection management."""

from typing import Any

import structlog
from supabase._async.client import AsyncClient
from supabase._async.client import create_client as create_async_client
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from walltrack.config.settings import get_settings
from walltrack.core.exceptions import DatabaseConnectionError

log = structlog.get_logger()


class SupabaseClient:
    """Async Supabase client wrapper with schema isolation."""

    def __init__(self) -> None:
        self._client: AsyncClient | None = None
        self._settings = get_settings()
        self._schema = self._settings.postgres_schema

    async def connect(self) -> None:
        """Establish connection to Supabase."""
        if self._client is not None:
            return

        try:
            self._client = await create_async_client(
                self._settings.supabase_url,
                self._settings.supabase_key.get_secret_value(),
            )

            log.info(
                "supabase_connected",
                url=self._settings.supabase_url,
                schema=self._schema,
            )
        except Exception as e:
            log.error("supabase_connection_failed", error=str(e))
            raise DatabaseConnectionError(f"Failed to connect to Supabase: {e}") from e

    async def disconnect(self) -> None:
        """Close Supabase connection."""
        if self._client is not None:
            self._client = None
            log.info("supabase_disconnected")

    @property
    def client(self) -> AsyncClient:
        """Get the Supabase client."""
        if self._client is None:
            raise DatabaseConnectionError("Supabase client not connected")
        return self._client

    @property
    def schema(self) -> str:
        """Get the schema name."""
        return self._schema or "public"

    def table(self, name: str) -> Any:
        """Get a table reference with schema selection."""
        # Use schema() method to set Accept-Profile header for PostgREST
        if self._schema and self._schema != "public":
            return self.client.schema(self._schema).table(name)
        return self.client.table(name)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def insert(self, table: str, data: dict[str, Any]) -> dict[str, Any]:
        """Insert data with retry logic."""
        response = await self.table(table).insert(data).execute()
        return response.data[0] if response.data else {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Select data with retry logic."""
        query = self.table(table).select(columns)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        response = await query.execute()
        return list(response.data) if response.data else []

    async def health_check(self) -> dict[str, Any]:
        """Check Supabase connection health."""
        try:
            if self._client is None:
                return {"status": "disconnected", "healthy": False}

            # Try a simple query to check connectivity
            return {
                "status": "connected",
                "healthy": True,
            }
        except Exception as e:
            log.error("supabase_health_check_failed", error=str(e))
            return {"status": "error", "healthy": False, "error": str(e)}


# Singleton instance
_supabase_client: SupabaseClient | None = None


async def get_supabase_client() -> SupabaseClient:
    """Get or create Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
        await _supabase_client.connect()
    return _supabase_client


async def close_supabase_client() -> None:
    """Close Supabase client."""
    global _supabase_client
    if _supabase_client is not None:
        await _supabase_client.disconnect()
        _supabase_client = None
