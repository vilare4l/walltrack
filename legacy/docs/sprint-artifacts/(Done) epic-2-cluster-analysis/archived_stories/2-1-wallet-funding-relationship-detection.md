# Story 2.1: Wallet Funding Relationship Detection (FUNDED_BY)

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: done
- **Priority**: High
- **FR**: FR7

## User Story

**As an** operator,
**I want** the system to detect funding relationships between wallets,
**So that** I can identify wallets that share common funding sources.

## Acceptance Criteria

### AC 1: Funding Analysis
**Given** a wallet address in the system
**When** funding analysis is triggered
**Then** incoming SOL transfers are analyzed
**And** source wallets are identified
**And** FUNDED_BY edges are created in Neo4j (source → target)
**And** funding amount and timestamp are stored on the edge

### AC 2: Relationship Query
**Given** wallet A funded wallet B with > 0.1 SOL
**When** the relationship is queried
**Then** Neo4j returns the FUNDED_BY edge with amount and date
**And** relationship strength is calculated based on amount/frequency

### AC 3: Funding Tree
**Given** multiple funding sources for a wallet
**When** funding tree is requested
**Then** all upstream funding wallets are returned (up to N levels)
**And** common ancestors between wallets are identified

## Technical Notes

- Implement in `src/walltrack/data/neo4j/queries/wallet.py`
- FR7: Map wallet funding relationships
- Use Cypher queries for graph traversal
- Store edges with properties: amount, timestamp, tx_signature

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/funding.py
"""Funding relationship models."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class FundingEdge(BaseModel):
    """FUNDED_BY relationship between wallets."""

    source_wallet: str = Field(..., description="Wallet that sent funds")
    target_wallet: str = Field(..., description="Wallet that received funds")
    amount_sol: float = Field(..., ge=0, description="Amount transferred in SOL")
    timestamp: datetime = Field(..., description="When the transfer occurred")
    tx_signature: str = Field(..., description="Transaction signature")
    strength: float = Field(default=0.0, ge=0, le=1, description="Relationship strength")

    class Config:
        frozen = True


class FundingNode(BaseModel):
    """A wallet node in the funding tree."""

    address: str
    level: int = Field(..., ge=0, description="Depth in funding tree (0 = target)")
    total_funded: float = Field(default=0.0, description="Total SOL funded to target")
    funding_count: int = Field(default=1, description="Number of funding transactions")
    first_funding: datetime
    last_funding: datetime


class FundingTree(BaseModel):
    """Complete funding tree for a wallet."""

    root_wallet: str
    nodes: list[FundingNode] = Field(default_factory=list)
    edges: list[FundingEdge] = Field(default_factory=list)
    max_depth: int = Field(default=0, description="Maximum depth of tree")


class CommonAncestor(BaseModel):
    """Common funding ancestor between wallets."""

    ancestor_address: str
    wallets_funded: list[str] = Field(..., description="List of wallets funded by this ancestor")
    total_descendants: int = Field(default=0)
    funding_strength: float = Field(default=0.0, description="Combined funding strength")


class FundingAnalysisResult(BaseModel):
    """Result of funding analysis for a wallet."""

    wallet_address: str
    edges_created: int = Field(default=0)
    edges_updated: int = Field(default=0)
    funders_found: int = Field(default=0)
    total_funding_sol: float = Field(default=0.0)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/funding.py
"""Funding analysis constants."""

# Minimum SOL transfer to consider as funding (filter dust)
MIN_FUNDING_AMOUNT_SOL = 0.1

# Maximum depth for funding tree traversal
MAX_FUNDING_TREE_DEPTH = 5

# Time window for analyzing funding (days)
FUNDING_ANALYSIS_WINDOW_DAYS = 90

# Strength calculation weights
STRENGTH_AMOUNT_WEIGHT = 0.6
STRENGTH_FREQUENCY_WEIGHT = 0.4

# Thresholds for relationship strength
STRONG_FUNDING_THRESHOLD = 0.7
MODERATE_FUNDING_THRESHOLD = 0.4
```

### 3. Neo4j Schema & Queries

```python
# src/walltrack/data/neo4j/queries/funding.py
"""Neo4j queries for funding relationships."""
from datetime import datetime
from typing import Optional


class FundingQueries:
    """Cypher queries for FUNDED_BY relationships."""

    # Schema constraints
    CREATE_CONSTRAINTS = """
    CREATE CONSTRAINT funded_by_unique IF NOT EXISTS
    FOR ()-[r:FUNDED_BY]->()
    REQUIRE (r.tx_signature) IS UNIQUE
    """

    # Create FUNDED_BY edge
    CREATE_FUNDED_BY = """
    MATCH (source:Wallet {address: $source_address})
    MATCH (target:Wallet {address: $target_address})
    MERGE (source)-[r:FUNDED_BY {tx_signature: $tx_signature}]->(target)
    ON CREATE SET
        r.amount_sol = $amount_sol,
        r.timestamp = datetime($timestamp),
        r.strength = $strength,
        r.created_at = datetime()
    ON MATCH SET
        r.amount_sol = r.amount_sol + $amount_sol,
        r.updated_at = datetime()
    RETURN r
    """

    # Create wallet nodes if not exist (before creating edge)
    ENSURE_WALLET_EXISTS = """
    MERGE (w:Wallet {address: $address})
    ON CREATE SET
        w.created_at = datetime(),
        w.discovered_via = 'funding_analysis'
    RETURN w
    """

    # Get direct funders of a wallet
    GET_DIRECT_FUNDERS = """
    MATCH (funder:Wallet)-[r:FUNDED_BY]->(target:Wallet {address: $wallet_address})
    WHERE r.amount_sol >= $min_amount
    RETURN funder.address AS funder_address,
           r.amount_sol AS amount,
           r.timestamp AS timestamp,
           r.tx_signature AS tx_signature,
           r.strength AS strength
    ORDER BY r.amount_sol DESC
    """

    # Get funding tree (N levels up)
    GET_FUNDING_TREE = """
    MATCH path = (ancestor:Wallet)-[:FUNDED_BY*1..$max_depth]->(target:Wallet {address: $wallet_address})
    WHERE ALL(r IN relationships(path) WHERE r.amount_sol >= $min_amount)
    WITH ancestor, path, length(path) AS depth,
         [r IN relationships(path) | r.amount_sol] AS amounts,
         [r IN relationships(path) | r.timestamp] AS timestamps
    RETURN ancestor.address AS ancestor_address,
           depth,
           reduce(total = 0.0, a IN amounts | total + a) AS total_funded,
           size(amounts) AS funding_count,
           head(timestamps) AS first_funding,
           last(timestamps) AS last_funding
    ORDER BY depth, total_funded DESC
    """

    # Find common ancestors between multiple wallets
    FIND_COMMON_ANCESTORS = """
    UNWIND $wallet_addresses AS target_addr
    MATCH path = (ancestor:Wallet)-[:FUNDED_BY*1..$max_depth]->(target:Wallet {address: target_addr})
    WHERE ALL(r IN relationships(path) WHERE r.amount_sol >= $min_amount)
    WITH ancestor, collect(DISTINCT target.address) AS funded_wallets
    WHERE size(funded_wallets) >= $min_common_count
    RETURN ancestor.address AS ancestor_address,
           funded_wallets,
           size(funded_wallets) AS wallets_funded_count
    ORDER BY wallets_funded_count DESC
    LIMIT $limit
    """

    # Calculate relationship strength between two wallets
    CALCULATE_STRENGTH = """
    MATCH (source:Wallet {address: $source_address})-[r:FUNDED_BY]->(target:Wallet {address: $target_address})
    WITH source, target,
         sum(r.amount_sol) AS total_amount,
         count(r) AS tx_count,
         max(r.timestamp) AS last_tx
    // Get total funding received by target for normalization
    OPTIONAL MATCH (any:Wallet)-[all_funding:FUNDED_BY]->(target)
    WITH source, target, total_amount, tx_count, last_tx,
         sum(all_funding.amount_sol) AS target_total_funding
    RETURN source.address AS source,
           target.address AS target,
           total_amount,
           tx_count,
           CASE WHEN target_total_funding > 0
                THEN total_amount / target_total_funding
                ELSE 0 END AS amount_ratio,
           last_tx
    """

    # Update strength on existing edge
    UPDATE_STRENGTH = """
    MATCH (source:Wallet {address: $source_address})-[r:FUNDED_BY]->(target:Wallet {address: $target_address})
    SET r.strength = $strength,
        r.updated_at = datetime()
    RETURN r
    """

    # Get all FUNDED_BY edges for a wallet (both directions)
    GET_ALL_FUNDING_EDGES = """
    MATCH (w:Wallet {address: $wallet_address})
    OPTIONAL MATCH (funder:Wallet)-[incoming:FUNDED_BY]->(w)
    OPTIONAL MATCH (w)-[outgoing:FUNDED_BY]->(funded:Wallet)
    RETURN
        collect(DISTINCT {
            source: funder.address,
            target: w.address,
            amount: incoming.amount_sol,
            direction: 'incoming'
        }) AS incoming_edges,
        collect(DISTINCT {
            source: w.address,
            target: funded.address,
            amount: outgoing.amount_sol,
            direction: 'outgoing'
        }) AS outgoing_edges
    """

    # Delete funding edge
    DELETE_FUNDED_BY = """
    MATCH (source:Wallet {address: $source_address})-[r:FUNDED_BY {tx_signature: $tx_signature}]->(target:Wallet {address: $target_address})
    DELETE r
    RETURN count(r) AS deleted_count
    """
```

### 4. FundingAnalyzer Service

```python
# src/walltrack/core/services/funding_analyzer.py
"""Service for analyzing wallet funding relationships."""
import structlog
from datetime import datetime, timedelta
from typing import Optional

from walltrack.core.models.funding import (
    FundingEdge, FundingNode, FundingTree,
    CommonAncestor, FundingAnalysisResult
)
from walltrack.core.constants.funding import (
    MIN_FUNDING_AMOUNT_SOL, MAX_FUNDING_TREE_DEPTH,
    FUNDING_ANALYSIS_WINDOW_DAYS,
    STRENGTH_AMOUNT_WEIGHT, STRENGTH_FREQUENCY_WEIGHT
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.funding import FundingQueries
from walltrack.integrations.solana.rpc import SolanaRPCClient

logger = structlog.get_logger(__name__)


class FundingAnalyzer:
    """Analyzes funding relationships between wallets."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        solana_client: SolanaRPCClient,
    ):
        self.neo4j = neo4j_client
        self.solana = solana_client
        self.queries = FundingQueries()

    async def analyze_wallet_funding(
        self,
        wallet_address: str,
        days_back: int = FUNDING_ANALYSIS_WINDOW_DAYS,
    ) -> FundingAnalysisResult:
        """
        Analyze incoming SOL transfers and create FUNDED_BY edges.

        Args:
            wallet_address: Wallet to analyze
            days_back: How far back to analyze transfers

        Returns:
            FundingAnalysisResult with analysis statistics
        """
        logger.info("analyzing_wallet_funding", wallet=wallet_address, days_back=days_back)

        # Ensure target wallet exists in Neo4j
        await self.neo4j.execute_write(
            self.queries.ENSURE_WALLET_EXISTS,
            {"address": wallet_address}
        )

        # Fetch SOL transfers from Solana
        since = datetime.utcnow() - timedelta(days=days_back)
        transfers = await self._fetch_sol_transfers(wallet_address, since)

        edges_created = 0
        edges_updated = 0
        funders = set()
        total_funding = 0.0

        for transfer in transfers:
            if transfer["amount_sol"] < MIN_FUNDING_AMOUNT_SOL:
                continue

            source = transfer["from_address"]
            funders.add(source)
            total_funding += transfer["amount_sol"]

            # Ensure source wallet exists
            await self.neo4j.execute_write(
                self.queries.ENSURE_WALLET_EXISTS,
                {"address": source}
            )

            # Calculate initial strength
            strength = await self._calculate_strength(source, wallet_address)

            # Create/update FUNDED_BY edge
            result = await self.neo4j.execute_write(
                self.queries.CREATE_FUNDED_BY,
                {
                    "source_address": source,
                    "target_address": wallet_address,
                    "amount_sol": transfer["amount_sol"],
                    "timestamp": transfer["timestamp"].isoformat(),
                    "tx_signature": transfer["signature"],
                    "strength": strength,
                }
            )

            if result:
                # Check if created or updated based on created_at vs updated_at
                record = result[0] if result else None
                if record and record.get("r", {}).get("updated_at"):
                    edges_updated += 1
                else:
                    edges_created += 1

        result = FundingAnalysisResult(
            wallet_address=wallet_address,
            edges_created=edges_created,
            edges_updated=edges_updated,
            funders_found=len(funders),
            total_funding_sol=total_funding,
        )

        logger.info(
            "funding_analysis_complete",
            wallet=wallet_address,
            edges_created=edges_created,
            funders=len(funders),
        )

        return result

    async def _fetch_sol_transfers(
        self,
        wallet_address: str,
        since: datetime,
    ) -> list[dict]:
        """Fetch incoming SOL transfers from Solana RPC."""
        # Get transaction signatures
        signatures = await self.solana.get_signatures_for_address(
            wallet_address,
            limit=1000,
        )

        transfers = []
        for sig_info in signatures:
            # Filter by time
            if sig_info.get("blockTime"):
                tx_time = datetime.fromtimestamp(sig_info["blockTime"])
                if tx_time < since:
                    continue

            # Get transaction details
            tx = await self.solana.get_transaction(sig_info["signature"])
            if not tx:
                continue

            # Parse SOL transfers to our wallet
            parsed = self._parse_sol_transfer(tx, wallet_address)
            if parsed:
                transfers.append(parsed)

        return transfers

    def _parse_sol_transfer(
        self,
        tx: dict,
        target_wallet: str,
    ) -> Optional[dict]:
        """Parse a transaction to extract SOL transfer details."""
        try:
            meta = tx.get("meta", {})
            if meta.get("err"):
                return None

            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])
            account_keys = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])

            # Find target wallet index
            target_idx = None
            for i, key in enumerate(account_keys):
                addr = key if isinstance(key, str) else key.get("pubkey", "")
                if addr == target_wallet:
                    target_idx = i
                    break

            if target_idx is None:
                return None

            # Calculate balance change
            if target_idx >= len(pre_balances) or target_idx >= len(post_balances):
                return None

            balance_change = post_balances[target_idx] - pre_balances[target_idx]
            if balance_change <= 0:
                return None  # Not an incoming transfer

            amount_sol = balance_change / 1e9  # Lamports to SOL

            # Find the sender (first signer with balance decrease)
            sender = None
            for i, key in enumerate(account_keys):
                if i == target_idx:
                    continue
                if i < len(pre_balances) and i < len(post_balances):
                    if post_balances[i] < pre_balances[i]:
                        sender = key if isinstance(key, str) else key.get("pubkey", "")
                        break

            if not sender:
                return None

            block_time = tx.get("blockTime", 0)

            return {
                "from_address": sender,
                "to_address": target_wallet,
                "amount_sol": amount_sol,
                "signature": tx.get("transaction", {}).get("signatures", [""])[0],
                "timestamp": datetime.fromtimestamp(block_time) if block_time else datetime.utcnow(),
            }
        except Exception as e:
            logger.warning("parse_transfer_failed", error=str(e))
            return None

    async def _calculate_strength(
        self,
        source_address: str,
        target_address: str,
    ) -> float:
        """
        Calculate relationship strength between wallets.

        Strength = (amount_weight * amount_ratio) + (freq_weight * frequency_score)
        """
        result = await self.neo4j.execute_read(
            self.queries.CALCULATE_STRENGTH,
            {
                "source_address": source_address,
                "target_address": target_address,
            }
        )

        if not result:
            return 0.0

        record = result[0]
        amount_ratio = record.get("amount_ratio", 0)
        tx_count = record.get("tx_count", 1)

        # Normalize frequency (cap at 10 transactions = 1.0)
        frequency_score = min(tx_count / 10, 1.0)

        strength = (
            STRENGTH_AMOUNT_WEIGHT * amount_ratio +
            STRENGTH_FREQUENCY_WEIGHT * frequency_score
        )

        return min(strength, 1.0)

    async def get_funding_tree(
        self,
        wallet_address: str,
        max_depth: int = MAX_FUNDING_TREE_DEPTH,
        min_amount: float = MIN_FUNDING_AMOUNT_SOL,
    ) -> FundingTree:
        """
        Get the funding tree for a wallet (upstream funders).

        Args:
            wallet_address: Target wallet
            max_depth: Maximum levels to traverse
            min_amount: Minimum funding amount to include

        Returns:
            FundingTree with all ancestors
        """
        logger.info(
            "getting_funding_tree",
            wallet=wallet_address,
            max_depth=max_depth,
        )

        result = await self.neo4j.execute_read(
            self.queries.GET_FUNDING_TREE,
            {
                "wallet_address": wallet_address,
                "max_depth": max_depth,
                "min_amount": min_amount,
            }
        )

        nodes = []
        seen_addresses = set()
        max_tree_depth = 0

        for record in result:
            addr = record["ancestor_address"]
            if addr in seen_addresses:
                continue
            seen_addresses.add(addr)

            depth = record["depth"]
            max_tree_depth = max(max_tree_depth, depth)

            node = FundingNode(
                address=addr,
                level=depth,
                total_funded=record["total_funded"],
                funding_count=record["funding_count"],
                first_funding=record["first_funding"],
                last_funding=record["last_funding"],
            )
            nodes.append(node)

        # Get edges
        edges = await self._get_tree_edges(wallet_address, max_depth, min_amount)

        return FundingTree(
            root_wallet=wallet_address,
            nodes=nodes,
            edges=edges,
            max_depth=max_tree_depth,
        )

    async def _get_tree_edges(
        self,
        wallet_address: str,
        max_depth: int,
        min_amount: float,
    ) -> list[FundingEdge]:
        """Get all FUNDED_BY edges in the funding tree."""
        query = """
        MATCH path = (ancestor:Wallet)-[r:FUNDED_BY*1..$max_depth]->(target:Wallet {address: $wallet_address})
        WHERE ALL(rel IN relationships(path) WHERE rel.amount_sol >= $min_amount)
        UNWIND relationships(path) AS edge
        WITH DISTINCT edge, startNode(edge) AS source, endNode(edge) AS dest
        RETURN source.address AS source_address,
               dest.address AS target_address,
               edge.amount_sol AS amount,
               edge.timestamp AS timestamp,
               edge.tx_signature AS tx_signature,
               edge.strength AS strength
        """

        result = await self.neo4j.execute_read(
            query,
            {
                "wallet_address": wallet_address,
                "max_depth": max_depth,
                "min_amount": min_amount,
            }
        )

        edges = []
        for record in result:
            edge = FundingEdge(
                source_wallet=record["source_address"],
                target_wallet=record["target_address"],
                amount_sol=record["amount"],
                timestamp=record["timestamp"],
                tx_signature=record["tx_signature"],
                strength=record.get("strength", 0.0),
            )
            edges.append(edge)

        return edges

    async def find_common_ancestors(
        self,
        wallet_addresses: list[str],
        max_depth: int = MAX_FUNDING_TREE_DEPTH,
        min_common: int = 2,
        limit: int = 20,
    ) -> list[CommonAncestor]:
        """
        Find common funding ancestors between multiple wallets.

        Args:
            wallet_addresses: Wallets to analyze
            max_depth: Max funding tree depth to search
            min_common: Minimum wallets an ancestor must fund
            limit: Maximum ancestors to return

        Returns:
            List of CommonAncestor sorted by wallets funded
        """
        if len(wallet_addresses) < 2:
            return []

        logger.info(
            "finding_common_ancestors",
            wallets=len(wallet_addresses),
            max_depth=max_depth,
        )

        result = await self.neo4j.execute_read(
            self.queries.FIND_COMMON_ANCESTORS,
            {
                "wallet_addresses": wallet_addresses,
                "max_depth": max_depth,
                "min_amount": MIN_FUNDING_AMOUNT_SOL,
                "min_common_count": min_common,
                "limit": limit,
            }
        )

        ancestors = []
        for record in result:
            ancestor = CommonAncestor(
                ancestor_address=record["ancestor_address"],
                wallets_funded=record["funded_wallets"],
                total_descendants=record["wallets_funded_count"],
            )
            ancestors.append(ancestor)

        return ancestors

    async def get_direct_funders(
        self,
        wallet_address: str,
        min_amount: float = MIN_FUNDING_AMOUNT_SOL,
    ) -> list[FundingEdge]:
        """Get immediate funders of a wallet."""
        result = await self.neo4j.execute_read(
            self.queries.GET_DIRECT_FUNDERS,
            {
                "wallet_address": wallet_address,
                "min_amount": min_amount,
            }
        )

        edges = []
        for record in result:
            edge = FundingEdge(
                source_wallet=record["funder_address"],
                target_wallet=wallet_address,
                amount_sol=record["amount"],
                timestamp=record["timestamp"],
                tx_signature=record["tx_signature"],
                strength=record.get("strength", 0.0),
            )
            edges.append(edge)

        return edges
