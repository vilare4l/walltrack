---
stepsCompleted: [1, 2, 3, 4, 7, 8, 9, 10, 11]
inputDocuments:
  - 'docs/analysis/product-brief-walltrack-2025-12-15.md'
  - 'wallet-tracking-memecoin-synthese.md'
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 0
  projectDocs: 0
workflowType: 'prd'
lastStep: 11
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-15'
---

# Product Requirements Document - walltrack

**Author:** Christophe
**Date:** 2025-12-15

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
| **Intelligence** | Continuous feedback loop improves wallet scoring |
| **Risk Management** | Moonbag strategy (50% secure at 2-3x, 50% rides) + circuit breakers |
| **Edge** | Cluster detection via Neo4j identifies coordinated insider groups |

**Goal:** Consistent daily profitability (≥1% daily return target), not home runs.

## Project Classification

**Technical Type:** Backend Automation System (api_backend)
**Domain:** Fintech (Crypto Trading)
**Complexity:** High
**Project Context:** Greenfield - new project

This is a high-complexity fintech project due to the trading domain, but regulatory concerns are minimized as it's a personal system with no external users. Key complexity drivers are security (private key management), risk management (capital protection), and system reliability (24/7 autonomous operation).

## Success Criteria

### User Success

**Primary Success Indicator:** Consistent profitability with zero daily trading decisions.

The system succeeds when the operator (Christophe) can:
- Configure parameters once and let the system run autonomously
- Check performance reports weekly, not daily
- Trust the system to protect capital via circuit breakers
- See consistent positive PnL over time

**Emotional Success:** "It was worth it" = the profit ratio speaks for itself. No need for active monitoring. Money in the account is the only metric that matters.

### Business Success

This is a personal autonomous trading system. Business success equals user success:
- Capital grows over time
- System pays for its own infrastructure costs (minimal)
- ROI justifies the development investment

No external users, no revenue targets, no growth metrics. Pure profit generation.

### Technical Success

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| System Uptime | ≥ 95% | Must run 24/7 to catch opportunities |
| Execution Latency | < 5 seconds | Signal → trade before price moves |
| Webhook Reliability | > 99% | Can't miss insider movements |
| Daily Signals | 10-20 | Enough opportunities without noise |

### Measurable Outcomes

**Trading Performance Targets:**

| Metric | Target | Measurement |
|--------|--------|-------------|
| Win Rate | ≥ 70% | Profitable trades / Total trades |
| Profit Ratio | ≥ 3:1 | Average win / Average loss |
| Daily Return | ≥ 1% | Daily PnL / Starting capital |
| Sharpe Ratio | > 2.0 | Risk-adjusted return |

**Circuit Breakers (Failure Detection):**

| Trigger | Action |
|---------|--------|
| Drawdown > 20% | Pause all trading, manual review |
| Win rate < 40% over 50 trades | Halt and recalibrate scoring |
| No signals for 48 hours | System health check |
| 3 consecutive max-loss trades | Reduce position size by 50% |

**North Star Metric:** Weekly profit generated with zero manual trading intervention.

## Product Scope

### V1 (MVP) - Autonomous Trading System

A complete, functional trading system with operator dashboard that generates real profits from day one.

**Core Capabilities:**
1. **Wallet Discovery Engine** - Identify high-performing wallets from successful token launches
2. **Wallet Profiling System** - Performance metrics, behavioral patterns, continuous updates
3. **Cluster Detection (Neo4j)** - Map wallet relationships, detect coordinated insider groups
4. **Real-Time Monitoring** - Helius webhooks for instant swap notifications
5. **ML Signal Scoring** - Multi-factor scoring (wallet 30%, cluster 25%, token 25%, context 20%)
6. **Live Execution** - Jupiter API integration with real trades
7. **Position Management** - Stop-loss, take-profit, moonbag strategy (50% secure, 50% rides)
8. **Feedback Loop** - Trade outcomes improve wallet scores automatically
9. **Circuit Breakers** - Automatic capital protection (drawdown limits, win rate monitoring)
10. **Gradio Dashboard** - Operator interface for config, monitoring, and control

