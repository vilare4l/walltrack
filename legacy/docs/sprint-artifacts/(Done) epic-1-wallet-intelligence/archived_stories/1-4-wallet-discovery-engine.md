# Story 1.4: Wallet Discovery Engine

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: completed
- **Priority**: High
- **FR**: FR1
- **Completed**: 2024-12-17

## User Story

**As an** operator,
**I want** to automatically discover high-performing wallets from successful token launches,
**So that** I can build a watchlist of smart money addresses.

## Acceptance Criteria

### AC 1: Discovery Execution
**Given** a list of successful token launches (provided or fetched)
**When** the discovery engine runs
**Then** early buyers are identified (bought within first N minutes)
**And** wallets with profitable exits are extracted
**And** wallet addresses are stored in Supabase with discovery metadata
**And** wallet nodes are created in Neo4j

### AC 2: Duplicate Handling
**Given** a discovered wallet already exists
**When** rediscovery occurs
**Then** the wallet is not duplicated
**And** discovery count is incremented

### AC 3: Results Reporting
**Given** the discovery process completes
**When** results are returned
**Then** count of new wallets discovered is provided
**And** count of existing wallets updated is provided
**And** process duration is logged

## Technical Specifications

### Wallet Data Model

**src/walltrack/data/models/wallet.py:**
```python
"""Wallet domain models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WalletStatus(str, Enum):
    """Wallet status enum."""

    ACTIVE = "active"
    DECAY_DETECTED = "decay_detected"
    BLACKLISTED = "blacklisted"
    INSUFFICIENT_DATA = "insufficient_data"


class WalletProfile(BaseModel):
    """Wallet performance profile."""

    win_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Win rate (0-1)")
    total_pnl: float = Field(default=0.0, description="Total PnL in USD")
    avg_pnl_per_trade: float = Field(default=0.0, description="Average PnL per trade")
    total_trades: int = Field(default=0, ge=0, description="Total number of trades")
    timing_percentile: float = Field(
        default=0.5, ge=0.0, le=1.0, description="How early they enter (0=earliest, 1=latest)"
    )
    avg_hold_time_hours: float = Field(default=0.0, ge=0.0, description="Average hold time in hours")
    preferred_hours: list[int] = Field(default_factory=list, description="Active trading hours (0-23)")
    avg_position_size_sol: float = Field(default=0.0, ge=0.0, description="Average position size in SOL")


class Wallet(BaseModel):
    """Wallet domain model."""

    address: str = Field(..., min_length=32, max_length=44, description="Solana wallet address")
    status: WalletStatus = Field(default=WalletStatus.ACTIVE, description="Current wallet status")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Wallet trust score (0-1)")
    profile: WalletProfile = Field(default_factory=WalletProfile, description="Performance profile")

    # Discovery metadata
    discovered_at: datetime = Field(default_factory=datetime.utcnow, description="First discovery timestamp")
    discovery_count: int = Field(default=1, ge=1, description="Times discovered from token launches")
    discovery_tokens: list[str] = Field(default_factory=list, description="Token mints from discovery")

    # Decay tracking
    decay_detected_at: datetime | None = Field(default=None, description="Decay detection timestamp")
    consecutive_losses: int = Field(default=0, ge=0, description="Current consecutive loss count")
    rolling_win_rate: float | None = Field(default=None, description="Rolling 20-trade win rate")

    # Blacklist
    blacklisted_at: datetime | None = Field(default=None, description="Blacklist timestamp")
    blacklist_reason: str | None = Field(default=None, description="Reason for blacklisting")

    # Timestamps
    last_profiled_at: datetime | None = Field(default=None, description="Last profile update")
    last_signal_at: datetime | None = Field(default=None, description="Last signal from this wallet")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

    def is_trackable(self) -> bool:
        """Check if wallet can be tracked for signals."""
        return self.status not in (WalletStatus.BLACKLISTED, WalletStatus.INSUFFICIENT_DATA)

    def has_sufficient_data(self) -> bool:
        """Check if wallet has enough trades for analysis."""
        return self.profile.total_trades >= 5


class DiscoveryResult(BaseModel):
    """Result of wallet discovery process."""

    new_wallets: int = Field(default=0, ge=0, description="Count of new wallets discovered")
    updated_wallets: int = Field(default=0, ge=0, description="Count of existing wallets updated")
    total_processed: int = Field(default=0, ge=0, description="Total wallets processed")
    token_mint: str = Field(..., description="Token mint address that was analyzed")
    duration_seconds: float = Field(..., ge=0, description="Processing duration")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")


class TokenLaunch(BaseModel):
    """Token launch data for discovery."""

    mint: str = Field(..., description="Token mint address")
    symbol: str = Field(default="", description="Token symbol")
    launch_time: datetime = Field(..., description="Token launch timestamp")
    peak_mcap: float = Field(default=0.0, ge=0, description="Peak market cap in USD")
    current_mcap: float = Field(default=0.0, ge=0, description="Current market cap in USD")
    volume_24h: float = Field(default=0.0, ge=0, description="24h volume in USD")
```

