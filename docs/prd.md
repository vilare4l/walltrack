---
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-15'
revised: '2025-12-28'
version: '2.0'
---

# Product Requirements Document - WallTrack

**Author:** Christophe
**Date:** 2025-12-15
**Revised:** 2025-12-28
**Version:** 2.0

## Executive Summary

WallTrack is a personal trading intelligence system designed to systematically exploit on-chain alpha on Solana memecoins. Rather than competing on execution speed with MEV bots, the system focuses on signal quality—identifying and tracking "smart money" wallets whose historical performance demonstrates consistent edge.

The core insight is simple: insiders leave public traces on the blockchain. The edge comes from systematic analysis of these traces, not execution speed. A good signal with 2 seconds of delay beats a bad signal executed instantly.

**Target Operator:** Single user (Christophe) operating the system as a "money printer"—configuring parameters, monitoring performance, and adjusting risk settings. Zero daily trading decisions required.

**Core Value Proposition:** Transform memecoin trading from a game of chance or unsustainable manual labor into a systematic, profitable daily operation.

### What Makes This Special

| Differentiator | Approach |
|----------------|----------|
| **Philosophy** | Signal quality over execution speed |
| **Target Market** | Memecoin-specific on Solana |
| **Architecture** | Owned data + logic; APIs are replaceable pipes |
| **Development** | Incremental validation—each step tested before next |
| **Risk Management** | Moonbag strategy + circuit breakers |
| **Edge** | Cluster detection via Neo4j identifies coordinated insider groups |

**Goal:** Consistent daily profitability (≥1% daily return target), not home runs.

## Project Classification

**Technical Type:** Backend Automation System (api_backend)
**Domain:** Fintech (Crypto Trading)
**Complexity:** High
**Project Context:** Rebuild V2 - Incremental reconstruction with validation at each step

This is a high-complexity fintech project due to the trading domain, but regulatory concerns are minimized as it's a personal system with no external users. Key complexity drivers are security (private key management), risk management (capital protection), and system reliability (24/7 autonomous operation).

## Success Criteria

### User Success

**Primary Success Indicator:** Consistent profitability with zero daily trading decisions.

The system succeeds when the operator (Christophe) can:
- Configure parameters once and let the system run autonomously
- Check performance reports weekly, not daily
- Trust the system to protect capital via circuit breakers
- See consistent positive PnL over time

**Emotional Success:** "It was worth it" = the profit ratio speaks for itself.

### Technical Success

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| System Uptime | ≥ 95% | Must run 24/7 to catch opportunities |
| Execution Latency | < 5 seconds | Signal → trade before price moves |
| Webhook Reliability | > 99% | Can't miss insider movements |
| Daily Signals | 5-20 | Enough opportunities without noise |

### Measurable Outcomes

**Trading Performance Targets:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Win Rate | ≥ 70% | Profitable trades / Total trades |
| Profit Ratio | ≥ 3:1 | Average win / Average loss |
| Daily Return | ≥ 1% | Daily PnL / Starting capital |

**Circuit Breakers (Failure Detection):**

| Trigger | Action |
|---------|--------|
| Drawdown > 20% | Pause all trading, manual review |
| Win rate < 40% over 50 trades | Halt and recalibrate scoring |
| 3 consecutive max-loss trades | Reduce position size by 50% |

**North Star Metric:** Weekly profit generated with zero manual trading intervention.

## Development Phases

### Phase 1 — Discovery & Visualization

Build the intelligence foundation. All discovery and analysis visible in UI.

| Feature | Description | Validation |
|---------|-------------|------------|
| Token Discovery | Manual trigger, list tokens from sources | UI shows tokens |
| Token Surveillance | Scheduled refresh of token data | Scheduler status visible |
| Wallet Discovery | Extract wallets from token transactions | UI shows wallets per token |
| Wallet Profiling | Calculate metrics (win rate, PnL, timing) | Profile visible in UI |
| Wallet Decay Detection | Detect when wallets lose their edge | Decay flags visible in UI |
| Clustering | Neo4j relationships, cluster grouping | Clusters visible in UI |

