"""End-to-end integration tests for wallet discovery workflow.

Tests the complete wallet discovery orchestration:
1. Token creation with wallets_discovered=FALSE
2. Helius API fetch (mocked with respx)
3. Wallet discovery filtering (early + profitable)
4. Wallet storage in Supabase
5. Token flag update to wallets_discovered=TRUE
6. Result statistics verification
"""

from datetime import UTC, datetime, timedelta

import pytest
import respx
from httpx import Response

from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.token_repo import TokenRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient


@pytest.fixture(autouse=True)
def set_helius_api_key():
    """Set dummy Helius API key for testing."""
    import os
    os.environ["HELIUS_API_KEY"] = "test-api-key-12345"
    yield
    del os.environ["HELIUS_API_KEY"]


@pytest.fixture
async def supabase_client():
    """Create connected Supabase client."""
    client = await get_supabase_client()
    yield client
    await client.disconnect()


@pytest.fixture
async def token_repo(supabase_client):
    """Create TokenRepository instance."""
    return TokenRepository(supabase_client)


@pytest.fixture
async def wallet_repo(supabase_client):
    """Create WalletRepository instance."""
    return WalletRepository(supabase_client)


@pytest.fixture
def test_token_address():
    """Test token mint address."""
    return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC (valid address)


@pytest.fixture
def test_token_launch_time():
    """Token launch time (1 hour ago)."""
    return datetime.now(UTC) - timedelta(hours=1)


@pytest.fixture
def early_profitable_buyer_transactions(test_token_address: str, test_token_launch_time: datetime):
    """Mock Helius transactions with 2 wallets:
    - Wallet1: Early buyer (10min after launch) + 60% profit → SHOULD BE DISCOVERED
    - Wallet2: Late buyer (45min after launch) + 80% profit → SHOULD BE FILTERED (too late)
    """
    launch_timestamp = int(test_token_launch_time.timestamp())

    # Wallet1: BUY at 10min, SELL at 20min with 60% profit
    wallet1_buy_timestamp = launch_timestamp + (10 * 60)  # 10 min after launch
    wallet1_sell_timestamp = launch_timestamp + (20 * 60)  # 20 min after launch

    # Wallet2: BUY at 45min, SELL at 60min with 80% profit (but TOO LATE - >30min)
    wallet2_buy_timestamp = launch_timestamp + (45 * 60)  # 45 min after launch
    wallet2_sell_timestamp = launch_timestamp + (60 * 60)  # 60 min after launch

    return [
        # Wallet1 BUY (0.5 SOL)
        {
            "signature": "sig1_buy",
            "timestamp": wallet1_buy_timestamp,
            "type": "SWAP",
            "source": "RAYDIUM",
            "nativeTransfers": [
                {
                    "fromUserAccount": "Wallet1TestAddress111111111111111",
                    "toUserAccount": "DEXPool11111111111111111111111111",
                    "amount": 500000000  # 0.5 SOL
                }
            ],
            "tokenTransfers": [
                {
                    "fromUserAccount": "DEXPool11111111111111111111111111",
                    "toUserAccount": "Wallet1TestAddress111111111111111",
                    "mint": test_token_address,
                    "tokenAmount": 1000000.0
                }
            ]
        },
        # Wallet1 SELL (0.8 SOL = 60% profit)
        {
            "signature": "sig1_sell",
            "timestamp": wallet1_sell_timestamp,
            "type": "SWAP",
            "source": "RAYDIUM",
            "nativeTransfers": [
                {
                    "fromUserAccount": "DEXPool11111111111111111111111111",
                    "toUserAccount": "Wallet1TestAddress111111111111111",
                    "amount": 800000000  # 0.8 SOL (60% profit)
                }
            ],
            "tokenTransfers": [
                {
                    "fromUserAccount": "Wallet1TestAddress111111111111111",
                    "toUserAccount": "DEXPool11111111111111111111111111",
                    "mint": test_token_address,
                    "tokenAmount": 1000000.0
                }
            ]
        },
        # Wallet2 BUY (1.0 SOL) - TOO LATE (45min)
        {
            "signature": "sig2_buy",
            "timestamp": wallet2_buy_timestamp,
            "type": "SWAP",
            "source": "RAYDIUM",
            "nativeTransfers": [
                {
                    "fromUserAccount": "Wallet2TestAddress222222222222222",
                    "toUserAccount": "DEXPool11111111111111111111111111",
                    "amount": 1000000000  # 1.0 SOL
                }
            ],
            "tokenTransfers": [
                {
                    "fromUserAccount": "DEXPool11111111111111111111111111",
                    "toUserAccount": "Wallet2TestAddress222222222222222",
                    "mint": test_token_address,
                    "tokenAmount": 2000000.0
                }
            ]
        },
        # Wallet2 SELL (1.8 SOL = 80% profit) - but late entry filtered
        {
            "signature": "sig2_sell",
            "timestamp": wallet2_sell_timestamp,
            "type": "SWAP",
            "source": "RAYDIUM",
            "nativeTransfers": [
                {
                    "fromUserAccount": "DEXPool11111111111111111111111111",
                    "toUserAccount": "Wallet2TestAddress222222222222222",
                    "amount": 1800000000  # 1.8 SOL (80% profit)
                }
            ],
            "tokenTransfers": [
                {
                    "fromUserAccount": "Wallet2TestAddress222222222222222",
                    "toUserAccount": "DEXPool11111111111111111111111111",
                    "mint": test_token_address,
                    "tokenAmount": 2000000.0
                }
            ]
        }
    ]


