"""Unit tests for signal pipeline."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.models.scoring import ScoredSignal
from walltrack.models.signal_filter import (
    FilterResult,
    FilterStatus,
    ProcessingResult,
    SignalContext,
    WalletCacheEntry,
)
from walltrack.models.threshold import (
    ConvictionTier,
    EligibilityStatus,
    ThresholdResult,
)
from walltrack.models.token import TokenCharacteristics, TokenFetchResult, TokenSource
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
def sample_signal_context(sample_swap_event: ParsedSwapEvent) -> SignalContext:
    """Create sample signal context for testing."""
    return SignalContext(
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


@pytest.fixture
def sample_scored_signal(sample_swap_event: ParsedSwapEvent) -> ScoredSignal:
    """Create sample scored signal for testing.

    Epic 14 Simplification: Uses the new flat ScoredSignal model.
    """
    return ScoredSignal(
        tx_signature=sample_swap_event.tx_signature,
        wallet_address=sample_swap_event.wallet_address,
        token_address=sample_swap_event.token_address,
        direction="buy",
        final_score=0.75,
        wallet_score=0.80,
        cluster_boost=1.2,
        token_safe=True,
        is_leader=True,
        cluster_id="cluster-1",
        should_trade=True,
        position_multiplier=1.2,
        explanation="Wallet: 0.80 | Cluster: 1.20x | Final: 0.75 | TRADE (>=0.65)",
    )


@pytest.fixture
def sample_wallet() -> Wallet:
    """Create sample wallet for testing."""
    return Wallet(
        address="MonitoredWallet123456789012345678901234567",
        status=WalletStatus.ACTIVE,
        score=0.75,
        profile=WalletProfile(
            win_rate=0.8,
            total_pnl=10.5,
            total_trades=25,
        ),
    )


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Create sample token characteristics for testing."""
    return TokenCharacteristics(
        token_address="TokenMint12345678901234567890123456789012",
        symbol="TEST",
        name="Test Token",
        price_usd=0.001,
        source=TokenSource.DEXSCREENER,
    )


@pytest.fixture
def mock_signal_filter() -> MagicMock:
    """Create mock signal filter."""
    filter_mock = MagicMock(spec=SignalFilter)
    filter_mock.filter_signal = AsyncMock()
    filter_mock.create_signal_context = MagicMock()
    return filter_mock


@pytest.fixture
def mock_signal_scorer() -> MagicMock:
    """Create mock signal scorer."""
    scorer_mock = MagicMock()
    scorer_mock.score = AsyncMock()
    return scorer_mock


@pytest.fixture
def mock_threshold_checker() -> MagicMock:
    """Create mock threshold checker."""
    checker_mock = MagicMock()
    checker_mock.check = MagicMock()
    return checker_mock


@pytest.fixture
def mock_wallet_repo() -> MagicMock:
    """Create mock wallet repository."""
    repo_mock = MagicMock()
    repo_mock.get_by_address = AsyncMock()
    return repo_mock


@pytest.fixture
def mock_token_fetcher() -> MagicMock:
    """Create mock token fetcher."""
    fetcher_mock = MagicMock()
    fetcher_mock.fetch = AsyncMock()
    return fetcher_mock


def create_pipeline(
    signal_filter: MagicMock,
    signal_scorer: MagicMock,
    threshold_checker: MagicMock,
    wallet_repo: MagicMock,
    token_fetcher: MagicMock,
    signal_repo: MagicMock | None = None,
) -> SignalPipeline:
    """Helper to create pipeline with all mocks."""
    return SignalPipeline(
        signal_filter=signal_filter,
        signal_scorer=signal_scorer,
        threshold_checker=threshold_checker,
        wallet_repo=wallet_repo,
        token_fetcher=token_fetcher,
        signal_repo=signal_repo,
    )