```

### 5. API Endpoints

```python
# src/walltrack/api/routes/funding.py
"""Funding analysis API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from walltrack.core.models.funding import (
    FundingTree, CommonAncestor, FundingAnalysisResult, FundingEdge
)
from walltrack.core.services.funding_analyzer import FundingAnalyzer
from walltrack.core.constants.funding import (
    MIN_FUNDING_AMOUNT_SOL, MAX_FUNDING_TREE_DEPTH
)
from walltrack.api.dependencies import get_funding_analyzer

router = APIRouter(prefix="/funding", tags=["funding"])


@router.post("/{wallet_address}/analyze", response_model=FundingAnalysisResult)
async def analyze_wallet_funding(
    wallet_address: str,
    days_back: int = Query(default=90, ge=1, le=365),
    analyzer: FundingAnalyzer = Depends(get_funding_analyzer),
) -> FundingAnalysisResult:
    """
    Analyze incoming SOL transfers and create FUNDED_BY relationships.
    """
    try:
        return await analyzer.analyze_wallet_funding(wallet_address, days_back)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}/tree", response_model=FundingTree)
async def get_funding_tree(
    wallet_address: str,
    max_depth: int = Query(default=MAX_FUNDING_TREE_DEPTH, ge=1, le=10),
    min_amount: float = Query(default=MIN_FUNDING_AMOUNT_SOL, ge=0),
    analyzer: FundingAnalyzer = Depends(get_funding_analyzer),
) -> FundingTree:
    """
    Get funding tree showing all upstream funders up to max_depth levels.
    """
    try:
        return await analyzer.get_funding_tree(
            wallet_address, max_depth, min_amount
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}/funders", response_model=list[FundingEdge])
async def get_direct_funders(
    wallet_address: str,
    min_amount: float = Query(default=MIN_FUNDING_AMOUNT_SOL, ge=0),
    analyzer: FundingAnalyzer = Depends(get_funding_analyzer),
) -> list[FundingEdge]:
    """
    Get direct (immediate) funders of a wallet.
    """
    try:
        return await analyzer.get_direct_funders(wallet_address, min_amount)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/common-ancestors", response_model=list[CommonAncestor])
async def find_common_ancestors(
    wallet_addresses: list[str],
    max_depth: int = Query(default=MAX_FUNDING_TREE_DEPTH, ge=1, le=10),
    min_common: int = Query(default=2, ge=2),
    limit: int = Query(default=20, ge=1, le=100),
    analyzer: FundingAnalyzer = Depends(get_funding_analyzer),
) -> list[CommonAncestor]:
    """
    Find wallets that funded multiple of the given wallets.

    Useful for identifying coordinated wallet groups.
    """
    if len(wallet_addresses) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 wallet addresses required"
        )

    try:
        return await analyzer.find_common_ancestors(
            wallet_addresses, max_depth, min_common, limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 6. Dependency Injection

```python
# src/walltrack/api/dependencies.py (addition)
"""API dependencies - add funding analyzer."""
from functools import lru_cache

from walltrack.core.services.funding_analyzer import FundingAnalyzer
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.integrations.solana.rpc import SolanaRPCClient


@lru_cache()
def get_funding_analyzer() -> FundingAnalyzer:
    """Get FundingAnalyzer singleton."""
    neo4j_client = get_neo4j_client()
    solana_client = get_solana_client()
    return FundingAnalyzer(neo4j_client, solana_client)
```

### 7. Unit Tests

```python
# tests/unit/core/services/test_funding_analyzer.py
"""Tests for FundingAnalyzer service."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.services.funding_analyzer import FundingAnalyzer
from walltrack.core.models.funding import FundingEdge, FundingTree, CommonAncestor


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j client."""
    client = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    client.execute_write = AsyncMock(return_value=[{"r": {}}])
    return client


@pytest.fixture
def mock_solana():
    """Mock Solana RPC client."""
    client = AsyncMock()
    client.get_signatures_for_address = AsyncMock(return_value=[])
    client.get_transaction = AsyncMock(return_value=None)
    return client


@pytest.fixture
def analyzer(mock_neo4j, mock_solana):
    """Create FundingAnalyzer with mocks."""
    return FundingAnalyzer(mock_neo4j, mock_solana)


class TestAnalyzeWalletFunding:
    """Tests for analyze_wallet_funding."""

    @pytest.mark.asyncio
    async def test_creates_funding_edges(self, analyzer, mock_neo4j, mock_solana):
        """Should create FUNDED_BY edges from SOL transfers."""
        wallet = "target123"
        funder = "funder456"

        # Mock Solana returning a transfer
        mock_solana.get_signatures_for_address.return_value = [
            {"signature": "sig1", "blockTime": int(datetime.utcnow().timestamp())}
        ]
        mock_solana.get_transaction.return_value = {
            "blockTime": int(datetime.utcnow().timestamp()),
            "transaction": {
                "signatures": ["sig1"],
                "message": {
                    "accountKeys": [funder, wallet]
                }
            },
            "meta": {
                "err": None,
                "preBalances": [2_000_000_000, 1_000_000_000],  # 2 SOL, 1 SOL
                "postBalances": [1_500_000_000, 1_500_000_000],  # 1.5 SOL, 1.5 SOL
            }
        }

        result = await analyzer.analyze_wallet_funding(wallet)

        assert result.wallet_address == wallet
        assert result.funders_found == 1
        assert result.total_funding_sol == 0.5

        # Verify Neo4j calls
        assert mock_neo4j.execute_write.called

    @pytest.mark.asyncio
    async def test_filters_dust_transfers(self, analyzer, mock_neo4j, mock_solana):
        """Should ignore transfers below MIN_FUNDING_AMOUNT_SOL."""
        wallet = "target123"

        # Mock tiny transfer (0.01 SOL < 0.1 SOL minimum)
        mock_solana.get_signatures_for_address.return_value = [
            {"signature": "sig1", "blockTime": int(datetime.utcnow().timestamp())}
        ]
        mock_solana.get_transaction.return_value = {
            "blockTime": int(datetime.utcnow().timestamp()),
            "transaction": {
                "signatures": ["sig1"],
                "message": {"accountKeys": ["funder", wallet]}
            },
            "meta": {
                "err": None,
                "preBalances": [100_000_000, 50_000_000],
                "postBalances": [90_000_000, 60_000_000],  # Only 0.01 SOL
            }
        }

        result = await analyzer.analyze_wallet_funding(wallet)

        assert result.edges_created == 0
        assert result.funders_found == 0


class TestGetFundingTree:
    """Tests for get_funding_tree."""

    @pytest.mark.asyncio
    async def test_returns_funding_tree(self, analyzer, mock_neo4j):
        """Should return tree with nodes and edges."""
        wallet = "target123"

        mock_neo4j.execute_read.return_value = [
            {
                "ancestor_address": "funder1",
                "depth": 1,
                "total_funded": 5.0,
                "funding_count": 2,
                "first_funding": datetime.utcnow() - timedelta(days=30),
                "last_funding": datetime.utcnow(),
            },
            {
                "ancestor_address": "funder2",
                "depth": 2,
                "total_funded": 10.0,
                "funding_count": 1,
                "first_funding": datetime.utcnow() - timedelta(days=60),
                "last_funding": datetime.utcnow() - timedelta(days=60),
            }
        ]

        tree = await analyzer.get_funding_tree(wallet, max_depth=3)

        assert tree.root_wallet == wallet
        assert len(tree.nodes) == 2
        assert tree.nodes[0].address == "funder1"
        assert tree.nodes[0].level == 1
        assert tree.nodes[1].level == 2


class TestFindCommonAncestors:
    """Tests for find_common_ancestors."""

    @pytest.mark.asyncio
    async def test_finds_common_funders(self, analyzer, mock_neo4j):
        """Should identify wallets funding multiple targets."""
        wallets = ["wallet1", "wallet2", "wallet3"]

        mock_neo4j.execute_read.return_value = [
            {
                "ancestor_address": "common_funder",
                "funded_wallets": ["wallet1", "wallet2", "wallet3"],
                "wallets_funded_count": 3,
            }
        ]

        ancestors = await analyzer.find_common_ancestors(wallets)

        assert len(ancestors) == 1
        assert ancestors[0].ancestor_address == "common_funder"
        assert ancestors[0].total_descendants == 3

    @pytest.mark.asyncio
    async def test_requires_minimum_wallets(self, analyzer):
        """Should return empty for less than 2 wallets."""
        result = await analyzer.find_common_ancestors(["single_wallet"])
        assert result == []


class TestStrengthCalculation:
    """Tests for relationship strength calculation."""

    @pytest.mark.asyncio
    async def test_calculates_strength(self, analyzer, mock_neo4j):
        """Should calculate strength from amount and frequency."""
        mock_neo4j.execute_read.return_value = [
            {
                "source": "funder",
                "target": "target",
                "total_amount": 5.0,
                "tx_count": 5,
                "amount_ratio": 0.5,  # 50% of target's funding
                "last_tx": datetime.utcnow(),
            }
        ]

        strength = await analyzer._calculate_strength("funder", "target")

        # strength = 0.6 * 0.5 + 0.4 * 0.5 = 0.5
        assert 0.4 <= strength <= 0.6
```

---

## Implementation Tasks

- [x] Create funding analysis service
- [x] Implement Neo4j FUNDED_BY edge creation
- [x] Add edge properties (amount, timestamp, tx_signature)
- [x] Implement relationship strength calculation
- [x] Create funding tree traversal query
- [x] Implement common ancestor detection

## Definition of Done

- [x] Funding relationships detected from SOL transfers
- [x] FUNDED_BY edges created in Neo4j with properties
- [x] Funding tree queries work up to N levels
- [x] Common ancestors identifiable between wallets
