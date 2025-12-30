"""Repository for wallet database operations.

This module provides CRUD operations for the walltrack.wallets table.
Follows the repository pattern with async Supabase client.
"""

from datetime import datetime

import structlog
from httpx import HTTPStatusError
from supabase._async.client import AsyncClient

from walltrack.data.models.wallet import Wallet, WalletCreate, WalletUpdate
from walltrack.data.supabase.client import SupabaseClient, get_supabase_client

log = structlog.get_logger(__name__)


class WalletRepository:
    """Repository for wallet database operations.

    Provides CRUD operations for discovered smart money wallets in Supabase.
    Uses async Supabase client for all database interactions.

    Attributes:
        supabase_client: Optional Supabase client (for testing, creates default if None).

    Example:
        repo = WalletRepository()
        wallet = await repo.create_wallet(
            WalletCreate(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            )
        )
    """

    def __init__(self, supabase_client: SupabaseClient | None = None) -> None:
        """Initialize wallet repository.

        Args:
            supabase_client: Optional SupabaseClient wrapper (for testing).
                            If None, will use get_supabase_client() singleton.
        """
        self._supabase_client_wrapper = supabase_client
        self._client_initialized = supabase_client is not None
        log.debug("wallet_repository_initialized")

    async def _get_client(self) -> AsyncClient:
        """Get Supabase client (lazy initialization).

        Returns:
            AsyncClient instance.
        """
        if self._supabase_client_wrapper is None:
            self._supabase_client_wrapper = await get_supabase_client()
        return self._supabase_client_wrapper.client

    async def create_wallet(self, wallet: WalletCreate) -> Wallet | None:
        """Create a new wallet record in database.

        Inserts wallet into walltrack.wallets table. If wallet_address already exists,
        the PRIMARY KEY constraint will prevent duplicate and return None.

        Args:
            wallet: WalletCreate model with required fields.

        Returns:
            Created Wallet model if successful, None if duplicate (PRIMARY KEY).

        Note:
            - discovery_date auto-set to now() by database
            - created_at/updated_at auto-set by database
            - Duplicate wallet_address is silently ignored (PRIMARY KEY prevents)
        """
        client = await self._get_client()

        log.info(
            "creating_wallet",
            wallet_address=wallet.wallet_address[:8] + "...",
            token_source=wallet.token_source[:8] + "...",
        )

        try:
            response = (
                await client.table("wallets")
                .insert(wallet.model_dump(exclude_none=True))
                .execute()
            )

            if not response.data:
                log.debug(
                    "wallet_creation_skipped_duplicate",
                    wallet_address=wallet.wallet_address[:8] + "...",
                )
                return None

            wallet_data = response.data[0]
            created_wallet = Wallet(
                wallet_address=wallet_data["wallet_address"],
                discovery_date=datetime.fromisoformat(wallet_data["discovery_date"]),
                token_source=wallet_data["token_source"],
                score=wallet_data["score"],
                win_rate=wallet_data["win_rate"],
                decay_status=wallet_data["decay_status"],
                is_blacklisted=wallet_data["is_blacklisted"],
                created_at=datetime.fromisoformat(wallet_data["created_at"]),
                updated_at=datetime.fromisoformat(wallet_data["updated_at"]),
            )

            log.info(
                "wallet_created",
                wallet_address=created_wallet.wallet_address[:8] + "...",
            )

            return created_wallet

        except HTTPStatusError as e:
            # FIXED: Check HTTP status code instead of string matching
            if e.response.status_code == 409:  # Conflict - duplicate key
                log.debug(
                    "wallet_creation_duplicate_constraint",
                    wallet_address=wallet.wallet_address[:8] + "...",
                    status_code=e.response.status_code,
                )
                return None

            log.error(
                "wallet_creation_failed",
                wallet_address=wallet.wallet_address[:8] + "...",
                error=str(e),
                status_code=e.response.status_code,
            )
            raise
        except Exception as e:
            log.error(
                "wallet_creation_failed",
                wallet_address=wallet.wallet_address[:8] + "...",
                error=str(e),
            )
            # Fallback: Check error message for duplicate indicators
            error_msg = str(e).lower()
            if "duplicate" in error_msg or "unique constraint" in error_msg or "23505" in error_msg:
                log.debug("wallet_creation_duplicate_detected_via_message")
                return None
            raise

    async def get_wallet(self, wallet_address: str) -> Wallet | None:
        """Retrieve wallet by address.

        Args:
            wallet_address: Solana wallet address (PRIMARY KEY).

        Returns:
            Wallet model if found, None if not exists.
        """
        client = await self._get_client()

        log.debug("fetching_wallet", wallet_address=wallet_address[:8] + "...")

        try:
            response = (
                await client.table("wallets")
                .select("*")
                .eq("wallet_address", wallet_address)
                .execute()
            )

            if not response.data:
                log.debug("wallet_not_found", wallet_address=wallet_address[:8] + "...")
                return None

            wallet_data = response.data[0]
            return Wallet(
                wallet_address=wallet_data["wallet_address"],
                discovery_date=datetime.fromisoformat(wallet_data["discovery_date"]),
                token_source=wallet_data["token_source"],
                score=wallet_data["score"],
                win_rate=wallet_data["win_rate"],
                decay_status=wallet_data["decay_status"],
                is_blacklisted=wallet_data["is_blacklisted"],
                created_at=datetime.fromisoformat(wallet_data["created_at"]),
                updated_at=datetime.fromisoformat(wallet_data["updated_at"]),
            )

        except Exception as e:
            log.error(
                "wallet_fetch_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

    async def list_wallets(self, limit: int = 50) -> list[Wallet]:
        """List wallets with pagination.

        Returns wallets ordered by discovery_date (most recent first).

        Args:
            limit: Maximum number of wallets to return (default: 50, max: 1000).

        Returns:
            List of Wallet models (empty list if none found).

        Note:
            - Results ordered by discovery_date DESC (newest first)
            - Limit capped at 1000 to prevent memory issues
        """
        client = await self._get_client()

        # Cap limit at 1000
        limit = min(limit, 1000)

        log.debug("listing_wallets", limit=limit)

        try:
            response = (
                await client.table("wallets")
                .select("*")
                .order("discovery_date", desc=True)
                .limit(limit)
                .execute()
            )

            wallets = [
                Wallet(
                    wallet_address=w["wallet_address"],
                    discovery_date=datetime.fromisoformat(w["discovery_date"]),
                    token_source=w["token_source"],
                    score=w["score"],
                    win_rate=w["win_rate"],
                    decay_status=w["decay_status"],
                    is_blacklisted=w["is_blacklisted"],
                    created_at=datetime.fromisoformat(w["created_at"]),
                    updated_at=datetime.fromisoformat(w["updated_at"]),
                )
                for w in response.data
            ]

            log.info("wallets_listed", count=len(wallets))

            return wallets

        except Exception as e:
            log.error("wallet_list_failed", error=str(e))
            raise

    async def update_wallet(
        self, wallet_address: str, updates: WalletUpdate
    ) -> Wallet | None:
        """Update wallet fields.

        Updates only the fields provided in WalletUpdate model.
        Primary key (wallet_address) cannot be updated.

        Args:
            wallet_address: Wallet address to update (PRIMARY KEY).
            updates: WalletUpdate model with fields to update.

        Returns:
            Updated Wallet model if successful, None if wallet not found.

        Note:
            - Only non-None fields in WalletUpdate are applied
            - updated_at auto-updated by database trigger
        """
        client = await self._get_client()

        # Only include non-None fields in update
        update_data = updates.model_dump(exclude_none=True)

        if not update_data:
            # No updates provided, return current wallet
            return await self.get_wallet(wallet_address)

        log.info(
            "updating_wallet",
            wallet_address=wallet_address[:8] + "...",
            fields=list(update_data.keys()),
        )

        try:
            response = (
                await client.table("wallets")
                .update(update_data)
                .eq("wallet_address", wallet_address)
                .execute()
            )

            if not response.data:
                log.debug(
                    "wallet_update_not_found",
                    wallet_address=wallet_address[:8] + "...",
                )
                return None

            wallet_data = response.data[0]
            updated_wallet = Wallet(
                wallet_address=wallet_data["wallet_address"],
                discovery_date=datetime.fromisoformat(wallet_data["discovery_date"]),
                token_source=wallet_data["token_source"],
                score=wallet_data["score"],
                win_rate=wallet_data["win_rate"],
                decay_status=wallet_data["decay_status"],
                is_blacklisted=wallet_data["is_blacklisted"],
                created_at=datetime.fromisoformat(wallet_data["created_at"]),
                updated_at=datetime.fromisoformat(wallet_data["updated_at"]),
            )

            log.info(
                "wallet_updated",
                wallet_address=updated_wallet.wallet_address[:8] + "...",
            )

            return updated_wallet

        except Exception as e:
            log.error(
                "wallet_update_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise
