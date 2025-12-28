---
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-28'
revised: '2025-12-28'
---

# Product Brief: WallTrack

**Date:** 2025-12-28
**Revised:** 2025-12-28
**Author:** Christophe

---

## Executive Summary

WallTrack is a personal trading intelligence system designed to systematically exploit on-chain alpha on Solana memecoins. Rather than competing on execution speed with MEV bots, the system focuses on signal quality—identifying and tracking "smart money" wallets whose historical performance demonstrates consistent edge.

The goal is simple: transform a game of chance or manual labor into a systematic, profitable daily operation.

---

## Core Vision

### Problem Statement

Trading memecoins profitably is fundamentally an insider's game. The information asymmetry is stark:

| Timing | Actor | Information Edge |
|--------|-------|------------------|
| T+0ms | Insiders, Devs, MEV Bots | First movers, privileged access |
| T+5min | Early followers | Fast but reactive |
| T+30min | KOL tweets | Distribution phase begins |
| T+1h | Retail FOMO | Exit liquidity |

For the average trader, there are only two paths: **luck** (random bets hoping to catch a pump) or **labor** (manually tracking hundreds of wallets, an unsustainable effort).

### Problem Impact

- Retail traders consistently lose money chasing pumps after the smart money has already positioned
- Manual wallet tracking is time-intensive and error-prone
- Without systematic analysis, distinguishing skilled wallets from lucky ones is impossible
- The information exists publicly on-chain, but extracting actionable signals requires significant effort

### Proposed Solution

WallTrack is a programmatic intelligence layer that:

1. **Discovers** high-performing wallets through historical analysis of successful token launches
2. **Profiles** each wallet with behavioral metrics (win rate, timing patterns, position sizing)
3. **Clusters** related wallets to detect coordinated insider groups
4. **Monitors** watchlist wallets in real-time via Helius webhooks
5. **Scores** each signal based on wallet quality, cluster confirmation, and token characteristics
6. **Executes** (simulation first, then live) only on high-conviction signals

### Key Differentiators

| Aspect | WallTrack Approach |
|--------|-------------------|
| **Philosophy** | Signal quality > execution speed |
| **Target** | Memecoin-specific on Solana |
| **Architecture** | Owned data + logic, APIs are replaceable pipes |
| **Development** | Incremental validation - each step tested before next |
| **Goal** | Consistent daily profitability, not home runs |

---

## Target User

### Primary User

**Persona: Christophe — The Robot Operator**

| Attribute | Description |
|-----------|-------------|
| **Profile** | Technical professional building autonomous trading infrastructure |
| **Role** | System operator, not active trader |
| **Time investment** | Configuration & monitoring only — zero daily trading decisions |
| **Technical comfort** | Builds with AI assistance, comfortable with complex systems |

**Core Motivation:**
"I want a money printer, not a trading assistant. Set parameters, let it run, collect profits."

**Operator Responsibilities:**
- Set capital allocation (total bankroll)
- Define risk parameters (% per trade, max concurrent positions)
- Configure scoring thresholds (minimum signal quality to execute)
- Monitor system health and performance metrics
- Adjust parameters based on results

**Success Vision:**
- System runs 24/7 fully autonomous
- Daily/weekly performance reports via dashboard
- Consistent profits with zero active trading time

---

## Development Phases

| Phase | Name | Goal |
|-------|------|------|
| **Phase 1** | Discovery & Visualization | Tokens + Wallets + Clusters visible in UI |
| **Phase 2** | Signal Pipeline | Webhooks → Scoring → Positions (simulation) |
| **Phase 3** | Order Management | Entry/Exit orders (simulation mode) |
| **Phase 4** | Live Micro | Real execution with minimal capital |

---

## MVP Scope

### Core Features

