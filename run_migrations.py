"""
Execute WallTrack database migrations on local Supabase instance.
Story 1.1: Database Schema Migration & Mock Data
"""

import psycopg2
from pathlib import Path
import sys

# Database connection
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"

# Migration files in order
MIGRATIONS_DIR = Path("src/walltrack/data/supabase/migrations")
MIGRATION_FILES = [
    "000_helper_functions.sql",
    "001_config_table.sql",
    "002_exit_strategies_table.sql",
    "003_wallets_table.sql",
    "004_tokens_table.sql",
    "005_signals_table.sql",
    "006_orders_table.sql",
    "007_positions_table.sql",
    "008_performance_table.sql",
    "009_circuit_breaker_events_table.sql",
]


def execute_migration(cursor, migration_file: Path):
    """Execute a single migration file."""
    print(f"\n{'='*80}")
    print(f"Executing: {migration_file.name}")
    print(f"{'='*80}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    try:
        cursor.execute(sql)
        print(f"✅ SUCCESS: {migration_file.name}")
        return True
    except Exception as e:
        print(f"❌ FAILED: {migration_file.name}")
        print(f"Error: {e}")
        return False


def verify_tables(cursor):
    """Verify tables were created."""
    print(f"\n{'='*80}")
    print("Verifying table creation...")
    print(f"{'='*80}")

    cursor.execute("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'walltrack'
        ORDER BY tablename;
    """)

    tables = cursor.fetchall()
    print(f"\n✅ Found {len(tables)} tables in walltrack schema:")
    for table in tables:
        print(f"   - {table[0]}")

    return tables


def verify_row_counts(cursor):
    """Verify mock data was inserted."""
    print(f"\n{'='*80}")
    print("Verifying mock data...")
    print(f"{'='*80}")

    tables_to_check = [
        'config', 'exit_strategies', 'wallets', 'tokens',
        'signals', 'orders', 'positions'
    ]

    for table in tables_to_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM walltrack.{table};")
            count = cursor.fetchone()[0]
            print(f"   {table}: {count} rows")
        except Exception as e:
            print(f"   {table}: ❌ Error - {e}")


def main():
    """Execute all migrations."""
    try:
        # Connect to database
        print(f"Connecting to database: {DATABASE_URL}")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        cursor = conn.cursor()

        # Execute migrations
        success_count = 0
        for migration_file_name in MIGRATION_FILES:
            migration_file = MIGRATIONS_DIR / migration_file_name

            if not migration_file.exists():
                print(f"⚠️  SKIPPED: {migration_file_name} (file not found)")
                continue

            if execute_migration(cursor, migration_file):
                success_count += 1
                conn.commit()
            else:
                conn.rollback()
                print("\n❌ Migration failed. Rolling back...")
                sys.exit(1)

        # Verify results
        verify_tables(cursor)
        verify_row_counts(cursor)

        # Summary
        print(f"\n{'='*80}")
        print(f"✅ ALL MIGRATIONS COMPLETED SUCCESSFULLY")
        print(f"{'='*80}")
        print(f"   Executed: {success_count}/{len(MIGRATION_FILES)} migrations")
        print(f"   Database: walltrack schema on localhost:5432")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
