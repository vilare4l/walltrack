"""Token characteristics domain models."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class TokenSource(str, Enum):
    """Source of token data."""

    DEXSCREENER = "dexscreener"
    BIRDEYE = "birdeye"
    CACHE = "cache"
    FALLBACK_NEUTRAL = "fallback_neutral"


class TokenLiquidity(BaseModel):
    """Token liquidity information."""

    usd: float = Field(default=0.0, ge=0)
    base: float = Field(default=0.0, ge=0)  # Base token amount
    quote: float = Field(default=0.0, ge=0)  # Quote token (usually SOL)


class TokenPriceChange(BaseModel):
    """Price change percentages."""

    m5: float | None = None  # 5 minutes
    h1: float | None = None  # 1 hour
    h6: float | None = None  # 6 hours
    h24: float | None = None  # 24 hours


class TokenVolume(BaseModel):
    """Trading volume information."""

    m5: float = 0.0
    h1: float = 0.0
    h6: float = 0.0
    h24: float = 0.0


class TokenTransactions(BaseModel):
    """Transaction counts."""

    buys: int = 0
    sells: int = 0
    total: int = 0

    @property
    def buy_sell_ratio(self) -> float:
        """Calculate buy/sell ratio."""
        if self.sells == 0:
            return float("inf") if self.buys > 0 else 1.0
        return self.buys / self.sells


class TokenCharacteristics(BaseModel):
    """Complete token characteristics for scoring."""

    # Identity
    token_address: str
    name: str | None = None
    symbol: str | None = None

    # Core metrics
    price_usd: float = Field(default=0.0, ge=0)
    price_sol: float = Field(default=0.0, ge=0)
    market_cap_usd: float | None = None
    fdv_usd: float | None = None  # Fully diluted valuation

    # Liquidity
    liquidity: TokenLiquidity = Field(default_factory=TokenLiquidity)

    # Trading activity
    volume: TokenVolume = Field(default_factory=TokenVolume)
    price_change: TokenPriceChange = Field(default_factory=TokenPriceChange)
    transactions_24h: TokenTransactions = Field(default_factory=TokenTransactions)

    # Token age and metadata
    created_at: datetime | None = None
    age_minutes: int = Field(default=0, ge=0)
    is_new_token: bool = False  # < 10 minutes old

    # Holder info (if available)
    holder_count: int | None = None
    top_10_holder_percentage: float | None = None

    # Risk indicators
    is_honeypot: bool | None = None
    has_freeze_authority: bool | None = None
    has_mint_authority: bool | None = None

    # Metadata
    source: TokenSource = TokenSource.DEXSCREENER
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    cache_ttl_seconds: int = 300

    @field_validator("token_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Validate token address format."""
        if not v or len(v) < 32 or len(v) > 44:
            raise ValueError(f"Invalid token address length: {len(v) if v else 0}")
        return v

    def is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        elapsed = (datetime.now(UTC) - self.fetched_at).total_seconds()
        return elapsed < self.cache_ttl_seconds


class TokenFetchResult(BaseModel):
    """Result of token fetch operation."""

    success: bool
    token: TokenCharacteristics | None = None
    source: TokenSource
    fetch_time_ms: float = 0.0
    error_message: str | None = None
    used_fallback: bool = False
