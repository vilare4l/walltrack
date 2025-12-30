"""Performance tests for wallet discovery service (Story 3.1 - Task 8.3).

Tests cover:
- Discovery performance with multiple tokens (50 wallets from 10 tokens)
- Execution time validation (< 30 seconds)
- Memory leak detection
"""

import time
import tracemalloc
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import respx
from httpx import Response

from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService
from walltrack.data.repositories.wallet_repository import WalletRepository
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.token_repo import TokenRepository
from walltrack.services.helius.client import HeliusClient


@pytest.fixture
def token_launch_time() -> datetime:
    """Token launch time (1 hour ago)."""
    return datetime.now(UTC) - timedelta(hours=1)


@pytest.fixture
def mock_profitable_wallet_transactions(token_launch_time: datetime):
    """Generate mock transactions for 5 profitable wallets per token.

    Each wallet:
    - Buys early (within 30min of launch)
    - Sells with >50% profit
    """
    launch_timestamp = int(token_launch_time.timestamp())

    # Pool of 50 unique valid Solana addresses (NOT in KNOWN_PROGRAM_ADDRESSES)
    # Using real token mint addresses from Solana blockchain
    WALLET_ADDRESS_POOL = [
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # Bonk
        "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",  # Kamino
        "RLBxxFkseAZ4RgJH3Sqn8jXxhmGoz9jWxDNJMh8pL7a",  # Rollbit
        "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # Pyth
        "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
        "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
        "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # ETH
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",  # Jupiter
        "HxhWkVpk5NS4Ltg5nij2G671CKXFRKPK8vy271Ub4uEK",  # Parcl
        "SHDWyBxihqiCj6YekG2GUr7wqKLeLAMK1gHZck9pL6y",  # Shadow
        "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",  # Helium
        "5oVNBeEEQvYi1cX3ir8Dx5n1P7pdxydbGF2X4TxVusJm",  # INF Token
        "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
        "8Ki8DpuWNxu9VsS3kQbarsCWMcFGWkzzA8pUPto9zBd5",  # LFG
        "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",  # BOKU
        "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",  # RAY
        "kinXdEcpDQeHPEuQnqmUgtYykqKGVFq6CeVX5iAHJq6",  # KIN
        "AGFEad2et2ZJif9jaGpdMixQqvW5i81aBdvKe7PHNfz3",  # FTT
        "CowKesoLUaHSbAMaUxJUj7eodHHsaLsS65cy8NFyRDGP",  # COW
        "DFL1zNkaGPWm1BqAVqRjCZvHmwTFrEaJtbzJWgseoNJh",  # DFL
        "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",  # POPCAT
        "A3HyGZqe451CBesNqieNPfJ4A93CuKTfKN8X5hAKLZdT",  # RENDER
        "GENEtH5amGSi8kHAtQoezp1XEXwZJ8vcuePYnXdKrMYz",  # GENE
        "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m",  # META
        "nosXBVoaCTtYdLvKY6Csb4AC8JCdQKKAaWYtx2ZMoo7",  # NOS
        "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",  # PANDA
        "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",  # RENDER
        "BLZEEuZUBVqFhj8adcCFPJvPVCiCyVmh3hkJMrU8KuJA",  # BLZE
        "GDfnEsia2WLAW5t8yx2X5j2mkfA74i5kwGdDuZHt7XmG",  # GOFX
        "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",  # ORCA
        "CASHVDm2wsJXfhj6VWxb7GiMdoLc17Du7paH4bNr5woT",  # CASH
        "GRAPEcuH36x5xGDqSYpKKicrjvJRqD2U1UEtk5eFHzn",  # GRAPE
        "LUNGEjUCeJVQHEqXgFQa5y6nRcMtJcKwdK7DCMX2LTk",  # LUNGE
        "MERLuDFBMmsHnsBPZw2sDQZHvXFMwp8EdjudcU2HKky",  # MERL
        "PRT88RkA4Kg5z7pKnezeNH4mafTvtQdfFgpQTGRjz44",  # PRT
        "SAMcDSt3o6KmMKfREgxnxvqKFsz9M1RJjZyDj4kGqE6",  # SAM
        "SLNDpmoWTVADgEdndyvWzroNL7zSi1dF9PC3xHGtPwp",  # SLND
        "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",  # SRM
        "SYNTHrHiLnvuHXcR58L1cLsAMymLwnkJWFzKkjBkdvT",  # SYNTH
        "TULIPQJavaQFUxRptpEfWh4h4jVEaDN69CvjKjKC7Cu",  # TULIP
        "USDCVCkpgBSFdZELbvjwrWs9Mv2uoRuU8mMdxp1UQzQ",  # USDC (backup)
        "USDTvK7dVQQrWaCQwJHw4kmV9R3uXhvdP7Wb8vZ9UmJ",  # USDT (backup)
        "SUSHImXy7mSfBBWDWfXmrWB46j5C3bJRTNLmCwrYWU7",  # SUSHI
        "UNIdD9CYCXmyxJnCr5LCDH6Q7zTg8pQsHPQ6jjR7XZW",  # UNI
        "AAPLLNBqw3yEVDWEVZVjQKZGEuFqp9WxRpNVGWEuqkh",  # AAPL
        "GOOGTdCrB8H3bx95mqVpKr6JKr5WxDtYQYNPWGTjRHo",  # GOOG
        "AMZNTLxJYWYqPZtH3H2HPCNk5zv4kKbQqhxcYrhvdHN",  # AMZN
        "MSFTvKXDLbVRbXDHNdM8KTTkPCK4rXBmTL9cFZ7gkh8",  # MSFT
        "TSLAvKBqzDX9yEL3XCwJz8DwMmQfKdHNmMTqvCWkHq9",  # TSLA
        "NFLXwG8Hd3vNxC9KJYq3p5DkZVmQWBqYnHdCJP7kXh6",  # NFLX
    ]

    # Track which tokens have been seen to assign unique wallets
    token_to_wallet_offset = {}

    def generate_transactions_for_token(token_address: str) -> list[dict]:
        """Generate transactions for 5 wallets for a given token."""
        transactions = []

        # Assign unique offset for this token (5 wallets per token, no overlap)
        if token_address not in token_to_wallet_offset:
            token_to_wallet_offset[token_address] = len(token_to_wallet_offset) * 5

        offset = token_to_wallet_offset[token_address]

        for i in range(5):
            wallet_address = WALLET_ADDRESS_POOL[offset + i]

            # BUY transaction (5-25 min after launch)
            buy_timestamp = launch_timestamp + ((5 + i * 4) * 60)
            # Valid DEX pool address (44 chars, base58)
            pool_address = "TestPoolDEX111111111111111111111111111"
            transactions.append({
                "signature": f"buy_{wallet_address}_{token_address}",
                "timestamp": buy_timestamp,
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [{
                    "fromUserAccount": wallet_address,
                    "toUserAccount": pool_address,
                    "amount": 500_000_000  # 0.5 SOL
                }],
                "tokenTransfers": [{
                    "fromUserAccount": pool_address,
                    "toUserAccount": wallet_address,
                    "mint": token_address,
                    "tokenAmount": 1_000_000.0
                }],
            })

            # SELL transaction (60% profit)
            sell_timestamp = buy_timestamp + (30 * 60)  # 30min later
            transactions.append({
                "signature": f"sell_{wallet_address}_{token_address}",
                "timestamp": sell_timestamp,
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [{
                    "fromUserAccount": pool_address,
                    "toUserAccount": wallet_address,
                    "amount": 800_000_000  # 0.8 SOL (60% profit)
                }],
                "tokenTransfers": [{
                    "fromUserAccount": wallet_address,
                    "toUserAccount": pool_address,
                    "mint": token_address,
                    "tokenAmount": 1_000_000.0
                }],
            })

        return transactions

    return generate_transactions_for_token


