"""Pydantic models for DexScreener API responses.

This module defines data models for parsing DexScreener API responses.
Models use Pydantic for validation and type coercion.

API Documentation: https://docs.dexscreener.com/api/reference
"""

from pydantic import BaseModel, ConfigDict, Field


class BoostedToken(BaseModel):
    """Token from the boosted/trending endpoint.

    Represents a token that has paid for promotion on DexScreener.

    Attributes:
        chain_id: Blockchain identifier (e.g., "solana", "ethereum").
        token_address: Token contract/mint address.
        icon: URL to token icon image.
        description: Token description text.
    """

    model_config = ConfigDict(populate_by_name=True)

    chain_id: str = Field(alias="chainId")
    token_address: str = Field(alias="tokenAddress")
    icon: str | None = None
    description: str | None = None


class TokenProfile(BaseModel):
    """Token from the profiles endpoint.

    Represents a token with a verified profile on DexScreener.

    Attributes:
        chain_id: Blockchain identifier.
        token_address: Token contract/mint address.
        url: DexScreener URL for the token.
        icon: URL to token icon image.
        description: Token description text.
    """

    model_config = ConfigDict(populate_by_name=True)

    chain_id: str = Field(alias="chainId")
    token_address: str = Field(alias="tokenAddress")
    url: str | None = None
    icon: str | None = None
    description: str | None = None


class BaseTokenInfo(BaseModel):
    """Base token information within a trading pair.

    Attributes:
        address: Token contract/mint address.
        name: Token name.
        symbol: Token ticker symbol.
    """

    address: str
    name: str | None = None
    symbol: str | None = None


class VolumeInfo(BaseModel):
    """Trading volume information.

    Attributes:
        h24: 24-hour trading volume in USD.
        h6: 6-hour trading volume in USD.
        h1: 1-hour trading volume in USD.
        m5: 5-minute trading volume in USD.
    """

    h24: float | None = None
    h6: float | None = None
    h1: float | None = None
    m5: float | None = None


class LiquidityInfo(BaseModel):
    """Liquidity information.

    Attributes:
        usd: Total liquidity in USD.
        base: Liquidity in base token.
        quote: Liquidity in quote token.
    """

    usd: float | None = None
    base: float | None = None
    quote: float | None = None


class TokenPair(BaseModel):
    """Trading pair information from token lookup.

    Represents a DEX trading pair with full market data.

    Attributes:
        chain_id: Blockchain identifier.
        dex_id: DEX identifier (e.g., "raydium", "orca").
        pair_address: Trading pair contract address.
        base_token: Base token information.
        price_usd: Current price in USD.
        volume: Trading volume data.
        liquidity: Liquidity information.
        market_cap: Market capitalization in USD.
        pair_created_at: Pair creation timestamp (Unix milliseconds).
    """

    model_config = ConfigDict(populate_by_name=True)

    chain_id: str = Field(alias="chainId")
    dex_id: str = Field(alias="dexId")
    pair_address: str = Field(alias="pairAddress")
    base_token: BaseTokenInfo = Field(alias="baseToken")
    price_usd: str | None = Field(default=None, alias="priceUsd")
    volume: VolumeInfo | None = None
    liquidity: LiquidityInfo | None = None
    market_cap: float | None = Field(default=None, alias="marketCap")
    pair_created_at: int | None = Field(default=None, alias="pairCreatedAt")


class TokenPairsResponse(BaseModel):
    """Response from token pairs endpoint.

    Attributes:
        pairs: List of trading pairs for the token.
    """

    pairs: list[TokenPair] | None = None
