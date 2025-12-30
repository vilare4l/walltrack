"""Pydantic models for Helius API responses.

This module defines type-safe models for parsing Helius Enhanced Transactions API responses,
focusing on swap transactions for token discovery and early profitable buyer analysis.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator


class NativeTransfer(BaseModel):
    """Represents a SOL transfer in a transaction.

    Used to identify BUY (SOL out) vs SELL (SOL in) transactions.
    """

    from_user_account: str = Field(..., alias="fromUserAccount")
    to_user_account: str = Field(..., alias="toUserAccount")
    amount: int  # SOL amount in lamports (1 SOL = 1_000_000_000 lamports)

    class Config:
        populate_by_name = True


class TokenTransfer(BaseModel):
    """Represents a token transfer in a transaction.

    Used to track token amounts in BUY/SELL transactions.
    """

    from_user_account: str = Field(..., alias="fromUserAccount")
    to_user_account: str = Field(..., alias="toUserAccount")
    mint: str  # Token mint address
    token_amount: float = Field(..., alias="tokenAmount")

    class Config:
        populate_by_name = True


class Transaction(BaseModel):
    """Helius Enhanced Transaction model.

    Represents a single transaction from Helius API with enriched data
    for swap detection and wallet profiling.

    Attributes:
        signature: Transaction signature (unique ID).
        timestamp: Unix timestamp (seconds since epoch).
        type: Transaction type (SWAP, TRANSFER, etc.).
        source: DEX source (RAYDIUM, ORCA, JUPITER, etc.).
        native_transfers: List of SOL transfers (BUY/SELL detection).
        token_transfers: List of token transfers (amount tracking).
    """

    signature: str
    timestamp: int  # Unix timestamp (seconds)
    type: str = Field(default="UNKNOWN")  # SWAP, TRANSFER, etc.
    source: str | None = None  # RAYDIUM, ORCA, JUPITER, etc.
    native_transfers: list[NativeTransfer] = Field(default_factory=list, alias="nativeTransfers")
    token_transfers: list[TokenTransfer] = Field(default_factory=list, alias="tokenTransfers")

    class Config:
        populate_by_name = True

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, v: int) -> int:
        """Validate timestamp is a positive integer."""
        if v < 0:
            msg = f"Timestamp must be positive, got {v}"
            raise ValueError(msg)
        return v

    @property
    def datetime_utc(self) -> datetime:
        """Get transaction datetime in UTC."""
        return datetime.fromtimestamp(self.timestamp, tz=UTC)

    @property
    def is_swap(self) -> bool:
        """Check if transaction is a SWAP type."""
        return self.type == "SWAP"


class SwapDetails(BaseModel):
    """Parsed swap transaction details for early profitable buyer analysis.

    This model extracts BUY/SELL information from a Transaction,
    identifying the wallet, direction, SOL amount, and token amount.

    Attributes:
        wallet_address: The wallet performing the swap.
        direction: BUY or SELL.
        timestamp: Unix timestamp of the swap.
        sol_amount: SOL amount in lamports.
        token_amount: Token amount.
        token_mint: Token mint address.
    """

    wallet_address: str
    direction: str  # BUY or SELL
    timestamp: int  # Unix timestamp (seconds)
    sol_amount: int  # In lamports
    token_amount: float
    token_mint: str

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        """Validate direction is BUY or SELL."""
        if v not in {"BUY", "SELL"}:
            msg = f"Direction must be BUY or SELL, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("sol_amount")
    @classmethod
    def validate_sol_amount(cls, v: int) -> int:
        """Validate SOL amount is positive."""
        if v < 0:
            msg = f"SOL amount must be positive, got {v}"
            raise ValueError(msg)
        return v

    @property
    def sol_in_full_units(self) -> float:
        """Get SOL amount in full units (not lamports)."""
        return self.sol_amount / 1_000_000_000

    @classmethod
    def from_transaction(
        cls,
        tx: Transaction,
        wallet_address: str,
        token_mint: str,
    ) -> "SwapDetails | None":
        """Parse SwapDetails from a Transaction.

        Detects BUY (SOL out) vs SELL (SOL in) based on nativeTransfers direction.

        Args:
            tx: Transaction to parse.
            wallet_address: Wallet address to track.
            token_mint: Token mint address to track.

        Returns:
            SwapDetails if valid swap found, None otherwise.

        Example:
            swap = SwapDetails.from_transaction(tx, "Wallet1...", "TokenMint...")
            if swap and swap.direction == "BUY":
                print(f"Wallet bought {swap.token_amount} tokens for {swap.sol_in_full_units} SOL")
        """
        if not tx.is_swap:
            return None

        # Find native transfer (SOL movement)
        native_transfer = None
        for transfer in tx.native_transfers:
            if wallet_address in {transfer.from_user_account, transfer.to_user_account}:
                native_transfer = transfer
                break

        if not native_transfer:
            return None

        # Find token transfer (token movement)
        token_transfer = None
        for transfer in tx.token_transfers:
            if transfer.mint == token_mint and wallet_address in {
                transfer.from_user_account,
                transfer.to_user_account,
            }:
                token_transfer = transfer
                break

        if not token_transfer:
            return None

        # Determine direction: BUY (SOL out) vs SELL (SOL in)
        if native_transfer.from_user_account == wallet_address:
            direction = "BUY"  # Wallet sent SOL out (buying tokens)
        else:
            direction = "SELL"  # Wallet received SOL in (selling tokens)

        return cls(
            wallet_address=wallet_address,
            direction=direction,
            timestamp=tx.timestamp,
            sol_amount=native_transfer.amount,
            token_amount=token_transfer.token_amount,
            token_mint=token_mint,
        )
