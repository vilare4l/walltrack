# Story 13-13: Implement Automatic Network Discovery & Clustering on Wallet Onboarding

## Priority: MEDIUM

## Problem Statement

Currently, the entire clustering pipeline is 100% manual:
1. **Relations creation** (FUNDED_BY, BUYS_WITH) = Manual API calls
2. **Cluster discovery** = Manual button click
3. **Leader detection** = Manual button click
4. **Multiplier calculation** = Manual button click

This creates a completely disconnected experience where:
- Wallets are discovered and profiled automatically
- But their network relationships are never analyzed
- Clusters never form unless someone manually triggers each step

The system should automatically:
1. Analyze funding sources when a wallet is profiled
2. Detect synchronized buying patterns
3. Create Neo4j relationships
4. Discover connected wallets
5. Form clusters organically

## Current State

```
Wallet discovered → Profiled → Added to watchlist → STOP
                                        ↓
                         (No FUNDED_BY relations created)
                         (No BUYS_WITH relations created)
                         (No network discovery)
                         (No clustering)
                                        ↓
            [Manual] POST /clusters/analysis/funding → FUNDED_BY created
            [Manual] POST /clusters/analysis/sync-buys → BUYS_WITH created
            [Manual] Click "Discover Clusters" → Clusters formed
            [Manual] Click "Detect Leaders" → Leaders assigned
            [Manual] Click "Update Multipliers" → Multipliers calculated
```

