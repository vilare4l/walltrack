"""Transaction-related Pydantic models.

This module defines data models for transaction validation and operations.
All models use Pydantic BaseModel per architecture rules.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TransactionType(str, Enum):
    """Transaction type enum for swap operations."""

    BUY = "BUY"
    SELL = "SELL"


class SwapTransaction(BaseModel):
    """Swap transaction model parsed from Helius API.

    Represents a token swap transaction (BUY or SELL) extracted from
    Helius transaction history for performance analysis.

    Attributes:
        signature: Unique transaction signature (hash).
        timestamp: Transaction timestamp (Unix seconds).
        tx_type: Transaction type (BUY or SELL).
        token_mint: SPL token mint address.
        sol_amount: SOL amount in transaction (in SOL, not lamports).
        token_amount: Token amount in transaction.
        wallet_address: Wallet address that executed the transaction.

    Example:
        tx = SwapTransaction(
            signature="5j7s8k2d...",
            timestamp=1703001234,
            tx_type=TransactionType.BUY,
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            sol_amount=1.5,
            token_amount=1000000,
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        )
    """

    signature: str = Field(description="Unique transaction signature (hash)")
    timestamp: int = Field(description="Transaction timestamp (Unix seconds)")
    tx_type: TransactionType = Field(description="Transaction type (BUY or SELL)")
    token_mint: str = Field(description="SPL token mint address")
    sol_amount: float = Field(description="SOL amount in transaction (in SOL)")
    token_amount: float = Field(description="Token amount in transaction")
    wallet_address: str = Field(description="Wallet address that executed the transaction")

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, v: str) -> str:
        """Validate transaction signature is not empty.

        Args:
            v: Signature string to validate.

        Returns:
            Validated signature string.

        Raises:
            ValueError: If signature is empty.
        """
        if not v or not v.strip():
            msg = "Transaction signature cannot be empty"
            raise ValueError(msg)
        return v.strip()

    @field_validator("token_mint", "wallet_address")
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana address format (base58, 32-44 characters).

        Args:
            v: Address string to validate.

        Returns:
            Validated address string.

        Raises:
            ValueError: If address format is invalid.
        """
        if not (32 <= len(v) <= 44):
            msg = f"Invalid Solana address length: {len(v)}"
            raise ValueError(msg)

        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not set(v).issubset(base58_chars):
            msg = "Invalid Solana address: contains non-base58 characters"
            raise ValueError(msg)

        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: int) -> int:
        """Validate timestamp is positive.

        Args:
            v: Timestamp to validate.

        Returns:
            Validated timestamp.

        Raises:
            ValueError: If timestamp is negative.
        """
        if v < 0:
            msg = f"Timestamp must be positive, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("sol_amount", "token_amount")
    @classmethod
    def validate_amounts(cls, v: float) -> float:
        """Validate amounts are non-negative.

        Args:
            v: Amount to validate.

        Returns:
            Validated amount.

        Raises:
            ValueError: If amount is negative.
        """
        if v < 0:
            msg = f"Amount must be non-negative, got {v}"
            raise ValueError(msg)
        return v

    def to_datetime(self) -> datetime:
        """Convert Unix timestamp to datetime object.

        Returns:
            datetime object from timestamp.
        """
        return datetime.fromtimestamp(self.timestamp)


class Trade(BaseModel):
    """Matched BUY/SELL pair representing a completed trade.

    Used for performance analysis to calculate PnL and win rate.

    Attributes:
        token_mint: SPL token mint address.
        entry_time: Entry timestamp (Unix seconds).
        exit_time: Exit timestamp (Unix seconds).
        pnl: Profit/loss in SOL (sell_sol - buy_sol).
        profitable: True if pnl > 0, False otherwise.

    Example:
        trade = Trade(
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            entry_time=1703001234,
            exit_time=1703005678,
            pnl=0.5,
            profitable=True,
        )
    """

    token_mint: str = Field(description="SPL token mint address")
    entry_time: int = Field(description="Entry timestamp (Unix seconds)")
    exit_time: int = Field(description="Exit timestamp (Unix seconds)")
    pnl: float = Field(description="Profit/loss in SOL")
    profitable: bool = Field(description="True if profitable, False otherwise")

    @field_validator("token_mint")
    @classmethod
    def validate_token_mint(cls, v: str) -> str:
        """Validate token mint address format.

        Args:
            v: Token mint address to validate.

        Returns:
            Validated token mint address.

        Raises:
            ValueError: If address format is invalid.
        """
        if not (32 <= len(v) <= 44):
            msg = f"Invalid token mint length: {len(v)}"
            raise ValueError(msg)

        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not set(v).issubset(base58_chars):
            msg = "Invalid token mint: contains non-base58 characters"
            raise ValueError(msg)

        return v

    @field_validator("entry_time", "exit_time")
    @classmethod
    def validate_timestamps(cls, v: int) -> int:
        """Validate timestamps are positive.

        Args:
            v: Timestamp to validate.

        Returns:
            Validated timestamp.

        Raises:
            ValueError: If timestamp is negative.
        """
        if v < 0:
            msg = f"Timestamp must be positive, got {v}"
            raise ValueError(msg)
        return v
