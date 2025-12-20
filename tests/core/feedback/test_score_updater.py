"""Tests for wallet score updater."""

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from walltrack.core.feedback.score_models import (
    BatchUpdateRequest,
    ScoreUpdateConfig,
    ScoreUpdateInput,
    ScoreUpdateType,
    WalletMetrics,
)
from walltrack.core.feedback.score_updater import WalletScoreUpdater


class ChainableMock(MagicMock):
    """Mock that supports Supabase's chainable API pattern."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._execute_result = MagicMock(data=None, count=0)

    def table(self, _table_name: str) -> "ChainableMock":
        return ChainableMock()

    def select(self, *_args, **_kwargs) -> "ChainableMock":
        return self

    def insert(self, _data) -> "ChainableMock":
        return self

    def upsert(self, _data) -> "ChainableMock":
        return self

    def eq(self, *_args) -> "ChainableMock":
        return self

    def single(self) -> "ChainableMock":
        return self

    def order(self, *_args, **_kwargs) -> "ChainableMock":
        return self

    def limit(self, _n: int) -> "ChainableMock":
        return self

    async def execute(self):
        return self._execute_result


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    return ChainableMock()


@pytest.fixture
def score_updater(mock_supabase):
    """Create WalletScoreUpdater instance."""
    return WalletScoreUpdater(mock_supabase)


@pytest.fixture
def winning_trade():
    """Create winning trade input."""
    return ScoreUpdateInput(
        wallet_address="WinningWallet123",
        trade_id=uuid4(),
        pnl_sol=Decimal("5.0"),
        pnl_percent=Decimal("50.0"),
        is_win=True,
    )


@pytest.fixture
def losing_trade():
    """Create losing trade input."""
    return ScoreUpdateInput(
        wallet_address="LosingWallet456",
        trade_id=uuid4(),
        pnl_sol=Decimal("-3.0"),
        pnl_percent=Decimal("-30.0"),
        is_win=False,
    )


class TestScoreModels:
    """Tests for score-related models."""

    def test_score_update_config_defaults(self):
        """Test default configuration values."""
        config = ScoreUpdateConfig()
        assert config.base_win_increase == Decimal("0.02")
        assert config.base_loss_decrease == Decimal("0.03")
        assert config.decay_flag_threshold == Decimal("0.3")
        assert config.blacklist_threshold == Decimal("0.15")
        assert config.rolling_window_trades == 20

    def test_wallet_metrics_computed_fields(self):
        """Test WalletMetrics computed fields."""
        metrics = WalletMetrics(
            wallet_address="TestWallet",
            current_score=Decimal("0.7"),
            lifetime_trades=10,
            lifetime_wins=7,
            lifetime_losses=3,
            lifetime_pnl=Decimal("15.0"),
        )
        assert metrics.lifetime_win_rate == Decimal("70")
        assert metrics.average_pnl == Decimal("1.5")

    def test_wallet_metrics_zero_trades(self):
        """Test WalletMetrics with zero trades."""
        metrics = WalletMetrics(
            wallet_address="NewWallet",
            current_score=Decimal("0.5"),
        )
        assert metrics.lifetime_win_rate == Decimal("0")
        assert metrics.rolling_win_rate == Decimal("0")
        assert metrics.average_pnl == Decimal("0")

    def test_score_update_input_validation(self):
        """Test ScoreUpdateInput validation."""
        update = ScoreUpdateInput(
            wallet_address="Wallet123",
            trade_id=uuid4(),
            pnl_sol=Decimal("5.0"),
            pnl_percent=Decimal("50.0"),
            is_win=True,
        )
        assert update.wallet_address == "Wallet123"
        assert update.is_win is True


class TestScoreCalculation:
    """Tests for score calculation logic."""

    def test_win_impact_base(self, score_updater):
        """Test base win impact calculation."""
        impact = score_updater._calculate_win_impact(Decimal("10"))
        assert impact > 0
        assert impact >= score_updater.config.base_win_increase

    def test_win_impact_large_profit(self, score_updater):
        """Test win impact with large profit."""
        small_impact = score_updater._calculate_win_impact(Decimal("10"))
        large_impact = score_updater._calculate_win_impact(Decimal("100"))
        assert large_impact > small_impact
        assert large_impact <= score_updater.config.max_win_increase

    def test_win_impact_capped(self, score_updater):
        """Test win impact is capped at max."""
        impact = score_updater._calculate_win_impact(Decimal("1000"))
        assert impact == score_updater.config.max_win_increase

    def test_loss_impact_base(self, score_updater):
        """Test base loss impact calculation."""
        impact = score_updater._calculate_loss_impact(Decimal("-10"))
        assert impact < 0
        assert abs(impact) >= score_updater.config.base_loss_decrease

    def test_loss_impact_large_loss(self, score_updater):
        """Test loss impact with large loss."""
        small_impact = score_updater._calculate_loss_impact(Decimal("-10"))
        large_impact = score_updater._calculate_loss_impact(Decimal("-50"))
        assert large_impact < small_impact  # More negative
        assert abs(large_impact) <= score_updater.config.max_loss_decrease

    def test_loss_impact_capped(self, score_updater):
        """Test loss impact is capped at max."""
        impact = score_updater._calculate_loss_impact(Decimal("-1000"))
        assert abs(impact) == score_updater.config.max_loss_decrease


class TestScoreUpdates:
    """Tests for score update operations."""

    @pytest.mark.asyncio
    async def test_winning_trade_increases_score(self, score_updater, winning_trade):
        """Test that winning trades increase score."""
        result = await score_updater.update_from_trade(winning_trade)
        assert result.new_score > result.previous_score
        assert result.score_change > 0
        assert result.update_type == ScoreUpdateType.TRADE_OUTCOME

    @pytest.mark.asyncio
    async def test_losing_trade_decreases_score(self, score_updater, losing_trade):
        """Test that losing trades decrease score."""
        result = await score_updater.update_from_trade(losing_trade)
        assert result.new_score < result.previous_score
        assert result.score_change < 0

    @pytest.mark.asyncio
    async def test_new_wallet_starts_at_neutral(self, score_updater, winning_trade):
        """Test new wallet starts at 0.5 score."""
        result = await score_updater.update_from_trade(winning_trade)
        # Previous score should be 0.5 (neutral starting point)
        assert result.previous_score == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_score_bounded_at_one(self, score_updater):
        """Test score cannot exceed 1.0."""
        # Create updater with existing high-score wallet in cache
        score_updater._metrics_cache["HighScoreWallet"] = WalletMetrics(
            wallet_address="HighScoreWallet",
            current_score=Decimal("0.98"),
            lifetime_trades=10,
            lifetime_wins=9,
            lifetime_losses=1,
        )

        trade = ScoreUpdateInput(
            wallet_address="HighScoreWallet",
            trade_id=uuid4(),
            pnl_sol=Decimal("10"),
            pnl_percent=Decimal("100"),
            is_win=True,
        )
        result = await score_updater.update_from_trade(trade)
        assert result.new_score <= Decimal("1.0")

    @pytest.mark.asyncio
    async def test_score_bounded_at_zero(self, score_updater):
        """Test score cannot go below 0.0."""
        score_updater._metrics_cache["LowScoreWallet"] = WalletMetrics(
            wallet_address="LowScoreWallet",
            current_score=Decimal("0.05"),
            lifetime_trades=10,
            lifetime_wins=1,
            lifetime_losses=9,
            is_flagged=True,
        )

        trade = ScoreUpdateInput(
            wallet_address="LowScoreWallet",
            trade_id=uuid4(),
            pnl_sol=Decimal("-10"),
            pnl_percent=Decimal("-100"),
            is_win=False,
        )
        result = await score_updater.update_from_trade(trade)
        assert result.new_score >= Decimal("0.0")


class TestDecayFlagging:
    """Tests for decay detection and flagging."""

    @pytest.mark.asyncio
    async def test_triggers_decay_flag(self, score_updater):
        """Test that low score triggers decay flag."""
        # Wallet just above threshold
        score_updater._metrics_cache["DecayWallet"] = WalletMetrics(
            wallet_address="DecayWallet",
            current_score=Decimal("0.32"),
            lifetime_trades=5,
            is_flagged=False,
        )

        trade = ScoreUpdateInput(
            wallet_address="DecayWallet",
            trade_id=uuid4(),
            pnl_sol=Decimal("-3"),
            pnl_percent=Decimal("-30"),
            is_win=False,
        )
        result = await score_updater.update_from_trade(trade)
        # Score drops below 0.3 threshold
        assert result.triggered_flag is True

    @pytest.mark.asyncio
    async def test_triggers_blacklist(self, score_updater):
        """Test that very low score triggers blacklist."""
        score_updater._metrics_cache["BlacklistWallet"] = WalletMetrics(
            wallet_address="BlacklistWallet",
            current_score=Decimal("0.18"),
            lifetime_trades=10,
            is_flagged=True,
            is_blacklisted=False,
        )

        trade = ScoreUpdateInput(
            wallet_address="BlacklistWallet",
            trade_id=uuid4(),
            pnl_sol=Decimal("-5"),
            pnl_percent=Decimal("-50"),
            is_win=False,
        )
        result = await score_updater.update_from_trade(trade)
        assert result.triggered_blacklist is True

    @pytest.mark.asyncio
    async def test_no_double_flagging(self, score_updater):
        """Test already flagged wallet doesn't re-trigger."""
        score_updater._metrics_cache["FlaggedWallet"] = WalletMetrics(
            wallet_address="FlaggedWallet",
            current_score=Decimal("0.25"),
            is_flagged=True,  # Already flagged
        )

        trade = ScoreUpdateInput(
            wallet_address="FlaggedWallet",
            trade_id=uuid4(),
            pnl_sol=Decimal("-1"),
            pnl_percent=Decimal("-10"),
            is_win=False,
        )
        result = await score_updater.update_from_trade(trade)
        # Should not trigger again since already flagged
        assert result.triggered_flag is False


