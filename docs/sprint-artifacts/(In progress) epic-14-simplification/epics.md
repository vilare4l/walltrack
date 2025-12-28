---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - 'docs/sprint-artifacts/epic-14-simplification/architecture.md'
  - 'docs/prd.md'
  - 'docs/ux-design-specification.md'
project_name: 'WallTrack'
epic_number: 14
epic_title: 'System Simplification & Automation'
user_name: 'Christophe'
date: '2025-12-27'
---

# WallTrack - Epic 14: System Simplification & Automation

## Overview

This document provides the complete epic and story breakdown for Epic 14, which aims to simplify the WallTrack codebase by:

1. **Removing unused features** (Exit Simulation, What-If) - ~2,500 LOC reduction
2. **Simplifying signal scoring** - From ~1,500 LOC to ~400 LOC
3. **Automating wallet network discovery** - Zero manual clustering steps

Based on TEA review findings from Epic 13 (Stories 13-11, 13-12, 13-13).

## Requirements Inventory

### Functional Requirements

**ADR-001: Exit Simulation Removal**
- FR1: Remove Exit Simulator UI page (exit_simulator.py - 251 lines)
- FR2: Remove What-If modal component (whatif_modal.py - 396 lines)
- FR3: Remove Exit Simulator tab from dashboard navigation
- FR4: Remove What-If Analysis button from position_details_sidebar
- FR5: Remove Simulate action button from positions_list
- FR6: Remove simulation services (services/exit/simulation_engine.py, what_if_calculator.py)
- FR7: Remove simulation folder (services/simulation/ - entire folder)
- FR8: Remove simulation API endpoints from routes/positions.py
- FR9: Delete related test files (6 files)
- FR10: Clean up dead imports and exports in __init__.py files

**ADR-002: Scoring Simplification**
- FR11: Simplify SignalScorer to 2-component model (wallet_score + cluster_boost)
- FR12: Change token scoring from weighted factors to binary safe/unsafe check
- FR13: Remove context_score factor entirely (was 2/3 placeholder anyway)
- FR14: Reduce configuration parameters from 30+ to ~8
- FR15: Change from 2 thresholds (0.70, 0.85) to single threshold (0.65)
- FR16: Simplify ScoredSignal model to flat structure
- FR17: Update Config Panel UI - remove Token/Context weight sliders, pie chart
- FR18: Simplify signals table columns (remove T, X columns, show Cluster boost)
- FR19: Add single trade threshold slider (0.65 default)
- FR20: Add wallet score weight config (win_rate 60%, PnL 40%)
- FR21: Add cluster boost range config (1.0x - 1.8x)
- FR22: Add leader bonus config (1.15x)

**ADR-003: Automatic Network Onboarding**
- FR23: Fix WalletCache cluster_id bug (currently always None)
- FR24: Load cluster memberships from Neo4j on cache initialization
- FR25: Add update_cluster_for_members() method to WalletCache
- FR26: Create NetworkOnboarder service (~250 lines)
- FR27: Auto-analyze funding sources after wallet profiling (reuse tx_history)
- FR28: Auto-detect synchronized buying patterns for recent tokens
- FR29: Auto-form clusters when >= 3 qualified wallets connected
- FR30: Auto-detect cluster leaders
- FR31: Auto-calculate cluster multipliers
- FR32: Update Clusters UI with info banner explaining automatic clustering
- FR33: Add "Rebuild All" button (combines all 4 manual steps)
- FR34: Move existing 4 manual buttons to collapsible "Advanced Actions"
- FR35: Add Onboarding Config section (max_depth, min_score, min_size, max_network)

**ADR-004: Cluster Architecture Refinement (Post 14-4 Review)**
- FR36: Create cluster catchup scheduler for orphan wallets
- FR37: Add discovery_source tracking (pump_discovery, cluster_expansion, funding_link, manual)
- FR38: Remove cluster caching from WalletCache (query Neo4j directly)
- FR39: Create ClusterService for direct Neo4j queries
- FR40: Update SignalScorer to use ClusterService instead of cached data

### Non-Functional Requirements

- NFR1: All tests must pass after each story completion
- NFR2: No dead imports remaining (verify with grep)
- NFR3: Application must start without errors
- NFR4: mypy type checks must pass
- NFR5: ruff linting must pass
- NFR6: Validation of new scoring formula against 30 days historical data (Story 14-3)
- NFR7: Safeguards against runaway recursion (max_depth=1, max_network_size=20)
- NFR8: WalletCache memory growth must be monitored
- NFR9: No console errors in Gradio UI

### Additional Requirements from Architecture & UX

**Database Migration:**
- V19__simplify_signals_scores.sql - Add deprecation comments to signals table columns (token_score, context_score)

**UI Patterns (from UX Spec):**
- Respect Gradio Sidebar pattern for drill-down
- Keep Status bar auto-refresh (every=30)
- Maintain click-to-drill pattern on tables
- Use CSS tokens for status colors (--status-healthy, --status-warning, --status-error)

