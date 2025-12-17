"""Trade repository."""

from datetime import datetime
from typing import Any

import structlog

from walltrack.data.models.trade import Trade, TradeResult, TradeStatus
from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger()


class TradeRepository:
    """Repository for trade data access."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "trades"

    async def get_by_id(self, trade_id: str) -> Trade | None:
        """Get trade by ID."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("id", trade_id)
            .maybe_single()
            .execute()
        )

        if not response.data:
            return None

        return self._row_to_trade(response.data)

    async def get_wallet_trades(
        self,
        wallet_address: str,
        limit: int = 100,
        order_by: str = "exit_at",
        order_desc: bool = True,
    ) -> list[Trade]:
        """
        Get trades for a wallet.

        Args:
            wallet_address: Wallet address
            limit: Maximum number of trades
            order_by: Field to sort by
            order_desc: Sort descending if True

        Returns:
            List of trades
        """
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("wallet_address", wallet_address)
            .eq("status", TradeStatus.FILLED.value)
            .order(order_by, desc=order_desc)
            .limit(limit)
            .execute()
        )

        return [self._row_to_trade(row) for row in response.data]

    async def get_recent_trades(
        self,
        wallet_address: str,
        since: datetime,
        limit: int = 100,
    ) -> list[Trade]:
        """Get trades since a specific time."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("wallet_address", wallet_address)
            .eq("status", TradeStatus.FILLED.value)
            .gte("exit_at", since.isoformat())
            .order("exit_at", desc=True)
            .limit(limit)
            .execute()
        )

        return [self._row_to_trade(row) for row in response.data]

    async def create(self, trade: Trade) -> Trade:
        """Create a new trade."""
        data = self._trade_to_row(trade)
        response = await (
            self.client.table(self.table)
            .insert(data)
            .execute()
        )

        return self._row_to_trade(response.data[0])

    async def update(self, trade: Trade) -> Trade:
        """Update an existing trade."""
        data = self._trade_to_row(trade)
        data["updated_at"] = datetime.utcnow().isoformat()

        response = await (
            self.client.table(self.table)
            .update(data)
            .eq("id", trade.id)
            .execute()
        )

        return self._row_to_trade(response.data[0])

    async def count_by_wallet(
        self,
        wallet_address: str,
        result: TradeResult | None = None,
    ) -> int:
        """Count trades for a wallet."""
        query = (
            self.client.table(self.table)
            .select("*", count="exact")
            .eq("wallet_address", wallet_address)
            .eq("status", TradeStatus.FILLED.value)
        )

        if result:
            query = query.eq("result", result.value)

        response = await query.execute()
        return response.count or 0

    def _trade_to_row(self, trade: Trade) -> dict[str, Any]:
        """Convert Trade to database row."""
        return {
            "id": trade.id,
            "signal_id": trade.signal_id,
            "wallet_address": trade.wallet_address,
            "token_address": trade.token_address,
            "token_symbol": trade.token_symbol,
            "side": trade.side,
            "status": trade.status.value,
            "result": trade.result.value,
            "entry_amount_sol": trade.entry_amount_sol,
            "entry_price": trade.entry_price,
            "entry_tx": trade.entry_tx,
            "entry_at": trade.entry_at.isoformat() if trade.entry_at else None,
            "exit_amount_sol": trade.exit_amount_sol,
            "exit_price": trade.exit_price,
            "exit_tx": trade.exit_tx,
            "exit_at": trade.exit_at.isoformat() if trade.exit_at else None,
            "pnl_sol": trade.pnl_sol,
            "pnl_percent": trade.pnl_percent,
            "exit_strategy": trade.exit_strategy,
            "moonbag_remaining": trade.moonbag_remaining,
            "score_at_entry": trade.score_at_entry,
        }

    def _row_to_trade(self, row: dict[str, Any]) -> Trade:
        """Convert database row to Trade."""
        return Trade(
            id=row["id"],
            signal_id=row["signal_id"],
            wallet_address=row["wallet_address"],
            token_address=row["token_address"],
            token_symbol=row.get("token_symbol"),
            side=row["side"],
            status=TradeStatus(row["status"]),
            result=TradeResult(row["result"]),
            entry_amount_sol=row["entry_amount_sol"],
            entry_price=row.get("entry_price"),
            entry_tx=row.get("entry_tx"),
            entry_at=(
                datetime.fromisoformat(row["entry_at"])
                if row.get("entry_at")
                else None
            ),
            exit_amount_sol=row.get("exit_amount_sol"),
            exit_price=row.get("exit_price"),
            exit_tx=row.get("exit_tx"),
            exit_at=(
                datetime.fromisoformat(row["exit_at"])
                if row.get("exit_at")
                else None
            ),
            pnl_sol=row.get("pnl_sol"),
            pnl_percent=row.get("pnl_percent"),
            exit_strategy=row.get("exit_strategy", "balanced"),
            moonbag_remaining=row.get("moonbag_remaining", 0),
            score_at_entry=row.get("score_at_entry"),
            created_at=(
                datetime.fromisoformat(row["created_at"])
                if row.get("created_at")
                else datetime.utcnow()
            ),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row.get("updated_at")
                else datetime.utcnow()
            ),
        )
