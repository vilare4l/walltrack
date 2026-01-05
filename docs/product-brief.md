---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'product-brief'
lastStep: 5
project_name: 'walltrack'
user_name: 'Christophe'
date: '2026-01-04'
---

# Product Brief: walltrack

**Date:** 2026-01-04
**Author:** Christophe

---

## Executive Summary

WallTrack is a personal trading automation system for exploiting on-chain alpha in Solana memecoin markets. Rather than competing on execution speed or manual effort, the system leverages insider edge through intelligent wallet copy-trading with full operator control.

**Core Philosophy:** Manual curation + Automated execution = Control + Efficiency

The system addresses a fundamental problem: memecoin trading is an insider's game, and existing copy-trading bots (Trojan, TradeWiz) work but extract too much value through fees while offering zero transparency or granular control.

**Target Operator:** Single user (Christophe) operating the system as a "money printer"—curating a watchlist of high-performing wallets, configuring exit strategies, and monitoring performance. Zero manual trading required.

**Core Value Proposition:** Transform memecoin trading from inaccessible insider game into a systematic, transparent, and controllable operation—keeping 100% of profits while maintaining full system mastery.

---

## Core Vision

### Problem Statement

Memecoin trading on Solana is fundamentally an insider's game. The information asymmetry is brutal:

- **Insiders/Devs** (T+0): First movers with privileged access
- **Smart money wallets** (T+seconds): Early followers with proven edge
- **KOL tweets** (T+30min): Distribution phase begins
- **Retail FOMO** (T+1h): Exit liquidity

For the average trader without insider connections, there are only two paths: **luck** (random bets hoping to catch pumps) or **unsustainable manual labor** (tracking hundreds of wallets across multiple tools).

The current state is clear: "Trading memecoins is too tedious, and I have no edge."

### Problem Impact

**Without a systematic approach:**

- Retail consistently loses money chasing pumps after smart money has positioned
- Manual wallet tracking via on-chain tools (GMGN, Solscan) is time-intensive and error-prone
- Copy-trading bots exist and work, but they extract significant value through fees (0.5-1% per trade)
- Existing bots are black boxes—zero transparency on decision logic, no granular control over strategies
- No way to validate wallet quality progressively (simulation mode missing)
- Capital protection relies on trusting third-party systems

**The fundamental blocker:** "I know the edge exists (insider wallets), but exploiting it requires either expensive bots I don't control or manual effort I won't sustain."

### Why Existing Solutions Fall Short

**Copy-Trading Bots (Trojan, TradeWiz, etc.):**

| What Works | What Fails |
|------------|------------|
| ✅ Proof of concept validated—copy trading works | ❌ High fees (0.5-1% per trade) erode profits |
| ✅ Real-time execution via webhooks | ❌ Black box—no transparency on why trades execute |
| ✅ Convenient Telegram UX | ❌ Zero granular control (fixed strategies, no customization) |
| | ❌ No simulation mode per wallet (all-or-nothing live trading) |
| | ❌ No performance tracking per wallet for data-driven exclusion |
| | ❌ Cannot customize exit strategies per wallet or position |

**On-Chain Discovery Tools (GMGN, Solscan, Birdeye):**

- Excellent for wallet discovery but require manual tracking afterward
- No automated execution—analysis tools only
- Time-intensive to monitor hundreds of wallets continuously

**Telegram/Discord Groups:**

- Shared wallet lists require manual trading afterward
- Not sustainable for daily operation

**MEV Bots:**

- Different game (front-running, not copy-trading)
- Not aligned with the copy-trading edge model

### Proposed Solution

WallTrack is a **personal trading intelligence system** that combines the best of existing solutions while eliminating their critical flaws:

**The System:**