**Config Migration:**
- Export current scoring config before migration
- Provide sensible defaults for new simplified parameters

**Documentation:**
- Delete docs/sprint-artifacts/(To review) epic-12-positions-whatif/ folder
- Update E2E test references

### FR Coverage Map

| Requirement | Story | Status |
|-------------|-------|--------|
| FR1-FR10 (Exit Removal) | 14-1 | Done |
| FR11-FR22 (Scoring) | 14-3 | Done |
| FR23-FR25 (WalletCache Fix) | 14-2 | Done (superseded by 14-5) |
| FR26-FR35 (Network Onboarding) | 14-4 | Done |
| FR36-FR40 (Cluster Refinement) | 14-5 | Pending |
| NFR1-NFR5 (Quality Gates) | All Stories | Ongoing |
| NFR6 (Historical Validation) | 14-3 | Done |
| NFR7-NFR8 (Safeguards) | 14-4 | Done |
| NFR9 (UI Quality) | 14-1, 14-3, 14-4 | Done |

## Epic List

| Epic | Title | Stories | Complexity |
|------|-------|---------|------------|
| 14 | System Simplification & Automation | 5 | High |

**Story Summary:**

| Story | Title | Type | Status | Dependencies |
|-------|-------|------|--------|--------------|
| 14-1 | Exit Simulation Removal | Tech Debt / Cleanup | Done | None |
| 14-2 | WalletCache Cluster Integration | Bug Fix / Critical | Done (superseded) | None |
| 14-3 | Scoring Simplification | Refactoring | Done | 14-2 |
| 14-4 | Automatic Network Onboarding | New Feature | Done | 14-2, 14-3 |
| 14-5 | Cluster Architecture Refinement | Refactoring | Pending | 14-4 |

## Epic 14: System Simplification & Automation

**Epic Goal:** Enable the operator to have a cleaner, more maintainable system with automated clustering, simplified configuration, and accurate signal scoring that actually uses cluster data.

**User Value:**
- ~4,000 LOC removed = less maintenance burden
- 8 config parameters vs 30+ = easier to understand and tune
- 0 manual clustering steps vs 5 = fully automated network discovery
- cluster_id fix = scoring finally uses cluster amplification correctly

**Implementation Order:**

```
Week 1: Cleanup & Foundation
├── 14-1: Exit Simulation Removal (parallel)
└── 14-2: WalletCache Cluster Fix (CRITICAL)

Week 2: Scoring
└── 14-3: Scoring Simplification (depends on 14-2)

Week 3: Automation
└── 14-4: Network Onboarding (depends on 14-2, 14-3)
```

### Story 14-1: Exit Simulation Removal
**Type:** Tech Debt / Cleanup | **Complexity:** Low | **Effort:** 3-4 hours
**FRs covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR7, FR8, FR9, FR10
**Dependencies:** None (can run in parallel with 14-2)

### Story 14-2: WalletCache Cluster Integration
**Type:** Bug Fix / Critical | **Complexity:** Medium | **Effort:** 2-3 hours
**FRs covered:** FR23, FR24, FR25
**Dependencies:** None
**MUST BE DONE BEFORE:** Story 14-3, Story 14-4

### Story 14-3: Scoring Simplification
**Type:** Refactoring | **Complexity:** High | **Effort:** 5-6 hours
**FRs covered:** FR11, FR12, FR13, FR14, FR15, FR16, FR17, FR18, FR19, FR20, FR21, FR22
**Dependencies:** Story 14-2 (WalletCache fix)

### Story 14-4: Automatic Network Onboarding
**Type:** New Feature | **Complexity:** High | **Effort:** 6-7 hours
**FRs covered:** FR26, FR27, FR28, FR29, FR30, FR31, FR32, FR33, FR34, FR35
**Dependencies:** Story 14-2, Story 14-3

### Story 14-5: Cluster Architecture Refinement
**Type:** Refactoring | **Complexity:** Medium | **Effort:** 4-5 hours
**FRs covered:** FR36, FR37, FR38, FR39, FR40
**Dependencies:** Story 14-4

**Key Decisions (from post-14-4 architectural review):**

1. **Scheduler de rattrapage** : Les wallets profilés avant 14-4 n'ont pas de cluster. Un scheduler périodique (toutes les 30 min) traite les wallets orphelins.

2. **Tracking origine découverte** : Nouveau champ `discovery_source` pour savoir d'où vient chaque wallet :
   - `pump_discovery` : Trouvé via token pumped
   - `cluster_expansion` : Trouvé via expansion de cluster
   - `funding_link` : Trouvé comme funder d'un autre wallet
   - `manual` : Ajouté manuellement

3. **Suppression cache cluster** : WalletCache ne cache plus `cluster_id`/`is_leader`. Requête directe Neo4j via nouveau `ClusterService` (~10-20ms acceptable).
