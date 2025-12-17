"""Repository for wallet data in Supabase."""

from datetime import datetime
from typing import Any

import structlog

from walltrack.data.models.wallet import (
    Wallet,
    WalletProfile,
    WalletStatus,
)
from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger()


class WalletRepository:
    """Repository for wallet CRUD operations."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "wallets"

    async def get_by_address(self, address: str) -> Wallet | None:
        """Get wallet by address."""
        try:
            response = await (
                self.client.table(self.table)
                .select("*")
                .eq("address", address)
                .maybe_single()
                .execute()
            )
            if response.data:
                return self._row_to_wallet(response.data)
            return None
        except Exception as e:
            log.error("wallet_get_error", address=address, error=str(e))
            return None

    async def exists(self, address: str) -> bool:
        """Check if wallet exists."""
        response = await (
            self.client.table(self.table)
            .select("address")
            .eq("address", address)
            .execute()
        )
        return len(response.data) > 0

    async def create(self, wallet: Wallet) -> Wallet:
        """Create a new wallet."""
        data = self._wallet_to_row(wallet)
        response = await self.client.table(self.table).insert(data).execute()
        log.info("wallet_created", address=wallet.address)
        return self._row_to_wallet(response.data[0])

    async def update(self, wallet: Wallet) -> Wallet:
        """Update an existing wallet."""
        data = self._wallet_to_row(wallet)
        data["updated_at"] = datetime.utcnow().isoformat()
        response = await (
            self.client.table(self.table)
            .update(data)
            .eq("address", wallet.address)
            .execute()
        )
        log.info("wallet_updated", address=wallet.address)
        return self._row_to_wallet(response.data[0])

    async def upsert(self, wallet: Wallet) -> tuple[Wallet, bool]:
        """Create or update wallet. Returns (wallet, is_new)."""
        existing = await self.exists(wallet.address)
        if existing:
            # Increment discovery count for existing wallet
            await self._increment_discovery(wallet.address, wallet.discovery_tokens)
            updated = await self.get_by_address(wallet.address)
            return updated if updated else wallet, False
        else:
            created = await self.create(wallet)
            return created, True

    async def _increment_discovery(
        self, address: str, new_tokens: list[str]
    ) -> None:
        """Increment discovery count and add new tokens."""
        try:
            await self.client.client.rpc(
                "increment_wallet_discovery",
                {"wallet_address": address, "new_tokens": new_tokens},
            ).execute()
        except Exception as e:
            # Fallback: manual update if RPC doesn't exist
            log.warning("rpc_fallback", address=address, error=str(e))
            existing = await self.get_by_address(address)
            if existing:
                existing.discovery_count += 1
                existing.discovery_tokens = list(
                    set(existing.discovery_tokens + new_tokens)
                )
                await self.update(existing)

    async def get_active_wallets(
        self,
        min_score: float = 0.0,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallet]:
        """Get active wallets with minimum score."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("status", WalletStatus.ACTIVE.value)
            .gte("score", min_score)
            .order("score", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return [self._row_to_wallet(row) for row in response.data]

    async def get_by_status(
        self, status: WalletStatus, limit: int = 100
    ) -> list[Wallet]:
        """Get wallets by status."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("status", status.value)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_wallet(row) for row in response.data]

    async def get_unprofiled_wallets(self, limit: int = 100) -> list[Wallet]:
        """Get wallets that have never been profiled.

        Args:
            limit: Maximum number of wallets to return

        Returns:
            List of wallets with last_profiled_at = None
        """
        response = await (
            self.client.table(self.table)
            .select("*")
            .is_("last_profiled_at", "null")
            .eq("status", WalletStatus.ACTIVE.value)
            .order("discovered_at", desc=False)  # Oldest first
            .limit(limit)
            .execute()
        )
        return [self._row_to_wallet(row) for row in response.data]

    async def set_status(
        self, address: str, status: WalletStatus, reason: str | None = None
    ) -> None:
        """Update wallet status."""
        data: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if status == WalletStatus.BLACKLISTED:
            data["blacklisted_at"] = datetime.utcnow().isoformat()
            data["blacklist_reason"] = reason
        elif status == WalletStatus.DECAY_DETECTED:
            data["decay_detected_at"] = datetime.utcnow().isoformat()

        await (
            self.client.table(self.table)
            .update(data)
            .eq("address", address)
            .execute()
        )
        log.info("wallet_status_updated", address=address, status=status.value)

    async def count_by_status(self, status: WalletStatus | None = None) -> int:
        """Count wallets by status (or all if None)."""
        query = self.client.table(self.table).select("address", count="exact")
        if status:
            query = query.eq("status", status.value)
        response = await query.execute()
        return response.count or 0

    async def delete(self, address: str) -> bool:
        """Delete a wallet."""
        response = await (
            self.client.table(self.table)
            .delete()
            .eq("address", address)
            .execute()
        )
        deleted = len(response.data) > 0
        if deleted:
            log.info("wallet_deleted", address=address)
        return deleted

    def _wallet_to_row(self, wallet: Wallet) -> dict[str, Any]:
        """Convert Wallet model to database row."""
        return {
            "address": wallet.address,
            "status": wallet.status.value,
            "score": wallet.score,
            "win_rate": wallet.profile.win_rate,
            "total_pnl": wallet.profile.total_pnl,
            "avg_pnl_per_trade": wallet.profile.avg_pnl_per_trade,
            "total_trades": wallet.profile.total_trades,
            "timing_percentile": wallet.profile.timing_percentile,
            "avg_hold_time_hours": wallet.profile.avg_hold_time_hours,
            "preferred_hours": wallet.profile.preferred_hours,
            "avg_position_size_sol": wallet.profile.avg_position_size_sol,
            "discovered_at": wallet.discovered_at.isoformat(),
            "discovery_count": wallet.discovery_count,
            "discovery_tokens": wallet.discovery_tokens,
            "decay_detected_at": (
                wallet.decay_detected_at.isoformat()
                if wallet.decay_detected_at
                else None
            ),
            "consecutive_losses": wallet.consecutive_losses,
            "rolling_win_rate": wallet.rolling_win_rate,
            "blacklisted_at": (
                wallet.blacklisted_at.isoformat() if wallet.blacklisted_at else None
            ),
            "blacklist_reason": wallet.blacklist_reason,
            "last_profiled_at": (
                wallet.last_profiled_at.isoformat()
                if wallet.last_profiled_at
                else None
            ),
            "last_signal_at": (
                wallet.last_signal_at.isoformat() if wallet.last_signal_at else None
            ),
        }

    def _row_to_wallet(self, row: dict[str, Any]) -> Wallet:
        """Convert database row to Wallet model."""
        profile = WalletProfile(
            win_rate=float(row.get("win_rate", 0) or 0),
            total_pnl=float(row.get("total_pnl", 0) or 0),
            avg_pnl_per_trade=float(row.get("avg_pnl_per_trade", 0) or 0),
            total_trades=int(row.get("total_trades", 0) or 0),
            timing_percentile=float(row.get("timing_percentile", 0.5) or 0.5),
            avg_hold_time_hours=float(row.get("avg_hold_time_hours", 0) or 0),
            preferred_hours=row.get("preferred_hours") or [],
            avg_position_size_sol=float(row.get("avg_position_size_sol", 0) or 0),
        )

        discovered_at = row.get("discovered_at")
        if discovered_at:
            discovered_at = datetime.fromisoformat(discovered_at)
        else:
            discovered_at = datetime.utcnow()

        decay_detected_at = row.get("decay_detected_at")
        if decay_detected_at:
            decay_detected_at = datetime.fromisoformat(decay_detected_at)

        blacklisted_at = row.get("blacklisted_at")
        if blacklisted_at:
            blacklisted_at = datetime.fromisoformat(blacklisted_at)

        last_profiled_at = row.get("last_profiled_at")
        if last_profiled_at:
            last_profiled_at = datetime.fromisoformat(last_profiled_at)

        last_signal_at = row.get("last_signal_at")
        if last_signal_at:
            last_signal_at = datetime.fromisoformat(last_signal_at)

        updated_at_str = row.get("updated_at")
        updated_at = (
            datetime.fromisoformat(updated_at_str) if updated_at_str else datetime.utcnow()
        )

        rolling_win_rate = row.get("rolling_win_rate")
        if rolling_win_rate is not None:
            rolling_win_rate = float(rolling_win_rate)

        return Wallet(
            address=row["address"],
            status=WalletStatus(row.get("status", "active")),
            score=float(row.get("score", 0.5) or 0.5),
            profile=profile,
            discovered_at=discovered_at,
            discovery_count=int(row.get("discovery_count", 1) or 1),
            discovery_tokens=row.get("discovery_tokens") or [],
            decay_detected_at=decay_detected_at,
            consecutive_losses=int(row.get("consecutive_losses", 0) or 0),
            rolling_win_rate=rolling_win_rate,
            blacklisted_at=blacklisted_at,
            blacklist_reason=row.get("blacklist_reason"),
            last_profiled_at=last_profiled_at,
            last_signal_at=last_signal_at,
            updated_at=updated_at,
        )
