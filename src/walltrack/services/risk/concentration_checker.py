"""Checks and enforces concentration limits.

Story 10.5-11: Prevents over-concentration in single tokens or clusters.
"""

from __future__ import annotations

import structlog

from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.models.position_sizing import ConcentrationMetrics, PositionSizingConfig

logger = structlog.get_logger(__name__)


class ConcentrationChecker:
    """Checks portfolio concentration limits.

    Features:
    - Maximum allocation per token (default 25%)
    - Maximum allocation per cluster (default 50%)
    - Maximum positions per cluster (default 3)
    - Block duplicate positions on same token
    """

    def __init__(
        self,
        client: SupabaseClient | None = None,
        config: PositionSizingConfig | None = None,
    ) -> None:
        """Initialize concentration checker.

        Args:
            client: Optional Supabase client
            config: Optional config (will use defaults if not provided)
        """
        self._client = client
        self._config = config or PositionSizingConfig()

    async def _get_client(self) -> SupabaseClient:
        """Get or create Supabase client."""
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    def update_config(self, config: PositionSizingConfig) -> None:
        """Update configuration.

        Args:
            config: New configuration
        """
        self._config = config

    async def check_entry(
        self,
        token_address: str,
        requested_amount_sol: float,
        cluster_id: str | None = None,
        portfolio_value_sol: float | None = None,
    ) -> ConcentrationMetrics:
        """Check if entry respects concentration limits.

        Args:
            token_address: Token address for the new position
            requested_amount_sol: Requested position size in SOL
            cluster_id: Optional cluster ID for cluster limits
            portfolio_value_sol: Optional portfolio value override

        Returns:
            ConcentrationMetrics with check results
        """
        log = logger.bind(token=token_address[:8] if token_address else "unknown")

        # Get portfolio value if not provided
        if portfolio_value_sol is None:
            portfolio_value_sol = await self._get_portfolio_value()

        # Initialize metrics
        metrics = ConcentrationMetrics(
            token_address=token_address,
            cluster_id=cluster_id,
            portfolio_value_sol=portfolio_value_sol,
            token_limit_pct=self._config.max_token_concentration_pct,
            cluster_limit_pct=self._config.max_cluster_concentration_pct,
            cluster_max_positions=self._config.max_positions_per_cluster,
            requested_amount_sol=requested_amount_sol,
            max_allowed_sol=requested_amount_sol,
        )

        # If no portfolio value, allow the trade (first position)
        if portfolio_value_sol <= 0:
            log.debug("concentration_check_skipped_no_portfolio")
            return metrics

        # Check for duplicate position
        if self._config.block_duplicate_positions and token_address:
            is_duplicate = await self._check_duplicate_position(token_address)
            if is_duplicate:
                log.warning("concentration_blocked_duplicate", token=token_address[:8])
                metrics.is_duplicate = True
                metrics.block_reason = "Position already exists for this token"
                metrics.max_allowed_sol = 0.0
                return metrics

        # Calculate token concentration
        token_metrics = await self._get_token_concentration(
            token_address=token_address,
            portfolio_value_sol=portfolio_value_sol,
        )
        metrics.token_current_value_sol = float(token_metrics["current_value"])
        metrics.token_current_pct = float(token_metrics["current_pct"])
        metrics.token_remaining_capacity_sol = float(token_metrics["remaining_capacity"])

        # Calculate cluster concentration (if cluster specified)
        if cluster_id:
            cluster_metrics = await self._get_cluster_concentration(
                cluster_id=cluster_id,
                portfolio_value_sol=portfolio_value_sol,
            )
            metrics.cluster_current_value_sol = float(cluster_metrics["current_value"])
            metrics.cluster_current_pct = float(cluster_metrics["current_pct"])
            metrics.cluster_positions_count = int(cluster_metrics["positions_count"])

            # Check max positions per cluster
            if cluster_metrics["positions_count"] >= self._config.max_positions_per_cluster:
                log.warning(
                    "concentration_blocked_cluster_max_positions",
                    cluster=cluster_id,
                    count=cluster_metrics["positions_count"],
                    max=self._config.max_positions_per_cluster,
                )
                metrics.is_cluster_max_positions = True
                metrics.block_reason = (
                    f"Max positions in cluster reached "
                    f"({self._config.max_positions_per_cluster})"
                )
                metrics.max_allowed_sol = 0.0
                return metrics

        # Calculate max allowed by token limit
        max_by_token = metrics.token_remaining_capacity_sol

        # Calculate max allowed by cluster limit
        max_by_cluster = float("inf")
        if cluster_id:
            cluster_max_value = portfolio_value_sol * (
                self._config.max_cluster_concentration_pct / 100
            )
            cluster_remaining = max(
                0.0, cluster_max_value - metrics.cluster_current_value_sol
            )
            max_by_cluster = cluster_remaining

        # Take minimum of all limits
        max_allowed = min(max_by_token, max_by_cluster, requested_amount_sol)

        # Check if blocked
        if max_allowed <= 0:
            if max_by_token <= 0:
                log.warning(
                    "concentration_blocked_token_limit",
                    token_pct=round(metrics.token_current_pct, 2),
                    limit_pct=self._config.max_token_concentration_pct,
                )
                metrics.is_token_limit_hit = True
                metrics.block_reason = (
                    f"Token concentration at limit "
                    f"({metrics.token_current_pct:.1f}% >= "
                    f"{self._config.max_token_concentration_pct}%)"
                )
            elif max_by_cluster <= 0:
                log.warning(
                    "concentration_blocked_cluster_limit",
                    cluster_pct=round(metrics.cluster_current_pct, 2),
                    limit_pct=self._config.max_cluster_concentration_pct,
                )
                metrics.is_cluster_limit_hit = True
                metrics.block_reason = (
                    f"Cluster concentration at limit "
                    f"({metrics.cluster_current_pct:.1f}% >= "
                    f"{self._config.max_cluster_concentration_pct}%)"
                )
            metrics.max_allowed_sol = 0.0
            return metrics

        # Check if amount was adjusted
        if max_allowed < requested_amount_sol:
            metrics.was_adjusted = True
            log.info(
                "concentration_size_reduced",
                requested=round(requested_amount_sol, 4),
                allowed=round(max_allowed, 4),
                token_remaining=round(max_by_token, 4),
                cluster_remaining=(
                    round(max_by_cluster, 4) if max_by_cluster != float("inf") else "unlimited"
                ),
            )

        metrics.max_allowed_sol = max_allowed
        return metrics

    async def _get_portfolio_value(self) -> float:
        """Get current portfolio value (sum of open positions)."""
        client = await self._get_client()

        try:
            result = await client.table("positions").select(
                "entry_amount_sol, unrealized_pnl"
            ).in_("status", ["open", "partial_exit"]).execute()

            total = 0.0
            for row in result.data:
                entry = float(row.get("entry_amount_sol", 0) or 0)
                pnl = float(row.get("unrealized_pnl", 0) or 0)
                total += entry + pnl

            return total
        except Exception as e:
            logger.warning("portfolio_value_fetch_failed", error=str(e))
            return 0.0

    async def _check_duplicate_position(self, token_address: str) -> bool:
        """Check if a position already exists for this token."""
        client = await self._get_client()

        try:
            result = await client.table("positions").select(
                "id"
            ).eq("token_address", token_address).in_(
                "status", ["open", "partial_exit", "exit_pending"]
            ).limit(1).execute()

            return len(result.data) > 0
        except Exception as e:
            logger.warning("duplicate_check_failed", error=str(e))
            return False

    async def _get_token_concentration(
        self,
        token_address: str,
        portfolio_value_sol: float,
    ) -> dict[str, float | int]:
        """Get concentration metrics for a specific token."""
        client = await self._get_client()

        try:
            result = await client.table("positions").select(
                "entry_amount_sol, unrealized_pnl"
            ).eq("token_address", token_address).in_(
                "status", ["open", "partial_exit"]
            ).execute()

            current_value = 0.0
            for row in result.data:
                current_value += float(row.get("entry_amount_sol", 0) or 0)
                current_value += float(row.get("unrealized_pnl", 0) or 0)

            current_pct = (
                (current_value / portfolio_value_sol * 100)
                if portfolio_value_sol > 0
                else 0.0
            )

            max_value = portfolio_value_sol * (
                self._config.max_token_concentration_pct / 100
            )
            remaining = max(0.0, max_value - current_value)

            return {
                "current_value": current_value,
                "current_pct": current_pct,
                "remaining_capacity": remaining,
                "positions_count": len(result.data),
            }
        except Exception as e:
            logger.warning("token_concentration_fetch_failed", error=str(e))
            return {
                "current_value": 0.0,
                "current_pct": 0.0,
                "remaining_capacity": float("inf"),
                "positions_count": 0,
            }

    async def _get_cluster_concentration(
        self,
        cluster_id: str,
        portfolio_value_sol: float,
    ) -> dict[str, float | int]:
        """Get concentration metrics for a cluster."""
        client = await self._get_client()

        try:
            result = await client.table("positions").select(
                "entry_amount_sol, unrealized_pnl"
            ).eq("cluster_id", cluster_id).in_(
                "status", ["open", "partial_exit"]
            ).execute()

            current_value = 0.0
            for row in result.data:
                current_value += float(row.get("entry_amount_sol", 0) or 0)
                current_value += float(row.get("unrealized_pnl", 0) or 0)

            current_pct = (
                (current_value / portfolio_value_sol * 100)
                if portfolio_value_sol > 0
                else 0.0
            )

            return {
                "current_value": current_value,
                "current_pct": current_pct,
                "positions_count": len(result.data),
            }
        except Exception as e:
            logger.warning("cluster_concentration_fetch_failed", error=str(e))
            return {
                "current_value": 0.0,
                "current_pct": 0.0,
                "positions_count": 0,
            }


# Singleton
_checker: ConcentrationChecker | None = None


async def get_concentration_checker() -> ConcentrationChecker:
    """Get or create concentration checker singleton.

    Returns:
        ConcentrationChecker instance
    """
    global _checker
    if _checker is None:
        _checker = ConcentrationChecker()
    return _checker


def reset_concentration_checker() -> None:
    """Reset singleton for testing."""
    global _checker
    _checker = None
