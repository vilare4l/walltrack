"""Neo4j wallet queries."""

from typing import Any

import structlog
from neo4j import AsyncSession

from walltrack.data.models.wallet import Wallet, WalletStatus

log = structlog.get_logger()


class WalletQueries:
    """Neo4j queries for wallet operations."""

    @staticmethod
    async def create_or_update_wallet(
        session: AsyncSession, wallet: Wallet
    ) -> dict[str, Any]:
        """Create or update a wallet node in Neo4j."""
        query = """
        MERGE (w:Wallet {address: $address})
        ON CREATE SET
            w.score = $score,
            w.status = $status,
            w.win_rate = $win_rate,
            w.total_pnl = $total_pnl,
            w.total_trades = $total_trades,
            w.discovered_at = datetime($discovered_at),
            w.discovery_count = $discovery_count,
            w.updated_at = datetime($updated_at)
        ON MATCH SET
            w.score = $score,
            w.status = $status,
            w.win_rate = $win_rate,
            w.total_pnl = $total_pnl,
            w.total_trades = $total_trades,
            w.discovery_count = w.discovery_count + 1,
            w.updated_at = datetime($updated_at)
        RETURN w
        """
        result = await session.run(
            query,
            address=wallet.address,
            score=wallet.score,
            status=wallet.status.value,
            win_rate=wallet.profile.win_rate,
            total_pnl=wallet.profile.total_pnl,
            total_trades=wallet.profile.total_trades,
            discovered_at=wallet.discovered_at.isoformat(),
            discovery_count=wallet.discovery_count,
            updated_at=wallet.updated_at.isoformat(),
        )
        record = await result.single()
        return dict(record["w"]) if record else {}

    @staticmethod
    async def get_wallet(session: AsyncSession, address: str) -> dict[str, Any] | None:
        """Get a wallet node by address."""
        query = """
        MATCH (w:Wallet {address: $address})
        RETURN w
        """
        result = await session.run(query, address=address)
        record = await result.single()
        return dict(record["w"]) if record else None

    @staticmethod
    async def get_active_wallets(
        session: AsyncSession, min_score: float = 0.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get active wallets with minimum score."""
        query = """
        MATCH (w:Wallet)
        WHERE w.status = 'active' AND w.score >= $min_score
        RETURN w
        ORDER BY w.score DESC
        LIMIT $limit
        """
        result = await session.run(query, min_score=min_score, limit=limit)
        records = await result.data()
        return [dict(r["w"]) for r in records]

    @staticmethod
    async def increment_discovery_count(
        session: AsyncSession, address: str
    ) -> int:
        """Increment discovery count for existing wallet."""
        query = """
        MATCH (w:Wallet {address: $address})
        SET w.discovery_count = COALESCE(w.discovery_count, 0) + 1,
            w.updated_at = datetime()
        RETURN w.discovery_count as count
        """
        result = await session.run(query, address=address)
        record = await result.single()
        return record["count"] if record else 0

    @staticmethod
    async def update_wallet_status(
        session: AsyncSession, address: str, status: WalletStatus
    ) -> bool:
        """Update wallet status."""
        query = """
        MATCH (w:Wallet {address: $address})
        SET w.status = $status,
            w.updated_at = datetime()
        RETURN w
        """
        result = await session.run(query, address=address, status=status.value)
        record = await result.single()
        return record is not None

    @staticmethod
    async def get_wallets_by_status(
        session: AsyncSession, status: WalletStatus, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get wallets by status."""
        query = """
        MATCH (w:Wallet {status: $status})
        RETURN w
        ORDER BY w.updated_at DESC
        LIMIT $limit
        """
        result = await session.run(query, status=status.value, limit=limit)
        records = await result.data()
        return [dict(r["w"]) for r in records]

    @staticmethod
    async def delete_wallet(session: AsyncSession, address: str) -> bool:
        """Delete a wallet node."""
        query = """
        MATCH (w:Wallet {address: $address})
        DELETE w
        RETURN COUNT(*) as deleted
        """
        result = await session.run(query, address=address)
        record = await result.single()
        return record["deleted"] > 0 if record else False
