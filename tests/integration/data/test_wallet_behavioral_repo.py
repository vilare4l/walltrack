"""Integration tests for WalletRepository behavioral profile updates.

Tests repository operations for behavioral profiling data persistence
across both Supabase and Neo4j databases.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from walltrack.data.models.wallet import Wallet
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


@pytest.fixture
async def wallet_repo():
    """Fixture providing WalletRepository instance."""
    client = await get_supabase_client()
    return WalletRepository(client)


@pytest.fixture
async def test_wallet(wallet_repo):
    """Fixture providing a test wallet with valid Solana addresses."""
    wallet = Wallet(
        wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        discovery_date=datetime.now(UTC),
        token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        score=0.0,
        win_rate=0.0,
        pnl_total=None,
        entry_delay_seconds=None,
        total_trades=0,
        metrics_last_updated=None,
        metrics_confidence="unknown",
        decay_status="ok",
        is_blacklisted=False,
    )

    # Create wallet in DB
    created = await wallet_repo.upsert_wallet(wallet)

    yield created

    # Cleanup
    await wallet_repo.delete_by_address(created.wallet_address)


@pytest.mark.asyncio
async def test_update_behavioral_profile_supabase(wallet_repo, test_wallet):
    """Test behavioral profile update in Supabase."""
    # Update behavioral profile
    success = await wallet_repo.update_behavioral_profile(
        wallet_address=test_wallet.wallet_address,
        position_size_style="medium",
        position_size_avg=2.5,
        hold_duration_avg=7200,
        hold_duration_style="day_trader",
        behavioral_confidence="medium",
    )

    assert success is True

    # Verify update
    updated_wallet = await wallet_repo.get_by_address(test_wallet.wallet_address)
    assert updated_wallet is not None
    assert updated_wallet.position_size_style == "medium"
    assert updated_wallet.position_size_avg == Decimal("2.5")
    assert updated_wallet.hold_duration_avg == 7200
    assert updated_wallet.hold_duration_style == "day_trader"
    assert updated_wallet.behavioral_confidence == "medium"
    assert updated_wallet.behavioral_last_updated is not None


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires Neo4j connection - enable when Neo4j available")
async def test_update_behavioral_profile_neo4j(test_wallet):
    """Test behavioral profile update in Neo4j.

    Note: Skipped by default as Neo4j may not be running in CI.
    Run with: pytest -m "not skip" to include.
    """
    from walltrack.data.neo4j.queries import wallet as neo4j_wallet

    # Update Neo4j
    result = await neo4j_wallet.update_wallet_behavioral_profile(
        wallet_address=test_wallet.wallet_address,
        position_size_style="large",
        position_size_avg=10.0,
        hold_duration_avg=604800,
        hold_duration_style="position_trader",
    )

    assert result is not None
    assert result["wallet_address"] == test_wallet.wallet_address
    assert result["position_size_style"] == "large"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires both Supabase and Neo4j - enable for full integration tests")
async def test_dual_database_sync(wallet_repo, test_wallet):
    """Test that behavioral profile syncs to both databases.

    Note: Skipped by default. Enable when both DBs available.
    """
    # Update using full sync method
    success = await wallet_repo.update_behavioral_profile_full(
        wallet_address=test_wallet.wallet_address,
        position_size_style="small",
        position_size_avg=0.5,
        hold_duration_avg=1800,
        hold_duration_style="scalper",
        behavioral_confidence="high",
    )

    assert success is True

    # Verify Supabase
    supabase_wallet = await wallet_repo.get_by_address(test_wallet.wallet_address)
    assert supabase_wallet.position_size_style == "small"
    assert supabase_wallet.hold_duration_style == "scalper"

    # Verify Neo4j
    from walltrack.data.neo4j.queries import wallet as neo4j_wallet
    neo4j_result = await neo4j_wallet.get_wallet_by_address(test_wallet.wallet_address)
    assert neo4j_result["position_size_style"] == "small"
    assert neo4j_result["hold_duration_style"] == "scalper"
