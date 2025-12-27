"""Repository for order persistence.

Story 10.5-12: Added locking methods for retry worker.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from walltrack.models.order import Order, OrderStatus, OrderType

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient

logger = structlog.get_logger()


class OrderRepository:
    """Repository for order CRUD operations."""

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def create(self, order: Order) -> Order:
        """Persist a new order."""
        data = self._serialize_order(order)

        await self._client.client.table("orders").insert(data).execute()

        logger.info(
            "order_created",
            order_id=str(order.id)[:8],
            type=order.order_type.value,
            token=order.token_address[:8],
        )
        return order

    async def update(self, order: Order) -> Order:
        """Update an existing order."""
        order.updated_at = datetime.utcnow()
        data = self._serialize_order(order)

        await (
            self._client.client.table("orders")
            .update(data)
            .eq("id", str(order.id))
            .execute()
        )

        logger.info(
            "order_updated",
            order_id=str(order.id)[:8],
            status=order.status.value,
        )
        return order

    async def get_by_id(self, order_id: UUID | str) -> Order | None:
        """Get order by ID."""
        result = (
            await self._client.client.table("orders")
            .select("*")
            .eq("id", str(order_id))
            .maybe_single()
            .execute()
        )

        if result.data:
            return self._deserialize_order(result.data)
        return None

    async def get_by_signal(self, signal_id: str) -> Order | None:
        """Get order by signal ID."""
        result = (
            await self._client.client.table("orders")
            .select("*")
            .eq("signal_id", signal_id)
            .maybe_single()
            .execute()
        )

        if result.data:
            return self._deserialize_order(result.data)
        return None

    async def get_by_position(
        self,
        position_id: UUID | str,
        order_type: OrderType | None = None,
    ) -> list[Order]:
        """Get orders for a position."""
        query = (
            self._client.client.table("orders")
            .select("*")
            .eq("position_id", str(position_id))
        )

        if order_type:
            query = query.eq("order_type", order_type.value)

        result = await query.order("created_at", desc=True).execute()

        return [self._deserialize_order(row) for row in result.data]

    async def get_pending_retries(
        self,
        limit: int = 10,
        include_pending: bool = True,
    ) -> list[Order]:
        """Get orders ready for retry with priority ordering.

        Orders are prioritized:
        1. EXIT orders before ENTRY (EXIT should complete first)
        2. Oldest first (FIFO within type)

        Only returns orders that are not locked or whose lock has expired.
        """
        now = datetime.utcnow()
        now_iso = now.isoformat()

        # Build status filter
        statuses = ["failed"]
        if include_pending:
            statuses.append("pending")

        # Query orders ready for retry, excluding locked ones
        result = (
            await self._client.client.table("orders")
            .select("*")
            .in_("status", statuses)
            .lte("next_retry_at", now_iso)
            .or_(f"locked_until.is.null,locked_until.lte.{now_iso}")
            .order("order_type", desc=True)  # exit > entry
            .order("created_at", desc=False)  # oldest first
            .limit(limit)
            .execute()
        )

        # Filter by can_retry in memory (attempt_count < max_attempts)
        orders = [self._deserialize_order(row) for row in result.data]
        return [o for o in orders if o.can_retry or o.status == OrderStatus.PENDING]

    async def acquire_lock(
        self,
        order_id: UUID | str,
        lock_by: str,
        lock_timeout_seconds: int = 60,
    ) -> bool:
        """Acquire processing lock for an order.

        Uses optimistic locking - only succeeds if order is not already locked.

        Returns:
            True if lock was acquired, False otherwise
        """
        now = datetime.utcnow()
        lock_until = now + timedelta(seconds=lock_timeout_seconds)
        now_iso = now.isoformat()

        # Update only if not locked (optimistic lock)
        result = (
            await self._client.client.table("orders")
            .update({
                "locked_until": lock_until.isoformat(),
                "locked_by": lock_by,
            })
            .eq("id", str(order_id))
            .or_(f"locked_until.is.null,locked_until.lte.{now_iso}")
            .execute()
        )

        acquired = len(result.data) > 0
        if acquired:
            logger.debug("order_lock_acquired", order_id=str(order_id)[:8], locked_by=lock_by)
        return acquired

    async def release_lock(self, order_id: UUID | str) -> None:
        """Release processing lock for an order."""
        await (
            self._client.client.table("orders")
            .update({
                "locked_until": None,
                "locked_by": None,
            })
            .eq("id", str(order_id))
            .execute()
        )
        logger.debug("order_lock_released", order_id=str(order_id)[:8])

    async def get_pending_count(self) -> int:
        """Get count of orders pending retry."""
        now = datetime.utcnow().isoformat()

        result = (
            await self._client.client.table("orders")
            .select("id", count="exact")
            .in_("status", ["pending", "failed"])
            .lte("next_retry_at", now)
            .execute()
        )

        return result.count or 0

    async def get_retry_stats(self, hours: int = 1) -> dict[str, int | float]:
        """Get retry statistics for the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Get all orders with retries in timeframe
        result = (
            await self._client.client.table("orders")
            .select("status, attempt_count")
            .gte("updated_at", cutoff.isoformat())
            .gt("attempt_count", 0)
            .execute()
        )

        data: list[dict[str, str | int]] = result.data  # type: ignore[assignment]
        total = len(data)
        succeeded = sum(1 for r in data if r.get("status") == "filled")
        failed = sum(1 for r in data if r.get("status") == "cancelled")
        pending = total - succeeded - failed

        return {
            "total_retries": total,
            "succeeded": succeeded,
            "failed": failed,
            "pending": pending,
            "success_rate_pct": round((succeeded / total * 100) if total > 0 else 0.0, 1),
        }

    async def get_active_orders(
        self,
        is_simulated: bool | None = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get non-terminal orders."""
        query = (
            self._client.client.table("orders")
            .select("*")
            .not_.in_("status", ["filled", "cancelled"])
        )

        if is_simulated is not None:
            query = query.eq("is_simulated", is_simulated)

        result = await query.order("created_at", desc=True).limit(limit).execute()

        return [self._deserialize_order(row) for row in result.data]

    async def get_history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        order_type: OrderType | None = None,
        status: OrderStatus | None = None,
        is_simulated: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Order]:
        """Get order history with filters."""
        query = self._client.client.table("orders").select("*")

        if start_date:
            query = query.gte("created_at", start_date.isoformat())
        if end_date:
            query = query.lte("created_at", end_date.isoformat())
        if order_type:
            query = query.eq("order_type", order_type.value)
        if status:
            query = query.eq("status", status.value)
        if is_simulated is not None:
            query = query.eq("is_simulated", is_simulated)

        result = (
            await query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return [self._deserialize_order(row) for row in result.data]

    async def count_by_status(
        self,
        is_simulated: bool | None = None,
    ) -> dict[str, int]:
        """Count orders by status."""
        query = self._client.client.table("orders").select("status")

        if is_simulated is not None:
            query = query.eq("is_simulated", is_simulated)

        result = await query.execute()

        # Count in memory
        counts: dict[str, int] = {}
        for row in result.data:  # type: ignore[union-attr]
            status = str(row["status"])  # type: ignore[index]
            counts[status] = counts.get(status, 0) + 1

        return counts

    def _serialize_order(self, order: Order) -> dict[str, str | int | float | bool | None]:
        """Serialize order for database."""
        return {
            "id": str(order.id),
            "order_type": order.order_type.value,
            "side": order.side.value,
            "signal_id": order.signal_id,
            "position_id": order.position_id,
            "token_address": order.token_address,
            "token_symbol": order.token_symbol,
            "amount_sol": float(order.amount_sol),
            "amount_tokens": float(order.amount_tokens) if order.amount_tokens else None,
            "expected_price": float(order.expected_price),
            "actual_price": float(order.actual_price) if order.actual_price else None,
            "max_slippage_bps": order.max_slippage_bps,
            "status": order.status.value,
            "tx_signature": order.tx_signature,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "attempt_count": order.attempt_count,
            "max_attempts": order.max_attempts,
            "last_error": order.last_error,
            "next_retry_at": (
                order.next_retry_at.isoformat() if order.next_retry_at else None
            ),
            "is_simulated": order.is_simulated,
            "locked_until": (
                order.locked_until.isoformat() if order.locked_until else None
            ),
            "locked_by": order.locked_by,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
        }

    def _deserialize_order(self, data: dict[str, str | int | float | bool | None]) -> Order:
        """Deserialize order from database."""
        return Order(
            id=UUID(data["id"]),
            order_type=OrderType(data["order_type"]),
            side=data["side"],
            signal_id=data.get("signal_id"),
            position_id=data.get("position_id"),
            token_address=data["token_address"],
            token_symbol=data.get("token_symbol"),
            amount_sol=Decimal(str(data["amount_sol"])),
            amount_tokens=(
                Decimal(str(data["amount_tokens"]))
                if data.get("amount_tokens")
                else None
            ),
            expected_price=Decimal(str(data["expected_price"])),
            actual_price=(
                Decimal(str(data["actual_price"])) if data.get("actual_price") else None
            ),
            max_slippage_bps=data["max_slippage_bps"],
            status=OrderStatus(data["status"]),
            tx_signature=data.get("tx_signature"),
            filled_at=(
                datetime.fromisoformat(data["filled_at"].replace("Z", "+00:00"))
                if data.get("filled_at")
                else None
            ),
            attempt_count=data["attempt_count"],
            max_attempts=data["max_attempts"],
            last_error=data.get("last_error"),
            next_retry_at=(
                datetime.fromisoformat(data["next_retry_at"].replace("Z", "+00:00"))
                if data.get("next_retry_at")
                else None
            ),
            is_simulated=data["is_simulated"],
            locked_until=(
                datetime.fromisoformat(data["locked_until"].replace("Z", "+00:00"))
                if data.get("locked_until")
                else None
            ),
            locked_by=data.get("locked_by"),
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                data["updated_at"].replace("Z", "+00:00")
            ),
        )


# Singleton
_repo: OrderRepository | None = None


async def get_order_repository() -> OrderRepository:
    """Get or create order repository singleton."""
    global _repo
    if _repo is None:
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()
        _repo = OrderRepository(client)
    return _repo