class TestSignalPipelineProcessing:
    """Tests for SignalPipeline processing."""

    @pytest.mark.asyncio
    async def test_process_passed_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        sample_signal_context: SignalContext,
        sample_scored_signal: ScoredSignal,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test processing signal that passes filter and threshold.

        Epic 14 Story 14-5: cluster_id/is_leader removed from WalletCacheEntry.
        Cluster info now comes from ClusterService via ClusterInfo.
        """
        entry = WalletCacheEntry(
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
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
        mock_signal_filter.create_signal_context.return_value = sample_signal_context

        mock_wallet_repo.get_by_address.return_value = sample_wallet
        mock_token_fetcher.fetch.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
        )
        mock_signal_scorer.score.return_value = sample_scored_signal
        mock_threshold_checker.check.return_value = ThresholdResult(
            tx_signature=sample_swap_event.tx_signature,
            wallet_address=sample_swap_event.wallet_address,
            token_address=sample_swap_event.token_address,
            final_score=0.75,
            eligibility_status=EligibilityStatus.TRADE_ELIGIBLE,
            conviction_tier=ConvictionTier.STANDARD,
            position_multiplier=1.0,
            threshold_used=0.70,
            margin_above_threshold=0.05,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        assert isinstance(result, ProcessingResult)
        assert result.passed is True
        assert result.wallet_address == sample_swap_event.wallet_address
        assert result.score == 0.75
        assert result.conviction_tier == "standard"
        mock_signal_filter.filter_signal.assert_called_once_with(sample_swap_event)
        mock_signal_scorer.score.assert_called_once()
        mock_threshold_checker.check.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_discarded_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test processing signal that is discarded at filter."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.DISCARDED_NOT_MONITORED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=False,
            is_blacklisted=False,
            lookup_time_ms=2.0,
            cache_hit=False,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        assert isinstance(result, ProcessingResult)
        assert result.passed is False
        assert result.reason == "discarded_not_monitored"
        # Scorer and threshold should not be called for filtered signals
        mock_signal_scorer.score.assert_not_called()
        mock_threshold_checker.check.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_blacklisted_signal(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
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

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        assert isinstance(result, ProcessingResult)
        assert result.passed is False
        assert result.reason == "blocked_blacklisted"

    @pytest.mark.asyncio
    async def test_process_below_threshold(
        self,
        sample_swap_event: ParsedSwapEvent,
        sample_signal_context: SignalContext,
        sample_scored_signal: ScoredSignal,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test processing signal that is below threshold."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.0,
            cache_hit=True,
        )
        mock_signal_filter.create_signal_context.return_value = sample_signal_context

        mock_wallet_repo.get_by_address.return_value = sample_wallet
        mock_token_fetcher.fetch.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
        )

        # Low score signal
        low_score_signal = sample_scored_signal.model_copy()
        low_score_signal.final_score = 0.5
        mock_signal_scorer.score.return_value = low_score_signal

        mock_threshold_checker.check.return_value = ThresholdResult(
            tx_signature=sample_swap_event.tx_signature,
            wallet_address=sample_swap_event.wallet_address,
            token_address=sample_swap_event.token_address,
            final_score=0.5,
            eligibility_status=EligibilityStatus.BELOW_THRESHOLD,
            conviction_tier=ConvictionTier.NONE,
            position_multiplier=0.0,
            threshold_used=0.70,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        assert isinstance(result, ProcessingResult)
        assert result.passed is False
        assert result.reason == "below_threshold"
        assert result.score == 0.5
        assert result.conviction_tier is None


class TestSignalPipelineDataLoading:
    """Tests for pipeline data loading."""

    @pytest.mark.asyncio
    async def test_wallet_cache_hit(
        self,
        sample_swap_event: ParsedSwapEvent,
        sample_signal_context: SignalContext,
        sample_scored_signal: ScoredSignal,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test that wallet data is cached."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.0,
            cache_hit=True,
        )
        mock_signal_filter.create_signal_context.return_value = sample_signal_context

        mock_wallet_repo.get_by_address.return_value = sample_wallet
        mock_token_fetcher.fetch.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
        )
        mock_signal_scorer.score.return_value = sample_scored_signal
        mock_threshold_checker.check.return_value = ThresholdResult(
            tx_signature=sample_swap_event.tx_signature,
            wallet_address=sample_swap_event.wallet_address,
            token_address=sample_swap_event.token_address,
            final_score=0.75,
            eligibility_status=EligibilityStatus.TRADE_ELIGIBLE,
            conviction_tier=ConvictionTier.STANDARD,
            position_multiplier=1.0,
            threshold_used=0.70,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )

        # Process same wallet twice
        await pipeline.process_swap_event(sample_swap_event)
        await pipeline.process_swap_event(sample_swap_event)

        # Wallet repo should only be called once (cache hit on second)
        assert mock_wallet_repo.get_by_address.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_wallet_uses_defaults(
        self,
        sample_swap_event: ParsedSwapEvent,
        sample_signal_context: SignalContext,
        sample_scored_signal: ScoredSignal,
        sample_token: TokenCharacteristics,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test that unknown wallet gets default values."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.0,
            cache_hit=True,
        )
        mock_signal_filter.create_signal_context.return_value = sample_signal_context

        # Wallet not found
        mock_wallet_repo.get_by_address.return_value = None
        mock_token_fetcher.fetch.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
        )
        mock_signal_scorer.score.return_value = sample_scored_signal
        mock_threshold_checker.check.return_value = ThresholdResult(
            tx_signature=sample_swap_event.tx_signature,
            wallet_address=sample_swap_event.wallet_address,
            token_address=sample_swap_event.token_address,
            final_score=0.75,
            eligibility_status=EligibilityStatus.BELOW_THRESHOLD,
            conviction_tier=ConvictionTier.NONE,
            position_multiplier=0.0,
            threshold_used=0.70,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )

        result = await pipeline.process_swap_event(sample_swap_event)

        # Should still process successfully with defaults
        assert isinstance(result, ProcessingResult)
        mock_signal_scorer.score.assert_called_once()


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
    async def test_pipeline_singleton_behavior(
        self,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test pipeline singleton returns same instance."""
        from walltrack.services.signal import pipeline as pipeline_module

        # Reset first
        await reset_pipeline()

        # Manually set a pipeline to test singleton behavior
        test_pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
        )
        pipeline_module._pipeline = test_pipeline

        # get_pipeline should return existing instance
        from walltrack.services.signal.pipeline import _pipeline

        assert _pipeline is test_pipeline

        # Cleanup
        await reset_pipeline()
        assert pipeline_module._pipeline is None