| # | Feature | Description | Validation |
|---|---------|-------------|------------|
| 1 | **Token Discovery** | Manual trigger, list tokens from sources | UI shows tokens |
| 2 | **Token Surveillance** | Scheduled refresh of token data | Scheduler status visible |
| 3 | **Wallet Discovery** | Extract wallets from token transactions | UI shows wallets per token |
| 4 | **Wallet Profiling** | Calculate metrics (win rate, PnL, timing) | Profile visible in UI |
| 5 | **Wallet Decay Detection** | Detect when wallets lose their edge (rolling window) | Decay flags visible in UI |
| 6 | **Clustering** | Neo4j relationships, cluster grouping | Clusters visible in UI |
| 7 | **Helius Webhooks** | Create/manage webhooks for watchlist | Webhook status in UI |
| 8 | **Signal Scoring** | Weighted rules on incoming alerts | Signals logged with scores |
| 9 | **Position Creation** | Positions from high-score signals | Positions visible in UI |
| 10 | **Order Entry** | Entry orders with risk-based sizing | Orders visible in UI |
| 11 | **Order Exit** | Exit orders per strategy | Exit orders visible |

### Signal Scoring Model

Weighted rule-based scoring:

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Wallet Quality | 35% | Historical win rate + PnL + consistency |
| Cluster Confirmation | 25% | Number of cluster wallets on same token |
| Token Characteristics | 25% | Liquidity, age, holder distribution |
| Timing Context | 15% | Time since token creation, market conditions |

**Threshold:** Score ≥ 0.70 → Create position (adjustable in settings)

### Wallet Decay Detection

Wallets can lose their edge over time. Detection logic:

| Metric | Threshold | Action |
|--------|-----------|--------|
| Rolling 20-trade win rate | < 40% | Flag for review |
| 3 consecutive losses | Same wallet | Temporary score downgrade |
| No activity | 30+ days | Mark as dormant |

### Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Simulation** | Full pipeline with orders, no real execution | Development, validation |
| **Live** | Real execution via Jupiter API | Production with capital |

Simulation mode mirrors live behavior exactly—same orders, same sizing, same exit strategies—only the final swap execution is skipped.

### Out of Scope

| Feature | Reason | Target |
|---------|--------|--------|
| ML Scoring (XGBoost) | Start simple with rules | v2 |
| Feedback Loop | Requires stable trading first | v2 |
| Backtest Engine | Focus on forward simulation | v2 |
| Social Sentiment | On-chain signal sufficient | v2 |
| Multi-chain | Solana focus first | v3 |

---

## Technical Stack

| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Runtime |
| FastAPI | API framework |
| Gradio | Dashboard UI |
| Supabase | PostgreSQL database, configuration |
| Neo4j | Graph database for clusters/relationships |
| httpx | Async HTTP client |
| Pydantic v2 | Data validation |

### External Integrations

| Service | Purpose |
|---------|---------|
| Helius | Webhooks for real-time swap events |
| DexScreener | Token prices, liquidity, market cap |
| Jupiter | Swap execution (live mode) |

---

## Success Metrics

### Trading Performance (Target)

| Metric | Target |
|--------|--------|
| **Win Rate** | ≥ 70% |
| **Profit Ratio** | ≥ 3:1 |
| **Daily Return** | ≥ 1% |

### MVP Validation Criteria

| Criteria | Threshold |
|----------|-----------|
| All 11 features working | E2E tests pass |
| UI fully functional | All tabs operational |
| Simulation mode stable | 7 days no crashes |
| Signals generated | 5+ per day |

### Circuit Breakers

| Trigger | Action |
|---------|--------|
| Drawdown > 20% | Pause trading, manual review |
| Win rate < 40% over 50 trades | Halt and recalibrate |
| No signals for 48 hours | System health check |
| 3 consecutive max-loss | Reduce position size 50% |

---

## Development Principles

1. **Validate before advancing** — Each feature must have working UI + passing E2E test
2. **Simplicity over sophistication** — Weighted rules before ML, simulation before live
3. **One place per responsibility** — No duplicate modules
4. **UI is not optional** — If you can't see it, you can't validate it
5. **Incremental complexity** — Start simple, add complexity only when needed

---

## Future Vision

**v2 — Enhanced Intelligence**
- ML-based scoring (XGBoost) with labeled data from simulation
- Feedback loop for automatic wallet score adjustment
- Advanced cluster analysis with network visualization
- Behavioral embeddings for wallet similarity

**v3 — Capital Scaling**
- Funding arbitrage integration
- Multi-strategy coordination
- Multi-chain expansion (Base, Arbitrum)

---

## References

- Architecture: `docs/architecture.md`
- Rebuild notes: `docs/rebuild-v2-notes.md`
- Legacy code: `legacy/src/` (reference only)
