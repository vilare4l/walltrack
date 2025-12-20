"""Helius webhook data models."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from walltrack.constants.webhook import (
    MAX_SOLANA_ADDRESS_LENGTH,
    MIN_SOLANA_ADDRESS_LENGTH,
)


class TransactionType(str, Enum):
    """Type of transaction detected."""

    SWAP = "SWAP"
    TRANSFER = "TRANSFER"
    NFT_SALE = "NFT_SALE"
    NFT_LISTING = "NFT_LISTING"
    NFT_BID = "NFT_BID"
    UNKNOWN = "UNKNOWN"


class SwapDirection(str, Enum):
    """Direction of swap transaction."""

    BUY = "buy"
    SELL = "sell"


class TokenTransfer(BaseModel):
    """Parsed token transfer from Helius payload."""

    from_account: str = Field(..., alias="fromUserAccount")
    to_account: str = Field(..., alias="toUserAccount")
    mint: str
    amount: float = Field(..., alias="tokenAmount")

    model_config = {"populate_by_name": True}


class NativeTransfer(BaseModel):
    """Native SOL transfer from Helius payload."""

    from_account: str = Field(..., alias="fromUserAccount")
    to_account: str = Field(..., alias="toUserAccount")
    amount: int  # In lamports

    model_config = {"populate_by_name": True}


class AccountData(BaseModel):
    """Account data from Helius payload."""

    account: str
    native_balance_change: int = Field(default=0, alias="nativeBalanceChange")
    token_balance_changes: list[dict] = Field(
        default_factory=list, alias="tokenBalanceChanges"
    )

    model_config = {"populate_by_name": True}


class HeliusWebhookPayload(BaseModel):
    """Raw Helius webhook payload structure."""

    webhook_id: str = Field(default="", alias="webhookID")
    transaction_type: str = Field(..., alias="type")
    timestamp: int
    signature: str
    fee: int
    fee_payer: str = Field(..., alias="feePayer")
    slot: int
    native_transfers: list[dict] = Field(default_factory=list, alias="nativeTransfers")
    token_transfers: list[dict] = Field(default_factory=list, alias="tokenTransfers")
    account_data: list[dict] = Field(default_factory=list, alias="accountData")
    source: str = Field(default="")
    description: str = Field(default="")

    model_config = {"populate_by_name": True}


class ParsedSwapEvent(BaseModel):
    """Parsed and validated swap event."""

    tx_signature: str
    wallet_address: str
    token_address: str
    direction: SwapDirection
    amount_token: float = Field(..., ge=0)
    amount_sol: float = Field(..., ge=0)
    timestamp: datetime
    slot: int
    fee_lamports: int = Field(..., ge=0)
    raw_payload: dict = Field(default_factory=dict)
    processing_started_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    @field_validator("wallet_address", "token_address")
    @classmethod
    def validate_solana_address(cls, v: str) -> str:
        """Validate Solana base58 address format."""
        if not v or len(v) < MIN_SOLANA_ADDRESS_LENGTH or len(v) > MAX_SOLANA_ADDRESS_LENGTH:
            raise ValueError(f"Invalid Solana address: {v}")
        return v


class WebhookValidationResult(BaseModel):
    """Result of webhook signature validation."""

    is_valid: bool
    error_message: str | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WebhookHealthStatus(BaseModel):
    """Health status for webhook endpoint."""

    status: str = "healthy"
    helius_connected: bool = True
    last_webhook_received: datetime | None = None
    webhooks_processed_24h: int = 0
    average_processing_ms: float = 0.0


class WebhookStats(BaseModel):
    """Statistics for webhook processing."""

    count: int = 0
    last_received: datetime | None = None
    avg_processing_ms: float = 0.0
