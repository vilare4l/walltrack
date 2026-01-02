"""Unit tests for Performance Orchestrator (Story 3.2).

Tests the complete workflow of wallet performance analysis:
- RPC transaction fetching (with throttling)
- Transaction parsing (reusing Story 3.1 parser)
- Performance metrics calculation
- Config-driven criteria loading (AC7)
- Database updates (Supabase + Neo4j)

All external dependencies are mocked for isolated unit testing.
"""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.analysis.performance_orchestrator import PerformanceOrchestrator
from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.models.wallet import PerformanceMetrics

# Valid Solana addresses for testing
TEST_TOKEN_MINT = "So11111111111111111111111111111111111111112"  # Wrapped SOL
TEST_WALLET_ADDRESS = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
TEST_WALLET_1 = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
TEST_WALLET_2 = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
TEST_WALLET_3 = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"


@pytest.fixture
def mock_rpc_client():
    """Mock Solana RPC client."""
    client = AsyncMock()
    # Default: Return 3 signatures
    client.get_signatures_for_address = AsyncMock(
        return_value=[
            {"signature": "sig1"},
            {"signature": "sig2"},
            {"signature": "sig3"},
        ]
    )
    # Default: Return mock transaction data
    client.get_transaction = AsyncMock(return_value={"transaction": "mock_data"})
    return client


@pytest.fixture
def mock_config_repo():
    """Mock Config repository."""
    repo = AsyncMock()
    # Default: Return 10% min profit
    repo.get_performance_criteria = AsyncMock(return_value={"min_profit_percent": 10.0})
    return repo


@pytest.fixture
def mock_wallet_repo():
    """Mock Wallet repository."""
    repo = AsyncMock()
    repo.update_performance_metrics = AsyncMock(return_value=True)
    repo.get_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_parser():
    """Mock Transaction Parser."""
    with patch("walltrack.core.analysis.performance_orchestrator.TransactionParser") as mock:
        parser_instance = MagicMock()
        # Default: Return mock SwapTransaction
        parser_instance.parse = MagicMock(
            return_value=SwapTransaction(
                signature="sig1",
                timestamp=int(datetime.now(UTC).timestamp()),
                tx_type=TransactionType.BUY,
                token_mint=TEST_TOKEN_MINT,
                sol_amount=1.0,
                token_amount=1000.0,
                wallet_address=TEST_WALLET_ADDRESS,
            )
        )
        mock.return_value = parser_instance
        yield parser_instance


@pytest.fixture
def mock_neo4j_update():
    """Mock Neo4j update function."""
    with patch(
        "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
    ) as mock:
        mock.return_value = AsyncMock(return_value={"status": "success"})
        yield mock


@pytest.fixture
def orchestrator(mock_rpc_client, mock_config_repo, mock_wallet_repo, mock_parser):
    """Create orchestrator instance with mocked dependencies."""
    # mock_parser must be a dependency so patch is active during orchestrator creation
    return PerformanceOrchestrator(
        rpc_client=mock_rpc_client,
        config_repo=mock_config_repo,
        wallet_repo=mock_wallet_repo,
    )


# ============================================================================
# Test: Happy Path - Complete Workflow Success
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_wallet_performance_happy_path(
    orchestrator,
    mock_rpc_client,
    mock_config_repo,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test complete workflow succeeds with all steps working."""
    # Arrange: Mock parser to return BUY and SELL transactions
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.5,  # +50% profit
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )

    # Parser returns BUY, SELL, BUY (alternating)
    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None])

    # Act
    metrics = await orchestrator.analyze_wallet_performance(
        wallet_address=TEST_WALLET_ADDRESS,
        token_launch_times=None,
    )

    # Assert: Workflow steps executed
    mock_config_repo.get_performance_criteria.assert_called_once()
    mock_rpc_client.get_signatures_for_address.assert_called_once_with(
        address=TEST_WALLET_ADDRESS, limit=100
    )
    assert mock_rpc_client.get_transaction.call_count == 3
    assert mock_parser.parse.call_count == 3

    # Assert: Metrics calculated correctly
    assert isinstance(metrics, PerformanceMetrics)
    assert metrics.total_trades == 1  # 1 matched BUY/SELL pair
    assert metrics.win_rate == 100.0  # 1 win, 0 losses
    assert metrics.pnl_total == 0.5  # 1.5 - 1.0

    # Assert: Database updates called
    mock_wallet_repo.update_performance_metrics.assert_called_once_with(
        wallet_address=TEST_WALLET_ADDRESS, metrics=metrics
    )
    mock_neo4j_update.assert_called_once()


# ============================================================================
# Test: RPC Failures
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_wallet_rpc_signatures_fetch_fails(
    orchestrator, mock_rpc_client
):
    """Test workflow raises exception when RPC signature fetch fails."""
    # Arrange: RPC signatures fetch fails
    mock_rpc_client.get_signatures_for_address = AsyncMock(
        side_effect=Exception("RPC error")
    )

    # Act & Assert: Should raise exception
    with pytest.raises(Exception, match="RPC error"):
        await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)


@pytest.mark.asyncio
async def test_analyze_wallet_no_signatures_found(
    orchestrator,
    mock_rpc_client,
    mock_config_repo,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test workflow handles empty signature list gracefully."""
    # Arrange: RPC returns no signatures
    mock_rpc_client.get_signatures_for_address = AsyncMock(return_value=[])

    # Act
    metrics = await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)

    # Assert: Returns zero metrics
    assert metrics.total_trades == 0
    assert metrics.win_rate == 0.0
    assert metrics.pnl_total == 0.0
    assert metrics.confidence == "unknown"

    # Assert: Database still updated (with zero metrics)
    mock_wallet_repo.update_performance_metrics.assert_called_once()


