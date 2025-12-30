"""Helius API client for Solana blockchain data.

This module provides an async client for the Helius API with retry logic,
circuit breaker pattern, and transaction history fetching capabilities.
"""

import os

import structlog

from walltrack.core.exceptions import ExternalServiceError
from walltrack.services.base import BaseAPIClient

log = structlog.get_logger(__name__)


class HeliusClient(BaseAPIClient):
    """Async client for Helius API.

    Extends BaseAPIClient with Helius-specific methods for fetching
    transaction history and wallet data from Solana blockchain.

    Attributes:
        api_key: Helius API key from environment.
        base_url: Helius API base URL (default: https://api.helius.xyz).

    Example:
        client = HeliusClient()
        transactions = await client.get_wallet_transactions(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            limit=100
        )
        await client.close()
    """

    def __init__(self) -> None:
        """Initialize HeliusClient with API key from environment."""
        api_key = os.getenv("HELIUS_API_KEY")
        if not api_key:
            msg = "HELIUS_API_KEY environment variable not set"
            raise ValueError(msg)

        self.api_key = api_key
        base_url = os.getenv("HELIUS_API_URL", "https://api.helius.xyz")

        super().__init__(
            base_url=base_url,
            timeout=30.0,
            headers={"Content-Type": "application/json"},
        )

        log.info("helius_client_initialized", base_url=base_url)

    async def get_wallet_transactions(
        self,
        wallet_address: str,
        limit: int = 100,
        tx_type: str | None = "SWAP",
    ) -> list[dict]:
        """Get transaction history for a wallet address.

        Fetches enriched transaction data from Helius API with optional
        filtering by transaction type.

        Args:
            wallet_address: Solana wallet address to fetch transactions for.
            limit: Maximum number of transactions to return (default: 100, max: 100).
            tx_type: Filter by transaction type (e.g., "SWAP", "TRANSFER").
                    Default: "SWAP" for token swaps only.

        Returns:
            List of transaction dictionaries from Helius API.

        Raises:
            ExternalServiceError: If API request fails after retries.
            ValueError: If wallet_address is invalid or limit is out of range.

        Example:
            transactions = await client.get_wallet_transactions(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                limit=50,
                tx_type="SWAP"
            )
            # Returns list of transaction dicts with enriched Helius data

        Note:
            - Uses Helius Enhanced Transactions API
            - Includes retry logic (3 attempts) via BaseAPIClient
            - Circuit breaker protection enabled
            - Pagination is not implemented (use limit parameter)
        """
        # Validate inputs
        if not wallet_address or len(wallet_address) < 32:
            msg = f"Invalid wallet address: {wallet_address}"
            raise ValueError(msg)

        if limit < 1 or limit > 100:
            msg = f"Limit must be between 1 and 100, got {limit}"
            raise ValueError(msg)

        # Build query parameters
        params = {
            "api-key": self.api_key,
            "limit": str(limit),
        }

        if tx_type:
            params["type"] = tx_type

        # Build endpoint path
        path = f"/v0/addresses/{wallet_address}/transactions"

        log.info(
            "fetching_wallet_transactions",
            wallet_address=wallet_address[:8] + "...",
            limit=limit,
            tx_type=tx_type or "all",
        )

        try:
            # Make request via BaseAPIClient (with retry + circuit breaker)
            response = await self.get(path, params=params)
            transactions = response.json()

            # Response should be a list
            if not isinstance(transactions, list):
                log.error(
                    "unexpected_helius_response_format",
                    wallet_address=wallet_address[:8] + "...",
                    response_type=type(transactions).__name__,
                )
                return []

            log.info(
                "wallet_transactions_fetched",
                wallet_address=wallet_address[:8] + "...",
                transaction_count=len(transactions),
            )

            return transactions

        except ExternalServiceError as e:
            log.error(
                "helius_api_error",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
                status_code=e.status_code,
            )
            raise

        except Exception as e:
            log.error(
                "unexpected_error_fetching_transactions",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise ExternalServiceError(
                service="Helius API",
                message=f"Unexpected error: {e}",
            ) from e


# Global client instance (lazy initialization)
_helius_client: HeliusClient | None = None


async def get_helius_client() -> HeliusClient:
    """Get or create the global HeliusClient instance.

    Returns:
        The global HeliusClient instance.

    Example:
        client = await get_helius_client()
        transactions = await client.get_wallet_transactions("wallet_address")
    """
    global _helius_client
    if _helius_client is None:
        _helius_client = HeliusClient()
        log.debug("global_helius_client_created")
    return _helius_client


async def close_helius_client() -> None:
    """Close the global HeliusClient instance.

    Example:
        await close_helius_client()
    """
    global _helius_client
    if _helius_client is not None:
        await _helius_client.close()
        _helius_client = None
        log.debug("global_helius_client_closed")
