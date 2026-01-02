"""Solana RPC client for wallet operations.

This module provides a client for interacting with Solana RPC endpoints,
specifically for wallet validation and account information retrieval.

The client extends BaseAPIClient to inherit:
- Automatic retry with exponential backoff
- Circuit breaker pattern for failure protection
- Proper resource cleanup
"""

import asyncio
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
            rate_limit="2 req/sec (global)",
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

    async def _throttle_request(self) -> None:
        """Enforce global rate limiting (2 req/sec shared across all instances).

        Uses GlobalRateLimiter singleton to coordinate rate limiting across:
        - WalletDiscoveryWorker
        - WalletProfilingWorker
        - DecayCheckScheduler

        Called automatically before each RPC request.

        Story: 3.5.5 - Global RPC Rate Limiter
        """
        from walltrack.services.solana.rate_limiter import GlobalRateLimiter

        limiter = GlobalRateLimiter.get_instance()
        await limiter.acquire()

    async def getSignaturesForAddress(
        self, address: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        """Get transaction signatures for an address via getSignaturesForAddress RPC.

        Fetches a list of transaction signatures for the given address,
        sorted by most recent first.

        Args:
            address: Solana address (wallet or token mint) to fetch signatures for.
            limit: Maximum number of signatures to return (default: 1000, max: 1000).

        Returns:
            List of signature objects with structure:
            [
                {
                    "signature": "5j7s8k...",
                    "slot": 123456789,
                    "blockTime": 1703001234,
                    "err": None,
                    "memo": None,
                },
                ...
            ]
            Returns empty list if no transactions found.

        Raises:
            WalletConnectionError: If RPC call fails after retries.

        Note:
            - Rate limited to 2 req/sec (safety margin below 4 req/sec RPC limit)
            - Retries automatically on 429 errors with exponential backoff
            - Signatures are returned newest first
        """
        await self._throttle_request()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [address, {"limit": limit}],
        }

        log.debug(
            "solana_get_signatures_for_address",
            address=address[:8] + "...",
            limit=limit,
        )

        try:
            response = await self.post("", json=payload)
            data = response.json()

            result = data.get("result", [])

            log.info(
                "solana_signatures_retrieved",
                address=address[:8] + "...",
                count=len(result),
            )

            return result

        except Exception as e:
            log.error(
                "solana_get_signatures_failed",
                address=address[:8] + "...",
                error=str(e),
            )
            raise WalletConnectionError(
                f"Failed to fetch signatures for address: {e}",
                wallet_address=address,
            ) from e

    async def getTransaction(self, signature: str) -> dict[str, Any] | None:
        """Get full transaction details via getTransaction RPC.

        Fetches complete transaction data including instructions, accounts,
        balance changes, and token transfers.

        Args:
            signature: Transaction signature (base58 format).

        Returns:
            Transaction object with structure:
            {
                "slot": 123456789,
                "transaction": {
                    "message": {
                        "accountKeys": ["wallet1", "wallet2", ...],
                        "instructions": [...]
                    },
                    "signatures": ["sig1", ...]
                },
                "meta": {
                    "err": None,
                    "preBalances": [1000000000, ...],
                    "postBalances": [500000000, ...],
                    "preTokenBalances": [...],
                    "postTokenBalances": [...]
                },
                "blockTime": 1703001234
            }
            Returns None if transaction not found.

        Raises:
            WalletConnectionError: If RPC call fails after retries.

        Note:
            - Rate limited to 2 req/sec (safety margin below 4 req/sec RPC limit)
            - Retries automatically on 429 errors with exponential backoff
            - Uses "jsonParsed" encoding for token balances
            - Max transaction age: ~2 weeks on RPC public nodes
        """
        await self._throttle_request()

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        }

        log.debug("solana_get_transaction", signature=signature[:8] + "...")

        try:
            response = await self.post("", json=payload)
            data = response.json()

            result = data.get("result")

            if result is None:
                log.debug(
                    "solana_transaction_not_found",
                    signature=signature[:8] + "...",
                )
                return None

            log.debug(
                "solana_transaction_retrieved",
                signature=signature[:8] + "...",
                block_time=result.get("blockTime"),
            )

            return result

        except Exception as e:
            log.error(
                "solana_get_transaction_failed",
                signature=signature[:8] + "...",
                error=str(e),
            )
            raise WalletConnectionError(
                f"Failed to fetch transaction: {e}",
                wallet_address=signature,
            ) from e
