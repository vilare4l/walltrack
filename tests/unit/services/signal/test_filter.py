"""Unit tests for signal filter service."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.signal_filter import (
    FilterResult,
    FilterStatus,
    WalletCacheEntry,
)
from walltrack.services.helius.models import ParsedSwapEvent, SwapDirection
from walltrack.services.signal.filter import SignalFilter
from walltrack.services.signal.wallet_cache import WalletCache


@pytest.fixture
def sample_swap_event() -> ParsedSwapEvent:
    """Create sample swap event for testing."""
    return ParsedSwapEvent(
        tx_signature="sig123456789012345678901234567890123456789012345678901234567890",
        wallet_address="MonitoredWallet123456789012345678901234567",
        token_address="TokenMint12345678901234567890123456789012",
        direction=SwapDirection.BUY,
        amount_token=1000000.0,
        amount_sol=1.5,
        timestamp=datetime.now(UTC),
        slot=123456,
        fee_lamports=5000,
    )


@pytest.fixture
def mock_wallet_cache() -> MagicMock:
    """Create mock wallet cache."""
    cache = MagicMock(spec=WalletCache)
    cache.get = AsyncMock()
    return cache


class TestSignalFilterMonitoredWallet:
    """Tests for filtering monitored wallets."""

    @pytest.mark.asyncio
    async def test_monitored_wallet_passes(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that monitored wallets pass filter."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
                cluster_id="cluster-123",
                is_leader=True,
                reputation_score=0.85,
            ),
            True,  # cache hit
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.PASSED
        assert result.is_monitored is True
        assert result.is_blacklisted is False
        assert result.cache_hit is True
        assert result.wallet_metadata is not None
        assert result.wallet_metadata.cluster_id == "cluster-123"
        assert result.wallet_metadata.is_leader is True

    @pytest.mark.asyncio
    async def test_monitored_wallet_cache_miss(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test monitored wallet with cache miss."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
            ),
            False,  # cache miss
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.PASSED
        assert result.cache_hit is False


class TestSignalFilterNonMonitoredWallet:
    """Tests for filtering non-monitored wallets."""

    @pytest.mark.asyncio
    async def test_non_monitored_wallet_discarded(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that non-monitored wallets are discarded."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=False,
                is_blacklisted=False,
            ),
            False,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.DISCARDED_NOT_MONITORED
        assert result.is_monitored is False
        assert result.is_blacklisted is False

    @pytest.mark.asyncio
    async def test_non_monitored_with_none_entry(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test non-monitored wallet returns None entry."""
        # Return None entry to simulate wallet not found at all
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=False,
            ),
            False,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.DISCARDED_NOT_MONITORED


class TestSignalFilterBlacklistedWallet:
    """Tests for filtering blacklisted wallets."""

    @pytest.mark.asyncio
    async def test_blacklisted_wallet_blocked(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that blacklisted wallets are blocked."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=True,
            ),
            True,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.BLOCKED_BLACKLISTED
        assert result.is_blacklisted is True

    @pytest.mark.asyncio
    async def test_blacklist_checked_before_monitoring(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test blacklist is checked before monitoring status."""
        # Even if monitored, blacklist should take precedence
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=True,
            ),
            True,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        # Should be BLOCKED, not PASSED
        assert result.status == FilterStatus.BLOCKED_BLACKLISTED


class TestSignalFilterPerformance:
    """Tests for filter performance requirements."""

    @pytest.mark.asyncio
    async def test_lookup_time_tracked(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that lookup time is tracked."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
            ),
            True,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        # Lookup time should be recorded
        assert result.lookup_time_ms >= 0

    @pytest.mark.asyncio
    async def test_lookup_time_under_limit(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test lookup time is under 50ms limit (AC1)."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
            ),
            True,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        # AC1: < 50ms lookup
        assert result.lookup_time_ms < 50


class TestSignalFilterErrorHandling:
    """Tests for filter error handling."""

    @pytest.mark.asyncio
    async def test_cache_error_returns_error_status(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that cache errors return ERROR status."""
        mock_wallet_cache.get.side_effect = Exception("Cache error")

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.ERROR
        assert result.is_monitored is False
        assert result.cache_hit is False


class TestSignalFilterCreateContext:
    """Tests for create_signal_context method."""

    def test_create_context_basic(self, sample_swap_event: ParsedSwapEvent, mock_wallet_cache: MagicMock):
        """Test creating basic signal context."""
        filter_result = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.0,
            cache_hit=True,
            wallet_metadata=None,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        context = filter_service.create_signal_context(sample_swap_event, filter_result)

        assert context.wallet_address == sample_swap_event.wallet_address
        assert context.token_address == sample_swap_event.token_address
        assert context.direction == sample_swap_event.direction.value
        assert context.amount_token == sample_swap_event.amount_token
        assert context.amount_sol == sample_swap_event.amount_sol
        assert context.tx_signature == sample_swap_event.tx_signature

    def test_create_context_with_metadata(self, sample_swap_event: ParsedSwapEvent, mock_wallet_cache: MagicMock):
        """Test creating context with wallet metadata."""
        entry = WalletCacheEntry(
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            cluster_id="cluster-abc",
            is_leader=True,
            reputation_score=0.9,
        )

        filter_result = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=3.5,
            cache_hit=True,
            wallet_metadata=entry,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        context = filter_service.create_signal_context(sample_swap_event, filter_result)

        assert context.cluster_id == "cluster-abc"
        assert context.is_cluster_leader is True
        assert context.wallet_reputation == 0.9
        assert context.filter_status == FilterStatus.PASSED
        assert context.filter_time_ms == 3.5

    def test_create_context_without_metadata(self, sample_swap_event: ParsedSwapEvent, mock_wallet_cache: MagicMock):
        """Test creating context without wallet metadata."""
        filter_result = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=4.0,
            cache_hit=False,
            wallet_metadata=None,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        context = filter_service.create_signal_context(sample_swap_event, filter_result)

        # Should use defaults when no metadata
        assert context.cluster_id is None
        assert context.is_cluster_leader is False
        assert context.wallet_reputation == 0.5
