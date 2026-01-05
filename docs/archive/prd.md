---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
inputDocuments: ['docs/product-brief.md']
documentCounts:
  briefs: 1
  research: 0
  brainstorming: 0
  projectDocs: 0
workflowType: 'prd'
lastStep: 11
project_name: 'walltrack'
user_name: 'Christophe'
date: '2026-01-04'
completed: true
---

# Product Requirements Document - walltrack

**Author:** Christophe
**Date:** 2026-01-04

## Executive Summary

WallTrack is a personal trading intelligence system for exploiting on-chain alpha in Solana memecoin markets through intelligent wallet copy-trading. The system addresses a fundamental market inefficiency: memecoin trading is an insider's game, and existing copy-trading solutions extract excessive value through fees while offering zero transparency or granular control.

The core value proposition combines manual wallet curation with automated execution—providing control + efficiency without the overhead of manual trading or the opacity of commercial bots. The operator (Christophe) curates a watchlist of high-performing wallets discovered via GMGN, receives real-time swap notifications via Helius webhooks, validates wallet quality in simulation mode before risking capital, and executes automated copy-trades with customizable exit strategies.

WallTrack transforms memecoin trading from an inaccessible insider game into a systematic, transparent, and controllable operation—retaining 100% of profits while building permanent skills in Solana/DeFi infrastructure.

### What Makes This Special

**Zero-Fee Intelligent Copy Trading with Progressive Validation**

The unique combination of capabilities not available in existing solutions:

1. **Cost Structure**: Zero fees = 100% profit retention vs. 0.5-1% per trade on commercial bots (significant savings at scale)

2. **Transparency**: Open code with full visibility into decision logic vs. black box systems—complete system mastery instead of blind trust

3. **Progressive Risk Management**: Per-wallet simulation mode validates quality before risking capital vs. all-or-nothing live trading on commercial platforms

4. **Strategy Customization**: Exit strategies per wallet + per-position overrides vs. fixed strategies—adapt to wallet behavior patterns

5. **Operator Control**: Daily high-level curation (watchlist management, strategy adjustments) without manual trading vs. either set-and-forget or unsustainable manual effort

6. **Performance Intelligence**: Win rate and signal analytics per wallet for data-driven watchlist management vs. no granular tracking

**The Insider Edge Made Accessible**: By copying proven smart money wallets in real-time with custom strategies, WallTrack exploits the same insider edge that drives memecoin markets—but with complete control, zero fees, and progressive validation from simulation to profitable live trading.

**Development Advantage**: Claude Code and AI assistance make building sophisticated trading infrastructure accessible to solo technical operators—a capability that didn't exist 12 months ago.

## Project Classification

**Technical Type:** blockchain_web3
**Domain:** fintech
**Complexity:** high
**Project Context:** Greenfield - new project

**Classification Rationale:**

- **Blockchain/Web3 Signals**: Solana blockchain integration, DeFi protocols, on-chain data analysis, wallet monitoring, smart money tracking, Jupiter DEX swaps, Helius webhooks
- **Fintech Domain**: Trading automation, transaction execution, risk management, position sizing, PnL tracking, wallet analytics, signal filtering
- **High Complexity Considerations**:
  - Cryptocurrency regulations and compliance (KYC/AML considerations for future productization)
  - Real-time trading system security and audit requirements
  - Fraud prevention and rug detection (token safety analysis)
  - Financial data protection and wallet security
  - Integration with multiple DeFi protocols and APIs

**Key Technical Components:**
- Helius webhooks for real-time blockchain event monitoring
- Jupiter API for decentralized swap execution
- DexScreener API for price monitoring
- Token safety analysis (liquidity, holder distribution, contract analysis)
- Dual-mode execution system (simulation + live)
- Position management with multiple exit strategies
- Performance tracking and analytics

## Success Criteria

### User Success

**Primary Success Indicator:** Progressive validation from simulation to profitable live trading.

The system succeeds when Christophe (the operator) achieves:

**Simulation Phase (Weeks 1-4):**
- System runs 7+ days without crashes
- Win rate ≥ 55-60% over 50+ simulated trades (profit ratio ≥ 3:1 makes this profitable)
- Complete understanding of every trade decision (transparency = trust)
- Daily synthesis shows consistent performance patterns

**Live Validation (Week 5+):**
- First profitable trade (+5€ minimum) = validation moment "It works!"
- Progressive capital increase as confidence builds (300€ → 500€ → 1000€+)
- Daily synthesis shows sustained profitable execution
- Autonomous 24/7 operation with minimal intervention

**Long-Term Operation (Months 2+):**
- Watchlist refinement based on performance data (exclude underperforming wallets)
- Customized exit strategies per wallet based on behavior patterns
- Daily high-level curation only (no manual trading required)
- Continuous learning and system mastery

**Emotional Success:** "It was worth it" = The profit validates the learning investment in Python, Solana/DeFi, and trading infrastructure.

### Business Success

**Phase 1: Proof of Concept (Months 1-2)**
- Simulation stability: 7+ consecutive days without system crashes
- Trading performance: 55-60% win rate across 50+ simulated trades (with 3:1 profit ratio = net positive)
- Signal generation: 5-20 signals per day per wallet across watchlist
- Complete transparency: Operator understands every automated decision

**Phase 2: Live Capital Validation (Months 3-4)**
- First profitable trade execution: +5€ minimum realized profit
- Progressive capital scaling: 300€ → 500€ → 1000€ as confidence builds
- Sustained win rate: 55%+ in live mode (with profit ratio ≥ 3:1)
- Net profitable over 30-day periods (focus on monthly profitability, not daily volatility)

