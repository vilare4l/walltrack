"""Unit tests for Solana RPC transaction parser.

Tests parsing of raw RPC transaction data into SwapTransaction models.
Uses real Solana transaction samples to validate BUY/SELL detection logic.
"""

import pytest

from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.services.solana.transaction_parser import TransactionParser


class TestTransactionParser:
    """Test transaction parser with various transaction types."""

    @pytest.fixture
    def parser(self) -> TransactionParser:
        """Create transaction parser instance."""
        return TransactionParser()

    @pytest.fixture
    def sample_buy_transaction(self) -> dict:
        """Sample Solana BUY transaction (SOL -> Token).

        This is a simplified real RPC transaction structure from getTransaction.
        Represents: Wallet bought tokens by spending SOL.
        """
        return {
            "slot": 123456789,
            "transaction": {
                "message": {
                    "accountKeys": [
                        "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",  # Wallet
                        "So11111111111111111111111111111111111111112",  # WSOL mint
                        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Token mint
                    ],
                    "instructions": [
                        {
                            "programId": "11111111111111111111111111111111",
                            "accounts": [0, 1],
                            "data": "transfer",
                        }
                    ],
                },
                "signatures": [
                    "5j7s8k2d3f4g5h6j7k8l9m0n1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j"
                ],
            },
            "meta": {
                "err": None,
                "preBalances": [1000000000, 2000000000],  # lamports before
                "postBalances": [500000000, 2500000000],  # lamports after
                "preTokenBalances": [],
                "postTokenBalances": [
                    {
                        "accountIndex": 2,
                        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        "uiTokenAmount": {
                            "amount": "1000000",
                            "decimals": 6,
                            "uiAmount": 1.0,
                        },
                    }
                ],
            },
            "blockTime": 1703001234,
        }

    @pytest.fixture
    def sample_sell_transaction(self) -> dict:
        """Sample Solana SELL transaction (Token -> SOL).

        Represents: Wallet sold tokens to receive SOL.
        """
        return {
            "slot": 123456790,
            "transaction": {
                "message": {
                    "accountKeys": [
                        "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",  # Wallet
                        "So11111111111111111111111111111111111111112",  # WSOL mint
                        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Token mint
                    ],
                    "instructions": [
                        {
                            "programId": "11111111111111111111111111111111",
                            "accounts": [0, 1],
                            "data": "transfer",
                        }
                    ],
                },
                "signatures": [
                    "2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b0c1d2e3f4g"
                ],
            },
            "meta": {
                "err": None,
                "preBalances": [500000000, 2500000000],  # lamports before
                "postBalances": [1500000000, 1500000000],  # lamports after (gained SOL)
                "preTokenBalances": [
                    {
                        "accountIndex": 2,
                        "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                        "uiTokenAmount": {
                            "amount": "1000000",
                            "decimals": 6,
                            "uiAmount": 1.0,
                        },
                    }
                ],
                "postTokenBalances": [],  # Token balance gone (sold)
            },
            "blockTime": 1703005678,
        }

    @pytest.fixture
    def non_swap_transaction(self) -> dict:
        """Sample non-swap transaction (transfer only)."""
        return {
            "slot": 123456791,
            "transaction": {
                "message": {
                    "accountKeys": [
                        "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                        "7xRqWvH927cVy8DPkYmbT34zxYN3ZWcssqZc8QvtVGjp",
                    ],
                    "instructions": [
                        {
                            "programId": "11111111111111111111111111111111",
                            "accounts": [0, 1],
                            "data": "transfer",
                        }
                    ],
                },
                "signatures": ["3c4d5e6f7g8h9i0j1k2l3m4n5o6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i"],
            },
            "meta": {
                "err": None,
                "preBalances": [1000000000, 500000000],
                "postBalances": [900000000, 600000000],
                "preTokenBalances": [],
                "postTokenBalances": [],
            },
            "blockTime": 1703009999,
        }

    def test_parse_buy_transaction(
        self, parser: TransactionParser, sample_buy_transaction: dict
    ):
        """Test parsing a BUY transaction (SOL -> Token).

        AC3: System identifies BUY/SELL events from raw instructions.
        AC3: Extracts wallet_address, token_amount, sol_amount, timestamp, direction.
        """
        result = parser.parse(sample_buy_transaction)

        assert result is not None
        assert isinstance(result, SwapTransaction)
        assert result.tx_type == TransactionType.BUY
        assert result.wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        assert result.token_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        assert result.token_amount == 1.0  # 1 token (6 decimals)
        assert result.sol_amount == 0.5  # Lost 0.5 SOL (500M lamports)
        assert result.timestamp == 1703001234
        assert len(result.signature) > 0

    def test_parse_sell_transaction(
        self, parser: TransactionParser, sample_sell_transaction: dict
    ):
        """Test parsing a SELL transaction (Token -> SOL).

        AC3: System identifies BUY/SELL events from raw instructions.
        """
        result = parser.parse(sample_sell_transaction)

        assert result is not None
        assert isinstance(result, SwapTransaction)
        assert result.tx_type == TransactionType.SELL
        assert result.wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        assert result.token_mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        assert result.token_amount == 1.0  # Sold 1 token
        assert result.sol_amount == 1.0  # Gained 1 SOL (1B lamports)
        assert result.timestamp == 1703005678

    def test_parse_non_swap_transaction(
        self, parser: TransactionParser, non_swap_transaction: dict
    ):
        """Test rejecting non-swap transactions.

        AC3: Parsing logic rejects non-SWAP transactions.
        """
        result = parser.parse(non_swap_transaction)

        assert result is None, "Non-swap transaction should return None"

    def test_parse_invalid_transaction_missing_meta(self, parser: TransactionParser):
        """Test handling transaction with missing meta field."""
        invalid_tx = {
            "slot": 123,
            "transaction": {"message": {}, "signatures": ["abc"]},
            # Missing "meta"
            "blockTime": 1703001234,
        }

        result = parser.parse(invalid_tx)
        assert result is None

    def test_parse_invalid_transaction_with_error(self, parser: TransactionParser):
        """Test handling failed transactions (meta.err not None)."""
        failed_tx = {
            "slot": 123,
            "transaction": {"message": {}, "signatures": ["abc"]},
            "meta": {"err": {"InstructionError": [0, "Custom"]}, "preBalances": []},
            "blockTime": 1703001234,
        }

        result = parser.parse(failed_tx)
        assert result is None

    def test_parse_transaction_missing_token_balance_change(
        self, parser: TransactionParser
    ):
        """Test transaction with SOL change but no token balance change."""
        tx = {
            "slot": 123456789,
            "transaction": {
                "message": {
                    "accountKeys": [
                        "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
                    ],
                    "instructions": [],
                },
                "signatures": ["sig123"],
            },
            "meta": {
                "err": None,
                "preBalances": [1000000000],
                "postBalances": [500000000],
                "preTokenBalances": [],
                "postTokenBalances": [],  # No token change
            },
            "blockTime": 1703001234,
        }

        result = parser.parse(tx)
        assert result is None, "Transaction without token balance change is not a swap"

    def test_parse_transaction_multi_hop_swap(self, parser: TransactionParser):
        """Test handling multi-hop swap (Token A -> Token B -> Token C).

        AC3: Handle edge cases: multi-hop swaps.
        Note: Current implementation should handle first detected token change.
        """
        multi_hop_tx = {
            "slot": 123456789,
            "transaction": {
                "message": {
                    "accountKeys": ["9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"],
                    "instructions": [],
                },
                "signatures": ["multihop_sig"],
            },
            "meta": {
                "err": None,
                "preBalances": [1000000000],
                "postBalances": [800000000],  # Lost 0.2 SOL
                "preTokenBalances": [],
                "postTokenBalances": [
                    {
                        "accountIndex": 1,
                        "mint": "TokenA111111111111111111111111111111111111",
                        "uiTokenAmount": {"amount": "500", "decimals": 2, "uiAmount": 5.0},
                    },
                    {
                        "accountIndex": 2,
                        "mint": "TokenB222222222222222222222222222222222222",
                        "uiTokenAmount": {"amount": "1000", "decimals": 3, "uiAmount": 1.0},
                    },
                ],
            },
            "blockTime": 1703001234,
        }

        result = parser.parse(multi_hop_tx)
        # Should parse as BUY for the first detected token
        assert result is not None
        assert result.tx_type == TransactionType.BUY
        assert result.token_mint in [
            "TokenA111111111111111111111111111111111111",
            "TokenB222222222222222222222222222222222222",
        ]