### Supabase Wallets Table Schema

**src/walltrack/data/supabase/migrations/002_wallets.sql:**
```sql
-- Wallets table for storing wallet data and profiles
CREATE TABLE IF NOT EXISTS wallets (
    address VARCHAR(44) PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    score DECIMAL(5, 4) NOT NULL DEFAULT 0.5000,

    -- Profile metrics
    win_rate DECIMAL(5, 4) DEFAULT 0.0000,
    total_pnl DECIMAL(18, 4) DEFAULT 0.0000,
    avg_pnl_per_trade DECIMAL(18, 4) DEFAULT 0.0000,
    total_trades INTEGER DEFAULT 0,
    timing_percentile DECIMAL(5, 4) DEFAULT 0.5000,
    avg_hold_time_hours DECIMAL(10, 2) DEFAULT 0.00,
    preferred_hours INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    avg_position_size_sol DECIMAL(18, 8) DEFAULT 0.00000000,

    -- Discovery metadata
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    discovery_count INTEGER DEFAULT 1,
    discovery_tokens TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Decay tracking
    decay_detected_at TIMESTAMPTZ,
    consecutive_losses INTEGER DEFAULT 0,
    rolling_win_rate DECIMAL(5, 4),

    -- Blacklist
    blacklisted_at TIMESTAMPTZ,
    blacklist_reason TEXT,

    -- Timestamps
    last_profiled_at TIMESTAMPTZ,
    last_signal_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('active', 'decay_detected', 'blacklisted', 'insufficient_data')),
    CONSTRAINT valid_score CHECK (score >= 0 AND score <= 1),
    CONSTRAINT valid_win_rate CHECK (win_rate >= 0 AND win_rate <= 1)
);

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_wallets_updated_at
    BEFORE UPDATE ON wallets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_wallets_status ON wallets(status);
CREATE INDEX IF NOT EXISTS idx_wallets_score ON wallets(score DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_win_rate ON wallets(win_rate DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_last_signal ON wallets(last_signal_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_discovered ON wallets(discovered_at DESC);

-- RLS policies
ALTER TABLE wallets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access" ON wallets FOR SELECT USING (true);
CREATE POLICY "Allow insert" ON wallets FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update" ON wallets FOR UPDATE USING (true);
```

### Neo4j Wallet Node Schema

**src/walltrack/data/neo4j/schemas.py:**
```python
"""Neo4j schema definitions and constraints."""

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
// - status: string (active, decay_detected, blacklisted)
// - win_rate: float (0-1)
// - total_pnl: float
// - total_trades: integer
// - discovered_at: datetime
// - updated_at: datetime
"""
```

