"""Jupiter V6 API client for swap execution.

Provides:
- Quote fetching with best route
- Swap transaction building
- Transaction submission and confirmation
- Retry logic with exponential backoff
"""

from __future__ import annotations

import base64
import time
from datetime import datetime, timedelta

import httpx
import structlog
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair  # noqa: TC002
from solders.transaction import VersionedTransaction
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from walltrack.config.jupiter_settings import JupiterSettings, get_jupiter_settings
from walltrack.config.wallet_settings import get_wallet_settings
from walltrack.models.trade import (
    FailureReason,
    SwapQuote,
    SwapResult,
    SwapTransaction,
    TradeStatus,
)

logger = structlog.get_logger()


class JupiterError(Exception):
    """Base Jupiter API error."""

    pass


class QuoteError(JupiterError):
    """Failed to get quote."""

    pass


class SwapError(JupiterError):
    """Failed to execute swap."""

    pass


class JupiterClient:
    """Jupiter V6 API client for swap execution.

    Provides:
    - Quote fetching with best route
    - Swap transaction building
    - Transaction submission and confirmation
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        settings: JupiterSettings | None = None,
        rpc_client: AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_jupiter_settings()
        self._rpc_client = rpc_client
        self._http_client: httpx.AsyncClient | None = None

    async def initialize(self) -> None:
        """Initialize HTTP client and dependencies."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.quote_timeout_seconds),
            headers={"Content-Type": "application/json"},
        )

        if self._rpc_client is None:
            wallet_settings = get_wallet_settings()
            self._rpc_client = AsyncClient(
                wallet_settings.solana_rpc_url,
                commitment=Confirmed,
            )

        logger.info("jupiter_client_initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int | None = None,
    ) -> SwapQuote:
        """Get swap quote from Jupiter V6 API.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Slippage tolerance in basis points

        Returns:
            SwapQuote with best route
        """
        if not self._http_client:
            raise JupiterError("Client not initialized")

        slippage = slippage_bps or self._settings.default_slippage_bps

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage,
            "onlyDirectRoutes": False,
            "asLegacyTransaction": False,
        }

        logger.debug(
            "jupiter_quote_request",
            input_mint=input_mint[:8],
            output_mint=output_mint[:8],
            amount=amount,
            slippage_bps=slippage,
        )

        start = time.perf_counter()

        try:
            response = await self._http_client.get(
                f"{self._settings.jupiter_api_url}/quote",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            latency = (time.perf_counter() - start) * 1000

            quote = SwapQuote(
                input_mint=data["inputMint"],
                output_mint=data["outputMint"],
                input_amount=int(data["inAmount"]),
                output_amount=int(data["outAmount"]),
                output_amount_min=int(data.get("otherAmountThreshold", data["outAmount"])),
                slippage_bps=slippage,
                price_impact_pct=float(data.get("priceImpactPct", 0)),
                route_plan=data.get("routePlan", []),
                quote_source="jupiter",
                expires_at=datetime.utcnow() + timedelta(seconds=30),
            )

            logger.info(
                "jupiter_quote_received",
                output_amount=quote.output_amount,
                price_impact=quote.price_impact_pct,
                route_count=len(quote.route_plan),
                latency_ms=round(latency, 2),
            )

            return quote

        except httpx.HTTPStatusError as e:
            logger.error(
                "jupiter_quote_http_error",
                status=e.response.status_code,
                body=e.response.text[:200],
            )
            raise QuoteError(f"Quote failed: {e.response.status_code}") from e

        except Exception as e:
            logger.error("jupiter_quote_error", error=str(e))
            raise QuoteError(f"Quote failed: {e}") from e

    async def build_swap_transaction(
        self,
        quote: SwapQuote,
        user_public_key: str,
        priority_fee: int | None = None,
    ) -> SwapTransaction:
        """Build swap transaction from quote.

        Args:
            quote: SwapQuote from get_quote()
            user_public_key: User's wallet public key
            priority_fee: Priority fee in lamports

        Returns:
            SwapTransaction ready for signing
        """
        if not self._http_client:
            raise JupiterError("Client not initialized")

        fee = priority_fee or self._settings.priority_fee_lamports

        payload = {
            "quoteResponse": {
                "inputMint": quote.input_mint,
                "outputMint": quote.output_mint,
                "inAmount": str(quote.input_amount),
                "outAmount": str(quote.output_amount),
                "otherAmountThreshold": str(quote.output_amount_min),
                "slippageBps": quote.slippage_bps,
                "priceImpactPct": str(quote.price_impact_pct),
                "routePlan": quote.route_plan,
            },
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": True,
            "computeUnitPriceMicroLamports": fee,
            "asLegacyTransaction": False,
        }

        try:
            response = await self._http_client.post(
                self._settings.jupiter_swap_api_url,
                json=payload,
                timeout=self._settings.swap_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            # Get recent blockhash for expiry calculation
            blockhash_response = await self._rpc_client.get_latest_blockhash()
            recent_blockhash = str(blockhash_response.value.blockhash)

            return SwapTransaction(
                quote=quote,
                serialized_transaction=data["swapTransaction"],
                recent_blockhash=recent_blockhash,
                expires_at=datetime.utcnow() + timedelta(seconds=60),
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "jupiter_swap_build_error",
                status=e.response.status_code,
                body=e.response.text[:200],
            )
            raise SwapError(f"Swap build failed: {e.response.status_code}") from e

    async def execute_swap(
        self,
        swap_tx: SwapTransaction,
        keypair: Keypair,
    ) -> SwapResult:
        """Execute swap transaction.

        Args:
            swap_tx: Prepared swap transaction
            keypair: Wallet keypair for signing

        Returns:
            SwapResult with execution details
        """
        start = time.perf_counter()

        try:
            # Deserialize and sign transaction
            tx_bytes = base64.b64decode(swap_tx.serialized_transaction)
            transaction = VersionedTransaction.from_bytes(tx_bytes)

            # Sign transaction
            signed_tx = transaction
            signed_tx.sign([keypair])

            # Submit transaction
            logger.info("jupiter_swap_submitting")

            response = await self._rpc_client.send_transaction(
                signed_tx,
                opts={
                    "skip_preflight": False,
                    "preflight_commitment": "confirmed",
                    "max_retries": 3,
                },
            )

            tx_signature = str(response.value)
            logger.info("jupiter_swap_submitted", signature=tx_signature[:16])

            # Wait for confirmation
            confirmation = await self._rpc_client.confirm_transaction(
                tx_signature,
                commitment="confirmed",
                sleep_seconds=0.5,
            )

            execution_time = (time.perf_counter() - start) * 1000

            if confirmation.value[0].err:
                # Transaction failed on-chain
                error_msg = str(confirmation.value[0].err)
                failure_reason = self._classify_error(error_msg)

                logger.error(
                    "jupiter_swap_onchain_error",
                    signature=tx_signature[:16],
                    error=error_msg,
                )

                return SwapResult(
                    success=False,
                    status=TradeStatus.FAILED,
                    tx_signature=tx_signature,
                    input_amount=swap_tx.quote.input_amount,
                    execution_time_ms=execution_time,
                    failure_reason=failure_reason,
                    error_message=error_msg,
                )

            # Success!
            logger.info(
                "jupiter_swap_confirmed",
                signature=tx_signature[:16],
                execution_time_ms=round(execution_time, 2),
            )

            return SwapResult(
                success=True,
                status=TradeStatus.SUCCESS,
                tx_signature=tx_signature,
                input_amount=swap_tx.quote.input_amount,
                output_amount=swap_tx.quote.output_amount,
                entry_price=swap_tx.quote.effective_price,
                execution_time_ms=execution_time,
                quote_source="jupiter",
                confirmed_at=datetime.utcnow(),
            )

        except Exception as e:
            execution_time = (time.perf_counter() - start) * 1000
            logger.error("jupiter_swap_error", error=str(e))

            return SwapResult(
                success=False,
                status=TradeStatus.FAILED,
                tx_signature=None,
                input_amount=swap_tx.quote.input_amount,
                execution_time_ms=execution_time,
                failure_reason=FailureReason.UNKNOWN,
                error_message=str(e),
            )

    def _classify_error(self, error_msg: str) -> FailureReason:
        """Classify on-chain error to FailureReason."""
        error_lower = error_msg.lower()

        if "slippage" in error_lower or "exceeds" in error_lower:
            return FailureReason.SLIPPAGE_EXCEEDED
        elif "insufficient" in error_lower or "balance" in error_lower:
            return FailureReason.INSUFFICIENT_BALANCE
        elif "expired" in error_lower or "blockhash" in error_lower:
            return FailureReason.TRANSACTION_EXPIRED
        else:
            return FailureReason.UNKNOWN


# Singleton
_jupiter_client: JupiterClient | None = None


async def get_jupiter_client() -> JupiterClient:
    """Get or create Jupiter client singleton."""
    global _jupiter_client
    if _jupiter_client is None:
        _jupiter_client = JupiterClient()
        await _jupiter_client.initialize()
    return _jupiter_client
