"""Neo4j schema definitions and constraints."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from walltrack.data.neo4j.client import Neo4jClient

WALLET_CONSTRAINTS = """
// Unique constraint on wallet address
CREATE CONSTRAINT wallet_address IF NOT EXISTS
FOR (w:Wallet)
REQUIRE w.address IS UNIQUE;

// Index on wallet score for fast lookups
CREATE INDEX wallet_score IF NOT EXISTS
FOR (w:Wallet)
ON (w.score);

// Index on wallet status
CREATE INDEX wallet_status IF NOT EXISTS
FOR (w:Wallet)
ON (w.status);
"""

WALLET_NODE_PROPERTIES = """
// Wallet node properties:
// - address: string (unique)
// - score: float (0-1)
// - status: string (active, decay_detected, blacklisted, insufficient_data)
// - win_rate: float (0-1)
// - total_pnl: float
// - total_trades: integer
// - discovered_at: datetime
// - discovery_count: integer
// - updated_at: datetime
"""


async def create_wallet_constraints(neo4j_client: "Neo4jClient") -> None:
    """Create wallet constraints and indexes in Neo4j."""
    queries = [
        # Unique constraint on address
        """
        CREATE CONSTRAINT wallet_address IF NOT EXISTS
        FOR (w:Wallet)
        REQUIRE w.address IS UNIQUE
        """,
        # Index on score
        """
        CREATE INDEX wallet_score IF NOT EXISTS
        FOR (w:Wallet)
        ON (w.score)
        """,
        # Index on status
        """
        CREATE INDEX wallet_status IF NOT EXISTS
        FOR (w:Wallet)
        ON (w.status)
        """,
    ]

    for query in queries:
        await neo4j_client.execute_write(query)