**Operator Dashboard (Gradio):**
- **Config Panel:** Risk parameters, scoring thresholds, capital allocation
- **Live Status:** System health, active positions, pending signals
- **Performance View:** PnL charts, win rate, trade history
- **Alerts:** Circuit breaker notifications, webhook failures
- **Controls:** Pause/resume, manual watchlist management

**Tech Stack:**
- Neo4j: Wallet relationships and cluster graphs
- Supabase PostgreSQL: Metrics, trade history, results
- Supabase Vectors: Behavioral embeddings, similarity search
- n8n: Workflow orchestration
- Python: Core logic, scoring, execution
- Gradio: Operator dashboard
- Helius/DexScreener/Jupiter: External APIs (replaceable)

**Validation:** Positive PnL over 30 days with <10% drawdown = success.

### V2 - Enhanced Intelligence

- Advanced cluster analysis with network visualization
- Wallet reputation decay detection
- Dynamic position sizing based on conviction level
- Scoring model optimization with more sophisticated ML
- Dashboard enhancements and mobile notifications

### V3 - Capital Scaling

- Funding arbitrage integration
- Pair trading strategies
- Multi-strategy coordination
- Infrastructure scaling for higher throughput
- Potential productization (SaaS for other operators)

## User Journeys

### Persona: Christophe — The Robot Operator

| Attribute | Description |
|-----------|-------------|
| **Profile** | Technical professional building autonomous trading infrastructure |
| **Role** | System operator, not active trader |
| **Time Investment** | Configuration & monitoring only — zero daily trading decisions |
| **Technical Comfort** | Builds with AI assistance, comfortable with complex systems |
| **Core Motivation** | "I want a money printer, not a trading assistant." |

### Journey 1: Initial Setup — "Day One"

Christophe has just finished developing WallTrack. He opens the Gradio dashboard for the first time. The interface displays a configuration wizard: initial capital (2 SOL), risk per trade (2%), scoring threshold (0.70), circuit breakers (20% max drawdown).

He connects his Solana wallet, verifies that Helius is receiving webhooks correctly, and launches wallet discovery. Within 30 minutes, the system identifies 150 high-performing wallets from recent successful launches. He quickly reviews the top 20, adjusts some clustering parameters, and activates live mode.

**Key Moment:** The first signal arrives. Score 0.82. The system automatically executes: 0.1 SOL on a detected token. Christophe observes but doesn't intervene. The trade closes at +40% two hours later. The robot works.

**Capabilities Required:** Config wizard, wallet connection, discovery launch, parameter setting, first trade execution.

### Journey 2: Weekly Monitoring — "Sunday Review"

Sunday evening. Christophe opens the dashboard for his weekly check. The Performance view shows: +8.3% for the week, 23 trades, 74% win rate. Everything is within targets.

He scrolls through recent trades. A pattern emerges: night signals (3h-6h UTC) have an 85% win rate vs 65% during the day. He mentally notes to investigate further. The system runs, profits accumulate.

**Key Moment:** No action required. He closes the dashboard after 5 minutes. This is exactly what he wanted.

**Capabilities Required:** Performance dashboard, trade history, metrics visualization, pattern visibility.

### Journey 3: Circuit Breaker Alert — "Red Alert"

Tuesday 2pm. Push notification: "Circuit Breaker Triggered - Trading Paused". Christophe opens the dashboard. The Alerts view shows: 3 consecutive max-loss trades, position sizing automatically reduced by 50%.

He analyzes: all 3 losses came from the same wallet cluster. He drills down — this cluster has been compromised (wallets sold or behavior changed). The feedback loop hasn't adjusted the scores yet.

**Actions:** He manually blacklists the cluster, resets the circuit breaker, and resumes trading with reduced parameters. The system will learn from this incident.

**Key Moment:** The system protected capital automatically. Human intervention corrects what ML hasn't learned yet.

**Capabilities Required:** Push notifications, circuit breaker status, drill-down analysis, manual overrides, blacklist management.

### Journey 4: Monthly Optimization — "Fine Tuning"

End of month. Christophe opens the Performance view for a deep review. 30 days: +31% PnL, 89 trades, 71% win rate. Objectives met.

