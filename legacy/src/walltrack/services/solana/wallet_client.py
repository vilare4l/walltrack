"""Solana wallet client for trading.

Secure wallet client for trade execution on Solana.

SECURITY NOTES:
- Private key is NEVER logged
- Safe mode prevents trades on connection failure
- All operations validate connectivity first
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

import base58
import structlog
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from walltrack.config.wallet_settings import WalletSettings, get_wallet_settings
from walltrack.models.trading_wallet import (
    SafeModeReason,
    SigningResult,
    TokenBalance,
    WalletBalance,
    WalletConnectionStatus,
    WalletState,
)

logger = structlog.get_logger()

# SPL Token Program ID
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")


class WalletConnectionError(Exception):
    """Raised when wallet connection fails."""

    pass


class WalletClient:
    """Secure Solana wallet client for trade execution.

    SECURITY NOTES:
    - Private key is NEVER logged
    - Safe mode prevents trades on connection failure
    - All operations validate connectivity first
    """

    def __init__(self, settings: WalletSettings | None = None) -> None:
        self._settings = settings or get_wallet_settings()
        self._keypair: Keypair | None = None
        self._client: AsyncClient | None = None
        self._state = WalletState(
            public_key="11111111111111111111111111111111",  # Placeholder (system program)
            status=WalletConnectionStatus.DISCONNECTED,
        )
        self._initialized = False
        self._balance_lock = asyncio.Lock()

    async def initialize(self) -> WalletState:
        """Initialize wallet from configuration.

        Loads keypair from environment and validates connectivity.
        """
        try:
            logger.info("wallet_initializing")

            # Load keypair from secret (NEVER log the key!)
            private_key_bytes = base58.b58decode(
                self._settings.trading_wallet_private_key.get_secret_value()
            )
            self._keypair = Keypair.from_bytes(private_key_bytes)

            # Update state with actual public key
            self._state = WalletState(
                public_key=str(self._keypair.pubkey()),
                status=WalletConnectionStatus.VALIDATING,
            )

            logger.info(
                "wallet_keypair_loaded",
                public_key=self._state.public_key,
            )

            # Initialize RPC client
            self._client = AsyncClient(
                self._settings.solana_rpc_url,
                commitment=Commitment(self._settings.rpc_commitment),
            )

            # Validate connectivity
            await self._validate_connectivity()

            # Fetch initial balance
            await self.refresh_balance()

            self._state.status = WalletConnectionStatus.CONNECTED
            self._state.last_validated = datetime.utcnow()
            self._initialized = True

            logger.info(
                "wallet_initialized",
                public_key=self._state.public_key,
                sol_balance=self._state.balance.sol_balance_ui if self._state.balance else 0,
            )

            return self._state

        except Exception as e:
            logger.error("wallet_initialization_failed", error=str(e))
            await self._enter_safe_mode(SafeModeReason.CONNECTION_FAILED, str(e))
            raise WalletConnectionError(f"Failed to initialize wallet: {e}") from e

    async def _validate_connectivity(self) -> None:
        """Validate RPC connectivity and wallet access."""
        if not self._client:
            raise WalletConnectionError("RPC client not initialized")

        # Test RPC connection
        try:
            health = await self._client.get_health()
            if health.value != "ok":
                raise WalletConnectionError(f"RPC unhealthy: {health.value}")
        except Exception as e:
            raise WalletConnectionError(f"RPC connection failed: {e}") from e

        logger.debug("wallet_rpc_healthy")

    async def validate_signing(self) -> SigningResult:
        """Test that wallet can sign transactions.

        Signs a test message to verify keypair works correctly.
        """
        if not self._keypair:
            return SigningResult(
                success=False,
                error="Wallet not initialized",
                latency_ms=0,
            )

        start = time.perf_counter()

        try:
            # Create a test message
            test_message = b"WallTrack signing validation test"

            # Sign the message
            signature = self._keypair.sign_message(test_message)

            latency_ms = (time.perf_counter() - start) * 1000

            logger.info(
                "wallet_signing_validated",
                latency_ms=round(latency_ms, 2),
            )

            return SigningResult(
                success=True,
                message_hash=test_message.hex(),
                signature=str(signature),
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error("wallet_signing_failed", error=str(e))

            await self._enter_safe_mode(SafeModeReason.SIGNING_FAILED, str(e))

            return SigningResult(
                success=False,
                error=str(e),
                latency_ms=latency_ms,
            )

    async def refresh_balance(self) -> WalletBalance:
        """Refresh wallet balance (SOL + tokens)."""
        async with self._balance_lock:
            if not self._client or not self._keypair:
                raise WalletConnectionError("Wallet not initialized")

            pubkey = self._keypair.pubkey()

            # Get SOL balance
            sol_response = await self._client.get_balance(pubkey)
            sol_lamports = sol_response.value
            sol_ui = sol_lamports / 1_000_000_000  # Convert lamports to SOL

            # Get token accounts
            token_balances = await self._fetch_token_balances(pubkey)

            # Calculate total value
            total_value = sol_ui + sum(tb.estimated_value_sol or 0 for tb in token_balances)

            balance = WalletBalance(
                sol_balance=float(sol_lamports),
                sol_balance_ui=sol_ui,
                token_balances=token_balances,
                total_value_sol=total_value,
                last_updated=datetime.utcnow(),
            )

            self._state.balance = balance

            logger.info(
                "wallet_balance_refreshed",
                sol_balance=round(sol_ui, 4),
                token_count=len(token_balances),
                total_value_sol=round(total_value, 4),
            )

            # Check minimum balance
            if not balance.has_sufficient_sol:
                logger.warning(
                    "wallet_low_sol_balance",
                    balance=sol_ui,
                    minimum=self._settings.min_sol_balance,
                )

            return balance

    async def _fetch_token_balances(self, pubkey: Pubkey) -> list[TokenBalance]:
        """Fetch all SPL token balances for wallet."""
        token_balances: list[TokenBalance] = []

        if not self._client:
            return token_balances

        try:
            # Get all token accounts
            response = await self._client.get_token_accounts_by_owner_json_parsed(
                pubkey,
                opts={"programId": TOKEN_PROGRAM_ID},
            )

            for account in response.value:
                try:
                    parsed = account.account.data.parsed
                    info = parsed["info"]
                    token_amount = info["tokenAmount"]

                    # Skip zero balances
                    ui_amount = float(token_amount.get("uiAmount") or 0)
                    if ui_amount == 0:
                        continue

                    token_balances.append(
                        TokenBalance(
                            mint_address=info["mint"],
                            symbol=None,  # Would need metadata lookup
                            amount=float(token_amount["amount"]),
                            decimals=token_amount["decimals"],
                            ui_amount=ui_amount,
                            estimated_value_sol=None,  # Would need price lookup
                        )
                    )
                except (KeyError, TypeError) as e:
                    logger.warning("token_balance_parse_error", error=str(e))
                    continue

        except Exception as e:
            logger.error("fetch_token_balances_failed", error=str(e))

        return token_balances

    async def _enter_safe_mode(
        self,
        reason: SafeModeReason,
        error_message: str,
    ) -> None:
        """Enter safe mode - block all trades."""
        if self._settings.auto_safe_mode_on_error:
            self._state.safe_mode = True
            self._state.safe_mode_reason = reason
            self._state.safe_mode_since = datetime.utcnow()
            self._state.error_message = error_message
            self._state.status = WalletConnectionStatus.ERROR

            logger.critical(
                "wallet_safe_mode_activated",
                reason=reason.value,
                error=error_message,
            )

    async def exit_safe_mode(self) -> bool:
        """Attempt to exit safe mode by re-validating connectivity."""
        if not self._state.safe_mode:
            return True

        logger.info("wallet_attempting_safe_mode_exit")

        try:
            await self._validate_connectivity()
            signing_result = await self.validate_signing()

            if signing_result.success:
                self._state.safe_mode = False
                self._state.safe_mode_reason = None
                self._state.safe_mode_since = None
                self._state.error_message = None
                self._state.status = WalletConnectionStatus.CONNECTED
                self._state.last_validated = datetime.utcnow()

                logger.info("wallet_safe_mode_exited")
                return True
            else:
                logger.warning(
                    "wallet_safe_mode_exit_failed",
                    error=signing_result.error,
                )
                return False

        except Exception as e:
            logger.error("wallet_safe_mode_exit_error", error=str(e))
            return False

    def set_manual_safe_mode(self, enabled: bool) -> None:
        """Manually enable/disable safe mode."""
        if enabled:
            self._state.safe_mode = True
            self._state.safe_mode_reason = SafeModeReason.MANUAL
            self._state.safe_mode_since = datetime.utcnow()
            logger.info("wallet_manual_safe_mode_enabled")
        else:
            self._state.safe_mode = False
            self._state.safe_mode_reason = None
            self._state.safe_mode_since = None
            logger.info("wallet_manual_safe_mode_disabled")

    @property
    def state(self) -> WalletState:
        """Get current wallet state."""
        return self._state

    @property
    def is_ready_for_trading(self) -> bool:
        """Check if wallet is ready to execute trades."""
        return (
            self._initialized
            and not self._state.safe_mode
            and self._state.status == WalletConnectionStatus.CONNECTED
            and self._state.balance is not None
            and self._state.balance.has_sufficient_sol
        )

    @property
    def keypair(self) -> Keypair | None:
        """Get keypair for signing (use with caution!).

        Returns None if safe mode is active to prevent trades.
        """
        if self._state.safe_mode:
            logger.warning("keypair_access_blocked_safe_mode")
            return None
        return self._keypair

    @property
    def public_key(self) -> Pubkey | None:
        """Get wallet public key."""
        return self._keypair.pubkey() if self._keypair else None

    async def close(self) -> None:
        """Close RPC client connection."""
        if self._client:
            await self._client.close()
            self._client = None
            self._state.status = WalletConnectionStatus.DISCONNECTED
            logger.info("wallet_client_closed")


# Singleton instance
_wallet_client: WalletClient | None = None


async def get_wallet_client() -> WalletClient:
    """Get or create wallet client singleton."""
    global _wallet_client
    if _wallet_client is None:
        _wallet_client = WalletClient()
        await _wallet_client.initialize()
    return _wallet_client
