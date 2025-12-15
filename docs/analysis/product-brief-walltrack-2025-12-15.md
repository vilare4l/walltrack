---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments:
  - 'wallet-tracking-memecoin-synthese.md'
workflowType: 'product-brief'
lastStep: 5
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-15'
---

# Product Brief: walltrack

**Date:** 2025-12-15
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

### Why Existing Solutions Fall Short

Current wallet tracking tools (Nansen, Arkham, DeBank, Cielo) are:
- Designed for general blockchain analytics, not memecoin-specific alpha generation
- Focused on visualization rather than actionable trading signals
- Not optimized for the speed and chaos of Solana memecoin markets
- Tedious to configure for active trading use cases

### Proposed Solution

WallTrack is a programmatic intelligence layer that:

1. **Discovers** high-performing wallets through historical analysis of successful token launches
2. **Profiles** each wallet with behavioral metrics (win rate, timing patterns, position sizing)
3. **Clusters** related wallets to detect coordinated insider groups
4. **Monitors** watchlist wallets in real-time via Helius webhooks
5. **Scores** each signal based on wallet quality, cluster confirmation, and token characteristics
6. **Executes** (paper first, then live) only on high-conviction signals

The system learns continuously: every trade outcome feeds back into wallet scoring and signal calibration.

### Key Differentiators

| Aspect | WallTrack Approach |
|--------|-------------------|
| **Philosophy** | Signal quality > execution speed |
| **Target** | Memecoin-specific on Solana |
| **Architecture** | Owned data + logic, APIs are replaceable pipes |
| **Learning** | Continuous feedback loop improves scoring |
| **Goal** | Consistent daily profitability, not home runs |

---

## Target Users

### Primary User

**Persona: Christophe — The Robot Operator**

| Attribute | Description |
|-----------|-------------|
| **Profile** | Technical professional building autonomous trading infrastructure |
| **Role** | System operator, not active trader |
| **Time investment** | Configuration & monitoring only — zero daily trading decisions |
| **Memecoin experience** | Intentionally distant — delegates to the system |
| **Technical comfort** | Builds with AI assistance, comfortable with complex systems |

**Core Motivation:**
"I want a money printer, not a trading assistant. Set parameters, let it run, collect profits."

**Operator Responsibilities:**
- Set capital allocation (total bankroll)
- Define risk parameters (% per trade, max concurrent positions)
- Configure scoring thresholds (minimum signal quality to execute)
- Monitor system health and performance metrics
- Adjust parameters based on results

**What Christophe Does NOT Do:**
- Review individual signals before execution
- Make trade-by-trade decisions
- Watch charts or monitor positions actively
- Manually enter or exit trades

**Success Vision:**
- System runs 24/7 fully autonomous
- Daily/weekly performance reports arrive automatically
- Adjusts risk parameters monthly based on results
- Consistent profits with zero active trading time

### Secondary Users

N/A — Personal autonomous trading system. No other users.

### User Journey

| Phase | Experience |
|-------|------------|
| **Initial setup** | Configure APIs, set capital allocation, define risk rules |
| **Parameter tuning** | Adjust scoring thresholds, position sizing, stop-loss rules |
| **Autonomous operation** | System discovers, scores, executes, manages positions 24/7 |
| **Passive monitoring** | Check dashboard/reports periodically (daily/weekly) |
| **Optimization** | Review performance, tweak parameters, let it run again |
| **Success moment** | Monthly review shows consistent profits with zero trading time |

---

## Success Metrics

### Trading Performance (Primary)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Win Rate** | ≥ 70% | Profitable trades / Total trades |
| **Profit Ratio** | ≥ 3:1 | Average win size / Average loss size |
| **Daily Return** | ≥ 1% | Daily PnL / Starting capital |
| **Sharpe Ratio** | > 2.0 | Risk-adjusted return measure |

### System Health

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Daily Signals** | 10-20 | High-score signals generated per day |
| **System Uptime** | ≥ 95% | Time system is operational and monitoring |
| **Execution Latency** | < 5 seconds | Signal detection → trade execution |
| **Webhook Reliability** | > 99% | Helius events received / Expected events |

### MVP Validation Criteria

| Phase | Duration | Success Threshold |
|-------|----------|-------------------|
| **Paper Trading** | 15 days | Any positive PnL |
| **Micro Live** | 30 days | Positive PnL with < 10% drawdown |
| **Scale Up** | Ongoing | Consistent 1%+ daily with risk controls |

### Circuit Breakers (Failure Detection)