**src/walltrack/data/neo4j/queries/wallet.py:**
```python
"""Neo4j wallet queries."""

from datetime import datetime
from typing import Any

import structlog
from neo4j import AsyncSession

from walltrack.data.models.wallet import Wallet, WalletStatus

log = structlog.get_logger()


class WalletQueries:
    """Neo4j queries for wallet operations."""

    @staticmethod
    async def create_or_update_wallet(
        session: AsyncSession, wallet: Wallet
    ) -> dict[str, Any]:
        """Create or update a wallet node in Neo4j."""
        query = """
        MERGE (w:Wallet {address: $address})
        ON CREATE SET
            w.score = $score,
            w.status = $status,
            w.win_rate = $win_rate,
            w.total_pnl = $total_pnl,
            w.total_trades = $total_trades,
            w.discovered_at = datetime($discovered_at),
            w.updated_at = datetime($updated_at)
        ON MATCH SET
            w.score = $score,
            w.status = $status,
            w.win_rate = $win_rate,
            w.total_pnl = $total_pnl,
            w.total_trades = $total_trades,
            w.updated_at = datetime($updated_at)
        RETURN w
        """
        result = await session.run(
            query,
            address=wallet.address,
            score=wallet.score,
            status=wallet.status.value,
            win_rate=wallet.profile.win_rate,
            total_pnl=wallet.profile.total_pnl,
            total_trades=wallet.profile.total_trades,
            discovered_at=wallet.discovered_at.isoformat(),
            updated_at=wallet.updated_at.isoformat(),
        )
        record = await result.single()
        return dict(record["w"]) if record else {}

    @staticmethod
    async def get_wallet(session: AsyncSession, address: str) -> dict[str, Any] | None:
        """Get a wallet node by address."""
        query = """
        MATCH (w:Wallet {address: $address})
        RETURN w
        """
        result = await session.run(query, address=address)
        record = await result.single()
        return dict(record["w"]) if record else None

    @staticmethod
    async def get_active_wallets(
        session: AsyncSession, min_score: float = 0.0, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get active wallets with minimum score."""
        query = """
        MATCH (w:Wallet)
        WHERE w.status = 'active' AND w.score >= $min_score
        RETURN w
        ORDER BY w.score DESC
        LIMIT $limit
        """
        result = await session.run(query, min_score=min_score, limit=limit)
        records = await result.data()
        return [dict(r["w"]) for r in records]

    @staticmethod
    async def increment_discovery_count(
        session: AsyncSession, address: str
    ) -> int:
        """Increment discovery count for existing wallet."""
        query = """
        MATCH (w:Wallet {address: $address})
        SET w.discovery_count = COALESCE(w.discovery_count, 0) + 1,
            w.updated_at = datetime()
        RETURN w.discovery_count as count
        """
        result = await session.run(query, address=address)
        record = await result.single()
        return record["count"] if record else 0
```

### Wallet Repository (Supabase)

