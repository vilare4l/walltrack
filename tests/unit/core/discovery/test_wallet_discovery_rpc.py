"""Unit tests for RPC-based wallet discovery logic.

Tests wallet discovery using Solana RPC Public API instead of Helius Enhanced API.
This is the cost-optimized approach for Story 3.1.

Tests focus on:
- Fetching signatures from RPC
- Batch fetching transactions with throttling
- Parsing transactions with shared TransactionParser
- Applying early entry + profitable exit filters
- Database storage (Supabase + Neo4j)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.discovery.wallet_discovery import WalletDiscoveryService
from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.models.wallet import Wallet


class TestWalletDiscoveryRPC:
    """Test RPC-based wallet discovery logic (Story 3.1 Task 3)."""

    @pytest.fixture
    def mock_helius_client(self):
        """Mock Helius client to avoid API key requirement in tests."""
        return MagicMock()

    @pytest.fixture
    def mock_rpc_client(self):
        """Mock RPC client with sample responses."""
        client = AsyncMock()

        # Mock getSignaturesForAddress - returns 6 transaction signatures
        # Wallet1: BUY + SELL (early profitable)
        # Wallet2: BUY only (late)
        # Wallet3: BUY + SELL (low profit)
        client.getSignaturesForAddress.return_value = [
            {
                "signature": "sig1_wallet1_buy",
                "slot": 123456789,
                "blockTime": 1703001234,  # 30 seconds after token launch
            },
            {
                "signature": "sig1_wallet1_sell",
                "slot": 123456790,
                "blockTime": 1703001434,  # 200 seconds after launch (profitable sell)
            },
            {
                "signature": "sig2_wallet2_buy",
                "slot": 123456791,
                "blockTime": 1703003034,  # 30 minutes after token launch (too late)
            },
            {
                "signature": "sig3_wallet3_buy",
                "slot": 123456792,
                "blockTime": 1703001334,  # 2 minutes after token launch (early)
            },
            {
                "signature": "sig3_wallet3_sell",
                "slot": 123456793,
                "blockTime": 1703001534,  # Low profit sell
            },
        ]

        # Mock getTransaction - default side_effect that returns transactions with correct signatures
        # This ensures the parser's side_effect can match the signature correctly
        def get_transaction_default(signature):
            return {
                "transaction": {
                    "signatures": [signature],  # Use the actual signature passed in
                    "message": {},
                },
                "meta": {},
                "blockTime": 1703001234,
            }

        client.getTransaction.side_effect = get_transaction_default

        return client

    @pytest.fixture
    def mock_parser(self):
        """Mock TransactionParser with sample parsed transactions."""
        parser = MagicMock()

        # Valid Solana addresses (44 characters base58)
        # NOTE: Avoid using addresses from KNOWN_PROGRAM_ADDRESSES
        TOKEN_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        WALLET1 = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"  # Early profitable
        WALLET2 = "2wmVCSfPxGPjrnMMn7rchp4uaeoTqN39mXFC2zhPdri9"  # Late buy
        WALLET3 = "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"  # Low profit

        # Configure parser.parse() to return different SwapTransactions based on signature
        def parse_side_effect(raw_tx):
            sig = raw_tx.get("transaction", {}).get("signatures", [""])[0]

            # Wallet1: BUY + SELL (early profitable - should PASS both filters)
            if sig == "sig1_wallet1_buy":
                return SwapTransaction(
                    signature=sig,
                    timestamp=1703001234,  # 30 seconds after launch
                    tx_type=TransactionType.BUY,
                    token_mint=TOKEN_MINT,
                    wallet_address=WALLET1,
                    sol_amount=1.0,
                    token_amount=1000.0,
                )
            elif sig == "sig1_wallet1_sell":
                return SwapTransaction(
                    signature=sig,
                    timestamp=1703001434,  # 200 seconds after launch
                    tx_type=TransactionType.SELL,
                    token_mint=TOKEN_MINT,
                    wallet_address=WALLET1,
                    sol_amount=2.0,  # 100% profit (bought 1 SOL, sold 2 SOL)
                    token_amount=1000.0,
                )

            # Wallet2: BUY only (late - should FAIL early entry filter)
            elif sig == "sig2_wallet2_buy":
                return SwapTransaction(
                    signature=sig,
                    timestamp=1703003034,  # 30 minutes after launch
                    tx_type=TransactionType.BUY,
                    token_mint=TOKEN_MINT,
                    wallet_address=WALLET2,
                    sol_amount=1.0,
                    token_amount=500.0,
                )

            # Wallet3: BUY + SELL (low profit - should FAIL profitable exit filter)
            elif sig == "sig3_wallet3_buy":
                return SwapTransaction(
                    signature=sig,
                    timestamp=1703001334,  # 2 minutes after launch (early)
                    tx_type=TransactionType.BUY,
                    token_mint=TOKEN_MINT,
                    wallet_address=WALLET3,
                    sol_amount=1.0,
                    token_amount=800.0,
                )
            elif sig == "sig3_wallet3_sell":
                return SwapTransaction(
                    signature=sig,
                    timestamp=1703001534,
                    tx_type=TransactionType.SELL,
                    token_mint=TOKEN_MINT,
                    wallet_address=WALLET3,
                    sol_amount=1.3,  # 30% profit (< 50% threshold)
                    token_amount=800.0,
                )

            return None

        parser.parse.side_effect = parse_side_effect
        return parser

    @pytest.fixture
    def mock_wallet_repository(self):
        """Mock WalletRepository for database operations."""
        repo = AsyncMock()

        # Mock create_wallet to return a Wallet instance (simulates successful creation)
        async def create_wallet_mock(wallet_create):
            return Wallet(
                wallet_address=wallet_create.wallet_address,
                token_source=wallet_create.token_source,
                discovery_date="2024-12-20T12:00:00+00:00",
                score=0.0,
                win_rate=0.0,
                decay_status="ok",
                is_blacklisted=False,
            )

        repo.create_wallet.side_effect = create_wallet_mock
        return repo

    @pytest.fixture
    def service(self, mock_helius_client, mock_rpc_client, mock_parser, mock_wallet_repository):
        """Create WalletDiscoveryService with all mocks."""
        with patch("walltrack.core.discovery.wallet_discovery.sync_wallet_to_neo4j", new_callable=AsyncMock) as mock_neo4j_sync:
            # Mock Neo4j sync to always succeed
            mock_neo4j_sync.return_value = True

            service = WalletDiscoveryService(
                helius_client=mock_helius_client,
                rpc_client=mock_rpc_client,
                parser=mock_parser,
                wallet_repository=mock_wallet_repository,
            )

            # Store mock_neo4j_sync for assertions in tests
            service._mock_neo4j_sync = mock_neo4j_sync

            yield service

    @pytest.mark.asyncio
    async def test_discover_wallets_fetches_signatures_from_rpc(
        self, service, mock_rpc_client
    ):
        """Test that discovery calls getSignaturesForAddress to fetch transaction signatures.

        Task 3: Fetch signatures via getSignaturesForAddress(token_mint).
        """

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"  # 1703001200

        await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Verify getSignaturesForAddress was called
        mock_rpc_client.getSignaturesForAddress.assert_called_once_with(
            address=token_mint,
            limit=1000,
        )

    @pytest.mark.asyncio
    async def test_discover_wallets_batch_fetches_transactions(
        self, service, mock_rpc_client
    ):
        """Test that discovery batch fetches transaction details for each signature.

        Task 3: Batch fetch transactions (throttled, with progress logging).
        Note: Throttling is handled by RPC client itself.
        """

        # Mock getTransaction to return raw transaction data
        mock_rpc_client.getTransaction.return_value = {
            "transaction": {"signatures": ["sig1"]},
            "meta": {},
            "blockTime": 1703001234,
        }

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Verify getTransaction was called for each signature (5 times)
        assert mock_rpc_client.getTransaction.call_count == 5

        # Verify correct signatures were fetched
        call_args_list = [call[0][0] for call in mock_rpc_client.getTransaction.call_args_list]
        assert "sig1_wallet1_buy" in call_args_list
        assert "sig1_wallet1_sell" in call_args_list
        assert "sig2_wallet2_buy" in call_args_list
        assert "sig3_wallet3_buy" in call_args_list
        assert "sig3_wallet3_sell" in call_args_list

    @pytest.mark.asyncio
    async def test_discover_wallets_parses_transactions_with_parser(
        self, service, mock_rpc_client, mock_parser
    ):
        """Test that discovery uses TransactionParser to parse each raw transaction.

        Task 3: Parse each transaction using shared parser.
        """

        mock_rpc_client.getTransaction.return_value = {
            "transaction": {"signatures": ["sig1"], "message": {}},
            "meta": {},
            "blockTime": 1703001234,
        }

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Verify parser.parse() was called for each transaction
        assert mock_parser.parse.call_count >= 5

    @pytest.mark.asyncio
    async def test_discover_wallets_filters_early_entry(
        self, service, mock_rpc_client
    ):
        """Test that discovery filters out wallets that bought too late (>30min after launch).

        Task 3: Apply filters: early entry (<30min).
        AC4: Wallets bought within 30 minutes of token launch.
        """

        # Mock getTransaction to trigger parser with correct signatures
        def get_tx_side_effect(signature):
            return {
                "transaction": {"signatures": [signature], "message": {}},
                "meta": {},
                "blockTime": 1703001234,
                "_mock_type": "BUY" if "buy" in signature else "SELL",
            }

        mock_rpc_client.getTransaction.side_effect = get_tx_side_effect

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"  # 1703001200

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Wallet2 (late buy) should be filtered out (bought at 1703003034 = 30min 34s after launch)
        assert "2wmVCSfPxGPjrnMMn7rchp4uaeoTqN39mXFC2zhPdri9" not in wallets

        # Wallet1 and Wallet3 bought early (should pass early filter)
        # Note: Wallet3 will be filtered by profit filter in next step

    @pytest.mark.asyncio
    async def test_discover_wallets_filters_profitable_exit(
        self, service, mock_rpc_client
    ):
        """Test that discovery filters out wallets with <50% profit.

        Task 3: Apply filters: profitable exit (>50%).
        AC4: Wallets sold with >50% profit.
        """

        def get_tx_side_effect(signature):
            return {
                "transaction": {"signatures": [signature], "message": {}},
                "meta": {},
                "blockTime": 1703001234,
                "_mock_type": "BUY" if "buy" in signature else "SELL",
            }

        mock_rpc_client.getTransaction.side_effect = get_tx_side_effect

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Wallet3 (low profit) should be filtered out (30% profit < 50% threshold)
        assert "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf" not in wallets

    @pytest.mark.asyncio
    async def test_discover_wallets_returns_smart_money_addresses(
        self, service, mock_rpc_client
    ):
        """Test that discovery returns only wallets passing BOTH filters.

        Task 3: Collect smart money wallet addresses.
        AC4: Wallets are "performers" (early entry + profitable exit).
        """

        # Use default mock from fixture - no override needed
        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Only Wallet1 (early profitable) should pass both filters
        # - Early entry: 30 seconds after launch (<30min) ✓
        # - Profitable exit: 100% profit (>50%) ✓
        assert len(wallets) == 1
        assert "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" in wallets

    @pytest.mark.asyncio
    async def test_discover_wallets_handles_no_transactions(
        self, service, mock_rpc_client
    ):
        """Test that discovery handles tokens with no transactions gracefully."""
        # Mock empty signatures list
        mock_rpc_client.getSignaturesForAddress.return_value = []

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        assert wallets == []
        # getTransaction should not be called if no signatures
        mock_rpc_client.getTransaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_wallets_skips_invalid_transactions(
        self, service, mock_rpc_client, mock_parser
    ):
        """Test that discovery skips transactions that fail to parse."""
        # Clear side_effect and set return_value to None for invalid transactions
        mock_parser.parse.side_effect = None
        mock_parser.parse.return_value = None

        mock_rpc_client.getTransaction.return_value = {
            "transaction": {"signatures": ["invalid_tx"], "message": {}},
            "meta": {},
        }

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Should return empty list (all transactions invalid)
        assert wallets == []

    @pytest.mark.asyncio
    async def test_discover_wallets_stores_to_supabase(
        self, service, mock_rpc_client, mock_wallet_repository
    ):
        """Test that discovery stores wallets to Supabase via wallet_repository.

        Task 4: Save wallets to Supabase via `wallet_repo.create_wallet()`.
        AC5: Wallets saved to Supabase `wallets` table.
        """
        def get_tx_side_effect(signature):
            return {
                "transaction": {"signatures": [signature], "message": {}},
                "meta": {},
                "blockTime": 1703001234,
            }

        mock_rpc_client.getTransaction.side_effect = get_tx_side_effect

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Verify wallet_repository.create_wallet was called for discovered wallet
        assert len(wallets) == 1
        assert mock_wallet_repository.create_wallet.call_count == 1

        # Verify correct wallet data was passed
        call_args = mock_wallet_repository.create_wallet.call_args[0][0]
        assert call_args.wallet_address == "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
        assert call_args.token_source == token_mint

    @pytest.mark.asyncio
    async def test_discover_wallets_syncs_to_neo4j(
        self, service, mock_rpc_client
    ):
        """Test that discovery syncs wallets to Neo4j via sync_wallet_to_neo4j.

        Task 4: Create Neo4j Wallet nodes via `neo4j_wallet_queries.create_wallet_node()`.
        AC5: Neo4j Wallet nodes created with properties.
        """
        def get_tx_side_effect(signature):
            return {
                "transaction": {"signatures": [signature], "message": {}},
                "meta": {},
                "blockTime": 1703001234,
            }

        mock_rpc_client.getTransaction.side_effect = get_tx_side_effect

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Verify sync_wallet_to_neo4j was called for discovered wallet
        assert len(wallets) == 1
        assert service._mock_neo4j_sync.call_count == 1

        # Verify correct wallet address was passed
        call_args = service._mock_neo4j_sync.call_args[0][0]
        assert call_args == "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"

    @pytest.mark.asyncio
    async def test_discover_wallets_handles_storage_errors(
        self, service, mock_rpc_client, mock_wallet_repository
    ):
        """Test that discovery continues even if storage fails (non-fatal errors).

        Task 4: Error handling for database operations.
        """
        # Mock create_wallet to raise an exception
        mock_wallet_repository.create_wallet.side_effect = Exception("Database error")

        def get_tx_side_effect(signature):
            return {
                "transaction": {"signatures": [signature], "message": {}},
                "meta": {},
                "blockTime": 1703001234,
            }

        mock_rpc_client.getTransaction.side_effect = get_tx_side_effect

        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        token_launch_time = "2024-12-20T12:00:00+00:00"

        # Should not raise exception (storage errors are non-fatal)
        wallets = await service.discover_wallets_from_token_rpc(token_mint, token_launch_time)

        # Wallet discovery should still succeed
        assert len(wallets) == 1
        assert "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU" in wallets