class TestBatchUpdates:
    """Tests for batch update processing."""

    @pytest.mark.asyncio
    async def test_batch_update_multiple_wallets(self, score_updater):
        """Test batch update with multiple wallets."""
        request = BatchUpdateRequest(
            updates=[
                ScoreUpdateInput(
                    wallet_address="Wallet1",
                    trade_id=uuid4(),
                    pnl_sol=Decimal("5"),
                    pnl_percent=Decimal("50"),
                    is_win=True,
                ),
                ScoreUpdateInput(
                    wallet_address="Wallet2",
                    trade_id=uuid4(),
                    pnl_sol=Decimal("-3"),
                    pnl_percent=Decimal("-30"),
                    is_win=False,
                ),
            ]
        )
        result = await score_updater.batch_update(request)
        assert result.total_processed == 2
        assert result.successful == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_batch_update_same_wallet(self, score_updater):
        """Test batch update with multiple trades for same wallet."""
        request = BatchUpdateRequest(
            updates=[
                ScoreUpdateInput(
                    wallet_address="SameWallet",
                    trade_id=uuid4(),
                    pnl_sol=Decimal("5"),
                    pnl_percent=Decimal("50"),
                    is_win=True,
                ),
                ScoreUpdateInput(
                    wallet_address="SameWallet",
                    trade_id=uuid4(),
                    pnl_sol=Decimal("3"),
                    pnl_percent=Decimal("30"),
                    is_win=True,
                ),
            ]
        )
        result = await score_updater.batch_update(request)
        assert result.total_processed == 2
        assert result.successful == 2
        # Second trade should build on first
        assert result.results[1].previous_score == result.results[0].new_score


