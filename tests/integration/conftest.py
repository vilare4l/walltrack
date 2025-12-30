"""Integration test fixtures for wallet discovery.

Provides automatic cleanup fixtures for Supabase and Neo4j test data.
These fixtures run automatically after each test to ensure clean state.
"""

import pytest


@pytest.fixture
async def supabase_client():
    """Provide Supabase client for integration tests."""
    from walltrack.data.supabase.client import get_supabase_client

    client = await get_supabase_client()
    yield client
    await client.disconnect()


@pytest.fixture(autouse=True)
async def cleanup_test_wallets():
    """Automatically clean up test wallets from Supabase after each test.

    Runs after every integration test to remove any wallets created with
    test prefixes (Wallet1Test, Wallet2Test, etc.).

    This ensures test isolation and prevents test data pollution.
    """
    # Track wallets to clean up
    test_wallet_addresses = []

    # Provide collection mechanism for tests
    def register_wallet(address: str):
        """Register a wallet address for cleanup."""
        if address not in test_wallet_addresses:
            test_wallet_addresses.append(address)

    # Make available via fixture
    yield register_wallet

    # CLEANUP: Remove all registered test wallets
    if test_wallet_addresses:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

        client = await get_supabase_client()
        repo = WalletRepository(client)

        for address in test_wallet_addresses:
            try:
                await repo.delete_by_address(address)
            except Exception:
                pass  # Ignore errors (wallet may not exist)

        await client.disconnect()


@pytest.fixture(autouse=True)
async def cleanup_test_tokens():
    """Automatically clean up test tokens from Supabase after each test.

    Runs after every integration test to remove any tokens created with
    test mint addresses (EPjFWdd5..., etc.).

    This ensures test isolation and prevents test data pollution.
    """
    # Track tokens to clean up
    test_token_mints = []

    # Provide collection mechanism for tests
    def register_token(mint: str):
        """Register a token mint for cleanup."""
        if mint not in test_token_mints:
            test_token_mints.append(mint)

    # Make available via fixture
    yield register_token

    # CLEANUP: Remove all registered test tokens
    if test_token_mints:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.token_repo import TokenRepository

        client = await get_supabase_client()
        repo = TokenRepository(client)

        for mint in test_token_mints:
            try:
                await repo.delete_by_mint(mint)
            except Exception:
                pass  # Ignore errors (token may not exist)

        await client.disconnect()


@pytest.fixture(autouse=True)
async def cleanup_test_neo4j_nodes():
    """Automatically clean up test wallet nodes from Neo4j after each test.

    Runs after every integration test to remove any Wallet nodes created
    with test wallet addresses.

    This ensures test isolation in Neo4j graph database.
    """
    # Track nodes to clean up
    test_wallet_addresses = []

    # Provide collection mechanism for tests
    def register_neo4j_wallet(address: str):
        """Register a wallet node for Neo4j cleanup."""
        if address not in test_wallet_addresses:
            test_wallet_addresses.append(address)

    # Make available via fixture
    yield register_neo4j_wallet

    # CLEANUP: Remove all registered test wallet nodes
    if test_wallet_addresses:
        from walltrack.data.neo4j.client import get_neo4j_client

        client = await get_neo4j_client()

        try:
            async with client.session() as session:
                # Delete wallet nodes matching test addresses
                for address in test_wallet_addresses:
                    try:
                        await session.run(
                            "MATCH (w:Wallet {wallet_address: $wallet_address}) DELETE w",
                            wallet_address=address
                        )
                    except Exception:
                        pass  # Ignore errors (node may not exist)
        finally:
            await client.disconnect()
