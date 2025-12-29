"""Solana RPC client for wallet operations.

This module provides a client for interacting with Solana RPC endpoints,
specifically for wallet validation and account information retrieval.

The client extends BaseAPIClient to inherit:
- Automatic retry with exponential backoff
- Circuit breaker pattern for failure protection
- Proper resource cleanup
"""

from typing import Any

import structlog

from walltrack.config.settings import get_settings
from walltrack.core.exceptions import WalletConnectionError
from walltrack.services.base import BaseAPIClient

log = structlog.get_logger(__name__)


class SolanaRPCClient(BaseAPIClient):
    """Client for Solana RPC operations.

    Provides methods to validate wallet addresses and retrieve account info
    from the Solana blockchain via JSON-RPC.

    Attributes:
        base_url: Solana RPC endpoint URL.
        timeout: Request timeout in seconds (5s for wallet validation).

    Example:
        client = SolanaRPCClient()
        exists = await client.validate_wallet_exists("wallet_address")
        await client.close()
    """

    def __init__(self) -> None:
        """Initialize Solana RPC client with settings."""
        settings = get_settings()
        super().__init__(
            base_url=settings.solana_rpc_url,
            timeout=5.0,  # 5 second timeout for wallet validation
            headers={"Content-Type": "application/json"},
            circuit_breaker_threshold=5,
            circuit_breaker_cooldown=30,
        )
        log.debug(
            "solana_rpc_client_initialized",
            base_url=settings.solana_rpc_url,
        )

    async def get_account_info(self, address: str) -> dict[str, Any] | None:
        """Get account info from Solana RPC.

        Calls the getAccountInfo JSON-RPC method to retrieve wallet data.

        Args:
            address: Solana wallet address (base58 format).

        Returns:
            Account info dict if wallet exists, None if not found.

        Raises:
            WalletConnectionError: If RPC call fails after retries.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [address, {"encoding": "base58"}],
        }

        log.debug("solana_get_account_info", wallet_address=address[:8] + "...")

        try:
            response = await self.post("", json=payload)
            data = response.json()

            result = data.get("result")
            if result is None:
                return None

            value = result.get("value")
            if value is None:
                log.debug(
                    "solana_wallet_not_found",
                    wallet_address=address[:8] + "...",
                )
                return None

            log.debug(
                "solana_wallet_found",
                wallet_address=address[:8] + "...",
                lamports=value.get("lamports", 0),
            )
            return value

        except Exception as e:
            log.error(
                "solana_get_account_info_failed",
                wallet_address=address[:8] + "...",
                error=str(e),
            )
            raise WalletConnectionError(
                f"Failed to validate wallet: {e}",
                wallet_address=address,
            ) from e

    async def validate_wallet_exists(self, address: str) -> bool:
        """Check if wallet address exists on-chain.

        This is a convenience method that wraps get_account_info
        to return a simple boolean result.

        Args:
            address: Solana wallet address to validate.

        Returns:
            True if wallet exists on-chain, False otherwise.
        """
        account_info = await self.get_account_info(address)
        return account_info is not None
