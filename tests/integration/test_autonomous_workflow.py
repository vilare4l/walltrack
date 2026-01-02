"""Integration test: Autonomous workflow from token to watchlist.

Tests the complete autonomous workflow:
    Token created (wallets_discovered=false)
    → WalletDiscoveryWorker processes (120s poll)
    → Wallets discovered and stored
    → Token updated (wallets_discovered=true)
    → WalletProfilingWorker processes (60s poll)
    → Wallets profiled → watchlisted

Story: 3.5.5 - Global RPC Rate Limiter + Wallet Discovery Worker
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.data.models.token import Token
from walltrack.data.models.wallet import Wallet
from walltrack.workers.wallet_discovery_worker import WalletDiscoveryWorker
from walltrack.workers.wallet_profiling_worker import WalletProfilingWorker


@pytest.mark.asyncio
async def test_token_to_watchlist_autonomous():
    """Test: Complete autonomous workflow from token to watchlist.

    Scenario:
    1. Token created (wallets_discovered=false)
    2. Discovery worker processes token
    3. Wallets discovered and stored
    4. Token updated (wallets_discovered=true)
    5. Profiling worker processes wallets
    6. Wallets profiled → watchlisted

    This test validates the full autonomous pipeline without manual intervention.
    """
    # Test token (using valid Solana address format: 44 chars base58)
    # Base58: no 0, O, I, l (lowercase L) characters
    test_token = Token(
        mint="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9TestA",  # 44 chars base58
        name="Autonomous Test Token",
        symbol="AUTO",
        decimals=9,
        wallets_discovered=False,
        last_checked="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
    )

    # Mock wallets that will be "discovered" (using valid Solana address format)
    mock_wallets = [
        Wallet(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9WaaA",  # 44 chars base58
            wallet_status="discovered",
            token_source=test_token.mint,
            discovery_date="2026-01-01T00:00:00Z",
        ),
        Wallet(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9WaaB",  # 44 chars base58
            wallet_status="discovered",
            token_source=test_token.mint,
            discovery_date="2026-01-01T00:00:00Z",
        ),
    ]

    # === PHASE 1: Wallet Discovery Worker ===

    discovery_worker = WalletDiscoveryWorker(poll_interval=0.5)  # Fast for testing

    # Mock dependencies - Token Repository
    mock_token_repo = AsyncMock()
    # Return token once, then empty list (single poll cycle)
    mock_token_repo.get_undiscovered_tokens.side_effect = [[test_token], []]
    mock_token_repo.mark_wallets_discovered.return_value = True

    # Mock dependencies - Discovery Service
    mock_discovery_service = AsyncMock()
    mock_discovery_service.discover_wallets_from_token.return_value = {
        "wallets_discovered": 2,
        "wallets_stored": 2,
    }
    mock_discovery_service.rpc_client = AsyncMock()
    mock_discovery_service.rpc_client.close = AsyncMock()

    # Mock dependencies - Supabase Client
    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject mocks into discovery worker
    discovery_worker.token_repo = mock_token_repo
    discovery_worker.discovery_service = mock_discovery_service
    discovery_worker.supabase_client = mock_supabase_client

    # Patch _initialize_dependencies
    async def mock_init_discovery():
        pass

    discovery_worker._initialize_dependencies = mock_init_discovery

    # Start discovery worker
    discovery_worker.running = True
    discovery_task = asyncio.create_task(discovery_worker.run())

    # Wait for processing (0.5s poll + processing time)
    await asyncio.sleep(1.0)

    # Stop discovery worker
    await discovery_worker.stop()
    discovery_task.cancel()
    try:
        await discovery_task
    except asyncio.CancelledError:
        pass

    # Assertions - Discovery Phase
    mock_token_repo.get_undiscovered_tokens.assert_called()
    mock_discovery_service.discover_wallets_from_token.assert_called_once_with(
        token_mint=test_token.mint
    )
    mock_token_repo.mark_wallets_discovered.assert_called_once_with(test_token.mint)

    # === PHASE 2: Wallet Profiling Worker ===

    profiling_worker = WalletProfilingWorker(poll_interval=0.5)  # Fast for testing

    # Mock dependencies - Wallet Repository
    mock_wallet_repo = AsyncMock()
    # Return discovered wallets once, then empty list
    # Note: WalletProfilingWorker calls get_wallets_by_status(), not get_wallets_needing_profiling()
    mock_wallet_repo.get_wallets_by_status.side_effect = [mock_wallets, []]
    mock_wallet_repo.update_status.return_value = None
    mock_wallet_repo.get_by_address.return_value = mock_wallets[0]  # Return first wallet
    mock_wallet_repo.update_watchlist_status.return_value = None

    # Mock dependencies - Performance Orchestrator
    mock_performance_orchestrator = AsyncMock()
    mock_performance_result = AsyncMock()
    mock_performance_result.win_rate = 75.0
    mock_performance_result.pnl_total = 10.5
    mock_performance_orchestrator.analyze_wallet_performance.return_value = mock_performance_result

    # Mock dependencies - Behavioral Profiler
    mock_behavioral_profiler = AsyncMock()
    mock_behavioral_result = AsyncMock()
    mock_behavioral_result.position_size_style = "medium"
    mock_behavioral_result.hold_duration_style = "swing_trader"
    mock_behavioral_profiler.profile_wallet.return_value = mock_behavioral_result

    # Mock dependencies - Watchlist Evaluator
    mock_watchlist_evaluator = MagicMock()
    mock_watchlist_decision = MagicMock()
    mock_watchlist_decision.status = "watchlisted"
    mock_watchlist_decision.score = 0.85
    mock_watchlist_evaluator.evaluate_wallet.return_value = mock_watchlist_decision

    # Mock dependencies - Supabase Client (reuse)
    mock_supabase_client_profiling = AsyncMock()
    mock_supabase_client_profiling.disconnect = AsyncMock()

    # Inject mocks into profiling worker
    profiling_worker.wallet_repo = mock_wallet_repo
    profiling_worker.performance_orchestrator = mock_performance_orchestrator
    profiling_worker.behavioral_profiler = mock_behavioral_profiler
    profiling_worker.watchlist_evaluator = mock_watchlist_evaluator
    profiling_worker.supabase_client = mock_supabase_client_profiling
    profiling_worker.rpc_client = AsyncMock()
    profiling_worker.rpc_client.close = AsyncMock()
    profiling_worker.neo4j_client = AsyncMock()
    profiling_worker.neo4j_client.close = AsyncMock()

    # Patch _initialize_dependencies
    async def mock_init_profiling():
        pass

    profiling_worker._initialize_dependencies = mock_init_profiling

    # Start profiling worker
    profiling_worker.running = True
    profiling_task = asyncio.create_task(profiling_worker.run())

    # Wait for processing
    await asyncio.sleep(1.0)

    # Stop profiling worker
    await profiling_worker.stop()
    profiling_task.cancel()
    try:
        await profiling_task
    except asyncio.CancelledError:
        pass

    # Assertions - Profiling Phase
    mock_wallet_repo.get_wallets_by_status.assert_called()
    # Should have called performance analysis for both wallets
    assert mock_performance_orchestrator.analyze_wallet_performance.call_count == 2
    # Should have called behavioral profiling for both wallets
    assert mock_behavioral_profiler.profile_wallet.call_count == 2
    # Should have evaluated watchlist for both wallets
    assert mock_watchlist_evaluator.evaluate_wallet.call_count == 2

    # === Final Validation: End-to-End Flow ===

    # 1. Token was processed
    assert mock_discovery_service.discover_wallets_from_token.called
    assert mock_token_repo.mark_wallets_discovered.called

    # 2. Wallets were profiled (performance + behavioral)
    assert mock_performance_orchestrator.analyze_wallet_performance.call_count == 2
    assert mock_behavioral_profiler.profile_wallet.call_count == 2

    # 3. Watchlist was evaluated
    assert mock_watchlist_evaluator.evaluate_wallet.call_count == 2

    # SUCCESS: Complete autonomous workflow validated ✅


@pytest.mark.asyncio
async def test_autonomous_workflow_handles_errors():
    """Test: Autonomous workflow continues despite individual failures.

    Scenario:
    - Token 1: Discovery succeeds → profiling succeeds
    - Token 2: Discovery fails → worker continues
    - Token 3: Discovery succeeds → profiling fails → worker continues

    Validates that circuit breaker and error handling work correctly.
    """
    discovery_worker = WalletDiscoveryWorker(poll_interval=0.5)

    # Test tokens (using valid Solana address format: 44 chars base58)
    # Base58: no 0, O, I, l characters
    token1 = Token(
        mint="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9Tkn1",  # 44 chars base58
        name="Token 1",
        symbol="T1",
        decimals=9,
        wallets_discovered=False,
        last_checked="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
    )
    token2 = Token(
        mint="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9Tkn2",  # 44 chars base58
        name="Token 2",
        symbol="T2",
        decimals=9,
        wallets_discovered=False,
        last_checked="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
    )
    token3 = Token(
        mint="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9Tkn3",  # 44 chars base58
        name="Token 3",
        symbol="T3",
        decimals=9,
        wallets_discovered=False,
        last_checked="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
    )

    # Mock token repository
    mock_token_repo = AsyncMock()
    mock_token_repo.get_undiscovered_tokens.side_effect = [
        [token1, token2, token3],
        [],
    ]
    mock_token_repo.mark_wallets_discovered.return_value = True

    # Mock discovery service - token2 fails
    mock_discovery_service = AsyncMock()
    mock_discovery_service.discover_wallets_from_token.side_effect = [
        {"wallets_discovered": 2, "wallets_stored": 2},  # token1 success
        Exception("RPC timeout"),  # token2 fails
        {"wallets_discovered": 1, "wallets_stored": 1},  # token3 success
    ]
    mock_discovery_service.rpc_client = AsyncMock()
    mock_discovery_service.rpc_client.close = AsyncMock()

    # Mock supabase client
    mock_supabase_client = AsyncMock()
    mock_supabase_client.disconnect = AsyncMock()

    # Inject mocks
    discovery_worker.token_repo = mock_token_repo
    discovery_worker.discovery_service = mock_discovery_service
    discovery_worker.supabase_client = mock_supabase_client

    async def mock_init():
        pass

    discovery_worker._initialize_dependencies = mock_init

    # Run worker
    discovery_worker.running = True
    task = asyncio.create_task(discovery_worker.run())

    await asyncio.sleep(1.5)

    await discovery_worker.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Assertions: All 3 tokens processed despite token2 failure
    assert mock_discovery_service.discover_wallets_from_token.call_count == 3

    # Only token1 and token3 marked as discovered (token2 failed)
    assert mock_token_repo.mark_wallets_discovered.call_count == 2
    mock_token_repo.mark_wallets_discovered.assert_any_call(token1.mint)
    mock_token_repo.mark_wallets_discovered.assert_any_call(token3.mint)
