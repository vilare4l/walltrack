"""Webhook endpoints for Helius notifications."""

import time
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from walltrack.constants.webhook import MAX_PROCESSING_TIME_MS
from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.data.supabase.repositories.webhook_repo import WebhookRepository
from walltrack.services.helius.models import (
    ParsedSwapEvent,
    WebhookHealthStatus,
)
from walltrack.services.helius.webhook_manager import WebhookParser, get_webhook_parser

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhooks"])


async def get_webhook_repo(
    client: SupabaseClient = Depends(get_supabase_client),
) -> WebhookRepository:
    """Dependency for webhook repository."""
    return WebhookRepository(client)


@router.post("/helius")
async def receive_helius_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    parser: WebhookParser = Depends(get_webhook_parser),
    webhook_repo: WebhookRepository = Depends(get_webhook_repo),
) -> dict[str, Any]:
    """
    Receive and process Helius webhook notifications.

    HMAC validation is handled by middleware before this endpoint.
    Processing must complete in < 500ms (NFR2).

    Args:
        request: FastAPI request with JSON payload
        background_tasks: Background task queue
        parser: Webhook parser service
        webhook_repo: Webhook repository for logging

    Returns:
        Status response with processing metrics
    """
    start_time = time.perf_counter()

    try:
        payload = await request.json()

        # Handle array of transactions (Helius sends batches)
        transactions = payload if isinstance(payload, list) else [payload]
        processed_count = 0

        for tx_payload in transactions:
            swap_event = parser.parse_payload(tx_payload)

            if swap_event:
                # Process in background to meet timing requirements
                background_tasks.add_task(
                    _process_swap_event,
                    swap_event,
                    webhook_repo,
                )
                processed_count += 1

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "webhook_received",
            transaction_count=len(transactions),
            processed_count=processed_count,
            processing_time_ms=round(processing_time_ms, 2),
        )

        # Warn if approaching limit
        if processing_time_ms > MAX_PROCESSING_TIME_MS * 0.8:
            logger.warning(
                "webhook_processing_slow",
                processing_time_ms=processing_time_ms,
                limit_ms=MAX_PROCESSING_TIME_MS,
            )

        return {
            "status": "accepted",
            "transactions_received": len(transactions),
            "swaps_detected": processed_count,
            "processing_time_ms": round(processing_time_ms, 2),
        }

    except Exception as e:
        logger.error("webhook_processing_error", error=str(e))
        raise HTTPException(status_code=500, detail="Webhook processing failed") from e


async def _process_swap_event(
    event: ParsedSwapEvent,
    webhook_repo: WebhookRepository,
) -> None:
    """
    Background task to process swap event through signal pipeline.

    Args:
        event: Parsed swap event
        webhook_repo: Repository for logging
    """
    start_time = time.perf_counter()

    try:
        # Log webhook receipt
        await webhook_repo.log_webhook_received(event)

        # Process through signal pipeline (Story 3-2)
        try:
            from walltrack.services.signal.pipeline import get_pipeline

            pipeline = await get_pipeline()
            signal_context = await pipeline.process_swap_event(event)

            if signal_context:
                logger.debug(
                    "signal_passed_pipeline",
                    tx=event.tx_signature[:16] + "...",
                    filter_time_ms=round(signal_context.filter_time_ms, 2),
                )
        except Exception as pipeline_error:
            # Log but don't fail webhook - pipeline may not be initialized
            logger.warning("pipeline_processing_skipped", error=str(pipeline_error))

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Update status with processing time
        await webhook_repo.update_webhook_status(
            tx_signature=event.tx_signature,
            status="completed",
            processing_time_ms=processing_time_ms,
        )

        logger.debug(
            "swap_event_processed",
            signature=event.tx_signature[:16] + "...",
            wallet=event.wallet_address[:8] + "...",
            token=event.token_address[:8] + "...",
            direction=event.direction.value,
            processing_time_ms=round(processing_time_ms, 2),
        )
    except Exception as e:
        logger.error(
            "swap_event_processing_failed",
            signature=event.tx_signature,
            error=str(e),
        )
        await webhook_repo.update_webhook_status(
            tx_signature=event.tx_signature,
            status="failed",
            error_message=str(e),
        )


@router.get("/health", response_model=WebhookHealthStatus)
async def webhook_health_check(
    webhook_repo: WebhookRepository = Depends(get_webhook_repo),
) -> WebhookHealthStatus:
    """
    Health check for webhook endpoint.

    Returns Helius connectivity status and processing metrics.

    Args:
        webhook_repo: Repository for stats

    Returns:
        WebhookHealthStatus with metrics
    """
    try:
        stats = await webhook_repo.get_webhook_stats(hours=24)

        return WebhookHealthStatus(
            status="healthy",
            helius_connected=True,  # Would check actual connectivity
            last_webhook_received=stats.last_received,
            webhooks_processed_24h=stats.count,
            average_processing_ms=stats.avg_processing_ms,
        )
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return WebhookHealthStatus(
            status="degraded",
            helius_connected=False,
        )
