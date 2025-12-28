"""P&L history tracking for simulation."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import structlog

from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


async def log_portfolio_pnl(
    unrealized_pnl: Decimal,
    realized_pnl: Decimal,
    position_count: int,
) -> dict:
    """Log portfolio P&L snapshot.

    Args:
        unrealized_pnl: Current unrealized P&L in USD
        realized_pnl: Total realized P&L in USD
        position_count: Number of open positions

    Returns:
        The created record
    """
    supabase = await get_supabase_client()

    record = {
        "id": str(uuid4()),
        "unrealized_pnl": float(unrealized_pnl),
        "realized_pnl": float(realized_pnl),
        "total_pnl": float(unrealized_pnl + realized_pnl),
        "position_count": position_count,
        "recorded_at": datetime.now(UTC).isoformat(),
        "simulated": True,
    }

    result = await supabase.insert("pnl_history", record)

    log.info(
        "pnl_snapshot_recorded",
        unrealized=float(unrealized_pnl),
        realized=float(realized_pnl),
        total=float(unrealized_pnl + realized_pnl),
        positions=position_count,
    )

    return result
