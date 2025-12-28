# Architecture Document: Epic 14 - System Simplification & Automation

**Version:** 1.0
**Date:** 2025-12-27
**Author:** Winston (Architect)
**Status:** DRAFT - Pending PM Review
**Origin:** Notes from TEA review in Epic 13 Phase D (Stories 13-11, 13-12, 13-13)

---

## Executive Summary

This document provides architectural guidance for Epic 14, which aims to simplify the WallTrack codebase by:

1. **Removing unused features** (Exit Simulation, What-If) - ~2,500 LOC reduction
2. **Simplifying signal scoring** - From ~1,500 LOC to ~400 LOC
3. **Automating wallet network discovery** - Zero manual clustering steps

These changes are interconnected and must be implemented in a specific order to avoid breaking the system.

---

## Table of Contents

1. [Current State Analysis](#1-current-state-analysis)
2. [ADR-001: Exit Simulation Removal](#adr-001-exit-simulation-removal)
3. [ADR-002: Signal Scoring Simplification](#adr-002-signal-scoring-simplification)
4. [ADR-003: Automatic Network Onboarding](#adr-003-automatic-network-onboarding)
5. [UI Gradio Changes](#5-ui-gradio-changes)
6. [Implementation Order & Dependencies](#6-implementation-order--dependencies)
7. [Risk Analysis](#7-risk-analysis)
8. [Story Decomposition for PM](#8-story-decomposition-for-pm)

---

## 1. Current State Analysis

### 1.1 Signal Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT SIGNAL PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Helius Webhook                                                  │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│  │ SignalFilter│────▶│SignalScorer │────▶│ Threshold   │        │
│  │ (wallet_    │     │ (707 LOC)   │     │ Checker     │        │
│  │  cache.py)  │     │             │     │ (184 LOC)   │        │
│  └─────────────┘     └─────────────┘     └─────────────┘        │
│        │                   │                    │                │
│        │                   ▼                    ▼                │
│        │            ┌─────────────┐     ┌─────────────┐         │
│        │            │ 4 Factors:  │     │ 2 Thresholds│         │
│        │            │ - Wallet 30%│     │ - 0.70 trade│         │
│        │            │ - Cluster25%│     │ - 0.85 high │         │
│        │            │ - Token 25% │     │             │         │
│        │            │ - Context20%│     │ 2 Tiers:    │         │
│        │            │             │     │ - STANDARD  │         │
│        │            │ 15+ criteria│     │ - HIGH      │         │
│        │            │ 30+ params  │     └─────────────┘         │
│        │            └─────────────┘                              │
│        │                                                         │
│        ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ WalletCache - CRITICAL BUG                               │    │
│  │ cluster_id = None  # TODO: Add cluster integration       │    │
│  │ is_leader = False  # Never populated from Neo4j          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Cluster Pipeline (100% Manual)

```
┌─────────────────────────────────────────────────────────────────┐
│                 CURRENT CLUSTERING (ALL MANUAL)                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Wallet Discovered ──▶ Profiled ──▶ Added to Watchlist ──▶ STOP │
│                                                                  │
│  [USER MUST MANUALLY]:                                           │
│                                                                  │
│  Step 1: POST /clusters/analysis/funding                         │
│          └── Creates FUNDED_BY edges in Neo4j                    │
│                                                                  │
│  Step 2: POST /clusters/analysis/sync-buys                       │
│          └── Creates BUYS_WITH edges in Neo4j                    │
│                                                                  │
│  Step 3: Click "Discover Clusters" button                        │
│          └── Runs ClusterGrouper.find_clusters()                 │
│                                                                  │
│  Step 4: Click "Detect Leaders" button                           │
│          └── Runs LeaderDetector.detect_cluster_leader()         │
│                                                                  │
│  Step 5: Click "Update Multipliers" button                       │
│          └── Runs SignalAmplifier.calculate_cluster_multiplier() │
│                                                                  │
│  RESULT: 5 manual steps, cluster_id NEVER reaches WalletCache    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Exit Simulation (Unused Feature)

```
┌─────────────────────────────────────────────────────────────────┐
│              EXIT SIMULATION FEATURE (TO REMOVE)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  UI Layer (~650 LOC):                                            │
│  ├── exit_simulator.py (251 lines) - Full page                   │
│  ├── whatif_modal.py (396 lines) - Modal component               │
│  └── Buttons in position_details_sidebar, positions_list         │
│                                                                  │
│  Service Layer (~1,200 LOC):                                     │
│  ├── services/exit/simulation_engine.py                          │
│  ├── services/exit/what_if_calculator.py                         │
│  ├── services/simulation/position_simulator.py                   │
│  ├── services/simulation/strategy_comparator.py                  │
│  └── services/simulation/global_analyzer.py                      │
│                                                                  │
│  API Layer (~240 LOC):                                           │
│  ├── POST /positions/simulate                                    │
│  └── GET /analysis/positions/{id}/compare-all                    │
│                                                                  │
│  Tests (~75KB):                                                   │
│  └── 6+ test files                                               │
│                                                                  │
│  STATUS: Never used in production, adds maintenance burden       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## ADR-001: Exit Simulation Removal

### Context

The Exit Simulation and What-If features were implemented speculatively but:
- Never reached production use
- Add ~2,500 lines of code to maintain
- Create cognitive load during development
- Have no active users or business requirement

### Decision

**REMOVE the Exit Simulation and What-If features entirely.**

### Consequences

**Positive:**
- Reduces codebase by ~2,500 LOC
- Faster test runs (fewer tests to execute)
- Simpler mental model for developers
- No migration needed (feature was never deployed)

**Negative:**
- Feature cannot be used if needed later (can restore from git)

### Implementation Strategy

This is a **surgical removal** with no architectural changes:

```
Phase 1: UI Layer Removal
├── DELETE exit_simulator.py
├── DELETE whatif_modal.py
├── MODIFY dashboard.py (remove tab)
├── MODIFY position_details_sidebar.py (remove button)
└── MODIFY positions_list.py (remove button)

Phase 2: Service Layer Removal
├── DELETE services/exit/simulation_engine.py
├── DELETE services/exit/what_if_calculator.py
├── DELETE services/simulation/ (entire folder)
└── MODIFY services/exit/__init__.py (remove exports)

Phase 3: API Layer Removal
└── MODIFY routes/positions.py (remove 2 endpoints + models)

Phase 4: Test & Doc Cleanup
├── DELETE 6 test files
├── DELETE docs/(To review) epic-12-positions-whatif/
└── UPDATE E2E test references
```

### Validation

- `uv run pytest` passes
- `uv run mypy src/` passes
- `uv run ruff check src/` passes
- Application starts without import errors
- No dead imports remain

---

## ADR-002: Signal Scoring Simplification

### Context

The current scoring system is over-engineered:

| Metric | Current | Problem |
|--------|---------|---------|
| Lines of Code | ~1,500 | Too complex to maintain |
| Scoring Factors | 4 | Context Score is 2/3 placeholders |
| Sub-criteria | 15+ | Many add minimal value |
| Config Parameters | 30+ | Overwhelming for users |
| Thresholds | 2 (0.70, 0.85) | Arbitrary distinction |

**Specific Issues:**

1. **Context Score (20%)**: Only `time_of_day` is real; `volatility_score` and `activity_score` are hardcoded placeholders
2. **Token Score complexity**: Liquidity, mcap, holders, volume calculations when a binary safety check suffices
3. **Wallet Consistency**: Complex calculation for ~4.5% impact on final score
4. **Dual thresholds**: No clear business rationale for HIGH vs STANDARD distinction

### Decision

**SIMPLIFY to a 3-component model:**

```python
# NEW SCORING MODEL

def should_trade(signal, wallet, token, cluster) -> TradeDecision:

    # 1. TOKEN SAFETY FILTER (Binary - blocks scams)
    if not is_token_safe(token):
        return NO_TRADE, reason="token_unsafe"

    # 2. WALLET SCORE (Simple: 60% win_rate + 40% PnL)
    wallet_score = calculate_wallet_score(wallet)

    # 3. CLUSTER BOOST (Multiplier 1.0x to 1.8x)
    cluster_boost = cluster.amplification_factor or 1.0

    # 4. FINAL DECISION
    final_score = wallet_score * cluster_boost

    if final_score >= TRADE_THRESHOLD:  # 0.65
        return TRADE, position_multiplier=cluster_boost
    else:
        return NO_TRADE, reason="below_threshold"


def is_token_safe(token) -> bool:
    """Binary safety gate - no gradations."""
    if token.is_honeypot:
        return False
    if token.has_freeze_authority:
        return False
    if token.has_mint_authority:
        return False
    return True


def calculate_wallet_score(wallet) -> float:
    """Simplified wallet quality metric."""
    win_rate = wallet.profile.win_rate or 0.0
    pnl_norm = normalize_pnl(wallet.profile.avg_pnl_per_trade)

    score = (win_rate * 0.6) + (pnl_norm * 0.4)

    # Leader bonus (from cluster context)
    if wallet.is_cluster_leader:
        score *= 1.15

    return min(1.0, score)
```

### Comparison

| Aspect | Before | After |
|--------|--------|-------|
| Lines of Code | ~1,500 | ~400 |
| Scoring Factors | 4 weighted | 2 + 1 filter |
| Sub-criteria | 15+ | 4 |
| Config Parameters | 30+ | ~8 |
| Thresholds | 2 (0.70, 0.85) | 1 (0.65) |
| Token Handling | Complex score | Binary safe/unsafe |
| Context Score | 3 components (2 fake) | Removed |

### Architectural Impact

```
BEFORE:
┌────────────────────────────────────────────────────────────┐
│ SignalScorer.score()                                        │
│   ├── _calculate_wallet_score() ──▶ FactorScore (30%)      │
│   │     ├── win_rate (35%)                                  │
│   │     ├── pnl (25%)                                       │
│   │     ├── timing_percentile (25%)      ◀── Remove        │
│   │     ├── consistency (15%)            ◀── Remove        │
│   │     ├── leader_bonus                                    │
│   │     └── decay_penalty                                   │
│   │                                                         │
│   ├── _calculate_cluster_score() ──▶ FactorScore (25%)     │
│   │     └── (keep as-is, already simple)                   │
│   │                                                         │
│   ├── _calculate_token_score() ──▶ FactorScore (25%)       │
│   │     ├── liquidity_score              ◀── Remove        │
│   │     ├── mcap_score                   ◀── Remove        │
│   │     ├── holder_distribution_score    ◀── Remove        │
│   │     ├── volume_score                 ◀── Remove        │
│   │     ├── age_penalty                  ◀── Remove        │
│   │     └── honeypot_risk                ◀── Keep (binary) │
│   │                                                         │
│   └── _calculate_context_score() ──▶ FactorScore (20%)     │
│         ├── time_of_day_score            ◀── Remove        │
│         ├── volatility_score (fake)      ◀── Remove        │
│         └── activity_score (fake)        ◀── Remove        │
└────────────────────────────────────────────────────────────┘

AFTER:
┌────────────────────────────────────────────────────────────┐
│ SignalScorer.score()                                        │
│   │                                                         │
│   ├── is_token_safe(token) ──▶ bool                        │
│   │     ├── is_honeypot                                     │
│   │     ├── has_freeze_authority                            │
│   │     └── has_mint_authority                              │
│   │     (Early return if False)                             │
│   │                                                         │
│   ├── calculate_wallet_score(wallet) ──▶ float             │
│   │     ├── win_rate (60%)                                  │
│   │     ├── pnl_normalized (40%)                            │
│   │     └── leader_bonus (×1.15)                            │
│   │                                                         │
│   └── apply_cluster_boost(cluster) ──▶ float               │
│         └── amplification_factor (1.0 - 1.8)                │
│                                                             │
│   FINAL = wallet_score × cluster_boost                      │
└────────────────────────────────────────────────────────────┘
```

### Model Changes

```python
# BEFORE: Complex nested structures
@dataclass
class ScoredSignal:
    wallet_score: FactorScore
    cluster_score: FactorScore
    token_score: FactorScore        # REMOVE
    context_score: FactorScore      # REMOVE
    wallet_components: WalletScoreComponents
    cluster_components: ClusterScoreComponents
    token_components: TokenScoreComponents    # REMOVE
    context_components: ContextScoreComponents  # REMOVE
    weights_used: ScoringWeights

# AFTER: Flat simple structure
@dataclass
class ScoredSignal:
    final_score: float
    wallet_score: float
    cluster_boost: float
    token_safe: bool
    is_leader: bool
    explanation: str
```

### Configuration Changes

```python
# BEFORE: 30+ parameters in ScoringConfig
wallet_weight, cluster_weight, token_weight, context_weight,
wallet_win_rate_weight, wallet_pnl_weight, wallet_timing_weight,
wallet_consistency_weight, wallet_leader_bonus, wallet_max_decay_penalty,
token_liquidity_weight, token_mcap_weight, token_holder_dist_weight,
token_volume_weight, token_min_liquidity_usd, token_optimal_liquidity_usd,
token_min_mcap_usd, token_optimal_mcap_usd, new_token_penalty_minutes,
max_new_token_penalty, solo_signal_base, peak_trading_hours_utc, ...

# AFTER: ~8 parameters
TRADE_THRESHOLD = 0.65
WALLET_WIN_RATE_WEIGHT = 0.60
WALLET_PNL_WEIGHT = 0.40
LEADER_BONUS = 1.15
PNL_NORMALIZE_MIN = -100
PNL_NORMALIZE_MAX = 500
MIN_CLUSTER_BOOST = 1.0
MAX_CLUSTER_BOOST = 1.8
```

### Validation Requirements

**CRITICAL**: Before implementing, validate the new formula against historical data:

1. Export last 30 days of signals with old scores
2. Recalculate with new formula
3. Compare: false positives, false negatives, score distribution
4. Threshold 0.65 should yield similar trade eligibility rate

---

## ADR-003: Automatic Network Onboarding

### Context

The current clustering system requires 5 manual steps and has a **critical bug**: `WalletCache.cluster_id` is always `None` because cluster data from Neo4j is never loaded into the cache.

This means:
- Clusters exist in Neo4j but are **never used** during signal processing
- The `cluster_score` factor (25% of total) always returns `solo_signal_base = 0.50`
- All the clustering work is wasted

### Decision

**CREATE a NetworkOnboarder service** that:
1. Automatically analyzes funding sources when a wallet is profiled
2. Automatically detects synchronized buying patterns
3. Creates Neo4j relationships (FUNDED_BY, BUYS_WITH)
4. Discovers connected wallets recursively (depth-limited)
5. Auto-forms clusters when >= 3 qualified wallets are connected
6. Updates WalletCache with cluster_id for O(1) lookups

### Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AUTOMATIC ONBOARDING FLOW                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Wallet A discovered (score > threshold)                              │
│       │                                                               │
│       ▼                                                               │
│  ┌─────────────────────┐                                              │
│  │ WalletProfiler      │ ◀── Helius API: get transactions             │
│  │ profile_wallet()    │     Returns tx_history                       │
│  └─────────┬───────────┘                                              │
│            │                                                          │
│            │ tx_history passed to NetworkOnboarder (REUSED)           │
│            ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    NetworkOnboarder                              │ │
│  │  onboard_wallet(address, tx_history, depth=0)                   │ │
│  │                                                                  │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │ Step 1: Analyze Funding (reuse tx_history)                │  │ │
│  │  │         FundingAnalyzer.analyze_wallet_funding()          │  │ │
│  │  │         ──▶ Creates FUNDED_BY edges in Neo4j              │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  │                           │                                      │ │
│  │                           ▼                                      │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │ Step 2: Analyze Sync Buys (for recent tokens)             │  │ │
│  │  │         SyncBuyDetector.detect_sync_buys_for_token()      │  │ │
│  │  │         ──▶ Creates BUYS_WITH edges in Neo4j              │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  │                           │                                      │ │
│  │                           ▼                                      │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │ Step 3: Discover Network (1-hop query)                    │  │ │
│  │  │         Neo4j: MATCH via FUNDED_BY|BUYS_WITH              │  │ │
│  │  │         ──▶ Returns list of connected wallet addresses    │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  │                           │                                      │ │
│  │                           ▼                                      │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │ Step 4: Quick-score linked wallets                        │  │ │
│  │  │         Neo4j lightweight query (tx_count + win_rate)     │  │ │
│  │  │         If score >= 0.4 ──▶ Add to qualified list         │  │ │
│  │  │         If depth < max_depth ──▶ Recurse                  │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  │                           │                                      │ │
│  │                           ▼                                      │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │ Step 5: Auto-cluster (if >= 3 qualified)                  │  │ │
│  │  │         ClusterGrouper.create_cluster_from_members()      │  │ │
│  │  │         LeaderDetector.detect_cluster_leader()            │  │ │
│  │  │         SignalAmplifier.calculate_cluster_multiplier()    │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  │                           │                                      │ │
│  │                           ▼                                      │ │
│  │  ┌───────────────────────────────────────────────────────────┐  │ │
│  │  │ Step 6: Update WalletCache (CRITICAL FIX)                 │  │ │
│  │  │         wallet_cache.update_cluster_for_members()         │  │ │
│  │  │         ──▶ cluster_id now available at signal time       │  │ │
│  │  │         ──▶ O(1) lookup, no Neo4j query needed            │  │ │
│  │  └───────────────────────────────────────────────────────────┘  │ │
│  │                                                                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│  RESULT:                                                              │
│  - Relations created automatically                                    │
│  - Cluster formed automatically                                       │
│  - Leader detected automatically                                      │
│  - Multiplier calculated automatically                                │
│  - WalletCache updated with cluster_id                                │
│  - Zero manual steps                                                  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Critical Fix: WalletCache Integration

The current `WalletCache` has these TODOs that must be fixed:

```python
# wallet_cache.py:73-74 (current)
cluster_id=None,  # TODO: Add cluster integration in Epic 2
is_leader=False,

# wallet_cache.py:149 (current)
cluster_id=None,  # TODO: Add cluster integration
```

**Required changes to WalletCache:**

```python
class WalletCache:

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
        MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster)
        RETURN w.address as wallet,
               c.id as cluster_id,
               CASE WHEN c.leader_address = w.address
                    THEN true ELSE false END as is_leader
        """
        results = await self._neo4j.execute_query(query)
        return [(r["wallet"], r["cluster_id"], r["is_leader"]) for r in results]

    async def update_cluster_for_members(
        self,
        cluster_id: str,
        member_addresses: list[str],
        leader_address: str | None = None
    ) -> None:
        """Update cluster_id for all cluster members."""
        for address in member_addresses:
            if address in self._cache:
                entry = self._cache[address]
                entry.cluster_id = cluster_id
                entry.is_leader = (address == leader_address)
```

### Safeguards Against Runaway Recursion

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `max_depth` | 1 | Only 1-hop recursion (direct connections) |
| `min_quick_score` | 0.4 | Threshold for watchlist qualification |
| `min_cluster_size` | 3 | Minimum members to form cluster |
| `max_network_size` | 20 | Cap on wallets analyzed per hop |
| `_processed` set | - | Prevents re-analyzing same wallet |

### API Call Efficiency

| Step | Before (Manual) | After (Auto) |
|------|-----------------|--------------|
| Profile wallet | 1 Helius call | 1 Helius call (same) |
| Analyze funding | 1 Helius call (manual) | 0 (reuse tx_history) |
| Analyze sync buys | N calls (manual) | N calls (automatic) |
| **Total per wallet** | **2+ calls + manual work** | **1 + N calls, zero manual** |

---

## 5. UI Gradio Changes

### Overview

L'UI Gradio subit des modifications significatives dans cet epic. Ce n'est pas du simple cleanup - c'est une refonte de l'expérience utilisateur pour refléter le modèle simplifié.

### 5.1 Composants à SUPPRIMER (Exit Simulation)

```
┌─────────────────────────────────────────────────────────────────┐
│                    UI FILES TO DELETE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PAGES (full pages):                                             │
│  ├── ui/pages/exit_simulator.py (251 lines)                      │
│  │   └── Full "Exit Simulator" tab in dashboard                  │
│  │                                                               │
│  COMPONENTS (modals & widgets):                                  │
│  ├── ui/components/whatif_modal.py (396 lines)                   │
│  │   └── "What-If Analysis" modal opened from positions          │
│  │                                                               │
│  │                                                               │
│  INTEGRATION POINTS TO CLEAN:                                    │
│  ├── ui/dashboard.py                                             │
│  │   └── Remove "Exit Simulator" tab from main tabs list         │
│  │                                                               │
│  ├── ui/components/position_details_sidebar.py                   │
│  │   └── Remove "What-If Analysis" button                        │
│  │   └── Remove whatif_modal imports                             │
│  │                                                               │
│  ├── ui/components/positions_list.py                             │
│  │   └── Remove "Simulate" action button                         │
│  │   └── Remove whatif-related handlers                          │
│  │                                                               │
│  ├── ui/pages/__init__.py                                        │
│  │   └── Remove exit_simulator export                            │
│  │                                                               │
│  └── ui/components/__init__.py                                   │
│      └── Remove whatif_modal export                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Config Panel - Refonte Majeure (Scoring)

Le composant `config_panel.py` (690 lignes) doit être simplifié significativement.

#### AVANT: 4 Facteurs avec Pie Chart

```
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT CONFIG PANEL (690 lines)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tab 1: Score Weights                                            │
│  ├── Wallet Weight Slider (0-0.5)     [====30%====]              │
│  ├── Cluster Weight Slider (0-0.5)    [===25%===]                │
│  ├── Token Weight Slider (0-0.5)      [===25%===]    ◀── REMOVE  │
│  ├── Context Weight Slider (0-0.5)    [==20%==]      ◀── REMOVE  │
│  ├── "Total: 1.000 (valid)" display                              │
│  ├── [Normalize] [Apply Weights] buttons                         │
│  └── Pie Chart (4 sectors)                           ◀── SIMPLIFY│
│                                                                  │
│  Tab 2: Trade Threshold                                          │
│  ├── Trade Threshold Slider (0.70)                   ◀── CHANGE  │
│  ├── High Conviction Slider (0.85)                   ◀── REMOVE  │
│  ├── Position Sizing Tiers Table                     ◀── SIMPLIFY│
│  └── [Reset to Defaults] button                                  │
│                                                                  │
│  Tab 3: Score Preview                                            │
│  ├── Wallet Factors: win_rate, pnl, timing, is_leader            │
│  ├── Token/Cluster Factors: cluster_size, liquidity, mcap, age   │
│  ├── [Calculate Preview] button                      ◀── SIMPLIFY│
│  └── Results Table (4 factors breakdown)             ◀── SIMPLIFY│
│                                                                  │
│  Tab 4: Signal Analysis                                          │
│  └── Table: Time, Wallet, Token, Score, W, C, T, X, Status       │
│                                                      ◀── SIMPLIFY│
└─────────────────────────────────────────────────────────────────┘
```

#### APRÈS: Modèle Simplifié

```
┌─────────────────────────────────────────────────────────────────┐
│  NEW CONFIG PANEL (~250 lines)                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Tab 1: Scoring Config                                           │
│  ├── Trade Threshold Slider (0.65)                               │
│  │   └── Single threshold, pas de HIGH/STANDARD distinction      │
│  │                                                               │
│  ├── Wallet Score Weights                                        │
│  │   ├── Win Rate Weight Slider (0.60)                           │
│  │   └── PnL Weight Slider (0.40)                                │
│  │                                                               │
│  ├── Cluster Boost Range                                         │
│  │   ├── Min Boost (1.0x)                                        │
│  │   └── Max Boost (1.8x)                                        │
│  │                                                               │
│  ├── Leader Bonus (1.15x)                                        │
│  │                                                               │
│  └── [Apply] [Reset to Defaults] buttons                         │
│                                                                  │
│  Tab 2: Score Preview (simplified)                               │
│  ├── Wallet Inputs: win_rate, avg_pnl, is_leader                 │
│  ├── Cluster Input: boost_multiplier (1.0-1.8)                   │
│  ├── [Calculate] button                                          │
│  └── Result: wallet_score × cluster_boost = final (pass/fail)   │
│                                                                  │
│  Tab 3: Signal Analysis (simplified columns)                     │
│  └── Table: Time, Wallet, Token, Score, Cluster, Status          │
│      (removed: Token Score, Context Score columns)               │
│                                                                  │
│  REMOVED ENTIRELY:                                               │
│  ├── Pie Chart (no more 4-factor weighting)                      │
│  ├── Token Weight / Context Weight sliders                       │
│  ├── High Conviction threshold                                   │
│  └── Complex Score Preview with 8 inputs                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Clusters Tab - Simplification des Actions Manuelles

Le composant `clusters.py` (352 lignes) garde sa structure mais les boutons manuels deviennent des "overrides".

#### AVANT: 4 Boutons Manuels Obligatoires

```
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT CLUSTERS TAB                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Actions Panel:                                                  │
│  ├── [Discover Clusters]      ◀── Required manual step 1         │
│  ├── [Analyze Co-occurrence]  ◀── Required manual step 2         │
│  ├── [Detect Leaders]         ◀── Required manual step 3         │
│  ├── [Update Multipliers]     ◀── Required manual step 4         │
│  └── [Refresh]                                                   │
│                                                                  │
│  User MUST click these 4 buttons in order for clusters to work  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### APRÈS: Actions Automatiques avec Override Manuel

```
┌─────────────────────────────────────────────────────────────────┐
│  NEW CLUSTERS TAB                                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Info Banner:                                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ ℹ️ Clusters are now created automatically when wallets are  ││
│  │ onboarded. Use "Rebuild All" only to force recalculation.   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  Actions Panel:                                                  │
│  ├── [Refresh]                   ◀── Primary action              │
│  ├── [Rebuild All]               ◀── Force full recalculation    │
│  │   └── Combines: Discovery + Co-occurrence + Leaders + Mult.  │
│  └── [Settings ⚙️]               ◀── Opens onboarding config     │
│                                                                  │
│  Advanced Actions (collapsed by default):                        │
│  ├── [Run Discovery Only]                                        │
│  ├── [Analyze Co-occurrence Only]                                │
│  ├── [Detect Leaders Only]                                       │
│  └── [Update Multipliers Only]                                   │
│                                                                  │
│  New: Onboarding Config Section                                  │
│  ├── Max Recursion Depth: [1] ▼                                  │
│  ├── Min Quick Score: [0.4] slider                               │
│  ├── Min Cluster Size: [3] ▼                                     │
│  ├── Max Network Size: [20] ▼                                    │
│  └── [Save Onboarding Settings]                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.4 Signals Component - Columns Simplifiées

Le composant `signals.py` (103 lignes) reste similaire mais les colonnes changent.

```
AVANT:
| Time | Wallet | Token | Score | W | C | T | X | Status |

APRÈS:
| Time | Wallet | Token | Score | Cluster | Status |

Notes:
- "W" (wallet_score) intégré dans "Score" (c'est le score principal)
- "C" (cluster_score) → devient "Cluster" (le boost factor, ex: "1.4x")
- "T" (token_score) → SUPPRIMÉ (binary check, pas affiché)
- "X" (context_score) → SUPPRIMÉ
```

### 5.5 Position Details Sidebar - Cleanup

```python
# position_details_sidebar.py - CHANGES

# REMOVE these imports:
- from walltrack.ui.components.whatif_modal import create_whatif_modal

# REMOVE these UI elements:
- whatif_btn = gr.Button("What-If Analysis", variant="secondary")
- whatif_modal = create_whatif_modal(...)

# REMOVE these event handlers:
- whatif_btn.click(fn=open_whatif_modal, ...)

# KEEP all other position management features:
- Close position button
- Change strategy button
- Position details display
```

### 5.6 Dashboard Tab Order

```python
# dashboard.py - CHANGES

# BEFORE:
tabs = [
    ("Home", create_home_tab),
    ("Explorer", create_explorer_tab),
    ("Positions", create_positions_tab),
    ("Exit Strategies", create_exit_strategies_tab),
    ("Exit Simulator", create_exit_simulator_tab),  # ◀── REMOVE
    ("Clusters", create_clusters_tab),
    ("Alerts", create_alerts_tab),
    ("Orders", create_orders_tab),
    ("Settings", create_settings_tab),
]

# AFTER:
tabs = [
    ("Home", create_home_tab),
    ("Explorer", create_explorer_tab),
    ("Positions", create_positions_tab),
    ("Exit Strategies", create_exit_strategies_tab),
    ("Clusters", create_clusters_tab),  # Updated UI
    ("Alerts", create_alerts_tab),
    ("Orders", create_orders_tab),
    ("Settings", create_settings_tab),  # Updated scoring config
]
```

### 5.7 Summary of UI Changes by File

| File | Action | Lines Before | Lines After | Change |
|------|--------|--------------|-------------|--------|
| `pages/exit_simulator.py` | DELETE | 251 | 0 | -251 |
| `components/whatif_modal.py` | DELETE | 396 | 0 | -396 |
| `components/config_panel.py` | REWRITE | 690 | ~250 | -440 |
| `components/clusters.py` | MODIFY | 352 | ~300 | -52 |
| `components/signals.py` | MODIFY | 103 | ~90 | -13 |
| `components/position_details_sidebar.py` | MODIFY | ~300 | ~260 | -40 |
| `components/positions_list.py` | MODIFY | ~250 | ~220 | -30 |
| `dashboard.py` | MODIFY | ~150 | ~140 | -10 |
| `pages/__init__.py` | MODIFY | ~20 | ~15 | -5 |
| `components/__init__.py` | MODIFY | ~30 | ~25 | -5 |
| **TOTAL UI** | | **~2742** | **~1300** | **-1442** |

---

## 6. Implementation Order & Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                   IMPLEMENTATION ORDER                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  WEEK 1: Cleanup & Foundation                                    │
│  ═══════════════════════════════                                 │
│                                                                  │
│  Story A: Exit Simulation Removal (ADR-001)                      │
│  ├── No dependencies                                             │
│  ├── Can be done in parallel with others                         │
│  └── Reduces noise for subsequent work                           │
│                                                                  │
│  Story B: WalletCache cluster_id Fix (Part of ADR-003)           │
│  ├── CRITICAL: Must be done before scoring changes               │
│  ├── Unblocks cluster amplification                              │
│  └── Small change, high impact                                   │
│                                                                  │
│  ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  WEEK 2: Scoring Simplification                                  │
│  ══════════════════════════════                                  │
│                                                                  │
│  Story C: Scoring Simplification (ADR-002)                       │
│  ├── Depends on: Story B (cluster_id in cache)                   │
│  ├── Changes SignalScorer, ThresholdChecker                      │
│  ├── Changes models/scoring.py                                   │
│  ├── Updates config parameters                                   │
│  └── Requires formula validation against historical data         │
│                                                                  │
│  ─────────────────────────────────────────────────────────────── │
│                                                                  │
│  WEEK 3: Automation                                              │
│  ══════════════════                                              │
│                                                                  │
│  Story D: Network Onboarder (ADR-003)                            │
│  ├── Depends on: Story B, Story C                                │
│  ├── Creates new NetworkOnboarder service                        │
│  ├── Modifies FundingAnalyzer (tx_history param)                 │
│  ├── Modifies WalletProfiler (auto_network_discovery)            │
│  └── Simplifies Clusters UI (remove manual buttons)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Dependency Graph

```
Story A (Exit Removal)
    │
    │ (independent)
    │
    ▼
[Can ship independently]


Story B (WalletCache Fix)
    │
    │ (required for)
    │
    ├──────────────────────┐
    ▼                      ▼
Story C (Scoring)     Story D (Onboarder)
    │                      │
    │ (required for)       │
    └──────────┬───────────┘
               ▼
        [Full system works]
```

---

## 7. Risk Analysis

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Scoring formula change affects trade quality | Trade decisions may be worse | Validate against 30 days of historical signals before deploying |
| Recursive onboarding causes API rate limits | Helius API throttling | Safeguards: max_depth=1, max_network_size=20 |
| WalletCache memory growth from cluster data | OOM in long-running process | Monitor cache size, implement eviction for cluster data |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Exit Simulation removal breaks unknown dependency | Runtime error | Comprehensive grep for all imports before deletion |
| Config migration loses user customizations | User frustration | Export current config before migration, provide defaults |
| Neo4j query latency during initialization | Slow startup | Async loading, don't block on cluster data |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| Test coverage gaps after removal | Regressions | Run full test suite, add integration tests |
| Documentation out of sync | Developer confusion | Update docs as part of each PR |

---

## 8. Story Decomposition for PM

Based on the architectural analysis, here is the recommended story breakdown for **Epic 14**.

---

### Story 14-1: Exit Simulation Removal (UI + Backend Cleanup)

**Type:** Tech Debt / Cleanup
**Complexity:** Low
**Estimated Effort:** 3-4 hours
**Dependencies:** None

**Scope Backend:**
- DELETE `services/exit/simulation_engine.py`
- DELETE `services/exit/what_if_calculator.py`
- DELETE `services/simulation/` (entire folder)
- MODIFY `routes/positions.py` (remove 2 endpoints + models)
- DELETE 6 test files

**Scope UI Gradio:**
- DELETE `ui/pages/exit_simulator.py` (251 lines)
- DELETE `ui/components/whatif_modal.py` (396 lines)
- MODIFY `ui/dashboard.py` - Remove "Exit Simulator" tab
- MODIFY `ui/components/position_details_sidebar.py` - Remove "What-If Analysis" button
- MODIFY `ui/components/positions_list.py` - Remove "Simulate" action button
- MODIFY `ui/pages/__init__.py` - Remove exit_simulator export
- MODIFY `ui/components/__init__.py` - Remove whatif_modal export

**Acceptance Criteria:**
- All exit simulation code removed (backend + UI)
- "Exit Simulator" tab no longer appears in dashboard
- "What-If" and "Simulate" buttons removed from position views
- All tests pass
- No dead imports remain
- Application starts without errors
- No console errors in Gradio UI

**Notes for DEV:**
- Start with UI deletion, then backend
- Run `git grep -l "simulation\|whatif\|what_if\|exit_simul"` to find any missed references
- Delete documentation: `docs/sprint-artifacts/(To review) epic-12-positions-whatif/`

---

### Story 14-2: WalletCache Cluster Integration

**Type:** Bug Fix / Critical
**Complexity:** Medium
**Estimated Effort:** 2-3 hours
**Dependencies:** None
**MUST BE DONE BEFORE Story 14-3**

**Scope Backend:**
- MODIFY `WalletCache.initialize()` to load cluster memberships from Neo4j
- ADD `update_cluster_for_members()` method
- ADD `_load_cluster_memberships()` method
- ADD Neo4j client dependency to WalletCache
- MODIFY `WalletCacheEntry` model to ensure `cluster_id` and `is_leader` are used

**Scope UI Gradio:**
- None (backend only fix)

**Acceptance Criteria:**
- `cluster_id` is populated from Neo4j on cache initialization
- `is_leader` flag is correctly set for cluster leaders
- Cache can be updated when new clusters are formed
- Signal scoring receives correct cluster context
- Logs show cluster_id in signal processing

**Notes for DEV:**
- This fixes a fundamental bug where cluster data is never used
- Neo4j query should be async and non-blocking
- Consider fallback if Neo4j is unavailable
- Test by checking signal logs include cluster_id

---

### Story 14-3: Scoring Simplification (Backend + UI)

**Type:** Refactoring
**Complexity:** High
**Estimated Effort:** 5-6 hours
**Dependencies:** Story 14-2 (WalletCache fix)

**Scope Backend:**
- REWRITE `SignalScorer` (707 → ~200 lines)
- SIMPLIFY `ThresholdChecker` (184 → ~50 lines)
- SIMPLIFY `models/scoring.py` structures
- REDUCE `constants/scoring.py` (30+ → ~8 params)
- UPDATE `ScoringConfig` in config service
- MODIFY `SignalPipeline` to use new scoring model

**Scope Database (Migration Required):**
```sql
-- V19__simplify_signals_scores.sql
-- Option A: Drop columns (if no historical analysis needed)
ALTER TABLE signals DROP COLUMN IF EXISTS token_score;
ALTER TABLE signals DROP COLUMN IF EXISTS context_score;

-- Option B: Keep deprecated (recommended for historical data)
COMMENT ON COLUMN signals.token_score IS 'DEPRECATED: Removed in Epic 14. Binary token safety check now.';
COMMENT ON COLUMN signals.context_score IS 'DEPRECATED: Removed in Epic 14. Context scoring eliminated.';

-- Update cluster_score semantics
COMMENT ON COLUMN signals.cluster_score IS 'Cluster boost multiplier (1.0-1.8x). Was percentage score.';
```

**Scope UI Gradio (Major Refonte - See Section 5.2):**
- REWRITE `ui/components/config_panel.py` (690 → ~250 lines)
  - REMOVE Token Weight slider
  - REMOVE Context Weight slider
  - REMOVE High Conviction threshold slider
  - REMOVE Pie Chart visualization
  - REMOVE 8-input Score Preview (replace with 4-input)
  - ADD single Trade Threshold slider (0.65 default)
  - ADD Wallet Score weights (win_rate 60%, pnl 40%)
  - ADD Cluster Boost range config (1.0x - 1.8x)
  - ADD Leader Bonus config (1.15x)
  - SIMPLIFY Signal Analysis table columns
- MODIFY `ui/components/signals.py`
  - Change columns from `| W | C | T | X |` to `| Cluster |`
  - Cluster column shows boost factor (e.g., "1.4x")

**Acceptance Criteria:**
- Token safety is binary check (3 conditions)
- Wallet score uses only win_rate (60%) + PnL (40%) + leader bonus
- Cluster boost is direct multiplier (1.0-1.8x)
- Context score completely removed
- Single trade threshold (0.65)
- Code reduced from ~1,500 to ~400 lines (backend)
- Config Panel UI reduced from 690 to ~250 lines
- Pie Chart removed from Settings
- All tests updated and passing
- UI shows simplified scoring model

**CRITICAL Validation Step:**
Before merging, export last 30 days of signals and compare:
- Old scores vs new scores distribution
- Trade eligibility rate (should be similar)
- No significant increase in false positives

**Notes for DEV:**
- Do backend first, then UI
- Keep the simplified `ScoredSignal` model backward-compatible for logging
- Remove unused imports from models
- API endpoints for scoring config must be updated to match new parameters

---

### Story 14-4: Automatic Network Onboarding (Backend + UI)

**Type:** New Feature
**Complexity:** High
**Estimated Effort:** 6-7 hours
**Dependencies:** Story 14-2, Story 14-3

**Scope Backend:**
- CREATE `NetworkOnboarder` service (~250 lines) in `services/wallet/network_onboarder.py`
- MODIFY `FundingAnalyzer` (add tx_history parameter to avoid duplicate API calls)
- MODIFY `SyncBuyDetector` (add tx_history parameter)
- MODIFY `WalletProfiler` (integrate onboarder call after profiling)
- ADD configuration model for onboarding parameters
- ADD API endpoint for onboarding config

**Scope UI Gradio (See Section 5.3):**
- MODIFY `ui/components/clusters.py` (352 lines)
  - ADD info banner explaining automatic clustering
  - KEEP [Refresh] button as primary
  - ADD [Rebuild All] button (combines all 4 manual steps)
  - MOVE existing 4 buttons to "Advanced Actions" accordion (collapsed by default)
  - ADD Onboarding Config section with:
    - Max Recursion Depth dropdown (default: 1)
    - Min Quick Score slider (default: 0.4)
    - Min Cluster Size dropdown (default: 3)
    - Max Network Size dropdown (default: 20)
    - [Save Onboarding Settings] button

**Acceptance Criteria:**
- Wallet profiling triggers network analysis automatically
- FUNDED_BY relations created from reused tx_history
- BUYS_WITH relations created for recent tokens
- Network discovered from new relations (1-hop)
- Clusters auto-formed when >= 3 members connected
- Leader detected automatically
- Multiplier calculated automatically
- WalletCache updated with cluster_id
- UI shows info banner about automatic clustering
- Manual "Rebuild All" button works as fallback
- Advanced actions collapsed but accessible
- Onboarding config editable from UI
- All safeguards in place (max_depth, max_network_size)

**Notes for DEV:**
- Use `_processed` set to prevent infinite loops
- Reuse tx_history from profiling (no duplicate API calls)
- Log all automatic operations for debugging
- UI changes can be done in parallel with backend if API contract is defined first

---

## Appendix A: Files Affected Summary

### To DELETE (Story 14-1) - Verified Inventory

```
# UI Files (647 LOC)
src/walltrack/ui/pages/exit_simulator.py              # 251 lines
src/walltrack/ui/components/whatif_modal.py           # 396 lines

# Backend Services - services/simulation/ folder (1,053 LOC)
src/walltrack/services/simulation/__init__.py         #  39 lines
src/walltrack/services/simulation/global_analyzer.py  # 520 lines
src/walltrack/services/simulation/position_simulator.py # 180 lines
src/walltrack/services/simulation/strategy_comparator.py # 314 lines

# Backend Services - services/exit/ (775 LOC)
src/walltrack/services/exit/simulation_engine.py      # 533 lines
src/walltrack/services/exit/what_if_calculator.py     # 242 lines

# Test Files (~400 LOC estimated)
tests/unit/services/exit/test_simulation_engine.py
tests/unit/services/exit/test_what_if.py
tests/unit/services/simulation/__init__.py
tests/unit/services/simulation/test_position_simulator.py
tests/unit/services/simulation/test_strategy_comparator.py
tests/unit/services/simulation/test_global_analyzer.py
tests/unit/ui/components/test_whatif_modal.py

# Documentation & Assets
docs/sprint-artifacts/(To review) epic-12-positions-whatif/
.playwright-mcp/e2e_exit_simulator_page.png
.playwright-mcp/e2e_exit_simulator_page.png
.playwright-mcp/tests/e2e/screenshots/e2e_11_exit_simulator.png

# TOTAL: ~2,875 LOC (code + tests)
```

### To MODIFY (All Stories)

```
# Story 14-1 (Exit Removal) - Full Cleanup Checklist

# UI Layer
src/walltrack/ui/dashboard.py                          # Remove Exit Simulator tab
src/walltrack/ui/pages/__init__.py                     # Remove exit_simulator export
src/walltrack/ui/components/__init__.py                # Remove whatif_modal export
src/walltrack/ui/components/position_details_sidebar.py # Remove What-If button + imports
src/walltrack/ui/components/positions_list.py          # Remove Simulate button + handlers

# API Layer (routes/positions.py)
# - Remove imports: from walltrack.services.simulation.global_analyzer import get_global_analyzer
# - Remove imports: from walltrack.services.simulation.strategy_comparator import ...
# - Remove models: SimulationRequest, SimulationRow
# - Remove endpoint: @router.post("/{position_id}/simulate", ...)
src/walltrack/api/routes/positions.py                  # Remove simulation endpoint + imports

# Service Layer (__init__.py cleanup)
# services/exit/__init__.py - Remove these exports:
#   - AggregateStats, ExitSimulationEngine, PricePoint, RuleTrigger
#   - SimulationResult, StrategyComparison
#   - WhatIfAnalysis, WhatIfCalculator, WhatIfScenario
#   - get_simulation_engine, reset_simulation_engine
src/walltrack/services/exit/__init__.py                # Remove 11 simulation exports

# E2E Tests & Docs
tests/e2e/E2E_TEST_STORIES.md                          # Update references

# Story 14-2 (WalletCache Fix) - Backend Only
src/walltrack/services/signal/wallet_cache.py          # Add cluster integration
src/walltrack/models/signal_filter.py                  # Update model if needed

# Story 14-3 (Scoring Simplification) - Backend + UI
src/walltrack/services/scoring/signal_scorer.py        # Rewrite
src/walltrack/services/scoring/threshold_checker.py    # Simplify
src/walltrack/models/scoring.py                        # Simplify structures
src/walltrack/constants/scoring.py                     # Reduce params
src/walltrack/constants/threshold.py                   # Single threshold
src/walltrack/services/config/models.py                # Update config model
src/walltrack/services/signal/pipeline.py              # Use new scoring
src/walltrack/ui/components/config_panel.py            # MAJOR REWRITE (-440 lines)
src/walltrack/ui/components/signals.py                 # Simplify columns
tests/unit/services/scoring/test_signal_scorer.py
tests/unit/services/scoring/test_threshold_checker.py

# Story 14-4 (Network Onboarding) - Backend + UI
src/walltrack/core/cluster/funding_analyzer.py         # Add tx_history param
src/walltrack/core/cluster/sync_detector.py            # Add tx_history param
src/walltrack/services/wallet/profiler.py              # Integrate onboarder
src/walltrack/ui/components/clusters.py                # Add banner, rebuild, config
src/walltrack/api/routes/clusters.py                   # Add onboarding config endpoint
```

### To CREATE (Story 14-4)

```
src/walltrack/services/wallet/network_onboarder.py     # New service (~250 lines)
tests/unit/services/wallet/test_network_onboarder.py   # Tests
```

---

## Appendix B: Configuration Migration

### Before (30+ parameters)

```yaml
scoring:
  wallet_weight: 0.30
  cluster_weight: 0.25
  token_weight: 0.25
  context_weight: 0.20
  wallet_win_rate_weight: 0.35
  wallet_pnl_weight: 0.25
  wallet_timing_weight: 0.25
  wallet_consistency_weight: 0.15
  wallet_leader_bonus: 0.15
  wallet_max_decay_penalty: 0.30
  token_liquidity_weight: 0.30
  token_mcap_weight: 0.25
  token_holder_dist_weight: 0.20
  token_volume_weight: 0.25
  token_min_liquidity_usd: 1000
  token_optimal_liquidity_usd: 50000
  token_min_mcap_usd: 10000
  token_optimal_mcap_usd: 500000
  new_token_penalty_minutes: 5
  max_new_token_penalty: 0.30
  solo_signal_base: 0.50
  peak_trading_hours_utc: [14, 15, 16, 17, 18]
  trade_threshold: 0.70
  high_conviction_threshold: 0.85
  # ... more
```

### After (~8 parameters)

```yaml
scoring:
  trade_threshold: 0.65
  wallet_win_rate_weight: 0.60
  wallet_pnl_weight: 0.40
  leader_bonus: 1.15
  pnl_normalize_min: -100
  pnl_normalize_max: 500

cluster:
  min_boost: 1.0
  max_boost: 1.8

onboarding:
  max_depth: 1
  min_quick_score: 0.4
  min_cluster_size: 3
  max_network_size: 20
  sync_window_seconds: 300
```

---

**Document End**

*This architecture document should be reviewed by the PM before story creation. Any questions or concerns should be raised before implementation begins.*
