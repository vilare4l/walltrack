"""Unit tests for signal pipeline."""

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
from walltrack.services.signal.pipeline import SignalPipeline, reset_pipeline


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
def mock_signal_filter() -> MagicMock:
    """Create mock signal filter."""
    filter_mock = MagicMock(spec=SignalFilter)
    filter_mock.filter_signal = AsyncMock()
    filter_mock.create_signal_context = MagicMock()
    return filter_mock


class TestSignalPipelineProcessing:
    """Tests for SignalPipeline processing."""

    @pytest.mark.asyncio
    async def test_process_passed_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
    ):
        """Test processing signal that passes filter."""
        entry = WalletCacheEntry(
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            cluster_id="cluster-1",
            is_leader=True,
            reputation_score=0.85,
        )

        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.0,
            cache_hit=True,
            wallet_metadata=entry,
        )

        from walltrack.models.signal_filter import SignalContext

        mock_signal_filter.create_signal_context.return_value = SignalContext(
            wallet_address=sample_swap_event.wallet_address,
            token_address=sample_swap_event.token_address,
            direction="buy",
            amount_token=1000000.0,
            amount_sol=1.5,
            timestamp=sample_swap_event.timestamp,
            tx_signature=sample_swap_event.tx_signature,
            cluster_id="cluster-1",
            is_cluster_leader=True,
            wallet_reputation=0.85,
        )

        pipeline = SignalPipeline(mock_signal_filter)
        result = await pipeline.process_swap_event(sample_swap_event)

        assert result is not None
        assert result.wallet_address == sample_swap_event.wallet_address
        assert result.cluster_id == "cluster-1"
        assert result.is_cluster_leader is True
        mock_signal_filter.filter_signal.assert_called_once_with(sample_swap_event)
        mock_signal_filter.create_signal_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_discarded_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
    ):
        """Test processing signal that is discarded."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.DISCARDED_NOT_MONITORED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=False,
            is_blacklisted=False,
            lookup_time_ms=2.0,
            cache_hit=False,
        )

        pipeline = SignalPipeline(mock_signal_filter)
        result = await pipeline.process_swap_event(sample_swap_event)

        assert result is None
        # create_signal_context should not be called for discarded signals
        mock_signal_filter.create_signal_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_blacklisted_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
    ):
        """Test processing signal from blacklisted wallet."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.BLOCKED_BLACKLISTED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=True,
            lookup_time_ms=3.0,
            cache_hit=True,
        )

        pipeline = SignalPipeline(mock_signal_filter)
        result = await pipeline.process_swap_event(sample_swap_event)

        assert result is None
        mock_signal_filter.create_signal_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_error_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
    ):
        """Test processing signal that errors."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.ERROR,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=False,
            is_blacklisted=False,
            lookup_time_ms=0.0,
            cache_hit=False,
        )

        pipeline = SignalPipeline(mock_signal_filter)
        result = await pipeline.process_swap_event(sample_swap_event)

        assert result is None


class TestSignalPipelineIntegration:
    """Integration tests for SignalPipeline with real filter."""

    @pytest.mark.asyncio
    async def test_full_pipeline_monitored(self, sample_swap_event: ParsedSwapEvent):
        """Test full pipeline with monitored wallet."""
        from walltrack.services.signal.wallet_cache import WalletCache

        # Create mock wallet cache
        mock_wallet_cache = MagicMock(spec=WalletCache)
        mock_wallet_cache.get = AsyncMock(
            return_value=(
                WalletCacheEntry(
                    wallet_address=sample_swap_event.wallet_address,
                    is_monitored=True,
                    is_blacklisted=False,
                    cluster_id="cluster-xyz",
                    is_leader=False,
                    reputation_score=0.7,
                ),
                True,
            )
        )

        signal_filter = SignalFilter(mock_wallet_cache)
        pipeline = SignalPipeline(signal_filter)

        result = await pipeline.process_swap_event(sample_swap_event)

        assert result is not None
        assert result.wallet_address == sample_swap_event.wallet_address
        assert result.token_address == sample_swap_event.token_address
        assert result.direction == "buy"
        assert result.cluster_id == "cluster-xyz"
        assert result.wallet_reputation == 0.7

    @pytest.mark.asyncio
    async def test_full_pipeline_not_monitored(self, sample_swap_event: ParsedSwapEvent):
        """Test full pipeline with non-monitored wallet."""
        from walltrack.services.signal.wallet_cache import WalletCache

        mock_wallet_cache = MagicMock(spec=WalletCache)
        mock_wallet_cache.get = AsyncMock(
            return_value=(
                WalletCacheEntry(
                    wallet_address=sample_swap_event.wallet_address,
                    is_monitored=False,
                    is_blacklisted=False,
                ),
                False,
            )
        )

        signal_filter = SignalFilter(mock_wallet_cache)
        pipeline = SignalPipeline(signal_filter)

        result = await pipeline.process_swap_event(sample_swap_event)

        assert result is None


class TestPipelineSingleton:
    """Tests for pipeline singleton functions."""

    @pytest.mark.asyncio
    async def test_reset_pipeline(self):
        """Test resetting pipeline singleton."""
        from walltrack.services.signal import pipeline as pipeline_module

        # Set a mock pipeline
        pipeline_module._pipeline = MagicMock()

        await reset_pipeline()

        assert pipeline_module._pipeline is None

    @pytest.mark.asyncio
    async def test_pipeline_singleton_behavior(self, mock_signal_filter: MagicMock):
        """Test pipeline singleton returns same instance."""
        from walltrack.services.signal import pipeline as pipeline_module

        # Reset first
        await reset_pipeline()

        # Manually set a pipeline to test singleton behavior
        test_pipeline = SignalPipeline(mock_signal_filter)
        pipeline_module._pipeline = test_pipeline

        # get_pipeline should return existing instance
        from walltrack.services.signal.pipeline import _pipeline

        assert _pipeline is test_pipeline

        # Cleanup
        await reset_pipeline()
        assert pipeline_module._pipeline is None
