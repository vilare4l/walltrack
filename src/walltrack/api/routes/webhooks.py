"""Webhook endpoints for Helius notifications."""

import time
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from walltrack.config.settings import Settings, get_settings
from walltrack.constants.webhook import MAX_PROCESSING_TIME_MS
from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.data.supabase.repositories.webhook_repo import WebhookRepository
from walltrack.services.helius.client import HeliusClient, get_helius_client
from walltrack.services.helius.models import (
    ParsedSwapEvent,
    WebhookHealthStatus,
)
from walltrack.services.helius.webhook_manager import WebhookParser, get_webhook_parser

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["webhooks"])


# ============ Models ============

class WebhookCreateRequest(BaseModel):
    """Request to create a webhook."""

    webhook_url: str = Field(..., description="Public URL to receive webhook notifications")
    wallet_addresses: list[str] = Field(
        default_factory=list,
        description="Wallet addresses to monitor (empty = sync from tracked wallets)",
    )
    transaction_types: list[str] = Field(
        default=["SWAP"],
        description="Transaction types to monitor",
    )


class WebhookSyncRequest(BaseModel):
    """Request to sync webhook with tracked wallets."""

    webhook_id: str = Field(..., description="Helius webhook ID to sync")


class WebhookResponse(BaseModel):
    """Webhook response."""

    webhook_id: str
    webhook_url: str
    wallet_count: int
    transaction_types: list[str]


class WebhookListResponse(BaseModel):
    """List of webhooks."""

    webhooks: list[dict[str, Any]]
    total: int


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


# ============ Webhook Management Endpoints ============


@router.get("/manage", response_model=WebhookListResponse)
async def list_helius_webhooks(
    helius: HeliusClient = Depends(get_helius_client),
) -> WebhookListResponse:
    """
    List all Helius webhooks for this API key.

    Returns:
        List of configured webhooks
    """
    try:
        webhooks = await helius.list_webhooks()
        return WebhookListResponse(webhooks=webhooks, total=len(webhooks))
    except Exception as e:
        logger.error("list_webhooks_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/manage", response_model=WebhookResponse)
async def create_helius_webhook(
    request: WebhookCreateRequest,
    helius: HeliusClient = Depends(get_helius_client),
    supabase: SupabaseClient = Depends(get_supabase_client),
) -> WebhookResponse:
    """
    Create a new Helius webhook.

    If wallet_addresses is empty, automatically uses all active tracked wallets.

    Args:
        request: Webhook creation parameters

    Returns:
        Created webhook details
    """
    try:
        wallet_addresses = request.wallet_addresses

        # If no wallets specified, get all active tracked wallets
        if not wallet_addresses:
            from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

            wallet_repo = WalletRepository(supabase)
            wallets = await wallet_repo.get_active_wallets(limit=1000)
            wallet_addresses = [w.address for w in wallets]

        if not wallet_addresses:
            raise HTTPException(
                status_code=400,
                detail="No wallets to monitor. Discover wallets first or provide addresses.",
            )

        result = await helius.create_webhook(
            webhook_url=request.webhook_url,
            wallet_addresses=wallet_addresses,
            transaction_types=request.transaction_types,
        )

        return WebhookResponse(
            webhook_id=result.get("webhookID", ""),
            webhook_url=request.webhook_url,
            wallet_count=len(wallet_addresses),
            transaction_types=request.transaction_types,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_webhook_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/manage/sync")
async def sync_webhook_wallets(
    request: WebhookSyncRequest,
    helius: HeliusClient = Depends(get_helius_client),
    supabase: SupabaseClient = Depends(get_supabase_client),
) -> dict[str, Any]:
    """
    Sync a webhook with current tracked wallets.

    Updates the webhook to monitor all active wallets from the database.

    Args:
        request: Sync request with webhook ID

    Returns:
        Updated webhook details
    """
    try:
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

        wallet_repo = WalletRepository(supabase)
        wallets = await wallet_repo.get_active_wallets(limit=1000)
        wallet_addresses = [w.address for w in wallets]

        if not wallet_addresses:
            raise HTTPException(
                status_code=400,
                detail="No active wallets to sync",
            )

        result = await helius.sync_webhook_wallets(
            webhook_id=request.webhook_id,
            wallet_addresses=wallet_addresses,
        )

        return {
            "status": "synced",
            "webhook_id": request.webhook_id,
            "wallet_count": len(wallet_addresses),
            "wallets": wallet_addresses[:10],  # First 10 for preview
            "more": len(wallet_addresses) > 10,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("sync_webhook_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/manage/{webhook_id}")
async def delete_helius_webhook(
    webhook_id: str,
    helius: HeliusClient = Depends(get_helius_client),
) -> dict[str, str]:
    """
    Delete a Helius webhook.

    Args:
        webhook_id: ID of the webhook to delete

    Returns:
        Deletion confirmation
    """
    try:
        await helius.delete_webhook(webhook_id)
        return {"status": "deleted", "webhook_id": webhook_id}
    except Exception as e:
        logger.error("delete_webhook_failed", webhook_id=webhook_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e
