"""Repository for position storage and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from walltrack.models.position import (
    CalculatedLevel,
    ExitExecution,
    ExitReason,
    Position,
    PositionLevels,
    PositionStatus,
)

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient

logger = structlog.get_logger()


class PositionRepository:
    """Repository for position storage and retrieval."""

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def create(self, position: Position) -> Position:
        """Create new position."""
        data = self._serialize_position(position)

        result = await self._client.client.table("positions").insert(data).execute()

        logger.info(
            "position_created",
            id=position.id[:8],
            token=position.token_address[:8],
        )
        return self._deserialize_position(result.data[0])

    async def update(self, position: Position) -> Position:
        """Update position."""
        position.updated_at = datetime.utcnow()
        data = self._serialize_position(position)

        result = (
            await self._client.client.table("positions")
            .update(data)
            .eq("id", position.id)
            .execute()
        )

        return self._deserialize_position(result.data[0])

    async def get_by_id(self, position_id: str) -> Position | None:
        """Get position by ID."""
        result = (
            await self._client.client.table("positions")
            .select("*")
            .eq("id", position_id)
            .maybe_single()
            .execute()
        )

        if result.data:
            return self._deserialize_position(result.data)
        return None

    async def list_open(self) -> list[Position]:
        """List all open positions."""
        result = (
            await self._client.client.table("positions")
            .select("*")
            .in_("status", ["open", "partial_exit", "moonbag"])
            .execute()
        )

        return [self._deserialize_position(row) for row in result.data]

    async def list_by_token(self, token_address: str) -> list[Position]:
        """List positions for a specific token."""
        result = (
            await self._client.client.table("positions")
            .select("*")
            .eq("token_address", token_address)
            .order("created_at", desc=True)
            .execute()
        )

        return [self._deserialize_position(row) for row in result.data]

    async def list_recent(self, limit: int = 50) -> list[Position]:
        """List recent positions."""
        result = (
            await self._client.client.table("positions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return [self._deserialize_position(row) for row in result.data]

    async def count_open(self) -> int:
        """Count open positions."""
        result = (
            await self._client.client.table("positions")
            .select("id", count="exact")
            .in_("status", ["open", "partial_exit", "moonbag"])
            .execute()
        )

        return result.count or 0

    async def save_exit_execution(self, execution: ExitExecution) -> None:
        """Save exit execution record."""
        data = {
            "id": execution.id,
            "position_id": execution.position_id,
            "exit_reason": execution.exit_reason.value,
            "trigger_level": execution.trigger_level,
            "sell_percentage": execution.sell_percentage,
            "amount_tokens_sold": execution.amount_tokens_sold,
            "amount_sol_received": execution.amount_sol_received,
            "exit_price": execution.exit_price,
            "tx_signature": execution.tx_signature,
            "realized_pnl_sol": execution.realized_pnl_sol,
            "executed_at": execution.executed_at.isoformat(),
        }

        await self._client.client.table("exit_executions").insert(data).execute()

    async def get_exit_executions(self, position_id: str) -> list[ExitExecution]:
        """Get all exit executions for a position."""
        result = (
            await self._client.client.table("exit_executions")
            .select("*")
            .eq("position_id", position_id)
            .order("executed_at", desc=True)
            .execute()
        )

        return [self._deserialize_execution(row) for row in result.data]

    def _serialize_position(self, position: Position) -> dict:
        """Serialize position for database."""
        levels_data = None
        if position.levels:
            levels_data = {
                "entry_price": position.levels.entry_price,
                "stop_loss_price": position.levels.stop_loss_price,
                "take_profit_levels": [
                    {
                        "level_type": tp.level_type,
                        "trigger_price": tp.trigger_price,
                        "sell_percentage": tp.sell_percentage,
                        "is_triggered": tp.is_triggered,
                        "triggered_at": (
                            tp.triggered_at.isoformat() if tp.triggered_at else None
                        ),
                        "tx_signature": tp.tx_signature,
                    }
                    for tp in position.levels.take_profit_levels
                ],
                "trailing_stop_activation_price": (
                    position.levels.trailing_stop_activation_price
                ),
                "trailing_stop_current_price": (
                    position.levels.trailing_stop_current_price
                ),
                "moonbag_stop_price": position.levels.moonbag_stop_price,
            }

        return {
            "id": position.id,
            "signal_id": position.signal_id,
            "token_address": position.token_address,
            "token_symbol": position.token_symbol,
            "status": position.status.value,
            "entry_tx_signature": position.entry_tx_signature,
            "entry_price": position.entry_price,
            "entry_amount_sol": position.entry_amount_sol,
            "entry_amount_tokens": position.entry_amount_tokens,
            "entry_time": position.entry_time.isoformat(),
            "current_amount_tokens": position.current_amount_tokens,
            "realized_pnl_sol": position.realized_pnl_sol,
            "exit_strategy_id": position.exit_strategy_id,
            "conviction_tier": position.conviction_tier,
            "levels": levels_data,
            "is_moonbag": position.is_moonbag,
            "moonbag_percentage": position.moonbag_percentage,
            "exit_reason": (
                position.exit_reason.value if position.exit_reason else None
            ),
            "exit_time": (
                position.exit_time.isoformat() if position.exit_time else None
            ),
            "exit_price": position.exit_price,
            "exit_tx_signatures": position.exit_tx_signatures,
            "last_price_check": (
                position.last_price_check.isoformat()
                if position.last_price_check
                else None
            ),
            "peak_price": position.peak_price,
            "created_at": position.created_at.isoformat(),
            "updated_at": position.updated_at.isoformat(),
        }

    def _deserialize_position(self, data: dict) -> Position:
        """Deserialize position from database."""
        levels = None
        if data.get("levels"):
            lvl = data["levels"]
            tp_levels = [
                CalculatedLevel(
                    level_type=tp["level_type"],
                    trigger_price=tp["trigger_price"],
                    sell_percentage=tp["sell_percentage"],
                    is_triggered=tp.get("is_triggered", False),
                    triggered_at=(
                        datetime.fromisoformat(tp["triggered_at"])
                        if tp.get("triggered_at")
                        else None
                    ),
                    tx_signature=tp.get("tx_signature"),
                )
                for tp in lvl.get("take_profit_levels", [])
            ]
            levels = PositionLevels(
                entry_price=lvl["entry_price"],
                stop_loss_price=lvl["stop_loss_price"],
                take_profit_levels=tp_levels,
                trailing_stop_activation_price=lvl.get(
                    "trailing_stop_activation_price"
                ),
                trailing_stop_current_price=lvl.get("trailing_stop_current_price"),
                moonbag_stop_price=lvl.get("moonbag_stop_price"),
            )

        exit_reason = None
        if data.get("exit_reason"):
            exit_reason = ExitReason(data["exit_reason"])

        return Position(
            id=data["id"],
            signal_id=data["signal_id"],
            token_address=data["token_address"],
            token_symbol=data.get("token_symbol"),
            status=PositionStatus(data["status"]),
            entry_tx_signature=data.get("entry_tx_signature"),
            entry_price=float(data["entry_price"]),
            entry_amount_sol=float(data["entry_amount_sol"]),
            entry_amount_tokens=float(data["entry_amount_tokens"]),
            entry_time=datetime.fromisoformat(
                data["entry_time"].replace("Z", "+00:00")
            ),
            current_amount_tokens=float(data["current_amount_tokens"]),
            realized_pnl_sol=float(data.get("realized_pnl_sol", 0)),
            exit_strategy_id=data["exit_strategy_id"],
            conviction_tier=data["conviction_tier"],
            levels=levels,
            is_moonbag=data.get("is_moonbag", False),
            moonbag_percentage=float(data.get("moonbag_percentage", 0)),
            exit_reason=exit_reason,
            exit_time=(
                datetime.fromisoformat(data["exit_time"].replace("Z", "+00:00"))
                if data.get("exit_time")
                else None
            ),
            exit_price=float(data["exit_price"]) if data.get("exit_price") else None,
            exit_tx_signatures=data.get("exit_tx_signatures", []),
            last_price_check=(
                datetime.fromisoformat(
                    data["last_price_check"].replace("Z", "+00:00")
                )
                if data.get("last_price_check")
                else None
            ),
            peak_price=float(data["peak_price"]) if data.get("peak_price") else None,
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            updated_at=datetime.fromisoformat(
                data["updated_at"].replace("Z", "+00:00")
            ),
        )

    def _deserialize_execution(self, data: dict) -> ExitExecution:
        """Deserialize exit execution from database."""
        return ExitExecution(
            id=data["id"],
            position_id=data["position_id"],
            exit_reason=ExitReason(data["exit_reason"]),
            trigger_level=data["trigger_level"],
            sell_percentage=float(data["sell_percentage"]),
            amount_tokens_sold=float(data["amount_tokens_sold"]),
            amount_sol_received=float(data["amount_sol_received"]),
            exit_price=float(data["exit_price"]),
            tx_signature=data["tx_signature"],
            realized_pnl_sol=float(data["realized_pnl_sol"]),
            executed_at=datetime.fromisoformat(
                data["executed_at"].replace("Z", "+00:00")
            ),
        )


# Singleton
_repo: PositionRepository | None = None


async def get_position_repository() -> PositionRepository:
    """Get or create position repository singleton."""
    global _repo
    if _repo is None:
        from walltrack.data.supabase.client import (  # noqa: PLC0415
            get_supabase_client,
        )

        client = await get_supabase_client()
        _repo = PositionRepository(client)
    return _repo