He analyzes patterns: signals with cluster confirmation (2+ wallets from same group) have 82% win rate vs 61% without. He adjusts scoring weights: cluster goes from 25% to 35%, token characteristics drops from 25% to 15%.

He runs a quick backtest on the month's data. The new scoring would have yielded +38% instead of +31%. He applies the changes.

**Key Moment:** The system improves through human intervention + automatic feedback loop. Operator-robot symbiosis.

**Capabilities Required:** Advanced analytics, pattern detection, parameter tuning, backtest preview, weight adjustment.

### Journey Requirements Summary

| Journey | Primary Capabilities |
|---------|---------------------|
| Initial Setup | Config wizard, wallet connection, discovery engine, parameter configuration |
| Weekly Monitoring | Performance dashboard, trade history, metrics visualization |
| Alert Handling | Push notifications, circuit breaker management, manual overrides, blacklist |
| Monthly Optimization | Advanced analytics, pattern detection, backtest, parameter tuning |

## Technical Architecture

### Architecture Overview

WallTrack is a pure Python autonomous trading system with the following components:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **API Gateway** | FastAPI | Webhook reception (Helius), health checks |
| **Orchestration** | Python asyncio | Event processing pipeline |
| **Graph Database** | Neo4j | Wallet relationships, cluster detection |
| **Relational DB** | Supabase PostgreSQL | Metrics, trade history, wallet profiles |
| **Vector Store** | Supabase Vectors | Behavioral embeddings, similarity search |
| **ML Engine** | XGBoost / scikit-learn | Wallet classification, signal scoring |
| **Execution** | Jupiter API | Swap execution on Solana |
| **Dashboard** | Gradio | Operator interface |
| **Scheduling** | APScheduler | Periodic tasks (discovery, cleanup) |

### Data Flow

```
Helius Webhook → FastAPI → Signal Processing → Neo4j/Supabase Query
                                    ↓
                              ML Scoring
                                    ↓
                         Score > Threshold?
                           ↓           ↓
                         YES          NO
                           ↓           ↓
                    Jupiter Swap    Log only
                           ↓
                    Supabase (save result)
                           ↓
                    Feedback Loop (update wallet scores)
```

### External Integrations

| Service | Purpose | Fallback |
|---------|---------|----------|
| **Helius** | Real-time swap webhooks | RPC polling + manual parsing |
| **DexScreener** | Token prices, liquidity, market cap | Birdeye, on-chain direct |
| **Jupiter** | Swap execution | Raydium direct |
| **Solana RPC** | Blockchain queries | Multiple public providers |

### Key Technical Decisions

1. **Pure Python Stack** — No n8n orchestration. Simpler to debug, deploy, and maintain.
2. **FastAPI for Webhooks** — Async, high-performance, native Python.
3. **Dual Database Strategy** — Neo4j for graph relationships, Supabase for metrics/history.
4. **API Independence** — All external APIs have identified fallbacks. Data and logic remain owned.

### Security Considerations

| Concern | Approach |
|---------|----------|
| **Private Key Management** | Environment variables, never in code |
| **API Keys** | Secure storage, rotation capability |
| **Webhook Validation** | Signature verification for Helius webhooks |
| **Capital Protection** | Circuit breakers, position limits, automated pause |

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Problem-Solving MVP — A complete, functional trading system that solves the core problem (alpha extraction from smart money signals) from day one.

**Resource Requirements:** Solo developer with AI assistance. Pure Python stack minimizes complexity.

### V1 (MVP) Feature Set — Revised

**Core Capabilities (12):**

1. **Wallet Discovery Engine** — Find high-performing wallets from successful launches
2. **Wallet Profiling System** — Performance metrics, behavioral patterns
3. **Cluster Detection (Neo4j)** — Map wallet relationships, detect insider groups
4. **Real-Time Monitoring** — Helius webhooks for instant notifications
5. **ML Signal Scoring** — Multi-factor scoring (wallet, cluster, token, context)
6. **Live Execution** — Jupiter API with real trades
7. **Position Management** — Stop-loss, take-profit, moonbag strategy
8. **Feedback Loop** — Trade outcomes improve wallet scores
9. **Circuit Breakers** — Automatic capital protection
10. **Gradio Dashboard** — Operator interface (config, monitoring, alerts)
11. **Wallet Decay Detection** — Detect when wallets lose their edge
12. **Dynamic Position Sizing** — Size based on conviction level

