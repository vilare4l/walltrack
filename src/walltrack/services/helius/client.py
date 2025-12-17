"""Helius API client for Solana blockchain data."""

from datetime import datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from walltrack.config.settings import get_settings

log = structlog.get_logger()


class HeliusClient:
    """Async client for Helius API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: httpx.AsyncClient | None = None
        self._api_key = self._settings.helius_api_key.get_secret_value()
        self._base_url = self._settings.helius_api_url

    async def connect(self) -> None:
        """Create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
            log.info("helius_client_connected")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            log.info("helius_client_disconnected")

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client."""
        if self._client is None:
            raise RuntimeError("HeliusClient not connected. Call connect() first.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def get_token_transactions(
        self,
        mint: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        wallet: str | None = None,
        tx_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get token transactions from Helius.

        Args:
            mint: Token mint address
            start_time: Start time filter
            end_time: End time filter
            wallet: Filter by wallet address (if provided, queries wallet instead of mint)
            tx_type: Filter by transaction type (SWAP, TRANSFER, etc.)
            limit: Maximum number of transactions

        Returns:
            List of transaction data
        """
        # Use the correct endpoint: /addresses/{address}/transactions
        address = wallet if wallet else mint
        url = f"{self._base_url}/addresses/{address}/transactions"

        params: dict[str, str | int] = {
            "api-key": self._api_key,
            "limit": limit,
        }

        if tx_type:
            params["type"] = tx_type

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            transactions = data if isinstance(data, list) else data.get("transactions", [])

            # Filter by time if specified
            if start_time or end_time:
                filtered = []
                for tx in transactions:
                    tx_time = tx.get("timestamp")
                    if tx_time:
                        if isinstance(tx_time, (int, float)):
                            tx_datetime = datetime.fromtimestamp(tx_time)
                        else:
                            tx_datetime = datetime.fromisoformat(str(tx_time))

                        if start_time and tx_datetime < start_time:
                            continue
                        if end_time and tx_datetime > end_time:
                            continue

                    filtered.append(tx)
                return filtered

            return transactions

        except httpx.HTTPStatusError as e:
            log.error(
                "helius_request_failed",
                status_code=e.response.status_code,
                address=address,
            )
            raise
        except Exception as e:
            log.error("helius_error", error=str(e), address=address)
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def get_wallet_transactions(
        self,
        wallet: str,
        start_time: datetime | None = None,
        tx_types: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get transactions for a wallet.

        Args:
            wallet: Wallet address
            start_time: Filter transactions after this time
            tx_types: Filter by transaction types (e.g., ["SWAP", "TRANSFER"])
            limit: Maximum number of transactions

        Returns:
            List of transaction data
        """
        url = f"{self._base_url}/addresses/{wallet}/transactions"

        params: dict[str, str | int] = {
            "api-key": self._api_key,
            "limit": limit,
        }

        response = await self.client.get(url, params=params)
        response.raise_for_status()
        transactions: list[dict[str, Any]] = response.json()

        # Filter by time if specified
        if start_time:
            filtered = []
            for tx in transactions:
                tx_time = tx.get("timestamp")
                if tx_time:
                    if isinstance(tx_time, (int, float)):
                        tx_datetime = datetime.fromtimestamp(tx_time)
                    else:
                        tx_datetime = datetime.fromisoformat(str(tx_time))

                    if tx_datetime >= start_time:
                        filtered.append(tx)
            transactions = filtered

        # Filter by transaction types if specified
        if tx_types:
            transactions = [
                tx for tx in transactions if tx.get("type") in tx_types
            ]

        return transactions

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def get_token_metadata(self, mint: str) -> dict[str, Any]:
        """Get token metadata."""
        url = f"{self._base_url}/token-metadata"

        params = {
            "api-key": self._api_key,
        }

        body = {"mintAccounts": [mint]}

        response = await self.client.post(url, params=params, json=body)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else {}

    async def health_check(self) -> dict[str, Any]:
        """Check Helius API health."""
        try:
            if self._client is None:
                return {"status": "disconnected", "healthy": False}

            # Simple test request
            url = f"{self._base_url}/addresses/11111111111111111111111111111111/transactions"
            params: dict[str, str | int] = {"api-key": self._api_key, "limit": 1}

            response = await self.client.get(url, params=params)

            return {
                "status": "connected",
                "healthy": response.status_code == 200,
            }
        except Exception as e:
            log.error("helius_health_check_failed", error=str(e))
            return {"status": "error", "healthy": False, "error": str(e)}


# Singleton instance
_helius_client: HeliusClient | None = None


async def get_helius_client() -> HeliusClient:
    """Get or create Helius client singleton."""
    global _helius_client
    if _helius_client is None:
        _helius_client = HeliusClient()
        await _helius_client.connect()
    return _helius_client


async def close_helius_client() -> None:
    """Close Helius client."""
    global _helius_client
    if _helius_client is not None:
        await _helius_client.disconnect()
        _helius_client = None
