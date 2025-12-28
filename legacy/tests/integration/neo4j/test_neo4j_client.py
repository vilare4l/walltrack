"""Integration tests for Neo4j client.

Test ID: 1.3-INT-001
"""

import pytest

from walltrack.data.neo4j.client import Neo4jClient


@pytest.mark.integration
class TestNeo4jClient:
    """Tests for Neo4j client."""

    @pytest.fixture
    async def client(self) -> Neo4jClient:
        """Create and connect client."""
        client = Neo4jClient()
        await client.connect()
        yield client
        await client.disconnect()

    async def test_connect(self, client: Neo4jClient) -> None:
        """Test connection establishment."""
        health = await client.health_check()
        assert health["healthy"] is True
        assert health["status"] == "connected"

    async def test_execute_query(self, client: Neo4jClient) -> None:
        """Test query execution."""
        result = await client.execute_query("RETURN 1 as value")
        assert result[0]["value"] == 1

    async def test_execute_write(self, client: Neo4jClient) -> None:
        """Test write execution."""
        # Create test node
        result = await client.execute_write(
            "CREATE (n:TestNode {name: $name}) RETURN n",
            {"name": "test"},
        )
        assert result["nodes_created"] == 1

        # Cleanup
        await client.execute_write("MATCH (n:TestNode) DELETE n")