### Phase 2 — Signal Pipeline (Simulation)

Real-time signal processing with paper positions.

| Feature | Description | Validation |
|---------|-------------|------------|
| Helius Webhooks | Create/manage webhooks for watchlist | Webhook status in UI |
| Signal Scoring | Weighted rules on incoming alerts | Signals logged with scores |
| Position Creation | Positions from high-score signals | Positions visible in UI |

### Phase 3 — Order Management (Simulation)

Complete order lifecycle in simulation mode.

| Feature | Description | Validation |
|---------|-------------|------------|
| Order Entry | Entry orders with risk-based sizing | Orders visible in UI |
| Order Exit | Exit orders per strategy | Exit orders visible |
| Risk Controls | Circuit breakers, position limits | Controls active |

### Phase 4 — Live Micro

Real execution with minimal capital.

| Feature | Description | Validation |
|---------|-------------|------------|
| Jupiter Integration | Real swap execution | Trade confirmed on-chain |
| Capital Protection | Live circuit breakers | Auto-pause on triggers |

**Validation Rule:** Each phase must be fully validated (UI + E2E tests) before advancing to the next.

## Product Scope

### MVP Features (11)

1. **Token Discovery Engine** — Find tokens from successful launches
2. **Token Surveillance** — Scheduled refresh of token data
3. **Wallet Discovery** — Extract wallets from token transactions
4. **Wallet Profiling System** — Performance metrics, behavioral patterns
5. **Wallet Decay Detection** — Detect when wallets lose their edge
6. **Cluster Detection (Neo4j)** — Map wallet relationships, detect insider groups
7. **Helius Webhooks** — Real-time swap notifications
8. **Signal Scoring** — Multi-factor weighted scoring
9. **Position Management** — Create and track positions
10. **Order Entry** — Entry orders with risk-based sizing
11. **Order Exit** — Exit orders per strategy

### Execution Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Simulation** | Full pipeline with orders, no real execution | Development, validation |
| **Live** | Real execution via Jupiter API | Production with capital |

Simulation mode mirrors live behavior exactly—same orders, same sizing, same exit strategies—only the final swap execution is skipped.

### Signal Scoring Model

Weighted rule-based scoring (V2 simplified):

| Factor | Weight | Calculation |
|--------|--------|-------------|
| Wallet Quality | 50% | Historical win rate + PnL + timing_percentile + consistency |
| Token Characteristics | 50% | Liquidity, age, market cap, holder distribution |

**V2 Simplifications:**
- **Cluster Confirmation removed:** FUNDED_BY clustering is organizational (network discovery), not trading coordination. Without SYNCED_BUY detection, cluster-based scoring lacks predictive value.
- **Timing Context merged into Token:** Token age is a token characteristic, not separate context. Market conditions deferred to V2+.

**Signal = 50% Wallet Quality × 50% Token Quality**

**Threshold:** Score ≥ 0.70 → Create position (adjustable)

**Position Sizing Logic:**

| Score Range | Multiplier | Action |
|-------------|------------|--------|
| ≥ 0.85 | 1.5x base | High conviction trade |
| 0.70 - 0.84 | 1.0x base | Standard trade |
| < 0.70 | 0x | No trade (below threshold) |

### Wallet Decay Detection

| Metric | Threshold | Action |
|--------|-----------|--------|
| Rolling 20-trade win rate | < 40% | Flag for review |
| 3 consecutive losses | Same wallet | Temporary score downgrade |
| No activity | 30+ days | Mark as dormant |

### Out of Scope (V2+)

