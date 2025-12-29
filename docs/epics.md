---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
inputDocuments:
  - 'docs/prd.md'
  - 'docs/architecture.md'
  - 'docs/ux-design-specification.md'
project_name: 'walltrack'
---

# WallTrack - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for WallTrack, decomposing the requirements from the PRD, UX Design, and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Token Discovery & Surveillance (3 FRs)**

- FR1: System can discover tokens from configured sources (manual trigger)
- FR2: System can refresh token data on a configurable schedule
- FR3: Operator can view discovered tokens in the dashboard

**Wallet Intelligence (6 FRs)**

- FR4: System can discover wallets from token transaction history
- FR5: System can analyze wallet historical performance (win rate, PnL, timing percentile)
- FR6: System can profile wallet behavioral patterns (activity hours, position sizing style)
- FR7: System can detect wallet performance decay using rolling window analysis
- FR8: System can flag wallets for review when performance drops below threshold
- FR9: Operator can manually blacklist specific wallets

**Cluster Analysis (6 FRs)**

- FR10: System can map wallet funding relationships (FUNDED_BY connections)
- FR11: System can detect synchronized buying patterns (SYNCED_BUY within 5 min)
- FR12: System can identify wallets appearing together on multiple early tokens
- FR13: System can group related wallets into clusters
- FR14: System can identify cluster leaders (wallets that initiate movements)
- FR15: System can amplify signal score when multiple cluster wallets move together

**Signal Processing (6 FRs)**

- FR16: System can receive real-time swap notifications via Helius webhooks
- FR17: System can filter notifications to only monitored wallet addresses
- FR18: System can calculate multi-factor signal score (wallet, cluster, token, context)
- FR19: System can apply scoring threshold to determine trade eligibility
- FR20: System can query token characteristics (age, market cap, liquidity)
- FR21: System can log all signals regardless of score for analysis

**Position & Order Management (7 FRs)**

- FR22: System can create positions from high-score signals
- FR23: System can apply dynamic position sizing based on signal score
- FR24: System can create entry orders with risk-based sizing
- FR25: System can create exit orders per configured strategy
- FR26: System can track all positions and orders with current status
- FR27: System can execute orders in live mode via Jupiter API
- FR28: System can skip execution in simulation mode (paper trading)

**Risk Management (4 FRs)**

- FR29: System can pause all trading when drawdown exceeds threshold (20%)
- FR30: System can reduce position size after consecutive losses
- FR31: System can enforce maximum concurrent position limits
- FR32: Operator can manually pause and resume trading

**Operator Dashboard (9 FRs)**

- FR33: Operator can configure risk parameters (capital allocation, position size, thresholds)
- FR34: Operator can view system status (running, paused, health indicators)
- FR35: Operator can view active positions and pending orders
- FR36: Operator can view performance metrics (PnL, win rate, trade count)
- FR37: Operator can view trade history with full details
- FR38: Operator can receive alerts for circuit breakers and system issues
- FR39: Operator can manage watchlist (add/remove wallets manually)
- FR40: Operator can view wallet and cluster analysis details
- FR41: Operator can switch between simulation and live mode

**Trading Wallet Management (3 FRs)**

- FR42: Operator can connect trading wallet to the system
- FR43: Operator can view trading wallet balance (SOL and tokens)
- FR44: System can validate wallet connectivity before trading

**Total: 44 Functional Requirements**

### Non-Functional Requirements

**Performance**

- NFR1: Signal-to-Trade Latency < 5 seconds
- NFR2: Webhook Processing < 500ms
- NFR3: Dashboard Response < 2 seconds
- NFR4: Database Queries < 100ms
- NFR5: Handle 10+ concurrent signals simultaneously

**Security**

- NFR6: Private Key Storage via environment variables only (never in code)
- NFR7: API Key Management with secure storage and rotation capability
- NFR8: Webhook Validation via HMAC signature verification for all Helius webhooks
- NFR9: Dashboard Access restricted to local network or authenticated
- NFR10: No sensitive data in logs (redact private keys, signatures)

**Reliability**

- NFR11: System Uptime ≥ 95%
- NFR12: Webhook Availability 24/7
- NFR13: Data Persistence with zero data loss
- NFR14: Error Recovery with auto-retry failed trades

**Scalability**

- NFR15: Watchlist Size supports 1,000+ monitored wallets
- NFR16: Trade History stores 1 year of trade data
- NFR17: Signal Log stores 6 months of all signals

**Total: 17 Non-Functional Requirements**

### Additional Requirements

**From Architecture Document:**