**src/walltrack/data/supabase/repositories/wallet_repo.py:**
```python
"""Repository for wallet data in Supabase."""

from datetime import datetime
from typing import Any

import structlog
from supabase import AsyncClient

from walltrack.data.models.wallet import (
    DiscoveryResult,
    Wallet,
    WalletProfile,
    WalletStatus,
)

log = structlog.get_logger()


class WalletRepository:
    """Repository for wallet CRUD operations."""

    def __init__(self, client: AsyncClient) -> None:
        self.client = client
        self.table = "wallets"

    async def get_by_address(self, address: str) -> Wallet | None:
        """Get wallet by address."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("address", address)
            .single()
            .execute()
        )
        if response.data:
            return self._row_to_wallet(response.data)
        return None

    async def exists(self, address: str) -> bool:
        """Check if wallet exists."""
        response = await (
            self.client.table(self.table)
            .select("address")
            .eq("address", address)
            .execute()
        )
        return len(response.data) > 0

    async def create(self, wallet: Wallet) -> Wallet:
        """Create a new wallet."""
        data = self._wallet_to_row(wallet)
        response = await self.client.table(self.table).insert(data).execute()
        log.info("wallet_created", address=wallet.address)
        return self._row_to_wallet(response.data[0])

    async def update(self, wallet: Wallet) -> Wallet:
        """Update an existing wallet."""
        data = self._wallet_to_row(wallet)
        data["updated_at"] = datetime.utcnow().isoformat()
        response = await (
            self.client.table(self.table)
            .update(data)
            .eq("address", wallet.address)
            .execute()
        )
        log.info("wallet_updated", address=wallet.address)
        return self._row_to_wallet(response.data[0])

    async def upsert(self, wallet: Wallet) -> tuple[Wallet, bool]:
        """Create or update wallet. Returns (wallet, is_new)."""
        existing = await self.exists(wallet.address)
        if existing:
            # Increment discovery count for existing wallet
            await self._increment_discovery(wallet.address, wallet.discovery_tokens)
            updated = await self.update(wallet)
            return updated, False
        else:
            created = await self.create(wallet)
            return created, True

    async def _increment_discovery(
        self, address: str, new_tokens: list[str]
    ) -> None:
        """Increment discovery count and add new tokens."""
        await self.client.rpc(
            "increment_wallet_discovery",
            {"wallet_address": address, "new_tokens": new_tokens},
        ).execute()

    async def get_active_wallets(
        self,
        min_score: float = 0.0,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Wallet]:
        """Get active wallets with minimum score."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("status", WalletStatus.ACTIVE.value)
            .gte("score", min_score)
            .order("score", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return [self._row_to_wallet(row) for row in response.data]

    async def get_by_status(
        self, status: WalletStatus, limit: int = 100
    ) -> list[Wallet]:
        """Get wallets by status."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("status", status.value)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._row_to_wallet(row) for row in response.data]

    async def set_status(
        self, address: str, status: WalletStatus, reason: str | None = None
    ) -> None:
        """Update wallet status."""
        data: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if status == WalletStatus.BLACKLISTED:
            data["blacklisted_at"] = datetime.utcnow().isoformat()
            data["blacklist_reason"] = reason
        elif status == WalletStatus.DECAY_DETECTED:
            data["decay_detected_at"] = datetime.utcnow().isoformat()

        await (
            self.client.table(self.table)
            .update(data)
            .eq("address", address)
            .execute()
        )
        log.info("wallet_status_updated", address=address, status=status.value)

    def _wallet_to_row(self, wallet: Wallet) -> dict[str, Any]:
        """Convert Wallet model to database row."""
        return {
            "address": wallet.address,
            "status": wallet.status.value,
            "score": wallet.score,
            "win_rate": wallet.profile.win_rate,
            "total_pnl": wallet.profile.total_pnl,
            "avg_pnl_per_trade": wallet.profile.avg_pnl_per_trade,
            "total_trades": wallet.profile.total_trades,
            "timing_percentile": wallet.profile.timing_percentile,
            "avg_hold_time_hours": wallet.profile.avg_hold_time_hours,
            "preferred_hours": wallet.profile.preferred_hours,
            "avg_position_size_sol": wallet.profile.avg_position_size_sol,
            "discovered_at": wallet.discovered_at.isoformat(),
            "discovery_count": wallet.discovery_count,
            "discovery_tokens": wallet.discovery_tokens,
            "decay_detected_at": wallet.decay_detected_at.isoformat() if wallet.decay_detected_at else None,
            "consecutive_losses": wallet.consecutive_losses,
            "rolling_win_rate": wallet.rolling_win_rate,
            "blacklisted_at": wallet.blacklisted_at.isoformat() if wallet.blacklisted_at else None,
            "blacklist_reason": wallet.blacklist_reason,
            "last_profiled_at": wallet.last_profiled_at.isoformat() if wallet.last_profiled_at else None,
            "last_signal_at": wallet.last_signal_at.isoformat() if wallet.last_signal_at else None,
        }

    def _row_to_wallet(self, row: dict[str, Any]) -> Wallet:
        """Convert database row to Wallet model."""
        profile = WalletProfile(
            win_rate=float(row.get("win_rate", 0)),
            total_pnl=float(row.get("total_pnl", 0)),
            avg_pnl_per_trade=float(row.get("avg_pnl_per_trade", 0)),
            total_trades=int(row.get("total_trades", 0)),
            timing_percentile=float(row.get("timing_percentile", 0.5)),
            avg_hold_time_hours=float(row.get("avg_hold_time_hours", 0)),
            preferred_hours=row.get("preferred_hours", []),
            avg_position_size_sol=float(row.get("avg_position_size_sol", 0)),
        )
        return Wallet(
            address=row["address"],
            status=WalletStatus(row.get("status", "active")),
            score=float(row.get("score", 0.5)),
            profile=profile,
            discovered_at=datetime.fromisoformat(row["discovered_at"]) if row.get("discovered_at") else datetime.utcnow(),
            discovery_count=int(row.get("discovery_count", 1)),
            discovery_tokens=row.get("discovery_tokens", []),
            decay_detected_at=datetime.fromisoformat(row["decay_detected_at"]) if row.get("decay_detected_at") else None,
            consecutive_losses=int(row.get("consecutive_losses", 0)),
            rolling_win_rate=float(row["rolling_win_rate"]) if row.get("rolling_win_rate") else None,
            blacklisted_at=datetime.fromisoformat(row["blacklisted_at"]) if row.get("blacklisted_at") else None,
            blacklist_reason=row.get("blacklist_reason"),
            last_profiled_at=datetime.fromisoformat(row["last_profiled_at"]) if row.get("last_profiled_at") else None,
            last_signal_at=datetime.fromisoformat(row["last_signal_at"]) if row.get("last_signal_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.utcnow(),
        )
```