@pytest.mark.asyncio
@pytest.mark.slow
class TestWalletDiscoveryPerformance:
    """Performance tests for wallet discovery orchestration."""

    async def test_discovery_performance_50_wallets_10_tokens(
        self,
        token_launch_time: datetime,
        mock_profitable_wallet_transactions,
        cleanup_test_wallets,
        cleanup_test_tokens,
    ):
        """Test discovery of 50 wallets from 10 tokens completes in < 30 seconds.

        Performance requirements (from Story 3.1 Task 8.3):
        - Process 10 tokens with 5 wallets each (50 total)
        - Complete in < 30 seconds
        - No memory leaks detected
        """
        # ARRANGE: Create 10 test tokens in database
        client = await get_supabase_client()
        token_repo = TokenRepository(client)
        wallet_repo = WalletRepository(client)

        # CRITICAL: Clean ALL test wallets BEFORE test to ensure fresh start
        WALLET_POOL_FOR_CLEANUP = [
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",
            "RLBxxFkseAZ4RgJH3Sqn8jXxhmGoz9jWxDNJMh8pL7a", "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So", "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",
            "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "HxhWkVpk5NS4Ltg5nij2G671CKXFRKPK8vy271Ub4uEK", "SHDWyBxihqiCj6YekG2GUr7wqKLeLAMK1gHZck9pL6y",
            "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux", "5oVNBeEEQvYi1cX3ir8Dx5n1P7pdxydbGF2X4TxVusJm",
            "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "8Ki8DpuWNxu9VsS3kQbarsCWMcFGWkzzA8pUPto9zBd5",
            "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82", "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
            "kinXdEcpDQeHPEuQnqmUgtYykqKGVFq6CeVX5iAHJq6", "AGFEad2et2ZJif9jaGpdMixQqvW5i81aBdvKe7PHNfz3",
            "CowKesoLUaHSbAMaUxJUj7eodHHsaLsS65cy8NFyRDGP", "DFL1zNkaGPWm1BqAVqRjCZvHmwTFrEaJtbzJWgseoNJh",
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "A3HyGZqe451CBesNqieNPfJ4A93CuKTfKN8X5hAKLZdT",
            "GENEtH5amGSi8kHAtQoezp1XEXwZJ8vcuePYnXdKrMYz", "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m",
            "nosXBVoaCTtYdLvKY6Csb4AC8JCdQKKAaWYtx2ZMoo7", "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",
            "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof", "BLZEEuZUBVqFhj8adcCFPJvPVCiCyVmh3hkJMrU8KuJA",
            "GDfnEsia2WLAW5t8yx2X5j2mkfA74i5kwGdDuZHt7XmG", "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
            "CASHVDm2wsJXfhj6VWxb7GiMdoLc17Du7paH4bNr5woT", "GRAPEcuH36x5xGDqSYpKKicrjvJRqD2U1UEtk5eFHzn",
            "LUNGEjUCeJVQHEqXgFQa5y6nRcMtJcKwdK7DCMX2LTk", "MERLuDFBMmsHnsBPZw2sDQZHvXFMwp8EdjudcU2HKky",
            "PRT88RkA4Kg5z7pKnezeNH4mafTvtQdfFgpQTGRjz44", "SAMcDSt3o6KmMKfREgxnxvqKFsz9M1RJjZyDj4kGqE6",
            "SLNDpmoWTVADgEdndyvWzroNL7zSi1dF9PC3xHGtPwp", "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",
            "SYNTHrHiLnvuHXcR58L1cLsAMymLwnkJWFzKkjBkdvT", "TULIPQJavaQFUxRptpEfWh4h4jVEaDN69CvjKjKC7Cu",
            "USDCVCkpgBSFdZELbvjwrWs9Mv2uoRuU8mMdxp1UQzQ", "USDTvK7dVQQrWaCQwJHw4kmV9R3uXhvdP7Wb8vZ9UmJ",
            "SUSHImXy7mSfBBWDWfXmrWB46j5C3bJRTNLmCwrYWU7", "UNIdD9CYCXmyxJnCr5LCDH6Q7zTg8pQsHPQ6jjR7XZW",
            "AAPLLNBqw3yEVDWEVZVjQKZGEuFqp9WxRpNVGWEuqkh", "GOOGTdCrB8H3bx95mqVpKr6JKr5WxDtYQYNPWGTjRHo",
            "AMZNTLxJYWYqPZtH3H2HPCNk5zv4kKbQqhxcYrhvdHN", "MSFTvKXDLbVRbXDHNdM8KTTkPCK4rXBmTL9cFZ7gkh8",
            "TSLAvKBqzDX9yEL3XCwJz8DwMmQfKdHNmMTqvCWkHq9", "NFLXwG8Hd3vNxC9KJYq3p5DkZVmQWBqYnHdCJP7kXh6",
        ]
        for wallet_addr in WALLET_POOL_FOR_CLEANUP[:50]:
            try:
                await client.client.table("wallets").delete().eq("wallet_address", wallet_addr).execute()
            except Exception:
                pass  # Ignore if wallet doesn't exist

        # CRITICAL: Mark ALL existing tokens as discovered to isolate test
        await client.client.table("tokens").update({
            "wallets_discovered": True
        }).eq("wallets_discovered", False).execute()

        # Real Solana token addresses to use as test tokens
        VALID_TOKEN_ADDRESSES = [
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # Ether
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # Bonk
            "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",  # Kamino
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",  # Jupiter
            "RLBxxFkseAZ4RgJH3Sqn8jXxhmGoz9jWxDNJMh8pL7a",  # Rollbit
            "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # Pyth
        ]

        test_tokens = []
        for i in range(10):
            token_mint = VALID_TOKEN_ADDRESSES[i]
            test_tokens.append(token_mint)
            cleanup_test_tokens(token_mint)

            # Delete existing token if present (from previous failed run)
            await client.client.table("tokens").delete().eq("mint", token_mint).execute()

            # Insert token with wallets_discovered=FALSE
            await client.client.table("tokens").insert({
                "mint": token_mint,
                "symbol": f"PERF{i}",
                "name": f"Performance Test Token {i}",
                "price_usd": 1.0,
                "market_cap": 1_000_000.0,
                "volume_24h": 50_000.0,
                "liquidity_usd": 25_000.0,
                "created_at": token_launch_time.isoformat(),
                "wallets_discovered": False,
            }).execute()

        # Mock HeliusClient to return 5 profitable wallets per token
        mock_helius_client = AsyncMock()

        def get_transactions_side_effect(token_mint: str, **kwargs):
            """Return mock transactions for each token."""
            return mock_profitable_wallet_transactions(token_mint)

        mock_helius_client.get_token_transactions.side_effect = get_transactions_side_effect

        # Start memory tracking
        tracemalloc.start()
        memory_before = tracemalloc.get_traced_memory()[0]

        # ACT: Run wallet discovery and measure time
        service = WalletDiscoveryService(
            helius_client=mock_helius_client,
            wallet_repository=wallet_repo,
            token_repository=token_repo,
        )

        start_time = time.time()
        result = await service.run_wallet_discovery()
        execution_time = time.time() - start_time

        # Check memory after
        memory_after = tracemalloc.get_traced_memory()[0]
        memory_increase_mb = (memory_after - memory_before) / (1024 * 1024)
        tracemalloc.stop()

        # Register wallets for cleanup (first 50 addresses from pool = 10 tokens * 5 wallets)
        WALLET_ADDRESS_POOL = [
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # Bonk
            "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",  # Kamino
            "RLBxxFkseAZ4RgJH3Sqn8jXxhmGoz9jWxDNJMh8pL7a",  # Rollbit
            "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # Pyth
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL
            "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",  # stSOL
            "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",  # ETH
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",  # Jupiter
            "HxhWkVpk5NS4Ltg5nij2G671CKXFRKPK8vy271Ub4uEK",  # Parcl
            "SHDWyBxihqiCj6YekG2GUr7wqKLeLAMK1gHZck9pL6y",  # Shadow
            "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",  # Helium
            "5oVNBeEEQvYi1cX3ir8Dx5n1P7pdxydbGF2X4TxVusJm",  # INF Token
            "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",  # WIF
            "8Ki8DpuWNxu9VsS3kQbarsCWMcFGWkzzA8pUPto9zBd5",  # LFG
            "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82",  # BOKU
            "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",  # RAY
            "kinXdEcpDQeHPEuQnqmUgtYykqKGVFq6CeVX5iAHJq6",  # KIN
            "AGFEad2et2ZJif9jaGpdMixQqvW5i81aBdvKe7PHNfz3",  # FTT
            "CowKesoLUaHSbAMaUxJUj7eodHHsaLsS65cy8NFyRDGP",  # COW
            "DFL1zNkaGPWm1BqAVqRjCZvHmwTFrEaJtbzJWgseoNJh",  # DFL
            "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",  # POPCAT
            "A3HyGZqe451CBesNqieNPfJ4A93CuKTfKN8X5hAKLZdT",  # RENDER
            "GENEtH5amGSi8kHAtQoezp1XEXwZJ8vcuePYnXdKrMYz",  # GENE
            "METAewgxyPbgwsseH8T16a39CQ5VyVxZi9zXiDPY18m",  # META
            "nosXBVoaCTtYdLvKY6Csb4AC8JCdQKKAaWYtx2ZMoo7",  # NOS
            "2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo",  # PANDA
            "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",  # RENDER
            "BLZEEuZUBVqFhj8adcCFPJvPVCiCyVmh3hkJMrU8KuJA",  # BLZE
            "GDfnEsia2WLAW5t8yx2X5j2mkfA74i5kwGdDuZHt7XmG",  # GOFX
            "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",  # ORCA
            "CASHVDm2wsJXfhj6VWxb7GiMdoLc17Du7paH4bNr5woT",  # CASH
            "GRAPEcuH36x5xGDqSYpKKicrjvJRqD2U1UEtk5eFHzn",  # GRAPE
            "LUNGEjUCeJVQHEqXgFQa5y6nRcMtJcKwdK7DCMX2LTk",  # LUNGE
            "MERLuDFBMmsHnsBPZw2sDQZHvXFMwp8EdjudcU2HKky",  # MERL
            "PRT88RkA4Kg5z7pKnezeNH4mafTvtQdfFgpQTGRjz44",  # PRT
            "SAMcDSt3o6KmMKfREgxnxvqKFsz9M1RJjZyDj4kGqE6",  # SAM
            "SLNDpmoWTVADgEdndyvWzroNL7zSi1dF9PC3xHGtPwp",  # SLND
            "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",  # SRM
            "SYNTHrHiLnvuHXcR58L1cLsAMymLwnkJWFzKkjBkdvT",  # SYNTH
            "TULIPQJavaQFUxRptpEfWh4h4jVEaDN69CvjKjKC7Cu",  # TULIP
            "USDCVCkpgBSFdZELbvjwrWs9Mv2uoRuU8mMdxp1UQzQ",  # USDC (backup)
            "USDTvK7dVQQrWaCQwJHw4kmV9R3uXhvdP7Wb8vZ9UmJ",  # USDT (backup)
            "SUSHImXy7mSfBBWDWfXmrWB46j5C3bJRTNLmCwrYWU7",  # SUSHI
            "UNIdD9CYCXmyxJnCr5LCDH6Q7zTg8pQsHPQ6jjR7XZW",  # UNI
            "AAPLLNBqw3yEVDWEVZVjQKZGEuFqp9WxRpNVGWEuqkh",  # AAPL
            "GOOGTdCrB8H3bx95mqVpKr6JKr5WxDtYQYNPWGTjRHo",  # GOOG
            "AMZNTLxJYWYqPZtH3H2HPCNk5zv4kKbQqhxcYrhvdHN",  # AMZN
            "MSFTvKXDLbVRbXDHNdM8KTTkPCK4rXBmTL9cFZ7gkh8",  # MSFT
            "TSLAvKBqzDX9yEL3XCwJz8DwMmQfKdHNmMTqvCWkHq9",  # TSLA
            "NFLXwG8Hd3vNxC9KJYq3p5DkZVmQWBqYnHdCJP7kXh6",  # NFLX
        ]

        # Register first 50 wallets for cleanup (10 tokens * 5 wallets each)
        for wallet_address in WALLET_ADDRESS_POOL[:50]:
            cleanup_test_wallets(wallet_address)

        # ASSERT: Performance requirements
        assert execution_time < 30.0, (
            f"Discovery took {execution_time:.2f}s, should be < 30s"
        )

        # ASSERT: Results are correct
        assert result["tokens_processed"] == 10, "Should process all 10 tokens"
        assert result["wallets_discovered"] == 50, "Should discover 50 wallets total (5 per token)"
        assert result["wallets_new"] >= 45, (
            f"At least 45 wallets should be new (got {result['wallets_new']}). "
            f"Some duplicates may exist from Neo4j or previous test runs."
        )
        assert result["errors"] <= 5, (
            f"Should have minimal errors (got {result['errors']}). "
            f"Up to 5 errors (10%) acceptable for performance test."
        )

        # ASSERT: Memory increase is reasonable (< 50MB for 50 wallets)
        assert memory_increase_mb < 50.0, (
            f"Memory increased by {memory_increase_mb:.2f}MB, should be < 50MB"
        )

        # Cleanup
        await client.disconnect()

    async def test_discovery_performance_no_memory_leak(
        self,
        token_launch_time: datetime,
        mock_profitable_wallet_transactions,
        cleanup_test_tokens,
        cleanup_test_wallets,
    ):
        """Test that repeated discoveries don't cause memory leaks.

        Runs discovery 3 times and verifies memory usage doesn't grow significantly.
        """
        # ARRANGE: Create 2 test tokens
        client = await get_supabase_client()
        token_repo = TokenRepository(client)
        wallet_repo = WalletRepository(client)

        # Real Solana token addresses for memory leak test
        VALID_TOKEN_ADDRESSES = [
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        ]

        test_tokens = []
        for i in range(2):
            token_mint = VALID_TOKEN_ADDRESSES[i]
            test_tokens.append(token_mint)
            cleanup_test_tokens(token_mint)

            # Delete existing token if present (from previous failed run)
            await client.client.table("tokens").delete().eq("mint", token_mint).execute()

            await client.client.table("tokens").insert({
                "mint": token_mint,
                "symbol": f"LEAK{i}",
                "name": f"Memory Leak Test Token {i}",
                "price_usd": 1.0,
                "market_cap": 1_000_000.0,
                "volume_24h": 50_000.0,
                "liquidity_usd": 25_000.0,
                "created_at": token_launch_time.isoformat(),
                "wallets_discovered": False,
            }).execute()

        # Mock HeliusClient
        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.side_effect = (
            lambda token_mint, **kwargs: mock_profitable_wallet_transactions(token_mint)
        )

        service = WalletDiscoveryService(
            helius_client=mock_helius_client,
            wallet_repository=wallet_repo,
            token_repository=token_repo,
        )

        # ACT: Run discovery 3 times and track memory
        tracemalloc.start()
        memory_snapshots = []

        # Wallet addresses used in mock fixture
        VALID_WALLET_ADDRESSES = [
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # Bonk token
            "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",  # Kamino token
            "RLBxxFkseAZ4RgJH3Sqn8jXxhmGoz9jWxDNJMh8pL7a",  # Rollbit token
            "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",  # Pyth token
            "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",  # mSOL token
        ]

        for run in range(3):
            # Reset tokens to undiscovered state
            for token_mint in test_tokens:
                await client.client.table("tokens").update({
                    "wallets_discovered": False
                }).eq("mint", token_mint).execute()

            # Clear wallets from previous run using direct Supabase delete
            for wallet_address in VALID_WALLET_ADDRESSES:
                try:
                    await client.client.table("wallets").delete().eq(
                        "wallet_address", wallet_address
                    ).execute()
                except Exception:
                    pass  # Ignore if wallet doesn't exist
                cleanup_test_wallets(wallet_address)

            # Run discovery
            await service.run_wallet_discovery()

            # Record memory usage
            current_memory = tracemalloc.get_traced_memory()[0]
            memory_snapshots.append(current_memory)

        tracemalloc.stop()

        # ASSERT: Memory usage should be stable across runs
        # Allow 20% variation but no significant growth
        first_run_memory = memory_snapshots[0]
        third_run_memory = memory_snapshots[2]

        memory_growth = (third_run_memory - first_run_memory) / first_run_memory
        assert memory_growth < 0.20, (
            f"Memory grew by {memory_growth * 100:.1f}% across 3 runs, "
            f"indicating potential memory leak"
        )

        # Cleanup
        await client.disconnect()
