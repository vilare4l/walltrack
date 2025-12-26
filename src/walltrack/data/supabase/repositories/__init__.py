"""Repository pattern implementations."""

from walltrack.data.supabase.repositories.discovery_repo import DiscoveryRepository
from walltrack.data.supabase.repositories.webhook_repo import WebhookRepository

__all__ = [
    "DiscoveryRepository",
    "WebhookRepository",
]