### Discovery Scanner

**src/walltrack/discovery/scanner.py:**
```python
"""Wallet discovery engine for finding smart money wallets."""

import asyncio
import time
from datetime import datetime, timedelta

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import (
    DiscoveryResult,
    TokenLaunch,
    Wallet,
    WalletProfile,
    WalletStatus,
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.wallet import WalletQueries
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger()


class WalletDiscoveryScanner:
    """Discovers high-performing wallets from successful token launches."""

    def __init__(
        self,
        wallet_repo: WalletRepository,
        neo4j_client: Neo4jClient,
        helius_client: HeliusClient,
    ) -> None:
        self.wallet_repo = wallet_repo
        self.neo4j = neo4j_client
        self.helius = helius_client
        self.settings = get_settings()

    async def discover_from_token(
        self,
        token_launch: TokenLaunch,
        early_window_minutes: int = 30,
        min_profit_pct: float = 50.0,
    ) -> DiscoveryResult:
        """
        Discover wallets from a single token launch.

        Args:
            token_launch: Token launch data
            early_window_minutes: Window for "early buyer" definition
            min_profit_pct: Minimum profit percentage to qualify

        Returns:
            DiscoveryResult with counts and duration
        """
        start_time = time.time()
        new_count = 0
        updated_count = 0
        errors: list[str] = []

        log.info(
            "discovery_started",
            token=token_launch.mint,
            symbol=token_launch.symbol,
            early_window=early_window_minutes,
        )

        try:
            # Get early buyers from Helius
            early_buyers = await self._get_early_buyers(
                token_launch.mint,
                token_launch.launch_time,
                early_window_minutes,
            )

            log.info("early_buyers_found", count=len(early_buyers), token=token_launch.mint)

            # Filter to profitable exits
            profitable_wallets = await self._filter_profitable_wallets(
                early_buyers,
                token_launch.mint,
                min_profit_pct,
            )

            log.info(
                "profitable_wallets_found",
                count=len(profitable_wallets),
                token=token_launch.mint,
            )

            # Store each wallet
            for wallet_data in profitable_wallets:
                try:
                    wallet = Wallet(
                        address=wallet_data["address"],
                        status=WalletStatus.ACTIVE,
                        score=0.5,  # Default score, will be updated by profiler
                        profile=WalletProfile(
                            total_pnl=wallet_data.get("pnl", 0),
                            total_trades=wallet_data.get("trades", 1),
                        ),
                        discovery_tokens=[token_launch.mint],
                    )

                    # Upsert to Supabase
                    _, is_new = await self.wallet_repo.upsert(wallet)

                    # Create/update in Neo4j
                    async with self.neo4j.session() as session:
                        await WalletQueries.create_or_update_wallet(session, wallet)

                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    log.error(
                        "wallet_storage_error",
                        address=wallet_data.get("address"),
                        error=str(e),
                    )
                    errors.append(f"Failed to store {wallet_data.get('address')}: {str(e)}")

        except Exception as e:
            log.error("discovery_error", token=token_launch.mint, error=str(e))
            errors.append(f"Discovery failed: {str(e)}")

        duration = time.time() - start_time

        result = DiscoveryResult(
            new_wallets=new_count,
            updated_wallets=updated_count,
            total_processed=new_count + updated_count,
            token_mint=token_launch.mint,
            duration_seconds=duration,
            errors=errors,
        )

        log.info(
            "discovery_completed",
            token=token_launch.mint,
            new=new_count,
            updated=updated_count,
            duration=f"{duration:.2f}s",
        )

        return result

    async def discover_from_multiple_tokens(
        self,
        token_launches: list[TokenLaunch],
        early_window_minutes: int = 30,
        min_profit_pct: float = 50.0,
        max_concurrent: int = 5,
    ) -> list[DiscoveryResult]:
        """
        Discover wallets from multiple token launches concurrently.

        Args:
            token_launches: List of token launches to analyze
            early_window_minutes: Window for "early buyer" definition
            min_profit_pct: Minimum profit percentage
            max_concurrent: Maximum concurrent discoveries

        Returns:
            List of DiscoveryResult for each token
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_discover(token: TokenLaunch) -> DiscoveryResult:
            async with semaphore:
                return await self.discover_from_token(
                    token, early_window_minutes, min_profit_pct
                )

        results = await asyncio.gather(
            *[bounded_discover(token) for token in token_launches],
            return_exceptions=True,
        )

        # Filter out exceptions and log them
        valid_results: list[DiscoveryResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error(
                    "discovery_batch_error",
                    token=token_launches[i].mint,
                    error=str(result),
                )
            else:
                valid_results.append(result)

        return valid_results

    async def _get_early_buyers(
        self,
        token_mint: str,
        launch_time: datetime,
        window_minutes: int,
    ) -> list[dict]:
        """Get wallets that bought within the early window."""
        end_time = launch_time + timedelta(minutes=window_minutes)

        # Use Helius to get token transfer history
        transactions = await self.helius.get_token_transactions(
            mint=token_mint,
            start_time=launch_time,
            end_time=end_time,
            tx_type="buy",
        )

        # Extract unique buyer addresses
        buyers: dict[str, dict] = {}
        for tx in transactions:
            buyer = tx.get("buyer")
            if buyer and buyer not in buyers:
                buyers[buyer] = {
                    "address": buyer,
                    "first_buy_time": tx.get("timestamp"),
                    "buy_amount": tx.get("amount", 0),
                }

        return list(buyers.values())

    async def _filter_profitable_wallets(
        self,
        wallets: list[dict],
        token_mint: str,
        min_profit_pct: float,
    ) -> list[dict]:
        """Filter wallets to those with profitable exits."""
        profitable: list[dict] = []

        for wallet_data in wallets:
            address = wallet_data["address"]

            # Get wallet's sell transactions for this token
            sells = await self.helius.get_token_transactions(
                mint=token_mint,
                wallet=address,
                tx_type="sell",
            )

            if not sells:
                continue

            # Calculate PnL
            buy_amount = wallet_data.get("buy_amount", 0)
            sell_amount = sum(tx.get("amount", 0) for tx in sells)

            if buy_amount > 0:
                profit_pct = ((sell_amount - buy_amount) / buy_amount) * 100

                if profit_pct >= min_profit_pct:
                    wallet_data["pnl"] = sell_amount - buy_amount
                    wallet_data["profit_pct"] = profit_pct
                    wallet_data["trades"] = 1 + len(sells)
                    profitable.append(wallet_data)

        return profitable
```

