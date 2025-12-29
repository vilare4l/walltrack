"""Token discovery service for orchestrating token discovery.

This module provides the TokenDiscoveryService which orchestrates:
1. Fetching tokens from DexScreener (boosted + profiles)
2. Enriching tokens with pair data (price, volume, liquidity)
3. Storing tokens in Supabase via TokenRepository

Architecture:
    Config Page UI
        │
        ▼
    TokenDiscoveryService (this module)
        │
        ├──► DexScreenerClient (services/dexscreener/)
        │
        └──► TokenRepository (data/supabase/repositories/)
"""

from datetime import datetime, timezone

import structlog

from walltrack.data.models.token import Token, TokenDiscoveryResult
from walltrack.data.supabase.client import SupabaseClient
from walltrack.data.supabase.repositories.token_repo import TokenRepository
from walltrack.services.dexscreener.client import DexScreenerClient

log = structlog.get_logger(__name__)


class TokenDiscoveryService:
    """Orchestrates token discovery from DexScreener.

    Combines boosted tokens and token profiles from DexScreener,
    enriches with market data, and stores in database.

    Attributes:
        _repo: TokenRepository for database operations.
        _dex_client: DexScreenerClient for API calls.

    Example:
        supabase = await get_supabase_client()
        dex_client = DexScreenerClient()
        try:
            service = TokenDiscoveryService(supabase, dex_client)
            result = await service.run_discovery()
            print(f"Found {result.tokens_found} tokens")
        finally:
            await dex_client.close()
    """

    def __init__(
        self, supabase_client: SupabaseClient, dex_client: DexScreenerClient
    ) -> None:
        """Initialize discovery service.

        Args:
            supabase_client: Connected SupabaseClient instance.
            dex_client: DexScreenerClient instance.
        """
        self._repo = TokenRepository(supabase_client)
        self._dex_client = dex_client

    async def run_discovery(self) -> TokenDiscoveryResult:
        """Execute token discovery workflow.

        Workflow:
            1. Fetch boosted tokens from DexScreener
            2. Fetch token profiles from DexScreener
            3. Combine and deduplicate by mint address
            4. Enrich with pair data (price, volume, market cap)
            5. Store/update tokens in database

        Returns:
            TokenDiscoveryResult with counts and status.

        Note:
            Does not raise on API errors - returns result with error status.
            This allows graceful UI handling of partial failures.
        """
        log.info("token_discovery_started")
        start_time = datetime.now(timezone.utc)

        try:
            # Step 1 & 2: Fetch from both endpoints
            boosted = await self._dex_client.fetch_boosted_tokens()
            profiles = await self._dex_client.fetch_token_profiles()

            log.info(
                "discovery_fetched_raw",
                boosted_count=len(boosted),
                profiles_count=len(profiles),
            )

            # Step 3: Combine and deduplicate
            all_addresses: set[str] = set()
            for token in boosted:
                all_addresses.add(token.token_address)
            for profile in profiles:
                all_addresses.add(profile.token_address)

            if not all_addresses:
                log.info("discovery_no_tokens_found")
                return TokenDiscoveryResult(
                    tokens_found=0,
                    new_tokens=0,
                    updated_tokens=0,
                    status="no_results",
                )

            log.info("discovery_unique_addresses", count=len(all_addresses))

            # Step 4: Enrich with pair data
            tokens = await self._enrich_tokens(list(all_addresses))

            if not tokens:
                log.info("discovery_no_valid_tokens")
                return TokenDiscoveryResult(
                    tokens_found=0,
                    new_tokens=0,
                    updated_tokens=0,
                    status="no_results",
                )

            # Step 5: Store in database
            new_count, updated_count = await self._repo.upsert_tokens(tokens)

            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            log.info(
                "token_discovery_completed",
                tokens_found=len(tokens),
                new_tokens=new_count,
                updated_tokens=updated_count,
                elapsed_seconds=elapsed,
            )

            return TokenDiscoveryResult(
                tokens_found=len(tokens),
                new_tokens=new_count,
                updated_tokens=updated_count,
                status="complete",
            )

        except Exception as e:
            log.error("token_discovery_failed", error=str(e))
            return TokenDiscoveryResult(
                tokens_found=0,
                new_tokens=0,
                updated_tokens=0,
                status="error",
                error_message=str(e),
            )

    async def _enrich_tokens(self, addresses: list[str]) -> list[Token]:
        """Enrich token addresses with market data.

        Fetches pair data for each address to get price, volume,
        market cap, and liquidity. Skips tokens with no valid pairs.

        Args:
            addresses: List of token mint addresses.

        Returns:
            List of Token models with market data.
        """
        tokens: list[Token] = []

        for address in addresses:
            try:
                pairs = await self._dex_client.fetch_token_by_address(address)

                if not pairs:
                    # Token exists but no trading pairs found
                    tokens.append(Token(mint=address))
                    continue

                # Use first (most liquid) pair for market data
                pair = pairs[0]

                # Calculate age in minutes if creation time available
                age_minutes = None
                if pair.pair_created_at:
                    created_dt = datetime.fromtimestamp(
                        pair.pair_created_at / 1000, tz=timezone.utc
                    )
                    age_minutes = int(
                        (datetime.now(timezone.utc) - created_dt).total_seconds() / 60
                    )

                token = Token(
                    mint=address,
                    symbol=pair.base_token.symbol,
                    name=pair.base_token.name,
                    price_usd=float(pair.price_usd) if pair.price_usd else None,
                    market_cap=pair.market_cap,
                    volume_24h=pair.volume.h24 if pair.volume else None,
                    liquidity_usd=pair.liquidity.usd if pair.liquidity else None,
                    age_minutes=age_minutes,
                )
                tokens.append(token)

            except Exception as e:
                log.warning(
                    "token_enrichment_failed",
                    address=address,
                    error=str(e),
                )
                # Still add token with just the address
                tokens.append(Token(mint=address))

        log.debug("tokens_enriched", count=len(tokens))
        return tokens
