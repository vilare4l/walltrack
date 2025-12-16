# Story 7.2: Simulated Trade Executor

## Story Info
- **Epic**: Epic 7 - Live Simulation (Paper Trading)
- **Status**: ready
- **Priority**: High
- **FR**: FR56

## User Story

**As an** operator,
**I want** trades to be simulated realistically when in simulation mode,
**So that** I get accurate performance estimates.

## Acceptance Criteria

### AC 1: Executor Selection
**Given** simulation mode is active
**When** trade execution is triggered
**Then** SimulatedTradeExecutor is used instead of JupiterExecutor
**And** trade is recorded with simulated=True flag
**And** execution price uses real-time market price

### AC 2: Buy Simulation
**Given** a buy signal in simulation
**When** simulated trade executes
**Then** current token price is fetched from DexScreener
**And** slippage is simulated (configurable, default 1%)
**And** entry price = market_price * (1 + slippage)
**And** trade record is created

### AC 3: Sell Simulation
**Given** a sell signal in simulation
**When** simulated trade executes
**Then** current token price is fetched
**And** slippage is simulated
**And** exit price = market_price * (1 - slippage)
**And** P&L is calculated from simulated entry

### AC 4: Trade Recording
**Given** simulated trade completes
**When** trade is logged
**Then** all standard trade fields are populated
**And** simulated=True is clearly marked
**And** no blockchain transaction is created

## Technical Specifications

### Simulated Trade Executor

**src/walltrack/core/simulation/simulated_executor.py:**
```python
"""Simulated trade executor for paper trading."""

from datetime import datetime, UTC
from decimal import Decimal
from uuid import uuid4

import structlog

from walltrack.config.settings import get_settings
from walltrack.core.trading.executor_factory import TradeExecutor
from walltrack.data.supabase.client import get_supabase_client
from walltrack.integrations.dexscreener.client import get_dexscreener_client

log = structlog.get_logger()


class SimulatedTradeExecutor(TradeExecutor):
    """Execute simulated trades using real market prices."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._slippage_bps = self._settings.simulation_slippage_bps

    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        slippage_bps: int | None = None,
    ) -> dict:
        """Simulate a buy trade."""
        slippage = slippage_bps or self._slippage_bps

        # Get current market price
        dex_client = await get_dexscreener_client()
        token_data = await dex_client.get_token_info(token_address)

        if not token_data or not token_data.price_usd:
            raise ValueError(f"Cannot get price for token {token_address}")

        market_price = Decimal(str(token_data.price_usd))

        # Apply slippage (worse price for buyer)
        slippage_multiplier = Decimal(1) + Decimal(slippage) / Decimal(10000)
        execution_price = market_price * slippage_multiplier

        # Calculate tokens received
        sol_price_usd = await self._get_sol_price()
        usd_amount = Decimal(str(amount_sol)) * sol_price_usd
        tokens_received = usd_amount / execution_price

        # Create trade record
        trade_id = str(uuid4())
        trade_record = {
            "id": trade_id,
            "token_address": token_address,
            "side": "buy",
            "amount_sol": amount_sol,
            "amount_tokens": float(tokens_received),
            "price_usd": float(execution_price),
            "slippage_bps": slippage,
            "simulated": True,
            "tx_signature": f"SIM_{trade_id[:8]}",
            "executed_at": datetime.now(UTC).isoformat(),
            "market_price_at_execution": float(market_price),
        }

        # Store trade
        supabase = await get_supabase_client()
        await supabase.insert("trades", trade_record)

        log.info(
            "simulated_buy_executed",
            token=token_address,
            amount_sol=amount_sol,
            tokens_received=float(tokens_received),
            price=float(execution_price),
        )

        return trade_record

    async def execute_sell(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_bps: int | None = None,
    ) -> dict:
        """Simulate a sell trade."""
        slippage = slippage_bps or self._slippage_bps

        # Get current market price
        dex_client = await get_dexscreener_client()
        token_data = await dex_client.get_token_info(token_address)

        if not token_data or not token_data.price_usd:
            raise ValueError(f"Cannot get price for token {token_address}")

        market_price = Decimal(str(token_data.price_usd))

        # Apply slippage (worse price for seller)
        slippage_multiplier = Decimal(1) - Decimal(slippage) / Decimal(10000)
        execution_price = market_price * slippage_multiplier

        # Calculate SOL received
        usd_amount = Decimal(str(amount_tokens)) * execution_price
        sol_price_usd = await self._get_sol_price()
        sol_received = usd_amount / sol_price_usd

        # Create trade record
        trade_id = str(uuid4())
        trade_record = {
            "id": trade_id,
            "token_address": token_address,
            "side": "sell",
            "amount_sol": float(sol_received),
            "amount_tokens": amount_tokens,
            "price_usd": float(execution_price),
            "slippage_bps": slippage,
            "simulated": True,
            "tx_signature": f"SIM_{trade_id[:8]}",
            "executed_at": datetime.now(UTC).isoformat(),
            "market_price_at_execution": float(market_price),
        }

        # Store trade
        supabase = await get_supabase_client()
        await supabase.insert("trades", trade_record)

        log.info(
            "simulated_sell_executed",
            token=token_address,
            amount_tokens=amount_tokens,
            sol_received=float(sol_received),
            price=float(execution_price),
        )

        return trade_record

    async def _get_sol_price(self) -> Decimal:
        """Get current SOL price in USD."""
        dex_client = await get_dexscreener_client()
        # SOL address on Solana
        sol_data = await dex_client.get_token_info(
            "So11111111111111111111111111111111111111112"
        )
        return Decimal(str(sol_data.price_usd)) if sol_data else Decimal("100")
```

### Trade Model Extension

**Add to trades table:**
```sql
ALTER TABLE trades ADD COLUMN simulated BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN market_price_at_execution DECIMAL(20, 10);
```

## Implementation Tasks

- [ ] Create simulated_executor.py
- [ ] Add simulated column to trades table
- [ ] Implement execute_buy with price fetching
- [ ] Implement execute_sell with price fetching
- [ ] Add SOL price fetching helper
- [ ] Write unit tests with mocked prices
- [ ] Integration test with DexScreener

## Definition of Done

- [ ] Simulated trades use real market prices
- [ ] Slippage is applied correctly
- [ ] All trades marked with simulated=True
- [ ] No actual blockchain transactions
- [ ] Trades stored in database
- [ ] Tests pass with mocked price data
