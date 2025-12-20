"""Trading wallet data models for trade execution.

This module contains models for:
- Wallet connection status tracking
- Balance information (SOL + tokens)
- Safe mode state management
- Transaction signing results

SECURITY: Private keys are NEVER stored in these models.
Use SecretStr from pydantic for any sensitive data.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

import base58
from pydantic import BaseModel, Field, field_validator


class WalletConnectionStatus(str, Enum):
    """Status of wallet connection."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    VALIDATING = "validating"


class SafeModeReason(str, Enum):
    """Reasons for entering safe mode."""

    CONNECTION_FAILED = "connection_failed"
    SIGNING_FAILED = "signing_failed"
    RPC_UNAVAILABLE = "rpc_unavailable"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    MANUAL = "manual"


class TokenBalance(BaseModel):
    """Balance of a specific SPL token."""

    mint_address: str = Field(..., description="Token mint address")
    symbol: str | None = Field(None, description="Token symbol if known")
    amount: float = Field(..., ge=0, description="Token amount in raw units")
    decimals: int = Field(..., ge=0, le=18)
    ui_amount: float = Field(..., ge=0, description="Human-readable amount")
    estimated_value_sol: float | None = Field(None, ge=0)

    @field_validator("mint_address")
    @classmethod
    def validate_mint(cls, v: str) -> str:
        """Validate mint address is valid base58."""
        try:
            decoded = base58.b58decode(v)
            if len(decoded) != 32:
                raise ValueError("Invalid mint address length")
        except Exception as e:
            raise ValueError(f"Invalid base58 mint address: {e}") from e
        return v


class WalletBalance(BaseModel):
    """Complete wallet balance information."""

    sol_balance: float = Field(..., ge=0, description="SOL balance in lamports")
    sol_balance_ui: float = Field(..., ge=0, description="SOL balance for display")
    token_balances: list[TokenBalance] = Field(default_factory=list)
    total_value_sol: float = Field(..., ge=0, description="Total portfolio value in SOL")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_sufficient_sol(self) -> bool:
        """Check if wallet has minimum SOL for transactions."""
        MIN_SOL_REQUIRED = 0.01  # ~10k lamports for fees
        return self.sol_balance_ui >= MIN_SOL_REQUIRED


class WalletState(BaseModel):
    """Current state of the trading wallet."""

    public_key: str = Field(..., description="Wallet public key (base58)")
    status: WalletConnectionStatus = Field(default=WalletConnectionStatus.DISCONNECTED)
    balance: WalletBalance | None = Field(None)
    safe_mode: bool = Field(default=False)
    safe_mode_reason: SafeModeReason | None = Field(None)
    safe_mode_since: datetime | None = Field(None)
    last_validated: datetime | None = Field(None)
    error_message: str | None = Field(None)

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, v: str) -> str:
        """Validate public key is valid base58."""
        try:
            decoded = base58.b58decode(v)
            if len(decoded) != 32:
                raise ValueError("Invalid public key length")
        except Exception as e:
            raise ValueError(f"Invalid base58 public key: {e}") from e
        return v


class SigningResult(BaseModel):
    """Result of a transaction signing test."""

    success: bool
    message_hash: str | None = Field(None)
    signature: str | None = Field(None)
    error: str | None = Field(None)
    latency_ms: float = Field(..., ge=0)