- AR1: Async Pipeline - All components must be non-blocking (httpx, async Neo4j driver)
- AR2: Error Handling - Custom WallTrackError hierarchy with specific exceptions per domain
- AR3: Retry Strategy - tenacity for external API calls (3 retries, exponential backoff 1s, 2s, 4s)
- AR4: Circuit Breaker - 5 failures → 30s cooldown for external services
- AR5: Logging - structlog JSON output with bound context (wallet_id, signal_score, trade_id)
- AR6: Configuration - Static (pydantic-settings/.env) + Dynamic (Supabase config table)
- AR7: API Abstraction - BaseAPIClient with retry and circuit breaker for all services
- AR8: Import Rules - Absolute imports only (`from walltrack.core.scoring import ...`)
- AR9: Layer Boundaries - api → core → data/services (never bypass)
- AR10: services/ contains ONLY 4 external API clients (Helius, Jupiter, DexScreener, Solana RPC)
- AR11: Starter Template - Custom layered Python structure (not a starter, build from scratch)
- AR12: Naming Conventions - snake_case (Python), PascalCase (Neo4j labels), UPPER_SNAKE (Neo4j relationships)
- AR13: Validation Step-by-Step - Each feature validated (UI + E2E test) before next

**From UX Design Document:**

- UX1: 3-page architecture - Home (synthesis), Explorer (navigation), Config (parameters)
- UX2: Status Bar - Auto-refresh every 30 seconds showing discovery/signals/webhooks status
- UX3: Contextual Sidebar - Right side, 380px, opens on row click with drill-down context
- UX4: Decay Status Visualization - 🟢 OK / 🟡 Flagged / 🔴 Downgraded / ⚪ Dormant
- UX5: Drill-down Interactions - Click any table row → sidebar opens with full context
- UX6: gr.Navbar for 3-page navigation
- UX7: Gradio theme: gr.themes.Soft()
- UX8: CSS Design Tokens defined for status colors, decay badges, typography

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 2 | Token discovery |
| FR2 | Epic 2 | Token surveillance |
| FR3 | Epic 2 | View tokens in dashboard |
| FR4 | Epic 3 | Wallet discovery |
| FR5 | Epic 3 | Wallet performance analysis |
| FR6 | Epic 3 | Wallet behavioral profiling |
| FR7 | Epic 3 | Decay detection |
| FR8 | Epic 3 | Flag wallets for review |
| FR9 | Epic 3 | Manual blacklist |
| FR10 | Epic 4 | FUNDED_BY relationships |
| FR11 | Epic 4 | SYNCED_BUY detection |
| FR12 | Epic 4 | Co-appearance detection |
| FR13 | Epic 4 | Cluster grouping |
| FR14 | Epic 4 | Leader identification |
| FR15 | Epic 4 | Score amplification |
| FR16 | Epic 5 | Webhook reception |
| FR17 | Epic 5 | Wallet filtering |
| FR18 | Epic 5 | Multi-factor scoring |
| FR19 | Epic 5 | Threshold application |
| FR20 | Epic 5 | Token characteristics |
| FR21 | Epic 5 | Signal logging |
| FR22 | Epic 6 | Position creation |
| FR23 | Epic 6 | Dynamic sizing |
| FR24 | Epic 6 | Entry orders |
| FR25 | Epic 6 | Exit orders |
| FR26 | Epic 6 | Status tracking |
| FR27 | Epic 8 | Live execution |
| FR28 | Epic 6 | Simulation mode |
| FR29 | Epic 7 | Drawdown pause |
| FR30 | Epic 7 | Size reduction |
| FR31 | Epic 7 | Position limits |
| FR32 | Epic 7 | Manual pause/resume |
| FR33 | Epic 7 | Risk config |
| FR34 | Epic 1 | System status |
| FR35 | Epic 6 | View positions |
| FR36 | Epic 8 | Performance metrics |
| FR37 | Epic 8 | Trade history |
| FR38 | Epic 7 | Alerts |
| FR39 | Epic 3 | Watchlist management |
| FR40 | Epic 4 | Cluster details |
| FR41 | Epic 8 | Mode switch |
| FR42 | Epic 1 | Wallet connection |
| FR43 | Epic 1 | Wallet balance |
| FR44 | Epic 1 | Wallet validation |

## Epic List

### Epic 1: Foundation & Core Infrastructure

**User Outcome:** Operator can launch the app, see system status, connect trading wallet, and configure basic settings.

**FRs covered:** FR34, FR42, FR43, FR44

**Additional Requirements:** AR1-AR13 (async pipeline, exceptions, config, logging, API clients, layer boundaries)

#### Story 1.1: Project Structure & Configuration

As an operator,
I want to launch the application with proper configuration,
So that I can start using WallTrack with my API keys and settings.

**Acceptance Criteria:**

**Given** the project structure is created per Architecture spec
**When** I set environment variables (.env file)
**Then** pydantic-settings loads configuration correctly
**And** the app can access SUPABASE_URL, NEO4J_URI, HELIUS_API_KEY

**Given** invalid or missing required config
**When** the app starts
**Then** it fails fast with clear error message indicating which config is missing

#### Story 1.2: Database Connections

As an operator,
I want the system to connect to Supabase and Neo4j,
So that data persistence is available for all features.

**Acceptance Criteria:**

**Given** valid Supabase credentials
**When** the app initializes
**Then** async Supabase client connects successfully
**And** a health check query returns OK

**Given** valid Neo4j credentials
**When** the app initializes
**Then** async Neo4j driver connects successfully
**And** a simple Cypher query executes without error

**Given** connection failure
**When** any database is unreachable
**Then** appropriate WallTrackError is raised with context

#### Story 1.3: Base API Client & Exception Hierarchy

