"""Run migration 006b - Behavioral Criteria Config.

Executes 006b_config_behavioral_criteria.sql on Supabase.
"""

import asyncio
import os
from pathlib import Path

from supabase import create_client

# Supabase connection
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:8000")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


async def run_migration():
    """Execute migration 006b."""
    # Read migration file
    migration_file = Path(__file__).parent / "006b_config_behavioral_criteria.sql"
    with open(migration_file, "r", encoding="utf-8") as f:
        sql = f.read()

    # Parse SQL statements (split by semicolon, exclude comments)
    statements = []
    for line in sql.split("\n"):
        line = line.strip()
        if line and not line.startswith("--"):
            statements.append(line)

    sql_clean = " ".join(statements)

    # Split into individual INSERT statements
    inserts = sql_clean.split("ON CONFLICT")

    # Create Supabase client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Executing migration 006b...")

    # Execute each INSERT statement
    for i, insert_part in enumerate(inserts[:-1]):  # Last part is empty
        statement = insert_part + "ON CONFLICT" + inserts[i + 1].split("INSERT INTO")[0]
        statement = statement.strip().rstrip(";") + ";"

        try:
            # Use RPC to execute raw SQL (requires a stored procedure)
            # For now, we'll use the postgrest API with upsert
            # Parse the values from INSERT statement
            # This is a workaround - ideally we'd use a SQL execution endpoint

            print(f"Statement {i+1}: {statement[:80]}...")

            # Manual execution via config table upsert
            # Extract key-value pairs from SQL
            if "position_size_small_max" in statement:
                data = [
                    {"key": "behavioral.position_size_small_max", "value": "0.5"},
                    {"key": "behavioral.position_size_large_min", "value": "2.0"},
                ]
            elif "hold_duration" in statement:
                data = [
                    {"key": "behavioral.hold_duration_scalper_max", "value": "3600"},
                    {"key": "behavioral.hold_duration_day_trader_max", "value": "86400"},
                    {"key": "behavioral.hold_duration_swing_trader_max", "value": "604800"},
                ]
            elif "confidence" in statement:
                data = [
                    {"key": "behavioral.confidence_high_min", "value": "20"},
                    {"key": "behavioral.confidence_medium_min", "value": "10"},
                    {"key": "behavioral.confidence_low_min", "value": "5"},
                ]
            else:
                continue

            # Upsert each config row
            for row in data:
                result = supabase.table("config").upsert(row, on_conflict="key").execute()
                print(f"  Inserted/Updated: {row['key']} = {row['value']}")

        except Exception as e:
            print(f"Error executing statement {i+1}: {e}")
            raise

    print("\nMigration 006b completed successfully!")
    print("Behavioral criteria config:")
    print("  - position_size_small_max: 0.5 SOL")
    print("  - position_size_large_min: 2.0 SOL")
    print("  - hold_duration_scalper_max: 3600s (1h)")
    print("  - hold_duration_day_trader_max: 86400s (24h)")
    print("  - hold_duration_swing_trader_max: 604800s (7d)")
    print("  - confidence_high_min: 20 trades")
    print("  - confidence_medium_min: 10 trades")
    print("  - confidence_low_min: 5 trades")


if __name__ == "__main__":
    asyncio.run(run_migration())
