"""Webhook synchronization service.

Auto-syncs Helius webhooks with tracked wallets after discovery runs.
"""

from typing import Any

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.supabase.client import SupabaseClient
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger()


class WebhookSyncService:
    """Service to sync Helius webhooks with tracked wallets."""

    def __init__(
        self,
        helius_client: HeliusClient,
        supabase_client: SupabaseClient,
    ) -> None:
        self._helius = helius_client
        self._supabase = supabase_client
        self._settings = get_settings()

    async def sync_tracked_wallets(self) -> dict[str, Any]:
        """
        Sync the Helius webhook with all active tracked wallets.

        If no webhook exists and webhook_url is configured, creates one.
        If webhook exists, updates it with current wallet list.

        Returns:
            Sync result with status and wallet count
        """
        if not self._settings.helius_auto_sync_webhook:
            log.debug("webhook_auto_sync_disabled")
            return {"status": "disabled", "reason": "auto_sync_disabled"}

        if not self._settings.helius_webhook_url:
            log.warning("webhook_sync_skipped", reason="no_webhook_url_configured")
            return {"status": "skipped", "reason": "no_webhook_url"}

        # Get all active wallets
        wallet_repo = WalletRepository(self._supabase)
        wallets = await wallet_repo.get_active_wallets(limit=1000)
        wallet_addresses = [w.address for w in wallets]

        if not wallet_addresses:
            log.info("webhook_sync_skipped", reason="no_wallets")
            return {"status": "skipped", "reason": "no_wallets"}

        webhook_id = self._settings.helius_webhook_id

        try:
            if webhook_id:
                # Update existing webhook
                existing = await self._helius.get_webhook(webhook_id)
                if existing:
                    await self._helius.update_webhook(
                        webhook_id=webhook_id,
                        wallet_addresses=wallet_addresses,
                    )
                    log.info(
                        "webhook_synced",
                        webhook_id=webhook_id,
                        wallet_count=len(wallet_addresses),
                    )
                    return {
                        "status": "synced",
                        "webhook_id": webhook_id,
                        "wallet_count": len(wallet_addresses),
                    }
                else:
                    log.warning(
                        "webhook_not_found",
                        webhook_id=webhook_id,
                        action="creating_new",
                    )
                    # Fall through to create new

            # Create new webhook
            result = await self._helius.create_webhook(
                webhook_url=self._settings.helius_webhook_url,
                wallet_addresses=wallet_addresses,
                transaction_types=["SWAP"],
            )

            new_webhook_id = result.get("webhookID", "")
            log.info(
                "webhook_created",
                webhook_id=new_webhook_id,
                wallet_count=len(wallet_addresses),
            )

            return {
                "status": "created",
                "webhook_id": new_webhook_id,
                "wallet_count": len(wallet_addresses),
                "action_required": f"Set HELIUS_WEBHOOK_ID={new_webhook_id} in .env",
            }

        except Exception as e:
            log.error("webhook_sync_failed", error=str(e))
            return {"status": "error", "error": str(e)}


# Singleton
_sync_service: WebhookSyncService | None = None


async def get_webhook_sync_service(
    helius_client: HeliusClient,
    supabase_client: SupabaseClient,
) -> WebhookSyncService:
    """Get or create webhook sync service."""
    global _sync_service
    if _sync_service is None:
        _sync_service = WebhookSyncService(helius_client, supabase_client)
    return _sync_service


async def sync_webhooks_after_discovery(
    helius_client: HeliusClient,
    supabase_client: SupabaseClient,
) -> dict[str, Any]:
    """
    Convenience function to sync webhooks after a discovery run.

    Args:
        helius_client: Helius API client
        supabase_client: Supabase client

    Returns:
        Sync result
    """
    service = await get_webhook_sync_service(helius_client, supabase_client)
    return await service.sync_tracked_wallets()
