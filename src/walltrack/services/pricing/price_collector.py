"""Collects and stores price history for positions.

Story 10.5-7: Price History Collection.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import structlog

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.position_repo import PositionRepository
    from walltrack.models.position import Position
    from walltrack.services.pricing.price_oracle import PriceOracle

logger = structlog.get_logger(__name__)


class PriceCollector:
    """
    Collects price data for active positions.

    Runs periodically to store price history and update metrics.
    """

    def __init__(
        self,
        price_oracle: PriceOracle,
        position_repo: PositionRepository,
        price_history_repo: Optional[PriceHistoryRepository] = None,
        collection_interval: float = 5.0,
    ):
        """
        Initialize PriceCollector.

        Args:
            price_oracle: Multi-source price oracle
            position_repo: Position repository
            price_history_repo: Price history repository (optional)
            collection_interval: Seconds between collections
        """
        self.oracle = price_oracle
        self.position_repo = position_repo
        self.history_repo = price_history_repo
        self.interval = collection_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._collection_count = 0

    async def start(self) -> None:
        """Start the price collector."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._collection_loop())
        logger.info("price_collector_started", interval=self.interval)

    async def stop(self) -> None:
        """Stop the price collector."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(
            "price_collector_stopped",
            collections=self._collection_count,
        )

    @property
    def is_running(self) -> bool:
        """Check if collector is running."""
        return self._running

    async def _collection_loop(self) -> None:
        """Main collection loop."""
        while self._running:
            try:
                await self._collect_prices()
                self._collection_count += 1
            except Exception as e:
                logger.error("price_collection_error", error=str(e))

            await asyncio.sleep(self.interval)

    async def _collect_prices(self) -> int:
        """
        Collect prices for all active positions.

        Returns:
            Number of positions with prices collected
        """
        # Get open positions
        positions = await self.position_repo.list_open()

        if not positions:
            return 0

        # Group by token for batch fetching
        token_positions: dict[str, list[Position]] = {}
        for pos in positions:
            if pos.token_address not in token_positions:
                token_positions[pos.token_address] = []
            token_positions[pos.token_address].append(pos)

        # Batch fetch prices
        token_addresses = list(token_positions.keys())
        price_results = await self.oracle.get_prices_batch(token_addresses)

        # Store prices and update metrics
        now = datetime.now(UTC)
        collected_count = 0

        for token_address, positions_for_token in token_positions.items():
            result = price_results.get(token_address)

            if result and result.success and result.price:
                source = (
                    result.source.value
                    if hasattr(result.source, "value")
                    else str(result.source)
                )
                for position in positions_for_token:
                    await self._store_price(
                        position,
                        result.price,
                        source,
                        now,
                    )
                    await self._update_metrics(
                        position,
                        result.price,
                        now,
                    )
                    collected_count += 1

        logger.debug(
            "prices_collected",
            positions=collected_count,
            tokens=len(token_addresses),
        )

        return collected_count

    async def collect_once(self) -> int:
        """Run a single collection cycle (for testing/manual trigger)."""
        return await self._collect_prices()

    async def _store_price(
        self,
        position: Position,
        price: Decimal,
        source: str,
        timestamp: datetime,
    ) -> None:
        """Store price point in history."""
        if self.history_repo:
            await self.history_repo.store_price(
                position_id=position.id,
                token_address=position.token_address,
                price=price,
                source=source,
                timestamp=timestamp,
            )
        else:
            # Direct DB access if no repository injected
            from walltrack.data.supabase.client import get_supabase_client

            client = await get_supabase_client()

            await client.table("price_history").insert(
                {
                    "position_id": str(position.id),
                    "token_address": position.token_address,
                    "price": str(price),
                    "source": source,
                    "recorded_at": timestamp.isoformat(),
                }
            ).execute()

    async def _update_metrics(
        self,
        position: Position,
        current_price: Decimal,
        timestamp: datetime,
    ) -> None:
        """Update position price metrics (peak, drawdown)."""
        if self.history_repo:
            await self.history_repo.update_metrics(
                position=position,
                current_price=current_price,
                timestamp=timestamp,
            )
        else:
            # Direct DB access
            from walltrack.data.supabase.client import get_supabase_client

            client = await get_supabase_client()

            # Get current metrics
            result = (
                await client.table("position_price_metrics")
                .select("*")
                .eq("position_id", str(position.id))
                .maybe_single()
                .execute()
            )

            if result.data:
                await self._update_existing_metrics(
                    client,
                    position,
                    current_price,
                    timestamp,
                    result.data,
                )
            else:
                await self._create_initial_metrics(
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
        metrics: dict,
    ) -> None:
        """Update existing metrics record."""
        peak_price = Decimal(str(metrics["peak_price"]))

        # Update peak if new high
        if current_price > peak_price:
            peak_price = current_price
            unrealized_pnl = (
                (current_price - position.entry_price)
                * position.entry_amount_tokens
            )

            await (
                client.table("position_price_metrics")
                .update(
                    {
                        "peak_price": str(peak_price),
                        "peak_at": timestamp.isoformat(),
                        "current_price": str(current_price),
                        "last_update": timestamp.isoformat(),
                        "current_drawdown_pct": "0",
                        "unrealized_pnl_at_peak": str(unrealized_pnl),
                        "updated_at": timestamp.isoformat(),
                    }
                )
                .eq("position_id", str(position.id))
                .execute()
            )
        else:
            # Calculate drawdown from peak
            drawdown_pct = ((peak_price - current_price) / peak_price) * 100
            max_drawdown = max(
                Decimal(str(metrics["max_drawdown_pct"])),
                drawdown_pct,
            )

            await (
                client.table("position_price_metrics")
                .update(
                    {
                        "current_price": str(current_price),
                        "last_update": timestamp.isoformat(),
                        "current_drawdown_pct": str(drawdown_pct),
                        "max_drawdown_pct": str(max_drawdown),
                        "updated_at": timestamp.isoformat(),
                    }
                )
                .eq("position_id", str(position.id))
                .execute()
            )

    async def _create_initial_metrics(
        self,
        client,
        position: Position,
        current_price: Decimal,
        timestamp: datetime,
    ) -> None:
        """Create initial metrics record for position."""
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


class PriceHistoryCompressor:
    """Compresses old price history to OHLC format."""

    def __init__(self, compression_threshold_hours: int = 24):
        """
        Initialize compressor.

        Args:
            compression_threshold_hours: Compress data older than this
        """
        self.threshold_hours = compression_threshold_hours

    async def compress_old_data(
        self,
        older_than_hours: Optional[int] = None,
    ) -> int:
        """
        Compress price history older than threshold.

        Aggregates 5-second data into 1-minute OHLC candles.

        Args:
            older_than_hours: Override threshold (uses default if None)

        Returns:
            Number of records compressed
        """
        from walltrack.data.supabase.client import get_supabase_client

        hours = older_than_hours or self.threshold_hours
        client = await get_supabase_client()
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        # Get distinct position_id/minute combinations to compress
        # Using raw SQL via RPC for aggregation
        try:
            result = await client.rpc(
                "compress_price_history",
                {"cutoff_time": cutoff.isoformat()},
            ).execute()

            compressed_count = result.data if result.data else 0
        except Exception as e:
            # If RPC not available, do client-side compression
            logger.warning(
                "compression_rpc_unavailable",
                error=str(e),
            )
            compressed_count = await self._compress_client_side(
                client,
                cutoff,
            )

        logger.info(
            "price_history_compressed",
            count=compressed_count,
            threshold_hours=hours,
        )
        return compressed_count

    async def _compress_client_side(self, client, cutoff: datetime) -> int:
        """
        Fallback client-side compression.

        Less efficient but works without server-side function.
        """
        # Get old records grouped by position and minute
        result = (
            await client.table("price_history")
            .select("position_id, token_address, price, recorded_at")
            .lt("recorded_at", cutoff.isoformat())
            .order("recorded_at")
            .limit(10000)
            .execute()
        )

        if not result.data:
            return 0

        # Group by position_id and minute
        grouped: dict[tuple, list] = {}
        for row in result.data:
            position_id = row["position_id"]
            recorded_at = datetime.fromisoformat(
                row["recorded_at"].replace("Z", "+00:00")
            )
            minute_key = recorded_at.replace(second=0, microsecond=0)
            key = (position_id, row["token_address"], minute_key)

            if key not in grouped:
                grouped[key] = []
            grouped[key].append(Decimal(str(row["price"])))

        # Insert compressed records
        compressed_count = 0
        for (position_id, token_address, period_start), prices in grouped.items():
            if len(prices) < 2:
                continue

            await client.table("price_history_compressed").upsert(
                {
                    "position_id": position_id,
                    "token_address": token_address,
                    "period_start": period_start.isoformat(),
                    "open_price": str(prices[0]),
                    "high_price": str(max(prices)),
                    "low_price": str(min(prices)),
                    "close_price": str(prices[-1]),
                    "sample_count": len(prices),
                },
                on_conflict="position_id,period_start",
            ).execute()

            compressed_count += len(prices)

        return compressed_count


class PriceHistoryCleanup:
    """Cleans up old price history for closed positions."""

    def __init__(self, retention_days: int = 7):
        """
        Initialize cleanup.

        Args:
            retention_days: Keep detailed history this long after close
        """
        self.retention_days = retention_days

    async def cleanup_closed_positions(
        self,
        closed_days_ago: Optional[int] = None,
    ) -> int:
        """
        Delete detailed history for long-closed positions.

        Keeps compressed OHLC data indefinitely.

        Args:
            closed_days_ago: Override retention period

        Returns:
            Number of positions cleaned up
        """
        from walltrack.data.supabase.client import get_supabase_client

        days = closed_days_ago or self.retention_days
        client = await get_supabase_client()
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Get positions closed before cutoff
        result = (
            await client.table("positions")
            .select("id")
            .eq("status", "closed")
            .lt("closed_at", cutoff.isoformat())
            .execute()
        )

        deleted_count = 0
        for row in result.data:
            position_id = row["id"]

            # Delete from price_history (keep compressed)
            await (
                client.table("price_history")
                .delete()
                .eq("position_id", position_id)
                .execute()
            )

            deleted_count += 1

        logger.info(
            "price_history_cleaned",
            positions=deleted_count,
            retention_days=days,
        )
        return deleted_count


# Import at module level for type hints
from walltrack.data.supabase.repositories.price_history_repo import (
    PriceHistoryRepository,
)
