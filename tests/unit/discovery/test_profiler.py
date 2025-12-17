"""Tests for wallet profiler."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.discovery.profiler import MIN_TRADES_FOR_PROFILE, WalletProfiler

# Valid Solana addresses for testing (44 characters, base58)
WALLET_1 = "A" * 44
WALLET_2 = "B" * 44
TOKEN_MINT = "C" * 44
SOL_MINT = "So11111111111111111111111111111111111111112"


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    repo.get_by_address.return_value = None
    repo.exists.return_value = False
    repo.create.return_value = MagicMock(spec=Wallet)
    repo.update.return_value = MagicMock(spec=Wallet)
    return repo


@pytest.fixture
def mock_helius_client() -> AsyncMock:
    """Mock Helius client."""
    client = AsyncMock()
    client.get_wallet_transactions.return_value = []
    return client


@pytest.fixture
def profiler(
    mock_wallet_repo: AsyncMock,
    mock_helius_client: AsyncMock,
) -> WalletProfiler:
    """Create profiler with mocked dependencies."""
    return WalletProfiler(
        wallet_repo=mock_wallet_repo,
        helius_client=mock_helius_client,
    )


@pytest.fixture
def sample_transactions() -> list[dict]:
    """Create sample transaction data."""
    now = datetime.utcnow()
    return [
        # Buy transaction (SOL -> TOKEN)
        {
            "type": "SWAP",
            "tokenIn": {"mint": SOL_MINT, "amount": 1.0},
            "tokenOut": {"mint": TOKEN_MINT, "amount": 1000},
            "timestamp": (now - timedelta(hours=5)).timestamp(),
        },
        # Sell transaction (TOKEN -> SOL) - profitable
        {
            "type": "SWAP",
            "tokenIn": {"mint": TOKEN_MINT, "amount": 1000},
            "tokenOut": {"mint": SOL_MINT, "amount": 2.0},
            "timestamp": (now - timedelta(hours=2)).timestamp(),
        },
    ]


class TestWalletProfiler:
    """Tests for WalletProfiler."""

    @pytest.mark.asyncio
    async def test_profile_wallet_new_wallet(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
        sample_transactions: list[dict],
    ) -> None:
        """Test profiling a new wallet."""
        mock_helius_client.get_wallet_transactions.return_value = sample_transactions
        mock_wallet_repo.exists.return_value = False

        wallet = await profiler.profile_wallet(WALLET_1)

        assert wallet.address == WALLET_1
        mock_wallet_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_profile_wallet_existing_wallet(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
        sample_transactions: list[dict],
    ) -> None:
        """Test profiling an existing wallet."""
        existing_wallet = Wallet(
            address=WALLET_1,
            last_profiled_at=datetime.utcnow() - timedelta(days=2),
        )
        mock_wallet_repo.get_by_address.return_value = existing_wallet
        mock_wallet_repo.exists.return_value = True
        mock_helius_client.get_wallet_transactions.return_value = sample_transactions

        wallet = await profiler.profile_wallet(WALLET_1)

        assert wallet.address == WALLET_1
        mock_wallet_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_profile_wallet_skips_recent(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that recent profiles are skipped."""
        recent_wallet = Wallet(
            address=WALLET_1,
            last_profiled_at=datetime.utcnow() - timedelta(hours=12),
        )
        mock_wallet_repo.get_by_address.return_value = recent_wallet

        wallet = await profiler.profile_wallet(WALLET_1)

        # Should return cached wallet without calling Helius
        assert wallet.address == WALLET_1
        mock_helius_client.get_wallet_transactions.assert_not_called()

    @pytest.mark.asyncio
    async def test_profile_wallet_force_update(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
        sample_transactions: list[dict],
    ) -> None:
        """Test force update ignores recency check."""
        recent_wallet = Wallet(
            address=WALLET_1,
            last_profiled_at=datetime.utcnow() - timedelta(hours=12),
        )
        mock_wallet_repo.get_by_address.return_value = recent_wallet
        mock_wallet_repo.exists.return_value = True
        mock_helius_client.get_wallet_transactions.return_value = sample_transactions

        wallet = await profiler.profile_wallet(WALLET_1, force_update=True)

        # Should call Helius despite recent profile
        mock_helius_client.get_wallet_transactions.assert_called_once()
        assert wallet.last_profiled_at is not None

    @pytest.mark.asyncio
    async def test_profile_wallet_insufficient_data(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test wallet with insufficient trading data."""
        # Only one trade (below MIN_TRADES_FOR_PROFILE)
        mock_helius_client.get_wallet_transactions.return_value = [
            {
                "type": "SWAP",
                "tokenIn": {"mint": SOL_MINT, "amount": 1.0},
                "tokenOut": {"mint": TOKEN_MINT, "amount": 1000},
                "timestamp": datetime.utcnow().timestamp(),
            }
        ]

        wallet = await profiler.profile_wallet(WALLET_1)

        assert wallet.status == WalletStatus.INSUFFICIENT_DATA

    @pytest.mark.asyncio
    async def test_profile_batch_success(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
        sample_transactions: list[dict],
    ) -> None:
        """Test batch profiling multiple wallets."""
        mock_helius_client.get_wallet_transactions.return_value = sample_transactions

        wallets = await profiler.profile_batch([WALLET_1, WALLET_2])

        assert len(wallets) == 2
        assert mock_helius_client.get_wallet_transactions.call_count == 2

    @pytest.mark.asyncio
    async def test_profile_batch_handles_errors(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
        sample_transactions: list[dict],
    ) -> None:
        """Test batch profiling handles individual errors gracefully."""
        # First succeeds, second fails
        mock_helius_client.get_wallet_transactions.side_effect = [
            sample_transactions,
            Exception("API Error"),
        ]

        wallets = await profiler.profile_batch([WALLET_1, WALLET_2])

        # Should return successful profiles only
        assert len(wallets) == 1

    @pytest.mark.asyncio
    async def test_profile_batch_respects_concurrency(
        self,
        profiler: WalletProfiler,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
        sample_transactions: list[dict],
    ) -> None:
        """Test batch profiling respects max_concurrent limit."""
        mock_helius_client.get_wallet_transactions.return_value = sample_transactions
        addresses = [f"{'A' * 40}{i:04d}" for i in range(20)]

        wallets = await profiler.profile_batch(addresses, max_concurrent=5)

        assert len(wallets) == 20


class TestProfileCalculations:
    """Tests for profile metric calculations."""

    @pytest.mark.asyncio
    async def test_calculate_profile_win_rate(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test win rate calculation."""
        trades = [
            {"type": "buy", "token": TOKEN_MINT, "amount_sol": 1.0, "timestamp": datetime.utcnow()},
            {"type": "sell", "token": TOKEN_MINT, "pnl": 0.5, "is_win": True, "timestamp": datetime.utcnow()},
            {"type": "sell", "token": "D" * 44, "pnl": -0.2, "is_win": False, "timestamp": datetime.utcnow()},
        ]

        profile = await profiler._calculate_profile(trades)

        # 1 win out of 2 completed trades = 50%
        assert profile.win_rate == 0.5

    @pytest.mark.asyncio
    async def test_calculate_profile_pnl(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test PnL calculation."""
        trades = [
            {"type": "sell", "token": TOKEN_MINT, "pnl": 1.0, "is_win": True, "timestamp": datetime.utcnow()},
            {"type": "sell", "token": "D" * 44, "pnl": 0.5, "is_win": True, "timestamp": datetime.utcnow()},
            {"type": "sell", "token": "E" * 44, "pnl": -0.3, "is_win": False, "timestamp": datetime.utcnow()},
        ]

        profile = await profiler._calculate_profile(trades)

        assert profile.total_pnl == 1.2  # 1.0 + 0.5 - 0.3

    @pytest.mark.asyncio
    async def test_calculate_profile_empty_trades(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test profile calculation with no trades."""
        profile = await profiler._calculate_profile([])

        assert profile.win_rate == 0.0
        assert profile.total_pnl == 0.0
        assert profile.total_trades == 0

    def test_calculate_initial_score_insufficient_data(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test score calculation with insufficient trades."""
        profile = WalletProfile(total_trades=MIN_TRADES_FOR_PROFILE - 1)

        score = profiler._calculate_initial_score(profile)

        assert score == 0.3  # Default for insufficient data

    def test_calculate_initial_score_good_trader(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test score calculation for good trader."""
        profile = WalletProfile(
            win_rate=0.8,
            total_pnl=50.0,
            total_trades=30,
            timing_percentile=0.2,  # Early buyer
        )

        score = profiler._calculate_initial_score(profile)

        # Should be high score: high win rate, good PnL, early timing
        assert score > 0.6

    def test_needs_profiling_never_profiled(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test _needs_profiling returns True for never profiled."""
        wallet = Wallet(address=WALLET_1, last_profiled_at=None)

        assert profiler._needs_profiling(wallet) is True

    def test_needs_profiling_stale_profile(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test _needs_profiling returns True for stale profile."""
        wallet = Wallet(
            address=WALLET_1,
            last_profiled_at=datetime.utcnow() - timedelta(hours=48),
        )

        assert profiler._needs_profiling(wallet, stale_hours=24) is True

    def test_needs_profiling_recent_profile(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test _needs_profiling returns False for recent profile."""
        wallet = Wallet(
            address=WALLET_1,
            last_profiled_at=datetime.utcnow() - timedelta(hours=12),
        )

        assert profiler._needs_profiling(wallet, stale_hours=24) is False


class TestSwapParsing:
    """Tests for swap transaction parsing."""

    def test_parse_buy_swap(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test parsing a buy swap (SOL -> token)."""
        tx = {
            "tokenIn": {"mint": SOL_MINT, "amount": 1.5},
            "tokenOut": {"mint": TOKEN_MINT, "amount": 1000},
            "timestamp": datetime.utcnow().timestamp(),
        }
        positions: dict = {}

        trade = profiler._parse_swap_transaction(tx, positions)

        assert trade is not None
        assert trade["type"] == "buy"
        assert trade["amount_sol"] == 1.5
        assert trade["amount_token"] == 1000
        assert trade["pnl"] is None

    def test_parse_sell_swap_with_profit(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test parsing a sell swap (token -> SOL) with profit."""
        positions = {
            TOKEN_MINT: {
                "entry_sol": 1.0,
                "entry_time": datetime.utcnow(),
                "tokens": 1000,
            }
        }
        tx = {
            "tokenIn": {"mint": TOKEN_MINT, "amount": 1000},
            "tokenOut": {"mint": SOL_MINT, "amount": 2.0},
            "timestamp": datetime.utcnow().timestamp(),
        }

        trade = profiler._parse_swap_transaction(tx, positions)

        assert trade is not None
        assert trade["type"] == "sell"
        assert trade["amount_sol"] == 2.0
        assert trade["pnl"] == 1.0  # 2.0 - 1.0 entry
        assert trade["is_win"] is True

    def test_parse_sell_swap_with_loss(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test parsing a sell swap with loss."""
        positions = {
            TOKEN_MINT: {
                "entry_sol": 2.0,
                "entry_time": datetime.utcnow(),
                "tokens": 1000,
            }
        }
        tx = {
            "tokenIn": {"mint": TOKEN_MINT, "amount": 1000},
            "tokenOut": {"mint": SOL_MINT, "amount": 1.0},
            "timestamp": datetime.utcnow().timestamp(),
        }

        trade = profiler._parse_swap_transaction(tx, positions)

        assert trade is not None
        assert trade["pnl"] == -1.0  # 1.0 - 2.0 entry
        assert trade["is_win"] is False

    def test_parse_invalid_swap(
        self,
        profiler: WalletProfiler,
    ) -> None:
        """Test parsing invalid swap returns None."""
        tx = {"tokenIn": {}, "tokenOut": {}}  # Missing timestamp
        positions: dict = {}

        trade = profiler._parse_swap_transaction(tx, positions)

        assert trade is None
