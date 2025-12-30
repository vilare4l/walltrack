"""Pydantic models for Solana RPC responses.

This module provides type-safe models for Solana JSON-RPC responses,
specifically for token account data from getProgramAccounts calls.

Models:
    TokenAccount: Individual token account data
    TokenAccountList: Wrapper for multiple token accounts
"""

from pydantic import BaseModel, Field, field_validator


class TokenAccount(BaseModel):
    """Token account data model for Solana SPL tokens.

    Represents a single token account returned by getProgramAccounts RPC.
    Token accounts are owned by wallets and hold balances of specific tokens.

    Attributes:
        pubkey: Token account's public key (base58 format).
        owner: Wallet address that owns this token account (base58 format).
        mint: Token mint address this account is for (base58 format).
        amount: Token balance as string (raw amount, not decimals-adjusted).

    Example:
        {
            "pubkey": "TokenAcc123...",
            "owner": "Wallet456...",
            "mint": "TokenMint789...",
            "amount": "1000000"  # 1 USDC (6 decimals)
        }
    """

    pubkey: str = Field(..., description="Token account public key")
    owner: str = Field(..., description="Wallet address owning this token account")
    mint: str = Field(..., description="Token mint address")
    amount: str = Field(..., description="Token balance (raw amount)")

    @field_validator("pubkey", "owner", "mint")
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana address format (base58, 32-44 characters).

        Args:
            v: Address string to validate.

        Returns:
            The validated address string.

        Raises:
            ValueError: If address format is invalid.
        """
        if not v:
            raise ValueError("Address cannot be empty")

        if not (32 <= len(v) <= 44):
            raise ValueError(
                f"Invalid Solana address length: {len(v)} "
                "(expected 32-44 characters)"
            )

        # Base58 alphabet (no 0, O, I, l)
        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not set(v).issubset(base58_chars):
            raise ValueError(
                "Invalid Solana address: contains non-base58 characters"
            )

        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        """Validate amount is a numeric string.

        Args:
            v: Amount string to validate.

        Returns:
            The validated amount string.

        Raises:
            ValueError: If amount is not a valid number.
        """
        try:
            int(v)
        except ValueError as e:
            raise ValueError(f"Amount must be a numeric string: {v}") from e
        return v


class TokenAccountList(BaseModel):
    """Wrapper for multiple token accounts from RPC response.

    Used to parse and validate getProgramAccounts responses that return
    arrays of token accounts.

    Attributes:
        accounts: List of TokenAccount objects.
        count: Number of accounts returned (convenience field).

    Example:
        {
            "accounts": [
                {"pubkey": "...", "owner": "...", "mint": "...", "amount": "..."},
                {"pubkey": "...", "owner": "...", "mint": "...", "amount": "..."}
            ],
            "count": 2
        }
    """

    accounts: list[TokenAccount] = Field(
        default_factory=list, description="List of token accounts"
    )

    @property
    def count(self) -> int:
        """Get number of token accounts in list."""
        return len(self.accounts)

    @property
    def owner_addresses(self) -> list[str]:
        """Extract list of unique wallet owner addresses.

        Returns:
            List of unique wallet addresses (owners) with non-zero balances.
        """
        return list({acc.owner for acc in self.accounts if int(acc.amount) > 0})
