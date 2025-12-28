"""Structured logging for simulation activity."""

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

import structlog

from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


class SimulationEventType(str, Enum):
    """Types of simulation events."""

    TRADE_EXECUTED = "trade_executed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    STOP_LOSS_HIT = "stop_loss_hit"
    TAKE_PROFIT_HIT = "take_profit_hit"
    CIRCUIT_BREAKER = "circuit_breaker"
    SIGNAL_PROCESSED = "signal_processed"
    DAILY_SUMMARY = "daily_summary"


class SimulationLogger:
    """Logger for simulation events.

    Stores structured events in the simulation_events table for tracking
    and analysis of paper trading activity.
    """

    async def log_trade(
        self,
        token_address: str,
        side: str,
        amount: float,
        price: float,
        signal_id: str | None = None,
        pnl: float | None = None,
    ) -> None:
        """Log a simulated trade.

        Args:
            token_address: Token mint address
            side: "buy" or "sell"
            amount: Trade amount
            price: Execution price
            signal_id: Optional source signal ID
            pnl: Optional P&L for this trade
        """
        await self._log_event(
            event_type=SimulationEventType.TRADE_EXECUTED,
            data={
                "token_address": token_address,
                "side": side,
                "amount": amount,
                "price": price,
                "signal_id": signal_id,
                "pnl": pnl,
            },
        )

        log.info(
            "simulation_trade_logged",
            token=token_address[:8],
            side=side,
            amount=amount,
            price=price,
        )

    async def log_circuit_breaker(
        self,
        breaker_type: str,
        trigger_value: float,
        threshold: float,
        action: str,
    ) -> None:
        """Log a simulated circuit breaker event.

        Args:
            breaker_type: Type of breaker (drawdown, consecutive_loss, etc.)
            trigger_value: Value that triggered the breaker
            threshold: Configured threshold
            action: Action taken (pause, reduce, etc.)
        """
        await self._log_event(
            event_type=SimulationEventType.CIRCUIT_BREAKER,
            data={
                "breaker_type": breaker_type,
                "trigger_value": trigger_value,
                "threshold": threshold,
                "action": action,
            },
        )

        log.warning(
            "simulation_circuit_breaker",
            breaker_type=breaker_type,
            trigger_value=trigger_value,
            threshold=threshold,
            action=action,
        )

    async def log_signal_processed(
        self,
        signal_id: str,
        score: float,
        decision: str,
        reason: str | None = None,
    ) -> None:
        """Log signal processing in simulation.

        Args:
            signal_id: Signal ID
            score: Signal score
            decision: Decision made (trade, skip, etc.)
            reason: Optional reason for decision
        """
        await self._log_event(
            event_type=SimulationEventType.SIGNAL_PROCESSED,
            data={
                "signal_id": signal_id,
                "score": score,
                "decision": decision,
                "reason": reason,
            },
        )

        log.info(
            "simulation_signal_processed",
            signal_id=signal_id[:8] if signal_id else None,
            score=score,
            decision=decision,
        )

    async def log_position_opened(
        self,
        position_id: str,
        token_address: str,
        entry_price: float,
        amount: float,
    ) -> None:
        """Log position opening in simulation.

        Args:
            position_id: Position ID
            token_address: Token mint address
            entry_price: Entry price
            amount: Position amount
        """
        await self._log_event(
            event_type=SimulationEventType.POSITION_OPENED,
            data={
                "position_id": position_id,
                "token_address": token_address,
                "entry_price": entry_price,
                "amount": amount,
            },
        )

    async def log_position_closed(
        self,
        position_id: str,
        exit_price: float,
        pnl: float,
        reason: str,
    ) -> None:
        """Log position closing in simulation.

        Args:
            position_id: Position ID
            exit_price: Exit price
            pnl: Realized P&L
            reason: Exit reason
        """
        await self._log_event(
            event_type=SimulationEventType.POSITION_CLOSED,
            data={
                "position_id": position_id,
                "exit_price": exit_price,
                "pnl": pnl,
                "reason": reason,
            },
        )

    async def _log_event(
        self,
        event_type: SimulationEventType,
        data: dict,
    ) -> None:
        """Store event in database.

        Args:
            event_type: Type of simulation event
            data: Event data dictionary
        """
        supabase = await get_supabase_client()

        record = {
            "id": str(uuid4()),
            "event_type": event_type.value,
            "data": data,
            "simulated": True,
            "created_at": datetime.now(UTC).isoformat(),
        }

        await supabase.insert("simulation_events", record)


# Singleton
_simulation_logger: SimulationLogger | None = None


async def get_simulation_logger() -> SimulationLogger:
    """Get simulation logger singleton."""
    global _simulation_logger
    if _simulation_logger is None:
        _simulation_logger = SimulationLogger()
    return _simulation_logger