**Phase 3: Operational Maturity (Months 5+)**
- Profit ratio: ≥ 3:1 (average win / average loss)
- System uptime: ≥ 95% (critical for 24/7 opportunity capture)
- Watchlist optimization: Data-driven curation based on wallet performance
- Skills acquisition: Permanent competence in Solana/DeFi infrastructure

**Long-Term Vision (Year 2+):**
- Capital scaling validated on Solana
- Multi-chain expansion (Base, Arbitrum) once foundation is mastered
- Optional productization (SaaS) if personally profitable and validated

### Technical Success

**System Reliability Metrics:**

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **System Uptime** | ≥ 95% | Must run 24/7 to catch insider opportunities |
| **Execution Latency** | < 5 seconds | Signal → trade before price moves significantly |
| **Webhook Reliability** | > 99% | Cannot miss insider movements |
| **Daily Signals** | 5-20 per wallet | Enough opportunities without noise/spam |
| **Price Monitoring Accuracy** | ±1% | Accurate stop-loss and trailing-stop triggers |

**Circuit Breakers (Automated Protection):**

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **Drawdown > 20%** | Pause all trading, manual review required | Capital protection threshold |
| **Win rate < 40%** over 50 trades | Halt and recalibrate system | Strategy no longer effective |
| **3 consecutive max-loss trades** | Flag for operator review | Pattern indicates systemic problem |
| **No signals for 48 hours** | System health check required | Potential webhook or API failure |

**Technical Validation Criteria:**

- **Token Safety Pipeline**: All signals pass safety threshold (≥ 0.60 score) before position creation
- **Dual-Mode Execution**: Both simulation and live modes operational from MVP
- **Position Management**: Stop-loss, trailing-stop, scaling-out, and mirror-exit all functional
- **Performance Tracking**: Per-wallet win rate, PnL, and signal analytics operational
- **Wallet Security**: Private key management secure and audited

### Measurable Outcomes

**MVP Completion Criteria (Before Live Trading):**

| Criteria | Threshold | Validation Method |
|----------|-----------|-------------------|
| **Core Features Operational** | All 9 features working | Manual testing + E2E tests |
| **Dashboard Functional** | All pages operational | UI walkthrough |
| **Simulation Stability** | 7 days no crashes | Stability monitoring |
| **Signal Generation** | 5+ signals per day per wallet | Signal logs review |
| **Trading Performance** | 55-60% win rate (simulation) with 3:1 profit ratio | Performance analytics |

**Live Trading Validation:**
- First profitable exit: +5€ realized profit minimum
- Progressive capital test: 50€ → 300€ → 500€ success sequence
- Sustained performance: 55%+ win rate over 30+ live trades (with 3:1 profit ratio)
- Zero manual trading: Full automation validated

**North Star Metric:** Profit generated with zero manual trading intervention—validated first in simulation, then in live mode.

## Product Scope

### MVP - Minimum Viable Product

**Core Features (All 9 support BOTH simulation and live modes):**

| # | Feature | Description | Success Validation |
|---|---------|-------------|-------------------|
| 1 | **Watchlist Management** | Manual CRUD for wallet addresses | UI shows watchlist with status indicators |
| 2 | **Helius Webhooks** | Real-time swap notifications | Webhook status visible in Config page |
| 3 | **Token Safety Analysis** | Rug/honeypot detection scoring | Safety scores logged and displayed |
| 4 | **Signal Filtering** | Filter by safety threshold | Only safe signals proceed to positions |
| 5 | **Position Creation** | Simulated positions from signals | Positions visible in Dashboard |
| 6 | **Price Monitoring** | Track prices for exit triggers | Price updates logged (DexScreener API) |
| 7 | **Wallet Activity Monitoring** | Monitor source wallet sales | Mirror-exit signals detected via Helius |
| 8 | **Order Execution (Dual Mode)** | Entry/exit with custom strategies | Simulation/Live toggle per wallet |
| 9 | **Performance Tracking** | Win rate, PnL per wallet | Analytics visible per wallet |

**Technical Stack:**
- **Backend**: Python 3.11+, FastAPI
- **Data Layer**: Supabase (PostgreSQL) for config, tokens, positions
- **Blockchain**: Solana (Helius webhooks, Jupiter API)
- **Price Data**: DexScreener API (30-60s polling)
- **UI**: Gradio (rapid iteration, operator-friendly)
- **Testing**: Pytest (unit + integration + E2E with Playwright)

**Token Safety Model (Simplified for MVP):**

| Check | Weight | Purpose |
|-------|--------|---------|
| **Liquidity Check** | 25% | Avoid low-liquidity rugs (min $50K) |
| **Holder Distribution** | 25% | Detect centralized ownership (top 10 < 80%) |
| **Contract Analysis** | 25% | Identify honeypot patterns |
| **Age Threshold** | 25% | Filter brand new tokens (min 24h age) |

**Safety Score = Weighted average ≥ 0.60 → Safe to trade**

**Exit Strategy Customization:**

| Strategy Type | Description | Example Configuration |
|---------------|-------------|----------------------|
| **Scaling Out (Paliers)** | Take profit at predefined levels | 50% @ 2x, 25% @ 3x, 25% hold |
| **Mirror Wallet Exit** | Sell when original wallet sells | If Liberty sells Token X → WallTrack sells |
| **Stop Loss** | Exit if price drops below threshold | -20% from entry (capital protection) |
| **Trailing Stop** | Follow price up, sell on reversal | Trail 15% below peak price |

