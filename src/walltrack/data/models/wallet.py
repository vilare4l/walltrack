"""Wallet-related Pydantic models.

This module defines data models for wallet validation and operations.
All models use Pydantic BaseModel (not dataclass) per architecture rules.
"""

from pydantic import BaseModel, Field


class WalletValidationResult(BaseModel):
    """Result of wallet address validation.

    Attributes:
        is_valid: Whether the wallet address is valid.
        address: The validated wallet address.
        exists_on_chain: Whether the wallet exists on Solana network.
        error_message: Error description if validation failed.

    Example:
        result = WalletValidationResult(
            is_valid=True,
            address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            exists_on_chain=True,
        )
    """

    is_valid: bool = Field(description="Whether the wallet address is valid")
    address: str = Field(description="The validated wallet address")
    exists_on_chain: bool = Field(
        default=False, description="Whether the wallet exists on Solana network"
    )
    error_message: str | None = Field(
        default=None, description="Error description if validation failed"
    )
