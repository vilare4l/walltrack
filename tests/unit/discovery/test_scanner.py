"""Tests for wallet discovery scanner."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.data.models.wallet import TokenLaunch, Wallet
from walltrack.discovery.scanner import WalletDiscoveryScanner

# Valid Solana addresses for testing (44 characters, base58)
WALLET_1 = "A" * 44  # Valid 44-char address
WALLET_2 = "B" * 44
TOKEN_MINT = "C" * 44


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    repo.upsert.return_value = (MagicMock(spec=Wallet), True)
    return repo


@pytest.fixture
def mock_neo4j_client() -> MagicMock:
    """Mock Neo4j client."""
    client = MagicMock()
    session = AsyncMock()

    # Create proper async context manager mock
    context_manager = AsyncMock()
    context_manager.__aenter__.return_value = session
    context_manager.__aexit__.return_value = None

    client.session.return_value = context_manager
    return client


@pytest.fixture
def mock_helius_client() -> AsyncMock:
    """Mock Helius client."""
    client = AsyncMock()
    client.get_token_transactions.return_value = [
        {"buyer": WALLET_1, "timestamp": datetime.utcnow(), "amount": 1.0},
        {"buyer": WALLET_2, "timestamp": datetime.utcnow(), "amount": 2.0},
    ]
    return client


@pytest.fixture
def scanner(
    mock_wallet_repo: AsyncMock,
    mock_neo4j_client: AsyncMock,
    mock_helius_client: AsyncMock,
) -> WalletDiscoveryScanner:
    """Create scanner with mocked dependencies."""
    return WalletDiscoveryScanner(
        wallet_repo=mock_wallet_repo,
        neo4j_client=mock_neo4j_client,
        helius_client=mock_helius_client,
    )


class TestWalletDiscoveryScanner:
    """Tests for WalletDiscoveryScanner."""

    @pytest.mark.asyncio
    async def test_discover_from_token_success(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test successful wallet discovery."""
        # Setup sells for profitable exit
        mock_helius_client.get_token_transactions.side_effect = [
            # First call: early buyers
            [
                {"buyer": WALLET_1, "timestamp": datetime.utcnow(), "amount": 1.0},
            ],
            # Second call: sells for wallet1
            [{"amount": 2.0}],  # 100% profit
        ]

        token = TokenLaunch(
            mint=TOKEN_MINT,
            symbol="TEST",
            launch_time=datetime.utcnow() - timedelta(hours=1),
            peak_mcap=1000000,
        )

        result = await scanner.discover_from_token(token)

        assert result.token_mint == TOKEN_MINT
        assert result.duration_seconds > 0
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_discover_filters_unprofitable(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that unprofitable wallets are filtered out."""
        mock_helius_client.get_token_transactions.side_effect = [
            # Early buyers
            [{"buyer": WALLET_1, "timestamp": datetime.utcnow(), "amount": 1.0}],
            # Sells - only 10% profit (below 50% threshold)
            [{"amount": 1.1}],
        ]

        token = TokenLaunch(
            mint=TOKEN_MINT,
            symbol="TEST",
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        result = await scanner.discover_from_token(token, min_profit_pct=50.0)

        # Should not add any wallets due to low profit
        assert result.new_wallets == 0

    @pytest.mark.asyncio
    async def test_discover_handles_duplicate_wallets(
        self,
        scanner: WalletDiscoveryScanner,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that existing wallets are updated, not duplicated."""
        mock_wallet_repo.upsert.return_value = (MagicMock(spec=Wallet), False)  # Not new

        mock_helius_client.get_token_transactions.side_effect = [
            [{"buyer": WALLET_1, "timestamp": datetime.utcnow(), "amount": 1.0}],
            [{"amount": 2.0}],
        ]

        token = TokenLaunch(
            mint=TOKEN_MINT,
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        result = await scanner.discover_from_token(token)

        assert result.new_wallets == 0
        assert result.updated_wallets == 1

    @pytest.mark.asyncio
    async def test_discover_from_multiple_tokens(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test batch discovery from multiple tokens."""
        mock_helius_client.get_token_transactions.return_value = []

        tokens = [
            TokenLaunch(mint="D" * 44 + str(i).zfill(4)[0:4], launch_time=datetime.utcnow())
            for i in range(3)
        ]

        results = await scanner.discover_from_multiple_tokens(tokens)

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_discover_handles_no_early_buyers(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test handling when no early buyers found."""
        mock_helius_client.get_token_transactions.return_value = []

        token = TokenLaunch(
            mint=TOKEN_MINT,
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        result = await scanner.discover_from_token(token)

        assert result.new_wallets == 0
        assert result.updated_wallets == 0
        assert result.total_processed == 0

    @pytest.mark.asyncio
    async def test_discover_handles_api_error(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test error handling when API fails."""
        mock_helius_client.get_token_transactions.side_effect = Exception("API Error")

        token = TokenLaunch(
            mint=TOKEN_MINT,
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        result = await scanner.discover_from_token(token)

        assert result.new_wallets == 0
        assert len(result.errors) > 0
        assert "Discovery failed" in result.errors[0]

    @pytest.mark.asyncio
    async def test_discover_concurrent_limit(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that concurrent discoveries are limited."""
        mock_helius_client.get_token_transactions.return_value = []

        # Create more tokens than max_concurrent
        tokens = [
            TokenLaunch(
                mint="E" * 40 + str(i).zfill(4),
                launch_time=datetime.utcnow(),
            )
            for i in range(10)
        ]

        results = await scanner.discover_from_multiple_tokens(tokens, max_concurrent=3)

        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_discover_stores_in_both_databases(
        self,
        scanner: WalletDiscoveryScanner,
        mock_wallet_repo: AsyncMock,
        mock_neo4j_client: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that wallets are stored in both Supabase and Neo4j."""
        mock_helius_client.get_token_transactions.side_effect = [
            [{"buyer": WALLET_1, "timestamp": datetime.utcnow(), "amount": 1.0}],
            [{"amount": 2.0}],  # 100% profit
        ]

        token = TokenLaunch(
            mint=TOKEN_MINT,
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        await scanner.discover_from_token(token)

        # Verify Supabase was called
        mock_wallet_repo.upsert.assert_called_once()

        # Verify Neo4j session was used
        mock_neo4j_client.session.assert_called()