As a developer,
I want a BaseAPIClient with retry and circuit breaker,
So that all external API calls are resilient.

**Acceptance Criteria:**

**Given** BaseAPIClient with tenacity retry
**When** an external API call fails transiently
**Then** it retries 3 times with exponential backoff (1s, 2s, 4s)
**And** logs each retry attempt via structlog

**Given** 5 consecutive failures
**When** circuit breaker threshold is reached
**Then** circuit opens for 30 seconds
**And** subsequent calls fail fast without hitting the API

**Given** WallTrackError exception hierarchy
**When** any domain error occurs
**Then** specific exception type is raised (ConfigError, DatabaseError, APIError, etc.)

#### Story 1.4: Gradio Base App & Status Bar

As an operator,
I want to see the application running with a status bar,
So that I know the system is alive at a glance.

**Acceptance Criteria:**

**Given** Gradio app with gr.themes.Soft()
**When** I open the dashboard
**Then** I see gr.Navbar with 3 pages (Home, Explorer, Config)
**And** status bar shows system status with auto-refresh (every 30s)

**Given** all services connected
**When** status bar renders
**Then** it shows "🟢 System: OK" with relative timestamps
**And** displays basic counts (0 wallets, 0 signals initially)

#### Story 1.5: Trading Wallet Connection

As an operator,
I want to connect my trading wallet to the system,
So that the system can execute trades on my behalf.

**Acceptance Criteria:**

**Given** Config page with wallet connection section
**When** I enter my wallet address
**Then** the system validates the address format (Solana base58)
**And** stores it in configuration

**Given** a connected wallet
**When** I view the Config page
**Then** I see the wallet address (truncated) and connection status
**And** can view balance placeholder (SOL: 0.00)

**Given** the system validates wallet connectivity
**When** wallet is reachable via Solana RPC
**Then** status shows "🟢 Wallet: Connected"
**And** FR42, FR43, FR44 are satisfied

#### Story 1.6: Integration & E2E Validation

As a developer,
I want Epic 1 deployed and tested end-to-end,
So that I can validate the foundation before building on it.

**Acceptance Criteria:**

**Given** Docker Compose configuration
**When** I run `docker compose up`
**Then** all services start (app, Neo4j, Supabase)
**And** health checks pass for all containers

**Given** Playwright E2E test suite for Epic 1
**When** tests run against the deployed app
**Then** configuration loading is validated
**And** database connections are tested
**And** Gradio base app renders with status bar
**And** wallet connection flow works end-to-end

**Given** CI pipeline integration
**When** code is pushed
**Then** Docker build succeeds
**And** E2E tests pass automatically

---

### Epic 2: Token Discovery & Surveillance

**User Outcome:** Operator can trigger token discovery and see tokens auto-refreshing in the dashboard.

**FRs covered:** FR1, FR2, FR3

#### Story 2.1: Token Discovery Trigger

As an operator,
I want to trigger token discovery manually,
So that I can find new tokens from configured sources.

**Acceptance Criteria:**

**Given** Config page with Discovery section
**When** I click "Run Discovery" button
**Then** the system fetches tokens from DexScreener API
**And** discovery status shows "Running..." then "Complete"

**Given** discovery completes successfully
**When** tokens are found
**Then** they are stored in Supabase tokens table
**And** status bar updates with token count

**Given** discovery finds no new tokens
**When** the process completes
**Then** a message indicates "No new tokens found"

#### Story 2.2: Token Surveillance Scheduler

As an operator,
I want tokens to refresh automatically on a schedule,
So that I always have up-to-date token data.

**Acceptance Criteria:**

**Given** APScheduler is configured
**When** surveillance interval is set (default: 4 hours)
**Then** tokens are refreshed automatically at each interval
**And** last_checked timestamp is updated

**Given** Config page with Discovery section
**When** I view the schedule settings
**Then** I see next scheduled run time
**And** can modify the interval (1h, 2h, 4h, 8h options)

**Given** status bar
**When** surveillance runs
**Then** it shows "🟢 Discovery: Xh ago (next: Yh)"

#### Story 2.3: Token Explorer View

As an operator,
I want to view discovered tokens in the Explorer,
So that I can see what tokens the system is tracking.

**Acceptance Criteria:**

**Given** Explorer page with Tokens tab
**When** I navigate to Explorer → Tokens
**Then** I see a table with columns: Token, Symbol, Price, Market Cap, Age, Wallets

**Given** tokens exist in database
**When** the table loads
**Then** tokens are sorted by discovery date (newest first)
**And** each row is clickable for future drill-down

**Given** no tokens discovered yet
**When** I view the Tokens tab
**Then** I see empty state: "No tokens discovered. Run discovery from Config."

#### Story 2.4: Integration & E2E Validation

As a developer,
I want Epic 2 deployed and tested end-to-end,
So that I can validate token discovery before building wallet features.

**Acceptance Criteria:**

**Given** Docker environment updated with Epic 2 features
**When** I run `docker compose up`
**Then** DexScreener service client is available
**And** APScheduler is running for surveillance

**Given** Playwright E2E test suite for Epic 2
**When** tests run against the deployed app
**Then** manual discovery trigger creates tokens
**And** tokens appear in Explorer → Tokens table
**And** scheduler status is visible in Config
**And** status bar shows token count

