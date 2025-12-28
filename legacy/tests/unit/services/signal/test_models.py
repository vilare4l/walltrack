"""Unit tests for signal filter models."""

from datetime import UTC, datetime, timedelta

import pytest

from walltrack.models.signal_filter import (
    FilterResult,
    FilterStatus,
    SignalContext,
    WalletCacheEntry,
)


class TestFilterStatus:
    """Tests for FilterStatus enum."""

    def test_status_values(self):
        """Test FilterStatus has expected values."""
        assert FilterStatus.PASSED.value == "passed"
        assert FilterStatus.DISCARDED_NOT_MONITORED.value == "discarded_not_monitored"
        assert FilterStatus.BLOCKED_BLACKLISTED.value == "blocked_blacklisted"
        assert FilterStatus.ERROR.value == "error"

    def test_status_is_string_enum(self):
        """Test FilterStatus is string-based enum."""
        assert isinstance(FilterStatus.PASSED.value, str)
        # FilterStatus inherits from str, so .value gives the string
        assert FilterStatus.PASSED.value == "passed"


class TestWalletCacheEntry:
    """Tests for WalletCacheEntry model."""

    def test_default_values(self):
        """Test WalletCacheEntry default values.

        Epic 14 Story 14-5: cluster_id and is_leader removed.
        Use ClusterService for cluster info.
        """
        entry = WalletCacheEntry(wallet_address="wallet123")

        assert entry.wallet_address == "wallet123"
        assert entry.is_monitored is False
        assert entry.is_blacklisted is False
        assert entry.reputation_score == 0.5
        assert entry.ttl_seconds == 300

    def test_custom_values(self):
        """Test WalletCacheEntry with custom values.

        Epic 14 Story 14-5: cluster_id and is_leader removed.
        Use ClusterService for cluster info.
        """
        entry = WalletCacheEntry(
            wallet_address="wallet456",
            is_monitored=True,
            is_blacklisted=False,
            reputation_score=0.9,
            ttl_seconds=600,
        )

        assert entry.wallet_address == "wallet456"
        assert entry.is_monitored is True
        assert entry.reputation_score == 0.9
        assert entry.ttl_seconds == 600

    def test_is_expired_not_expired(self):
        """Test is_expired returns False when within TTL."""
        entry = WalletCacheEntry(
            wallet_address="wallet789",
            ttl_seconds=300,
        )

        assert entry.is_expired() is False

    def test_is_expired_is_expired(self):
        """Test is_expired returns True when past TTL."""
        entry = WalletCacheEntry(
            wallet_address="wallet789",
            cached_at=datetime.now(UTC) - timedelta(seconds=400),
            ttl_seconds=300,
        )

        assert entry.is_expired() is True

    def test_reputation_score_bounds(self):
        """Test reputation_score validation."""
        entry = WalletCacheEntry(
            wallet_address="wallet",
            reputation_score=0.0,
        )
        assert entry.reputation_score == 0.0

        entry = WalletCacheEntry(
            wallet_address="wallet",
            reputation_score=1.0,
        )
        assert entry.reputation_score == 1.0

    def test_reputation_score_invalid(self):
        """Test reputation_score rejects invalid values."""
        with pytest.raises(ValueError):
            WalletCacheEntry(
                wallet_address="wallet",
                reputation_score=-0.1,
            )

        with pytest.raises(ValueError):
            WalletCacheEntry(
                wallet_address="wallet",
                reputation_score=1.1,
            )


