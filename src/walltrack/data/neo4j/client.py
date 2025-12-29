"""Neo4j async client with connection management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from walltrack.config.settings import get_settings
from walltrack.core.exceptions import DatabaseConnectionError

log = structlog.get_logger()


class Neo4jClient:
    """Async Neo4j client with connection management.

    Provides connection management, health checks, and session context
    manager for executing Cypher queries.
    """

    def __init__(self) -> None:
        """Initialize client with settings."""
        self._driver: AsyncDriver | None = None
        self._settings = get_settings()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def connect(self) -> None:
        """Establish connection to Neo4j.

        Raises:
            DatabaseConnectionError: If connection fails after retries.
        """
        if self._driver is not None:
            return

        try:
            self._driver = AsyncGraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(
                    self._settings.neo4j_user,
                    self._settings.neo4j_password.get_secret_value(),
                ),
            )
            # Verify connectivity
            await self._driver.verify_connectivity()

            log.info(
                "neo4j_connected",
                uri=self._settings.neo4j_uri,
            )
        except Exception as e:
            log.error("neo4j_connection_failed", error=str(e))
            raise DatabaseConnectionError(f"Neo4j: {e}") from e

    async def disconnect(self) -> None:
        """Close Neo4j connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            log.info("neo4j_disconnected")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a Neo4j session context manager.

        Yields:
            AsyncSession for executing queries.

        Raises:
            DatabaseConnectionError: If not connected.
        """
        if self._driver is None:
            raise DatabaseConnectionError("Neo4j: Driver not connected")

        session = self._driver.session()
        try:
            yield session
        finally:
            await session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query with retry logic.

        Args:
            query: Cypher query string.
            parameters: Optional query parameters.

        Returns:
            List of result records as dictionaries.
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def health_check(self) -> dict[str, Any]:
        """Check Neo4j connection health.

        Returns:
            Dict with status, healthy flag, and optional error.
        """
        if self._driver is None:
            return {"status": "disconnected", "healthy": False}

        try:
            await self._driver.verify_connectivity()
            return {"status": "connected", "healthy": True}
        except Exception as e:
            log.error("neo4j_health_check_failed", error=str(e))
            return {"status": "error", "healthy": False, "error": str(e)}


# Singleton instance
_neo4j_client: Neo4jClient | None = None


async def get_neo4j_client() -> Neo4jClient:
    """Get or create Neo4j client singleton.

    Returns:
        Connected Neo4jClient instance.
    """
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
        await _neo4j_client.connect()
    return _neo4j_client


async def close_neo4j_client() -> None:
    """Close and clear Neo4j client singleton."""
    global _neo4j_client
    if _neo4j_client is not None:
        await _neo4j_client.disconnect()
        _neo4j_client = None