**Position Sizing Logic:**

| Score Range | Multiplier | Action |
|-------------|------------|--------|
| ≥ 0.85 | 1.5x base | High conviction trade |
| 0.70 - 0.84 | 1.0x base | Standard trade |
| < 0.70 | 0x | No trade (below threshold) |

**Decay Detection Logic:**
- Rolling 20-trade window per wallet
- Win rate drops below 40% → Flag for review
- 3 consecutive losses from same wallet → Temporary score downgrade

### V2 — Enhanced Intelligence

- Advanced cluster visualization (network graphs in dashboard)
- ML scoring optimization (hyperparameter tuning, model improvements)
- Mobile push notifications
- Dashboard enhancements and UX improvements
- **Wallet rotation anti-detection strategy** (multi-wallet support, randomized delays, cooling periods)

### V3 — Capital Scaling

- Funding arbitrage integration
- Pair trading strategies
- Multi-strategy coordination
- Infrastructure scaling for higher throughput
- Potential productization (SaaS for other operators)

### Risk Mitigation Strategy

| Risk Type | Risk | Mitigation |
|-----------|------|------------|
| **Technical** | ML scoring inaccuracy | Fallback to rules-based scoring; continuous feedback loop |
| **Market** | Alpha decay (wallets get spotted) | Continuous discovery; decay detection flags stale wallets |
| **Resource** | Solo developer | Simple stack (pure Python); AI-assisted development |
| **Capital** | Drawdown | Circuit breakers (20% max); position limits; automatic pause |

## Functional Requirements

### Wallet Intelligence

- FR1: System can discover high-performing wallets from successful token launches automatically
- FR2: System can analyze wallet historical performance (win rate, PnL, timing percentile)
- FR3: System can profile wallet behavioral patterns (activity hours, position sizing style, token preferences)
- FR4: System can detect wallet performance decay using rolling window analysis
- FR5: System can flag wallets for review when performance drops below threshold
- FR6: Operator can manually blacklist specific wallets

### Cluster Analysis

- FR7: System can map wallet funding relationships (FUNDED_BY connections)
- FR8: System can detect synchronized buying patterns (SYNCED_BUY within 5 min)
- FR9: System can identify wallets appearing together on multiple early tokens
- FR10: System can group related wallets into clusters
- FR11: System can identify cluster leaders (wallets that initiate movements)
- FR12: System can amplify signal score when multiple cluster wallets move together

### Signal Processing

- FR13: System can receive real-time swap notifications via Helius webhooks
- FR14: System can filter notifications to only monitored wallet addresses
- FR15: System can calculate multi-factor signal score (wallet, cluster, token, context)
- FR16: System can apply scoring threshold to determine trade eligibility
- FR17: System can query token characteristics (age, market cap, liquidity, holder distribution)
- FR18: System can log all signals regardless of score for analysis

### Trade Execution

- FR19: System can execute swap trades via Jupiter API
- FR20: System can apply dynamic position sizing based on signal score
- FR21: System can set and monitor stop-loss levels per position
- FR22: System can set and monitor take-profit levels per position
- FR23: System can execute configurable exit strategies with multiple take-profit levels
- FR24: System can track all open positions and their current status
- FR25: System can execute trailing stop on active positions
- FR26: System can apply time-based exit rules (max hold duration, stagnation detection)
- FR27: System can assign exit strategy based on signal score or operator override

### Risk Management

- FR28: System can pause all trading when drawdown exceeds threshold (20%)
- FR29: System can reduce position size after consecutive losses
- FR30: System can halt trading when win rate falls below threshold over N trades
- FR31: System can alert operator when circuit breaker triggers
- FR32: Operator can manually pause and resume trading
- FR33: System can enforce maximum concurrent position limits

### System Feedback

- FR34: System can record trade outcomes (entry price, exit price, PnL, duration)
- FR35: System can update wallet scores based on trade outcomes
- FR36: System can recalibrate scoring model weights based on results
- FR37: System can track signal accuracy over time
- FR38: System can identify patterns in successful vs unsuccessful trades

