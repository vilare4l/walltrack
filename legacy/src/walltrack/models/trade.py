"""Trade execution data models.

Models for:
- Swap quotes from Jupiter/Raydium
- Trade requests and results
- Execution status tracking
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

import base58
from pydantic import BaseModel, Field, field_validator


class SwapDirection(str, Enum):
    """Direction of swap."""

    BUY = "buy"  # SOL -> Token
    SELL = "sell"  # Token -> SOL


class TradeStatus(str, Enum):
    """Status of trade execution."""

    PENDING = "pending"
    QUOTING = "quoting"
    SIGNING = "signing"
    SUBMITTED = "submitted"
    CONFIRMING = "confirming"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


class FailureReason(str, Enum):
    """Reasons for trade failure."""

    QUOTE_FAILED = "quote_failed"
    SLIPPAGE_EXCEEDED = "slippage_exceeded"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    TRANSACTION_EXPIRED = "transaction_expired"
    NETWORK_ERROR = "network_error"
    RPC_ERROR = "rpc_error"
    UNKNOWN = "unknown"


class SwapQuote(BaseModel):
    """Quote from Jupiter/Raydium for swap."""

    input_mint: str = Field(..., description="Input token mint")
    output_mint: str = Field(..., description="Output token mint")
    input_amount: int = Field(..., ge=0, description="Input amount in smallest unit")
    output_amount: int = Field(..., ge=0, description="Expected output amount")
    output_amount_min: int = Field(..., ge=0, description="Minimum output with slippage")
    slippage_bps: int = Field(..., ge=0, le=5000, description="Slippage in basis points")
    price_impact_pct: float = Field(..., description="Price impact percentage")
    route_plan: list[dict] = Field(default_factory=list, description="Swap route")
    quote_source: str = Field(default="jupiter", description="jupiter or raydium")
    quoted_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = Field(None)

    @property
    def effective_price(self) -> float:
        """Calculate effective price (output/input)."""
        if self.input_amount == 0:
            return 0.0
        return self.output_amount / self.input_amount

    @field_validator("input_mint", "output_mint")
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


class SwapTransaction(BaseModel):
    """Prepared swap transaction ready for signing."""

    quote: SwapQuote
    serialized_transaction: str = Field(..., description="Base64 serialized transaction")
    recent_blockhash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


class SwapResult(BaseModel):
    """Result of swap execution."""

    success: bool
    status: TradeStatus
    tx_signature: str | None = Field(None)
    input_amount: int = Field(..., ge=0)
    output_amount: int | None = Field(None, ge=0)
    entry_price: float | None = Field(None, description="Effective entry price")
    execution_time_ms: float = Field(..., ge=0)
    quote_source: str = Field(default="jupiter")
    failure_reason: FailureReason | None = Field(None)
    error_message: str | None = Field(None)
    slot: int | None = Field(None)
    confirmed_at: datetime | None = Field(None)

    @property
    def was_successful(self) -> bool:
        """Check if trade was successful."""
        return self.success and self.tx_signature is not None


class TradeRequest(BaseModel):
    """Request to execute a trade."""

    signal_id: str = Field(..., description="Source signal ID")
    token_address: str = Field(..., description="Token to trade")
    direction: SwapDirection
    amount_sol: float = Field(..., gt=0, description="SOL amount for buy")
    slippage_bps: int = Field(default=100, ge=10, le=5000, description="Slippage tolerance")
    priority_fee_lamports: int = Field(default=10000, ge=0, description="Priority fee")
    max_retries: int = Field(default=2, ge=0, le=5)

    @field_validator("token_address")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate token address is valid base58."""
        try:
            decoded = base58.b58decode(v)
            if len(decoded) != 32:
                raise ValueError("Invalid token address length")
        except Exception as e:
            raise ValueError(f"Invalid base58 token address: {e}") from e
        return v