**Given** mock DexScreener responses
**When** E2E tests run
**Then** tests are deterministic and fast
**And** real API is not called during CI

---

### Epic 3: Wallet Discovery & Profiling

**User Outcome:** Operator can see wallets extracted from tokens with profiles, decay status, and blacklist capability.

**FRs covered:** FR4, FR5, FR6, FR7, FR8, FR9, FR39

#### Story 3.1: Wallet Discovery from Tokens

As an operator,
I want wallets to be discovered from token transactions,
So that I can track smart money wallets.

**Acceptance Criteria:**

**Given** a discovered token
**When** wallet discovery runs (via Helius transaction history)
**Then** top buyers/sellers are extracted
**And** wallets are stored in Supabase wallets table + Neo4j Wallet nodes

**Given** wallet discovery completes
**When** new wallets are found
**Then** status bar updates wallet count
**And** wallets appear in Explorer → Wallets tab

#### Story 3.2: Wallet Performance Analysis

As an operator,
I want to see wallet performance metrics,
So that I can understand which wallets have edge.

**Acceptance Criteria:**

**Given** a wallet with transaction history
**When** profiling runs
**Then** win_rate is calculated (profitable trades / total trades)
**And** pnl_total is calculated (sum of trade profits/losses)
**And** timing_percentile is calculated (how early they enter)

**Given** wallet metrics are calculated
**When** I view a wallet in Explorer
**Then** I see Score, Win Rate, PnL columns
**And** can click for detailed breakdown in sidebar

#### Story 3.3: Wallet Behavioral Profiling

As an operator,
I want to see wallet behavioral patterns,
So that I can understand trading style.

**Acceptance Criteria:**

**Given** a wallet with sufficient history
**When** behavioral profiling runs
**Then** activity_hours pattern is identified (when they trade)
**And** position_size_style is classified (small/medium/large)
**And** hold_duration_avg is calculated

**Given** sidebar drill-down on a wallet
**When** I click a wallet row
**Then** I see behavioral profile section
**And** patterns are displayed clearly

#### Story 3.4: Wallet Decay Detection

As an operator,
I want to detect when wallets lose their edge,
So that I don't follow degraded wallets.

**Acceptance Criteria:**

**Given** decay detection with rolling 20-trade window
**When** win_rate drops below 40%
**Then** wallet decay_status changes to "flagged"
**And** badge shows 🟡 in Wallets table

**Given** 3 consecutive losses on a wallet
**When** the third loss is recorded
**Then** wallet decay_status changes to "downgraded"
**And** badge shows 🔴 in Wallets table

**Given** no activity for 30+ days
**When** decay check runs
**Then** wallet decay_status changes to "dormant"
**And** badge shows ⚪ in Wallets table

**Given** wallet is performing well
**When** decay check runs
**Then** decay_status remains "ok"
**And** badge shows 🟢 in Wallets table

#### Story 3.5: Wallet Blacklist & Watchlist Management

As an operator,
I want to blacklist wallets and manage my watchlist,
So that I control which wallets generate signals.

**Acceptance Criteria:**

**Given** a wallet in Explorer
**When** I click "Blacklist" in sidebar
**Then** wallet is_blacklisted flag is set to true
**And** wallet no longer generates signals

**Given** Config page with Watchlist section
**When** I view the watchlist
**Then** I see all tracked wallets with status
**And** can add/remove wallets manually by address

**Given** a blacklisted wallet
**When** I view it in Explorer
**Then** it shows "Blacklisted" badge
**And** I can click "Remove from Blacklist" to restore

#### Story 3.6: Integration & E2E Validation

As a developer,
I want Epic 3 deployed and tested end-to-end,
So that I can validate wallet profiling before building cluster analysis.

**Acceptance Criteria:**

**Given** Docker environment updated with Epic 3 features
**When** I run `docker compose up`
**Then** Helius client is available for transaction history
**And** Neo4j Wallet nodes can be created

**Given** Playwright E2E test suite for Epic 3
**When** tests run against the deployed app
**Then** wallet discovery extracts wallets from tokens
**And** wallet profiles show metrics in Explorer
**And** decay status badges display correctly (🟢🟡🔴⚪)
**And** blacklist/watchlist management works

**Given** test fixtures with wallet data
**When** E2E tests run
**Then** profiling calculations are validated
**And** sidebar drill-down renders correctly

---

### Epic 4: Cluster Analysis

**User Outcome:** Operator can see wallet relationships, clusters, and leaders in Neo4j visualization.

**FRs covered:** FR10, FR11, FR12, FR13, FR14, FR15, FR40

#### Story 4.1: Wallet Funding Relationships

As an operator,
I want to see wallet funding relationships,
So that I can identify connected wallets.

**Acceptance Criteria:**

**Given** wallet transaction history
**When** funding analysis runs
**Then** FUNDED_BY edges are created in Neo4j
**And** relationships show source → destination with amount

**Given** a wallet with funding relationships
**When** I view it in sidebar
**Then** I see "Funded by" section with linked wallets
**And** can click to navigate to funding wallet