@pytest.mark.asyncio
class TestWalletDiscoveryE2E:
    """End-to-end integration tests for wallet discovery orchestration."""

    async def test_run_wallet_discovery_complete_workflow(
        self,
        supabase_client,
        token_repo: TokenRepository,
        wallet_repo: WalletRepository,
        test_token_address: str,
        test_token_launch_time: datetime,
        early_profitable_buyer_transactions: list[dict],
        cleanup_test_wallets,
        cleanup_test_tokens,
        cleanup_test_neo4j_nodes,
    ):
        """Test complete wallet discovery workflow from token to stored wallets.

        Workflow:
        1. Create token with wallets_discovered=FALSE
        2. Mock Helius API to return transactions
        3. Run wallet discovery orchestration
        4. Verify:
           - Only Wallet1 discovered (early + profitable)
           - Wallet2 filtered out (late entry)
           - Wallet stored in database
           - Token flag updated to wallets_discovered=TRUE
           - Statistics correct
        """
        # ARRANGE: Register test data for automatic cleanup
        test_wallet1 = "Wallet1TestAddress111111111111111"
        test_wallet2 = "Wallet2TestAddress222222222222222"

        cleanup_test_wallets(test_wallet1)
        cleanup_test_wallets(test_wallet2)
        cleanup_test_tokens(test_token_address)
        cleanup_test_neo4j_nodes(test_wallet1)
        cleanup_test_neo4j_nodes(test_wallet2)

        # Create test token with wallets_discovered=FALSE via direct SQL
        # (allows us to control created_at precisely for testing)
        await supabase_client.client.table("tokens").insert({
            "mint": test_token_address,
            "symbol": "TEST",
            "name": "Test Token",
            "price_usd": 1.0,
            "market_cap": 1000000.0,
            "volume_24h": 50000.0,
            "liquidity_usd": 25000.0,
            "created_at": test_token_launch_time.isoformat(),
            "wallets_discovered": False,
        }).execute()

        # Verify token created
        created_token = await token_repo.get_by_mint(test_token_address)
        assert created_token is not None
        assert created_token.wallets_discovered is False

        # Create service with real repos
        helius_client = HeliusClient()
        service = WalletDiscoveryService(
            helius_client=helius_client,
            wallet_repository=wallet_repo,
            token_repository=token_repo,
        )

        try:
            # Mock Helius API only (allow Supabase requests to pass through)
            with respx.mock(base_url="https://api.helius.xyz") as respx_mock:
                # Mock the Helius transaction endpoint
                respx_mock.get(
                    url__regex=rf"/v0/addresses/{test_token_address}/transactions.*"
                ).mock(return_value=Response(200, json=early_profitable_buyer_transactions))

                # ACT: Run wallet discovery orchestration
                result = await service.run_wallet_discovery()

        finally:
            # Close Helius client
            await helius_client.close()

        # ASSERT: Verify statistics
        assert result["tokens_processed"] == 1, "Should process 1 token"
        assert result["wallets_discovered"] == 1, "Should discover 1 wallet (Wallet1 only - Wallet2 filtered)"
        assert result["wallets_new"] == 1, "Should create 1 new wallet (Wallet1 only)"
        assert result["wallets_existing"] == 0, "Should have 0 existing wallets"
        assert result["errors"] == 0, "Should have 0 errors"

        # ASSERT: Verify Wallet1 stored in database (early + profitable)
        stored_wallet1 = await wallet_repo.get_wallet(test_wallet1)
        assert stored_wallet1 is not None, "Wallet1 should be stored"
        assert stored_wallet1.wallet_address == test_wallet1
        assert stored_wallet1.token_source == test_token_address

        # ASSERT: Verify Wallet2 NOT stored (filtered - late entry)
        stored_wallet2 = await wallet_repo.get_wallet(test_wallet2)
        assert stored_wallet2 is None, "Wallet2 should NOT be stored (late entry)"

        # ASSERT: Verify token flag updated
        updated_token = await token_repo.get_by_mint(test_token_address)
        assert updated_token is not None
        assert updated_token.wallets_discovered is True, "Token should be marked as discovered"

        # CLEANUP: Automatic via fixtures (cleanup_test_wallets, cleanup_test_tokens, cleanup_test_neo4j_nodes)
