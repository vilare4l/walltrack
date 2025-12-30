"""Unit tests for WalletDiscoveryService (Story 3.1 - Helius approach).

Tests cover:
- Early profitable buyer detection via Helius transaction history
- Filter #1: Early entry (BUY within 30min of token launch)
- Filter #2: Profitable exit (SELL with >50% profit)
- SwapDetails parsing for BUY/SELL detection
- Program address filtering
"""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, patch

import pytest

from walltrack.services.helius.models import Transaction


class TestWalletDiscoveryService:
    """Tests for WalletDiscoveryService with Helius early profitable buyer filtering."""

    @pytest.fixture
    def token_address(self) -> str:
        """Sample token mint address."""
        return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC

    @pytest.fixture
    def token_launch_timestamp(self) -> int:
        """Token launch time (Unix timestamp)."""
        # 2024-01-01 00:00:00 UTC
        return 1704067200

    @pytest.fixture
    def token_created_at(self, token_launch_timestamp: int) -> str:
        """Token launch time (ISO format)."""
        return datetime.fromtimestamp(token_launch_timestamp, tz=UTC).isoformat()

    @pytest.fixture
    def early_profitable_buyer_transactions(
        self, token_address: str, token_launch_timestamp: int
    ) -> list[dict]:
        """Mock transactions for a wallet that bought early and sold profitably.

        Wallet1 behavior:
        - BUY at launch + 15min (EARLY ✓)
        - SELL at launch + 60min with 60% profit (PROFITABLE ✓)
        → Should be INCLUDED
        """
        return [
            # BUY transaction (15min after launch)
            {
                "signature": "buy_tx_wallet1",
                "timestamp": token_launch_timestamp + (15 * 60),  # +15min
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "Wallet1abc",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000  # 0.5 SOL out (BUY)
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet1abc",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0
                    }
                ],
            },
            # SELL transaction (60min after launch, 60% profit)
            {
                "signature": "sell_tx_wallet1",
                "timestamp": token_launch_timestamp + (60 * 60),  # +60min
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet1abc",
                        "amount": 800_000_000  # 0.8 SOL in (SELL) = 60% profit
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "Wallet1abc",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0
                    }
                ],
            },
        ]

    @pytest.fixture
    def late_buyer_transactions(
        self, token_address: str, token_launch_timestamp: int
    ) -> list[dict]:
        """Mock transactions for a wallet that bought too late.

        Wallet2 behavior:
        - BUY at launch + 45min (LATE ✗ - should be < 30min)
        - SELL with 60% profit
        → Should be EXCLUDED (late entry)
        """
        return [
            # BUY transaction (45min after launch - TOO LATE)
            {
                "signature": "buy_tx_wallet2",
                "timestamp": token_launch_timestamp + (45 * 60),  # +45min
                "type": "SWAP",
                "source": "JUPITER",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "Wallet2xyz",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet2xyz",
                        "mint": token_address,
                        "tokenAmount": 500_000.0
                    }
                ],
            },
            # SELL transaction (profitable but irrelevant due to late entry)
            {
                "signature": "sell_tx_wallet2",
                "timestamp": token_launch_timestamp + (90 * 60),
                "type": "SWAP",
                "source": "JUPITER",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet2xyz",
                        "amount": 800_000_000
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "Wallet2xyz",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 500_000.0
                    }
                ],
            },
        ]

    @pytest.fixture
    def unprofitable_exit_transactions(
        self, token_address: str, token_launch_timestamp: int
    ) -> list[dict]:
        """Mock transactions for a wallet with unprofitable exit.

        Wallet3 behavior:
        - BUY at launch + 10min (EARLY ✓)
        - SELL with only 30% profit (UNPROFITABLE ✗ - should be > 50%)
        → Should be EXCLUDED (insufficient profit)
        """
        return [
            # BUY transaction (10min after launch - EARLY)
            {
                "signature": "buy_tx_wallet3",
                "timestamp": token_launch_timestamp + (10 * 60),  # +10min
                "type": "SWAP",
                "source": "ORCA",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "Wallet3def",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet3def",
                        "mint": token_address,
                        "tokenAmount": 2_000_000.0
                    }
                ],
            },
            # SELL transaction (only 30% profit - NOT ENOUGH)
            {
                "signature": "sell_tx_wallet3",
                "timestamp": token_launch_timestamp + (50 * 60),
                "type": "SWAP",
                "source": "ORCA",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet3def",
                        "amount": 650_000_000  # 0.65 SOL = 30% profit (< 50%)
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "Wallet3def",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 2_000_000.0
                    }
                ],
            },
        ]

    @pytest.mark.asyncio
    async def test_discover_early_profitable_buyers_success(
        self,
        token_address: str,
        token_created_at: str,
        early_profitable_buyer_transactions: list[dict],
    ):
        """Should discover wallets that bought early AND sold profitably."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Mock HeliusClient to return early profitable buyer transactions
        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = (
            early_profitable_buyer_transactions
        )

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should include Wallet1 (early + profitable)
        assert len(wallets) == 1
        assert "Wallet1abc" in wallets

    @pytest.mark.asyncio
    async def test_discover_filters_late_buyers(
        self,
        token_address: str,
        token_created_at: str,
        late_buyer_transactions: list[dict],
    ):
        """Should exclude wallets that bought after 30min window."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = late_buyer_transactions

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should exclude Wallet2 (late entry)
        assert len(wallets) == 0
        assert "Wallet2xyz" not in wallets

    @pytest.mark.asyncio
    async def test_discover_filters_unprofitable_exits(
        self,
        token_address: str,
        token_created_at: str,
        unprofitable_exit_transactions: list[dict],
    ):
        """Should exclude wallets with < 50% profit on exit."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = (
            unprofitable_exit_transactions
        )

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should exclude Wallet3 (insufficient profit)
        assert len(wallets) == 0
        assert "Wallet3def" not in wallets

    @pytest.mark.asyncio
    async def test_discover_filters_holders_without_sell(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should exclude wallets that bought but never sold (bag holders)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Only BUY transaction, no SELL
        holder_transactions = [
            {
                "signature": "buy_tx_wallet4",
                "timestamp": token_launch_timestamp + (5 * 60),  # Early buy
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "Wallet4holder",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "Wallet4holder",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            }
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = holder_transactions

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should exclude bag holders (no sell = no proven performance)
        assert len(wallets) == 0
        assert "Wallet4holder" not in wallets

    @pytest.mark.asyncio
    async def test_discover_empty_when_no_transactions(
        self, token_address: str, token_created_at: str
    ):
        """Should return empty list when no transactions found."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = []

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        assert isinstance(wallets, list)
        assert len(wallets) == 0

    @pytest.mark.asyncio
    async def test_discover_filters_program_addresses(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should exclude known program addresses (DEX contracts)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Transaction with Jupiter program address
        program_transactions = [
            {
                "signature": "tx_with_program",
                "timestamp": token_launch_timestamp + (10 * 60),
                "type": "SWAP",
                "source": "JUPITER",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",  # Jupiter program
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            }
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = program_transactions

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Jupiter program should be filtered out
        assert len(wallets) == 0
        assert "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB" not in wallets

    @pytest.mark.asyncio
    async def test_discover_multiple_profitable_buyers(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should discover multiple wallets when they all meet criteria."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Two profitable buyers
        multi_wallet_transactions = [
            # Wallet A - BUY early
            {
                "signature": "buy_a",
                "timestamp": token_launch_timestamp + (10 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "WalletA",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletA",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
            # Wallet A - SELL profitably
            {
                "signature": "sell_a",
                "timestamp": token_launch_timestamp + (40 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletA",
                        "amount": 800_000_000,  # 60% profit
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "WalletA",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
            # Wallet B - BUY early
            {
                "signature": "buy_b",
                "timestamp": token_launch_timestamp + (20 * 60),
                "type": "SWAP",
                "source": "JUPITER",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "WalletB",
                        "toUserAccount": "PoolXYZ",
                        "amount": 1_000_000_000,
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletB",
                        "mint": token_address,
                        "tokenAmount": 2_000_000.0,
                    }
                ],
            },
            # Wallet B - SELL profitably
            {
                "signature": "sell_b",
                "timestamp": token_launch_timestamp + (50 * 60),
                "type": "SWAP",
                "source": "JUPITER",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletB",
                        "amount": 1_600_000_000,  # 60% profit
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "WalletB",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 2_000_000.0,
                    }
                ],
            },
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = multi_wallet_transactions

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should discover both profitable buyers
        assert len(wallets) == 2
        assert "WalletA" in wallets
        assert "WalletB" in wallets

    @pytest.mark.asyncio
    async def test_discover_fetches_token_created_at_from_database(
        self,
        token_address: str,
        token_launch_timestamp: int,
        early_profitable_buyer_transactions: list[dict],
    ):
        """Should fetch token.created_at from database when not provided."""
        from datetime import datetime, UTC
        from unittest.mock import AsyncMock

        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService
        from walltrack.data.models.token import Token

        # Create mock Token with created_at
        mock_token = Token(
            mint=token_address,
            symbol="TEST",
            name="Test Token",
            created_at=datetime.fromtimestamp(token_launch_timestamp, tz=UTC),
        )

        # Mock TokenRepository.get_by_mint to return token
        mock_token_repo = AsyncMock()
        mock_token_repo.get_by_mint.return_value = mock_token

        # Mock HeliusClient
        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = (
            early_profitable_buyer_transactions
        )

        # Create service with mocked token_repo
        service = WalletDiscoveryService(
            helius_client=mock_helius_client,
            token_repository=mock_token_repo,
        )

        # Call WITHOUT token_created_at - should fetch from database
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=None,  # Not provided - will be fetched from DB
        )

        # Verify TokenRepository.get_by_mint was called
        mock_token_repo.get_by_mint.assert_called_once_with(token_address)

        # Verify wallets discovered correctly (early profitable buyer)
        assert len(wallets) == 1
        assert "Wallet1abc" in wallets

    @pytest.mark.asyncio
    async def test_discover_handles_timezone_naive_datetime(
        self,
        token_address: str,
        token_launch_timestamp: int,
        early_profitable_buyer_transactions: list[dict],
    ):
        """Should handle timezone-naive datetime by forcing UTC (Fix #3)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Create datetime WITHOUT timezone (naive)
        naive_datetime_str = datetime.fromtimestamp(token_launch_timestamp).isoformat()

        # Mock HeliusClient
        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = (
            early_profitable_buyer_transactions
        )

        service = WalletDiscoveryService(helius_client=mock_helius_client)

        # Should handle naive datetime and apply UTC
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=naive_datetime_str,
        )

        # Should still discover wallet (timezone fixed internally)
        assert len(wallets) == 1
        assert "Wallet1abc" in wallets

    @pytest.mark.asyncio
    async def test_discover_rejects_invalid_token_address_length(
        self, token_created_at: str
    ):
        """Should reject token addresses with invalid length (Fix #15)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        mock_helius_client = AsyncMock()
        service = WalletDiscoveryService(helius_client=mock_helius_client)

        # Test too short (< 32 characters)
        short_address = "EPjFWdd5"
        wallets = await service.discover_wallets_from_token(
            token_address=short_address,
            token_created_at=token_created_at,
        )
        assert len(wallets) == 0

        # Test too long (> 44 characters)
        long_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v12345678901234567890"
        wallets = await service.discover_wallets_from_token(
            token_address=long_address,
            token_created_at=token_created_at,
        )
        assert len(wallets) == 0

    @pytest.mark.asyncio
    async def test_discover_rejects_invalid_token_address_characters(
        self, token_created_at: str
    ):
        """Should reject token addresses with invalid Base58 characters (Fix #15)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        mock_helius_client = AsyncMock()
        service = WalletDiscoveryService(helius_client=mock_helius_client)

        # Invalid characters: 0 (zero), O (capital o), I (capital i), l (lowercase L)
        invalid_addresses = [
            "0PjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # starts with 0
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1O",  # contains O
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1I",  # contains I
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDtlv",  # contains l
        ]

        for invalid_address in invalid_addresses:
            wallets = await service.discover_wallets_from_token(
                token_address=invalid_address,
                token_created_at=token_created_at,
            )
            assert len(wallets) == 0

    @pytest.mark.asyncio
    async def test_discover_filters_partial_sells(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should filter wallets that sold < 90% of their position (Fix #7)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Wallet buys 1M tokens, sells only 500K (50% - partial exit)
        partial_sell_transactions = [
            # BUY 1M tokens (early)
            {
                "signature": "buy_partial",
                "timestamp": token_launch_timestamp + (10 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "WalletPartialSeller",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,  # 0.5 SOL
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletPartialSeller",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,  # Bought 1M tokens
                    }
                ],
            },
            # SELL only 500K tokens (50% exit - NOT ENOUGH)
            {
                "signature": "sell_partial",
                "timestamp": token_launch_timestamp + (40 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletPartialSeller",
                        "amount": 800_000_000,  # 0.8 SOL (60% profit on SOLD portion)
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "WalletPartialSeller",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 500_000.0,  # Sold only 500K (50% of position)
                    }
                ],
            },
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = (
            partial_sell_transactions
        )

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should filter out - only sold 50% (needs ≥90%)
        assert len(wallets) == 0
        assert "WalletPartialSeller" not in wallets

    @pytest.mark.asyncio
    async def test_discover_allows_full_position_exit(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should allow wallets that sold ≥90% of their position (Fix #7)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Wallet buys 1M tokens, sells 950K (95% - full exit)
        full_exit_transactions = [
            # BUY 1M tokens
            {
                "signature": "buy_full",
                "timestamp": token_launch_timestamp + (10 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "WalletFullSeller",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletFullSeller",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
            # SELL 950K tokens (95% exit - VALID)
            {
                "signature": "sell_full",
                "timestamp": token_launch_timestamp + (40 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletFullSeller",
                        "amount": 800_000_000,  # 60% profit
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "WalletFullSeller",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 950_000.0,  # Sold 95% of position
                    }
                ],
            },
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = full_exit_transactions

        service = WalletDiscoveryService(helius_client=mock_helius_client)
        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should be discovered (95% >= 90%)
        assert len(wallets) == 1
        assert "WalletFullSeller" in wallets

    @pytest.mark.asyncio
    async def test_discover_respects_custom_max_transactions(
        self,
        token_address: str,
        token_created_at: str,
    ):
        """Should respect custom max_transactions parameter (Fix #6)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = []

        # Create service with custom max_transactions
        service = WalletDiscoveryService(
            helius_client=mock_helius_client,
            max_transactions=10000,  # Custom value
        )

        await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Verify HeliusClient called with correct limit
        mock_helius_client.get_token_transactions.assert_called_once_with(
            token_mint=token_address,
            limit=10000,
            tx_type="SWAP",
        )

    @pytest.mark.asyncio
    async def test_discover_respects_custom_early_window(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should respect custom early_window_minutes parameter (Fix #12)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Wallet buys at 45min (would fail default 30min window)
        late_for_default_transactions = [
            {
                "signature": "buy_45min",
                "timestamp": token_launch_timestamp + (45 * 60),  # 45min
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "WalletLateForDefault",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletLateForDefault",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
            {
                "signature": "sell_45min",
                "timestamp": token_launch_timestamp + (90 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletLateForDefault",
                        "amount": 800_000_000,  # 60% profit
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "WalletLateForDefault",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = (
            late_for_default_transactions
        )

        # Create service with custom 60min early window
        service = WalletDiscoveryService(
            helius_client=mock_helius_client,
            early_window_minutes=60,  # Extended window
        )

        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should be discovered with 60min window (45min < 60min)
        assert len(wallets) == 1
        assert "WalletLateForDefault" in wallets

    @pytest.mark.asyncio
    async def test_discover_respects_custom_min_profit_ratio(
        self,
        token_address: str,
        token_created_at: str,
        token_launch_timestamp: int,
    ):
        """Should respect custom min_profit_ratio parameter (Fix #12)."""
        from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService

        # Wallet with 40% profit (would fail default 50% minimum)
        low_profit_transactions = [
            {
                "signature": "buy_low_profit",
                "timestamp": token_launch_timestamp + (10 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "WalletLowProfit",
                        "toUserAccount": "PoolXYZ",
                        "amount": 500_000_000,  # 0.5 SOL
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletLowProfit",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
            {
                "signature": "sell_low_profit",
                "timestamp": token_launch_timestamp + (40 * 60),
                "type": "SWAP",
                "source": "RAYDIUM",
                "nativeTransfers": [
                    {
                        "fromUserAccount": "PoolXYZ",
                        "toUserAccount": "WalletLowProfit",
                        "amount": 700_000_000,  # 0.7 SOL = 40% profit
                    }
                ],
                "tokenTransfers": [
                    {
                        "fromUserAccount": "WalletLowProfit",
                        "toUserAccount": "PoolXYZ",
                        "mint": token_address,
                        "tokenAmount": 1_000_000.0,
                    }
                ],
            },
        ]

        mock_helius_client = AsyncMock()
        mock_helius_client.get_token_transactions.return_value = low_profit_transactions

        # Create service with custom 30% minimum profit
        service = WalletDiscoveryService(
            helius_client=mock_helius_client,
            min_profit_ratio=0.30,  # Lower threshold
        )

        wallets = await service.discover_wallets_from_token(
            token_address=token_address,
            token_created_at=token_created_at,
        )

        # Should be discovered with 30% threshold (40% > 30%)
        assert len(wallets) == 1
        assert "WalletLowProfit" in wallets