#### Story 4.2: Synchronized Buying Detection

As an operator,
I want to detect wallets buying together,
So that I can identify coordinated groups.

**Acceptance Criteria:**

**Given** multiple wallets buying same token
**When** purchases occur within 5 minutes of each other
**Then** SYNCED_BUY edges are created in Neo4j
**And** sync count is tracked per wallet pair

**Given** wallets with sync patterns
**When** I view cluster analysis
**Then** synchronized pairs are highlighted
**And** frequency of syncs is displayed

#### Story 4.3: Co-appearance Detection

As an operator,
I want to identify wallets appearing together on early tokens,
So that I can spot insider groups.

**Acceptance Criteria:**

**Given** wallet transaction history across tokens
**When** co-appearance analysis runs
**Then** wallets appearing together on 3+ early tokens are flagged
**And** co-appearance score is calculated

**Given** wallets with high co-appearance
**When** I view them in Explorer
**Then** they show "Frequent co-buyer" indicator
**And** relationship strength is visible

#### Story 4.4: Cluster Grouping & Leaders

As an operator,
I want wallets grouped into clusters with leaders identified,
So that I can follow the most influential wallets.

**Acceptance Criteria:**

**Given** wallets with relationships (FUNDED_BY, SYNCED_BUY)
**When** cluster detection runs
**Then** related wallets are grouped into clusters
**And** cluster_id is assigned to each wallet

**Given** a cluster
**When** leader detection runs
**Then** wallet that initiates most movements is marked as leader
**And** leader badge appears in Explorer

**Given** Explorer → Clusters tab
**When** I view clusters
**Then** I see table with: Cluster ID, Leader, Member Count, Avg Score
**And** can click to see all members

#### Story 4.5: Cluster Drill-down & Score Amplification

As an operator,
I want to see cluster details and understand score amplification,
So that I know why certain signals are stronger.

**Acceptance Criteria:**

**Given** a cluster in Explorer
**When** I click on it
**Then** sidebar shows all member wallets
**And** displays cluster statistics (total PnL, avg win rate)

**Given** cluster score amplification logic
**When** multiple cluster wallets move on same token
**Then** signal score is amplified per FR15
**And** amplification factor is visible in signal details

**Given** sidebar cluster view
**When** I see the cluster
**Then** I understand relationships visually
**And** can navigate to any member wallet

#### Story 4.6: Integration & E2E Validation

As a developer,
I want Epic 4 deployed and tested end-to-end,
So that I can validate cluster analysis before building signal pipeline.

**Acceptance Criteria:**

**Given** Docker environment updated with Epic 4 features
**When** I run `docker compose up`
**Then** Neo4j graph queries execute correctly
**And** cluster detection algorithms run

**Given** Playwright E2E test suite for Epic 4
**When** tests run against the deployed app
**Then** FUNDED_BY relationships appear in wallet details
**And** SYNCED_BUY patterns are detected
**And** clusters display in Explorer → Clusters tab
**And** leaders are identified and marked

**Given** Neo4j test fixtures with relationship data
**When** E2E tests run
**Then** cluster grouping is validated
**And** score amplification logic is correct

---

### Epic 5: Signal Pipeline

**User Outcome:** Operator can receive real-time webhook signals and see multi-factor scores.

**FRs covered:** FR16, FR17, FR18, FR19, FR20, FR21

#### Story 5.1: Helius Webhook Reception

As an operator,
I want to receive real-time swap notifications,
So that I know when tracked wallets trade.

**Acceptance Criteria:**

**Given** FastAPI webhook endpoint at /api/webhooks/helius
**When** Helius sends a swap notification
**Then** the webhook is received and validated via HMAC signature
**And** raw payload is logged for debugging

**Given** invalid HMAC signature
**When** webhook is received
**Then** request is rejected with 401
**And** security event is logged

**Given** valid webhook
**When** swap data is parsed
**Then** wallet_address, token_address, amount, direction are extracted
**And** signal processing pipeline is triggered

#### Story 5.2: Wallet Filtering

As an operator,
I want signals filtered to only monitored wallets,
So that I don't process noise from unknown wallets.

**Acceptance Criteria:**

**Given** incoming webhook signal
**When** wallet_address is checked against watchlist
**Then** only monitored wallets proceed to scoring
**And** non-monitored wallets are silently discarded

**Given** a monitored wallet that is blacklisted
**When** signal is received
**Then** it is filtered out
**And** logged as "blacklisted wallet signal ignored"

#### Story 5.3: Multi-Factor Signal Scoring

As an operator,
I want signals scored using multiple factors,
So that I can identify high-quality opportunities.

**Acceptance Criteria:**

**Given** a signal from monitored wallet
**When** scoring runs
**Then** wallet_score contributes 35% (win rate, PnL, consistency)
**And** cluster_score contributes 25% (cluster confirmation count)
**And** token_score contributes 25% (liquidity, age, holder distribution)
**And** context_score contributes 15% (timing, market conditions)

**Given** scoring completes
**When** final score is calculated
**Then** score is between 0.0 and 1.0
**And** score breakdown is stored with signal

#### Story 5.4: Threshold Application & Token Characteristics