### Discovery API Endpoint

**src/walltrack/api/routes/wallets.py:**
```python
"""Wallet API routes."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from walltrack.api.dependencies import get_wallet_repo, get_discovery_scanner
from walltrack.data.models.wallet import DiscoveryResult, TokenLaunch, Wallet, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.scanner import WalletDiscoveryScanner

router = APIRouter(prefix="/wallets", tags=["wallets"])


class DiscoveryRequest(BaseModel):
    """Request to discover wallets from token launches."""

    tokens: list[TokenLaunch] = Field(..., min_length=1, max_length=10)
    early_window_minutes: int = Field(default=30, ge=5, le=120)
    min_profit_pct: float = Field(default=50.0, ge=10.0, le=500.0)


class WalletListResponse(BaseModel):
    """Response for wallet list."""

    wallets: list[Wallet]
    total: int
    limit: int
    offset: int


@router.post("/discover", response_model=list[DiscoveryResult])
async def discover_wallets(
    request: DiscoveryRequest,
    scanner: Annotated[WalletDiscoveryScanner, Depends(get_discovery_scanner)],
) -> list[DiscoveryResult]:
    """
    Discover wallets from successful token launches.

    Analyzes early buyers and filters to profitable exits.
    """
    results = await scanner.discover_from_multiple_tokens(
        token_launches=request.tokens,
        early_window_minutes=request.early_window_minutes,
        min_profit_pct=request.min_profit_pct,
    )
    return results


@router.get("", response_model=WalletListResponse)
async def list_wallets(
    repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
    status: WalletStatus | None = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> WalletListResponse:
    """List wallets with filtering and pagination."""
    if status:
        wallets = await repo.get_by_status(status, limit=limit)
    else:
        wallets = await repo.get_active_wallets(
            min_score=min_score, limit=limit, offset=offset
        )

    return WalletListResponse(
        wallets=wallets,
        total=len(wallets),  # TODO: Add count query
        limit=limit,
        offset=offset,
    )


@router.get("/{address}", response_model=Wallet)
async def get_wallet(
    address: str,
    repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
) -> Wallet:
    """Get wallet by address."""
    wallet = await repo.get_by_address(address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {address} not found",
        )
    return wallet
```