**Priority Logic:**
1. Stop loss triggers first (capital protection)
2. Mirror wallet exit overrides scaling if source wallet sells
3. Trailing stop activates after profit threshold
4. Scaling out executes at predefined levels

**Execution Modes:**

| Mode | Description | Technical Implementation |
|------|-------------|--------------------------|
| **Simulation** | Full pipeline, no real execution | All features active, Jupiter API call skipped |
| **Live** | Real execution via Jupiter API | Full pipeline + Jupiter swap execution |

**Per-Wallet Mode Selection:** Operator can set each wallet to simulation or live independently, enabling progressive validation (simulation → small live test → full live).

### Growth Features (Post-MVP)

**V2 — Enhanced Intelligence (Months 6-12):**

**Optional if manual curation proves insufficient:**
- Token discovery automation (if GMGN manual approach becomes bottleneck)
- Automated wallet profiling with ML-based win rate prediction
- Feedback loop for automatic wallet score adjustment based on performance
- Advanced exit strategy optimization per wallet behavior patterns
- Portfolio rebalancing across multiple positions

**Enhanced Analytics:**
- Wallet clustering to identify insider networks
- Signal pattern analysis across wallet types
- Performance attribution (which wallets/strategies drive profit)
- Risk exposure visualization across positions

### Vision (Future)

**V3 — Capital Scaling (Year 2+):**

**Multi-Chain Expansion:**
- Base (Coinbase L2) integration once Solana mastered
- Arbitrum integration for EVM memecoin markets
- Unified watchlist management across chains
- Cross-chain performance comparison

**Advanced Network Analysis:**
- Neo4j clustering for insider network detection
- Social graph analysis of wallet connections
- Cluster-based signal weighting (insider network proximity)
- Network visualization for manual curation assistance

**Potential Productization:**
- SaaS offering if personally profitable and validated
- Community wallet sharing (curated watchlists)
- API access for external integrations
- White-label infrastructure for other operators

**Long-Term North Star:** Complete trading infrastructure mastery—skills are permanent, system scales with capital, potential to productize once validated at personal scale.

## User Journeys

### Primary User: Christophe (System Operator)

**Journey 1: Discovery & Setup (Day 1)**

**Context:** Christophe decides to build WallTrack after researching copy-trading bots and concluding "They work, but I can do better while learning."

**Steps:**
1. Configure system parameters (capital: 300€, risk: 2% per trade)
2. Discover 2-3 promising wallets on GMGN (on-chain discovery tool)
3. Add wallets to watchlist in **simulation mode** via Watchlist Management UI
4. Launch system and wait for first signals

**Emotion:** Mix of excitement and uncertainty—"Will this actually work?"

**Success Criteria:**
- System configured without errors
- Wallets added to watchlist successfully
- Helius webhooks operational (visible in Config page)
- First signals received within 24 hours

---

**Journey 2: Validation Through Simulation (Weeks 2-4)**

**Context:** Daily operator workflow establishes confidence through simulation validation.

**Daily Workflow:**
- **Morning:** Dashboard review—active positions, PnL, watchlist analytics (signals all/30d/7d/24h, win rates)
- **During Day:** Curate watchlist (add/remove wallets based on performance), adjust exit strategies per wallet
- **Evening:** Review daily synthesis (PnL, signals executed, circuit breaker status)

**Confidence-Building Criteria:**
- ✅ 55-60% win rate over 50+ simulated trades (with 3:1 profit ratio = net profitable)
- ✅ System runs 7+ days without crashes
- ✅ Complete understanding of every trade decision (transparency = trust)

**Key Moment:** After 2 weeks of stable simulation: "I understand how this works. Time to test with real capital."

**Success Criteria:**
- Simulation mode operational for 7+ consecutive days
- Performance analytics show 55-60% win rate with 3:1 profit ratio
- All safety checks pass (token safety, signal filtering)
- Operator confident in system behavior

---

**Journey 3: First Live Capital (Week 5)**

**Context:** System already supports live mode (Jupiter API integrated in MVP), but Christophe has been using simulation only. Now he toggles one high-performing wallet to live mode with minimal capital (50€ test).

**First Signal in Live Mode:**
1. Helius webhook triggers: Wallet X swaps into Token Y
2. System evaluates: safety checks pass, creates position
3. Executes REAL entry order via Jupiter API
4. Christophe monitors but doesn't intervene
5. Position tracked with configured exit strategies (stop-loss, scaling-out, mirror-exit)
6. Exit triggers automatically → **First profitable trade: +5€ realized profit**

**The "Aha" Moment:** "It works. Not theoretical, not simulated—real profit from real execution. Now I increase the stakes."

**Emotion:** Validation and confidence-building

**Success Criteria:**
- First live trade executes successfully via Jupiter API
- Position management (entry + exit) works in production
- Profitable outcome validates simulation predictions
- Zero manual intervention required

---

**Journey 4: Long-Term Operation (Months 2+)**

**Context:** Progressive capital increase and system mastery.

**Activities:**
- Increase capital allocation progressively (300€ → 500€ → 1000€+)
- Refine watchlist based on performance data (exclude underperforming wallets)
- Customize exit strategies per wallet based on behavior patterns
- Maintain daily high-level curation without manual trading

**Success Criteria:**
- Sustained 55%+ win rate in live mode (with 3:1 profit ratio)
- System uptime ≥ 95%
- Net profitable over monthly periods (memecoin volatility makes daily targets unrealistic)
- Complete system ownership—skills are permanent