1. **Wallet Discovery** (Manual via GMGN) → Curate high-quality wallet watchlist
2. **Signal Detection** (Helius Webhooks) → Real-time swap notifications for watchlist wallets
3. **Validation** (Simulation Mode Per Wallet) → Test wallet quality before risking capital
4. **Execution** (Automated Copy-Trading) → Mirror smart money moves with custom strategies
5. **Performance Tracking** → Data-driven watchlist curation based on wallet win rates
6. **Exit Strategy Customization** → Per-wallet strategies with per-position overrides
7. **Risk Management** → Simple global position sizing (2% per trade)

**Daily Operator Workflow:**

- **Morning:** Dashboard review—active positions, PnL, watchlist analytics (signals all/30d/7d/24h, win rates)
- **During Day:** Curate watchlist (add/remove wallets), adjust exit strategies, promote wallets from simulation → live
- **Evening:** Review daily synthesis (PnL, signals executed, circuit breaker status)

**Key Principle:** "Trading without overdoing it"—high-level system operation, not active trading.

### Key Differentiators

| Differentiator | WallTrack Approach | Competitive Advantage |
|----------------|-------------------|----------------------|
| **Cost Structure** | Zero fees—100% profit retention | vs. 0.5-1% per trade on bots = significant savings at scale |
| **Transparency** | Open code, full visibility into decision logic | vs. Black box bots—complete system mastery |
| **Simulation** | Per-wallet simulation mode—validate before risking capital | vs. All-or-nothing live trading—progressive risk management |
| **Customization** | Exit strategies per wallet + per-position overrides | vs. Fixed strategies—adapt to wallet behavior patterns |
| **Control** | Daily high-level curation, not manual trading | vs. Set-and-forget OR manual trading—operator sweet spot |
| **Performance Tracking** | Win rate and signal analytics per wallet | vs. No granular tracking—data-driven watchlist management |
| **Development** | Claude Code + AI makes complex system accessible | vs. Buy vs. build tradeoff—learning + ownership |

**Unique Edge:** The combination of **zero fees + full control + simulation validation + strategy customization** creates a system that's simultaneously more profitable, safer, and more flexible than paid bots—while building permanent skills in Solana/DeFi infrastructure.

**Why Now:** Claude Code and AI assistance make building sophisticated trading infrastructure accessible to solo technical operators—a capability that didn't exist 12 months ago.

---

## Target Users

### Primary User

**Persona: Christophe — The System Operator**

| Attribute | Description |
|-----------|-------------|
| **Profile** | Technical professional building personal trading infrastructure with AI assistance |
| **Technical Level** | Beginner across Python, Solana/DeFi, and trading—learning by building |
| **Role** | Solo system operator—no team, no external users |
| **Time Investment** | Daily high-level interaction (watchlist curation, strategy adjustments), zero manual trading |
| **Capital Approach** | Start small (300€), increase stakes progressively as confidence builds |

**Core Motivation:**

"I know memecoin trading is an insider's game. I want to exploit that edge without expensive bots I don't control or unsustainable manual effort. Building WallTrack means learning Solana/DeFi infrastructure while creating a personal money printer."

**Current Frustrations:**

- Copy-trading bots (Trojan, TradeWiz) work but extract too much value via fees
- Black box systems—zero transparency, zero granular control
- No way to validate wallet quality progressively (simulation missing)
- Manual tracking via GMGN is unsustainable for daily operation

**Success Vision:**

- System runs autonomously 24/7 with high-level daily curation
- Progressive validation: simulation → small live capital → increase stakes
- Complete system mastery—understands every decision, not trusting a black box
- Long-term: multi-chain expansion (Base, Arbitrum) once Solana foundation is solid

### Secondary Users

**N/A** — This is a personal system with no external users, stakeholders, or secondary roles.

### User Journey

**Phase 1: Discovery & Setup (Day 1)**

Christophe decides to build WallTrack after researching copy-trading bots and concluding: "They work, but I can do better while learning."

**Initial Setup:**
- Configure system parameters (capital: 300€, risk: 2% per trade)
- Discover 2-3 promising wallets on GMGN (on-chain discovery tool)
- Add wallets to watchlist in **simulation mode**
- Launch system and wait for first signals