| Feature | Reason | Target |
|---------|--------|--------|
| ML Scoring (XGBoost) | Start simple with rules | V2 |
| Feedback Loop | Requires stable trading first | V2 |
| Backtest Engine | Focus on forward simulation | V2 |
| Behavioral Embeddings | Complexity not justified yet | V2 |
| Position Size in Scoring | V1 calculates & displays only, complexity deferred | V2 |
| Dynamic Exit Strategies | V1 uses fixed moonbag (50%@2x, 25%@3x), adapt per wallet style later | V2 |
| Multi-chain | Solana focus first | V3 |

## User Journey

### Persona: Christophe — The Robot Operator

| Attribute | Description |
|-----------|-------------|
| **Profile** | Technical professional building autonomous trading infrastructure |
| **Role** | System operator, not active trader |
| **Time Investment** | Configuration & monitoring only — zero daily trading decisions |
| **Core Motivation** | "I want a money printer, not a trading assistant." |

### Journey 1: Initial Setup — "Day One"

Christophe opens the Gradio dashboard. The interface displays configuration options: initial capital (2 SOL), risk per trade (2%), scoring threshold (0.70).

He launches token discovery. Within 30 minutes, the system identifies tokens and their associated wallets. He reviews the wallet profiles, sees clusters forming in Neo4j, and activates webhooks for the watchlist.

**Key Moment:** The first signal arrives. Score 0.82. The system creates a position automatically. Christophe observes but doesn't intervene.

### Journey 2: Weekly Monitoring — "Sunday Review"

Sunday evening. Christophe opens the dashboard. The Performance view shows: +8.3% for the week, 23 trades, 74% win rate.

**Key Moment:** No action required. He closes the dashboard after 5 minutes.

### Journey 3: Circuit Breaker Alert — "Red Alert"

Push notification: "Circuit Breaker Triggered - Trading Paused". The dashboard shows: 3 consecutive max-loss trades, position sizing reduced by 50%.

He analyzes: all 3 losses came from the same wallet cluster. He manually blacklists the cluster, resets the circuit breaker, and resumes trading.

**Key Moment:** The system protected capital automatically.

## Technical Architecture

### Architecture Overview

WallTrack is a pure Python autonomous trading system:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API Gateway** | FastAPI | Webhook reception (Helius), health checks |
| **Core Logic** | Python asyncio | Event processing pipeline |
| **Graph Database** | Neo4j | Wallet relationships, cluster detection |
| **Relational DB** | Supabase PostgreSQL | Metrics, trade history, wallet profiles, config |
| **Execution** | Jupiter API | Swap execution on Solana (live mode) |
| **Dashboard** | Gradio | Operator interface |
| **Scheduling** | APScheduler | Periodic tasks (discovery, surveillance) |

### Simplified Structure

```
src/walltrack/
├── api/routes/           # FastAPI endpoints
├── core/                  # BUSINESS LOGIC ONLY
│   ├── discovery/         # Token + Wallet discovery
│   ├── cluster/           # Profiling + Clustering
│   ├── signal/            # Scoring + Filtering
│   ├── position/          # Position management
│   ├── order/             # Entry + Exit unified
│   └── risk/              # Risk management
├── data/
│   ├── models/            # Pydantic models (ONE place)
│   ├── supabase/          # Client + repositories
│   └── neo4j/             # Client + queries
├── services/              # EXTERNAL API CLIENTS ONLY
│   ├── helius/            # Webhooks management
│   ├── jupiter/           # Swap execution
│   ├── dexscreener/       # Token data
│   └── solana/            # RPC client
├── ui/                    # Gradio dashboard
├── config/                # Settings
└── scheduler/             # Periodic tasks
```

**Key Principle:** `services/` = external API clients ONLY. `core/` = business logic ONLY.

### Data Flow

```
**Default Flow (RPC Polling)**:
RPC Polling Worker (10s) → Signal Processing → Neo4j/Supabase Query
                                   ↓
                             Rule-based Scoring
                                   ↓
                          Score ≥ Threshold?
                            ↓           ↓
                          YES          NO
                            ↓           ↓
                     Create Position   Log only
                            ↓
                     Create Orders (Entry)
                            ↓
                     Monitor → Exit Orders
                            ↓
                     Execute (Live mode only)

**Optional Flow (Helius Webhooks)**:
Helius Webhook → FastAPI → Signal Processing → (same as above)
```

