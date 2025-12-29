"""Clean Neo4j and Supabase databases completely for V2 rebuild."""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()


async def clean_neo4j() -> None:
    """Delete all nodes and relationships from Neo4j."""
    from neo4j import AsyncGraphDatabase

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "walltrackpass")

    print(f"Connecting to Neo4j at {uri}...")

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async with driver.session() as session:
        # Count before
        result = await session.run("MATCH (n) RETURN count(n) as count")
        record = await result.single()
        count_before = record["count"] if record else 0
        print(f"  Nodes before: {count_before}")

        # Delete all relationships first, then nodes
        await session.run("MATCH ()-[r]->() DELETE r")
        await session.run("MATCH (n) DELETE n")

        # Count after
        result = await session.run("MATCH (n) RETURN count(n) as count")
        record = await result.single()
        count_after = record["count"] if record else 0
        print(f"  Nodes after: {count_after}")

    await driver.close()
    print("[OK] Neo4j cleaned!")


async def clean_supabase() -> None:
    """Drop all tables in walltrack schema from PostgreSQL."""
    import asyncpg

    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    schema = os.getenv("POSTGRES_SCHEMA", "walltrack")

    print(f"Connecting to PostgreSQL...")

    conn = await asyncpg.connect(database_url)

    try:
        # Get all tables in walltrack schema
        tables = await conn.fetch(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = $1
            """,
            schema,
        )

        print(f"  Tables found in '{schema}' schema: {len(tables)}")

        if tables:
            for table in tables:
                table_name = table["tablename"]
                print(f"    Dropping {schema}.{table_name}...")
                await conn.execute(
                    f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE'
                )

        # Also drop the schema itself to start fresh
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        print(f"  Schema '{schema}' dropped")

        # Recreate empty schema
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        print(f"  Schema '{schema}' recreated (empty)")

    finally:
        await conn.close()

    print("[OK] Supabase/PostgreSQL cleaned!")


async def main() -> None:
    """Run both cleanup operations."""
    print("=" * 60)
    print("WallTrack V2 - Database Cleanup")
    print("=" * 60)
    print()

    try:
        await clean_neo4j()
    except Exception as e:
        print(f"[ERROR] Neo4j error: {e}")

    print()

    try:
        await clean_supabase()
    except Exception as e:
        print(f"[ERROR] Supabase error: {e}")

    print()
    print("=" * 60)
    print("Database cleanup complete - ready for V2!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
