"""Neo4j async client with connection pooling and retry logic."""

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
    """Async Neo4j client with connection management."""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self._settings = get_settings()

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            return

        try:
            self._driver = AsyncGraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(
                    self._settings.neo4j_user,
                    self._settings.neo4j_password.get_secret_value(),
                ),
                max_connection_pool_size=self._settings.neo4j_max_connection_pool_size,
            )
            # Verify connectivity
            await self._driver.verify_connectivity()

            # Ensure dedicated database exists (Neo4j 4.0+)
            await self._ensure_database_exists()

            log.info(
                "neo4j_connected",
                uri=self._settings.neo4j_uri,
                database=self._settings.neo4j_database,
            )
        except Exception as e:
            log.error("neo4j_connection_failed", error=str(e))
            raise DatabaseConnectionError(f"Failed to connect to Neo4j: {e}") from e

    async def _ensure_database_exists(self) -> None:
        """Create dedicated database if it doesn't exist (Neo4j 4.0+ Enterprise/Community)."""
        if self._driver is None:
            return

        db_name = self._settings.neo4j_database
        if db_name == "neo4j":
            return  # Default database, skip creation

        try:
            # Use system database to check/create
            async with self._driver.session(database="system") as session:
                # Check if database exists
                result = await session.run("SHOW DATABASES")
                databases = [record["name"] async for record in result]

                if db_name not in databases:
                    await session.run(f"CREATE DATABASE {db_name} IF NOT EXISTS")
                    log.info("neo4j_database_created", database=db_name)
        except Exception as e:
            # Neo4j Community may not support multiple databases
            log.warning(
                "neo4j_database_creation_skipped",
                database=db_name,
                reason=str(e),
            )

    async def disconnect(self) -> None:
        """Close Neo4j connection."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            log.info("neo4j_disconnected")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a Neo4j session context manager."""
        if self._driver is None:
            await self.connect()

        if self._driver is None:
            raise DatabaseConnectionError("Failed to establish Neo4j connection")

        session = self._driver.session(database=self._settings.neo4j_database)
        try:
            yield session
        finally:
            await session.close()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher query with retry logic."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a write query with retry logic."""
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            summary = await result.consume()
            return {
                "nodes_created": summary.counters.nodes_created,
                "nodes_deleted": summary.counters.nodes_deleted,
                "relationships_created": summary.counters.relationships_created,
                "relationships_deleted": summary.counters.relationships_deleted,
                "properties_set": summary.counters.properties_set,
            }

    async def health_check(self) -> dict[str, Any]:
        """Check Neo4j connection health."""
        try:
            if self._driver is None:
                return {"status": "disconnected", "healthy": False}

            await self._driver.verify_connectivity()
            records = await self.execute_query("RETURN 1 as ping")
            return {
                "status": "connected",
                "healthy": True,
                "ping": records[0]["ping"] if records else None,
            }
        except Exception as e:
            log.error("neo4j_health_check_failed", error=str(e))
            return {"status": "error", "healthy": False, "error": str(e)}


# Singleton instance
_neo4j_client: Neo4jClient | None = None


async def get_neo4j_client() -> Neo4jClient:
    """Get or create Neo4j client singleton."""
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
        await _neo4j_client.connect()
    return _neo4j_client


async def close_neo4j_client() -> None:
    """Close Neo4j client."""
    global _neo4j_client
    if _neo4j_client is not None:
        await _neo4j_client.disconnect()
        _neo4j_client = None
