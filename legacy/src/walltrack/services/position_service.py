"""Position service with simulation filtering."""

from datetime import UTC, datetime
from uuid import uuid4

import structlog

from walltrack.core.simulation.context import is_simulation_mode
from walltrack.data.supabase.client import get_supabase_client
from walltrack.models.position import Position, PositionStatus

log = structlog.get_logger()


class PositionService:
    """Service for managing positions with simulation support."""

    async def get_active_positions(
        self,
        simulated: bool | None = None,
    ) -> list[Position]:
        """Get active positions, optionally filtered by simulation status.

        Args:
            simulated: If None, uses current execution mode.
                      If True/False, filters explicitly.

        Returns:
            List of active Position objects
        """
        supabase = await get_supabase_client()

        filters: dict = {"status": PositionStatus.OPEN.value}

        # If not specified, use current execution mode
        if simulated is None:
            simulated = is_simulation_mode()

        filters["simulated"] = simulated

        records = await supabase.select("positions", filters=filters)
        return [Position(**r) for r in records]

    async def get_all_simulated_positions(self) -> list[Position]:
        """Get all simulated positions (open and closed).

        Returns:
            List of all simulated Position objects
        """
        supabase = await get_supabase_client()
        records = await supabase.select(
            "positions",
            filters={"simulated": True},
        )
        return [Position(**r) for r in records]

    async def create_position(
        self,
        signal_id: str,
        token_address: str,
        entry_price: float,
        entry_amount_sol: float,
        entry_amount_tokens: float,
        exit_strategy_id: str,
        conviction_tier: str,
        token_symbol: str | None = None,
    ) -> Position:
        """Create a new position.

        The simulated flag is automatically set based on current execution mode.

        Args:
            signal_id: Source signal ID
            token_address: Token mint address
            entry_price: Entry price in USD
            entry_amount_sol: Amount of SOL spent
            entry_amount_tokens: Amount of tokens received
            exit_strategy_id: Exit strategy ID
            conviction_tier: "high" or "standard"
            token_symbol: Optional token symbol

        Returns:
            Created Position object
        """
        position_data = {
            "id": str(uuid4()),
            "signal_id": signal_id,
            "token_address": token_address,
            "token_symbol": token_symbol,
            "entry_price": entry_price,
            "entry_amount_sol": entry_amount_sol,
            "entry_amount_tokens": entry_amount_tokens,
            "current_amount_tokens": entry_amount_tokens,
            # Legacy columns required by DB schema
            "entry_amount": entry_amount_sol,
            "tokens_held": entry_amount_tokens,
            "status": PositionStatus.OPEN.value,
            "simulated": is_simulation_mode(),
            "exit_strategy_id": exit_strategy_id,
            "conviction_tier": conviction_tier,
            "entry_time": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }

        supabase = await get_supabase_client()
        result = await supabase.insert("positions", position_data)

        log.info(
            "position_created",
            position_id=position_data["id"],
            token=token_address,
            simulated=position_data["simulated"],
        )

        return Position(**result)

    async def close_position(
        self,
        position_id: str,
        exit_price: float,
        realized_pnl_sol: float,
        exit_reason: str | None = None,
    ) -> Position:
        """Close a position.

        Args:
            position_id: Position ID to close
            exit_price: Exit price in USD
            realized_pnl_sol: Realized P&L in SOL
            exit_reason: Optional exit reason

        Returns:
            Updated Position object
        """
        supabase = await get_supabase_client()

        update_data = {
            "status": PositionStatus.CLOSED.value,
            "exit_time": datetime.now(UTC).isoformat(),
            "exit_price": exit_price,
            "realized_pnl_sol": realized_pnl_sol,
            "updated_at": datetime.now(UTC).isoformat(),
        }

        if exit_reason:
            update_data["exit_reason"] = exit_reason

        result = await supabase.update(
            "positions",
            {"id": position_id},
            update_data,
        )

        log.info(
            "position_closed",
            position_id=position_id,
            exit_price=exit_price,
            pnl=realized_pnl_sol,
        )

        return Position(**result)


# Singleton
_position_service: PositionService | None = None


async def get_position_service() -> PositionService:
    """Get position service singleton."""
    global _position_service
    if _position_service is None:
        _position_service = PositionService()
    return _position_service
