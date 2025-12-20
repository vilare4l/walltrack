"""Repository for webhook logging and metrics."""

from datetime import UTC, datetime, timedelta

import structlog

from walltrack.data.supabase.client import SupabaseClient
from walltrack.services.helius.models import ParsedSwapEvent, WebhookStats

logger = structlog.get_logger(__name__)


class WebhookRepository:
    """Repository for webhook logging and metrics."""

    def __init__(self, client: SupabaseClient) -> None:
        """
        Initialize webhook repository.

        Args:
            client: Supabase client instance
        """
        self._client = client

    async def log_webhook_received(self, event: ParsedSwapEvent) -> None:
        """
        Log received webhook for tracking and debugging.

        Args:
            event: Parsed swap event to log
        """
        try:
            await self._client.insert(
                "webhook_logs",
                {
                    "tx_signature": event.tx_signature,
                    "wallet_address": event.wallet_address,
                    "token_address": event.token_address,
                    "direction": event.direction.value,
                    "amount_token": float(event.amount_token),
                    "amount_sol": float(event.amount_sol),
                    "slot": event.slot,
                    "received_at": datetime.now(UTC).isoformat(),
                    "processing_started_at": event.processing_started_at.isoformat(),
                    "status": "received",
                },
            )
            logger.debug(
                "webhook_logged",
                tx_signature=event.tx_signature[:16] + "...",
            )
        except Exception as e:
            # Log but don't fail - webhook processing should continue
            logger.error(
                "webhook_log_failed",
                error=str(e),
                tx_signature=event.tx_signature,
            )

    async def update_webhook_status(
        self,
        tx_signature: str,
        status: str,
        processing_time_ms: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Update webhook processing status.

        Args:
            tx_signature: Transaction signature
            status: New status (processing, completed, failed)
            processing_time_ms: Processing time in milliseconds
            error_message: Error message if failed
        """
        try:
            update_data: dict = {
                "status": status,
                "processing_completed_at": datetime.now(UTC).isoformat(),
            }
            if processing_time_ms is not None:
                update_data["processing_time_ms"] = processing_time_ms
            if error_message:
                update_data["error_message"] = error_message

            await self._client.table("webhook_logs").update(update_data).eq(
                "tx_signature", tx_signature
            ).execute()
        except Exception as e:
            logger.error(
                "webhook_status_update_failed",
                error=str(e),
                tx_signature=tx_signature,
            )

    async def get_webhook_stats(self, hours: int = 24) -> WebhookStats:
        """
        Get webhook processing statistics.

        Args:
            hours: Number of hours to look back

        Returns:
            WebhookStats with count, last received, and avg processing time
        """
        try:
            cutoff = datetime.now(UTC) - timedelta(hours=hours)

            # Get count
            result = await self._client.table("webhook_logs").select(
                "received_at",
                count="exact",
            ).gte("received_at", cutoff.isoformat()).execute()

            count = result.count or 0

            # Get latest webhook
            latest = await self._client.table("webhook_logs").select(
                "received_at"
            ).order("received_at", desc=True).limit(1).execute()

            last_received = None
            if latest.data:
                last_received = datetime.fromisoformat(
                    latest.data[0]["received_at"].replace("Z", "+00:00")
                )

            # Get average processing time
            avg_result = await self._client.table("webhook_logs").select(
                "processing_time_ms"
            ).gte("received_at", cutoff.isoformat()).not_.is_(
                "processing_time_ms", "null"
            ).execute()

            avg_processing_ms = 0.0
            if avg_result.data:
                times = [
                    r["processing_time_ms"]
                    for r in avg_result.data
                    if r["processing_time_ms"]
                ]
                if times:
                    avg_processing_ms = sum(times) / len(times)

            return WebhookStats(
                count=count,
                last_received=last_received,
                avg_processing_ms=avg_processing_ms,
            )

        except Exception as e:
            logger.error("get_webhook_stats_failed", error=str(e))
            return WebhookStats(count=0, last_received=None, avg_processing_ms=0.0)

    async def check_duplicate(self, tx_signature: str) -> bool:
        """
        Check if a webhook with this signature was already processed.

        Args:
            tx_signature: Transaction signature to check

        Returns:
            True if duplicate exists
        """
        try:
            result = await self._client.table("webhook_logs").select(
                "tx_signature"
            ).eq("tx_signature", tx_signature).limit(1).execute()

            return bool(result.data)
        except Exception as e:
            logger.error("check_duplicate_failed", error=str(e))
            return False