**Emotion:** Mix of excitement and uncertainty—"Will this actually work?"

---

**Phase 2: Validation Through Simulation (Weeks 2-4)**

Daily operator workflow establishes:

- **Morning:** Dashboard review—active positions, PnL, watchlist analytics (signals all/30d/7d/24h, win rates)
- **During Day:** Curate watchlist (add/remove wallets based on performance), adjust exit strategies
- **Evening:** Review daily synthesis (PnL, signals executed, circuit breaker status)

**Confidence-Building Criteria:**

- ✅ 70%+ win rate over 50+ simulated trades
- ✅ System runs 7+ days without crashes
- ✅ Complete understanding of every trade decision (transparency = trust)

**Key Moment:** After 2 weeks of stable simulation, Christophe thinks: "I understand how this works. Time to test with real capital."

---

**Phase 3: First Live Capital (Week 5)**

The system already supports live mode (Jupiter API integrated in MVP), but Christophe has been using simulation only. Now he toggles one high-performing wallet to live mode with minimal capital (50€ test).

**First Signal in Live Mode:**
- Helius webhook triggers: Wallet X swaps into Token Y
- System evaluates: safety checks pass, creates position, executes REAL entry order via Jupiter API
- Christophe monitors but doesn't intervene

**The "Aha" Moment:**

First profitable exit: **+5€ realized profit**

**Emotion:** "It works. Not theoretical, not simulated—real profit from real execution. Now I increase the stakes."

**What Success Means:**
- Not about scaling to thousands of euros immediately
- Validation that the system works as designed
- Foundation for progressive stake increases as confidence grows
- Proof that learning investment (Python, Solana, trading infrastructure) pays off

---

**Phase 4: Long-Term Operation (Months 2+)**

- Increase capital allocation progressively (300€ → 500€ → 1000€+)
- Refine watchlist based on performance data (exclude underperforming wallets)
- Customize exit strategies per wallet based on behavior patterns
- Maintain daily high-level curation without manual trading

**Future Vision:**
- Multi-chain expansion (Base, Arbitrum) once Solana foundation is mastered
- Complete system ownership—skills are permanent, profits compound

---

## Success Metrics

### User Success (Operator Perspective)

**Primary Success Indicator:** Progressive validation from simulation to profitable live trading.

The system succeeds when Christophe (the operator) can:

1. **Simulation Phase (Weeks 1-4):**
   - System runs 7+ days without crashes
   - Win rate ≥ 70% over 50+ simulated trades
   - Complete understanding of every trade decision (transparency = trust)

2. **Live Validation (Week 5+):**
   - First profitable trade (+5€) = "It works!"
   - Progressive capital increase as confidence builds
   - Daily synthesis shows consistent performance

3. **Long-Term Operation (Months 2+):**
   - Autonomous 24/7 operation with minimal intervention
   - Daily high-level curation only (no manual trading)
   - Continuous learning and system mastery

**Emotional Success:** "It was worth it" = The profit validates the learning investment.

### Trading Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Win Rate** | ≥ 70% | Profitable trades / Total trades |
| **Profit Ratio** | ≥ 3:1 | Average win / Average loss |
| **Daily Return** | ≥ 1% | Daily PnL / Starting capital (aggressive target) |

### System Reliability Metrics

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **System Uptime** | ≥ 95% | Must run 24/7 to catch opportunities |
| **Execution Latency** | < 5 seconds | Signal → trade before price moves |
| **Webhook Reliability** | > 99% | Can't miss insider movements |
| **Daily Signals** | 5-20 per wallet | Enough opportunities without noise |

### Circuit Breakers (Failure Detection)

Automated protection against capital loss:

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **Drawdown > 20%** | Pause all trading, manual review | Capital protection threshold |
| **Win rate < 40%** over 50 trades | Halt and recalibrate | Strategy no longer working |
| **3 consecutive max-loss trades** | Flag for review | Pattern indicates problem |
| **No signals for 48 hours** | System health check | Potential webhook failure |