class TestManualAdjustment:
    """Tests for manual score adjustments."""

    @pytest.mark.asyncio
    async def test_manual_increase(self, score_updater):
        """Test manual score increase."""
        score_updater._metrics_cache["ManualWallet"] = WalletMetrics(
            wallet_address="ManualWallet",
            current_score=Decimal("0.5"),
            lifetime_trades=5,
        )

        result = await score_updater.manual_adjust(
            wallet_address="ManualWallet",
            adjustment=Decimal("0.1"),
            reason="Performance review bonus",
        )
        assert result.new_score == Decimal("0.6")
        assert result.update_type == ScoreUpdateType.MANUAL_ADJUSTMENT

    @pytest.mark.asyncio
    async def test_manual_decrease(self, score_updater):
        """Test manual score decrease."""
        score_updater._metrics_cache["ManualWallet2"] = WalletMetrics(
            wallet_address="ManualWallet2",
            current_score=Decimal("0.7"),
        )

        result = await score_updater.manual_adjust(
            wallet_address="ManualWallet2",
            adjustment=Decimal("-0.2"),
            reason="Suspicious activity",
        )
        assert result.new_score == Decimal("0.5")

    @pytest.mark.asyncio
    async def test_manual_adjust_bounds(self, score_updater):
        """Test manual adjustment respects bounds."""
        score_updater._metrics_cache["BoundWallet"] = WalletMetrics(
            wallet_address="BoundWallet",
            current_score=Decimal("0.9"),
        )

        result = await score_updater.manual_adjust(
            wallet_address="BoundWallet",
            adjustment=Decimal("0.5"),  # Would exceed 1.0
            reason="Test",
        )
        assert result.new_score == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_manual_adjust_not_found(self, score_updater):
        """Test manual adjustment for non-existent wallet."""
        with pytest.raises(ValueError, match="not found"):
            await score_updater.manual_adjust(
                wallet_address="NonExistent",
                adjustment=Decimal("0.1"),
                reason="Test",
            )


class TestRollingWindow:
    """Tests for rolling window calculations."""

    def test_rolling_window_update(self, score_updater):
        """Test rolling window is updated correctly."""
        score_updater._update_rolling_window(
            "TestWallet",
            is_win=True,
            pnl_sol=Decimal("5"),
        )
        assert "TestWallet" in score_updater._rolling_windows
        assert len(score_updater._rolling_windows["TestWallet"]) == 1

    def test_rolling_window_max_size(self, score_updater):
        """Test rolling window respects max size."""
        for i in range(25):  # More than default 20
            score_updater._update_rolling_window(
                "TestWallet",
                is_win=i % 2 == 0,
                pnl_sol=Decimal(str(i)),
            )
        assert len(score_updater._rolling_windows["TestWallet"]) == 20

    @pytest.mark.asyncio
    async def test_rolling_metrics_calculation(self, score_updater):
        """Test rolling metrics are calculated correctly."""
        metrics = WalletMetrics(
            wallet_address="RollingWallet",
            current_score=Decimal("0.5"),
        )
        # Add some trades to window
        for i in range(5):
            score_updater._update_rolling_window(
                "RollingWallet",
                is_win=i < 3,  # 3 wins, 2 losses
                pnl_sol=Decimal("2") if i < 3 else Decimal("-1"),
            )

        await score_updater._recalculate_rolling_metrics(metrics)
        assert metrics.rolling_trades == 5
        assert metrics.rolling_wins == 3
        assert metrics.rolling_pnl == Decimal("4")  # 6 - 2
