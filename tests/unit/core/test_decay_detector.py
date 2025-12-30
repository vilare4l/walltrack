"""Unit tests for decay detector service.

Story 3.4 - Wallet Decay Detection
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.core.wallets.decay_detector import (
    DecayConfig,
    DecayDetector,
    MAX_SCORE,
    MIN_SCORE,
    Trade,
)
from walltrack.data.models.decay_event import DecayEventType
from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.models.wallet import Wallet


@pytest.fixture
def decay_config():
    """Decay configuration with default values."""
    return DecayConfig(
        rolling_window_size=20,
        min_trades=20,
        decay_threshold=0.40,
        recovery_threshold=0.50,
        consecutive_loss_threshold=3,
        dormancy_days=30,
        score_downgrade_decay=0.80,
        score_downgrade_loss=0.95,
        score_recovery_boost=1.10,
    )


@pytest.fixture
def mock_wallet_repo():
    """Mock WalletRepository."""
    repo = AsyncMock()
    repo.update_decay_status = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_helius_client():
    """Mock HeliusClient."""
    client = AsyncMock()
    return client


@pytest.fixture
def detector(decay_config, mock_wallet_repo, mock_helius_client):
    """DecayDetector instance with mocked dependencies."""
    return DecayDetector(decay_config, mock_wallet_repo, mock_helius_client)


def create_wallet(
    wallet_address: str = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
    score: float = 0.85,
    decay_status: str = "ok",
    win_rate: float = 0.65,
    last_activity_date: datetime | None = None,
) -> Wallet:
    """Helper to create wallet instance."""
    return Wallet(
        wallet_address=wallet_address,
        discovery_date=datetime.now(UTC),
        token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        score=score,
        decay_status=decay_status,
        win_rate=win_rate,
        consecutive_losses=0,
        last_activity_date=last_activity_date or datetime.now(UTC),
        rolling_win_rate=None,
    )


def create_swap_transaction(
    token_mint: str,
    tx_type: TransactionType,
    sol_amount: float,
    timestamp: datetime,
) -> SwapTransaction:
    """Helper to create swap transaction.

    Args:
        token_mint: Token mint address (if short, will be padded to valid length).
        tx_type: BUY or SELL.
        sol_amount: SOL amount.
        timestamp: Transaction timestamp.

    Returns:
        SwapTransaction instance.
    """
    # If token_mint is short (like "token0"), convert to base58-compatible address
    if len(token_mint) < 32:
        # Extract numeric suffix if present (e.g., "token0" → 0, "token1" → 1)
        import re

        match = re.search(r"\d+$", token_mint)
        if match:
            num = int(match.group())
            # Create unique suffix using base58 chars (excludes: 0, O, I, l)
            base58_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
            suffix = base58_chars[num % len(base58_chars)] * 9
            token_mint = f"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGG{suffix}"[:44]
        else:
            # Fallback to a valid address
            token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    return SwapTransaction(
        signature=f"5j7s8k2d9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9Pus{int(timestamp.timestamp())}",
        timestamp=int(timestamp.timestamp()),
        tx_type=tx_type,
        token_mint=token_mint,
        sol_amount=sol_amount,
        token_amount=1000.0,
        wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
    )


class TestDecayDetector:
    """Tests for DecayDetector class."""

    @pytest.mark.asyncio
    async def test_insufficient_trades_returns_none(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test that detector returns None if wallet has < 20 trades (AC compliance)."""
        wallet = create_wallet()
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create only 10 trades (less than min_trades threshold of 20)
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(10):
            buy_time = base_time - timedelta(days=20 - i, hours=12)
            sell_time = base_time - timedelta(days=20 - i, hours=8)
            transactions.append(
                create_swap_transaction("token1", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction("token1", TransactionType.SELL, 1.5, sell_time)
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify: no event created
        assert event is None

    @pytest.mark.asyncio
    async def test_decay_detected_below_threshold(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test decay detected when rolling win rate < 40% (AC1)."""
        wallet = create_wallet(score=0.85, decay_status="ok")
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with 35% win rate (7 wins, 13 losses) - below 40% threshold
        # Pattern: L W L L W L L W L L W L L W L L W L L W
        # This gives 35% win rate WITHOUT triggering consecutive loss detector (max 2 consecutive losses)
        win_pattern = [False, True, False, False, True, False, False, True, False, False, 
                       True, False, False, True, False, False, True, False, False, True]
        
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            # Win if pattern says so, else loss
            sell_amount = 1.5 if win_pattern[i] else 0.8
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify
        assert event is not None
        assert event.event_type == DecayEventType.DECAY_DETECTED
        assert event.rolling_win_rate == Decimal("0.35")  # 7/20 = 35%
        assert event.score_before == Decimal("0.85")
        assert event.score_after == Decimal("0.68")  # 0.85 * 0.80 = 0.68
        assert event.wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

        # Verify update_decay_status called with correct params
        mock_wallet_repo.update_decay_status.assert_called_once()
        call_kwargs = mock_wallet_repo.update_decay_status.call_args.kwargs
        assert call_kwargs["decay_status"] == "flagged"
        assert call_kwargs["score"] == pytest.approx(0.68, abs=0.01)

    @pytest.mark.asyncio
    async def test_recovery_above_threshold(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test recovery when rolling win rate >= 50% and wallet is flagged (AC1)."""
        wallet = create_wallet(score=0.68, decay_status="flagged")
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with 55% win rate (11 wins, 9 losses) - above 50% recovery threshold
        # Pattern: W L W W L W L W W L W L W L W W L W L L (11 wins, 9 losses, max 2 consecutive)
        win_pattern = [True, False, True, True, False, True, False, True, True, False,
                       True, False, True, False, True, True, False, True, False, False]
        
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            # Win if pattern says so, else loss
            sell_amount = 1.5 if win_pattern[i] else 0.8
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify
        assert event is not None
        assert event.event_type == DecayEventType.RECOVERY
        assert event.rolling_win_rate == Decimal("0.55")  # 11/20 = 55%
        assert event.score_before == Decimal("0.68")
        assert event.score_after == pytest.approx(Decimal("0.748"), abs=0.001)  # 0.68 * 1.10 = 0.748
        assert event.wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

        # Verify update_decay_status called with correct params
        mock_wallet_repo.update_decay_status.assert_called_once()
        call_kwargs = mock_wallet_repo.update_decay_status.call_args.kwargs
        assert call_kwargs["decay_status"] == "ok"
        assert call_kwargs["score"] == pytest.approx(0.748, abs=0.01)

    @pytest.mark.asyncio
    async def test_consecutive_losses(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test downgraded status when 3+ consecutive losses (AC2)."""
        wallet = create_wallet(score=0.85, decay_status="ok")
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with last 5 being consecutive losses
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            # Last 5 are losers, rest are winners
            sell_amount = 0.8 if i >= 15 else 1.5
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify
        assert event is not None
        assert event.event_type == DecayEventType.CONSECUTIVE_LOSSES
        assert event.consecutive_losses == 5
        assert event.wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

        # Verify update_decay_status called with correct params
        mock_wallet_repo.update_decay_status.assert_called_once()
        call_kwargs = mock_wallet_repo.update_decay_status.call_args.kwargs
        assert call_kwargs["decay_status"] == "downgraded"
        assert call_kwargs["consecutive_losses"] == 5

    @pytest.mark.asyncio
    async def test_dormancy_detection(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test dormant status when 30+ days inactive (AC3)."""
        # Wallet with last activity 45 days ago
        last_activity = datetime.now(UTC) - timedelta(days=45)
        wallet = create_wallet(
            score=0.85, decay_status="ok", last_activity_date=last_activity
        )
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create old trades (all 45+ days ago)
        transactions = []
        base_time = datetime.now(UTC) - timedelta(days=45)
        for i in range(20):
            buy_time = base_time - timedelta(days=20 - i, hours=12)
            sell_time = base_time - timedelta(days=20 - i, hours=8)
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, 1.5, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify
        assert event is not None
        assert event.event_type == DecayEventType.DORMANCY
        assert event.wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

        # Verify update_decay_status called with correct params
        mock_wallet_repo.update_decay_status.assert_called_once()
        call_kwargs = mock_wallet_repo.update_decay_status.call_args.kwargs
        assert call_kwargs["decay_status"] == "dormant"

    @pytest.mark.asyncio
    async def test_score_downgrade_decay(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test 20% score reduction on decay event."""
        wallet = create_wallet(score=0.85, decay_status="ok")
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with 35% win rate (below 40% threshold)
        # Pattern: L W L L W L L W L L W L L W L L W L L W (max 2 consecutive losses)
        win_pattern = [False, True, False, False, True, False, False, True, False, False, 
                       True, False, False, True, False, False, True, False, False, True]
        
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            sell_amount = 1.5 if win_pattern[i] else 0.8
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify: score reduced by 20% (0.85 * 0.80 = 0.68)
        assert event.score_before == Decimal("0.85")
        assert event.score_after == Decimal("0.68")

    @pytest.mark.asyncio
    async def test_score_bounds_enforcement_min(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test score never goes below MIN_SCORE (0.1)."""
        wallet = create_wallet(score=0.12, decay_status="ok")  # Close to minimum
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with 35% win rate (triggers decay)
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            sell_amount = 1.5 if i < 7 else 0.8
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify: score reduced but not below MIN_SCORE
        # 0.12 * 0.80 = 0.096, but should be clamped to 0.1
        assert event.score_after == Decimal(str(MIN_SCORE))

    @pytest.mark.asyncio
    async def test_score_bounds_enforcement_max(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test score never exceeds MAX_SCORE (1.0)."""
        wallet = create_wallet(score=0.95, decay_status="flagged")  # Close to maximum
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with 55% win rate (triggers recovery)
        # Pattern: W W L W L W W L W L W W L W L W W L W L (max 2 consecutive)
        win_pattern = [True, True, False, True, False, True, True, False, True, False,
                       True, True, False, True, False, True, True, False, True, False]
        
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            sell_amount = 1.5 if win_pattern[i] else 0.8
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify: score increased but not above MAX_SCORE
        # 0.95 * 1.10 = 1.045, but should be clamped to 1.0
        assert event.score_after == Decimal(str(MAX_SCORE))

    @pytest.mark.asyncio
    async def test_no_status_change_returns_none(
        self, detector, mock_wallet_repo, mock_helius_client
    ):
        """Test that no event is created if status unchanged."""
        wallet = create_wallet(score=0.85, decay_status="ok")
        mock_wallet_repo.get_by_address = AsyncMock(return_value=wallet)

        # Create 20 trades with 65% win rate (healthy, no change)
        # Pattern: W W L W L W W L W W L W L W W L W W L W (max 2 consecutive)
        win_pattern = [True, True, False, True, False, True, True, False, True, True,
                       False, True, False, True, True, False, True, True, False, True]
        
        transactions = []
        base_time = datetime.now(UTC)
        for i in range(20):
            buy_time = base_time - timedelta(days=30 - i, hours=12)
            sell_time = base_time - timedelta(days=30 - i, hours=8)
            sell_amount = 1.5 if win_pattern[i] else 0.8
            transactions.append(
                create_swap_transaction(f"token{i}", TransactionType.BUY, 1.0, buy_time)
            )
            transactions.append(
                create_swap_transaction(
                    f"token{i}", TransactionType.SELL, sell_amount, sell_time
                )
            )

        mock_helius_client.get_swap_transactions = AsyncMock(return_value=transactions)

        # Execute
        event = await detector.check_wallet_decay("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Verify: no event created (status remains "ok")
        assert event is None

        # But tracking fields still updated
        mock_wallet_repo.update_decay_status.assert_called_once()

    def test_match_trades_fifo(self, detector):
        """Test FIFO matching of BUY/SELL pairs."""
        base_time = datetime.now(UTC)

        transactions = [
            create_swap_transaction("token1", TransactionType.BUY, 1.0, base_time),
            create_swap_transaction(
                "token1", TransactionType.SELL, 1.5, base_time + timedelta(hours=2)
            ),
            create_swap_transaction(
                "token2", TransactionType.BUY, 2.0, base_time + timedelta(hours=4)
            ),
            create_swap_transaction(
                "token2", TransactionType.SELL, 1.8, base_time + timedelta(hours=6)
            ),
        ]

        trades = detector._match_trades(transactions)

        assert len(trades) == 2
        # token1 → "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGG222222222"
        assert trades[0].token_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGG222222222"
        assert trades[0].pnl == pytest.approx(0.5, abs=0.01)  # 1.5 - 1.0
        assert trades[0].profitable is True
        # token2 → "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGG333333333"
        assert trades[1].token_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGG333333333"
        assert trades[1].pnl == pytest.approx(-0.2, abs=0.01)  # 1.8 - 2.0
        assert trades[1].profitable is False

    def test_count_consecutive_losses(self, detector):
        """Test consecutive loss counter from most recent trade."""
        trades = [
            Trade("t1", datetime.now(UTC), datetime.now(UTC), 0.5, True),  # Win
            Trade("t2", datetime.now(UTC), datetime.now(UTC), -0.2, False),  # Loss
            Trade("t3", datetime.now(UTC), datetime.now(UTC), -0.1, False),  # Loss
            Trade("t4", datetime.now(UTC), datetime.now(UTC), -0.3, False),  # Loss (latest)
        ]

        count = detector._count_consecutive_losses(trades)

        assert count == 3  # Last 3 trades are losses