### MVP Validation Criteria

Before considering MVP complete:

| Criteria | Threshold | Validation Method |
|----------|-----------|-------------------|
| **Core features operational** | All 7 features working | Manual testing + E2E tests |
| **Dashboard functional** | All pages operational | UI walkthrough |
| **Simulation stability** | 7 days no crashes | Stability monitoring |
| **Signal generation** | 5+ signals per day per wallet | Signal logs |

**North Star Metric:** Profit generated with zero manual trading intervention—validated first in simulation, then in live mode.

---

## MVP Scope

### Core Features

Based on our conversation, WallTrack focuses on **simulation-first copy trading** with manual curation:

| # | Feature | Description | Validation |
|---|---------|-------------|------------|
| 1 | **Watchlist Management** | Manual CRUD for wallet addresses (add/remove/view) | UI shows watchlist with status |
| 2 | **Helius Webhooks** | Real-time swap notifications for watchlist wallets | Webhook status visible in Config |
| 3 | **Token Safety Analysis** | Analyze swap signals for rug/honeypot detection | Safety scores logged |
| 4 | **Signal Filtering** | Filter signals by safety threshold | Only safe signals proceed |
| 5 | **Position Creation (Simulation)** | Create simulated positions from safe signals | Positions visible in Dashboard |
| 6 | **Price Monitoring** | Track token prices for active positions (stop loss, trailing stop) | Price updates logged |
| 7 | **Wallet Activity Monitoring** | Monitor source wallet sales via Helius (mirror exit) | Wallet exits detected |
| 8 | **Order Execution (Dual Mode)** | Entry/exit orders with custom strategies + Jupiter API for live swaps | Simulation/Live toggle per wallet |
| 9 | **Performance Tracking** | Track win rate, PnL per wallet (simulation) | Analytics visible per wallet |

**Execution Modes:** All 9 features support BOTH simulation and live modes from MVP. The operator chooses which mode to use per wallet.

**Implementation Notes:**
- **Price Monitoring:** DexScreener API polling (30-60s intervals) for active positions
- **Wallet Monitoring:** Helius webhooks already cover this (same system as signal detection)
- **Live Execution:** Jupiter API integration developed in MVP, operator chooses when to activate per wallet

### Token Safety Analysis Model

Simplified scoring focused on capital protection:

| Check | Weight | Purpose |
|-------|--------|---------|
| **Liquidity Check** | 25% | Avoid low-liquidity rugs (min $50K) |
| **Holder Distribution** | 25% | Detect centralized ownership (top 10 < 80%) |
| **Contract Analysis** | 25% | Identify honeypot patterns |
| **Age Threshold** | 25% | Filter brand new tokens (min 24h) |

**Safety Score = Weighted average of 4 checks**

**Threshold:** Score ≥ 0.60 → Safe to trade (adjustable via Config)

### Exit Strategy Customization

WallTrack supports multiple exit strategies that can be combined:

| Strategy Type | Description | Example |
|---------------|-------------|---------|
| **Scaling Out (Paliers)** | Take profit at predefined levels | 50% @ 2x, 25% @ 3x, 25% hold |
| **Mirror Wallet Exit** | Sell when original wallet sells | If Liberty wallet exits Token X → we exit |
| **Stop Loss** | Exit if price drops below threshold | Exit if -20% from entry |
| **Trailing Stop** | Follow price upward, sell on reversal | Trail 15% below peak price |

**Per-Wallet Configuration:**
- Default: Scaling out + Mirror exit + Stop loss (-20%)
- Wallet "Liberty": Scaling 70% @ 1.5x + Mirror exit + Trailing stop 10%
- Wallet "Conservative": Stop loss only (-10%) + Mirror exit

**Per-Position Override:**
- Ability to disable mirror exit for specific position
- Adjust stop loss/trailing stop per position
- Override scaling levels manually

