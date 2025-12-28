"""API routes for order management.

Story 13-1: Created to expose order CRUD and retry operations.
Epic 10.5-13: Required for Order UI.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from walltrack.data.supabase.repositories.order_repo import get_order_repository
from walltrack.models.order import Order, OrderStatus, OrderSummary, OrderType

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["orders"])


# Response Models


class OrderListResponse(BaseModel):
    """Paginated list of orders."""

    orders: list[OrderSummary]
    total: int
    limit: int
    offset: int


class OrderStatsResponse(BaseModel):
    """Order statistics and health metrics."""

    total_orders: int
    by_status: dict[str, int]
    retry_stats: dict[str, int | float]
    pending_retry_count: int


class OrderRetryResponse(BaseModel):
    """Response from retry operation."""

    success: bool
    order_id: str
    new_status: str
    message: str


class OrderCancelResponse(BaseModel):
    """Response from cancel operation."""

    success: bool
    order_id: str
    message: str


class BulkStatusRequest(BaseModel):
    """Request for bulk status check."""

    order_ids: list[UUID] = Field(..., description="List of order IDs to check")


# Endpoints


@router.get("", response_model=OrderListResponse)
async def list_orders(
    status: str | None = Query(
        None, description="Filter by status (pending, submitted, confirming, filled, failed, cancelled)"
    ),
    order_type: str | None = Query(
        None, description="Filter by type (entry, exit)"
    ),
    is_simulated: bool | None = Query(
        None, description="Filter by simulation mode"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum orders to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> OrderListResponse:
    """
    List orders with pagination and filters.

    Supports filtering by status, type, and simulation mode.
    Returns paginated results sorted by creation date (newest first).
    """
    repo = await get_order_repository()

    # Convert string filters to enums
    status_enum = OrderStatus(status) if status else None
    type_enum = OrderType(order_type) if order_type else None

    orders = await repo.get_history(
        status=status_enum,
        order_type=type_enum,
        is_simulated=is_simulated,
        limit=limit,
        offset=offset,
    )

    # Get total count for pagination
    counts = await repo.count_by_status(is_simulated=is_simulated)
    total = sum(counts.values())

    summaries = [
        OrderSummary(
            id=o.id,
            order_type=o.order_type,
            side=o.side,
            token_symbol=o.token_symbol,
            amount_sol=o.amount_sol,
            status=o.status,
            attempt_count=o.attempt_count,
            is_simulated=o.is_simulated,
            created_at=o.created_at,
            slippage_bps=o.slippage_bps,
        )
        for o in orders
    ]

    logger.debug("orders_listed", count=len(orders), status=status, type=order_type)

    return OrderListResponse(
        orders=summaries,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/stats", response_model=OrderStatsResponse)
async def get_order_stats(
    hours: int = Query(1, ge=1, le=168, description="Hours to look back for retry stats"),
) -> OrderStatsResponse:
    """
    Get order statistics and health metrics.

    Returns counts by status, retry success rate, and pending retry count.
    Useful for monitoring order health and retry queue status.
    """
    repo = await get_order_repository()

    by_status = await repo.count_by_status()
    retry_stats = await repo.get_retry_stats(hours=hours)
    pending_count = await repo.get_pending_count()

    total = sum(by_status.values())

    logger.info(
        "order_stats_fetched",
        total=total,
        pending_retries=pending_count,
        retry_success_rate=retry_stats.get("success_rate_pct", 0),
    )

    return OrderStatsResponse(
        total_orders=total,
        by_status=by_status,
        retry_stats=retry_stats,
        pending_retry_count=pending_count,
    )


@router.get("/active", response_model=OrderListResponse)
async def list_active_orders(
    is_simulated: bool | None = Query(None, description="Filter by simulation mode"),
    limit: int = Query(50, ge=1, le=200, description="Maximum orders to return"),
) -> OrderListResponse:
    """
    List non-terminal orders (pending, submitted, confirming, failed).

    These are orders that are still being processed or awaiting retry.
    """
    repo = await get_order_repository()

    orders = await repo.get_active_orders(is_simulated=is_simulated, limit=limit)

    summaries = [
        OrderSummary(
            id=o.id,
            order_type=o.order_type,
            side=o.side,
            token_symbol=o.token_symbol,
            amount_sol=o.amount_sol,
            status=o.status,
            attempt_count=o.attempt_count,
            is_simulated=o.is_simulated,
            created_at=o.created_at,
            slippage_bps=o.slippage_bps,
        )
        for o in orders
    ]

    return OrderListResponse(
        orders=summaries,
        total=len(summaries),
        limit=limit,
        offset=0,
    )


@router.get("/pending-retries", response_model=OrderListResponse)
async def list_pending_retries(
    limit: int = Query(20, ge=1, le=100, description="Maximum orders to return"),
) -> OrderListResponse:
    """
    List orders pending retry.

    Returns orders that are ready to be retried, ordered by priority
    (EXIT orders first, then by age).
    """
    repo = await get_order_repository()

    orders = await repo.get_pending_retries(limit=limit)

    summaries = [
        OrderSummary(
            id=o.id,
            order_type=o.order_type,
            side=o.side,
            token_symbol=o.token_symbol,
            amount_sol=o.amount_sol,
            status=o.status,
            attempt_count=o.attempt_count,
            is_simulated=o.is_simulated,
            created_at=o.created_at,
            slippage_bps=o.slippage_bps,
        )
        for o in orders
    ]

    return OrderListResponse(
        orders=summaries,
        total=len(summaries),
        limit=limit,
        offset=0,
    )


@router.get("/{order_id}", response_model=Order)
async def get_order(order_id: UUID) -> Order:
    """
    Get detailed order information by ID.

    Returns full order object including execution details,
    retry information, and timestamps.
    """
    repo = await get_order_repository()

    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    return order


@router.post("/{order_id}/retry", response_model=OrderRetryResponse)
async def retry_order(order_id: UUID) -> OrderRetryResponse:
    """
    Force immediate retry of a failed order.

    Only works for orders in FAILED status that haven't exceeded max attempts.
    Resets the order to PENDING status for immediate processing.
    """
    repo = await get_order_repository()

    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    if order.status != OrderStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry order in {order.status.value} status. Only FAILED orders can be retried.",
        )

    if not order.can_retry:
        raise HTTPException(
            status_code=400,
            detail=f"Order has exceeded max retry attempts ({order.attempt_count}/{order.max_attempts})",
        )

    # Reset to pending for immediate retry
    order.schedule_retry()
    await repo.update(order)

    logger.info(
        "order_retry_triggered",
        order_id=str(order_id)[:8],
        attempt=order.attempt_count,
    )

    return OrderRetryResponse(
        success=True,
        order_id=str(order_id),
        new_status=order.status.value,
        message=f"Order scheduled for retry (attempt {order.attempt_count + 1}/{order.max_attempts})",
    )


@router.post("/{order_id}/cancel", response_model=OrderCancelResponse)
async def cancel_order(
    order_id: UUID,
    reason: str = Query("Manually cancelled", description="Cancellation reason"),
) -> OrderCancelResponse:
    """
    Cancel an order permanently.

    Only works for orders that are not in terminal state (FILLED or CANCELLED).
    """
    repo = await get_order_repository()

    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    if order.is_terminal:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order in {order.status.value} status. Order is already terminal.",
        )

    order.cancel(reason)
    await repo.update(order)

    logger.info(
        "order_cancelled",
        order_id=str(order_id)[:8],
        reason=reason,
    )

    return OrderCancelResponse(
        success=True,
        order_id=str(order_id),
        message=f"Order cancelled: {reason}",
    )


@router.post("/bulk-status")
async def get_bulk_status(
    request: BulkStatusRequest,
) -> dict[str, str]:
    """
    Get status of multiple orders at once.

    Returns a mapping of order_id -> status for each requested order.
    Missing orders are not included in the response.
    """
    repo = await get_order_repository()

    result: dict[str, str] = {}
    for order_id in request.order_ids:
        order = await repo.get_by_id(order_id)
        if order:
            result[str(order_id)] = order.status.value

    return result
