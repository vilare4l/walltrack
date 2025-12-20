"""Repository for signal logging and queries."""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from supabase import AsyncClient

from walltrack.constants.signal_log import MAX_QUERY_RESULTS
from walltrack.models.signal_log import (
    SignalLogEntry,
    SignalLogFilter,
    SignalLogSummary,
    SignalStatus,
)

logger = structlog.get_logger(__name__)


class SignalRepository:
    """Repository for signal logging and queries."""

    def __init__(self, client: AsyncClient):
        """Initialize repository with Supabase client.

        Args:
            client: Async Supabase client
        """
        self.client = client

    async def save(self, signal: SignalLogEntry) -> str:
        """Save signal to database.

        Args:
            signal: Signal entry to save

        Returns:
            Generated UUID for the signal

        Raises:
            Exception: If save fails
        """
        data = {
            "tx_signature": signal.tx_signature,
            "wallet_address": signal.wallet_address,
            "token_address": signal.token_address,
            "direction": signal.direction,
            "amount_token": signal.amount_token,
            "amount_sol": signal.amount_sol,
            "slot": signal.slot,
            "final_score": signal.final_score,
            "wallet_score": signal.wallet_score,
            "cluster_score": signal.cluster_score,
            "token_score": signal.token_score,
            "context_score": signal.context_score,
            "status": signal.status.value,
            "eligibility_status": signal.eligibility_status,
            "conviction_tier": signal.conviction_tier,
            "filter_status": signal.filter_status,
            "filter_reason": signal.filter_reason,
            "timestamp": signal.timestamp.isoformat(),
            "received_at": signal.received_at.isoformat(),
            "processing_time_ms": signal.processing_time_ms,
            "raw_factors": signal.raw_factors,
        }

        result = await self.client.table("signals").insert(data).execute()

        if result.data:
            signal_id = result.data[0]["id"]
            logger.debug(
                "signal_saved",
                signal_id=signal_id,
                tx=signal.tx_signature[:8] + "...",
                status=signal.status.value,
            )
            return signal_id

        raise Exception("Failed to save signal")

    async def save_batch(self, signals: list[SignalLogEntry]) -> list[str]:
        """Save multiple signals in a batch.

        Args:
            signals: List of signals to save

        Returns:
            List of generated UUIDs
        """
        if not signals:
            return []

        data = [
            {
                "tx_signature": s.tx_signature,
                "wallet_address": s.wallet_address,
                "token_address": s.token_address,
                "direction": s.direction,
                "amount_token": s.amount_token,
                "amount_sol": s.amount_sol,
                "slot": s.slot,
                "final_score": s.final_score,
                "wallet_score": s.wallet_score,
                "cluster_score": s.cluster_score,
                "token_score": s.token_score,
                "context_score": s.context_score,
                "status": s.status.value,
                "eligibility_status": s.eligibility_status,
                "conviction_tier": s.conviction_tier,
                "filter_status": s.filter_status,
                "filter_reason": s.filter_reason,
                "timestamp": s.timestamp.isoformat(),
                "received_at": s.received_at.isoformat(),
                "processing_time_ms": s.processing_time_ms,
                "raw_factors": s.raw_factors,
            }
            for s in signals
        ]

        result = await self.client.table("signals").insert(data).execute()

        if result.data:
            ids = [r["id"] for r in result.data]
            logger.debug("signal_batch_saved", count=len(ids))
            return ids
        return []

    async def get_by_signature(self, tx_signature: str) -> SignalLogEntry | None:
        """Get signal by transaction signature.

        Args:
            tx_signature: Transaction signature to look up

        Returns:
            Signal entry or None if not found
        """
        result = (
            await self.client.table("signals")
            .select("*")
            .eq("tx_signature", tx_signature)
            .single()
            .execute()
        )

        if result.data:
            return self._row_to_entry(result.data)
        return None

    async def get_by_id(self, signal_id: str) -> SignalLogEntry | None:
        """Get signal by ID.

        Args:
            signal_id: UUID of the signal

        Returns:
            Signal entry or None if not found
        """
        result = (
            await self.client.table("signals")
            .select("*")
            .eq("id", signal_id)
            .single()
            .execute()
        )

        if result.data:
            return self._row_to_entry(result.data)
        return None

    async def query(self, filter: SignalLogFilter) -> list[SignalLogEntry]:
        """Query signals with filters.

        Args:
            filter: Filter criteria for the query

        Returns:
            List of matching signals
        """
        query = self.client.table("signals").select("*")

        # Apply filters
        if filter.start_date:
            query = query.gte("timestamp", filter.start_date.isoformat())
        if filter.end_date:
            query = query.lte("timestamp", filter.end_date.isoformat())
        if filter.wallet_address:
            query = query.eq("wallet_address", filter.wallet_address)
        if filter.min_score is not None:
            query = query.gte("final_score", filter.min_score)
        if filter.max_score is not None:
            query = query.lte("final_score", filter.max_score)
        if filter.status:
            query = query.eq("status", filter.status.value)
        if filter.eligibility_status:
            query = query.eq("eligibility_status", filter.eligibility_status)

        # Sorting
        query = query.order(
            filter.sort_by,
            desc=filter.sort_desc,
        )

        # Pagination
        limit = min(filter.limit, MAX_QUERY_RESULTS)
        query = query.range(filter.offset, filter.offset + limit - 1)

        result = await query.execute()

        return [self._row_to_entry(row) for row in result.data]

    async def get_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> SignalLogSummary:
        """Get summary statistics for signals.

        Args:
            start_date: Start of period (defaults to 24h ago)
            end_date: End of period (defaults to now)

        Returns:
            Summary statistics
        """
        if not start_date:
            start_date = datetime.now(UTC) - timedelta(days=1)
        if not end_date:
            end_date = datetime.now(UTC)

        # Count total
        total_result = (
            await self.client.table("signals")
            .select("id", count="exact")
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .execute()
        )
        total = total_result.count or 0

        # Get counts by eligibility
        eligible_result = (
            await self.client.table("signals")
            .select("id", count="exact")
            .eq("eligibility_status", "trade_eligible")
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .execute()
        )

        below_result = (
            await self.client.table("signals")
            .select("id", count="exact")
            .eq("eligibility_status", "below_threshold")
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .execute()
        )

        filtered_result = (
            await self.client.table("signals")
            .select("id", count="exact")
            .eq("status", SignalStatus.FILTERED_OUT.value)
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .execute()
        )

        executed_result = (
            await self.client.table("signals")
            .select("id", count="exact")
            .eq("status", SignalStatus.EXECUTED.value)
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .execute()
        )

        # Calculate averages via RPC function
        avg_score = None
        avg_processing = None
        try:
            avg_result = await self.client.rpc(
                "get_signal_averages",
                {"start_ts": start_date.isoformat(), "end_ts": end_date.isoformat()},
            ).execute()

            if avg_result.data and len(avg_result.data) > 0:
                avg_data = avg_result.data[0]
                avg_score = avg_data.get("avg_score")
                avg_processing = avg_data.get("avg_processing_ms")
        except Exception as e:
            logger.warning("failed_to_get_averages", error=str(e))

        return SignalLogSummary(
            total_count=total,
            trade_eligible_count=eligible_result.count or 0,
            below_threshold_count=below_result.count or 0,
            filtered_count=filtered_result.count or 0,
            executed_count=executed_result.count or 0,
            avg_score=avg_score,
            avg_processing_time_ms=avg_processing,
            period_start=start_date,
            period_end=end_date,
        )

    async def link_to_trade(self, tx_signature: str, trade_id: str) -> None:
        """Link signal to executed trade.

        Args:
            tx_signature: Transaction signature of the signal
            trade_id: UUID of the executed trade
        """
        await (
            self.client.table("signals")
            .update(
                {
                    "trade_id": trade_id,
                    "status": SignalStatus.EXECUTED.value,
                }
            )
            .eq("tx_signature", tx_signature)
            .execute()
        )

        logger.info(
            "signal_linked_to_trade",
            tx=tx_signature[:8] + "...",
            trade_id=trade_id,
        )

    async def update_status(
        self,
        tx_signature: str,
        status: SignalStatus,
    ) -> None:
        """Update signal status.

        Args:
            tx_signature: Transaction signature of the signal
            status: New status to set
        """
        await (
            self.client.table("signals")
            .update({"status": status.value})
            .eq("tx_signature", tx_signature)
            .execute()
        )

        logger.debug(
            "signal_status_updated",
            tx=tx_signature[:8] + "...",
            status=status.value,
        )

    def _row_to_entry(self, row: dict[str, Any]) -> SignalLogEntry:
        """Convert database row to SignalLogEntry.

        Args:
            row: Database row as dictionary

        Returns:
            SignalLogEntry model
        """
        # Parse timestamp
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        # Parse received_at
        received_at = row.get("received_at")
        if received_at:
            if isinstance(received_at, str):
                received_at = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        else:
            received_at = datetime.now(UTC)

        return SignalLogEntry(
            id=row.get("id"),
            tx_signature=row["tx_signature"],
            wallet_address=row["wallet_address"],
            token_address=row["token_address"],
            direction=row["direction"],
            amount_token=row.get("amount_token") or 0.0,
            amount_sol=row.get("amount_sol") or 0.0,
            slot=row.get("slot"),
            final_score=row.get("final_score"),
            wallet_score=row.get("wallet_score"),
            cluster_score=row.get("cluster_score"),
            token_score=row.get("token_score"),
            context_score=row.get("context_score"),
            status=SignalStatus(row.get("status", "received")),
            eligibility_status=row.get("eligibility_status"),
            conviction_tier=row.get("conviction_tier"),
            filter_status=row.get("filter_status"),
            filter_reason=row.get("filter_reason"),
            trade_id=row.get("trade_id"),
            timestamp=timestamp,
            received_at=received_at,
            processing_time_ms=row.get("processing_time_ms") or 0.0,
            raw_factors=row.get("raw_factors") or {},
        )