**Priority Logic:**
1. **Stop loss** triggers first (capital protection)
2. **Mirror wallet exit** overrides scaling if wallet sells
3. **Trailing stop** activates after profit threshold
4. **Scaling out** executes at predefined levels

**Exemple concret:**
- Wallet Liberty achète Token X
- WallTrack copie: Entry @ $0.10
- Stop loss: -20% ($0.08)
- Scaling: 50% @ $0.20 (2x)
- **Mirror exit ACTIVE:** Si Liberty vend @ $0.15 → WallTrack vend aussi (ignore scaling)

### Execution Modes

**BOTH modes developed in MVP:**

| Mode | Description | Technical Implementation |
|------|-------------|--------------------------|
| **Simulation** | Full pipeline with orders, no real execution | All features active, Jupiter API call skipped |
| **Live** | Real execution via Jupiter API | Full pipeline + Jupiter swap execution |

**Key Clarification:**
- ✅ **Development:** BOTH modes built in MVP (simulation AND Jupiter API integration)
- ✅ **Usage Strategy:** Operator USES simulation first (Weeks 1-4), then activates live mode when validated

**Simulation mode:** Mirrors live behavior exactly—same orders, same sizing, same exit strategies—only the final Jupiter swap execution is skipped.

**Per-Wallet Mode Selection:**
- Wallet A: Simulation (testing new wallet)
- Wallet B: Live (validated, profitable)
- Progressive promotion: simulation → small live test (50€) → full live (300€+)

**Technical Requirements for MVP:**
1. ✅ Simulation engine (mock execution, PnL tracking)
2. ✅ Jupiter API integration (swap execution on Solana)
3. ✅ Mode toggle per wallet (UI config)
4. ✅ Wallet connection (Solana keypair management)

### Out of Scope for MVP

| Feature | Reason | Target |
|---------|--------|--------|
| **Token Discovery** | Manual curation via GMGN sufficient | Optional V2 |
| **Wallet Discovery** | Manual watchlist approach (GMGN) | Optional V2 (ML-based) |
| **Wallet Profiling System** | Manual tracking sufficient for MVP | Optional V2 (automated profiling) |
| **Clustering (Neo4j)** | Complexity not justified yet | V3 (research required) |
| **ML Scoring (XGBoost)** | Start simple with rules | V2 |
| **Feedback Loop** | Requires stable trading first | V2 |
| **Backtest Engine** | Focus on forward simulation | V2 |
| **Multi-chain** | Solana focus first | V3+ (Base, Arbitrum) |

**Rationale:**
- Manual curation gives operator full control over wallet quality
- Eliminates complexity of automated profiling/discovery
- Faster MVP validation (2-4 weeks vs months)
- Can add automation in V2 if manual becomes bottleneck

### MVP Success Criteria

Before moving to live trading:

| Criteria | Threshold | Validation Method |
|----------|-----------|-------------------|
| **Simulation Stability** | 7 days no crashes | Uptime monitoring |
| **Trading Performance** | 70%+ win rate over 50+ simulated trades | Performance logs |
| **Signal Generation** | 5-20 signals per day across watchlist | Signal logs |
| **System Understanding** | Operator understands every trade decision | Manual review + transparency |
| **Dashboard Operational** | All pages functional (Home, Watchlist, Config) | UI walkthrough |

**Go/No-Go Decision:** Only proceed to live mode when ALL criteria met.

### Future Vision

**V2 — Enhanced Intelligence (Months 6-12):**
- Optional token discovery if manual curation proves insufficient
- Automated wallet profiling (ML-based win rate prediction)
- Feedback loop for automatic wallet score adjustment
- Advanced exit strategy optimization per wallet behavior

**V3 — Capital Scaling (Year 2+):**
- Multi-chain expansion (Base, Arbitrum) once Solana mastered
- Neo4j clustering for insider network detection
- Advanced cluster analysis with network visualization
- Potential productization (SaaS) if personally profitable

**Long-term North Star:** Complete trading infrastructure mastery—skills are permanent, system scales with capital.

---