**Future Vision:**
- Multi-chain expansion (Base, Arbitrum) once Solana foundation is mastered
- Potential productization if personally profitable

## Functional Requirements

### FR-1: Watchlist Management

**Description:** Manual CRUD operations for managing wallet addresses in the watchlist.

**User Stories:**
- As an operator, I can add a wallet address to the watchlist so that I can track its trading activity
- As an operator, I can remove a wallet from the watchlist so that I stop receiving signals from underperforming wallets
- As an operator, I can view all wallets in my watchlist with their current status (simulation/live, win rate, recent signals)
- As an operator, I can toggle a wallet between simulation and live mode so that I can progressively validate performance

**Acceptance Criteria:**
- UI provides add/remove/edit functionality for wallet addresses
- Each wallet has configurable mode (simulation/live)
- Wallet status visible in Dashboard (signals count, win rate, mode)
- Changes persist in Supabase database

**Priority:** MUST HAVE (MVP)

---

### FR-2: Real-Time Signal Detection

**Description:** Helius webhooks deliver real-time swap notifications for all watchlist wallets.

**User Stories:**
- As an operator, I want to receive real-time notifications when a watchlist wallet executes a swap so that I can copy the trade immediately
- As an operator, I want webhook status visible in the Config page so that I can verify the system is receiving signals
- As an operator, I want signal logs accessible so that I can audit what signals were received and processed

**Acceptance Criteria:**
- Helius webhooks configured for all active watchlist wallets
- Swap events trigger signal processing pipeline
- Webhook status visible in Config UI (connected/disconnected, last signal timestamp)
- Signal logs stored in Supabase for audit trail

**Priority:** MUST HAVE (MVP)

---

### FR-3: Token Safety Analysis

**Description:** Automated scoring system to detect rug pulls and honeypots before creating positions.

**User Stories:**
- As an operator, I want all tokens automatically analyzed for safety so that I avoid rug pulls
- As an operator, I want to see safety scores for each signal so that I can understand why trades are filtered
- As an operator, I want configurable safety thresholds so that I can adjust risk tolerance

**Acceptance Criteria:**
- Safety scoring uses 4 checks: Liquidity (≥$50K), Holder Distribution (top 10 < 80%), Contract Analysis (honeypot detection), Age (≥24h)
- Weighted average score calculated (each check = 25%)
- Configurable threshold (default 0.60)
- Signals below threshold filtered out automatically
- Safety scores logged and visible in UI

**Priority:** MUST HAVE (MVP)

---

### FR-4: Position Creation & Management

**Description:** Create positions from safe signals with dual-mode execution (simulation/live).

**User Stories:**
- As an operator, I want positions created automatically from safe signals so that I don't miss opportunities
- As an operator, I want simulation mode to track positions without real execution so that I can validate wallet quality
- As an operator, I want live mode to execute real trades via Jupiter API so that I can generate profit
- As an operator, I want to see all active positions in the Dashboard so that I can monitor performance

**Acceptance Criteria:**
- Simulation mode: Full pipeline (signal → position → exit) without Jupiter API execution
- Live mode: Full pipeline WITH Jupiter swap execution
- Position data includes: entry price, amount, source wallet, timestamp, mode
- Positions visible in Dashboard with real-time status

**Priority:** MUST HAVE (MVP)

---

### FR-5: Price Monitoring

**Description:** Track token prices for active positions using DexScreener API to trigger exit strategies.

**User Stories:**
- As an operator, I want real-time price updates for active positions so that stop-loss and trailing-stop triggers work correctly
- As an operator, I want price monitoring accuracy ±1% so that exit strategies execute at intended levels

**Acceptance Criteria:**
- DexScreener API polling (30-60s intervals) for all active position tokens
- Price updates logged and trigger exit strategy evaluation
- Accuracy within ±1% of actual market price
- Monitoring continues until position closed

**Priority:** MUST HAVE (MVP)

---

### FR-6: Exit Strategy Execution

**Description:** Multiple exit strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) with per-wallet configuration and per-position overrides.

**User Stories:**
- As an operator, I want stop-loss protection so that I limit downside risk (-20% default)
- As an operator, I want trailing-stop to capture upside while protecting profits (configurable trail %)
- As an operator, I want scaling-out at predefined levels so that I take partial profits (e.g., 50% @ 2x)
- As an operator, I want mirror-exit so that I sell when the source wallet sells
- As an operator, I want to configure exit strategies per wallet so that I can adapt to different wallet behaviors
- As an operator, I want to override exit strategies per position so that I can manually adjust for specific trades

**Acceptance Criteria:**
- Stop-loss triggers first (capital protection priority)
- Mirror-exit overrides scaling if source wallet sells
- Trailing-stop activates after profit threshold
- Scaling-out executes at configured levels
- Per-wallet default strategies configurable in UI
- Per-position overrides available in Dashboard

**Priority:** MUST HAVE (MVP)

---

### FR-7: Wallet Activity Monitoring

**Description:** Monitor source wallet sales via Helius webhooks to trigger mirror-exit strategy.

**User Stories:**
- As an operator, I want to be notified when a source wallet sells a token I'm holding so that I can mirror the exit
- As an operator, I want mirror-exit to execute automatically when enabled so that I follow smart money exits

**Acceptance Criteria:**
- Helius webhooks monitor ALL source wallets for sell events
- Sell events matched against active positions
- Mirror-exit triggers position close if enabled
- Execution logged for audit trail

**Priority:** MUST HAVE (MVP)

---

### FR-8: Performance Tracking & Analytics