As an operator,
I want scoring threshold applied to determine trade eligibility,
So that only high-confidence signals create positions.

**Acceptance Criteria:**

**Given** score threshold configured (default: 0.70)
**When** signal score >= threshold
**Then** signal is marked as "actionable"
**And** position creation is triggered

**Given** signal score < threshold
**When** scoring completes
**Then** signal is marked as "below_threshold"
**And** no position is created

**Given** token characteristics needed for scoring
**When** token_score is calculated
**Then** DexScreener API is queried for age, market_cap, liquidity
**And** characteristics are cached for performance

#### Story 5.5: Signal Logging & Explorer View

As an operator,
I want all signals logged and viewable,
So that I can analyze system behavior.

**Acceptance Criteria:**

**Given** any signal received
**When** processing completes
**Then** signal is stored in Supabase signals table
**And** includes: wallet, token, score, breakdown, timestamp, status

**Given** Explorer → Signals tab
**When** I view signals
**Then** I see table with: Time, Wallet, Token, Score, Status
**And** can filter by score range, date, wallet

**Given** Home page
**When** signals arrive
**Then** "Recent Signals" feed shows last 5 signals
**And** new signals appear in real-time (or on refresh)

#### Story 5.6: Integration & E2E Validation

As a developer,
I want Epic 5 deployed and tested end-to-end,
So that I can validate signal pipeline before building position management.

**Acceptance Criteria:**

**Given** Docker environment updated with Epic 5 features
**When** I run `docker compose up`
**Then** webhook endpoint is exposed (/api/webhooks/helius)
**And** scoring engine is initialized

**Given** Playwright E2E test suite for Epic 5
**When** tests run against the deployed app
**Then** mock webhook payloads are processed correctly
**And** HMAC validation accepts valid signatures
**And** signals appear in Explorer → Signals tab
**And** score breakdown is visible in sidebar

**Given** mock Helius webhook payloads
**When** E2E tests run
**Then** wallet filtering works correctly
**And** scoring weights are applied as configured
**And** threshold logic triggers position creation correctly

---

### Epic 6: Position & Order Management

**User Outcome:** Operator can see positions and orders created from signals, execute in simulation mode.

**FRs covered:** FR22, FR23, FR24, FR25, FR26, FR28, FR35

#### Story 6.1: Position Creation from Signals

As an operator,
I want positions created automatically from high-score signals,
So that trading opportunities are captured.

**Acceptance Criteria:**

**Given** an actionable signal (score >= threshold)
**When** position creation is triggered
**Then** a new position is created in Supabase positions table
**And** position includes: signal_id, token, wallet_source, entry_price, size, status

**Given** position is created
**When** I view Home page
**Then** position appears in Active Positions table
**And** shows Token, Entry, Current, P&L%, Wallet columns

#### Story 6.2: Dynamic Position Sizing

As an operator,
I want position size adjusted based on signal score,
So that higher conviction trades get more capital.

**Acceptance Criteria:**

**Given** signal score >= 0.85 (high conviction)
**When** position size is calculated
**Then** size = base_size * 1.5x multiplier
**And** sizing reason is logged

**Given** signal score between 0.70 and 0.84
**When** position size is calculated
**Then** size = base_size * 1.0x (standard)

**Given** base_size configured in Config
**When** sizing runs
**Then** it respects max position size limits
**And** never exceeds configured risk percentage

#### Story 6.3: Entry Order Creation

As an operator,
I want entry orders created with risk-based sizing,
So that positions are properly capitalized.

**Acceptance Criteria:**

**Given** a new position
**When** entry order is created
**Then** order includes: position_id, type="entry", amount, price, status
**And** order is stored in Supabase orders table

**Given** risk parameters configured
**When** entry order size is calculated
**Then** it respects risk_per_trade percentage
**And** total exposure stays within limits

**Given** entry order created
**When** I view position in sidebar
**Then** I see entry order details
**And** order status (pending/filled/failed)

#### Story 6.4: Exit Order Strategy

As an operator,
I want exit orders created per configured strategy,
So that profits are taken systematically.

**Acceptance Criteria:**

**Given** moonbag exit strategy configured
**When** position is opened
**Then** exit orders are planned: 50% at 2x, 25% at 3x, keep 25% moonbag

**Given** position reaches exit target
**When** price hits 2x entry
**Then** 50% exit order is marked for execution
**And** position.exited_amount is updated

**Given** trailing stop configured
**When** price moves favorably
**Then** stop price trails behind
**And** protects gains dynamically

#### Story 6.5: Position & Order Tracking

As an operator,
I want to track all positions and orders with current status,
So that I know my exposure at all times.

**Acceptance Criteria:**

**Given** active positions exist
**When** I view Home → Active Positions
**Then** I see real-time P&L for each position
**And** total exposure summary

**Given** position status changes
**When** fills/exits occur
**Then** status updates: open → partial_exit → closed
**And** timestamps are recorded

**Given** sidebar drill-down on position
**When** I click a position row
**Then** I see full context: signal source, wallet, score breakdown
**And** all related orders with their status

#### Story 6.6: Simulation Mode

As an operator,
I want simulation mode to skip real execution,
So that I can validate the system without risking capital.

