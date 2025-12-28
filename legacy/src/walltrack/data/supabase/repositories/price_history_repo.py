"""Repository for price history queries.

Story 10.5-7: Price History Collection.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from walltrack.models.position import Position

logger = structlog.get_logger(__name__)


class PricePoint(BaseModel):
    """Single price point in history."""

    price: Decimal
    source: str
    recorded_at: datetime


class OHLCCandle(BaseModel):
    """OHLC candle for compressed history."""

    period_start: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    sample_count: int = 1


class PositionPriceMetrics(BaseModel):
    """Price metrics for a position."""

    position_id: UUID
    peak_price: Decimal
    peak_at: datetime
    current_price: Decimal | None = None
    last_update: datetime | None = None
    max_drawdown_pct: Decimal = Field(default=Decimal("0"))
    current_drawdown_pct: Decimal = Field(default=Decimal("0"))
    unrealized_pnl_at_peak: Decimal | None = None


class PriceHistoryRepository:
    """Repository for price history queries and storage."""

    async def store_price(
        self,
        position_id: UUID | str,
        token_address: str,
        price: Decimal,
        source: str,
        timestamp: datetime,
    ) -> None:
        """
        Store a price point in history.

        Args:
            position_id: Position UUID
            token_address: Token mint address
            price: Price in USD
            source: Price source name
            timestamp: When price was recorded
        """
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        await client.table("price_history").insert(
            {
                "position_id": str(position_id),
                "token_address": token_address,
                "price": str(price),
                "source": source,
                "recorded_at": timestamp.isoformat(),
            }
        ).execute()

    async def update_metrics(
        self,
        position: Position,
        current_price: Decimal,
        timestamp: datetime,
    ) -> PositionPriceMetrics:
        """
        Update position price metrics.

        Creates initial metrics if none exist.

        Args:
            position: Position model
            current_price: Current price
            timestamp: Current time

        Returns:
            Updated metrics
        """
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        # Get existing metrics
        result = (
            await client.table("position_price_metrics")
            .select("*")
            .eq("position_id", str(position.id))
            .maybe_single()
            .execute()
        )

        if result.data:
            return await self._update_existing_metrics(
                client,
                position,
                current_price,
                timestamp,
                result.data,
            )
        else:
            return await self._create_initial_metrics(
                client,
                position,
                current_price,
                timestamp,
            )

    async def _update_existing_metrics(
        self,
        client,
        position: Position,
        current_price: Decimal,
        timestamp: datetime,
        existing: dict,
    ) -> PositionPriceMetrics:
        """Update existing metrics record."""
        peak_price = Decimal(str(existing["peak_price"]))

        if current_price > peak_price:
            # New peak
            unrealized_pnl = (
                (current_price - position.entry_price)
                * position.entry_amount_tokens
            )

            update_data = {
                "peak_price": str(current_price),
                "peak_at": timestamp.isoformat(),
                "current_price": str(current_price),
                "last_update": timestamp.isoformat(),
                "current_drawdown_pct": "0",
                "unrealized_pnl_at_peak": str(unrealized_pnl),
                "updated_at": timestamp.isoformat(),
            }

            await (
                client.table("position_price_metrics")
                .update(update_data)
                .eq("position_id", str(position.id))
                .execute()
            )

            return PositionPriceMetrics(
                position_id=position.id,
                peak_price=current_price,
                peak_at=timestamp,
                current_price=current_price,
                last_update=timestamp,
                max_drawdown_pct=Decimal(str(existing["max_drawdown_pct"])),
                current_drawdown_pct=Decimal("0"),
                unrealized_pnl_at_peak=unrealized_pnl,
            )
        else:
            # Calculate drawdown
            drawdown_pct = ((peak_price - current_price) / peak_price) * 100
            max_drawdown = max(
                Decimal(str(existing["max_drawdown_pct"])),
                drawdown_pct,
            )

            update_data = {
                "current_price": str(current_price),
                "last_update": timestamp.isoformat(),
                "current_drawdown_pct": str(drawdown_pct),
                "max_drawdown_pct": str(max_drawdown),
                "updated_at": timestamp.isoformat(),
            }

            await (
                client.table("position_price_metrics")
                .update(update_data)
                .eq("position_id", str(position.id))
                .execute()
            )

            return PositionPriceMetrics(
                position_id=position.id,
                peak_price=peak_price,
                peak_at=datetime.fromisoformat(
                    existing["peak_at"].replace("Z", "+00:00")
                ),
                current_price=current_price,
                last_update=timestamp,
                max_drawdown_pct=max_drawdown,
                current_drawdown_pct=drawdown_pct,
                unrealized_pnl_at_peak=(
                    Decimal(str(existing["unrealized_pnl_at_peak"]))
                    if existing.get("unrealized_pnl_at_peak")
                    else None
                ),
            )

    async def _create_initial_metrics(
        self,
        client,
        position: Position,
        current_price: Decimal,
        timestamp: datetime,
    ) -> PositionPriceMetrics:
        """Create initial metrics for new position."""
        await client.table("position_price_metrics").insert(
            {
                "position_id": str(position.id),
                "peak_price": str(current_price),
                "peak_at": timestamp.isoformat(),
                "current_price": str(current_price),
                "last_update": timestamp.isoformat(),
                "max_drawdown_pct": "0",
                "current_drawdown_pct": "0",
            }
        ).execute()

        return PositionPriceMetrics(
            position_id=position.id,
            peak_price=current_price,
            peak_at=timestamp,
            current_price=current_price,
            last_update=timestamp,
            max_drawdown_pct=Decimal("0"),
            current_drawdown_pct=Decimal("0"),
        )

    async def get_history(
        self,
        position_id: UUID | str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[PricePoint]:
        """
        Get price history for a position.

        Args:
            position_id: Position UUID
            start: Start time (inclusive)
            end: End time (inclusive)
            limit: Max records to return

        Returns:
            List of price points, newest first
        """
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        query = (
            client.table("price_history")
            .select("price, source, recorded_at")
            .eq("position_id", str(position_id))
        )

        if start:
            query = query.gte("recorded_at", start.isoformat())
        if end:
            query = query.lte("recorded_at", end.isoformat())

        result = await query.order("recorded_at", desc=True).limit(limit).execute()

        return [
            PricePoint(
                price=Decimal(str(row["price"])),
                source=row["source"],
                recorded_at=datetime.fromisoformat(
                    row["recorded_at"].replace("Z", "+00:00")
                ),
            )
            for row in result.data
        ]

    async def get_compressed_history(
        self,
        position_id: UUID | str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[OHLCCandle]:
        """
        Get compressed OHLC history for a position.

        Args:
            position_id: Position UUID
            start: Start time (inclusive)
            end: End time (inclusive)
            limit: Max records to return

        Returns:
            List of OHLC candles, newest first
        """
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        query = (
            client.table("price_history_compressed")
            .select("*")
            .eq("position_id", str(position_id))
        )

        if start:
            query = query.gte("period_start", start.isoformat())
        if end:
            query = query.lte("period_start", end.isoformat())

        result = await query.order("period_start", desc=True).limit(limit).execute()

        return [
            OHLCCandle(
                period_start=datetime.fromisoformat(
                    row["period_start"].replace("Z", "+00:00")
                ),
                open_price=Decimal(str(row["open_price"])),
                high_price=Decimal(str(row["high_price"])),
                low_price=Decimal(str(row["low_price"])),
                close_price=Decimal(str(row["close_price"])),
                sample_count=row["sample_count"],
            )
            for row in result.data
        ]

    async def get_metrics(
        self,
        position_id: UUID | str,
    ) -> PositionPriceMetrics | None:
        """
        Get price metrics for a position.

        Args:
            position_id: Position UUID

        Returns:
            Metrics or None if not found
        """
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        result = (
            await client.table("position_price_metrics")
            .select("*")
            .eq("position_id", str(position_id))
            .maybe_single()
            .execute()
        )

        if not result.data:
            return None

        row = result.data
        return PositionPriceMetrics(
            position_id=UUID(row["position_id"]),
            peak_price=Decimal(str(row["peak_price"])),
            peak_at=datetime.fromisoformat(row["peak_at"].replace("Z", "+00:00")),
            current_price=(
                Decimal(str(row["current_price"]))
                if row.get("current_price")
                else None
            ),
            last_update=(
                datetime.fromisoformat(row["last_update"].replace("Z", "+00:00"))
                if row.get("last_update")
                else None
            ),
            max_drawdown_pct=Decimal(str(row["max_drawdown_pct"])),
            current_drawdown_pct=Decimal(str(row["current_drawdown_pct"])),
            unrealized_pnl_at_peak=(
                Decimal(str(row["unrealized_pnl_at_peak"]))
                if row.get("unrealized_pnl_at_peak")
                else None
            ),
        )

    async def get_latest_price(
        self,
        position_id: UUID | str,
    ) -> PricePoint | None:
        """
        Get most recent price for a position.

        Args:
            position_id: Position UUID

        Returns:
            Latest price point or None
        """
        history = await self.get_history(position_id, limit=1)
        return history[0] if history else None

    async def delete_history(
        self,
        position_id: UUID | str,
        keep_compressed: bool = True,
    ) -> int:
        """
        Delete price history for a position.

        Args:
            position_id: Position UUID
            keep_compressed: Keep OHLC compressed data

        Returns:
            Number of records deleted
        """
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        # Delete raw history
        result = (
            await client.table("price_history")
            .delete()
            .eq("position_id", str(position_id))
            .execute()
        )

        deleted = len(result.data) if result.data else 0

        if not keep_compressed:
            # Also delete compressed
            await (
                client.table("price_history_compressed")
                .delete()
                .eq("position_id", str(position_id))
                .execute()
            )

            # Delete metrics
            await (
                client.table("position_price_metrics")
                .delete()
                .eq("position_id", str(position_id))
                .execute()
            )

        logger.debug(
            "price_history_deleted",
            position_id=str(position_id),
            records=deleted,
        )
        return deleted


# Singleton
_price_history_repo: PriceHistoryRepository | None = None


async def get_price_history_repository() -> PriceHistoryRepository:
    """Get or create price history repository singleton."""
    global _price_history_repo

    if _price_history_repo is None:
        _price_history_repo = PriceHistoryRepository()

    return _price_history_repo


def reset_price_history_repository() -> None:
    """Reset the singleton (for testing)."""
    global _price_history_repo
    _price_history_repo = None