**Description:** Track win rate, PnL, and signal analytics per wallet for data-driven curation.

**User Stories:**
- As an operator, I want to see win rate per wallet so that I can identify underperforming wallets for removal
- As an operator, I want PnL tracking per wallet so that I understand which wallets drive profit
- As an operator, I want signal analytics (count all/30d/7d/24h) so that I can monitor wallet activity levels
- As an operator, I want performance data available in Dashboard so that I can make curation decisions

**Acceptance Criteria:**
- Win rate calculated per wallet: (profitable trades / total trades)
- PnL aggregated per wallet: sum of all closed position profits/losses
- Signal counts tracked with time windows (all/30d/7d/24h)
- Analytics visible in Dashboard with sortable columns
- Historical data persisted in Supabase

**Priority:** MUST HAVE (MVP)

---

### FR-9: System Configuration & Status

**Description:** Centralized configuration interface for system parameters and status monitoring.

**User Stories:**
- As an operator, I want to configure capital allocation and risk parameters so that I control position sizing
- As an operator, I want to see webhook status so that I can verify signal reception
- As an operator, I want to see circuit breaker status so that I know if trading is paused
- As an operator, I want to configure safety thresholds so that I adjust risk tolerance

**Acceptance Criteria:**
- Config UI provides: capital amount, risk % per trade, safety threshold
- Webhook status visible (connected/disconnected, last signal)
- Circuit breaker status visible (active/paused, reason)
- Configuration changes persist and apply immediately

**Priority:** MUST HAVE (MVP)

---

## System Configuration Parameters

All system behavior should be configurable to allow operator adaptation to market conditions and risk tolerance. This section defines all configurable parameters with their default values.

### Trading Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Starting Capital** | 300€ | 50€ - unlimited | Total capital allocated to trading | Config UI |
| **Risk Per Trade** | 2% | 0.5% - 5% | Percentage of capital per position | Config UI |
| **Position Sizing Mode** | Fixed % | Fixed % / Dynamic | How position sizes are calculated | Config UI |

### Risk Management Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Stop Loss** | -20% | -5% to -50% | Maximum loss per position before exit | Per-wallet default + per-position override |
| **Trailing Stop %** | 15% | 5% - 30% | Distance below peak price for trailing stop | Per-wallet default + per-position override |
| **Slippage Tolerance** | 3% | 1% - 10% | Maximum acceptable slippage on Jupiter swaps | Config UI |
| **Max Drawdown (Circuit Breaker)** | 20% | 10% - 50% | Total portfolio loss triggering trading halt | Config UI |
| **Min Win Rate Alert** | 40% | 30% - 60% | Win rate threshold triggering wallet review | Config UI |
| **Consecutive Max-Loss Trigger** | 3 trades | 2 - 10 | Consecutive stop-loss hits triggering review | Config UI |

### Safety Analysis Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Safety Score Threshold** | 0.60 | 0.40 - 0.90 | Minimum score for trade execution | Config UI |
| **Liquidity Check Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Holder Distribution Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Contract Analysis Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Age Check Weight** | 25% | 0% - 50% | Weight in safety score calculation | Config file (advanced) |
| **Min Liquidity** | $50K | $10K - $500K | Minimum token liquidity threshold | Config UI |
| **Max Top 10 Holder %** | 80% | 50% - 95% | Maximum concentration in top 10 holders | Config UI |
| **Min Token Age** | 24 hours | 1h - 7 days | Minimum token age before trading | Config UI |

### Exit Strategy Parameters (Per-Wallet Defaults)

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Scaling Level 1** | 50% @ 2x | 10-100% @ 1.2x-10x | First scaling out level | Per-wallet config |
| **Scaling Level 2** | 25% @ 3x | 10-100% @ 1.5x-20x | Second scaling out level | Per-wallet config |
| **Scaling Level 3** | 25% hold | 0-100% @ any multiplier | Final scaling level or hold | Per-wallet config |
| **Mirror Exit Enabled** | true | true/false | Follow source wallet exits | Per-wallet config |
| **Trailing Stop Enabled** | false | true/false | Activate trailing stop | Per-wallet config |
| **Trailing Activation Threshold** | +20% | +10% to +100% | Profit level to activate trailing stop | Per-wallet config |

**Note:** All exit strategy parameters have per-wallet defaults but can be overridden per-position in the Dashboard UI.

### System Monitoring Parameters

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Price Polling Interval** | 45s | 15s - 120s | DexScreener API polling frequency | Config UI |
| **Webhook Timeout Alert** | 48 hours | 12h - 7 days | No signals threshold for system health alert | Config UI |
| **Max Price Data Staleness** | 5 minutes | 1m - 30m | Alert if price data not updated | Config file (advanced) |
| **Auto-Restart on Crash** | true | true/false | System auto-restart behavior | Config file (advanced) |

### Performance Thresholds (Circuit Breakers)

| Parameter | Default Value | Range | Description | Configurable Via |
|-----------|---------------|-------|-------------|------------------|
| **Min Win Rate (50+ trades)** | 40% | 30% - 60% | Halt trading if below this rate | Config UI |
| **Max Drawdown** | 20% | 10% - 50% | Halt trading if exceeded | Config UI |
| **Consecutive Max-Loss** | 3 trades | 2 - 10 | Flag for review after N stop-losses | Config UI |

### Configuration Persistence

**Storage:** All configuration parameters persist in Supabase `config` table.

**Change Propagation:**
- Config UI changes: Apply immediately to new signals/positions
- Per-wallet changes: Apply immediately to that wallet's new positions
- Per-position overrides: Apply only to that specific position

