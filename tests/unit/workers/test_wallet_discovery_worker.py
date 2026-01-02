"""Unit tests for WalletDiscoveryWorker.

Tests:
- Worker processes undiscovered tokens
- Worker updates token flag (wallets_discovered=true)
- Worker handles single token errors gracefully
- Circuit breaker stops after 5 consecutive errors
- Worker stops gracefully on stop()

Story: 3.5.5 - Global RPC Rate Limiter + Wallet Discovery Worker
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.data.models.token import Token
from walltrack.workers.wallet_discovery_worker import WalletDiscoveryWorker


@pytest.fixture
def mock_token():
    """Create a mock token for testing."""
    return Token(
        mint="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9TstA",  # 44 chars - valid Solana address (base58)
        name="Test Token",
        symbol="TEST",
        decimals=9,
        wallets_discovered=False,
        last_checked="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
    )


@pytest.mark.asyncio
async def test_worker_processes_undiscovered_tokens(mock_token):
    """Test: Worker fetches and processes undiscovered tokens.

    AC3: Fetches tokens where wallets_discovered = false
    AC3: For each token: discovers smart money wallets
    """
    worker = WalletDiscoveryWorker(poll_interval=1)

    # Mock dependencies
    mock_token_repo = AsyncMock()
    # Return tokens once, then empty list (to prevent second poll cycle)
    mock_token_repo.get_undiscovered_tokens.side_effect = [[mock_token], []]
    mock_token_repo.mark_wallets_discovered.return_value = True

    mock_discovery_service = AsyncMock()
    mock_discovery_service.discover_wallets_from_token.return_value = {
        "wallets_discovered": 5,
        "wallets_stored": 3,
    }
    mock_discovery_service.rpc_client = AsyncMock()
    mock_discovery_service.rpc_client.close = AsyncMock()

    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject dependencies
    worker.token_repo = mock_token_repo
    worker.discovery_service = mock_discovery_service
    worker.supabase_client = mock_supabase_client

    # Patch _initialize_dependencies to avoid real client initialization
    async def mock_init():
        pass

    worker._initialize_dependencies = mock_init

    # Run worker for one iteration
    worker.running = True
    task = asyncio.create_task(worker.run())

    # Wait for processing
    await asyncio.sleep(1.5)

    # Stop worker
    await worker.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Assertions
    mock_token_repo.get_undiscovered_tokens.assert_called()
    mock_discovery_service.discover_wallets_from_token.assert_called_once_with(
        token_mint=mock_token.mint
    )
    mock_token_repo.mark_wallets_discovered.assert_called_once_with(mock_token.mint)


@pytest.mark.asyncio
async def test_worker_updates_token_flag(mock_token):
    """Test: Worker sets wallets_discovered = true after discovery.

    AC3: Updates token: wallets_discovered = true
    """
    worker = WalletDiscoveryWorker(poll_interval=1)

    # Mock dependencies
    mock_token_repo = AsyncMock()
    mock_token_repo.get_undiscovered_tokens.return_value = [mock_token]
    mock_token_repo.mark_wallets_discovered.return_value = True

    mock_discovery_service = AsyncMock()
    mock_discovery_service.discover_wallets_from_token.return_value = {
        "wallets_discovered": 2,
        "wallets_stored": 2,
    }
    mock_discovery_service.rpc_client = AsyncMock()
    mock_discovery_service.rpc_client.close = AsyncMock()

    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject dependencies
    worker.token_repo = mock_token_repo
    worker.discovery_service = mock_discovery_service
    worker.supabase_client = mock_supabase_client

    # Process single token
    await worker._process_token(mock_token.mint)

    # Verify token flag updated
    mock_token_repo.mark_wallets_discovered.assert_called_once_with(mock_token.mint)


@pytest.mark.asyncio
async def test_worker_error_handling(mock_token):
    """Test: Worker continues on single token failure (1 token ≠ worker crash).

    AC4: Error is logged with context
    AC4: Worker continues to next token
    """
    worker = WalletDiscoveryWorker(poll_interval=1)

    # Create 2 tokens: first fails, second succeeds
    token1 = mock_token
    token2 = Token(
        mint="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9TstB",  # 44 chars - valid Solana address (base58)
        name="Token 2",
        symbol="TOK2",
        decimals=9,
        wallets_discovered=False,
        last_checked="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
    )

    # Mock dependencies
    mock_token_repo = AsyncMock()
    # Return tokens once, then empty list (to prevent second poll cycle)
    mock_token_repo.get_undiscovered_tokens.side_effect = [[token1, token2], []]
    mock_token_repo.mark_wallets_discovered.return_value = True

    mock_discovery_service = AsyncMock()
    # First token fails, second succeeds
    mock_discovery_service.discover_wallets_from_token.side_effect = [
        Exception("RPC timeout"),
        {"wallets_discovered": 1, "wallets_stored": 1},
    ]
    mock_discovery_service.rpc_client = AsyncMock()
    mock_discovery_service.rpc_client.close = AsyncMock()

    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject dependencies
    worker.token_repo = mock_token_repo
    worker.discovery_service = mock_discovery_service
    worker.supabase_client = mock_supabase_client

    # Patch _initialize_dependencies to avoid real client initialization
    async def mock_init():
        pass

    worker._initialize_dependencies = mock_init

    # Run worker for one iteration
    worker.running = True
    task = asyncio.create_task(worker.run())

    # Wait for processing
    await asyncio.sleep(1.5)

    # Stop worker
    await worker.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Assertions: Both tokens processed despite first failure
    assert mock_discovery_service.discover_wallets_from_token.call_count == 2
    # Only second token marked (first failed)
    mock_token_repo.mark_wallets_discovered.assert_called_once_with(token2.mint)


@pytest.mark.asyncio
async def test_worker_circuit_breaker():
    """Test: Circuit breaker stops worker after 5 consecutive errors.

    AC4: Circuit breaker stops worker after 5 consecutive errors
    """
    worker = WalletDiscoveryWorker(poll_interval=0.1)  # Fast polls for testing

    # Mock dependencies
    mock_token_repo = AsyncMock()
    # Always raise exception
    mock_token_repo.get_undiscovered_tokens.side_effect = Exception("DB connection lost")

    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject dependencies
    worker.token_repo = mock_token_repo
    worker.supabase_client = mock_supabase_client

    # Patch _initialize_dependencies to avoid real client initialization
    async def mock_init():
        pass

    worker._initialize_dependencies = mock_init

    # Run worker (will hit circuit breaker)
    worker.running = True
    task = asyncio.create_task(worker.run())

    # Wait for circuit breaker (5 errors × 0.1s poll + backoff ~31s total)
    # Backoff: 2^1=2s, 2^2=4s, 2^3=8s, 2^4=16s, 2^5=32s
    await asyncio.sleep(35)

    # Worker should have stopped itself
    assert not worker.running, "Worker should stop after 5 consecutive errors"

    # Cleanup
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_worker_graceful_shutdown():
    """Test: Worker stops cleanly on stop().

    AC5: Worker stops gracefully (finishes current token)
    AC5: Worker closes RPC client
    AC5: Worker task is cancelled properly
    """
    worker = WalletDiscoveryWorker(poll_interval=10)  # Long poll to test shutdown

    # Mock dependencies
    mock_token_repo = AsyncMock()
    mock_token_repo.get_undiscovered_tokens.return_value = []

    mock_discovery_service = AsyncMock()
    mock_discovery_service.rpc_client = AsyncMock()
    mock_discovery_service.rpc_client.close = AsyncMock()

    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject dependencies
    worker.token_repo = mock_token_repo
    worker.discovery_service = mock_discovery_service
    worker.supabase_client = mock_supabase_client

    # Patch _initialize_dependencies to avoid real client initialization
    async def mock_init():
        pass

    worker._initialize_dependencies = mock_init

    # Start worker
    worker.running = True
    task = asyncio.create_task(worker.run())

    # Let it start
    await asyncio.sleep(0.5)

    # Stop worker
    await worker.stop()

    # Wait for task to finish
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Assertions
    assert not worker.running, "Worker should be stopped"
    mock_discovery_service.rpc_client.close.assert_called_once()
    mock_supabase_client.disconnect.assert_called_once()
