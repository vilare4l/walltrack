"""Unit tests for ClusterService - direct Neo4j cluster queries."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.cluster.cluster_service import ClusterInfo, ClusterService


class TestClusterServiceInit:
    """Test ClusterService initialization."""

    def test_init_with_neo4j(self):
        """Service initializes with Neo4j client."""
        neo4j = MagicMock()
        service = ClusterService(neo4j)
        assert service._neo4j is neo4j

    def test_init_without_neo4j(self):
        """Service initializes without Neo4j client."""
        service = ClusterService(neo4j=None)
        assert service._neo4j is None


class TestGetWalletClusterInfo:
    """Test get_wallet_cluster_info method."""

    @pytest.mark.asyncio
    async def test_returns_cluster_info_when_in_cluster(self):
        """Returns cluster info when wallet is in a cluster."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[
                {
                    "cluster_id": "cluster_123",
                    "is_leader": True,
                    "amplification_factor": 1.4,
                    "cluster_size": 5,
                }
            ]
        )

        service = ClusterService(neo4j)
        info = await service.get_wallet_cluster_info("wallet_A")

        assert info.cluster_id == "cluster_123"
        assert info.is_leader is True
        assert info.amplification_factor == 1.4
        assert info.cluster_size == 5

    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_cluster(self):
        """Returns defaults when wallet not in any cluster."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(return_value=[])

        service = ClusterService(neo4j)
        info = await service.get_wallet_cluster_info("solo_wallet")

        assert info.cluster_id is None
        assert info.is_leader is False
        assert info.amplification_factor == 1.0
        assert info.cluster_size == 0

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_error(self):
        """Returns defaults when Neo4j query fails."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(side_effect=Exception("Connection failed"))

        service = ClusterService(neo4j)
        info = await service.get_wallet_cluster_info("wallet_A")

        assert info.cluster_id is None
        assert info.is_leader is False
        assert info.amplification_factor == 1.0
        assert info.cluster_size == 0

    @pytest.mark.asyncio
    async def test_handles_no_neo4j_client(self):
        """Returns defaults when no Neo4j client configured."""
        service = ClusterService(neo4j=None)
        info = await service.get_wallet_cluster_info("wallet_A")

        assert info.cluster_id is None
        assert info.is_leader is False
        assert info.amplification_factor == 1.0
        assert info.cluster_size == 0

    @pytest.mark.asyncio
    async def test_handles_null_cluster_size(self):
        """Handles null cluster_size from Neo4j."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[
                {
                    "cluster_id": "cluster_456",
                    "is_leader": False,
                    "amplification_factor": 1.2,
                    "cluster_size": None,
                }
            ]
        )

        service = ClusterService(neo4j)
        info = await service.get_wallet_cluster_info("wallet_B")

        assert info.cluster_id == "cluster_456"
        assert info.cluster_size == 0

    @pytest.mark.asyncio
    async def test_query_uses_correct_parameters(self):
        """Query is called with correct wallet address."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(return_value=[])

        service = ClusterService(neo4j)
        await service.get_wallet_cluster_info("test_wallet_addr")

        neo4j.execute_query.assert_called_once()
        call_args = neo4j.execute_query.call_args
        # Parameters are passed as second positional argument
        params = call_args[0][1]
        assert params["address"] == "test_wallet_addr"


class TestClusterInfo:
    """Test ClusterInfo dataclass."""

    def test_cluster_info_creation(self):
        """ClusterInfo can be created with all fields."""
        info = ClusterInfo(
            cluster_id="cluster_1",
            is_leader=True,
            amplification_factor=1.5,
            cluster_size=3,
        )
        assert info.cluster_id == "cluster_1"
        assert info.is_leader is True
        assert info.amplification_factor == 1.5
        assert info.cluster_size == 3

    def test_cluster_info_defaults(self):
        """ClusterInfo with default values."""
        info = ClusterInfo(
            cluster_id=None,
            is_leader=False,
            amplification_factor=1.0,
            cluster_size=0,
        )
        assert info.cluster_id is None
        assert info.is_leader is False
        assert info.amplification_factor == 1.0
        assert info.cluster_size == 0