**Acceptance Criteria:**

**Given** system in Simulation mode
**When** orders are created
**Then** they are marked as "simulated"
**And** no Jupiter API calls are made

**Given** simulated order
**When** it would be filled (price target hit)
**Then** order status updates to "sim_filled"
**And** P&L is calculated as if real

**Given** Home page in Simulation mode
**When** status bar renders
**Then** it shows "🔵 SIMULATION MODE" prominently
**And** all positions show simulated status

#### Story 6.7: Integration & E2E Validation

As a developer,
I want Epic 6 deployed and tested end-to-end,
So that I can validate position management before building risk controls.

**Acceptance Criteria:**

**Given** Docker environment updated with Epic 6 features
**When** I run `docker compose up`
**Then** position and order tables are created
**And** simulation mode is active by default

**Given** Playwright E2E test suite for Epic 6
**When** tests run against the deployed app
**Then** positions are created from high-score signals
**And** dynamic sizing applies correct multipliers
**And** entry/exit orders appear in sidebar
**And** simulation mode skips real execution

**Given** full signal-to-position flow test
**When** mock webhook triggers position creation
**Then** position appears in Home → Active Positions
**And** P&L updates correctly (simulated)
**And** exit orders are planned per strategy

---

### Epic 7: Risk Management & Circuit Breakers

**User Outcome:** Operator can configure and observe circuit breakers protecting capital.

**FRs covered:** FR29, FR30, FR31, FR32, FR33, FR38

#### Story 7.1: Drawdown Circuit Breaker

As an operator,
I want trading paused when drawdown exceeds threshold,
So that my capital is protected during bad streaks.

**Acceptance Criteria:**

**Given** drawdown threshold configured (default: 20%)
**When** current drawdown from peak exceeds threshold
**Then** all trading is paused automatically
**And** circuit_breaker status changes to "triggered"

**Given** circuit breaker triggered
**When** I view Home page
**Then** alert shows "⚠️ Circuit Breaker: Drawdown limit reached"
**And** status bar shows "🔴 Trading Paused"

**Given** DrawdownCircuitBreaker implementation
**When** peak equity is tracked
**Then** drawdown is calculated as (peak - current) / peak * 100
**And** state is persisted in Supabase for recovery

#### Story 7.2: Consecutive Loss Protection

As an operator,
I want position size reduced after consecutive losses,
So that losing streaks don't compound.

**Acceptance Criteria:**

**Given** 3 consecutive max-loss trades
**When** the third loss is recorded
**Then** position size multiplier reduces to 0.5x (50%)
**And** alert shows "Position sizing reduced due to consecutive losses"

**Given** reduced sizing is active
**When** a winning trade occurs
**Then** consecutive loss counter resets
**And** sizing gradually returns to normal

**Given** Config → Risk section
**When** I view consecutive loss settings
**Then** I see current streak count
**And** can adjust the threshold (default: 3)

#### Story 7.3: Position Limits

As an operator,
I want maximum concurrent position limits enforced,
So that I don't over-expose my capital.

**Acceptance Criteria:**

**Given** max_concurrent_positions configured (default: 5)
**When** a new position would be created
**Then** system checks current open position count
**And** rejects new position if limit is reached

**Given** position limit reached
**When** actionable signal arrives
**Then** signal is logged as "position_limit_reached"
**And** no position is created

**Given** Config → Risk section
**When** I view position limits
**Then** I see current count vs maximum
**And** can adjust the limit

#### Story 7.4: Manual Pause & Resume

As an operator,
I want to manually pause and resume trading,
So that I can intervene when needed.

**Acceptance Criteria:**

**Given** Config → Risk section
**When** I click "Pause Trading" button
**Then** all trading stops immediately
**And** status shows "⏸️ Trading Paused (Manual)"

**Given** trading is paused
**When** I click "Resume Trading" button
**Then** trading resumes
**And** status shows normal operation

**Given** circuit breaker was triggered
**When** I review and click "Reset Circuit Breaker"
**Then** circuit breaker resets to normal state
**And** trading can resume (if not manually paused)

#### Story 7.5: Risk Configuration

As an operator,
I want to configure all risk parameters,
So that I can tune the system to my risk tolerance.

**Acceptance Criteria:**

**Given** Config → Risk section
**When** I view risk settings
**Then** I see all configurable parameters:
- Capital allocation (SOL)
- Risk per trade (%)
- Drawdown threshold (%)
- Max concurrent positions
- Consecutive loss threshold

**Given** I change a risk parameter
**When** I click "Save"
**Then** parameter is updated in Supabase config table
**And** takes effect immediately (no restart needed)

**Given** invalid parameter value
**When** I try to save
**Then** validation error is shown
**And** invalid value is rejected

#### Story 7.6: Risk Alerts & Notifications

As an operator,
I want alerts for circuit breakers and risk events,
So that I'm aware of critical situations.

**Acceptance Criteria:**

**Given** circuit breaker triggers
**When** drawdown or loss threshold is hit
**Then** alert appears in Home → Alerts section
**And** includes timestamp, trigger reason, action taken

