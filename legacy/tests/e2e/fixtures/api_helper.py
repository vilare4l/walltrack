"""API helper for E2E test data seeding and verification.

This module provides utilities to:
- Seed test data via API endpoints
- Verify API responses match UI state
- Clean up test data after tests
"""

import httpx
from typing import Any

API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 10.0


class APIHelper:
    """Helper for API interactions during E2E tests."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "APIHelper":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=API_TIMEOUT,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            raise RuntimeError("APIHelper must be used as async context manager")
        return self._client

    # -------------------------------------------------------------------------
    # Health Check
    # -------------------------------------------------------------------------

    async def check_health(self) -> bool:
        """Check if API is healthy."""
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    async def get_detailed_health(self) -> dict[str, Any]:
        """Get detailed health status."""
        response = await self.client.get("/health/detailed")
        return response.json()

    # -------------------------------------------------------------------------
    # Wallet Operations
    # -------------------------------------------------------------------------

    async def get_wallets(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get wallets list."""
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        response = await self.client.get("/api/wallets", params=params)
        return response.json()

    async def add_wallet(self, address: str) -> dict[str, Any]:
        """Add a wallet to watchlist."""
        response = await self.client.post(
            "/api/wallets/add",
            json={"address": address},
        )
        return response.json()

    async def blacklist_wallet(self, address: str, reason: str) -> dict[str, Any]:
        """Blacklist a wallet."""
        response = await self.client.post(
            "/api/blacklist",
            json={"address": address, "reason": reason},
        )
        return response.json()

    # -------------------------------------------------------------------------
    # Position Operations
    # -------------------------------------------------------------------------

    async def get_active_positions(self) -> dict[str, Any]:
        """Get active positions."""
        response = await self.client.get("/api/positions/active")
        return response.json()

    async def get_position_details(self, position_id: str) -> dict[str, Any]:
        """Get position details."""
        response = await self.client.get(f"/api/positions/{position_id}")
        return response.json()

    # -------------------------------------------------------------------------
    # Order Operations
    # -------------------------------------------------------------------------

    async def get_orders(
        self,
        status: str | None = None,
        order_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get orders list."""
        params = {"limit": limit}
        if status:
            params["status"] = status
        if order_type:
            params["type"] = order_type
        response = await self.client.get("/api/orders", params=params)
        return response.json()

    # -------------------------------------------------------------------------
    # Signal Operations
    # -------------------------------------------------------------------------

    async def get_signals(self, hours: int = 24) -> dict[str, Any]:
        """Get recent signals."""
        response = await self.client.get(
            "/api/signals",
            params={"hours": hours},
        )
        return response.json()

    async def get_signal_stats(self) -> dict[str, Any]:
        """Get signal statistics."""
        response = await self.client.get("/api/signals/stats/today")
        return response.json()

    # -------------------------------------------------------------------------
    # Cluster Operations
    # -------------------------------------------------------------------------

    async def get_clusters(self) -> list[dict[str, Any]]:
        """Get all clusters."""
        response = await self.client.get("/api/clusters")
        return response.json()

    async def trigger_cluster_discovery(self) -> dict[str, Any]:
        """Trigger cluster discovery."""
        response = await self.client.post("/api/clusters/discover")
        return response.json()

    # -------------------------------------------------------------------------
    # Config Operations
    # -------------------------------------------------------------------------

    async def get_config(self) -> dict[str, Any]:
        """Get current configuration."""
        response = await self.client.get("/api/config")
        return response.json()

    async def update_config(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Update configuration."""
        response = await self.client.patch("/api/config", json=updates)
        return response.json()

    # -------------------------------------------------------------------------
    # Exit Strategy Operations
    # -------------------------------------------------------------------------

    async def get_exit_strategies(self) -> list[dict[str, Any]]:
        """Get all exit strategies."""
        response = await self.client.get("/api/exit-strategies")
        return response.json()

    async def create_exit_strategy(self, strategy: dict[str, Any]) -> dict[str, Any]:
        """Create a new exit strategy."""
        response = await self.client.post("/api/exit-strategies", json=strategy)
        return response.json()

    # -------------------------------------------------------------------------
    # Discovery Operations
    # -------------------------------------------------------------------------

    async def get_discovery_status(self) -> dict[str, Any]:
        """Get discovery status."""
        response = await self.client.get("/api/discovery/status")
        return response.json()


def sync_api_helper() -> httpx.Client:
    """Create a sync API client for simple checks."""
    return httpx.Client(base_url=API_BASE_URL, timeout=API_TIMEOUT)
