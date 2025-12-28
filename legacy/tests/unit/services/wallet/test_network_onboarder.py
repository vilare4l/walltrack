"""Unit tests for automatic network onboarding.

Epic 14 Story 14-4: Automatic Network Onboarding
Tests for NetworkOnboarder service that auto-discovers networks and forms clusters.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.wallet.network_onboarder import (
    NetworkOnboarder,
    OnboardingConfig,
    OnboardingResult,
)


@pytest.fixture
def mock_neo4j() -> AsyncMock:
    """Create mock Neo4j client."""
    return AsyncMock()


@pytest.fixture
def mock_wallet_cache() -> AsyncMock:
    """Create mock wallet cache."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=(None, False))
    cache.update_cluster_for_members = AsyncMock(return_value=3)
    return cache


@pytest.fixture
def mock_funding_analyzer() -> AsyncMock:
    """Create mock funding analyzer."""
    analyzer = AsyncMock()
    analyzer.analyze_wallet_funding = AsyncMock(return_value=[])
    return analyzer


@pytest.fixture
def mock_sync_detector() -> AsyncMock:
    """Create mock sync detector."""
    detector = AsyncMock()
    detector.detect_sync_buys_for_token = AsyncMock(return_value=[])
    return detector


@pytest.fixture
def mock_cluster_grouper() -> AsyncMock:
    """Create mock cluster grouper."""
    grouper = AsyncMock()
    grouper.create_cluster_from_members = AsyncMock(return_value="cluster-123")
    grouper.add_members_to_cluster = AsyncMock(return_value=2)
    return grouper


@pytest.fixture
def mock_leader_detector() -> AsyncMock:
    """Create mock leader detector."""
    detector = AsyncMock()
    detector.detect_cluster_leader = AsyncMock(return_value="leader-wallet")
    return detector


@pytest.fixture
def mock_signal_amplifier() -> AsyncMock:
    """Create mock signal amplifier."""
    amplifier = AsyncMock()
    amplifier.calculate_cluster_multiplier = AsyncMock(return_value=1.5)
    amplifier.update_cluster_multipliers = AsyncMock(return_value={"cluster-123": 1.5})
    return amplifier


@pytest.fixture
def onboarder(
    mock_neo4j: AsyncMock,
    mock_wallet_cache: AsyncMock,
    mock_funding_analyzer: AsyncMock,
    mock_sync_detector: AsyncMock,
    mock_cluster_grouper: AsyncMock,
    mock_leader_detector: AsyncMock,
    mock_signal_amplifier: AsyncMock,
) -> NetworkOnboarder:
    """Create onboarder with mocked dependencies."""
    return NetworkOnboarder(
        neo4j=mock_neo4j,
        wallet_cache=mock_wallet_cache,
        funding_analyzer=mock_funding_analyzer,
        sync_detector=mock_sync_detector,
        cluster_grouper=mock_cluster_grouper,
        leader_detector=mock_leader_detector,
        signal_amplifier=mock_signal_amplifier,
        config=OnboardingConfig(
            max_depth=1,
            min_quick_score=0.4,
            min_cluster_size=3,
            max_network_size=20,
        ),
    )


