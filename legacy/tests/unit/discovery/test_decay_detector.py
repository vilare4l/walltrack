"""Tests for decay detector."""

from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.discovery.decay_detector import (
    CONSECUTIVE_LOSS_THRESHOLD,
    DECAY_THRESHOLD,
    RECOVERY_THRESHOLD,
    DecayDetector,
)

# Valid Solana addresses for testing
WALLET_1 = "A" * 44


@dataclass
class MockTrade:
    """Mock trade for testing."""

    pnl_sol: float
    exit_at: datetime


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    repo.update.return_value = None
    repo.get_by_status.return_value = []
    return repo


@pytest.fixture
def mock_trade_repo() -> AsyncMock:
    """Mock trade repository."""
    repo = AsyncMock()
    repo.get_wallet_trades.return_value = []
    return repo


@pytest.fixture
def detector(mock_wallet_repo: AsyncMock, mock_trade_repo: AsyncMock) -> DecayDetector:
    """Create detector with mocked dependencies."""
    return DecayDetector(
        wallet_repo=mock_wallet_repo,
        trade_repo=mock_trade_repo,
    )


class TestDecayDetector:
    """Tests for DecayDetector."""

    @pytest.mark.asyncio
    async def test_decay_detected_below_threshold(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test decay detection when win rate drops below threshold."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        # 30% win rate (6/20) - below 40% threshold
        trades = [
            MockTrade(pnl_sol=10, exit_at=datetime.utcnow()) if i < 6 else MockTrade(pnl_sol=-5, exit_at=datetime.utcnow())
            for i in range(20)
        ]
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is not None
        assert event.event_type == "decay_detected"
        assert wallet.status == WalletStatus.DECAY_DETECTED
        assert wallet.score < 0.7  # Score should be reduced

    @pytest.mark.asyncio
    async def test_recovery_above_threshold(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test recovery when win rate exceeds recovery threshold."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.DECAY_DETECTED,
            score=0.5,
            decay_detected_at=datetime.utcnow(),
            profile=WalletProfile(win_rate=0.55, total_trades=50),
        )

        # 55% win rate (11/20) - above 50% recovery threshold
        trades = [
            MockTrade(pnl_sol=10, exit_at=datetime.utcnow()) if i < 11 else MockTrade(pnl_sol=-5, exit_at=datetime.utcnow())
            for i in range(20)
        ]
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is not None
        assert event.event_type == "recovery"
        assert wallet.status == WalletStatus.ACTIVE
        assert wallet.decay_detected_at is None

    @pytest.mark.asyncio
    async def test_consecutive_losses_downgrade(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test score downgrade on consecutive losses."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.8,
            consecutive_losses=0,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        # 3 consecutive losses at the start (most recent), then wins
        trades = [MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()) for _ in range(3)]
        trades.extend([MockTrade(pnl_sol=10, exit_at=datetime.utcnow()) for _ in range(17)])
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is not None
        assert event.event_type == "consecutive_losses"
        assert wallet.consecutive_losses == 3
        assert wallet.score < 0.8

    @pytest.mark.asyncio
    async def test_no_event_for_healthy_wallet(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test no event for healthy performing wallet."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        # 60% win rate (12/20) - healthy, above decay threshold
        trades = [
            MockTrade(pnl_sol=10, exit_at=datetime.utcnow()) if i < 12 else MockTrade(pnl_sol=-5, exit_at=datetime.utcnow())
            for i in range(20)
        ]
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is None
        assert wallet.status == WalletStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_insufficient_trades_skipped(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test that wallets with insufficient trades are skipped."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=10),
        )

        # Only 10 trades, below MIN_TRADES_FOR_DECAY_CHECK (20)
        mock_trade_repo.get_wallet_trades.return_value = [
            MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()) for _ in range(10)
        ]

        event = await detector.check_wallet_decay(wallet)

        assert event is None  # Not enough trades

    @pytest.mark.asyncio
    async def test_record_trade_outcome_loss(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test recording a losing trade outcome."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.8,
            consecutive_losses=2,
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        event = await detector.record_trade_outcome(
            wallet_address=WALLET_1,
            is_win=False,
            pnl=-10,
        )

        # Third consecutive loss triggers event
        assert event is not None
        assert event.event_type == "consecutive_losses"
        assert wallet.consecutive_losses == 3

    @pytest.mark.asyncio
    async def test_record_trade_outcome_win_resets(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test that a winning trade resets consecutive losses."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.8,
            consecutive_losses=2,
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        event = await detector.record_trade_outcome(
            wallet_address=WALLET_1,
            is_win=True,
            pnl=20,
        )

        assert event is None
        assert wallet.consecutive_losses == 0

    @pytest.mark.asyncio
    async def test_record_trade_outcome_wallet_not_found(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test recording trade for non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        event = await detector.record_trade_outcome(
            wallet_address="nonexistent",
            is_win=False,
            pnl=-10,
        )

        assert event is None

    @pytest.mark.asyncio
    async def test_check_all_wallets_no_wallets(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test check_all_wallets with no wallets."""
        mock_wallet_repo.get_by_status.return_value = []

        events = await detector.check_all_wallets()

        assert events == []

    @pytest.mark.asyncio
    async def test_check_all_wallets_with_events(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test check_all_wallets generates events."""
        # Create wallets
        active_wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        mock_wallet_repo.get_by_status.side_effect = [
            [active_wallet],  # Active wallets
            [],  # Decay wallets
        ]

        # Low win rate to trigger decay (25% = 5/20)
        # Start with 2 losses, then a win to avoid consecutive_losses event
        trades = [
            MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()),  # Loss 1
            MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()),  # Loss 2
            MockTrade(pnl_sol=10, exit_at=datetime.utcnow()),  # Win breaks streak
        ]
        # Add remaining trades: 13 losses, 4 wins = total 15 losses, 5 wins
        trades.extend([MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()) for _ in range(13)])
        trades.extend([MockTrade(pnl_sol=10, exit_at=datetime.utcnow()) for _ in range(4)])
        mock_trade_repo.get_wallet_trades.return_value = trades

        events = await detector.check_all_wallets()

        assert len(events) == 1
        assert events[0].event_type == "decay_detected"


class TestDecayConstants:
    """Tests for decay detection constants."""

    def test_decay_threshold_value(self) -> None:
        """Test decay threshold is 40%."""
        assert DECAY_THRESHOLD == 0.40

    def test_recovery_threshold_value(self) -> None:
        """Test recovery threshold is 50%."""
        assert RECOVERY_THRESHOLD == 0.50

    def test_consecutive_loss_threshold_value(self) -> None:
        """Test consecutive loss threshold is 3."""
        assert CONSECUTIVE_LOSS_THRESHOLD == 3


class TestDecayEvent:
    """Tests for DecayEvent."""

    def test_to_dict(self) -> None:
        """Test DecayEvent.to_dict() method."""
        from walltrack.discovery.decay_detector import DecayEvent

        timestamp = datetime.utcnow()
        event = DecayEvent(
            wallet_address=WALLET_1,
            event_type="decay_detected",
            rolling_win_rate=0.35,
            lifetime_win_rate=0.55,
            consecutive_losses=2,
            score_before=0.7,
            score_after=0.56,
            timestamp=timestamp,
        )

        result = event.to_dict()

        assert result["wallet_address"] == WALLET_1
        assert result["event_type"] == "decay_detected"
        assert result["rolling_win_rate"] == 0.35
        assert result["lifetime_win_rate"] == 0.55
        assert result["consecutive_losses"] == 2
        assert result["score_before"] == 0.7
        assert result["score_after"] == 0.56
        assert result["timestamp"] == timestamp.isoformat()


class TestCountConsecutiveLosses:
    """Tests for _count_consecutive_losses helper."""

    def test_all_losses(
        self,
        detector: DecayDetector,
    ) -> None:
        """Test counting all losses."""
        trades = [MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()) for _ in range(5)]

        count = detector._count_consecutive_losses(trades)

        assert count == 5

    def test_no_losses(
        self,
        detector: DecayDetector,
    ) -> None:
        """Test counting with no losses."""
        trades = [MockTrade(pnl_sol=10, exit_at=datetime.utcnow()) for _ in range(5)]

        count = detector._count_consecutive_losses(trades)

        assert count == 0

    def test_mixed_trades(
        self,
        detector: DecayDetector,
    ) -> None:
        """Test counting with loss streak then win."""
        trades = [
            MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()),
            MockTrade(pnl_sol=-3, exit_at=datetime.utcnow()),
            MockTrade(pnl_sol=10, exit_at=datetime.utcnow()),  # Win breaks streak
            MockTrade(pnl_sol=-2, exit_at=datetime.utcnow()),
        ]

        count = detector._count_consecutive_losses(trades)

        assert count == 2  # Only first two before win

    def test_breakeven_counted_as_loss(
        self,
        detector: DecayDetector,
    ) -> None:
        """Test that breakeven (pnl=0) is counted as loss."""
        trades = [
            MockTrade(pnl_sol=0, exit_at=datetime.utcnow()),  # Breakeven
            MockTrade(pnl_sol=-5, exit_at=datetime.utcnow()),
            MockTrade(pnl_sol=10, exit_at=datetime.utcnow()),
        ]

        count = detector._count_consecutive_losses(trades)

        assert count == 2  # Breakeven + loss
