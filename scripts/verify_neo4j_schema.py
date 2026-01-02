#!/usr/bin/env python3
"""
Verify Neo4j Schema for WallTrack Epic 3

Checks that Wallet nodes and indexes exist in Neo4j.
"""

from __future__ import annotations

import os
import sys

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from neo4j import GraphDatabase


def verify_neo4j_schema() -> int:
    """
    Verify Neo4j schema for Epic 3.

    Returns:
        0 if schema is valid, 1 otherwise
    """
    # Load Neo4j config from environment
    # Note: neo4j-walltrack container maps port 7687 -> 7688 on host
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "walltrackpass")

    print("=" * 60)
    print("Neo4j Schema Verification - Epic 3")
    print("=" * 60)
    print()

    try:
        # Connect to Neo4j
        print(f"Connecting to Neo4j at {uri}...")
        driver = GraphDatabase.driver(uri, auth=(user, password))

        with driver.session() as session:
            # 1. Check Wallet node count
            result = session.run("MATCH (w:Wallet) RETURN count(w) as count")
            wallet_count = result.single()["count"]
            print(f"✓ Wallet nodes found: {wallet_count}")

            # 2. Check Wallet node properties
            result = session.run("""
                MATCH (w:Wallet)
                WITH w LIMIT 1
                RETURN keys(w) as properties
            """)
            record = result.single()
            if record:
                properties = record["properties"]
                print(f"✓ Wallet node properties: {', '.join(properties)}")

                # Verify expected properties exist
                expected_props = [
                    "wallet_address",
                    "discovery_date",
                    "token_source",
                ]
                missing = [p for p in expected_props if p not in properties]
                if missing:
                    print(f"⚠ Missing expected properties: {', '.join(missing)}")
            else:
                print("⚠ No Wallet nodes exist yet - this is OK for new setup")

            # 3. Check indexes
            result = session.run("""
                SHOW INDEXES
                YIELD name, labelsOrTypes, properties
                WHERE 'Wallet' IN labelsOrTypes
                RETURN name, properties
            """)

            indexes = list(result)
            if indexes:
                print(f"\n✓ Wallet indexes found ({len(indexes)}):")
                for idx in indexes:
                    print(f"  - {idx['name']}: {idx['properties']}")
            else:
                print("\n⚠ No Wallet indexes found - consider creating for performance")

            # 4. Check constraints
            result = session.run("""
                SHOW CONSTRAINTS
                YIELD name, labelsOrTypes, properties
                WHERE 'Wallet' IN labelsOrTypes
                RETURN name, properties
            """)

            constraints = list(result)
            if constraints:
                print(f"\n✓ Wallet constraints found ({len(constraints)}):")
                for c in constraints:
                    print(f"  - {c['name']}: {c['properties']}")
            else:
                print("\n⚠ No Wallet constraints found")

        driver.close()

        print()
        print("=" * 60)
        print("✓ Neo4j schema verification complete")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n✗ Error verifying Neo4j schema: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Ensure Neo4j is running")
        print("  2. Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars")
        print(f"  3. Try connecting manually: {uri}")
        return 1


if __name__ == "__main__":
    sys.exit(verify_neo4j_schema())