class TestFilterResult:
    """Tests for FilterResult model."""

    def test_passed_result(self):
        """Test FilterResult for passed filter."""
        result = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address="wallet123",
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.5,
            cache_hit=True,
        )

        assert result.status == FilterStatus.PASSED
        assert result.is_monitored is True
        assert result.is_blacklisted is False
        assert result.lookup_time_ms == 5.5
        assert result.cache_hit is True

    def test_discarded_result(self):
        """Test FilterResult for discarded signal."""
        result = FilterResult(
            status=FilterStatus.DISCARDED_NOT_MONITORED,
            wallet_address="unknown_wallet",
            is_monitored=False,
            is_blacklisted=False,
            lookup_time_ms=2.0,
        )

        assert result.status == FilterStatus.DISCARDED_NOT_MONITORED
        assert result.is_monitored is False

    def test_blocked_result(self):
        """Test FilterResult for blocked signal."""
        result = FilterResult(
            status=FilterStatus.BLOCKED_BLACKLISTED,
            wallet_address="blacklisted_wallet",
            is_monitored=True,
            is_blacklisted=True,
            lookup_time_ms=3.0,
        )

        assert result.status == FilterStatus.BLOCKED_BLACKLISTED
        assert result.is_blacklisted is True

    def test_with_wallet_metadata(self):
        """Test FilterResult with wallet metadata.

        Epic 14 Story 14-5: cluster_id removed from WalletCacheEntry.
        Use ClusterService for cluster info.
        """
        entry = WalletCacheEntry(
            wallet_address="wallet123",
            is_monitored=True,
            reputation_score=0.85,
        )

        result = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address="wallet123",
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=4.0,
            wallet_metadata=entry,
        )

        assert result.wallet_metadata is not None
        assert result.wallet_metadata.is_monitored is True
        assert result.wallet_metadata.reputation_score == 0.85

    def test_lookup_time_validation(self):
        """Test lookup_time_ms rejects negative values."""
        with pytest.raises(ValueError):
            FilterResult(
                status=FilterStatus.PASSED,
                wallet_address="wallet",
                is_monitored=True,
                is_blacklisted=False,
                lookup_time_ms=-1.0,
            )


class TestSignalContext:
    """Tests for SignalContext model."""

    def test_basic_context(self):
        """Test SignalContext with basic values."""
        now = datetime.now(UTC)
        context = SignalContext(
            wallet_address="wallet123",
            token_address="token456",
            direction="buy",
            amount_token=1000.0,
            amount_sol=2.5,
            timestamp=now,
            tx_signature="sig789",
        )

        assert context.wallet_address == "wallet123"
        assert context.token_address == "token456"
        assert context.direction == "buy"
        assert context.amount_token == 1000.0
        assert context.amount_sol == 2.5
        assert context.timestamp == now
        assert context.tx_signature == "sig789"

    def test_enriched_context(self):
        """Test SignalContext with enriched metadata."""
        now = datetime.now(UTC)
        context = SignalContext(
            wallet_address="wallet123",
            token_address="token456",
            direction="sell",
            amount_token=500.0,
            amount_sol=1.0,
            timestamp=now,
            tx_signature="sig789",
            cluster_id="cluster-abc",
            is_cluster_leader=True,
            wallet_reputation=0.85,
            filter_status=FilterStatus.PASSED,
            filter_time_ms=5.5,
        )

        assert context.cluster_id == "cluster-abc"
        assert context.is_cluster_leader is True
        assert context.wallet_reputation == 0.85
        assert context.filter_status == FilterStatus.PASSED
        assert context.filter_time_ms == 5.5

    def test_default_values(self):
        """Test SignalContext default values."""
        now = datetime.now(UTC)
        context = SignalContext(
            wallet_address="wallet123",
            token_address="token456",
            direction="buy",
            amount_token=100.0,
            amount_sol=0.5,
            timestamp=now,
            tx_signature="sig789",
        )

        assert context.cluster_id is None
        assert context.is_cluster_leader is False
        assert context.wallet_reputation == 0.5
        assert context.filter_status == FilterStatus.PASSED
        assert context.filter_time_ms == 0.0

    def test_wallet_reputation_bounds(self):
        """Test wallet_reputation validation."""
        now = datetime.now(UTC)

        with pytest.raises(ValueError):
            SignalContext(
                wallet_address="wallet",
                token_address="token",
                direction="buy",
                amount_token=100.0,
                amount_sol=0.5,
                timestamp=now,
                tx_signature="sig",
                wallet_reputation=-0.1,
            )

        with pytest.raises(ValueError):
            SignalContext(
                wallet_address="wallet",
                token_address="token",
                direction="buy",
                amount_token=100.0,
                amount_sol=0.5,
                timestamp=now,
                tx_signature="sig",
                wallet_reputation=1.1,
            )
