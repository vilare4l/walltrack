"""Integration tests for decay event repository.

Story 3.4 - Wallet Decay Detection
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from walltrack.data.models.decay_event import DecayEventCreate, DecayEventType
from walltrack.data.models.wallet import Wallet
from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


async def create_test_wallet(supabase_client, wallet_address: str):
    """Helper to create a test wallet in database."""
    wallet_repo = WalletRepository(supabase_client)
    wallet_data = Wallet(
        wallet_address=wallet_address,
        discovery_date=datetime.now(UTC),
        token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        score=0.85,
        decay_status="ok",
    )
    await wallet_repo.upsert_wallet(wallet_data)
    return wallet_address


# Valid base58 Solana addresses for testing (32-44 chars, base58 charset only)
TEST_WALLET_1 = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
TEST_WALLET_2 = "HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH"
TEST_WALLET_3 = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
TEST_WALLET_4 = "GUfCR9mK6azb9vcpsxgXyj7XRPAKJd4KMHTTVvtncGgp"
TEST_WALLET_5 = "CuieVDEDtLo7FypA9SbLM9saXFdb1dsshEkyErMqkRQq"
TEST_WALLET_6 = "F8Vyqk3unwxkXukZFQeYyGmFfTG3CAX4v24iyrjEYBJV"


@pytest.mark.integration
class TestDecayEventRepository:
    """Integration tests for DecayEventRepository with real Supabase."""

    @pytest.mark.asyncio
    async def test_create_decay_event(self, supabase_client):
        """Test creating decay event in database."""
        repo = DecayEventRepository(supabase_client)
        
        # Create wallet first (required for foreign key)
        await create_test_wallet(supabase_client, TEST_WALLET_1)

        # Create event
        event_data = DecayEventCreate(
            wallet_address=TEST_WALLET_1,
            event_type=DecayEventType.DECAY_DETECTED,
            rolling_win_rate=Decimal("0.35"),
            lifetime_win_rate=Decimal("0.62"),
            consecutive_losses=0,
            score_before=Decimal("0.8500"),
            score_after=Decimal("0.6800"),
        )

        created_event = await repo.create(event_data)

        # Verify
        assert created_event.id is not None
        assert created_event.wallet_address == TEST_WALLET_1
        assert created_event.event_type == DecayEventType.DECAY_DETECTED
        assert created_event.rolling_win_rate == Decimal("0.35")
        assert created_event.lifetime_win_rate == Decimal("0.62")
        assert created_event.consecutive_losses == 0
        assert created_event.score_before == Decimal("0.8500")
        assert created_event.score_after == Decimal("0.6800")
        assert created_event.created_at is not None

    @pytest.mark.asyncio
    async def test_get_wallet_events(self, supabase_client):
        """Test fetching events for specific wallet."""
        repo = DecayEventRepository(supabase_client)

        # Create wallet first (required for foreign key)
        await create_test_wallet(supabase_client, TEST_WALLET_2)
        
        # Create multiple events for same wallet
        event1 = DecayEventCreate(
            wallet_address=TEST_WALLET_2,
            event_type=DecayEventType.DECAY_DETECTED,
            rolling_win_rate=Decimal("0.35"),
            lifetime_win_rate=Decimal("0.65"),
            consecutive_losses=0,
            score_before=Decimal("0.85"),
            score_after=Decimal("0.68"),
        )
        event2 = DecayEventCreate(
            wallet_address=TEST_WALLET_2,
            event_type=DecayEventType.RECOVERY,
            rolling_win_rate=Decimal("0.55"),
            lifetime_win_rate=Decimal("0.67"),
            consecutive_losses=0,
            score_before=Decimal("0.68"),
            score_after=Decimal("0.748"),
        )

        await repo.create(event1)
        await repo.create(event2)

        # Fetch events
        events = await repo.get_wallet_events(TEST_WALLET_2, limit=10)

        # Verify
        assert len(events) >= 2
        # Should be ordered by created_at DESC (most recent first)
        assert events[0].event_type == DecayEventType.RECOVERY  # Latest
        assert events[1].event_type == DecayEventType.DECAY_DETECTED  # Earlier  # Earlier  # Earlier

    @pytest.mark.asyncio
    async def test_get_recent_events_all(self, supabase_client):
        """Test fetching recent events across all wallets."""
        repo = DecayEventRepository(supabase_client)

        # Create wallets first (required for foreign key)
        await create_test_wallet(supabase_client, TEST_WALLET_3)
        await create_test_wallet(supabase_client, TEST_WALLET_4)
        
        # Create events for different wallets
        event1 = DecayEventCreate(
            wallet_address=TEST_WALLET_3,
            event_type=DecayEventType.DECAY_DETECTED,
            rolling_win_rate=Decimal("0.35"),
            lifetime_win_rate=Decimal("0.65"),
            consecutive_losses=0,
            score_before=Decimal("0.85"),
            score_after=Decimal("0.68"),
        )
        event2 = DecayEventCreate(
            wallet_address=TEST_WALLET_4,
            event_type=DecayEventType.CONSECUTIVE_LOSSES,
            rolling_win_rate=Decimal("0.45"),
            lifetime_win_rate=Decimal("0.60"),
            consecutive_losses=5,
            score_before=Decimal("0.80"),
            score_after=Decimal("0.68"),
        )

        await repo.create(event1)
        await repo.create(event2)

        # Fetch recent events
        events = await repo.get_recent_events(limit=50)

        # Verify
        assert len(events) >= 2
        # Should include events from both wallets
        wallet_addresses = {e.wallet_address for e in events}
        assert TEST_WALLET_3 in wallet_addresses
        assert TEST_WALLET_4 in wallet_addresses

    @pytest.mark.asyncio
    async def test_get_recent_events_filtered_by_type(self, supabase_client):
        """Test fetching recent events filtered by event type."""
        repo = DecayEventRepository(supabase_client)

        # Create wallets first (required for foreign key)
        await create_test_wallet(supabase_client, TEST_WALLET_5)
        await create_test_wallet(supabase_client, TEST_WALLET_6)
        
        # Create different types of events
        decay_event = DecayEventCreate(
            wallet_address=TEST_WALLET_5,
            event_type=DecayEventType.DECAY_DETECTED,
            rolling_win_rate=Decimal("0.35"),
            lifetime_win_rate=Decimal("0.65"),
            consecutive_losses=0,
            score_before=Decimal("0.85"),
            score_after=Decimal("0.68"),
        )
        recovery_event = DecayEventCreate(
            wallet_address=TEST_WALLET_6,
            event_type=DecayEventType.RECOVERY,
            rolling_win_rate=Decimal("0.55"),
            lifetime_win_rate=Decimal("0.67"),
            consecutive_losses=0,
            score_before=Decimal("0.68"),
            score_after=Decimal("0.748"),
        )

        await repo.create(decay_event)
        await repo.create(recovery_event)

        # Fetch only recovery events
        recovery_events = await repo.get_recent_events(
            event_type="recovery", limit=50
        )

        # Verify: all returned events are recovery type
        assert len(recovery_events) >= 1
        assert all(e.event_type == DecayEventType.RECOVERY for e in recovery_events)

    @pytest.mark.asyncio
    async def test_count_by_type(self, supabase_client):
        """Test counting events by type."""
        repo = DecayEventRepository(supabase_client)

        # Get initial count
        initial_count = await repo.count_by_type("decay_detected")

        # Create wallet first (required for foreign key)
        await create_test_wallet(supabase_client, TEST_WALLET_1)
        
        # Create decay event
        event = DecayEventCreate(
            wallet_address=TEST_WALLET_1,
            event_type=DecayEventType.DECAY_DETECTED,
            rolling_win_rate=Decimal("0.35"),
            lifetime_win_rate=Decimal("0.65"),
            consecutive_losses=0,
            score_before=Decimal("0.85"),
            score_after=Decimal("0.68"),
        )
        await repo.create(event)

        # Get new count
        new_count = await repo.count_by_type("decay_detected")

        # Verify: count increased by 1
        assert new_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_create_with_null_values(self, supabase_client):
        """Test creating event with null optional fields."""
        repo = DecayEventRepository(supabase_client)

        # Create wallet first (required for foreign key)
        await create_test_wallet(supabase_client, TEST_WALLET_2)
        
        # Create event with minimal fields (dormancy event may have nulls)
        event_data = DecayEventCreate(
            wallet_address=TEST_WALLET_2,
            event_type=DecayEventType.DORMANCY,
            rolling_win_rate=None,  # NULL for dormant wallet
            lifetime_win_rate=None,
            consecutive_losses=0,
            score_before=None,
            score_after=None,
        )

        created_event = await repo.create(event_data)

        # Verify
        assert created_event.id is not None
        assert created_event.event_type == DecayEventType.DORMANCY
        assert created_event.rolling_win_rate is None
        assert created_event.lifetime_win_rate is None
        assert created_event.score_before is None
        assert created_event.score_after is None