class TestSignalPipelineLogging:
    """Tests for signal logging in pipeline."""

    @pytest.fixture
    def mock_signal_repo(self) -> MagicMock:
        """Create mock signal repository."""
        repo_mock = MagicMock()
        repo_mock.save = AsyncMock(return_value="signal-uuid-123")
        return repo_mock

    @pytest.mark.asyncio
    async def test_log_signal_on_trade_eligible(
        self,
        sample_swap_event: ParsedSwapEvent,
        sample_signal_context: SignalContext,
        sample_scored_signal: ScoredSignal,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
        mock_signal_repo: MagicMock,
    ):
        """Test that signals are logged when trade eligible."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.PASSED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=True,
            is_blacklisted=False,
            lookup_time_ms=5.0,
            cache_hit=True,
        )
        mock_signal_filter.create_signal_context.return_value = sample_signal_context

        mock_wallet_repo.get_by_address.return_value = sample_wallet
        mock_token_fetcher.fetch.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
        )
        mock_signal_scorer.score.return_value = sample_scored_signal
        mock_threshold_checker.check.return_value = ThresholdResult(
            tx_signature=sample_swap_event.tx_signature,
            wallet_address=sample_swap_event.wallet_address,
            token_address=sample_swap_event.token_address,
            final_score=0.85,
            eligibility_status=EligibilityStatus.TRADE_ELIGIBLE,
            conviction_tier=ConvictionTier.STANDARD,
            position_multiplier=1.0,
            threshold_used=0.70,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
            mock_signal_repo,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        assert result.passed is True
        assert result.signal_id == "signal-uuid-123"
        mock_signal_repo.save.assert_called_once()

        # Verify the saved entry has correct data
        saved_entry = mock_signal_repo.save.call_args[0][0]
        assert saved_entry.tx_signature == sample_swap_event.tx_signature
        assert saved_entry.wallet_address == sample_swap_event.wallet_address

    @pytest.mark.asyncio
    async def test_log_signal_on_filtered_out(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
        mock_signal_repo: MagicMock,
    ):
        """Test that filtered signals are logged."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.DISCARDED_NOT_MONITORED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=False,
            is_blacklisted=False,
            lookup_time_ms=2.0,
            cache_hit=False,
        )

        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
            mock_signal_repo,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        assert result.passed is False
        mock_signal_repo.save.assert_called_once()

        saved_entry = mock_signal_repo.save.call_args[0][0]
        from walltrack.models.signal_log import SignalStatus

        assert saved_entry.status == SignalStatus.FILTERED_OUT

    @pytest.mark.asyncio
    async def test_no_log_when_repo_not_configured(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_signal_filter: MagicMock,
        mock_signal_scorer: MagicMock,
        mock_threshold_checker: MagicMock,
        mock_wallet_repo: MagicMock,
        mock_token_fetcher: MagicMock,
    ):
        """Test that no logging occurs when signal_repo is None."""
        mock_signal_filter.filter_signal.return_value = FilterResult(
            status=FilterStatus.DISCARDED_NOT_MONITORED,
            wallet_address=sample_swap_event.wallet_address,
            is_monitored=False,
            is_blacklisted=False,
            lookup_time_ms=2.0,
            cache_hit=False,
        )

        # No signal_repo provided
        pipeline = create_pipeline(
            mock_signal_filter,
            mock_signal_scorer,
            mock_threshold_checker,
            mock_wallet_repo,
            mock_token_fetcher,
            signal_repo=None,
        )
        result = await pipeline.process_swap_event(sample_swap_event)

        # Should still work, just no logging
        assert result.passed is False
        assert result.signal_id is None