### Unit Tests

**tests/unit/discovery/test_scanner.py:**
```python
"""Tests for wallet discovery scanner."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.data.models.wallet import TokenLaunch, Wallet, WalletStatus
from walltrack.discovery.scanner import WalletDiscoveryScanner


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    repo.upsert.return_value = (MagicMock(spec=Wallet), True)
    return repo


@pytest.fixture
def mock_neo4j_client() -> AsyncMock:
    """Mock Neo4j client."""
    client = AsyncMock()
    session = AsyncMock()
    client.session.return_value.__aenter__.return_value = session
    return client


@pytest.fixture
def mock_helius_client() -> AsyncMock:
    """Mock Helius client."""
    client = AsyncMock()
    client.get_token_transactions.return_value = [
        {"buyer": "wallet1", "timestamp": datetime.utcnow(), "amount": 1.0},
        {"buyer": "wallet2", "timestamp": datetime.utcnow(), "amount": 2.0},
    ]
    return client


@pytest.fixture
def scanner(
    mock_wallet_repo: AsyncMock,
    mock_neo4j_client: AsyncMock,
    mock_helius_client: AsyncMock,
) -> WalletDiscoveryScanner:
    """Create scanner with mocked dependencies."""
    return WalletDiscoveryScanner(
        wallet_repo=mock_wallet_repo,
        neo4j_client=mock_neo4j_client,
        helius_client=mock_helius_client,
    )


class TestWalletDiscoveryScanner:
    """Tests for WalletDiscoveryScanner."""

    async def test_discover_from_token_success(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test successful wallet discovery."""
        # Setup sells for profitable exit
        mock_helius_client.get_token_transactions.side_effect = [
            # First call: early buyers
            [
                {"buyer": "wallet1", "timestamp": datetime.utcnow(), "amount": 1.0},
            ],
            # Second call: sells for wallet1
            [{"amount": 2.0}],  # 100% profit
        ]

        token = TokenLaunch(
            mint="token123",
            symbol="TEST",
            launch_time=datetime.utcnow() - timedelta(hours=1),
            peak_mcap=1000000,
        )

        result = await scanner.discover_from_token(token)

        assert result.token_mint == "token123"
        assert result.duration_seconds > 0
        assert len(result.errors) == 0

    async def test_discover_filters_unprofitable(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that unprofitable wallets are filtered out."""
        mock_helius_client.get_token_transactions.side_effect = [
            # Early buyers
            [{"buyer": "wallet1", "timestamp": datetime.utcnow(), "amount": 1.0}],
            # Sells - only 10% profit (below 50% threshold)
            [{"amount": 1.1}],
        ]

        token = TokenLaunch(
            mint="token123",
            symbol="TEST",
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        result = await scanner.discover_from_token(token, min_profit_pct=50.0)

        # Should not add any wallets due to low profit
        assert result.new_wallets == 0

    async def test_discover_handles_duplicate_wallets(
        self,
        scanner: WalletDiscoveryScanner,
        mock_wallet_repo: AsyncMock,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test that existing wallets are updated, not duplicated."""
        mock_wallet_repo.upsert.return_value = (MagicMock(spec=Wallet), False)  # Not new

        mock_helius_client.get_token_transactions.side_effect = [
            [{"buyer": "existing_wallet", "timestamp": datetime.utcnow(), "amount": 1.0}],
            [{"amount": 2.0}],
        ]

        token = TokenLaunch(
            mint="token123",
            launch_time=datetime.utcnow() - timedelta(hours=1),
        )

        result = await scanner.discover_from_token(token)

        assert result.new_wallets == 0
        assert result.updated_wallets == 1

    async def test_discover_from_multiple_tokens(
        self,
        scanner: WalletDiscoveryScanner,
        mock_helius_client: AsyncMock,
    ) -> None:
        """Test batch discovery from multiple tokens."""
        mock_helius_client.get_token_transactions.return_value = []

        tokens = [
            TokenLaunch(mint=f"token{i}", launch_time=datetime.utcnow())
            for i in range(3)
        ]

        results = await scanner.discover_from_multiple_tokens(tokens)

        assert len(results) == 3
        assert all(r.token_mint.startswith("token") for r in results)
```