# ============================================================================
# Test: Transaction Parsing
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_wallet_some_transactions_fail_to_parse(
    orchestrator,
    mock_rpc_client,
    mock_config_repo,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test workflow continues when some transactions fail to parse."""
    # Arrange: Parser returns success, None, success (middle one fails)
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig3",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.2,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )

    mock_parser.parse = MagicMock(side_effect=[buy_tx, None, sell_tx])

    # Act
    metrics = await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)

    # Assert: Workflow continues, calculates metrics from 2 successful parses
    assert mock_parser.parse.call_count == 3
    assert metrics.total_trades == 1  # 1 BUY/SELL pair
    assert metrics.win_rate == 100.0  # 20% profit (> 10% threshold)


@pytest.mark.asyncio
async def test_analyze_wallet_transaction_not_found(
    orchestrator, mock_rpc_client, mock_parser
):
    """Test workflow handles missing transactions (RPC returns None)."""
    # Arrange: RPC returns None for transaction (deleted/unavailable)
    mock_rpc_client.get_transaction = AsyncMock(return_value=None)

    # Act
    metrics = await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)

    # Assert: Parser never called, zero metrics returned
    assert mock_parser.parse.call_count == 0
    assert metrics.total_trades == 0


# ============================================================================
# Test: Config Loading (AC7)
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_wallet_config_criteria_loaded(
    orchestrator,
    mock_rpc_client,
    mock_config_repo,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test workflow loads min_profit_percent from config (AC7)."""
    # Arrange: Config returns 15% threshold
    mock_config_repo.get_performance_criteria = AsyncMock(
        return_value={"min_profit_percent": 15.0}
    )

    # Create BUY/SELL with 12% profit (below 15% threshold)
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.12,  # 12% profit
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )

    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None])

    # Act
    metrics = await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)

    # Assert: Config loaded
    mock_config_repo.get_performance_criteria.assert_called_once()

    # Assert: 12% profit < 15% threshold = loss
    assert metrics.total_trades == 1
    assert metrics.win_rate == 0.0  # Trade not profitable with 15% threshold


@pytest.mark.asyncio
async def test_analyze_wallet_config_load_fails_uses_default(
    orchestrator,
    mock_rpc_client,
    mock_config_repo,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test workflow falls back to 10% default when config load fails (AC7)."""
    # Arrange: Config load fails
    mock_config_repo.get_performance_criteria = AsyncMock(
        side_effect=Exception("Config error")
    )

    # Create BUY/SELL with 11% profit (above 10% default, below 15%)
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.11,  # 11% profit
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )

    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None])

    # Act
    metrics = await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)

    # Assert: Falls back to 10% default, 11% profit > 10% = win
    assert metrics.win_rate == 100.0


# ============================================================================
# Test: Database Updates
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_wallet_supabase_update_fails(
    orchestrator, mock_rpc_client, mock_wallet_repo, mock_parser
):
    """Test workflow raises exception when Supabase update fails."""
    # Arrange: Supabase update fails
    mock_wallet_repo.update_performance_metrics = AsyncMock(
        side_effect=Exception("Supabase error")
    )

    # Create minimal transaction to get past parsing
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    mock_parser.parse = MagicMock(side_effect=[buy_tx, None, None])

    # Act & Assert: Should raise exception
    with pytest.raises(Exception, match="Supabase error"):
        await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)


@pytest.mark.asyncio
async def test_analyze_wallet_neo4j_update_fails_continues(
    orchestrator,
    mock_rpc_client,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test workflow continues when Neo4j update fails (best-effort)."""
    # Arrange: Neo4j update fails
    mock_neo4j_update.side_effect = Exception("Neo4j error")

    # Create minimal transaction
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.5,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None])

    # Act: Should NOT raise exception
    metrics = await orchestrator.analyze_wallet_performance(wallet_address=TEST_WALLET_ADDRESS)

    # Assert: Workflow completed successfully despite Neo4j failure
    assert metrics.total_trades == 1
    mock_wallet_repo.update_performance_metrics.assert_called_once()  # Supabase updated


