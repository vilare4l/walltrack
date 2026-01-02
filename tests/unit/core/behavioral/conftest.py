"""Shared fixtures for behavioral profiling tests."""

import pytest

from walltrack.data.models.transaction import SwapTransaction, TransactionType


# Valid Solana addresses for testing (44 characters, base58 encoded)
VALID_WALLET_ADDRESS = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
VALID_TOKEN_MINT_ABC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC mint
VALID_TOKEN_MINT_DEF = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"  # USDT mint
VALID_TOKEN_MINT_XYZ = "So11111111111111111111111111111111111111112"  # SOL wrapped


@pytest.fixture
def swap_transaction_factory():
    """Factory to create valid SwapTransaction instances for tests.

    Returns:
        Function that creates SwapTransaction with valid defaults.
    """
    def create(
        signature: str = "sig1",
        timestamp: int = 1000,
        tx_type: TransactionType = TransactionType.BUY,
        token_mint: str = VALID_TOKEN_MINT_ABC,
        sol_amount: float = 1.0,
        token_amount: float = 100.0,
        wallet_address: str = VALID_WALLET_ADDRESS,
    ) -> SwapTransaction:
        return SwapTransaction(
            signature=signature,
            timestamp=timestamp,
            tx_type=tx_type,
            token_mint=token_mint,
            sol_amount=sol_amount,
            token_amount=token_amount,
            wallet_address=wallet_address,
        )

    return create