**Config Backup:**
- Configuration exported to JSON on every change
- Stored in `config_backup/` directory with timestamp
- Allows rollback to previous config if needed

**Validation:**
- All parameter changes validated before persistence
- Range checks enforced (e.g., stop-loss must be between -5% and -50%)
- Invalid values rejected with clear error message

---

## Non-Functional Requirements

### NFR-1: Performance

**Requirement:** System must execute trades within 5 seconds of signal receipt to capture price before significant movement.

**Rationale:** Copy-trading effectiveness depends on execution speed—smart money moves fast, and delays erode profit potential.

**Acceptance Criteria:**
- Webhook → Signal processing → Trade execution < 5 seconds (P95)
- Price monitoring polling: 30-60s intervals (sufficient for position management)
- Dashboard loads < 2 seconds (operator experience)

**Priority:** CRITICAL

---

### NFR-2: Reliability

**Requirement:** System uptime ≥ 95% to ensure 24/7 opportunity capture.

**Rationale:** Memecoin opportunities occur at any time—downtime means missed profitable trades.

**Acceptance Criteria:**
- System restarts automatically on crash
- Health checks monitor critical components (webhooks, API connections, database)
- Alerting for prolonged downtime (>30 minutes)
- Circuit breakers prevent cascade failures

**Priority:** CRITICAL

---

### NFR-3: Security

**Requirement:** Wallet private keys must be securely managed with no exposure in logs or UI.

**Rationale:** Compromise of trading wallet = total capital loss.

**Acceptance Criteria:**
- Private keys stored encrypted at rest (Supabase encryption or environment variables)
- No private key exposure in logs, error messages, or UI
- Jupiter API calls signed securely without key exposure
- Audit trail for all wallet operations

**Priority:** CRITICAL

---

### NFR-4: Data Integrity

**Requirement:** All trade execution, PnL, and performance data must be accurate and auditable.

**Rationale:** Operator trust depends on data accuracy—incorrect performance tracking undermines decision-making.

**Acceptance Criteria:**
- Atomic database transactions for position lifecycle (create → update → close)
- Audit trail for all state changes (signals, positions, exits)
- Data validation on all inputs (wallet addresses, prices, amounts)
- Reconciliation checks for PnL calculations

**Priority:** HIGH

---

### NFR-5: Observability

**Requirement:** Complete visibility into system state and trade decisions for operator trust.

**Rationale:** "Transparency = Trust"—operator must understand every automated decision to build confidence.

**Acceptance Criteria:**
- All signals logged with safety scores and filter decisions
- All positions logged with entry/exit details and PnL
- Circuit breaker triggers logged with reason
- Dashboard provides real-time system state view
- Historical logs queryable for debugging

**Priority:** HIGH

---

### NFR-6: Maintainability

**Requirement:** Codebase must be simple, well-documented, and testable for solo operator maintenance.

**Rationale:** Christophe is learning Python—code must be approachable for ongoing evolution and debugging.

**Acceptance Criteria:**
- Test coverage ≥ 70% (unit + integration + E2E)
- Clear separation of concerns (API clients, data layer, business logic)
- Type hints throughout codebase (Pydantic models)
- README with architecture overview and setup instructions

**Priority:** MEDIUM

---

### NFR-7: Scalability

**Requirement:** System must handle 10-20 watchlist wallets generating 50-400 signals per day.

**Rationale:** MVP target is 5-20 signals/day/wallet × 10 wallets = 50-200 signals/day. System must handle peak load.

**Acceptance Criteria:**
- Webhook processing handles burst of 10 signals within 30 seconds
- Database queries optimized for dashboard load (indexes on wallet_id, timestamp)
- Supabase free tier sufficient for MVP data volumes

**Priority:** MEDIUM

---

### NFR-8: Compliance Readiness (Future)

**Requirement:** System architecture must support future KYC/AML compliance if productized.

**Rationale:** If WallTrack becomes SaaS offering, fintech regulations will apply.

**Acceptance Criteria:**
- User data model extensible for KYC information
- Audit trail already captures required transaction data
- Architecture supports multi-tenancy (future)

**Priority:** LOW (Future consideration)

## Technical Requirements

### TR-1: Technology Stack

**Backend:**
- Python 3.11+ with type hints
- FastAPI for API endpoints
- Pydantic v2 for data validation
- httpx for async HTTP clients

**Data Layer:**
- Supabase (PostgreSQL) for application data (config, tokens, positions, wallets)
- SQL migrations in `src/walltrack/data/supabase/migrations/`

**Blockchain Integration:**
- Helius API for Solana webhooks (swap notifications, wallet monitoring)
- Jupiter API for decentralized swap execution (live mode)
- Solana Web3.py for wallet operations

**Price Data:**
- DexScreener API for real-time token price monitoring

**UI:**
- Gradio for rapid operator interface development
- Pages: Dashboard, Watchlist, Config

**Testing:**
- Pytest for unit + integration tests
- Playwright for E2E UI tests (separate from other tests)

---

### TR-2: Database Schema

**Tables Required (MVP):**

1. **config**: System configuration (capital, risk %, safety threshold)
2. **wallets**: Watchlist wallets (address, mode, exit_strategy_default)
3. **tokens**: Token metadata cache (address, safety_score, last_analyzed)
4. **signals**: Raw signals from Helius (wallet_id, token, timestamp, filtered_reason)
5. **positions**: Open/closed positions (wallet_id, token, entry_price, exit_price, pnl, mode)
6. **performance**: Aggregated wallet performance (wallet_id, win_rate, total_pnl, signal_counts)

