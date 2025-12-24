"""Service to find tokens that have pumped for wallet discovery."""

from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import TokenLaunch

log = structlog.get_logger()

# DexScreener API endpoints
DEXSCREENER_BASE_URL = "https://api.dexscreener.com"
SOLANA_CHAIN = "solana"

# Default pump criteria
DEFAULT_MIN_PRICE_CHANGE_PCT = 100.0  # At least 100% gain
DEFAULT_MIN_VOLUME_USD = 50000.0  # Minimum $50k volume
DEFAULT_MIN_LIQUIDITY_USD = 10000.0  # Minimum $10k liquidity
DEFAULT_MAX_AGE_HOURS = 72  # Max 72 hours old


class PumpFinder:
    """Finds tokens that have pumped recently for wallet discovery."""

    def __init__(self, timeout: int = 30) -> None:
        """Initialize PumpFinder.

        Args:
            timeout: Request timeout in seconds
        """
        self.settings = get_settings()
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    async def find_pumped_tokens(
        self,
        min_price_change_pct: float = DEFAULT_MIN_PRICE_CHANGE_PCT,
        min_volume_usd: float = DEFAULT_MIN_VOLUME_USD,
        min_liquidity_usd: float = DEFAULT_MIN_LIQUIDITY_USD,
        max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
        limit: int = 50,
    ) -> list[TokenLaunch]:
        """Find tokens that have pumped based on criteria.

        Uses DexScreener's token profiles and boosted tokens endpoints
        to find high-performing tokens on Solana.

        Args:
            min_price_change_pct: Minimum 24h price change percentage
            min_volume_usd: Minimum 24h volume in USD
            min_liquidity_usd: Minimum liquidity in USD
            max_age_hours: Maximum token age in hours
            limit: Maximum number of tokens to return

        Returns:
            List of TokenLaunch objects for discovered tokens
        """
        log.info(
            "pump_search_started",
            min_change=min_price_change_pct,
            min_volume=min_volume_usd,
            max_age_hours=max_age_hours,
        )

        token_launches: list[TokenLaunch] = []

        try:
            # Strategy 1: Get boosted tokens (promoted/trending)
            boosted = await self._fetch_boosted_tokens()
            token_launches.extend(
                self._filter_and_convert(
                    boosted,
                    min_price_change_pct,
                    min_volume_usd,
                    min_liquidity_usd,
                    max_age_hours,
                )
            )

            # Strategy 2: Get token profiles (latest tokens with activity)
            profiles = await self._fetch_token_profiles()
            for token in self._filter_and_convert(
                profiles,
                min_price_change_pct,
                min_volume_usd,
                min_liquidity_usd,
                max_age_hours,
            ):
                # Avoid duplicates
                if not any(t.mint == token.mint for t in token_launches):
                    token_launches.append(token)

            # Sort by volume and limit
            token_launches.sort(key=lambda t: t.volume_24h, reverse=True)
            token_launches = token_launches[:limit]

            log.info(
                "pump_search_completed",
                found=len(token_launches),
            )

        except Exception as e:
            log.error("pump_search_error", error=str(e))

        return token_launches

    async def find_tokens_by_addresses(
        self,
        addresses: list[str],
    ) -> list[TokenLaunch]:
        """Fetch token launch data for specific addresses.

        Useful when you already have a list of token addresses
        (e.g., from another source) and want to create TokenLaunch objects.

        Args:
            addresses: List of token mint addresses

        Returns:
            List of TokenLaunch objects
        """
        token_launches: list[TokenLaunch] = []
        client = await self._get_client()

        for address in addresses:
            try:
                url = f"{DEXSCREENER_BASE_URL}/latest/dex/tokens/{address}"
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                pairs = data.get("pairs", [])
                if pairs:
                    token_launch = self._pair_to_token_launch(pairs[0])
                    if token_launch:
                        token_launches.append(token_launch)

            except Exception as e:
                log.debug(
                    "token_fetch_failed",
                    address=address[:20],
                    error=str(e),
                )
                continue

        return token_launches

    async def _fetch_boosted_tokens(self) -> list[dict[str, Any]]:
        """Fetch boosted/trending tokens from DexScreener."""
        client = await self._get_client()

        try:
            # DexScreener boosted tokens endpoint
            url = f"{DEXSCREENER_BASE_URL}/token-boosts/top/v1"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # Filter to Solana only
            tokens = [
                t for t in data
                if t.get("chainId") == SOLANA_CHAIN
            ]

            log.debug("boosted_tokens_fetched", count=len(tokens))
            return tokens

        except Exception as e:
            log.warning("boosted_fetch_failed", error=str(e))
            return []

    async def _fetch_token_profiles(self) -> list[dict[str, Any]]:
        """Fetch latest token profiles from DexScreener."""
        client = await self._get_client()

        try:
            # DexScreener token profiles endpoint (latest tokens)
            url = f"{DEXSCREENER_BASE_URL}/token-profiles/latest/v1"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # Filter to Solana only
            tokens = [
                t for t in data
                if t.get("chainId") == SOLANA_CHAIN
            ]

            log.debug("token_profiles_fetched", count=len(tokens))
            return tokens

        except Exception as e:
            log.warning("profiles_fetch_failed", error=str(e))
            return []

    def _filter_and_convert(
        self,
        tokens: list[dict[str, Any]],
        min_price_change_pct: float,  # noqa: ARG002 - for future filtering
        min_volume_usd: float,  # noqa: ARG002 - for future filtering
        min_liquidity_usd: float,  # noqa: ARG002 - for future filtering
        max_age_hours: int,  # noqa: ARG002 - for future filtering
    ) -> list[TokenLaunch]:
        """Filter tokens by pump criteria and convert to TokenLaunch.

        Note: Parameters are kept for future implementation of
        more sophisticated filtering based on price/volume data.
        Currently returns all tokens that can be converted.
        """
        results: list[TokenLaunch] = []

        for token_data in tokens:
            try:
                # Get token address
                address = token_data.get("tokenAddress")
                if not address:
                    continue

                # Note: boosted/profiles endpoints have limited data
                # Full filtering would require fetching detailed pair data
                # For now, we convert all tokens and let the caller filter

                token_launch = self._token_data_to_launch(token_data)
                if token_launch:
                    results.append(token_launch)

            except Exception as e:
                log.debug(
                    "token_filter_failed",
                    token=str(token_data.get("tokenAddress", "?"))[:20],
                    error=str(e),
                )
                continue

        return results

    def _token_data_to_launch(
        self,
        data: dict[str, Any],
    ) -> TokenLaunch | None:
        """Convert token data to TokenLaunch object."""
        try:
            address = data.get("tokenAddress")
            if not address:
                return None

            # Parse created time if available
            created_at = None
            if data.get("createdAt"):
                created_at = datetime.fromtimestamp(
                    data["createdAt"] / 1000,
                    tz=UTC,
                )

            # Use current time if no creation time
            launch_time = created_at or datetime.now(UTC)

            return TokenLaunch(
                mint=address,
                symbol=data.get("symbol", ""),
                launch_time=launch_time,
                peak_mcap=data.get("marketCap", 0.0) or 0.0,
                current_mcap=data.get("marketCap", 0.0) or 0.0,
                volume_24h=data.get("volume24h", 0.0) or 0.0,
            )

        except Exception as e:
            log.debug("token_convert_failed", error=str(e))
            return None

    def _pair_to_token_launch(
        self,
        pair: dict[str, Any],
    ) -> TokenLaunch | None:
        """Convert DexScreener pair data to TokenLaunch."""
        try:
            base_token = pair.get("baseToken", {})
            address = base_token.get("address")

            if not address:
                return None

            # Parse created time
            created_at = None
            if pair.get("pairCreatedAt"):
                created_at = datetime.fromtimestamp(
                    pair["pairCreatedAt"] / 1000,
                    tz=UTC,
                )

            launch_time = created_at or datetime.now(UTC)

            # Get volume
            volume = pair.get("volume", {})
            volume_24h = volume.get("h24", 0.0) or 0.0

            return TokenLaunch(
                mint=address,
                symbol=base_token.get("symbol", ""),
                launch_time=launch_time,
                peak_mcap=pair.get("marketCap", 0.0) or 0.0,
                current_mcap=pair.get("marketCap", 0.0) or 0.0,
                volume_24h=volume_24h,
            )

        except Exception as e:
            log.debug("pair_convert_failed", error=str(e))
            return None


async def find_pumped_tokens_quick(
    min_price_change_pct: float = DEFAULT_MIN_PRICE_CHANGE_PCT,
    min_volume_usd: float = DEFAULT_MIN_VOLUME_USD,
    limit: int = 20,
) -> list[TokenLaunch]:
    """Quick helper function to find pumped tokens.

    Args:
        min_price_change_pct: Minimum 24h price change percentage
        min_volume_usd: Minimum 24h volume in USD
        limit: Maximum number of tokens to return

    Returns:
        List of TokenLaunch objects
    """
    finder = PumpFinder()
    try:
        return await finder.find_pumped_tokens(
            min_price_change_pct=min_price_change_pct,
            min_volume_usd=min_volume_usd,
            limit=limit,
        )
    finally:
        await finder.close()
