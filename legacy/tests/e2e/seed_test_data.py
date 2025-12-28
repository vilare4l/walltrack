"""Seed test data for E2E testing.

This script creates realistic test data directly in the database
for testing the UI display and order management.
"""

import asyncio
import os
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import structlog

# Set simulation mode at start (lowercase as required by enum)
os.environ["EXECUTION_MODE"] = "simulation"

# Configure logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
)
log = structlog.get_logger()

# Sample data
SAMPLE_TOKENS = [
    {"address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "symbol": "BONK"},
    {"address": "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr", "symbol": "POPCAT"},
    {"address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "symbol": "WIF"},
    {"address": "HeLp6NuQkmYB4pYWo2zYs22mESHXPQYzXbB8n4V98jwC", "symbol": "AI16Z"},
    {"address": "ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82", "symbol": "BOME"},
]

SAMPLE_WALLETS = [
    "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK",
    "FuEFBbzJjHJz7aJGnrfYKLbkXL7xLPvWfQsHJRyHT3VY",
]


async def seed_wallets():
    """Seed tracked wallets using proper schema."""
    from walltrack.data.supabase.client import get_supabase_client

    client = await get_supabase_client()

    log.info("seeding_wallets", count=len(SAMPLE_WALLETS))

    for address in SAMPLE_WALLETS:
        try:
            # Check if wallet exists
            result = await client.table("wallets").select("address").eq("address", address).execute()
            if result.data:
                log.info("wallet_exists", address=address[:16])
                continue

            # Insert using actual schema columns
            wallet_data = {
                "address": address,
                "status": "active",
                "score": random.uniform(0.6, 0.95),
                "win_rate": 0.65 + random.uniform(-0.1, 0.15),
                "total_pnl": random.uniform(10, 100),
                "avg_pnl_per_trade": random.uniform(0.5, 5.0),
                "total_trades": 50 + random.randint(0, 100),
                "timing_percentile": random.uniform(0.5, 0.9),
                "avg_hold_time_hours": random.uniform(2, 24),
                "avg_position_size_sol": random.uniform(0.5, 2.5),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            await client.table("wallets").insert(wallet_data).execute()
            log.info("wallet_created", address=address[:16])
        except Exception as e:
            log.warning("wallet_error", address=address[:16], error=str(e))


async def seed_signals():
    """Seed signal log entries."""
    from walltrack.data.supabase.client import get_supabase_client

    client = await get_supabase_client()

    log.info("seeding_signals", count=10)

    for i in range(10):
        token = random.choice(SAMPLE_TOKENS)
        wallet = random.choice(SAMPLE_WALLETS)

        # Use actual schema columns from signals table
        signal_data = {
            "id": str(uuid4()),
            "tx_signature": f"sig_{uuid4().hex[:44]}",
            "wallet_address": wallet,
            "token_address": token["address"],
            "direction": "buy",
            "amount_token": random.randint(100000, 10000000),
            "amount_sol": float(Decimal(str(random.uniform(0.5, 3.0))).quantize(Decimal("0.0001"))),
            "slot": 250000000 + random.randint(1, 1000000),
            "final_score": random.uniform(0.6, 0.95),
            "wallet_score": random.uniform(0.5, 0.95),
            "cluster_score": random.uniform(0.4, 0.85),
            "token_score": random.uniform(0.4, 0.9),
            "context_score": random.uniform(0.5, 0.9),
            "status": "processed",
            "eligibility_status": "trade_eligible",
            "conviction_tier": random.choice(["high", "standard"]),
            "filter_status": "passed",
            "timestamp": (datetime.now(UTC) - timedelta(hours=random.randint(1, 72))).isoformat(),
            "received_at": datetime.now(UTC).isoformat(),
            "processing_time_ms": random.uniform(50, 200),
            "created_at": datetime.now(UTC).isoformat(),
        }

        try:
            await client.table("signals").insert(signal_data).execute()
            log.info("signal_created", token=token["symbol"], score=signal_data["final_score"])
        except Exception as e:
            log.warning("signal_error", error=str(e))


async def seed_positions():
    """Seed positions with various statuses."""
    from walltrack.data.supabase.client import get_supabase_client

    client = await get_supabase_client()

    log.info("seeding_positions")

    positions = []

    # Active positions with realistic data
    for i in range(3):
        token = SAMPLE_TOKENS[i]
        entry_price = Decimal(str(random.uniform(0.0001, 0.01)))
        current_multiplier = random.uniform(0.8, 2.5)
        current_price = entry_price * Decimal(str(current_multiplier))
        entry_sol = Decimal(str(random.uniform(0.5, 2.0))).quantize(Decimal("0.0001"))
        tokens_amount = Decimal(str(float(entry_sol) / float(entry_price))).quantize(Decimal("0.01"))

        position = {
            "id": str(uuid4()),
            "token_address": token["address"],
            "token_symbol": token["symbol"],
            "wallet_address": SAMPLE_WALLETS[i % len(SAMPLE_WALLETS)],
            "status": "open",
            "entry_price": str(entry_price),
            "current_price": str(current_price),
            "entry_amount_sol": str(entry_sol),
            "entry_amount_tokens": str(tokens_amount),
            "current_amount_tokens": str(tokens_amount),
            "entry_time": (datetime.now(UTC) - timedelta(hours=random.randint(2, 48))).isoformat(),
            "conviction_tier": random.choice(["high", "standard"]),
            "unrealized_pnl": float(current_price - entry_price) * float(tokens_amount),
            "realized_pnl": 0,
            "simulated": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        positions.append(position)

    # Closed positions with profit
    for i in range(2):
        token = SAMPLE_TOKENS[i + 3]
        entry_price = Decimal(str(random.uniform(0.0001, 0.005)))
        exit_price = entry_price * Decimal(str(random.uniform(1.5, 3.0)))
        entry_sol = Decimal(str(random.uniform(0.5, 1.5))).quantize(Decimal("0.0001"))
        tokens_amount = Decimal(str(float(entry_sol) / float(entry_price))).quantize(Decimal("0.01"))

        position = {
            "id": str(uuid4()),
            "token_address": token["address"],
            "token_symbol": token["symbol"],
            "wallet_address": SAMPLE_WALLETS[i % len(SAMPLE_WALLETS)],
            "status": "closed",
            "entry_price": str(entry_price),
            "exit_price": str(exit_price),
            "current_price": str(exit_price),
            "entry_amount_sol": str(entry_sol),
            "entry_amount_tokens": str(tokens_amount),
            "current_amount_tokens": "0",
            "exit_reason": random.choice(["take_profit", "trailing_stop"]),
            "conviction_tier": "standard",
            "unrealized_pnl": 0,
            "realized_pnl": float(exit_price - entry_price) * float(tokens_amount),
            "realized_pnl_sol": float((exit_price - entry_price) * Decimal(str(float(entry_sol) / float(entry_price)))),
            "simulated": True,
            "entry_time": (datetime.now(UTC) - timedelta(hours=random.randint(48, 120))).isoformat(),
            "exit_time": (datetime.now(UTC) - timedelta(hours=random.randint(12, 47))).isoformat(),
            "closed_at": (datetime.now(UTC) - timedelta(hours=random.randint(12, 47))).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        positions.append(position)

    for pos in positions:
        try:
            await client.table("positions").insert(pos).execute()
            log.info("position_created", token=pos["token_symbol"], status=pos["status"])
        except Exception as e:
            log.warning("position_error", token=pos.get("token_symbol"), error=str(e))


async def seed_trades():
    """Seed trades (orders) table."""
    from walltrack.data.supabase.client import get_supabase_client

    client = await get_supabase_client()

    log.info("seeding_trades")

    # Check if trades table has data
    try:
        result = await client.table("trades").select("*").limit(1).execute()
        log.info("trades_table_check", has_data=bool(result.data))
    except Exception as e:
        log.warning("trades_table_not_available", error=str(e))
        return

    # Note: trades table may have different schema - skip for now if errors


async def seed_exit_strategies():
    """Seed exit strategies."""
    from walltrack.data.supabase.client import get_supabase_client

    client = await get_supabase_client()

    log.info("seeding_exit_strategies")

    # First check what columns exist
    try:
        result = await client.table("exit_strategies").select("*").limit(1).execute()
        # Table exists, try inserting
    except Exception as e:
        log.warning("exit_strategies_not_available", error=str(e))
        return

    strategies = [
        {
            "id": str(uuid4()),
            "name": "Conservative",
            "description": "Low risk strategy with tight stop loss",
            "version": 1,
            "status": "active",
            "max_hold_hours": 24,
            "stagnation_hours": 4,
            "stagnation_threshold_pct": 1.5,
            "rules": [
                {"rule_type": "stop_loss", "trigger_pct": -8, "exit_pct": 100, "priority": 0, "enabled": True},
                {"rule_type": "take_profit", "trigger_pct": 15, "exit_pct": 50, "priority": 1, "enabled": True},
                {"rule_type": "take_profit", "trigger_pct": 30, "exit_pct": 100, "priority": 2, "enabled": True},
            ],
            "created_at": datetime.now(UTC).isoformat(),
        },
        {
            "id": str(uuid4()),
            "name": "Aggressive Moon",
            "description": "High risk strategy for moonshots",
            "version": 1,
            "status": "active",
            "max_hold_hours": 72,
            "stagnation_hours": 12,
            "stagnation_threshold_pct": 3.0,
            "rules": [
                {"rule_type": "stop_loss", "trigger_pct": -15, "exit_pct": 100, "priority": 0, "enabled": True},
                {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 25, "priority": 1, "enabled": True},
                {"rule_type": "take_profit", "trigger_pct": 100, "exit_pct": 50, "priority": 2, "enabled": True},
                {"rule_type": "trailing_stop", "trigger_pct": -10, "exit_pct": 100, "priority": 3, "enabled": True},
            ],
            "created_at": datetime.now(UTC).isoformat(),
        },
        {
            "id": str(uuid4()),
            "name": "Draft Strategy",
            "description": "Work in progress",
            "version": 1,
            "status": "draft",
            "max_hold_hours": 48,
            "rules": [
                {"rule_type": "stop_loss", "trigger_pct": -10, "exit_pct": 100, "priority": 0, "enabled": True},
            ],
            "created_at": datetime.now(UTC).isoformat(),
        },
    ]

    for strategy in strategies:
        try:
            await client.table("exit_strategies").insert(strategy).execute()
            log.info("strategy_created", name=strategy["name"], status=strategy["status"])
        except Exception as e:
            log.warning("strategy_error", name=strategy.get("name"), error=str(e))


async def main():
    """Seed all test data."""
    print("\n" + "#" * 60)
    print("# WallTrack E2E - Data Seeding")
    print("#" * 60)

    try:
        await seed_wallets()
        await seed_signals()
        await seed_positions()
        await seed_trades()
        await seed_exit_strategies()

        print("\n" + "=" * 60)
        print("DATA SEEDING COMPLETE")
        print("=" * 60)
        print("\nYou can now:")
        print("1. Start the Gradio UI: uv run python -m walltrack.ui.dashboard")
        print("2. Navigate to http://localhost:7860")
        print("3. Check the Home, Explorer, and Exit Strategies pages")

    except Exception as e:
        print(f"\nERROR: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