**Problems:**
- 5 manual steps to get a cluster working
- Network context never available automatically
- Relations only created on-demand via API calls
- Helius API calls wasted (profiling fetches tx history but doesn't analyze it)

## Target State

```
Wallet A enters watchlist (score > threshold)
    ↓
1. Profile A (existing - fetches tx history from Helius)
    ↓
2. Analyze A's funding sources (reuse tx history)
   → Create FUNDED_BY relations in Neo4j
    ↓
3. Analyze A's recent token buys
   → Create BUYS_WITH relations for sync patterns
    ↓
4. Query Neo4j for connected wallets (1 hop)
    ↓
5. Quick-score each linked wallet
    ↓
6. If linked wallet qualifies:
   → Add to watchlist
   → Recurse (create its relations too)
    ↓
7. Auto-form cluster if >= 3 qualified wallets connected
    ↓
8. Detect leader + calculate multiplier immediately
```

## Required Implementation

### Phase 1: Create Unified Onboarding Service

**CREATE** `src/walltrack/services/wallet/network_onboarder.py`:

```python
"""
Unified wallet onboarding with automatic:
- Funding analysis (FUNDED_BY)
- Sync buy detection (BUYS_WITH)
- Network discovery
- Auto-clustering
"""

from dataclasses import dataclass
from walltrack.core.cluster.funding_analyzer import FundingAnalyzer
from walltrack.core.cluster.sync_detector import SyncBuyDetector
from walltrack.core.cluster.grouping import ClusterGrouper
from walltrack.core.cluster.leader_detection import LeaderDetector
from walltrack.core.cluster.signal_amplifier import SignalAmplifier

@dataclass
class OnboardingConfig:
    max_depth: int = 1
    min_quick_score: float = 0.4
    min_cluster_size: int = 3
    max_network_size: int = 20
    analyze_funding: bool = True
    analyze_sync_buys: bool = True
    sync_window_seconds: int = 300  # 5 min

@dataclass
class OnboardingResult:
    address: str
    relations_created: int
    network_size: int
    qualified_count: int
    cluster_id: str | None
    cluster_multiplier: float | None

class NetworkOnboarder:
    """Handles complete wallet onboarding with network analysis."""

    def __init__(
        self,
        funding_analyzer: FundingAnalyzer,
        sync_detector: SyncBuyDetector,
        grouper: ClusterGrouper,
        leader_detector: LeaderDetector,
        amplifier: SignalAmplifier,
        config: OnboardingConfig = None
    ):
        self.funding = funding_analyzer
        self.sync = sync_detector
        self.grouper = grouper
        self.leader = leader_detector
        self.amplifier = amplifier
        self.config = config or OnboardingConfig()
        self._processed: set[str] = set()

    async def onboard_wallet(
        self,
        address: str,
        tx_history: list[dict] | None = None,  # Reuse from profiling
        depth: int = 0
    ) -> OnboardingResult:
        """
        Complete wallet onboarding:
        1. Analyze funding (create FUNDED_BY)
        2. Analyze sync buys (create BUYS_WITH)
        3. Discover network from new relations
        4. Quick-score and recurse for qualified wallets
        5. Auto-cluster if enough connections
        """
        if address in self._processed:
            return OnboardingResult(address, skipped=True)

        if depth > self.config.max_depth:
            return OnboardingResult(address, skipped=True)

        self._processed.add(address)
        relations_created = 0

        # === STEP 1: Create FUNDED_BY relations ===
        if self.config.analyze_funding:
            funding_edges = await self.funding.analyze_wallet_funding(
                address,
                tx_history=tx_history  # Reuse if available
            )
            relations_created += len(funding_edges)

        # === STEP 2: Create BUYS_WITH relations ===
        if self.config.analyze_sync_buys:
            # Get recent tokens bought by this wallet
            recent_tokens = await self._get_recent_tokens(address, tx_history)

            for token in recent_tokens[:5]:  # Limit to 5 tokens
                sync_edges = await self.sync.detect_sync_buys_for_token(
                    token_mint=token,
                    wallets=[address],  # Will find other buyers
                    window_seconds=self.config.sync_window_seconds
                )
                relations_created += len(sync_edges)

        # === STEP 3: Discover network from Neo4j ===
        network = await self._discover_network(address)

        # === STEP 4: Quick-score and recurse ===
        qualified_wallets = []
        for linked in network[:self.config.max_network_size]:
            if linked in self._processed:
                continue

            score = await self._quick_score(linked)
            if score >= self.config.min_quick_score:
                qualified_wallets.append(linked)

                # Recurse for qualified wallets
                if depth < self.config.max_depth:
                    await self.onboard_wallet(linked, depth=depth + 1)

        # === STEP 5: Auto-cluster ===
        cluster_id = None
        multiplier = None
        all_members = [address] + qualified_wallets

        if len(all_members) >= self.config.min_cluster_size:
            # Create cluster
            cluster = await self.grouper.create_cluster_from_members(all_members)
            cluster_id = cluster.id

            # Detect leader
            await self.leader.detect_cluster_leader(cluster_id)

            # Calculate multiplier
            multiplier = await self.amplifier.calculate_cluster_multiplier(cluster_id)

        return OnboardingResult(
            address=address,
            relations_created=relations_created,
            network_size=len(network),
            qualified_count=len(qualified_wallets),
            cluster_id=cluster_id,
            cluster_multiplier=multiplier
        )

    async def _discover_network(self, address: str) -> list[str]:
        """Find wallets connected via FUNDED_BY or BUYS_WITH."""
        query = """
        MATCH (w:Wallet {address: $address})
        OPTIONAL MATCH (w)-[:FUNDED_BY|BUYS_WITH]-(linked:Wallet)
        RETURN DISTINCT linked.address as address
        """
        results = await self.queries.execute(query, {"address": address})
        return [r["address"] for r in results if r["address"]]

    async def _get_recent_tokens(
        self,
        address: str,
        tx_history: list[dict] | None
    ) -> list[str]:
        """Extract recent token mints from transaction history."""
        if tx_history:
            # Reuse existing data
            tokens = set()
            for tx in tx_history:
                if tx.get("type") == "SWAP":
                    for transfer in tx.get("tokenTransfers", []):
                        tokens.add(transfer.get("mint"))
            return list(tokens)[:10]
        else:
            # Fetch from Helius if not provided
            return await self.helius.get_wallet_tokens(address, limit=10)

    async def _quick_score(self, address: str) -> float:
        """Lightweight scoring from Neo4j stats."""
        query = """
        MATCH (w:Wallet {address: $address})
        OPTIONAL MATCH (w)-[:MADE]->(t:Trade)
        WITH w, count(t) as tx_count,
             sum(CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END) as wins
        RETURN tx_count,
               CASE WHEN tx_count > 0 THEN toFloat(wins)/tx_count ELSE 0 END as win_rate
        """
        result = await self.queries.execute(query, {"address": address})

        tx_score = min(1.0, result["tx_count"] / 50)
        return (tx_score * 0.3) + (result["win_rate"] * 0.7)
```

### Phase 2: Modify FundingAnalyzer to Reuse TX History

**MODIFY** `src/walltrack/core/cluster/funding_analyzer.py`:

```python
async def analyze_wallet_funding(
    self,
    address: str,
    tx_history: list[dict] | None = None  # NEW: reuse from profiling
) -> list[FundingEdge]:
    """Analyze funding sources, optionally reusing existing tx data."""

    if tx_history is None:
        # Fetch from Helius (existing behavior)
        tx_history = await self._helius.get_wallet_transactions(
            wallet=address,
            tx_types=["TRANSFER"],
            limit=100
        )

    # Filter to SOL transfers only
    sol_transfers = [tx for tx in tx_history if self._is_sol_transfer(tx)]

    # Create edges...
    edges = []
    for tx in sol_transfers:
        edge = await self._create_funding_edge(tx, address)
        if edge:
            edges.append(edge)

    return edges
```

### Phase 3: Integrate with Profiling

**MODIFY** `src/walltrack/services/wallet/profiler.py`:

```python
async def profile_wallet(
    self,
    address: str,
    auto_network_discovery: bool = True
) -> WalletProfile:
    """Profile wallet with optional automatic network discovery."""

    # Existing profiling logic
    tx_history = await self._helius.get_wallet_transactions(address, limit=100)
    profile = await self._calculate_profile(address, tx_history)

    # NEW: Trigger network onboarding if qualified
    if auto_network_discovery and profile.score >= WATCHLIST_THRESHOLD:
        onboarder = get_network_onboarder()
        await onboarder.onboard_wallet(
            address=address,
            tx_history=tx_history  # Reuse - no extra API calls!
        )

    return profile
```

### Phase 4: Update Discovery Task

**MODIFY** `src/walltrack/scheduler/tasks/discovery_task.py`:

```python
async def run_discovery_task(params: DiscoveryParams):
    """Discovery pipeline with automatic network analysis."""

    # Existing: Find pumped tokens, discover wallets
    tokens = await find_pumped_tokens()
    wallets = await discover_wallets_from_tokens(tokens)

    # Profile each wallet (now includes network discovery)
    for wallet in wallets:
        await profiler.profile_wallet(
            address=wallet.address,
            auto_network_discovery=True  # Triggers full onboarding
        )
```

### Phase 5: Fix WalletCache cluster_id Integration

**CRITICAL BUG**: Currently `WalletCache` always returns `cluster_id=None` (TODO comments in code). This means clusters are NEVER used during signal processing even if they exist in Neo4j.

**MODIFY** `src/walltrack/services/signal/wallet_cache.py`:

```python
class WalletCache:
    # ... existing code ...

    async def update_cluster_id(
        self,
        wallet_address: str,
        cluster_id: str,
        is_leader: bool = False
    ) -> None:
        """Update cluster_id for a cached wallet."""
        if wallet_address in self._cache:
            entry = self._cache[wallet_address]
            entry.cluster_id = cluster_id
            entry.is_leader = is_leader
            logger.debug(
                "wallet_cluster_updated",
                wallet=wallet_address,
                cluster_id=cluster_id,
                is_leader=is_leader
            )

    async def update_cluster_for_members(
        self,
        cluster_id: str,
        member_addresses: list[str],
        leader_address: str | None = None
    ) -> None:
        """Update cluster_id for all cluster members."""
        for address in member_addresses:
            is_leader = address == leader_address
            await self.update_cluster_id(address, cluster_id, is_leader)

    async def initialize(self) -> None:
        """Load initial wallet data from database."""
        # ... existing code ...

        # NEW: Load cluster memberships from Neo4j
        cluster_memberships = await self._load_cluster_memberships()
        for wallet_address, cluster_id, is_leader in cluster_memberships:
            if wallet_address in self._cache:
                self._cache[wallet_address].cluster_id = cluster_id
                self._cache[wallet_address].is_leader = is_leader

    async def _load_cluster_memberships(self) -> list[tuple[str, str, bool]]:
        """Load wallet->cluster mappings from Neo4j."""
        query = """
        MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster)
        RETURN w.address as wallet, c.id as cluster_id,
               CASE WHEN c.leader_address = w.address THEN true ELSE false END as is_leader
        """
        results = await self._neo4j.execute_query(query)
        return [(r["wallet"], r["cluster_id"], r["is_leader"]) for r in results]
```

**MODIFY** `src/walltrack/services/wallet/network_onboarder.py`:

Add cache update after cluster creation:

```python
async def onboard_wallet(self, address: str, ...):
    # ... existing code ...

    # After cluster creation
    if cluster_id:
        # Update cache for all members
        await self.wallet_cache.update_cluster_for_members(
            cluster_id=cluster_id,
            member_addresses=all_members,
            leader_address=leader_address
        )

    return OnboardingResult(...)
```

### Phase 6: Simplify UI

**MODIFY** `src/walltrack/ui/components/clusters.py`:

Remove manual buttons that are now automatic:
- ~~"Discover Clusters"~~ → Automatic on onboarding
- ~~"Analyze Funding"~~ → Automatic on onboarding
- ~~"Analyze Sync Buys"~~ → Automatic on onboarding

Keep for manual override:
- "Detect Leaders" (in case auto-detection missed)
- "Update Multipliers" (to recalculate)
- "Rebuild All" (full re-analysis)

## Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AUTOMATIC ONBOARDING FLOW                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Wallet A discovered (score > threshold)                             │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────┐                                             │
│  │ Profile A           │ ◄── Helius API: get transactions            │
│  │ (fetches tx_history)│     (SWAP, TRANSFER types)                  │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            │ tx_history passed down (reused, no extra API calls)     │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Analyze Funding     │ ◄── Parse SOL transfers from tx_history     │
│  │ (FundingAnalyzer)   │     Create FUNDED_BY edges in Neo4j         │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Analyze Sync Buys   │ ◄── For each recent token:                  │
│  │ (SyncBuyDetector)   │     - Find other buyers within 5 min        │
│  │                     │     - Create BUYS_WITH edges in Neo4j       │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Discover Network    │ ◄── Neo4j query: 1-hop from A               │
│  │ (from new relations)│     via FUNDED_BY | BUYS_WITH               │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Quick-score B,C,D   │ ◄── Lightweight Neo4j query                 │
│  │                     │     (tx_count + win_rate)                   │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ├── B score 0.6 ✓ → Recurse: onboard B (depth=1)          │
│            ├── C score 0.3 ✗ → Skip                                  │
│            └── D score 0.5 ✓ → Recurse: onboard D (depth=1)          │
│                                                                      │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Auto-cluster        │ ◄── A + B + D = 3 members                   │
│  │ [A, B, D]           │     → Create cluster in Neo4j               │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Detect Leader       │ ◄── Score members on funding influence,     │
│  │                     │     timing, centrality, performance         │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Calculate Multiplier│ ◄── 1.0 + size + cohesion + performance     │
│  │ = 1.4x              │     + leader bonus = final multiplier       │
│  └─────────┬───────────┘                                             │
│            │                                                         │
│            ▼                                                         │
│  ┌─────────────────────┐                                             │
│  │ Update WalletCache  │ ◄── Store cluster_id for A, B, D            │
│  │ cluster_id for      │     Mark leader (is_leader=true)            │
│  │ all members         │     O(1) lookup at signal time              │
│  └─────────────────────┘                                             │
│                                                                      │
│  ══════════════════════════════════════════════════════════════════  │
│  RESULT: Cluster ready for signal amplification                      │
│  - Relations: FUNDED_BY, BUYS_WITH created                           │
│  - Cluster: formed with 3 members                                    │
│  - Leader: detected                                                  │
│  - Multiplier: 1.4x calculated                                       │
│  - Cache updated: cluster_id available at signal time (O(1))         │
│  - Zero manual steps required                                        │
│  - Zero Neo4j queries at signal time                                 │
└──────────────────────────────────────────────────────────────────────┘
```

## Files Summary

### To CREATE
```
src/walltrack/services/wallet/network_onboarder.py (~250 lines)
```

### To MODIFY
```
src/walltrack/core/cluster/funding_analyzer.py (add tx_history param)
src/walltrack/core/cluster/sync_detector.py (add tx_history param)
src/walltrack/services/wallet/profiler.py (integrate onboarder)
src/walltrack/scheduler/tasks/discovery_task.py (enable auto-discovery)
src/walltrack/services/signal/wallet_cache.py (add cluster_id support - CRITICAL)
src/walltrack/ui/components/clusters.py (remove manual buttons)
src/walltrack/api/routes/clusters.py (add rebuild endpoint)
src/walltrack/services/config/models.py (add OnboardingConfig)
```

### To ADD TESTS
```
tests/unit/services/wallet/test_network_onboarder.py
```

## Acceptance Criteria

- [ ] Wallet profiling automatically triggers network analysis
- [ ] FUNDED_BY relations created from tx_history (no extra API call)
- [ ] BUYS_WITH relations created for recent tokens
- [ ] Network discovered from newly created relations
- [ ] Linked wallets quick-scored and qualified ones recursed
- [ ] Clusters auto-formed when >= 3 members connected
- [ ] Leader detected automatically on cluster creation
- [ ] Multiplier calculated automatically on cluster creation
- [ ] **WalletCache stores cluster_id for all cluster members**
- [ ] **WalletCache stores is_leader flag for cluster leader**
- [ ] **WalletCache loads cluster memberships on initialization**
- [ ] **Signal processing uses cached cluster_id (O(1), no Neo4j query)**
- [ ] tx_history reused (profiling API call not duplicated)
- [ ] Manual override still available via API
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes

## API Calls Comparison

| Step | BEFORE (Manual) | AFTER (Auto) |
|------|-----------------|--------------|
| Profile wallet | 1 Helius call | 1 Helius call (same) |
| Analyze funding | 1 Helius call (manual) | 0 (reuse tx_history) |
| Analyze sync buys | N Helius calls (manual) | N calls (but automatic) |
| Total per wallet | 2+ calls + manual work | 1 + N calls, zero manual |

## Configuration Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_depth` | `1` | Recursion hops (1 = direct network) |
| `min_quick_score` | `0.4` | Threshold for watchlist |
| `min_cluster_size` | `3` | Min members for cluster |
| `max_network_size` | `20` | Max wallets per hop |
| `analyze_funding` | `true` | Auto-create FUNDED_BY |
| `analyze_sync_buys` | `true` | Auto-create BUYS_WITH |
| `sync_window_seconds` | `300` | 5 min window for sync |

## Safeguards

1. **Loop Prevention**: `_processed` set tracks already-seen addresses
2. **Depth Limit**: `max_depth = 1` prevents explosion
3. **Network Cap**: `max_network_size = 20` per wallet
4. **Token Cap**: Max 5 tokens analyzed for sync buys
5. **TX Reuse**: Profiling tx_history passed down (no duplicate API calls)
6. **Async**: Non-blocking background execution

## Dependencies

- Existing FundingAnalyzer
- Existing SyncBuyDetector
- Existing ClusterGrouper
- Existing LeaderDetector
- Existing SignalAmplifier

## Estimated Effort

4-5 hours

## Impact

- **Full Automation**: From wallet discovery to cluster-ready in one flow
- **API Efficiency**: tx_history reused, fewer Helius calls
- **Zero Manual Steps**: Clusters form automatically
- **Immediate Context**: Network visible as soon as wallet is profiled
- **Simplified UI**: Remove 3+ manual buttons