## Implementation Tasks

- [x] Create `src/walltrack/data/models/wallet.py` with Wallet, WalletProfile, DiscoveryResult models
- [x] Create `src/walltrack/data/supabase/migrations/002_wallets.sql`
- [x] Create `src/walltrack/data/neo4j/schemas.py` with constraints
- [x] Create `src/walltrack/data/neo4j/queries/wallet.py`
- [x] Create `src/walltrack/data/supabase/repositories/wallet_repo.py`
- [x] Create `src/walltrack/discovery/scanner.py`
- [x] Create `src/walltrack/api/routes/wallets.py`
- [x] Add Supabase RPC function for increment_wallet_discovery
- [x] Write unit tests for scanner
- [x] Write integration tests for wallet repository

## Definition of Done

- [x] Discovery engine identifies early buyers
- [x] Wallets stored in both Supabase and Neo4j
- [x] No duplicate wallets created
- [x] Discovery results logged with counts and duration
- [x] All unit tests pass
- [x] mypy and ruff pass

## Implementation Notes

### Files Created
- `src/walltrack/data/models/wallet.py` - Wallet, WalletProfile, WalletStatus, TokenLaunch, DiscoveryResult models
- `src/walltrack/data/supabase/repositories/wallet_repo.py` - WalletRepository with CRUD operations
- `src/walltrack/data/neo4j/neo4j_client.py` - Neo4j client for graph operations
- `src/walltrack/discovery/scanner.py` - WalletDiscoveryScanner with batch discovery
- `src/walltrack/api/routes/wallets.py` - REST API endpoints for wallet operations
- `src/walltrack/api/dependencies.py` - FastAPI dependency injection

### Tests
- `tests/unit/discovery/test_scanner.py` - 12 tests for discovery scanner
- `tests/unit/data/test_wallet_repo.py` - Repository tests
- `tests/integration/` - Integration tests for Supabase and Neo4j

### Key Implementation Details
- Async discovery with configurable concurrency (semaphore-based)
- Upsert pattern for duplicate handling with discovery_count increment
- Neo4j wallet nodes with DISCOVERED_FROM relationships to tokens
- Full API with pagination, filtering by status/score