| Trigger | Action |
|---------|--------|
| Drawdown > 20% of capital | Pause all trading, manual review required |
| Win rate < 40% over 50 trades | Halt and recalibrate scoring model |
| No signals for 48 hours | System health check, verify integrations |
| 3 consecutive max-loss trades | Reduce position size by 50%, analyze pattern |

### Business Objectives

N/A — Personal project. Success = consistent autonomous profits.

### Key Performance Indicators

**North Star Metric:** Weekly profit generated with zero manual trading intervention.

**Leading Indicators:**
- Wallet discovery rate (new high-quality wallets found per week)
- Signal quality trend (average score of executed trades)
- Cluster detection accuracy (confirmed insider groups identified)

**Lagging Indicators:**
- Cumulative PnL
- Maximum drawdown experienced
- Capital growth rate

---

## MVP Scope

### Core Features

**1. Wallet Discovery Engine**
- Automatic identification of high-performing wallets from successful token launches
- Analysis of Pump.fun early buyers on tokens that achieved 10x+
- Filtering by performance criteria: win rate > 50%, 20+ trades minimum, consistent sizing

**2. Wallet Profiling System**
- Performance metrics: win rate, PnL, timing percentile, hold duration
- Behavioral patterns: hours of activity, position sizing style, token preferences
- Continuous profile updates as new trades occur

**3. Cluster Detection (Neo4j)**
- Relationship mapping: FUNDED_BY, SYNCED_BUY, SAME_EARLY_TOKENS
- Coordinated group identification
- Leader detection within clusters
- Signal amplification when multiple cluster wallets move

**4. Real-Time Monitoring**
- Helius webhook integration for instant swap notifications
- Dynamic watchlist management (add/remove wallets via API)
- n8n orchestration for event processing pipeline

**5. ML-Based Signal Scoring**
- Multi-factor scoring: wallet quality (30%), cluster confirmation (25%), token characteristics (25%), context (20%)
- XGBoost classification: smart money vs retail vs bot vs scammer
- Automatic threshold calibration based on results

**6. Autonomous Execution**
- Live trading via Jupiter API
- Position sizing based on signal score and risk parameters
- Automatic stop-loss and take-profit management
- Moonbag strategy: 50% exit at 2-3x, 50% rides

**7. Feedback Loop**
- Trade outcome tracking and analysis
- Automatic wallet score adjustment based on results
- Scoring model weight recalibration

**8. Data Infrastructure**
- Neo4j: wallet relationships, clusters, graph queries
- Supabase PostgreSQL: metrics, trade history, results
- Supabase Vectors: behavioral embeddings, similarity search

**9. External Integrations**
- Helius: webhooks for real-time swap events
- DexScreener: token prices, liquidity, market cap
- Jupiter: swap execution

### Out of Scope for MVP

| Feature | Reason | Target Version |
|---------|--------|----------------|
| Social sentiment (Twitter, Telegram) | On-chain signal sufficient | v2 |
| KOL mapping | Distribution phase, not accumulation | v2 |
| Funding arbitrage | Requires more capital | v3 |
| Pair trading | Advanced strategy | v3 |
| Ultra-fast sniping | Not our edge | Never |
| Paid APIs | Independence principle | Never |
| Dashboard/UI | CLI/logs sufficient for solo operator | v2 |
| Multi-chain support | Solana focus first | v3 |

### MVP Success Criteria

| Criteria | Threshold | Validation Method |
|----------|-----------|-------------------|
| System operational | 95% uptime over 15 days | Monitoring logs |
| Signals generated | 10+ high-score signals per day | Signal log count |
| Execution working | Trades execute within 5 seconds | Latency metrics |
| Positive PnL | Any profit over 15-day period | Portfolio tracking |
| Win rate | ≥ 70% on executed trades | Trade outcome analysis |

**Go/No-Go Decision:** After 15 days, if positive PnL achieved → scale up capital. If not → analyze and iterate.

### Future Vision

**v2 — Enhanced Intelligence**
- Gradio dashboard for monitoring and parameter adjustment
- Advanced cluster analysis with network visualization
- Wallet reputation decay detection (alpha erosion monitoring)
- Dynamic position sizing based on conviction level

**v3 — Capital Scaling**
- Funding arbitrage integration
- Pair trading strategies
- Multi-strategy coordination
- Infrastructure scaling for higher throughput

**Long-term Vision**
- Self-improving autonomous trading system
- Potential productization for other operators (SaaS model)
- Multi-chain expansion (Base, Arbitrum memecoins)

