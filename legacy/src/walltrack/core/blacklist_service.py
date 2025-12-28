"""Wallet blacklist management service."""

from datetime import datetime

import structlog

from walltrack.data.models.wallet import Wallet, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

log = structlog.get_logger()


class BlacklistService:
    """Service for managing wallet blacklisting."""

    def __init__(self, wallet_repo: WalletRepository) -> None:
        self.wallet_repo = wallet_repo

    async def add_to_blacklist(
        self,
        address: str,
        reason: str,
        operator_id: str | None = None,
    ) -> Wallet:
        """
        Add a wallet to the blacklist.

        Args:
            address: Wallet address to blacklist
            reason: Reason for blacklisting
            operator_id: Optional ID of operator who blacklisted

        Returns:
            Updated Wallet

        Raises:
            ValueError: If wallet not found
        """
        wallet = await self.wallet_repo.get_by_address(address)
        if not wallet:
            raise ValueError(f"Wallet {address} not found")

        if wallet.status == WalletStatus.BLACKLISTED:
            log.info("wallet_already_blacklisted", address=address)
            return wallet

        # Store previous status for potential restoration
        previous_status = wallet.status.value

        wallet.status = WalletStatus.BLACKLISTED
        wallet.blacklisted_at = datetime.utcnow()
        wallet.blacklist_reason = reason

        await self.wallet_repo.update(wallet)

        log.warning(
            "wallet_blacklisted",
            address=address,
            reason=reason,
            previous_status=previous_status,
            operator=operator_id,
        )

        return wallet

    async def remove_from_blacklist(
        self,
        address: str,
        operator_id: str | None = None,
    ) -> Wallet:
        """
        Remove a wallet from the blacklist.

        Args:
            address: Wallet address to unblacklist
            operator_id: Optional ID of operator who removed blacklist

        Returns:
            Updated Wallet

        Raises:
            ValueError: If wallet not found or not blacklisted
        """
        wallet = await self.wallet_repo.get_by_address(address)
        if not wallet:
            raise ValueError(f"Wallet {address} not found")

        if wallet.status != WalletStatus.BLACKLISTED:
            raise ValueError(f"Wallet {address} is not blacklisted")

        blacklist_reason = wallet.blacklist_reason
        blacklisted_at = wallet.blacklisted_at

        # Restore to active status (will need re-evaluation)
        wallet.status = WalletStatus.ACTIVE
        wallet.blacklisted_at = None
        wallet.blacklist_reason = None

        await self.wallet_repo.update(wallet)

        duration = None
        if blacklisted_at:
            duration = (datetime.utcnow() - blacklisted_at).total_seconds()

        log.info(
            "wallet_unblacklisted",
            address=address,
            previous_reason=blacklist_reason,
            blacklisted_duration=duration,
            operator=operator_id,
        )

        return wallet

    async def is_blacklisted(self, address: str) -> bool:
        """
        Check if a wallet is blacklisted.

        Args:
            address: Wallet address to check

        Returns:
            True if blacklisted, False otherwise
        """
        wallet = await self.wallet_repo.get_by_address(address)
        return wallet is not None and wallet.status == WalletStatus.BLACKLISTED

    async def get_blacklisted_wallets(
        self,
        limit: int = 100,
        offset: int = 0,  # noqa: ARG002 - kept for future pagination support
    ) -> list[Wallet]:
        """Get all blacklisted wallets."""
        return await self.wallet_repo.get_by_status(
            WalletStatus.BLACKLISTED,
            limit=limit,
        )

    async def check_and_block_signal(
        self,
        wallet_address: str,
    ) -> tuple[bool, str | None]:
        """
        Check if signal should be blocked due to blacklist.

        Args:
            wallet_address: Source wallet of the signal

        Returns:
            Tuple of (is_blocked, block_reason)
        """
        if await self.is_blacklisted(wallet_address):
            return True, "blocked_blacklisted"
        return False, None