**Migration Strategy:**
- All table creation via SQL migration files
- Migrations numbered sequentially (001_config_table.sql, 002_wallets_table.sql, etc.)
- Rollback scripts included as comments in each migration

---

### TR-3: External API Integration

**Helius API:**
- Webhook configuration for swap events
- Rate limits: TBD (check Helius free tier)
- Authentication: API key in environment variable

**Jupiter API:**
- Swap execution endpoint
- Quote endpoint for price estimation
- Rate limits: TBD (check Jupiter limits)
- Authentication: None required (public API)

**DexScreener API:**
- Token price endpoint
- Polling frequency: 30-60s per active position
- Rate limits: TBD (check DexScreener limits)
- Authentication: None required (public API)

---

### TR-4: Testing Strategy

**Unit Tests:**
- Test coverage for business logic (signal filtering, safety scoring, exit strategy logic)
- Mocked external APIs (Helius, Jupiter, DexScreener)
- Target: ≥ 70% coverage

**Integration Tests:**
- Test data layer (Supabase operations)
- Test API client integrations with mocked responses
- Test end-to-end pipelines (signal → position → exit) in simulation mode

**E2E Tests (Playwright):**
- UI workflows (add wallet, view dashboard, change config)
- Run separately from unit/integration tests (different test command)

**Testing Commands:**
```bash
# Unit + Integration (fast, ~40s)
uv run pytest tests/unit tests/integration -v

# E2E Playwright (separate, opens browser)
uv run pytest tests/e2e -v
```

---

### TR-5: Deployment & Operations

**Development:**
- Local development with Supabase local instance or cloud free tier
- Environment variables for API keys (.env file, never committed)

**Production:**
- Single server deployment (personal use, not multi-tenant)
- Process manager for auto-restart (systemd or supervisor)
- Logs to file with rotation (max 100MB, keep 7 days)

**Monitoring:**
- Health check endpoint (FastAPI /health)
- Circuit breaker status exposed via API
- Alert on prolonged downtime (email or Telegram bot - future)

---

### TR-6: Security Measures

**Wallet Security:**
- Private key in environment variable or encrypted file (never in code/database)
- No private key logging or UI exposure
- Use Solana Keypair library for secure key management

**API Security:**
- Helius/Jupiter API keys in environment variables
- Rate limiting on API endpoints (prevent abuse)
- Input validation on all wallet addresses (Solana address format check)

**Data Security:**
- Supabase RLS policies (if using cloud Supabase)
- Database connection over TLS
- No sensitive data in logs (mask wallet addresses in non-critical logs)

## Dependencies & Integrations

### External Dependencies

**Critical (System Cannot Function Without):**
- Helius API (webhooks for signal detection and wallet monitoring)
- Jupiter API (swap execution in live mode)
- DexScreener API (price monitoring for exit strategies)
- Supabase (data persistence)

**Optional (Enhances Functionality):**
- GMGN (manual wallet discovery - external tool, not integrated)

### Integration Points

**Helius Webhooks:**
- **Integration Type:** Event-driven webhooks
- **Data Flow:** Helius → WallTrack webhook endpoint → Signal processing pipeline
- **Error Handling:** Retry on transient failures, log webhook failures, alert if no signals for 48h
- **SLA Impact:** Webhook downtime = missed signals = missed trades

**Jupiter API:**
- **Integration Type:** REST API (synchronous swap execution)
- **Data Flow:** WallTrack → Jupiter quote API → Jupiter swap API → Transaction confirmation
- **Error Handling:** Retry on transient failures, abort on critical errors (insufficient funds, invalid token), log all failures
- **SLA Impact:** API downtime = cannot execute live trades (simulation mode unaffected)

**DexScreener API:**
- **Integration Type:** REST API (polling)
- **Data Flow:** WallTrack → DexScreener price endpoint → Price update → Exit strategy evaluation
- **Error Handling:** Retry on transient failures, use last known price if API unavailable, alert if stale data >5 minutes
- **SLA Impact:** API downtime = delayed exit triggers (stop-loss/trailing-stop may not execute on time)

**Supabase:**
- **Integration Type:** PostgreSQL database (client library)
- **Data Flow:** WallTrack → Supabase client → PostgreSQL
- **Error Handling:** Connection pooling, retry on transient failures, log database errors
- **SLA Impact:** Database downtime = system inoperable (no state persistence)

## Risks & Mitigations

### High Risk

**Risk 1: Helius Webhook Reliability**

**Description:** If Helius webhooks fail or deliver signals late, WallTrack misses trades or executes at worse prices.

**Impact:** HIGH - Core signal detection depends on webhook reliability

**Likelihood:** MEDIUM - Third-party API dependencies always carry risk

**Mitigation:**
- Monitor webhook status (last signal timestamp visible in UI)
- Circuit breaker triggers alert if no signals for 48 hours
- Consider backup signal source (direct Solana RPC polling) in V2
- Test webhook delivery during simulation phase before live trading

---

**Risk 2: Jupiter API Execution Failures**

**Description:** Jupiter swap execution fails due to slippage, insufficient liquidity, or API errors.

**Impact:** HIGH - Live trading depends on successful execution

**Likelihood:** MEDIUM - DEX liquidity varies by token

**Mitigation:**
- Implement retry logic with exponential backoff
- Set slippage tolerance appropriately (e.g., 2-5%)
- Log all execution failures with reason codes
- Fall back to simulation mode manually if persistent failures
- Monitor execution success rate in analytics

