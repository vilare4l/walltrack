"""Helius API client for Solana blockchain data."""

from datetime import UTC, datetime
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
                            tx_datetime = datetime.fromtimestamp(tx_time, tz=UTC)
                        else:
                            tx_datetime = datetime.fromisoformat(str(tx_time))
                            if tx_datetime.tzinfo is None:
                                tx_datetime = tx_datetime.replace(tzinfo=UTC)

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
                        tx_datetime = datetime.fromtimestamp(tx_time, tz=UTC)
                    else:
                        tx_datetime = datetime.fromisoformat(str(tx_time))
                        if tx_datetime.tzinfo is None:
                            tx_datetime = tx_datetime.replace(tzinfo=UTC)

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

    # ============ Webhook Management ============

    async def create_webhook(
        self,
        webhook_url: str,
        wallet_addresses: list[str],
        webhook_type: str = "enhanced",
        transaction_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new webhook with Helius to monitor wallet addresses.

        Args:
            webhook_url: URL to receive webhook notifications
            wallet_addresses: List of wallet addresses to monitor
            webhook_type: Type of webhook ("enhanced" or "raw")
            transaction_types: Filter by transaction types (e.g., ["SWAP"])

        Returns:
            Webhook creation response with webhook ID
        """
        url = f"{self._base_url}/webhooks"
        params = {"api-key": self._api_key}

        payload: dict[str, Any] = {
            "webhookURL": webhook_url,
            "accountAddresses": wallet_addresses,
            "webhookType": webhook_type,
            "transactionTypes": transaction_types or ["SWAP"],
        }

        try:
            response = await self.client.post(url, params=params, json=payload)
            response.raise_for_status()
            result = response.json()
            log.info(
                "helius_webhook_created",
                webhook_id=result.get("webhookID"),
                wallet_count=len(wallet_addresses),
            )
            return result
        except httpx.HTTPStatusError as e:
            log.error(
                "helius_webhook_create_failed",
                status_code=e.response.status_code,
                detail=e.response.text,
            )
            raise

    async def update_webhook(
        self,
        webhook_id: str,
        wallet_addresses: list[str] | None = None,
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Update an existing webhook.

        Args:
            webhook_id: ID of the webhook to update
            wallet_addresses: New list of wallet addresses (replaces existing)
            webhook_url: New webhook URL

        Returns:
            Updated webhook data
        """
        url = f"{self._base_url}/webhooks/{webhook_id}"
        params = {"api-key": self._api_key}

        payload: dict[str, Any] = {}
        if wallet_addresses is not None:
            payload["accountAddresses"] = wallet_addresses
        if webhook_url is not None:
            payload["webhookURL"] = webhook_url

        try:
            response = await self.client.put(url, params=params, json=payload)
            response.raise_for_status()
            result = response.json()
            log.info(
                "helius_webhook_updated",
                webhook_id=webhook_id,
                wallet_count=len(wallet_addresses) if wallet_addresses else "unchanged",
            )
            return result
        except httpx.HTTPStatusError as e:
            log.error(
                "helius_webhook_update_failed",
                webhook_id=webhook_id,
                status_code=e.response.status_code,
            )
            raise

    async def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook.

        Args:
            webhook_id: ID of the webhook to delete

        Returns:
            True if deletion successful
        """
        url = f"{self._base_url}/webhooks/{webhook_id}"
        params = {"api-key": self._api_key}

        try:
            response = await self.client.delete(url, params=params)
            response.raise_for_status()
            log.info("helius_webhook_deleted", webhook_id=webhook_id)
            return True
        except httpx.HTTPStatusError as e:
            log.error(
                "helius_webhook_delete_failed",
                webhook_id=webhook_id,
                status_code=e.response.status_code,
            )
            raise

    async def list_webhooks(self) -> list[dict[str, Any]]:
        """
        List all webhooks for this API key.

        Returns:
            List of webhook configurations
        """
        url = f"{self._base_url}/webhooks"
        params = {"api-key": self._api_key}

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            webhooks = response.json()
            log.debug("helius_webhooks_listed", count=len(webhooks))
            return webhooks
        except httpx.HTTPStatusError as e:
            log.error(
                "helius_webhooks_list_failed",
                status_code=e.response.status_code,
            )
            raise

    async def get_webhook(self, webhook_id: str) -> dict[str, Any] | None:
        """
        Get a specific webhook by ID.

        Args:
            webhook_id: ID of the webhook

        Returns:
            Webhook data or None if not found
        """
        url = f"{self._base_url}/webhooks/{webhook_id}"
        params = {"api-key": self._api_key}

        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def sync_webhook_wallets(
        self,
        webhook_id: str,
        wallet_addresses: list[str],
    ) -> dict[str, Any]:
        """
        Sync webhook with current list of tracked wallets.
        Adds new wallets and keeps existing ones.

        Args:
            webhook_id: ID of the webhook to sync
            wallet_addresses: Complete list of wallet addresses to monitor

        Returns:
            Updated webhook data
        """
        return await self.update_webhook(webhook_id, wallet_addresses=wallet_addresses)


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
