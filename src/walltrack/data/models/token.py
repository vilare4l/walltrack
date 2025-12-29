"""Token-related Pydantic models.

This module defines data models for token storage and discovery operations.
All models use Pydantic BaseModel (not dataclass) per architecture rules.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Token(BaseModel):
    """Token model for database storage.

    Represents a discovered token from DexScreener or other sources.
    Maps directly to the walltrack.tokens table schema.

    Attributes:
        id: Unique identifier for the token record (auto-generated).
        mint: Solana token mint address (unique).
        symbol: Token symbol (e.g., SOL, USDC).
        name: Token name (e.g., Solana, USD Coin).
        price_usd: Current price in USD.
        market_cap: Market capitalization in USD.
        volume_24h: 24-hour trading volume in USD.
        liquidity_usd: Total liquidity in USD.
        age_minutes: Token age in minutes since creation.
        created_at: When this record was first created.
        updated_at: Last modification timestamp.
        last_checked: Last time token data was refreshed from API.

    Example:
        token = Token(
            mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            symbol="USDC",
            name="USD Coin",
            price_usd=1.00,
            market_cap=25000000000.0,
        )
    """

    id: UUID | None = Field(default=None, description="Unique identifier (auto-generated)")
    mint: str = Field(description="Solana token mint address")
    symbol: str | None = Field(default=None, description="Token symbol")
    name: str | None = Field(default=None, description="Token name")
    price_usd: float | None = Field(default=None, description="Current price in USD")
    market_cap: float | None = Field(default=None, description="Market capitalization in USD")
    volume_24h: float | None = Field(default=None, description="24-hour trading volume in USD")
    liquidity_usd: float | None = Field(default=None, description="Total liquidity in USD")
    age_minutes: int | None = Field(default=None, description="Token age in minutes")
    created_at: datetime | None = Field(default=None, description="Record creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last modification timestamp")
    last_checked: datetime | None = Field(default=None, description="Last API refresh timestamp")


class TokenDiscoveryResult(BaseModel):
    """Result of a token discovery run.

    Returned by TokenDiscoveryService.run_discovery() to summarize
    the discovery operation outcome.

    Attributes:
        tokens_found: Total number of tokens fetched from API.
        new_tokens: Number of newly inserted tokens.
        updated_tokens: Number of existing tokens that were updated.
        status: Operation status (complete, error, no_results).
        error_message: Error description if status is error.

    Example:
        result = TokenDiscoveryResult(
            tokens_found=50,
            new_tokens=12,
            updated_tokens=38,
            status="complete",
        )
    """

    tokens_found: int = Field(default=0, description="Total tokens fetched from API")
    new_tokens: int = Field(default=0, description="Newly inserted tokens")
    updated_tokens: int = Field(default=0, description="Existing tokens updated")
    status: str = Field(default="complete", description="Operation status")
    error_message: str | None = Field(default=None, description="Error description if failed")
