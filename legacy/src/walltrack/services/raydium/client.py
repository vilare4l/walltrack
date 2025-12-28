"""Raydium API client for fallback swaps.

Used when Jupiter fails (NFR19).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from walltrack.config.jupiter_settings import JupiterSettings, get_jupiter_settings
from walltrack.models.trade import SwapQuote

logger = structlog.get_logger()


class RaydiumError(Exception):
    """Raydium API error."""

    pass


class RaydiumClient:
    """Raydium API client for fallback swaps.

    Used when Jupiter fails (NFR19).
    """

    def __init__(self, settings: JupiterSettings | None = None) -> None:
        self._settings = settings or get_jupiter_settings()
        self._http_client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize HTTP client."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.quote_timeout_seconds),
            headers={"Content-Type": "application/json"},
        )
        logger.info("raydium_client_initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    )
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int | None = None,
    ) -> SwapQuote:
        """Get swap quote from Raydium.

        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in smallest unit
            slippage_bps: Slippage tolerance

        Returns:
            SwapQuote from Raydium
        """
        if not self._http_client:
            raise RaydiumError("Client not initialized")

        slippage = slippage_bps or self._settings.default_slippage_bps

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippage": slippage / 10000,  # Raydium uses decimal
        }

        start = time.perf_counter()

        try:
            response = await self._http_client.get(
                f"{self._settings.raydium_api_url}/swap/compute",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            latency = (time.perf_counter() - start) * 1000

            # Map Raydium response to our SwapQuote model
            quote = SwapQuote(
                input_mint=input_mint,
                output_mint=output_mint,
                input_amount=amount,
                output_amount=int(data.get("amountOut", 0)),
                output_amount_min=int(data.get("minAmountOut", 0)),
                slippage_bps=slippage,
                price_impact_pct=float(data.get("priceImpact", 0)),
                route_plan=[{"source": "raydium"}],
                quote_source="raydium",
                expires_at=datetime.utcnow() + timedelta(seconds=30),
            )

            logger.info(
                "raydium_quote_received",
                output_amount=quote.output_amount,
                latency_ms=round(latency, 2),
            )

            return quote

        except httpx.HTTPStatusError as e:
            logger.error(
                "raydium_quote_http_error",
                status=e.response.status_code,
            )
            raise RaydiumError(f"Quote failed: {e.response.status_code}") from e

        except Exception as e:
            logger.error("raydium_quote_error", error=str(e))
            raise RaydiumError(f"Quote failed: {e}") from e


# Singleton
_raydium_client: RaydiumClient | None = None


async def get_raydium_client() -> RaydiumClient:
    """Get or create Raydium client singleton."""
    global _raydium_client
    if _raydium_client is None:
        _raydium_client = RaydiumClient()
        await _raydium_client.initialize()
    return _raydium_client