### External Integrations

| Service | Purpose | Fallback |
|---------|---------|----------|
| **Solana RPC Public** | Primary: Transaction history, wallet profiling, signal detection (polling) | Multiple providers (Helius RPC, QuickNode, Alchemy) |
| **Helius Enhanced** | Optional: Webhooks for real-time signals (opt-in), fallback if RPC fails | Solana RPC Public |
| **DexScreener** | Token prices, liquidity, market cap | Birdeye |
| **Jupiter** | Swap execution | Raydium direct |

### Security Considerations

| Concern | Approach |
|---------|----------|
| **Private Key Management** | Environment variables, never in code |
| **API Keys** | Secure storage, rotation capability |
| **Webhook Validation** | Signature verification for Helius webhooks |
| **Capital Protection** | Circuit breakers, position limits, automated pause |

## Functional Requirements

### Token Discovery & Surveillance

- FR1: System can discover tokens from configured sources (manual trigger)
- FR2: System can refresh token data on a configurable schedule
- FR3: Operator can view discovered tokens in the dashboard

### Wallet Intelligence

- FR4: System can discover wallets from token transaction history via Solana RPC Public (`getSignaturesForAddress` + `getTransaction` + custom parsing)
- FR5: System can analyze wallet historical performance (win rate, PnL, timing percentile)
- FR6: System can profile wallet behavioral patterns (activity hours, position sizing style)
- FR7: System can detect wallet performance decay using rolling window analysis
- FR8: System can flag wallets for review when performance drops below threshold
- FR9: Operator can manually blacklist specific wallets

### Watchlist Management

- FR10: System can evaluate profiled wallets against configurable criteria
- FR11: System can automatically add wallets to watchlist if criteria met
- FR12: System can mark wallets as 'ignored' if criteria not met
- FR13: System can track wallet status lifecycle (discovered → profiled → watchlisted/ignored → flagged → removed)
- FR14: Operator can configure watchlist criteria (win rate, PnL, trades count, decay threshold)
- FR15: Operator can manually add/remove wallets from watchlist
- FR16: Operator can blacklist wallets (permanent exclusion)

### Cluster Analysis & Network Discovery

- FR17: System can map wallet funding relationships (FUNDED_BY connections)
- FR18: ~~System can detect synchronized buying patterns (SYNCED_BUY within 5 min)~~ **Out of scope V2** - Complexity not justified, FUNDED_BY sufficient
- FR19: ~~System can identify wallets appearing together on multiple early tokens~~ **Out of scope V2** - Deferred to future version
- FR20: System can group related wallets into clusters (watchlist only)
- FR21: System can identify cluster leaders (wallets that initiate movements)
- FR22: ~~System can amplify signal score when multiple cluster wallets move together~~ **Out of scope V2** - Scoring simplified to Wallet Quality (50%) + Token Characteristics (50%)

**Network Discovery (Epic 4):**
- When wallet is watchlisted, system automatically discovers sibling wallets via funding relationships
- Discovered wallets go through full profiling cycle (Stories 3.2-3.3) and watchlist evaluation (Story 3.5)
- Configurable safeguards prevent discovery explosion (max_siblings_per_funder, min_funding_amount, max_network_size)
- Network discovery can be enabled/disabled via configuration

### Signal Processing

- FR23: System can detect swap signals via dual-mode approach:
  - **Default**: RPC Polling (10-second intervals, free tier, no external dependencies)
  - **Optional**: Helius Webhooks (real-time, requires Helius API key, opt-in via Config UI)
- FR24: System can filter notifications to only monitored wallet addresses
- FR25: System can calculate multi-factor signal score (wallet, cluster, token, context)
- FR26: System can apply scoring threshold to determine trade eligibility
- FR27: System can query token characteristics (age, market cap, liquidity)
- FR28: System can log all signals regardless of score for analysis