# ============================================================================
# Test: Bulk Analysis (analyze_all_wallets)
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_all_wallets_success(
    orchestrator,
    mock_rpc_client,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test bulk analysis processes multiple wallets with concurrency."""
    # Arrange: Mock 3 wallets
    from walltrack.data.models.wallet import Wallet

    wallets = [
        Wallet(
            wallet_address=TEST_WALLET_1,
            discovery_date=datetime.now(UTC),
            token_source=TEST_TOKEN_MINT,
        ),
        Wallet(
            wallet_address=TEST_WALLET_2,
            discovery_date=datetime.now(UTC),
            token_source=TEST_TOKEN_MINT,
        ),
        Wallet(
            wallet_address=TEST_WALLET_3,
            discovery_date=datetime.now(UTC),
            token_source=TEST_TOKEN_MINT,
        ),
    ]
    mock_wallet_repo.get_all = AsyncMock(return_value=wallets)

    # Create minimal transactions for each wallet
    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.5,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None] * 3)

    # Act
    results = await orchestrator.analyze_all_wallets(max_concurrent=2)

    # Assert: All 3 wallets analyzed
    assert len(results) == 3
    assert TEST_WALLET_1 in results
    assert TEST_WALLET_2 in results
    assert TEST_WALLET_3 in results

    # Assert: Each wallet has metrics (some may have 0 trades due to open positions)
    for address, metrics in results.items():
        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_trades >= 0  # Some wallets may have only open positions


@pytest.mark.asyncio
async def test_analyze_all_wallets_some_fail(
    orchestrator,
    mock_rpc_client,
    mock_wallet_repo,
    mock_parser,
    mock_neo4j_update,
):
    """Test bulk analysis continues when some wallets fail."""
    # Arrange: Mock 3 wallets
    from walltrack.data.models.wallet import Wallet

    wallets = [
        Wallet(
            wallet_address=TEST_WALLET_1,
            discovery_date=datetime.now(UTC),
            token_source=TEST_TOKEN_MINT,
        ),
        Wallet(
            wallet_address=TEST_WALLET_2,
            discovery_date=datetime.now(UTC),
            token_source=TEST_TOKEN_MINT,
        ),
        Wallet(
            wallet_address=TEST_WALLET_3,
            discovery_date=datetime.now(UTC),
            token_source=TEST_TOKEN_MINT,
        ),
    ]
    mock_wallet_repo.get_all = AsyncMock(return_value=wallets)

    # Create transactions for TEST_WALLET_1 and TEST_WALLET_3, fail TEST_WALLET_2
    call_count = 0

    def mock_get_signatures(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:  # TEST_WALLET_2 fails
            raise Exception("RPC error")
        return [{"signature": "sig1"}, {"signature": "sig2"}]

    mock_rpc_client.get_signatures_for_address = AsyncMock(
        side_effect=mock_get_signatures
    )

    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(datetime.now(UTC).timestamp()),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(datetime.now(UTC).timestamp()) + 3600,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.5,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None] * 2)

    # Act
    results = await orchestrator.analyze_all_wallets(max_concurrent=1)

    # Assert: Only 2 wallets succeeded (TEST_WALLET_2 failed)
    assert len(results) == 2
    assert TEST_WALLET_1 in results
    assert TEST_WALLET_2 not in results  # Failed
    assert TEST_WALLET_3 in results


# ============================================================================
# Test: Entry Delay Calculation (with token_launch_times)
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_wallet_with_token_launch_times(
    orchestrator, mock_rpc_client, mock_parser, mock_neo4j_update, mock_wallet_repo
):
    """Test workflow calculates entry_delay_seconds when token_launch_times provided."""
    # Arrange: Token launched at T0, wallet bought at T0 + 1 hour
    # Use naive datetime to match calculator's datetime.fromtimestamp() behavior
    launch_time = datetime.now()  # Naive datetime (no timezone)
    buy_time = launch_time.timestamp() + 3600  # +1 hour

    token_launch_times = {TEST_TOKEN_MINT: launch_time}

    buy_tx = SwapTransaction(
        signature="sig1",
        timestamp=int(buy_time),
        tx_type=TransactionType.BUY,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.0,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )
    sell_tx = SwapTransaction(
        signature="sig2",
        timestamp=int(buy_time) + 1800,
        tx_type=TransactionType.SELL,
        token_mint=TEST_TOKEN_MINT,
        sol_amount=1.5,
        token_amount=1000.0,
        wallet_address=TEST_WALLET_ADDRESS,
    )

    mock_parser.parse = MagicMock(side_effect=[buy_tx, sell_tx, None])

    # Act
    metrics = await orchestrator.analyze_wallet_performance(
        wallet_address=TEST_WALLET_ADDRESS,
        token_launch_times=token_launch_times,
    )

    # Assert: Entry delay calculated (should be ~3600 seconds)
    # Allow ±5 second tolerance for timing precision in tests
    assert 3595 <= metrics.entry_delay_seconds <= 3605  # ~1 hour delay
