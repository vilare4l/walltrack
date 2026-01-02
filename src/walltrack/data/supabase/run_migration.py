"""Execute Supabase migration script.

This script executes a SQL migration file against the Supabase PostgreSQL database.
Usage: python run_migration.py <migration_file.sql>
"""

import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

def run_migration(migration_file: Path) -> None:
    """Execute a SQL migration file.

    Args:
        migration_file: Path to the SQL migration file to execute.

    Raises:
        FileNotFoundError: If migration file doesn't exist.
        psycopg2.Error: If database connection or query execution fails.
    """
    if not migration_file.exists():
        raise FileNotFoundError(f"Migration file not found: {migration_file}")

    # Read migration SQL
    sql = migration_file.read_text(encoding="utf-8")

    # Connect to database
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")

    print(f"[*] Connecting to database...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True

    try:
        print(f"[*] Executing migration: {migration_file.name}")
        with conn.cursor() as cursor:
            cursor.execute(sql)

        print(f"[OK] Migration {migration_file.name} executed successfully!")

    except psycopg2.Error as e:
        print(f"[ERROR] Migration failed: {e}")
        raise

    finally:
        conn.close()
        print(f"[*] Database connection closed")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_migration.py <migration_file.sql>")
        sys.exit(1)

    migration_path = Path(sys.argv[1])
    run_migration(migration_path)
