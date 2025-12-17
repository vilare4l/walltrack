"""Integration tests for Supabase client.

Test ID: 1.3-INT-002
"""

import subprocess

import pytest

from walltrack.data.supabase.client import SupabaseClient


@pytest.mark.integration
class TestSupabaseClient:
    """Tests for Supabase client."""

    @pytest.fixture
    async def client(self) -> SupabaseClient:
        """Create and connect client."""
        client = SupabaseClient()
        await client.connect()
        yield client
        await client.disconnect()

    async def test_connect(self, client: SupabaseClient) -> None:
        """Test connection establishment."""
        health = await client.health_check()
        assert health["healthy"] is True
        assert health["status"] == "connected"

    async def test_schema_property(self, client: SupabaseClient) -> None:
        """Test schema property."""
        assert client.schema == "walltrack"

    def test_walltrack_schema_exists_in_postgres(self) -> None:
        """Test that walltrack schema exists in PostgreSQL.

        This test verifies the schema was created correctly by checking
        directly via psql in the supabase-db container.
        """
        result = subprocess.run(
            [
                "docker",
                "exec",
                "supabase-db",
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-t",
                "-c",
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'walltrack';",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, f"psql command failed: {result.stderr}"
        assert "walltrack" in result.stdout, "walltrack schema not found in PostgreSQL"
