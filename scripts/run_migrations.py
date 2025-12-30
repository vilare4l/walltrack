#!/usr/bin/env python3
"""
Run Supabase migrations for WallTrack V2.

Tracks executed migrations in walltrack.schema_migrations table.
Only runs NEW migrations that haven't been executed yet.

Usage:
    uv run python scripts/run_migrations.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import asyncpg
from dotenv import load_dotenv


async def get_connection() -> asyncpg.Connection:
    """Get database connection from DATABASE_URL."""
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = "postgresql://postgres.localhost:postgres@localhost:6543/postgres"

    if ":5432/" in database_url or ":5432?" in database_url:
        database_url = database_url.replace(":5432", ":6543")

    print(f"📡 Connecting to: {database_url.split('@')[1] if '@' in database_url else database_url}")
    return await asyncpg.connect(database_url)


async def ensure_migrations_table(conn: asyncpg.Connection) -> None:
    """Create migrations tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE SCHEMA IF NOT EXISTS walltrack;

        CREATE TABLE IF NOT EXISTS walltrack.schema_migrations (
            version VARCHAR(255) PRIMARY KEY,
            executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)


async def get_executed_migrations(conn: asyncpg.Connection) -> set[str]:
    """Get list of already executed migration versions."""
    rows = await conn.fetch("SELECT version FROM walltrack.schema_migrations ORDER BY version")
    return {row['version'] for row in rows}


async def mark_migration_executed(conn: asyncpg.Connection, version: str) -> None:
    """Mark a migration as executed."""
    await conn.execute(
        "INSERT INTO walltrack.schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
        version
    )


async def run_migration(conn: asyncpg.Connection, migration_path: Path) -> None:
    """Execute a single migration file."""
    version = migration_path.stem  # e.g., "001_config"

    print(f"  ⏳ Executing: {migration_path.name}")

    sql = migration_path.read_text(encoding="utf-8")

    # Execute in transaction
    async with conn.transaction():
        await conn.execute(sql)
        await mark_migration_executed(conn, version)

    print(f"  ✅ Success: {migration_path.name}")


async def run_all_migrations() -> None:
    """Run all pending migrations."""
    migrations_dir = Path(__file__).parent.parent / "src/walltrack/data/supabase/migrations"

    if not migrations_dir.exists():
        print(f"❌ Migrations directory not found: {migrations_dir}")
        sys.exit(1)

    # Get all SQL files sorted by name
    all_migrations = sorted(migrations_dir.glob("*.sql"))

    if not all_migrations:
        print("❌ No migration files found")
        return

    print(f"\n{'='*60}")
    print(f"🔧 WallTrack Migration Runner")
    print(f"{'='*60}\n")

    conn = await get_connection()

    try:
        # Ensure tracking table exists
        await ensure_migrations_table(conn)

        # Get executed migrations
        executed = await get_executed_migrations(conn)
        print(f"📊 Already executed: {len(executed)} migrations")

        # Find pending migrations
        pending = [m for m in all_migrations if m.stem not in executed]

        if not pending:
            print("✨ All migrations up to date!\n")
            return

        print(f"📋 Pending: {len(pending)} migrations\n")
        print("🚀 Executing pending migrations:\n")

        # Execute pending migrations
        for migration_file in pending:
            await run_migration(conn, migration_file)

        print(f"\n{'='*60}")
        print(f"✨ Success: {len(pending)} new migration(s) executed")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


async def main() -> None:
    """Main entry point."""
    await run_all_migrations()


if __name__ == "__main__":
    asyncio.run(main())