**Given** alert is displayed
**When** I click on it
**Then** sidebar shows full details
**And** suggested actions (reset, review, adjust)

**Given** multiple alerts
**When** I view Alerts section
**Then** alerts are sorted by time (newest first)
**And** I can dismiss acknowledged alerts

#### Story 7.7: Integration & E2E Validation

As a developer,
I want Epic 7 deployed and tested end-to-end,
So that I can validate risk management before enabling live execution.

**Acceptance Criteria:**

**Given** Docker environment updated with Epic 7 features
**When** I run `docker compose up`
**Then** circuit breaker state is persisted in Supabase
**And** risk configuration is loaded from database

**Given** Playwright E2E test suite for Epic 7
**When** tests run against the deployed app
**Then** drawdown circuit breaker triggers at threshold
**And** consecutive loss protection reduces sizing
**And** position limits reject new positions when full
**And** manual pause/resume works from Config

**Given** circuit breaker trigger scenarios
**When** E2E tests simulate drawdown or losses
**Then** alerts appear in Home → Alerts section
**And** trading pauses automatically
**And** reset flow works correctly

---

### Epic 8: Execution & Performance Dashboard

**User Outcome:** Operator can switch to live mode, execute real trades, and view performance metrics.

**FRs covered:** FR27, FR36, FR37, FR41

#### Story 8.1: Jupiter Live Execution

As an operator,
I want real trades executed via Jupiter API,
So that I can profit from validated signals.

**Acceptance Criteria:**

**Given** system in Live mode
**When** an order needs execution
**Then** Jupiter API is called with swap parameters
**And** transaction is submitted to Solana blockchain

**Given** Jupiter swap succeeds
**When** transaction is confirmed
**Then** order status updates to "filled"
**And** actual fill price is recorded

**Given** Jupiter swap fails
**When** error occurs (slippage, insufficient funds)
**Then** order status updates to "failed"
**And** error details are logged for review
**And** retry logic attempts recovery if transient

#### Story 8.2: Mode Toggle (Simulation/Live)

As an operator,
I want to switch between simulation and live mode,
So that I can control when real capital is at risk.

**Acceptance Criteria:**

**Given** Config → Trading section
**When** I toggle mode from Simulation to Live
**Then** confirmation dialog appears: "Switch to Live mode? Real capital will be used."
**And** requires explicit confirmation

**Given** mode switched to Live
**When** status bar renders
**Then** it shows "🟢 LIVE" with capital balance
**And** mode indicator is prominent

**Given** mode switched to Simulation
**When** orders execute
**Then** no real transactions occur
**And** status shows "🔵 SIMULATION"

#### Story 8.3: Performance Metrics Dashboard

As an operator,
I want to view performance metrics,
So that I can track profitability.

**Acceptance Criteria:**

**Given** Home page KPI section
**When** I view dashboard
**Then** I see Today's P&L (SOL and %)
**And** Win Rate (trades won / total trades)
**And** Active Positions count

**Given** performance data exists
**When** metrics are calculated
**Then** P&L includes realized + unrealized gains
**And** win rate is calculated correctly
**And** metrics update on page refresh

**Given** no trades yet
**When** I view metrics
**Then** appropriate zero/empty state is shown
**And** no division errors occur

#### Story 8.4: Trade History

As an operator,
I want to view complete trade history,
So that I can analyze past performance.

**Acceptance Criteria:**

**Given** Explorer → History tab (or dedicated section)
**When** I view trade history
**Then** I see all closed positions with:
- Token, Entry, Exit, P&L, Duration, Wallet source

**Given** trade history table
**When** I click a row
**Then** sidebar shows full trade context
**And** includes signal score, entry/exit timestamps, fees

**Given** filter controls
**When** I filter by date range or P&L
**Then** table updates to show matching trades
**And** summary stats reflect filtered data

#### Story 8.5: Home Dashboard Integration

As an operator,
I want Home page to answer key questions instantly,
So that I know system status in 5 seconds.

**Acceptance Criteria:**

**Given** Home page
**When** I open the dashboard
**Then** I immediately see:
- System status (mode, health)
- Performance KPIs (P&L, win rate)
- Active positions count
- Recent signals (last 5)
- Any active alerts

**Given** all components load
**When** dashboard renders
**Then** response time < 2 seconds
**And** auto-refresh updates data

**Given** drill-down interaction
**When** I click any element (position, signal, alert)
**Then** sidebar opens with full context
**And** I can navigate to related items

#### Story 8.6: Integration & E2E Validation

As a developer,
I want Epic 8 deployed and tested end-to-end,
So that I can validate the complete system before production.

**Acceptance Criteria:**

**Given** Docker environment with all features
**When** I run `docker compose up`
**Then** full system is operational
**And** Jupiter client is available (mock in test)

**Given** Playwright E2E test suite for Epic 8
**When** tests run against the deployed app
**Then** mode toggle between Simulation/Live works
**And** performance metrics display correctly
**And** trade history is searchable and filterable
**And** Home dashboard answers key questions in <2s

**Given** complete system integration test
**When** full signal-to-exit flow runs
**Then** all components communicate correctly
**And** data flows through the entire pipeline
**And** system is ready for production deployment