### Position & Order Management

- FR29: System can create positions from high-score signals
- FR30: System can apply dynamic position sizing based on signal score
- FR31: System can create entry orders with risk-based sizing
- FR32: System can create exit orders per configured strategy
- FR33: System can track all positions and orders with current status
- FR34: System can execute orders in live mode via Jupiter API
- FR35: System can skip execution in simulation mode (paper trading)

### Risk Management

- FR36: System can pause all trading when drawdown exceeds threshold (20%)
- FR37: System can reduce position size after consecutive losses
- FR38: System can enforce maximum concurrent position limits
- FR39: Operator can manually pause and resume trading

### Operator Dashboard

- FR40: Operator can configure risk parameters (capital allocation, position size, thresholds)
- FR41: Operator can view system status (running, paused, health indicators)
- FR42: Operator can view active positions and pending orders
- FR43: Operator can view performance metrics (PnL, win rate, trade count)
- FR44: Operator can view trade history with full details
- FR45: Operator can receive alerts for circuit breakers and system issues
- FR46: Operator can manage watchlist (add/remove wallets manually)
- FR47: Operator can view wallet and cluster analysis details
- FR48: Operator can switch between simulation and live mode

### Trading Wallet Management

- FR49: Operator can connect trading wallet to the system
- FR50: Operator can view trading wallet balance (SOL and tokens)
- FR51: System can validate wallet connectivity before trading

## Non-Functional Requirements

### Performance

| Requirement | Target |
|-------------|--------|
| Signal-to-Trade Latency | < 5 seconds |
| Webhook Processing | < 500ms |
| Dashboard Response | < 2 seconds |
| Database Queries | < 100ms |
| Concurrent Signals | Handle 10+ simultaneous |

### Security

| Requirement | Specification |
|-------------|---------------|
| Private Key Storage | Environment variables only |
| API Key Management | Secure storage with rotation capability |
| Webhook Validation | Signature verification for all Helius webhooks |
| Dashboard Access | Local network only or authenticated |
| Logging | No sensitive data in logs |

### Reliability

| Requirement | Target |
|-------------|--------|
| System Uptime | ≥ 95% |
| Webhook Availability | 24/7 |
| Data Persistence | Zero data loss |
| Error Recovery | Auto-retry failed trades |

### Scalability (Limited Scope)

| Requirement | Target |
|-------------|--------|
| Watchlist Size | Support 1,000+ monitored wallets |
| Trade History | Store 1 year of trade data |
| Signal Log | Store 6 months of all signals |

### Cost Optimization (NFR)

- **Target**: Reduce external API costs from 125K+ req/month (Helius) to 0-75K req/month
- **Strategy**:
  - Use Solana RPC Public (free, 240 req/min) for Epic 3 (discovery, profiling)
  - Use RPC Polling (10s intervals) for Epic 5 signals (default mode)
  - Reserve Helius for opt-in webhooks only (premium feature)
- **Measurement**: Track monthly Helius API usage via Config dashboard

## Risk Mitigation Strategy

| Risk Type | Risk | Mitigation |
|-----------|------|------------|
| **Technical** | Scoring inaccuracy | Fallback to conservative thresholds; continuous monitoring |
| **Market** | Alpha decay | Continuous discovery; decay detection flags stale wallets |
| **Resource** | Solo developer | Simple stack (pure Python); AI-assisted development |
| **Capital** | Drawdown | Circuit breakers (20% max); position limits; automatic pause |

## Future Vision

### V2 — Enhanced Intelligence

- ML-based scoring (XGBoost) with labeled data from simulation
- Feedback loop for automatic wallet score adjustment
- Advanced cluster analysis with network visualization
- Behavioral embeddings for wallet similarity

### V3 — Capital Scaling

- Funding arbitrage integration
- Multi-strategy coordination
- Multi-chain expansion (Base, Arbitrum)
- Potential productization (SaaS)
