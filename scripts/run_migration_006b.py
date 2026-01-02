"""Execute migration 006b - Behavioral Criteria Config."""

import asyncio

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.config_repo import ConfigRepository


async def run_migration():
    """Execute migration 006b by inserting behavioral criteria."""
    client = await get_supabase_client()
    repo = ConfigRepository(client)

    print("Executing migration 006b: Behavioral Criteria Config...")

    # Position Size Thresholds
    await repo.set_value("behavioral.position_size_small_max", "0.5")
    await repo.set_value("behavioral.position_size_large_min", "2.0")
    print("  Position size thresholds inserted")

    # Hold Duration Thresholds (seconds)
    await repo.set_value("behavioral.hold_duration_scalper_max", "3600")
    await repo.set_value("behavioral.hold_duration_day_trader_max", "86400")
    await repo.set_value("behavioral.hold_duration_swing_trader_max", "604800")
    print("  Hold duration thresholds inserted")

    # Confidence Level Thresholds (number of trades)
    await repo.set_value("behavioral.confidence_high_min", "20")
    await repo.set_value("behavioral.confidence_medium_min", "10")
    await repo.set_value("behavioral.confidence_low_min", "5")
    print("  Confidence level thresholds inserted")

    print("\n✅ Migration 006b completed successfully!")
    print("\nBehavioral criteria configured:")
    print("  Position Size:")
    print("    - Small: ≤ 0.5 SOL")
    print("    - Medium: 0.5 - 2.0 SOL")
    print("    - Large: > 2.0 SOL")
    print("  Hold Duration:")
    print("    - Scalper: ≤ 3600s (1h)")
    print("    - Day Trader: 3600s - 86400s (24h)")
    print("    - Swing Trader: 86400s - 604800s (7d)")
    print("    - Position Trader: > 604800s")
    print("  Confidence:")
    print("    - High: ≥ 20 trades")
    print("    - Medium: 10-19 trades")
    print("    - Low: 5-9 trades")
    print("    - Unknown: < 5 trades")


if __name__ == "__main__":
    asyncio.run(run_migration())