### Operator Dashboard

- FR39: Operator can configure risk parameters (capital allocation, position size, thresholds)
- FR40: Operator can view system status (running, paused, health indicators)
- FR41: Operator can view active positions and pending signals
- FR42: Operator can view performance metrics (PnL, win rate, trade count)
- FR43: Operator can view trade history with full details
- FR44: Operator can receive alerts for circuit breakers and system issues
- FR45: Operator can adjust scoring weights and thresholds
- FR46: Operator can manage watchlist (add/remove wallets manually)
- FR47: Operator can run backtest preview on parameter changes
- FR48: Operator can view wallet and cluster analysis details
- FR49: Operator can define custom exit strategies with configurable parameters
- FR50: Operator can assign default exit strategy and score-based overrides
- FR51: Operator can view and modify exit strategy for active positions

### Trading Wallet Management

- FR52: Operator can connect trading wallet to the system
- FR53: Operator can view trading wallet balance (SOL and tokens)
- FR54: System can validate wallet connectivity before trading

### Live Simulation (Paper Trading)

- FR55: System can run in simulation mode without executing real trades
- FR56: System can simulate trade execution with realistic pricing and slippage
- FR57: System can track simulated positions separately from live positions
- FR58: System can calculate real-time P&L for simulated positions using market prices
- FR59: Operator can view simulation dashboard with dedicated views
- FR60: System can log and alert for simulation activity separately

### Backtesting & Scenario Analysis

- FR61: System can collect and store historical signal and price data for backtesting
- FR62: System can replay historical signals with different parameters (backtest engine)
- FR63: Operator can define and save backtest scenarios with parameter configurations
- FR64: System can run multiple backtests in batch for scenario comparison
- FR65: Operator can compare backtest results across multiple scenarios
- FR66: System can optimize parameters via grid search over configurable ranges
- FR67: Operator can manage backtests and view results via dashboard

## Non-Functional Requirements

### Performance

| Requirement | Target | Measurement |
|-------------|--------|-------------|
| **Signal-to-Trade Latency** | < 5 seconds | Time from webhook receipt to trade execution |
| **Webhook Processing** | < 500ms | Time to process and score incoming signal |
| **Dashboard Response** | < 2 seconds | Page load and data refresh time |
| **Database Queries** | < 100ms | Neo4j and Supabase query response |
| **Concurrent Signals** | Handle 10+ simultaneous | No signal dropped under burst load |

### Security

| Requirement | Specification |
|-------------|---------------|
| **Private Key Storage** | Environment variables only, never in code or logs |
| **API Key Management** | Secure storage with rotation capability |
| **Webhook Validation** | Signature verification for all Helius webhooks |
| **Dashboard Access** | Local network only (no public exposure) or authenticated |
| **Logging** | No sensitive data (keys, signatures) in logs |
| **Backup** | Daily backup of Supabase data, Neo4j export weekly |

### Reliability

| Requirement | Target | Recovery |
|-------------|--------|----------|
| **System Uptime** | ≥ 95% | Auto-restart on crash |
| **Webhook Availability** | 24/7 | Health check endpoint, alerting |
| **Data Persistence** | Zero data loss | Transaction logging, backup |
| **Graceful Degradation** | Continue without non-critical services | Fallback to core functions |
| **Error Recovery** | Auto-retry failed trades (configurable) | Manual override available |

### Integration

| External Service | Reliability Requirement | Fallback Strategy |
|------------------|------------------------|-------------------|
| **Helius Webhooks** | > 99% event delivery | RPC polling fallback |
| **DexScreener API** | Tolerate 5min outage | Cache recent data, Birdeye fallback |
| **Jupiter API** | < 1% trade failure rate | Raydium direct, retry logic |
| **Solana RPC** | Multiple provider rotation | Failover to backup RPC |

### Scalability (Limited Scope)

| Requirement | Target |
|-------------|--------|
| **Watchlist Size** | Support 1,000+ monitored wallets |
| **Trade History** | Store 1 year of trade data |
| **Signal Log** | Store 6 months of all signals |

