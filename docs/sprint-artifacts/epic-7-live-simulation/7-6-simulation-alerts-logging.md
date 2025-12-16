# Story 7.6: Simulation Alerts & Logging

## Story Info
- **Epic**: Epic 7 - Live Simulation (Paper Trading)
- **Status**: ready
- **Priority**: Medium
- **FR**: FR60

## User Story

**As an** operator,
**I want** simulation activity to be logged and alerts to be generated,
**So that** I can review simulation performance over time.

## Acceptance Criteria

### AC 1: Trade Logging
**Given** simulation mode is active
**When** any simulated trade occurs
**Then** detailed log entry is created
**And** log includes: signal, decision, simulated price, P&L
**And** logs are tagged with simulation=True

### AC 2: Circuit Breaker Tracking
**Given** circuit breaker would trigger in simulation
**When** threshold is reached
**Then** circuit breaker state is tracked separately
**And** alert is generated (marked as simulation)
**And** operator is notified of simulated circuit breaker

### AC 3: Daily Summary
**Given** simulation summary is requested
**When** daily summary runs
**Then** simulation performance report is generated
**And** comparison to live mode (if any) is included
**And** report is sent via configured alerts

### AC 4: Log Querying
**Given** historical simulation data
**When** operator queries logs
**Then** all simulated activity is retrievable
**And** filtering by date range is available
**And** export to CSV is available

## Technical Specifications

### Simulation Logger

**src/walltrack/core/simulation/logger.py:**
```python
"""Structured logging for simulation activity."""

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from typing import Optional
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
    """Logger for simulation events."""

    async def log_trade(
        self,
        token_address: str,
        side: str,
        amount: float,
        price: float,
        signal_id: Optional[str] = None,
        pnl: Optional[float] = None,
    ) -> None:
        """Log a simulated trade."""
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
            token=token_address,
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
        """Log a simulated circuit breaker event."""
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
        )

    async def log_signal_processed(
        self,
        signal_id: str,
        score: float,
        decision: str,
        reason: Optional[str] = None,
    ) -> None:
        """Log signal processing in simulation."""
        await self._log_event(
            event_type=SimulationEventType.SIGNAL_PROCESSED,
            data={
                "signal_id": signal_id,
                "score": score,
                "decision": decision,
                "reason": reason,
            },
        )

    async def _log_event(
        self,
        event_type: SimulationEventType,
        data: dict,
    ) -> None:
        """Store event in database."""
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
_simulation_logger: Optional[SimulationLogger] = None


async def get_simulation_logger() -> SimulationLogger:
    """Get simulation logger singleton."""
    global _simulation_logger
    if _simulation_logger is None:
        _simulation_logger = SimulationLogger()
    return _simulation_logger
```

### Daily Summary Generator

**src/walltrack/core/simulation/daily_summary.py:**
```python
"""Daily simulation summary generator."""

from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional

import structlog

from walltrack.core.simulation.pnl_calculator import get_pnl_calculator
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


async def generate_daily_summary() -> dict:
    """Generate daily simulation performance summary."""
    supabase = await get_supabase_client()
    pnl_calc = await get_pnl_calculator()

    # Get today's date range
    today = datetime.now(UTC).date()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    # Get trades from today
    trades = await supabase.select(
        "trades",
        filters={
            "simulated": True,
        },
    )
    today_trades = [
        t for t in trades
        if start <= datetime.fromisoformat(t["executed_at"]) <= end
    ]

    # Calculate metrics
    portfolio = await pnl_calc.calculate_portfolio_pnl(simulated=True)

    wins = [t for t in today_trades if t.get("pnl", 0) > 0]
    losses = [t for t in today_trades if t.get("pnl", 0) <= 0]

    summary = {
        "date": today.isoformat(),
        "trades_count": len(today_trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(today_trades) * 100 if today_trades else 0,
        "total_pnl": float(portfolio.total_pnl),
        "unrealized_pnl": float(portfolio.total_unrealized_pnl),
        "realized_pnl": float(portfolio.total_realized_pnl),
        "open_positions": portfolio.position_count,
    }

    log.info("daily_simulation_summary", **summary)

    return summary


async def send_summary_alert(summary: dict) -> None:
    """Send daily summary via configured alert channels."""
    from walltrack.config.settings import get_settings

    settings = get_settings()

    message = f"""
SIMULATION Daily Summary - {summary['date']}

Trades: {summary['trades_count']} ({summary['wins']}W / {summary['losses']}L)
Win Rate: {summary['win_rate']:.1f}%
Total P&L: ${summary['total_pnl']:.2f}
  - Realized: ${summary['realized_pnl']:.2f}
  - Unrealized: ${summary['unrealized_pnl']:.2f}
Open Positions: {summary['open_positions']}

This is a SIMULATION summary - no real trades were executed.
"""

    # Discord alert
    if settings.discord_webhook_url:
        await _send_discord_alert(settings.discord_webhook_url, message)

    # Telegram alert
    if settings.telegram_bot_token and settings.telegram_chat_id:
        await _send_telegram_alert(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            message,
        )


async def _send_discord_alert(webhook_url: str, message: str) -> None:
    """Send alert to Discord webhook."""
    import httpx

    async with httpx.AsyncClient() as client:
        await client.post(
            webhook_url,
            json={"content": f"```{message}```"},
        )


async def _send_telegram_alert(
    bot_token: str,
    chat_id: str,
    message: str,
) -> None:
    """Send alert to Telegram."""
    import httpx

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            json={"chat_id": chat_id, "text": message},
        )
```

## Database Schema

```sql
-- Simulation events table
CREATE TABLE IF NOT EXISTS simulation_events (
    id UUID PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    data JSONB NOT NULL,
    simulated BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sim_events_type ON simulation_events(event_type);
CREATE INDEX idx_sim_events_created ON simulation_events(created_at);
```

## Implementation Tasks

- [ ] Create SimulationLogger class
- [ ] Create simulation_events table
- [ ] Implement trade logging
- [ ] Implement circuit breaker logging
- [ ] Create daily summary generator
- [ ] Implement Discord/Telegram alerts
- [ ] Add scheduled daily summary job
- [ ] Write unit tests

## Definition of Done

- [ ] All simulation events are logged
- [ ] Circuit breaker tracking works
- [ ] Daily summary generates correctly
- [ ] Alerts are sent via configured channels
- [ ] Logs are queryable and exportable
- [ ] Tests cover all event types
