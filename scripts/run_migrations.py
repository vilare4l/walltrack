#!/usr/bin/env python3
"""
Run Supabase migrations for WallTrack V2.

Usage:
    uv run python scripts/run_migrations.py
    uv run python scripts/run_migrations.py --check  # Verify only, don't apply
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncpg
from dotenv import load_dotenv


async def get_connection() -> asyncpg.Connection:
    """Get database connection from DATABASE_URL."""
    load_dotenv()

    # Try DATABASE_URL first, fallback to transaction pooler
    database_url = os.getenv("DATABASE_URL")

    # Default to transaction pooler (port 6543) for Supabase
    if not database_url:
        database_url = "postgresql://postgres.localhost:postgres@localhost:6543/postgres"

    # If using session pooler (5432), switch to transaction pooler (6543)
    if ":5432/" in database_url or ":5432?" in database_url:
        database_url = database_url.replace(":5432", ":6543")
        print("NOTE: Switched from port 5432 to 6543 (transaction pooler)")

    print(f"Connecting to: {database_url.split('@')[1] if '@' in database_url else database_url}")
    return await asyncpg.connect(database_url)


async def check_table_exists(conn: asyncpg.Connection, schema: str, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = $1 AND table_name = $2
        )
        """,
        schema,
        table_name,
    )
    return bool(result)


async def run_migration(conn: asyncpg.Connection, migration_path: Path) -> None:
    """Execute a single migration file."""
    print(f"\n{'='*60}")
    print(f"Running: {migration_path.name}")
    print("=" * 60)

    sql = migration_path.read_text(encoding="utf-8")

    # Execute the migration
    await conn.execute(sql)
    print(f"SUCCESS: {migration_path.name} applied")


async def run_all_migrations(check_only: bool = False) -> None:
    """Run all pending migrations."""
    migrations_dir = Path(__file__).parent.parent / "src/walltrack/data/supabase/migrations"

    if not migrations_dir.exists():
        print(f"ERROR: Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    # Get all SQL files sorted by name
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found")
        return

    print(f"\nFound {len(migration_files)} migration(s):")
    for mf in migration_files:
        print(f"  - {mf.name}")

    conn = await get_connection()

    try:
        for migration_file in migration_files:
            if check_only:
                print(f"\n[CHECK] Would apply: {migration_file.name}")
            else:
                await run_migration(conn, migration_file)

        # Verify tables exist
        print("\n" + "=" * 60)
        print("Verification")
        print("=" * 60)

        tables_to_check = ["config", "tokens"]
        for table in tables_to_check:
            exists = await check_table_exists(conn, "walltrack", table)
            status = "EXISTS" if exists else "MISSING"
            print(f"  Table 'walltrack.{table}': {status}")

    finally:
        await conn.close()


async def main() -> None:
    """Main entry point."""
    check_only = "--check" in sys.argv

    if check_only:
        print("CHECK MODE: Will not apply migrations")

    await run_all_migrations(check_only=check_only)

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
