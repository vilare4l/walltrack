"""Supabase async client with connection management."""

from typing import Any

import structlog
from supabase._async.client import AsyncClient
from supabase._async.client import create_client as create_async_client
from supabase.lib.client_options import AsyncClientOptions
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
    """Async Supabase client wrapper.

    Provides connection management, health checks, and basic CRUD operations
    with retry logic for resilience.
    """

    def __init__(self) -> None:
        """Initialize client with settings."""
        self._client: AsyncClient | None = None
        self._settings = get_settings()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def connect(self) -> None:
        """Establish connection to Supabase.

        Raises:
            DatabaseConnectionError: If connection fails after retries.
        """
        if self._client is not None:
            return

        try:
            options = AsyncClientOptions(schema=self._settings.postgres_schema)
            self._client = await create_async_client(
                self._settings.supabase_url,
                self._settings.supabase_key.get_secret_value(),
                options=options,
            )

            log.info(
                "supabase_connected",
                url=self._settings.supabase_url,
                schema=self._settings.postgres_schema,
            )
        except Exception as e:
            log.error("supabase_connection_failed", error=str(e))
            raise DatabaseConnectionError(f"Supabase: {e}") from e

    async def disconnect(self) -> None:
        """Close Supabase connection."""
        if self._client is not None:
            self._client = None
            log.info("supabase_disconnected")

    @property
    def client(self) -> AsyncClient:
        """Get the underlying Supabase client.

        Raises:
            DatabaseConnectionError: If not connected.
        """
        if self._client is None:
            raise DatabaseConnectionError("Supabase: Client not connected")
        return self._client

    async def health_check(self) -> dict[str, Any]:
        """Check Supabase connection health.

        Performs an actual connection verification by attempting
        to access the auth session.

        Returns:
            Dict with status, healthy flag, and optional error.
        """
        if self._client is None:
            return {"status": "disconnected", "healthy": False}

        try:
            # Lightweight operation to verify connection is alive
            await self._client.auth.get_session()
            return {"status": "connected", "healthy": True}
        except Exception as e:
            log.error("supabase_health_check_failed", error=str(e))
            return {"status": "error", "healthy": False, "error": str(e)}


# Singleton instance
_supabase_client: SupabaseClient | None = None


async def get_supabase_client() -> SupabaseClient:
    """Get or create Supabase client singleton.

    Returns:
        Connected SupabaseClient instance.
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
        await _supabase_client.connect()
    return _supabase_client


async def close_supabase_client() -> None:
    """Close and clear Supabase client singleton."""
    global _supabase_client
    if _supabase_client is not None:
        await _supabase_client.disconnect()
        _supabase_client = None