class TestOnboardingConfig:
    """Tests for OnboardingConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OnboardingConfig()

        assert config.max_depth == 1
        assert config.min_quick_score == 0.4
        assert config.min_cluster_size == 3
        assert config.max_network_size == 20
        assert config.sync_window_seconds == 300

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = OnboardingConfig(
            max_depth=2,
            min_quick_score=0.6,
            min_cluster_size=5,
            max_network_size=50,
        )

        assert config.max_depth == 2
        assert config.min_quick_score == 0.6
        assert config.min_cluster_size == 5
        assert config.max_network_size == 50


class TestOnboardingResult:
    """Tests for OnboardingResult dataclass."""

    def test_default_result(self) -> None:
        """Test default result values."""
        result = OnboardingResult(wallet_address="test-wallet")

        assert result.wallet_address == "test-wallet"
        assert result.funding_edges_created == 0
        assert result.sync_buy_edges_created == 0
        assert result.network_wallets_found == 0
        assert result.cluster_formed is False
        assert result.cluster_id is None

    def test_full_result(self) -> None:
        """Test fully populated result."""
        result = OnboardingResult(
            wallet_address="test-wallet",
            funding_edges_created=3,
            sync_buy_edges_created=2,
            network_wallets_found=5,
            cluster_formed=True,
            cluster_id="cluster-123",
            cluster_size=4,
            leader_address="leader-wallet",
        )

        assert result.funding_edges_created == 3
        assert result.cluster_formed is True
        assert result.cluster_id == "cluster-123"
        assert result.leader_address == "leader-wallet"


class TestNetworkOnboarder:
    """Tests for NetworkOnboarder service."""

    @pytest.mark.asyncio
    async def test_onboard_creates_funding_edges(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Funding analysis runs on tx_history."""
        # Setup
        mock_edges = [MagicMock(), MagicMock()]
        onboarder._funding_analyzer.analyze_wallet_funding = AsyncMock(
            return_value=mock_edges
        )
        onboarder._neo4j.execute_query = AsyncMock(return_value=[])

        # Execute
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[{"type": "transfer", "from": "funder_1"}],
        )

        # Verify
        assert result.funding_edges_created == 2
        onboarder._funding_analyzer.analyze_wallet_funding.assert_called_once()

    @pytest.mark.asyncio
    async def test_onboard_skips_processed(self, onboarder: NetworkOnboarder) -> None:
        """Already processed wallets are skipped."""
        # Setup
        onboarder._processed.add("wallet_A")

        # Execute
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[],
        )

        # Verify
        assert result.funding_edges_created == 0
        assert result.cluster_formed is False
        # Funding analyzer should not be called
        onboarder._funding_analyzer.analyze_wallet_funding.assert_not_called()

    @pytest.mark.asyncio
    async def test_cluster_formed_with_three_members(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Cluster is formed when >= 3 qualified wallets."""
        # Setup
        onboarder._neo4j.execute_query = AsyncMock(
            side_effect=[
                # _discover_network returns 3 connected wallets
                [
                    {"address": "wallet_B"},
                    {"address": "wallet_C"},
                    {"address": "wallet_D"},
                ],
                # _quick_score queries (all qualify with good scores)
                [{"tx_count": 50, "win_rate": 0.6}],
                [{"tx_count": 40, "win_rate": 0.5}],
                [{"tx_count": 30, "win_rate": 0.5}],
                # _find_existing_cluster returns None
                [],
            ]
        )

        # Execute
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[{"type": "swap", "tokenTransfers": [{"mint": "token_1"}]}],
        )

        # Verify
        assert result.cluster_formed is True
        assert result.cluster_id == "cluster-123"
        onboarder._wallet_cache.update_cluster_for_members.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_cluster_with_few_members(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """No cluster formed when < min_cluster_size wallets."""
        # Setup - only 1 connected wallet
        onboarder._neo4j.execute_query = AsyncMock(
            side_effect=[
                # _discover_network returns only 1 wallet
                [{"address": "wallet_B"}],
                # _quick_score
                [{"tx_count": 50, "win_rate": 0.6}],
            ]
        )

        # Execute
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[],
        )

        # Verify - only 2 wallets (wallet_A + wallet_B), need 3
        assert result.cluster_formed is False
        assert result.cluster_id is None

    @pytest.mark.asyncio
    async def test_merges_into_existing_cluster(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Merges into existing cluster when overlap found."""
        # Setup
        onboarder._neo4j.execute_query = AsyncMock(
            side_effect=[
                # _discover_network
                [{"address": "wallet_B"}, {"address": "wallet_C"}],
                # _quick_score queries
                [{"tx_count": 50, "win_rate": 0.6}],
                [{"tx_count": 40, "win_rate": 0.5}],
                # _find_existing_cluster returns existing cluster
                [{"cluster_id": "existing-cluster"}],
            ]
        )

        # Execute
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[],
        )

        # Verify
        assert result.cluster_formed is True
        assert result.cluster_id == "existing-cluster"
        onboarder._cluster_grouper.add_members_to_cluster.assert_called_once()

    @pytest.mark.asyncio
    async def test_low_score_wallets_filtered_out(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Wallets below min_quick_score are filtered out."""
        # Setup
        onboarder._neo4j.execute_query = AsyncMock(
            side_effect=[
                # _discover_network returns 3 wallets
                [
                    {"address": "wallet_B"},
                    {"address": "wallet_C"},
                    {"address": "wallet_D"},
                ],
                # _quick_score - all have low scores
                [{"tx_count": 5, "win_rate": 0.1}],  # score < 0.4
                [{"tx_count": 3, "win_rate": 0.1}],  # score < 0.4
                [{"tx_count": 2, "win_rate": 0.1}],  # score < 0.4
            ]
        )

        # Execute
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[],
        )

        # Verify - none qualify, so no cluster formed
        assert result.cluster_formed is False

    @pytest.mark.asyncio
    async def test_extract_recent_tokens(self, onboarder: NetworkOnboarder) -> None:
        """Token extraction from tx_history works correctly."""
        tx_history = [
            {"type": "SWAP", "tokenTransfers": [{"mint": "token_1"}]},
            {"type": "SWAP", "tokenTransfers": [{"mint": "token_2"}]},
            {"type": "TRANSFER", "nativeTransfers": []},
            {"type": "SWAP", "token_address": "token_3"},
        ]

        tokens = onboarder._extract_recent_tokens(tx_history)

        assert "token_1" in tokens
        assert "token_2" in tokens
        assert "token_3" in tokens

    @pytest.mark.asyncio
    async def test_reset_clears_processed(self, onboarder: NetworkOnboarder) -> None:
        """Reset clears the processed set."""
        onboarder._processed.add("wallet_A")
        onboarder._processed.add("wallet_B")

        onboarder.reset()

        assert len(onboarder._processed) == 0

    @pytest.mark.asyncio
    async def test_update_config(self, onboarder: NetworkOnboarder) -> None:
        """Config update works correctly."""
        new_config = OnboardingConfig(
            max_depth=2,
            min_cluster_size=5,
        )

        onboarder.update_config(new_config)

        assert onboarder._config.max_depth == 2
        assert onboarder._config.min_cluster_size == 5


class TestRecursionSafeguards:
    """Tests for safeguards against runaway recursion."""

    @pytest.mark.asyncio
    async def test_max_depth_respected(
        self,
        mock_neo4j: AsyncMock,
        mock_wallet_cache: AsyncMock,
        mock_funding_analyzer: AsyncMock,
        mock_sync_detector: AsyncMock,
        mock_cluster_grouper: AsyncMock,
        mock_leader_detector: AsyncMock,
        mock_signal_amplifier: AsyncMock,
    ) -> None:
        """Recursion stops at max_depth."""
        config = OnboardingConfig(max_depth=0)  # No recursion
        onboarder = NetworkOnboarder(
            neo4j=mock_neo4j,
            wallet_cache=mock_wallet_cache,
            funding_analyzer=mock_funding_analyzer,
            sync_detector=mock_sync_detector,
            cluster_grouper=mock_cluster_grouper,
            leader_detector=mock_leader_detector,
            signal_amplifier=mock_signal_amplifier,
            config=config,
        )

        # Setup - returns connected wallets
        mock_neo4j.execute_query = AsyncMock(
            side_effect=[
                [{"address": "wallet_B"}],
                [{"tx_count": 50, "win_rate": 0.6}],
            ]
        )

        # Execute at depth=0
        result = await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[],
            depth=0,
        )

        # Verify - should not recurse since max_depth=0
        assert result.wallet_address == "wallet_A"
        # Only wallet_A should be processed (no recursion)
        assert "wallet_A" in onboarder._processed
        assert "wallet_B" not in onboarder._processed

    @pytest.mark.asyncio
    async def test_max_network_size_in_query(
        self,
        mock_neo4j: AsyncMock,
        mock_wallet_cache: AsyncMock,
        mock_funding_analyzer: AsyncMock,
        mock_sync_detector: AsyncMock,
        mock_cluster_grouper: AsyncMock,
        mock_leader_detector: AsyncMock,
        mock_signal_amplifier: AsyncMock,
    ) -> None:
        """Max network size is passed to query."""
        config = OnboardingConfig(max_network_size=5)
        onboarder = NetworkOnboarder(
            neo4j=mock_neo4j,
            wallet_cache=mock_wallet_cache,
            funding_analyzer=mock_funding_analyzer,
            sync_detector=mock_sync_detector,
            cluster_grouper=mock_cluster_grouper,
            leader_detector=mock_leader_detector,
            signal_amplifier=mock_signal_amplifier,
            config=config,
        )

        mock_neo4j.execute_query = AsyncMock(return_value=[])

        await onboarder.onboard_wallet(
            address="wallet_A",
            tx_history=[],
        )

        # Verify the limit was passed in the query call
        call_args = mock_neo4j.execute_query.call_args_list[0]
        assert call_args.kwargs.get("limit") == 5 or call_args.args[1].get("limit") == 5


class TestRebuildAllClusters:
    """Tests for rebuild_all_clusters method."""

    @pytest.mark.asyncio
    async def test_rebuild_all_runs_full_pipeline(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Rebuild all runs the complete clustering pipeline."""
        # Setup
        mock_cluster = MagicMock()
        mock_cluster.id = "cluster-123"
        mock_cluster.leader_address = "leader-wallet"
        mock_cluster.members = [
            MagicMock(wallet_address="wallet_A"),
            MagicMock(wallet_address="wallet_B"),
        ]
        onboarder._cluster_grouper.find_clusters = AsyncMock(
            return_value=[mock_cluster]
        )

        # Execute
        result = await onboarder.rebuild_all_clusters()

        # Verify
        assert result["clusters_found"] == 1
        onboarder._cluster_grouper.find_clusters.assert_called_once()
        onboarder._leader_detector.detect_cluster_leader.assert_called_once()
        onboarder._signal_amplifier.update_cluster_multipliers.assert_called_once()
        onboarder._wallet_cache.update_cluster_for_members.assert_called_once()


class TestQuickScore:
    """Tests for quick scoring logic."""

    @pytest.mark.asyncio
    async def test_quick_score_calculation(self, onboarder: NetworkOnboarder) -> None:
        """Quick score calculation works correctly."""
        onboarder._neo4j.execute_query = AsyncMock(
            return_value=[{"tx_count": 100, "win_rate": 0.7}]
        )

        score = await onboarder._quick_score("wallet_A")

        # tx_score = min(1.0, 100/100) = 1.0
        # score = (1.0 * 0.3) + (0.7 * 0.7) = 0.3 + 0.49 = 0.79
        assert score == pytest.approx(0.79, rel=0.01)

    @pytest.mark.asyncio
    async def test_quick_score_zero_for_missing_wallet(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Quick score returns 0 for missing wallet."""
        onboarder._neo4j.execute_query = AsyncMock(return_value=[])

        score = await onboarder._quick_score("unknown_wallet")

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_quick_score_handles_none_values(
        self, onboarder: NetworkOnboarder
    ) -> None:
        """Quick score handles None values in results."""
        onboarder._neo4j.execute_query = AsyncMock(
            return_value=[{"tx_count": None, "win_rate": None}]
        )

        score = await onboarder._quick_score("wallet_A")

        assert score == 0.0
