"""Unit tests for cluster catchup scheduler task."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.scheduler.tasks.cluster_catchup_task import run_cluster_catchup


class TestClusterCatchup:
    """Test cluster catchup scheduler."""

    @pytest.mark.asyncio
    async def test_finds_orphan_wallets(self):
        """Scheduler finds wallets without clusters."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[
                {"address": "wallet_A"},
                {"address": "wallet_B"},
            ]
        )

        onboarder = MagicMock()
        onboarder.reset = MagicMock()
        onboarder.onboard_wallet = AsyncMock(
            return_value=MagicMock(cluster_formed=False)
        )

        result = await run_cluster_catchup(neo4j, onboarder, batch_size=10)

        assert result["orphans_found"] == 2
        assert result["processed"] == 2
        assert onboarder.onboard_wallet.call_count == 2

    @pytest.mark.asyncio
    async def test_no_orphans_exits_early(self):
        """Scheduler exits cleanly when no orphans found."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(return_value=[])

        onboarder = MagicMock()

        result = await run_cluster_catchup(neo4j, onboarder)

        assert result["processed"] == 0
        assert result["clusters_formed"] == 0
        onboarder.onboard_wallet.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_individual_failures(self):
        """Scheduler continues after individual wallet failure."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[
                {"address": "wallet_A"},
                {"address": "wallet_B"},
                {"address": "wallet_C"},
            ]
        )

        onboarder = MagicMock()
        onboarder.reset = MagicMock()
        onboarder.onboard_wallet = AsyncMock(
            side_effect=[
                MagicMock(cluster_formed=True),
                Exception("Network error"),
                MagicMock(cluster_formed=False),
            ]
        )

        result = await run_cluster_catchup(neo4j, onboarder)

        assert result["processed"] == 2
        assert result["errors"] == 1
        assert result["clusters_formed"] == 1

    @pytest.mark.asyncio
    async def test_counts_clusters_formed(self):
        """Scheduler correctly counts clusters formed."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[
                {"address": "wallet_A"},
                {"address": "wallet_B"},
                {"address": "wallet_C"},
            ]
        )

        onboarder = MagicMock()
        onboarder.reset = MagicMock()
        onboarder.onboard_wallet = AsyncMock(
            side_effect=[
                MagicMock(cluster_formed=True),
                MagicMock(cluster_formed=True),
                MagicMock(cluster_formed=False),
            ]
        )

        result = await run_cluster_catchup(neo4j, onboarder)

        assert result["clusters_formed"] == 2
        assert result["processed"] == 3

    @pytest.mark.asyncio
    async def test_respects_batch_size(self):
        """Scheduler respects batch size limit."""
        neo4j = MagicMock()
        # Return 5 wallets
        neo4j.execute_query = AsyncMock(
            return_value=[
                {"address": "w1"},
                {"address": "w2"},
                {"address": "w3"},
                {"address": "w4"},
                {"address": "w5"},
            ]
        )

        onboarder = MagicMock()
        onboarder.reset = MagicMock()
        onboarder.onboard_wallet = AsyncMock(
            return_value=MagicMock(cluster_formed=False)
        )

        result = await run_cluster_catchup(neo4j, onboarder, batch_size=3)

        # Neo4j query should have been called with limit=3
        call_args = neo4j.execute_query.call_args
        query = call_args[0][0]
        assert "LIMIT" in query
        params = call_args[0][1]
        assert params["limit"] == 3

    @pytest.mark.asyncio
    async def test_resets_onboarder_state(self):
        """Scheduler resets onboarder state before processing."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[{"address": "wallet_A"}]
        )

        onboarder = MagicMock()
        onboarder.reset = MagicMock()
        onboarder.onboard_wallet = AsyncMock(
            return_value=MagicMock(cluster_formed=False)
        )

        await run_cluster_catchup(neo4j, onboarder)

        onboarder.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_empty_tx_history(self):
        """Scheduler calls onboard_wallet with empty tx_history."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(
            return_value=[{"address": "wallet_A"}]
        )

        onboarder = MagicMock()
        onboarder.reset = MagicMock()
        onboarder.onboard_wallet = AsyncMock(
            return_value=MagicMock(cluster_formed=False)
        )

        await run_cluster_catchup(neo4j, onboarder)

        call_kwargs = onboarder.onboard_wallet.call_args[1]
        assert call_kwargs["tx_history"] == []
        assert call_kwargs["depth"] == 0

    @pytest.mark.asyncio
    async def test_returns_duration(self):
        """Scheduler returns processing duration."""
        neo4j = MagicMock()
        neo4j.execute_query = AsyncMock(return_value=[])

        onboarder = MagicMock()

        result = await run_cluster_catchup(neo4j, onboarder)

        assert "duration_seconds" in result
        assert result["duration_seconds"] >= 0
