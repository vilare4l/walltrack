"""Wallet address validation logic.

This module provides functions to validate Solana wallet addresses:
- Format validation (base58, length)
- On-chain existence validation via RPC
"""

import structlog

from walltrack.core.exceptions import WalletConnectionError
from walltrack.data.models.wallet import WalletValidationResult
from walltrack.services.solana.rpc_client import SolanaRPCClient

log = structlog.get_logger(__name__)

# Solana base58 alphabet (excludes 0, O, I, l to avoid confusion)
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# Solana addresses are typically 32-44 characters
SOLANA_ADDRESS_MIN_LENGTH = 32
SOLANA_ADDRESS_MAX_LENGTH = 44


def is_valid_solana_address(address: str | None) -> bool:
    """Validate Solana address format (base58).

    Performs local validation without network calls:
    - Checks for None/empty values
    - Validates length (32-44 characters)
    - Verifies all characters are in base58 alphabet

    Args:
        address: Potential Solana wallet address to validate.

    Returns:
        True if address has valid format, False otherwise.

    Example:
        >>> is_valid_solana_address("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")
        True
        >>> is_valid_solana_address("invalid_0OIl")
        False
    """
    if address is None or not isinstance(address, str):
        return False

    # Strip whitespace and check if empty
    address = address.strip()
    if not address:
        return False

    # Check length (32-44 characters for Solana addresses)
    if not (SOLANA_ADDRESS_MIN_LENGTH <= len(address) <= SOLANA_ADDRESS_MAX_LENGTH):
        return False

    # Check all characters are in base58 alphabet
    return all(c in BASE58_ALPHABET for c in address)


async def validate_wallet_on_chain(address: str) -> WalletValidationResult:
    """Validate wallet address format and existence on-chain.

    Performs two-step validation:
    1. Format validation (base58, length) - fast, local
    2. On-chain validation via RPC - requires network

    Args:
        address: Solana wallet address to validate.

    Returns:
        WalletValidationResult with validation details.

    Example:
        result = await validate_wallet_on_chain("9WzDXwBbmkg8...")
        if result.is_valid:
            print(f"Wallet valid and exists: {result.exists_on_chain}")
        else:
            print(f"Error: {result.error_message}")
    """
    truncated = address[:8] + "..." if len(address) > 8 else address
    log.info("wallet_validation_started", wallet_address=truncated)

    # Step 1: Format validation (no network call)
    if not is_valid_solana_address(address):
        log.warning("wallet_format_invalid", wallet_address=truncated)
        return WalletValidationResult(
            is_valid=False,
            address=address,
            error_message="Invalid Solana address format",
        )

    # Step 2: On-chain validation
    client = SolanaRPCClient()
    try:
        exists = await client.validate_wallet_exists(address)

        if not exists:
            log.info("wallet_not_found_on_chain", wallet_address=address[:8] + "...")
            return WalletValidationResult(
                is_valid=False,
                address=address,
                error_message="Wallet not found on Solana network",
            )

        log.info("wallet_validation_success", wallet_address=address[:8] + "...")
        return WalletValidationResult(
            is_valid=True,
            address=address,
            exists_on_chain=True,
        )

    except WalletConnectionError as e:
        log.warning("wallet_validation_rpc_error", error=str(e))
        return WalletValidationResult(
            is_valid=False,
            address=address,
            error_message=str(e),
        )
    finally:
        await client.close()
