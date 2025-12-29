"""DexScreener API client for token discovery.

This module provides a client for interacting with the DexScreener API
to discover trending tokens and fetch token market data.

API Documentation: https://docs.dexscreener.com/api/reference
Rate Limits: ~300 requests/minute (no auth required)
"""

import structlog

from walltrack.core.exceptions import ExternalServiceError
from walltrack.services.base import BaseAPIClient
from walltrack.services.dexscreener.models import (
    BoostedToken,
    TokenPair,
    TokenPairsResponse,
    TokenProfile,
)

log = structlog.get_logger(__name__)


class DexScreenerClient(BaseAPIClient):
    """DexScreener API client for token discovery.

    Inherits from BaseAPIClient to provide retry logic and circuit breaker
    protection for API calls.

    Endpoints used:
        - GET /token-boosts/top/v1 - Trending/boosted tokens
        - GET /token-profiles/latest/v1 - Latest token profiles
        - GET /latest/dex/tokens/{address} - Token pair data

    Example:
        client = DexScreenerClient()
        try:
            tokens = await client.fetch_boosted_tokens()
            for token in tokens:
                print(f"Found: {token.token_address}")
        finally:
            await client.close()
    """

    BASE_URL = "https://api.dexscreener.com"
    SOLANA_CHAIN_ID = "solana"
    DEFAULT_TIMEOUT = 30.0
    CIRCUIT_BREAKER_THRESHOLD = 5
    CIRCUIT_BREAKER_COOLDOWN = 30

    def __init__(self) -> None:
        """Initialize DexScreener client with default settings."""
        super().__init__(
            base_url=self.BASE_URL,
            timeout=self.DEFAULT_TIMEOUT,
            circuit_breaker_threshold=self.CIRCUIT_BREAKER_THRESHOLD,
            circuit_breaker_cooldown=self.CIRCUIT_BREAKER_COOLDOWN,
        )
        log.info("dexscreener_client_initialized", base_url=self.BASE_URL)

    async def fetch_boosted_tokens(self) -> list[BoostedToken]:
        """Fetch trending/boosted tokens filtered to Solana.

        Returns:
            List of BoostedToken models for Solana chain only.

        Raises:
            ExternalServiceError: If API request fails after retries.
        """
        log.debug("fetching_boosted_tokens")

        try:
            response = await self.get("/token-boosts/top/v1")
            data = response.json()

            if not isinstance(data, list):
                log.warning("boosted_tokens_unexpected_format", data_type=type(data).__name__)
                return []

            # Filter to Solana and parse
            tokens = []
            for item in data:
                if item.get("chainId") == self.SOLANA_CHAIN_ID:
                    try:
                        tokens.append(BoostedToken.model_validate(item))
                    except Exception as e:
                        log.warning("boosted_token_parse_error", error=str(e), item=item)

            log.info("boosted_tokens_fetched", total=len(data), solana_count=len(tokens))
            return tokens

        except ExternalServiceError:
            raise
        except Exception as e:
            log.error("fetch_boosted_tokens_failed", error=str(e))
            raise ExternalServiceError(
                service="dexscreener",
                message=f"Failed to fetch boosted tokens: {e}",
            ) from e

    async def fetch_token_profiles(self) -> list[TokenProfile]:
        """Fetch latest token profiles filtered to Solana.

        Returns:
            List of TokenProfile models for Solana chain only.

        Raises:
            ExternalServiceError: If API request fails after retries.
        """
        log.debug("fetching_token_profiles")

        try:
            response = await self.get("/token-profiles/latest/v1")
            data = response.json()

            if not isinstance(data, list):
                log.warning("token_profiles_unexpected_format", data_type=type(data).__name__)
                return []

            # Filter to Solana and parse
            tokens = []
            for item in data:
                if item.get("chainId") == self.SOLANA_CHAIN_ID:
                    try:
                        tokens.append(TokenProfile.model_validate(item))
                    except Exception as e:
                        log.warning("token_profile_parse_error", error=str(e), item=item)

            log.info("token_profiles_fetched", total=len(data), solana_count=len(tokens))
            return tokens

        except ExternalServiceError:
            raise
        except Exception as e:
            log.error("fetch_token_profiles_failed", error=str(e))
            raise ExternalServiceError(
                service="dexscreener",
                message=f"Failed to fetch token profiles: {e}",
            ) from e

    async def fetch_token_by_address(self, address: str) -> list[TokenPair] | None:
        """Fetch full pair data for a token address.

        Args:
            address: Solana token mint address.

        Returns:
            List of TokenPair models if found, None on error.
            Returns None (not raises) to allow graceful handling of
            individual token lookup failures during batch discovery.
        """
        log.debug("fetching_token_by_address", address=address)

        try:
            response = await self.get(f"/latest/dex/tokens/{address}")
            data = response.json()

            pairs_response = TokenPairsResponse.model_validate(data)

            if not pairs_response.pairs:
                log.debug("token_no_pairs", address=address)
                return None

            # Filter to Solana pairs
            solana_pairs = [
                pair for pair in pairs_response.pairs
                if pair.chain_id == self.SOLANA_CHAIN_ID
            ]

            log.debug(
                "token_pairs_fetched",
                address=address,
                total=len(pairs_response.pairs),
                solana_count=len(solana_pairs),
            )
            return solana_pairs

        except ExternalServiceError:
            log.warning("fetch_token_by_address_api_error", address=address)
            return None
        except Exception as e:
            log.warning("fetch_token_by_address_failed", address=address, error=str(e))
            return None