---

**Risk 3: Token Rug Pulls Despite Safety Checks**

**Description:** Token safety analysis fails to detect sophisticated rug pulls, leading to capital loss.

**Impact:** MEDIUM - Safety scoring reduces but doesn't eliminate risk

**Likelihood:** MEDIUM - Memecoin scams are sophisticated

**Mitigation:**
- Conservative safety threshold (0.60 default, adjustable)
- Stop-loss protection on all positions (-20% default)
- Manual review of safety scores for unfamiliar tokens
- Iterate safety model based on false negatives (V2 improvement)
- Start with small capital in live mode to limit downside

---

**Risk 4: Smart Money Wallet Performance Degradation**

**Description:** Previously profitable wallets become unprofitable (market conditions change, wallet strategy shifts).

**Impact:** MEDIUM - Watchlist quality affects overall profitability

**Likelihood:** HIGH - Wallet performance is dynamic

**Mitigation:**
- Performance tracking with win rate per wallet
- Automatic alerts for wallets dropping below 40% win rate
- Regular watchlist curation (weekly review recommended)
- Simulation mode for new wallets before live promotion
- Data-driven removal of underperforming wallets

### Medium Risk

**Risk 5: Price Monitoring Lag**

**Description:** DexScreener API polling delay causes stop-loss/trailing-stop triggers to execute late.

**Impact:** MEDIUM - Exit strategy effectiveness reduced

**Likelihood:** LOW-MEDIUM - API latency varies

**Mitigation:**
- 30-60s polling frequency (balance API load vs. responsiveness)
- Use last known price if API unavailable temporarily
- Alert if price data stale >5 minutes
- Consider WebSocket price feeds in V2 for real-time updates

---

**Risk 6: System Downtime During Critical Market Events**

**Description:** System crashes or restarts during high-volatility period, missing exit opportunities.

**Impact:** MEDIUM - Could result in missed exits or larger losses

**Likelihood:** LOW - Python/FastAPI reasonably stable

**Mitigation:**
- Auto-restart on crash (process manager)
- Health checks and monitoring
- Circuit breakers prevent cascade failures
- Graceful shutdown handling (close positions before restart if possible)

### Low Risk

**Risk 7: Supabase Free Tier Limits**

**Description:** MVP data volume exceeds Supabase free tier limits (storage, API calls).

**Impact:** LOW - Can upgrade to paid tier if needed

**Likelihood:** LOW - Free tier generous for personal use

**Mitigation:**
- Monitor Supabase usage dashboard
- Implement data retention policy (archive old signals/positions after 90 days)
- Upgrade to paid tier if approaching limits ($25/month acceptable)

---

**Risk 8: Regulatory Compliance (Future)**

**Description:** If productized, WallTrack may require KYC/AML compliance and financial licensing.

**Impact:** LOW (MVP is personal use only)

**Likelihood:** N/A for MVP, HIGH if productized

**Mitigation:**
- Architecture supports multi-tenancy and user data (future-proof)
- Audit trail already captures required transaction data
- Consult legal counsel before any productization
- Focus on personal use in MVP to avoid regulatory complexity

## Appendix

### Glossary

**Terms:**
- **Smart Money Wallet**: Wallet addresses belonging to insiders, developers, or early movers with proven edge in memecoin markets
- **Copy-Trading**: Automated mirroring of trades executed by another wallet
- **Rug Pull**: Scam where token creators drain liquidity, leaving holders with worthless tokens
- **Honeypot**: Malicious token contract that allows buying but prevents selling
- **Memecoin**: Highly speculative cryptocurrency with no fundamental value, driven by hype and social sentiment
- **Simulation Mode**: Full trade pipeline execution without real capital (paper trading)
- **Live Mode**: Real trade execution with actual capital via Jupiter DEX
- **Mirror-Exit**: Exit strategy that sells when the source wallet sells
- **Scaling-Out**: Taking partial profits at predefined price levels
- **Trailing-Stop**: Dynamic stop-loss that follows price upward, protecting profits
- **Circuit Breaker**: Automated trading halt triggered by loss thresholds or anomalies

**Acronyms:**
- **DEX**: Decentralized Exchange
- **DeFi**: Decentralized Finance
- **PnL**: Profit and Loss
- **MVP**: Minimum Viable Product
- **KYC**: Know Your Customer
- **AML**: Anti-Money Laundering
- **RPC**: Remote Procedure Call

### References

**Product Brief:**
- Source: `docs/product-brief.md`
- Date: 2026-01-04
- Used for: Product vision, user journeys, success criteria, MVP scope

**Technical Documentation:**
- Helius API Docs: https://docs.helius.dev/
- Jupiter API Docs: https://docs.jup.ag/
- DexScreener API Docs: https://docs.dexscreener.com/
- Solana Web3.py Docs: https://solana-py.readthedocs.io/

**Tools & Platforms:**
- GMGN: https://gmgn.ai/ (wallet discovery)
- Supabase: https://supabase.com/docs
- Gradio: https://www.gradio.app/docs

### Document Control

**Version History:**
- v1.0 - 2026-01-04 - Initial PRD created via BMad Method workflow

**Approvals:**
- Product Manager: Christophe (self-approval for personal project)
- Technical Lead: Christophe
- Stakeholder: Christophe (solo operator)

**Next Steps:**
1. Review and refine PRD
2. Create UX Design (if UI refinement needed beyond Gradio defaults)
3. Create Architecture document
4. Create Epics & Stories
5. Implementation Readiness validation
6. Sprint Planning → Development
