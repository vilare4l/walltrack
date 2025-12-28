"""Shared pytest fixtures for WallTrack tests.

This module provides fixtures for:
- Database clients (Neo4j, Supabase) with automatic cleanup
- External API mocking (Helius, Jupiter, DexScreener)
- Test data factories
- Common test utilities

Usage:
    @pytest.mark.unit
    def test_something(wallet_factory):
        wallet = wallet_factory()
        assert wallet.score >= 0
"""

import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

# Import factories (will be created in tests/factories/)
from tests.factories.signal import SignalFactory
from tests.factories.trade import TradeFactory
from tests.factories.wallet import WalletFactory

# =============================================================================
# Environment Configuration
# =============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> Generator[None, None, None]:
    """Set up test environment variables.

    Loads .env file first, then sets defaults for any missing variables.
    """
    from dotenv import load_dotenv

    original_env = os.environ.copy()

    # Load .env file if it exists (won't override existing env vars)
    load_dotenv()

    # Set test-specific environment variables (only if not already set)
    os.environ.setdefault("WALLTRACK_ENV", "test")
    os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
    os.environ.setdefault("NEO4J_USER", "neo4j")
    os.environ.setdefault("NEO4J_PASSWORD", "neo4jpass")
    os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
    os.environ.setdefault("SUPABASE_KEY", "test-key")

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# =============================================================================
# Factory Fixtures
# =============================================================================


@pytest.fixture
def wallet_factory() -> type[WalletFactory]:
    """Provide wallet factory for creating test wallets."""
    return WalletFactory


@pytest.fixture
def signal_factory() -> type[SignalFactory]:
    """Provide signal factory for creating test signals."""
    return SignalFactory


@pytest.fixture
def trade_factory() -> type[TradeFactory]:
    """Provide trade factory for creating test trades."""
    return TradeFactory


# =============================================================================
# Mock External APIs
# =============================================================================


@pytest.fixture
def mock_helius_client() -> MagicMock:
    """Mock Helius API client.

    Returns a mock that simulates Helius webhook and API responses.
    """
    mock = MagicMock()
    mock.verify_signature = MagicMock(return_value=True)
    mock.get_wallet_transactions = AsyncMock(return_value=[])
    mock.create_webhook = AsyncMock(
        return_value={"webhookID": "test-webhook-id", "webhookURL": "https://test.com/webhook"}
    )
    return mock


@pytest.fixture
def mock_jupiter_client() -> MagicMock:
    """Mock Jupiter API client.

    Returns a mock that simulates swap quotes and execution.
    """
    mock = MagicMock()
    mock.get_quote = AsyncMock(
        return_value={
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": "TokenMintAddress",
            "inAmount": "1000000000",
            "outAmount": "1000000",
            "priceImpactPct": "0.01",
        }
    )
    mock.execute_swap = AsyncMock(
        return_value={"txid": "test-transaction-signature", "status": "success"}
    )
    return mock


@pytest.fixture
def mock_dexscreener_client() -> MagicMock:
    """Mock DexScreener API client.

    Returns a mock that simulates token data responses.
    """
    mock = MagicMock()
    mock.get_token_info = AsyncMock(
        return_value={
            "pairs": [
                {
                    "baseToken": {"address": "TokenMintAddress", "symbol": "TEST"},
                    "priceUsd": "0.001",
                    "liquidity": {"usd": 50000},
                    "volume": {"h24": 10000},
                }
            ]
        }
    )
    return mock


# =============================================================================
# Database Fixtures (Mocked for Unit Tests)
# =============================================================================


@pytest.fixture
def mock_neo4j_session() -> MagicMock:
    """Mock Neo4j session for unit tests.

    For integration tests, use `neo4j_session` fixture instead.
    """
    mock = MagicMock()
    mock.run = AsyncMock(return_value=MagicMock(data=lambda: []))
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Mock Supabase client for unit tests.

    For integration tests, use `supabase_client` fixture instead.
    """
    mock = MagicMock()

    # Mock table operations
    table_mock = MagicMock()
    table_mock.select = MagicMock(return_value=table_mock)
    table_mock.insert = MagicMock(return_value=table_mock)
    table_mock.update = MagicMock(return_value=table_mock)
    table_mock.delete = MagicMock(return_value=table_mock)
    table_mock.eq = MagicMock(return_value=table_mock)
    table_mock.execute = MagicMock(return_value=MagicMock(data=[]))

    mock.table = MagicMock(return_value=table_mock)
    return mock


# =============================================================================
# Integration Test Fixtures
# =============================================================================


@pytest.fixture
async def neo4j_session() -> AsyncGenerator[Any, None]:
    """Real Neo4j session for integration tests.

    Automatically cleans up test data after each test.
    Skip if Neo4j is not available.
    """
    pytest.importorskip("neo4j")

    try:
        from neo4j import AsyncGraphDatabase

        uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = os.environ.get("NEO4J_USER", "neo4j")
        password = os.environ.get("NEO4J_PASSWORD", "testpassword")

        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

        async with driver.session() as session:
            # Mark test data for cleanup
            yield session

            # Cleanup: delete all test nodes
            await session.run("MATCH (n) WHERE n._test = true DETACH DELETE n")

        await driver.close()

    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}")


@pytest.fixture
async def supabase_client() -> AsyncGenerator[Any, None]:
    """Real Supabase client for integration tests.

    Uses transaction rollback for cleanup.
    Skip if Supabase is not available.
    """
    pytest.importorskip("supabase")

    try:
        from supabase import create_client

        url = os.environ.get("SUPABASE_URL", "http://localhost:54321")
        key = os.environ.get("SUPABASE_KEY", "test-key")

        client = create_client(url, key)
        yield client

        # Cleanup is handled by test transaction rollback
        # or explicit deletion in tests

    except Exception as e:
        pytest.skip(f"Supabase not available: {e}")


# =============================================================================
# HTTP Client Fixtures
# =============================================================================


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for API testing."""
    async with AsyncClient() as client:
        yield client


# =============================================================================
# Time Fixtures
# =============================================================================


@pytest.fixture
def frozen_time() -> datetime:
    """Provide a fixed datetime for deterministic tests."""
    return datetime(2025, 1, 15, 12, 0, 0)


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def valid_solana_address() -> str:
    """Provide a valid Solana wallet address format."""
    return "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"


@pytest.fixture
def valid_token_mint() -> str:
    """Provide a valid SPL token mint address."""
    return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


@pytest.fixture
def sample_webhook_payload() -> dict[str, Any]:
    """Provide a sample Helius webhook payload."""
    return {
        "type": "TRANSFER",
        "timestamp": 1705320000,
        "signature": "test-signature-123",
        "slot": 123456789,
        "nativeTransfers": [
            {
                "fromUserAccount": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                "toUserAccount": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "amount": 1000000000,
            }
        ],
        "tokenTransfers": [],
    }


# =============================================================================
# Markers for Test Selection
# =============================================================================

# Usage:
# pytest -m unit          # Run only unit tests
# pytest -m integration   # Run only integration tests
# pytest -m e2e           # Run only E2E tests
# pytest -m "not slow"    # Skip slow tests
