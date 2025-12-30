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

    async def get_token_accounts(
        self, token_mint: str, limit: int = 100
    ) -> list[str]:
        """Get token holder wallet addresses via getProgramAccounts RPC.

        Discovers wallet addresses holding a specific SPL token by querying
        the Token Program for all token accounts associated with the mint.

        Args:
            token_mint: Token mint address (base58 format).
            limit: Maximum number of token accounts to return (default 100).

        Returns:
            List of wallet addresses (owners of token accounts) with non-zero balance.
            Returns empty list if no holders found.

        Raises:
            WalletConnectionError: If RPC call fails after retries.

        Note:
            Uses Solana RPC getProgramAccounts with:
            - Token Program ID: TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA
            - Filter: token mint address + jsonParsed encoding
            - Returns only accounts with balance > 0
        """
        # Token Program ID (SPL Token Program)
        token_program_id = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getProgramAccounts",
            "params": [
                token_program_id,
                {
                    "encoding": "jsonParsed",
                    "filters": [
                        {"dataSize": 165},  # Token account size
                        {
                            "memcmp": {
                                "offset": 0,
                                "bytes": token_mint,  # Filter by mint address
                            }
                        },
                    ],
                },
            ],
        }

        log.debug(
            "solana_get_token_accounts",
            token_mint=token_mint[:8] + "...",
            limit=limit,
        )

        try:
            response = await self.post("", json=payload)
            data = response.json()

            result = data.get("result", [])
            if not result:
                log.debug(
                    "solana_no_token_holders_found",
                    token_mint=token_mint[:8] + "...",
                )
                return []

            # Extract owner addresses from parsed token account data
            wallet_addresses = []
            for account in result[:limit]:  # Respect limit
                try:
                    parsed_info = account["account"]["data"]["parsed"]["info"]
                    owner = parsed_info.get("owner")
                    token_amount = parsed_info.get("tokenAmount", {})
                    amount = int(token_amount.get("amount", "0"))

                    # Only include accounts with non-zero balance
                    if owner and amount > 0:
                        wallet_addresses.append(owner)
                except (KeyError, ValueError) as e:
                    log.warning(
                        "solana_token_account_parse_error",
                        account_pubkey=account.get("pubkey", "unknown"),
                        error=str(e),
                    )
                    continue

            log.info(
                "solana_token_accounts_retrieved",
                token_mint=token_mint[:8] + "...",
                holders_count=len(wallet_addresses),
            )
            return wallet_addresses

        except Exception as e:
            log.error(
                "solana_get_token_accounts_failed",
                token_mint=token_mint[:8] + "...",
                error=str(e),
            )
            raise WalletConnectionError(
                f"Failed to get token accounts: {e}",
                wallet_address=token_mint,
            ) from e
