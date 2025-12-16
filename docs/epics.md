---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - 'docs/prd.md'
  - 'docs/architecture.md'
workflowType: 'epics-stories'
lastStep: 3
status: 'complete'
completedAt: '2025-12-15'
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-15'
---

# WallTrack - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for WallTrack, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Wallet Intelligence (6 FRs)**
- FR1: System can discover high-performing wallets from successful token launches automatically
- FR2: System can analyze wallet historical performance (win rate, PnL, timing percentile)
- FR3: System can profile wallet behavioral patterns (activity hours, position sizing style, token preferences)
- FR4: System can detect wallet performance decay using rolling window analysis
- FR5: System can flag wallets for review when performance drops below threshold
- FR6: Operator can manually blacklist specific wallets

**Cluster Analysis (6 FRs)**
- FR7: System can map wallet funding relationships (FUNDED_BY connections)
- FR8: System can detect synchronized buying patterns (SYNCED_BUY within 5 min)
- FR9: System can identify wallets appearing together on multiple early tokens
- FR10: System can group related wallets into clusters
- FR11: System can identify cluster leaders (wallets that initiate movements)
- FR12: System can amplify signal score when multiple cluster wallets move together

**Signal Processing (6 FRs)**
- FR13: System can receive real-time swap notifications via Helius webhooks
- FR14: System can filter notifications to only monitored wallet addresses
- FR15: System can calculate multi-factor signal score (wallet, cluster, token, context)
- FR16: System can apply scoring threshold to determine trade eligibility
- FR17: System can query token characteristics (age, market cap, liquidity, holder distribution)
- FR18: System can log all signals regardless of score for analysis

**Trade Execution (9 FRs)**
- FR19: System can execute swap trades via Jupiter API
- FR20: System can apply dynamic position sizing based on signal score
- FR21: System can set and monitor stop-loss levels per position
- FR22: System can set and monitor take-profit levels per position
- FR23: System can execute configurable exit strategies with multiple take-profit levels
- FR24: System can track all open positions and their current status
- FR25: System can execute trailing stop on active positions
- FR26: System can apply time-based exit rules (max hold duration, stagnation detection)
- FR27: System can assign exit strategy based on signal score or operator override

**Risk Management (6 FRs)**
- FR28: System can pause all trading when drawdown exceeds threshold (20%)
- FR29: System can reduce position size after consecutive losses
- FR30: System can halt trading when win rate falls below threshold over N trades
- FR31: System can alert operator when circuit breaker triggers
- FR32: Operator can manually pause and resume trading
- FR33: System can enforce maximum concurrent position limits

**System Feedback (5 FRs)**
- FR34: System can record trade outcomes (entry price, exit price, PnL, duration)
- FR35: System can update wallet scores based on trade outcomes
- FR36: System can recalibrate scoring model weights based on results
- FR37: System can track signal accuracy over time
- FR38: System can identify patterns in successful vs unsuccessful trades

**Operator Dashboard - Gradio (13 FRs)**
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

**Trading Wallet Management (3 FRs)**
- FR52: Operator can connect trading wallet to the system
- FR53: Operator can view trading wallet balance (SOL and tokens)
- FR54: System can validate wallet connectivity before trading

**Total: 54 Functional Requirements**

### Non-Functional Requirements

**Performance**
- NFR1: Signal-to-Trade Latency < 5 seconds (from webhook receipt to trade execution)
- NFR2: Webhook Processing < 500ms (time to process and score incoming signal)
- NFR3: Dashboard Response < 2 seconds (page load and data refresh)
- NFR4: Database Queries < 100ms (Neo4j and Supabase query response)
- NFR5: Handle 10+ concurrent signals without dropping any

**Security**
- NFR6: Private key storage via environment variables only, never in code or logs
- NFR7: API key management with secure storage and rotation capability
- NFR8: Webhook validation via signature verification for all Helius webhooks
- NFR9: Dashboard access restricted to local network only or authenticated
- NFR10: No sensitive data (keys, signatures) in logs
- NFR11: Daily backup of Supabase data, Neo4j export weekly

**Reliability**
- NFR12: System uptime >= 95% with auto-restart on crash
- NFR13: Webhook availability 24/7 with health check endpoint and alerting
- NFR14: Zero data loss via transaction logging and backup
- NFR15: Graceful degradation - continue without non-critical services
- NFR16: Auto-retry failed trades with manual override available

**Integration**
- NFR17: Helius webhooks > 99% event delivery (fallback: RPC polling)
- NFR18: DexScreener API tolerate 5min outage (fallback: cache + Birdeye)
- NFR19: Jupiter API < 1% trade failure rate (fallback: Raydium direct, retry logic)
- NFR20: Solana RPC with multiple provider rotation

**Scalability**
- NFR21: Support 1,000+ monitored wallets
- NFR22: Store 1 year of trade history data
- NFR23: Store 6 months of all signal logs

**Total: 23 Non-Functional Requirements**

### Additional Requirements from Architecture

**Project Initialization**
- AR1: Custom layered Python structure (no existing starter template)
- AR2: Initialize with uv package manager
- AR3: Python 3.11+ with strict type hints and AsyncIO throughout
- AR4: Project structure: api → core → data/services layers

**Technology Stack**
- AR5: FastAPI for webhooks and API endpoints
- AR6: Gradio for operator dashboard
- AR7: Neo4j for wallet relationships and cluster graphs
- AR8: Supabase PostgreSQL for metrics, trade history, wallet profiles
- AR9: Supabase Vectors for behavioral embeddings
- AR10: XGBoost/scikit-learn for ML scoring
- AR11: httpx with tenacity for async HTTP with retry
- AR12: structlog for JSON logging with bound context
- AR13: pydantic-settings for configuration management

**Implementation Patterns**
- AR14: PEP 8 strict naming conventions
- AR15: Absolute imports only (from walltrack.*)
- AR16: Custom exceptions hierarchy (WallTrackError base)
- AR17: All async functions must be fully async (no asyncio.run inside async)
- AR18: Standard API response format (data/meta for success, error object for failures)

**Exit Strategy System**
- AR19: Configurable exit strategies with TakeProfitLevel, TrailingStopConfig, TimeRules
- AR20: Preconfigured strategies: Conservative, Balanced, Moonbag Aggressive, Quick Flip, Diamond Hands
- AR21: Score-based strategy assignment (>= 0.90 Diamond Hands, 0.80-0.89 Moonbag Aggressive, 0.70-0.79 Balanced)

**Database Design**
- AR22: Neo4j owns: Wallet nodes, FUNDED_BY edges, SYNCED_BUY edges, cluster membership
- AR23: Supabase owns: Wallet metrics, trade history, signal logs, performance scores, exit_strategies table
- AR24: Runtime config stored in Supabase config table (dashboard-editable, no restart required)

**Service Abstraction**
- AR25: BaseAPIClient with retry and circuit breaker pattern
- AR26: Retry: max 3, exponential backoff (1s, 2s, 4s), jitter ±500ms
- AR27: Circuit breaker: 5 failures → 30s cooldown

**Total: 27 Additional Architecture Requirements**

### FR Coverage Map

| FR | Epic | Description |
|----|------|-------------|
| FR1 | Epic 1 | Wallet discovery from successful launches |
| FR2 | Epic 1 | Wallet historical performance analysis |
| FR3 | Epic 1 | Wallet behavioral profiling |
| FR4 | Epic 1 | Wallet decay detection |
| FR5 | Epic 1 | Wallet flagging for review |
| FR6 | Epic 1 | Manual wallet blacklisting |
| FR7 | Epic 2 | Wallet funding relationships (FUNDED_BY) |
| FR8 | Epic 2 | Synchronized buying patterns (SYNCED_BUY) |
| FR9 | Epic 2 | Co-occurrence on early tokens |
| FR10 | Epic 2 | Cluster grouping |
| FR11 | Epic 2 | Cluster leader identification |
| FR12 | Epic 2 | Cluster signal amplification |
| FR13 | Epic 3 | Helius webhook reception |
| FR14 | Epic 3 | Notification filtering |
| FR15 | Epic 3 | Multi-factor signal scoring |
| FR16 | Epic 3 | Scoring threshold application |
| FR17 | Epic 3 | Token characteristics query |
| FR18 | Epic 3 | Signal logging |
| FR19 | Epic 4 | Jupiter swap execution |
| FR20 | Epic 4 | Dynamic position sizing |
| FR21 | Epic 4 | Stop-loss management |
| FR22 | Epic 4 | Take-profit management |
| FR23 | Epic 4 | Configurable exit strategies |
| FR24 | Epic 4 | Position tracking |
| FR25 | Epic 4 | Trailing stop execution |
| FR26 | Epic 4 | Time-based exit rules |
| FR27 | Epic 4 | Score-based strategy assignment |
| FR28 | Epic 5 | Drawdown circuit breaker |
| FR29 | Epic 5 | Position size reduction |
| FR30 | Epic 5 | Win rate circuit breaker |
| FR31 | Epic 5 | Circuit breaker alerts |
| FR32 | Epic 5 | Manual pause/resume |
| FR33 | Epic 5 | Position limits |
| FR34 | Epic 6 | Trade outcome recording |
| FR35 | Epic 6 | Wallet score updates |
| FR36 | Epic 6 | Scoring model recalibration |
| FR37 | Epic 6 | Signal accuracy tracking |
| FR38 | Epic 6 | Pattern identification |
| FR39 | Epic 5 | Risk parameters configuration |
| FR40 | Epic 5 | System status view |
| FR41 | Epic 4 | Active positions view |
| FR42 | Epic 6 | Performance metrics view |
| FR43 | Epic 4 | Trade history view |
| FR44 | Epic 5 | Circuit breaker alerts UI |
| FR45 | Epic 3 | Scoring weights adjustment |
| FR46 | Epic 1 | Watchlist management |
| FR47 | Epic 6 | Backtest preview |
| FR48 | Epic 1/2 | Wallet and cluster analysis view |
| FR49 | Epic 4 | Custom exit strategy definition |
| FR50 | Epic 4 | Default exit strategy assignment |
| FR51 | Epic 4 | Exit strategy modification |
| FR52 | Epic 4 | Trading wallet connection |
| FR53 | Epic 4 | Wallet balance view |
| FR54 | Epic 4 | Wallet connectivity validation |
| FR55 | Epic 7 | Simulation mode execution |
| FR56 | Epic 7 | Simulated trade execution |
| FR57 | Epic 7 | Simulated position tracking |
| FR58 | Epic 7 | Real-time P&L for simulation |
| FR59 | Epic 7 | Simulation dashboard view |
| FR60 | Epic 7 | Simulation alerts and logging |
| FR61 | Epic 8 | Historical data collection |
| FR62 | Epic 8 | Backtest engine replay |
| FR63 | Epic 8 | Scenario configuration |
| FR64 | Epic 8 | Batch backtest execution |
| FR65 | Epic 8 | Scenario comparison |
| FR66 | Epic 8 | Parameter optimization |
| FR67 | Epic 8 | Backtest dashboard |

## Epic List

### Epic 1: Wallet Intelligence & Discovery

**Goal:** Operator can discover, profile, and manage high-performing wallets with a basic dashboard view.

**User Value:** From day one, the operator can identify smart money wallets, understand their performance patterns, and build a curated watchlist of alpha-generating addresses.

**FRs Covered:** FR1, FR2, FR3, FR4, FR5, FR6, FR46, FR48 (wallet part)

**Includes:**
- Project initialization and core infrastructure (AR1-AR13)
- Database setup (Neo4j + Supabase connections)
- Wallet discovery engine
- Wallet profiling and performance metrics
- Decay detection system
- Basic Gradio dashboard with wallet views
- Watchlist management

---

### Epic 2: Cluster Analysis & Graph Intelligence

**Goal:** Operator can visualize wallet relationships and identify coordinated insider groups.

**User Value:** The operator gains insight into hidden wallet networks—who funds whom, who buys together—enabling detection of coordinated insider activity that individual wallet tracking would miss.

**FRs Covered:** FR7, FR8, FR9, FR10, FR11, FR12, FR48 (cluster part)

**Includes:**
- Neo4j graph relationship queries
- FUNDED_BY edge detection
- SYNCED_BUY pattern detection
- Cluster grouping algorithm
- Cluster leader identification
- Signal amplification logic
- Dashboard cluster visualization

---

### Epic 3: Real-Time Signal Processing & Scoring

**Goal:** System receives and scores insider movements in real-time with configurable thresholds.

**User Value:** The operator has a live feed of smart money activity, with each signal automatically scored by a multi-factor model. No manual monitoring required—the system watches 24/7.

**FRs Covered:** FR13, FR14, FR15, FR16, FR17, FR18, FR45

**Includes:**
- Helius webhook integration with HMAC validation
- Signal filtering to monitored wallets
- Multi-factor scoring engine (wallet 30%, cluster 25%, token 25%, context 20%)
- Token characteristics fetching (DexScreener)
- Signal logging for analysis
- Scoring weight adjustment UI

---

### Epic 4: Automated Trade Execution & Position Management

**Goal:** System automatically executes trades based on signals with configurable exit strategies.

**User Value:** The operator's capital works autonomously. High-conviction signals trigger trades automatically, positions are managed with sophisticated exit strategies, and the operator can monitor everything without intervening.

**FRs Covered:** FR19, FR20, FR21, FR22, FR23, FR24, FR25, FR26, FR27, FR41, FR43, FR49, FR50, FR51, FR52, FR53, FR54

**Includes:**
- Jupiter API integration for swaps
- Dynamic position sizing by score
- Exit strategy system (stop-loss, multi-level take-profit, trailing stop, moonbag)
- Time-based exit rules (max hold, stagnation)
- Position tracking and status
- Trading wallet connection and balance
- Dashboard: positions view, trade history, exit strategy management

---

### Epic 5: Risk Management & Capital Protection

**Goal:** System automatically protects capital with circuit breakers and alerts.

**User Value:** The operator's capital is protected 24/7. Circuit breakers pause trading before losses compound, alerts notify of critical events, and manual overrides provide ultimate control.

**FRs Covered:** FR28, FR29, FR30, FR31, FR32, FR33, FR39, FR40, FR44

**Includes:**
- Drawdown circuit breaker (20% max)
- Win rate monitoring and halt
- Consecutive loss handling (position size reduction)
- Maximum concurrent position limits
- Alert system for circuit breakers
- Manual pause/resume controls
- Dashboard: system status, risk configuration, alerts

---

### Epic 6: Feedback Loop & Performance Analytics

**Goal:** System continuously improves based on trade outcomes and operator can analyze performance.

**User Value:** The system gets smarter over time. Trade results update wallet scores, patterns emerge from the data, and the operator has complete visibility into what's working and what isn't.

**FRs Covered:** FR34, FR35, FR36, FR37, FR38, FR42, FR47

**Includes:**
- Trade outcome recording (entry, exit, PnL, duration)
- Automatic wallet score updates
- Scoring model recalibration
- Signal accuracy tracking
- Pattern analysis (success vs failure)
- Dashboard: performance metrics, PnL charts, backtest preview

---

## Epic 1: Wallet Intelligence & Discovery

**Epic Goal:** Operator can discover, profile, and manage high-performing wallets with a basic dashboard view.

### Story 1.1: Project Initialization and Structure

As an operator,
I want the project initialized with the correct structure and dependencies,
So that development can proceed with a solid foundation.

**Acceptance Criteria:**

**Given** a fresh development environment
**When** the initialization script is run
**Then** the project is created with uv package manager
**And** all core dependencies are installed (fastapi, uvicorn, gradio, neo4j, supabase, httpx, pydantic-settings, apscheduler, xgboost, scikit-learn, structlog, tenacity)
**And** dev dependencies are installed (pytest, pytest-asyncio, ruff, mypy)
**And** the directory structure matches architecture specification (src/walltrack/ with api/, core/, data/, services/, discovery/, ml/, ui/, config/, scheduler/)
**And** pyproject.toml is configured with ruff and mypy settings
**And** .env.example is created with placeholder values
**And** .gitignore includes standard Python ignores plus .env

**Technical Notes:**
- Follow AR1-AR4 from Architecture
- Use PEP 8 strict naming (AR14)
- Configure absolute imports (AR15)

---

### Story 1.2: Core Configuration Layer

As an operator,
I want a centralized configuration system,
So that I can manage settings via environment variables and runtime config.

**Acceptance Criteria:**

**Given** the project structure is initialized
**When** the configuration module is implemented
**Then** pydantic-settings BaseSettings loads all secrets from environment variables
**And** settings include: database URLs, API keys, Solana RPC endpoints
**And** sensitive values are never logged or exposed
**And** a Settings singleton is available via dependency injection
**And** configuration validation fails fast with clear error messages

**Given** invalid or missing required environment variables
**When** the application starts
**Then** a clear error message indicates which variables are missing
**And** the application does not start

**Technical Notes:**
- Implement in src/walltrack/config/settings.py
- Follow AR13 (pydantic-settings)
- No secrets in code or logs (NFR6, NFR10)

---

### Story 1.3: Database Connections

As an operator,
I want reliable connections to Neo4j and Supabase,
So that wallet data can be stored and queried.

**Acceptance Criteria:**

**Given** valid database credentials in environment
**When** the application starts
**Then** async Neo4j driver connects successfully
**And** Supabase client connects successfully
**And** connection health can be verified via health check endpoint

**Given** database connection fails
**When** a query is attempted
**Then** the error is logged with context (no sensitive data)
**And** retry logic attempts reconnection (max 3, exponential backoff)
**And** circuit breaker opens after 5 consecutive failures

**Given** the health check endpoint is called
**When** databases are connected
**Then** response includes status for Neo4j and Supabase
**And** response time is < 100ms (NFR4)

**Technical Notes:**
- Neo4j client in src/walltrack/data/neo4j/client.py
- Supabase client in src/walltrack/data/supabase/client.py
- Follow AR7, AR8, AR22, AR23
- Implement retry with tenacity (AR11, AR26)

---

### Story 1.4: Wallet Discovery Engine

As an operator,
I want to automatically discover high-performing wallets from successful token launches,
So that I can build a watchlist of smart money addresses.

**Acceptance Criteria:**

**Given** a list of successful token launches (provided or fetched)
**When** the discovery engine runs
**Then** early buyers are identified (bought within first N minutes)
**And** wallets with profitable exits are extracted
**And** wallet addresses are stored in Supabase with discovery metadata
**And** wallet nodes are created in Neo4j

**Given** a discovered wallet already exists
**When** rediscovery occurs
**Then** the wallet is not duplicated
**And** discovery count is incremented

**Given** the discovery process completes
**When** results are returned
**Then** count of new wallets discovered is provided
**And** count of existing wallets updated is provided
**And** process duration is logged

**Technical Notes:**
- Implement in src/walltrack/discovery/scanner.py
- FR1: Automatic discovery from successful launches
- Create wallets table in Supabase
- Create Wallet nodes in Neo4j

---

### Story 1.5: Wallet Performance Profiling

As an operator,
I want to see performance metrics and behavioral patterns for each wallet,
So that I can assess wallet quality before adding to watchlist.

**Acceptance Criteria:**

**Given** a wallet address
**When** profiling is requested
**Then** historical performance is calculated (win rate, total PnL, average PnL per trade)
**And** timing percentile is calculated (how early they typically enter)
**And** behavioral patterns are extracted (activity hours, avg position size, preferred token types)
**And** profile is stored in Supabase wallets table

**Given** insufficient historical data (< 5 trades)
**When** profiling is requested
**Then** profile is marked as "insufficient_data"
**And** available metrics are still calculated

**Given** profiling completes successfully
**When** the wallet is viewed in dashboard
**Then** all metrics are displayed with last updated timestamp

**Technical Notes:**
- Implement in src/walltrack/discovery/profiler.py
- FR2: Historical performance analysis
- FR3: Behavioral pattern profiling
- Query on-chain data via Solana RPC or Helius

---

### Story 1.6: Wallet Decay Detection

As an operator,
I want the system to detect when wallet performance degrades,
So that I can review and potentially remove underperforming wallets.

**Acceptance Criteria:**

**Given** a wallet with at least 20 historical trades
**When** decay detection runs
**Then** rolling 20-trade window win rate is calculated
**And** comparison to lifetime win rate is made

**Given** rolling win rate drops below 40%
**When** decay threshold is breached
**Then** wallet is flagged with status "decay_detected"
**And** flag timestamp is recorded
**And** operator is notified (if notifications enabled)

**Given** 3 consecutive losses from the same wallet
**When** the third loss is recorded
**Then** wallet score receives temporary downgrade
**And** downgrade is logged with reason

**Given** wallet performance recovers (rolling win rate > 50%)
**When** next decay check runs
**Then** decay flag is cleared
**And** score downgrade is removed

**Technical Notes:**
- Implement in src/walltrack/discovery/decay_detector.py
- FR4: Rolling window decay detection
- FR5: Flagging for review
- Run via APScheduler periodic task

---

### Story 1.7: Wallet Blacklisting

As an operator,
I want to manually blacklist wallets,
So that they are excluded from all signals and analysis.

**Acceptance Criteria:**

**Given** a wallet address
**When** operator adds to blacklist via dashboard or API
**Then** wallet status is set to "blacklisted"
**And** blacklist timestamp and reason are recorded
**And** wallet is excluded from signal processing

**Given** a blacklisted wallet
**When** a signal is received from this wallet
**Then** signal is logged but not scored
**And** signal is marked as "blocked_blacklisted"

**Given** a blacklisted wallet
**When** operator removes from blacklist
**Then** wallet status returns to previous state
**And** wallet resumes normal signal processing

**Technical Notes:**
- FR6: Manual blacklisting
- Add blacklist fields to wallets table
- Implement blacklist check in signal pipeline

---

### Story 1.8: Basic Dashboard - Wallet Views

As an operator,
I want a Gradio dashboard to view and manage wallets,
So that I can interact with the system visually.

**Acceptance Criteria:**

**Given** the dashboard is launched
**When** operator navigates to Wallets tab
**Then** list of all wallets is displayed with key metrics (address, win rate, PnL, status)
**And** wallets can be sorted by any column
**And** wallets can be filtered by status (active, decay_detected, blacklisted)

**Given** a wallet in the list
**When** operator clicks on it
**Then** detailed profile is displayed (all metrics from Story 1.5)
**And** recent trades are shown
**And** blacklist button is available

**Given** the watchlist management view
**When** operator adds a wallet address manually
**Then** wallet is added to watchlist
**And** profiling is triggered automatically
**And** success/error feedback is displayed

**Given** the dashboard is loaded
**When** data is refreshed
**Then** response time is < 2 seconds (NFR3)

**Technical Notes:**
- Implement in src/walltrack/ui/dashboard.py and src/walltrack/ui/components/
- FR46: Watchlist management
- FR48: Wallet analysis view
- Use Gradio Blocks for layout

---

## Epic 2: Cluster Analysis & Graph Intelligence

**Epic Goal:** Operator can visualize wallet relationships and identify coordinated insider groups.

### Story 2.1: Wallet Funding Relationship Detection (FUNDED_BY)

As an operator,
I want the system to detect funding relationships between wallets,
So that I can identify wallets that share common funding sources.

**Acceptance Criteria:**

**Given** a wallet address in the system
**When** funding analysis is triggered
**Then** incoming SOL transfers are analyzed
**And** source wallets are identified
**And** FUNDED_BY edges are created in Neo4j (source → target)
**And** funding amount and timestamp are stored on the edge

**Given** wallet A funded wallet B with > 0.1 SOL
**When** the relationship is queried
**Then** Neo4j returns the FUNDED_BY edge with amount and date
**And** relationship strength is calculated based on amount/frequency

**Given** multiple funding sources for a wallet
**When** funding tree is requested
**Then** all upstream funding wallets are returned (up to N levels)
**And** common ancestors between wallets are identified

**Technical Notes:**
- Implement in src/walltrack/data/neo4j/queries/wallet.py
- FR7: Map wallet funding relationships
- Use Cypher queries for graph traversal
- Store edges with properties: amount, timestamp, tx_signature

---

### Story 2.2: Synchronized Buying Pattern Detection (SYNCED_BUY)

As an operator,
I want the system to detect when wallets buy the same token within a short time window,
So that I can identify coordinated buying behavior.

**Acceptance Criteria:**

**Given** transaction history for monitored wallets
**When** sync detection analysis runs
**Then** wallets buying the same token within 5 minutes are identified
**And** SYNCED_BUY edges are created in Neo4j between the wallets
**And** edge properties include: token address, time delta, buy amounts

**Given** wallets A and B bought token X within 3 minutes
**When** the relationship is queried
**Then** SYNCED_BUY edge is returned with token and timing details
**And** sync count (how many times they've synced) is available

**Given** sync detection completes
**When** results are summarized
**Then** count of new SYNCED_BUY relationships is provided
**And** wallets with highest sync frequency are highlighted

**Technical Notes:**
- Implement sync detection in src/walltrack/discovery/scanner.py or dedicated module
- FR8: Detect synchronized buying patterns within 5 min
- Neo4j edge: (Wallet)-[:SYNCED_BUY {token, time_delta, count}]->(Wallet)

---

### Story 2.3: Co-occurrence Analysis on Early Tokens

As an operator,
I want to identify wallets that consistently appear together on early token entries,
So that I can detect wallets that may share insider information.

**Acceptance Criteria:**

**Given** historical trade data for wallets
**When** co-occurrence analysis runs
**Then** tokens where wallet entered in first 10 minutes are identified
**And** other wallets that entered the same tokens early are found
**And** co-occurrence count per wallet pair is calculated

**Given** wallets A and B appeared together on 5+ early tokens
**When** co-occurrence threshold is met
**Then** relationship is flagged as "high_co_occurrence"
**And** CO_OCCURS edge is created/updated in Neo4j
**And** shared tokens list is stored

**Given** co-occurrence data exists
**When** operator queries a wallet's associates
**Then** all wallets with co-occurrence > threshold are returned
**And** shared token count and list are provided

**Technical Notes:**
- FR9: Identify wallets appearing together on multiple early tokens
- Store in Neo4j: (Wallet)-[:CO_OCCURS {count, tokens}]->(Wallet)
- Run as periodic batch job via APScheduler

---

### Story 2.4: Cluster Grouping Algorithm

As an operator,
I want wallets with strong relationships to be grouped into clusters,
So that I can analyze coordinated groups rather than individual wallets.

**Acceptance Criteria:**

**Given** wallets with FUNDED_BY, SYNCED_BUY, and CO_OCCURS relationships
**When** cluster detection algorithm runs
**Then** connected components are identified in the graph
**And** clusters are created as Cluster nodes in Neo4j
**And** MEMBER_OF edges link wallets to their cluster

**Given** a cluster is formed
**When** cluster properties are calculated
**Then** cluster size (wallet count) is stored
**And** cluster strength (avg relationship weight) is calculated
**And** cluster creation date is recorded

**Given** new relationships are added
**When** cluster recalculation runs
**Then** clusters are updated or merged as appropriate
**And** orphan wallets (no strong relationships) remain unclustered

**Given** a wallet belongs to a cluster
**When** wallet is queried
**Then** cluster_id is returned
**And** other cluster members are accessible

**Technical Notes:**
- FR10: Group related wallets into clusters
- Use Neo4j community detection or connected components algorithm
- Cluster node: (:Cluster {id, size, strength, created_at})
- Edge: (Wallet)-[:MEMBER_OF]->(Cluster)

---

### Story 2.5: Cluster Leader Identification

As an operator,
I want to identify which wallets lead movements within a cluster,
So that I can prioritize signals from leaders over followers.

**Acceptance Criteria:**

**Given** a cluster with multiple wallets
**When** leader analysis runs
**Then** wallets that consistently act first are identified
**And** "leader_score" is calculated per wallet (based on timing precedence)
**And** top N leaders per cluster are flagged

**Given** wallet A consistently buys 1-5 minutes before other cluster members
**When** leader score is calculated
**Then** wallet A receives high leader_score
**And** wallet A is marked as cluster leader

**Given** a cluster has identified leaders
**When** cluster is queried
**Then** leader wallets are returned with their leader_score
**And** leader status is visible in dashboard

**Given** signal comes from a cluster leader
**When** signal is processed (in Epic 3)
**Then** leader status is available for scoring amplification

**Technical Notes:**
- FR11: Identify cluster leaders
- Store leader_score on Wallet node or MEMBER_OF edge
- Calculate based on temporal analysis of coordinated buys

---

### Story 2.6: Cluster Signal Amplification Logic

As an operator,
I want signals to be amplified when multiple cluster members move together,
So that coordinated insider activity gets higher priority.

**Acceptance Criteria:**

**Given** a signal from wallet A in cluster X
**When** signal processing checks cluster activity
**Then** recent signals from other cluster X members are queried
**And** if 2+ cluster members signaled same token in last 10 minutes, amplification applies

**Given** cluster amplification condition is met
**When** signal score is calculated
**Then** cluster_amplification_factor is added to scoring context
**And** factor is proportional to: number of cluster members, leader involvement

**Given** no other cluster members moved
**When** signal is processed
**Then** no amplification is applied
**And** signal proceeds with base scoring

**Given** amplification is applied
**When** signal is logged
**Then** amplification details are recorded (which members, timing)
**And** cluster contribution to final score is trackable

**Technical Notes:**
- FR12: Amplify signal score when multiple cluster wallets move together
- Implement in src/walltrack/core/scoring/ (used by Epic 3)
- Store amplification rules in config (configurable thresholds)

---

### Story 2.7: Dashboard - Cluster Visualization

As an operator,
I want to view cluster relationships and members in the dashboard,
So that I can understand the network of insider groups.

**Acceptance Criteria:**

**Given** the dashboard is open
**When** operator navigates to Clusters tab
**Then** list of all clusters is displayed (id, size, strength, leader count)
**And** clusters can be sorted by size or strength
**And** clusters can be filtered by minimum size

**Given** a cluster is selected
**When** cluster detail view opens
**Then** all member wallets are listed with their role (leader/member)
**And** cluster metrics are displayed (total PnL, avg win rate)
**And** relationship types between members are summarized

**Given** the cluster visualization component
**When** operator requests graph view
**Then** a visual representation shows wallets as nodes
**And** relationships (FUNDED_BY, SYNCED_BUY, CO_OCCURS) are shown as edges
**And** leaders are visually distinguished (color/size)

**Given** a wallet in cluster view
**When** operator clicks on it
**Then** navigation to wallet detail (from Epic 1) is available

**Technical Notes:**
- FR48 (cluster part): Cluster analysis view
- Implement in src/walltrack/ui/components/clusters.py
- Consider simple network visualization (Gradio + plotly or pyvis)

---

## Epic 3: Real-Time Signal Processing & Scoring

**Epic Goal:** System receives and scores insider movements in real-time with configurable thresholds.

### Story 3.1: Helius Webhook Integration

As an operator,
I want the system to receive real-time swap notifications from Helius,
So that insider movements are detected instantly.

**Acceptance Criteria:**

**Given** Helius webhook is configured with system endpoint
**When** a monitored wallet executes a swap on Solana
**Then** Helius sends webhook notification to FastAPI endpoint
**And** webhook is received within seconds of on-chain confirmation

**Given** an incoming webhook request
**When** the request is processed
**Then** HMAC signature is validated against Helius secret
**And** invalid signatures are rejected with 401
**And** rejection is logged with request metadata (no sensitive data)

**Given** a valid webhook payload
**When** payload is parsed
**Then** transaction details are extracted (wallet, token, amount, direction, timestamp)
**And** payload is passed to signal processing pipeline
**And** processing time is < 500ms (NFR2)

**Given** webhook endpoint
**When** health check is performed
**Then** endpoint responds with 200 OK
**And** Helius connectivity status is included

**Technical Notes:**
- Implement in src/walltrack/api/routes/webhooks.py
- FR13: Receive real-time swap notifications via Helius webhooks
- NFR8: Webhook validation via signature verification
- Use middleware for HMAC validation (src/walltrack/api/middleware/hmac_validation.py)

---

### Story 3.2: Signal Filtering to Monitored Wallets

As an operator,
I want only signals from monitored wallets to be processed,
So that system resources focus on relevant activity.

**Acceptance Criteria:**

**Given** a webhook notification arrives
**When** the wallet address is checked
**Then** query confirms if wallet is in monitored watchlist
**And** query response time is < 50ms

**Given** wallet IS in monitored watchlist
**When** filter check passes
**Then** signal proceeds to scoring pipeline
**And** signal is marked with source wallet metadata

**Given** wallet is NOT in monitored watchlist
**When** filter check runs
**Then** signal is discarded
**And** discard is logged at DEBUG level (not stored)
**And** no further processing occurs

**Given** wallet is blacklisted
**When** filter check runs
**Then** signal is logged with status "blocked_blacklisted"
**And** signal is NOT scored or processed further

**Technical Notes:**
- FR14: Filter notifications to only monitored wallet addresses
- Implement efficient lookup (in-memory cache or fast DB query)
- Integrate with blacklist from Story 1.7

---

### Story 3.3: Token Characteristics Fetching

As an operator,
I want token data fetched for each signal,
So that token quality factors into scoring.

**Acceptance Criteria:**

**Given** a signal with token address
**When** token characteristics are requested
**Then** DexScreener API is queried for token data
**And** response includes: age, market cap, liquidity, holder count, price

**Given** DexScreener returns data
**When** data is processed
**Then** token characteristics are cached (TTL: 5 minutes)
**And** data is attached to signal context

**Given** DexScreener API fails or times out
**When** fallback is triggered
**Then** Birdeye API is attempted as fallback (NFR18)
**And** if both fail, cached data is used if available
**And** if no data available, token score component is neutral

**Given** token is very new (< 10 minutes old)
**When** characteristics are evaluated
**Then** "new_token" flag is set
**And** limited historical data is handled gracefully

**Technical Notes:**
- FR17: Query token characteristics
- Implement in src/walltrack/services/dexscreener/client.py
- Fallback in src/walltrack/services/birdeye/client.py (or similar)
- Cache in memory or Redis-like structure

---

### Story 3.4: Multi-Factor Signal Scoring Engine

As an operator,
I want signals scored using multiple factors,
So that high-quality opportunities are prioritized.

**Acceptance Criteria:**

**Given** a filtered signal with wallet and token data
**When** scoring engine processes the signal
**Then** four factor scores are calculated:
- Wallet score (30%): based on wallet performance metrics
- Cluster score (25%): based on cluster activity and leader status
- Token score (25%): based on token characteristics
- Context score (20%): based on timing, market conditions

**Given** wallet score calculation
**When** wallet metrics are evaluated
**Then** win rate, PnL history, timing percentile contribute to score
**And** decay status reduces score if flagged
**And** leader status in cluster boosts score

**Given** cluster score calculation
**When** cluster activity is checked (from Story 2.6)
**Then** amplification factor is applied if cluster members moved together
**And** solo wallet movement gets base cluster score

**Given** token score calculation
**When** token characteristics are evaluated
**Then** liquidity, market cap, holder distribution contribute
**And** very new tokens (< 5 min) get reduced score
**And** suspicious patterns (honeypot indicators) reduce score

**Given** context score calculation
**When** market context is evaluated
**Then** time of day patterns are considered
**And** recent market volatility is factored

**Given** all factor scores calculated
**When** final score is computed
**Then** weighted average produces score between 0.0 and 1.0
**And** individual factor contributions are preserved for analysis

**Technical Notes:**
- FR15: Calculate multi-factor signal score
- Implement in src/walltrack/core/scoring/signal_scorer.py
- Weights configurable via Supabase config table
- ML model (XGBoost) can replace/augment rules-based scoring later

---

### Story 3.5: Scoring Threshold Application

As an operator,
I want signals below threshold to be filtered out,
So that only high-conviction signals trigger trades.

**Acceptance Criteria:**

**Given** a scored signal
**When** threshold check is applied
**Then** signal score is compared to configurable threshold (default: 0.70)

**Given** signal score >= threshold
**When** threshold check passes
**Then** signal is marked as "trade_eligible"
**And** signal proceeds to trade execution pipeline (Epic 4)
**And** eligibility is logged with score details

**Given** signal score < threshold
**When** threshold check fails
**Then** signal is marked as "below_threshold"
**And** signal is logged but NOT sent to execution
**And** signal remains available for analysis

**Given** dynamic threshold based on score ranges
**When** position sizing is determined (in Epic 4)
**Then** score range informs sizing multiplier:
- Score >= 0.85: High conviction (1.5x)
- Score 0.70-0.84: Standard (1.0x)
- Score < 0.70: No trade (0x)

**Technical Notes:**
- FR16: Apply scoring threshold to determine trade eligibility
- Threshold stored in Supabase config table (adjustable via dashboard)
- Support for multiple threshold tiers

---

### Story 3.6: Signal Logging and Storage

As an operator,
I want all signals logged regardless of score,
So that I can analyze patterns and improve the system.

**Acceptance Criteria:**

**Given** any signal (filtered, scored, or discarded)
**When** signal processing completes
**Then** signal is stored in Supabase signals table
**And** stored data includes: timestamp, wallet, token, score, factors, status, processing_time

**Given** signals table
**When** queried for analysis
**Then** signals can be filtered by: date range, wallet, score range, status
**And** query performance is acceptable for 6 months of data (NFR23)

**Given** a signal is stored
**When** trade is later executed (Epic 4)
**Then** signal record is linked to trade record
**And** signal-to-trade correlation is trackable

**Given** signal logging
**When** high volume of signals arrives
**Then** logging does not block main processing pipeline
**And** async write ensures < 500ms processing time maintained

**Technical Notes:**
- FR18: Log all signals regardless of score for analysis
- Implement signals table in Supabase
- Create signal_repo.py in src/walltrack/data/supabase/repositories/
- Index on timestamp, wallet_address, score for query performance

---

### Story 3.7: Dashboard - Scoring Configuration

As an operator,
I want to adjust scoring weights and thresholds in the dashboard,
So that I can tune the system without code changes.

**Acceptance Criteria:**

**Given** the dashboard Scoring Config panel
**When** operator views current settings
**Then** all scoring weights are displayed (wallet, cluster, token, context)
**And** current threshold is displayed
**And** last modified timestamp is shown

**Given** operator adjusts a weight
**When** change is saved
**Then** new weight is stored in Supabase config table
**And** change takes effect immediately (no restart)
**And** change is logged with previous and new values

**Given** operator adjusts threshold
**When** new threshold is saved
**Then** subsequent signals use new threshold
**And** validation ensures threshold is between 0.0 and 1.0

**Given** invalid configuration input
**When** save is attempted
**Then** validation error is displayed
**And** invalid change is not saved
**And** current valid config remains in effect

**Given** scoring config panel
**When** operator wants to reset to defaults
**Then** "Reset to Defaults" button is available
**And** confirmation is required before reset

**Technical Notes:**
- FR45: Operator can adjust scoring weights and thresholds
- Implement in src/walltrack/ui/components/config_panel.py
- Read/write via config_repo.py
- Hot-reload config without application restart (AR24)

---

## Epic 4: Automated Trade Execution & Position Management

**Epic Goal:** System automatically executes trades based on signals with configurable exit strategies.

### Story 4.1: Trading Wallet Connection and Balance

As an operator,
I want to connect my trading wallet to the system,
So that the system can execute trades on my behalf.

**Acceptance Criteria:**

**Given** operator has a Solana wallet with private key
**When** wallet is configured in environment variables
**Then** system loads wallet securely via pydantic-settings
**And** private key is NEVER logged or exposed (NFR6)

**Given** wallet is configured
**When** connectivity is validated
**Then** system confirms wallet can sign transactions
**And** current SOL balance is retrieved
**And** validation result is displayed in dashboard

**Given** connected wallet
**When** balance view is requested
**Then** SOL balance is displayed
**And** token balances (open positions) are listed
**And** balance refreshes on demand or automatically

**Given** wallet connection fails
**When** trade is attempted
**Then** trade is blocked with clear error
**And** alert is raised to operator
**And** system enters safe mode (no trades until resolved)

**Technical Notes:**
- FR52: Operator can connect trading wallet
- FR53: View trading wallet balance
- FR54: Validate wallet connectivity before trading
- Implement in src/walltrack/services/solana/wallet_client.py
- Use solders or solana-py for wallet operations

---

### Story 4.2: Jupiter API Integration for Swaps

As an operator,
I want the system to execute swaps via Jupiter,
So that trades are executed with best available pricing.

**Acceptance Criteria:**

**Given** a trade-eligible signal
**When** trade execution is triggered
**Then** Jupiter quote API is called for best route
**And** slippage tolerance is applied (configurable, default 1%)
**And** swap transaction is built and signed

**Given** swap transaction is ready
**When** transaction is submitted
**Then** transaction is sent to Solana network
**And** confirmation is awaited (with timeout)
**And** result (success/failure) is recorded

**Given** successful swap
**When** confirmation is received
**Then** entry price, amount, and tx signature are stored
**And** position is created in positions table
**And** execution latency is logged (target < 5s total, NFR1)

**Given** Jupiter API fails
**When** fallback is triggered
**Then** Raydium direct swap is attempted (NFR19)
**And** if both fail, trade is marked as "execution_failed"
**And** failure is logged with reason

**Given** transaction fails on-chain
**When** error is returned
**Then** error type is identified (slippage, insufficient balance, etc.)
**And** appropriate retry or abort logic is applied

**Technical Notes:**
- FR19: Execute swap trades via Jupiter API
- Implement in src/walltrack/services/jupiter/client.py
- Use Jupiter V6 Quote and Swap APIs
- Implement retry with tenacity (AR26)

---

### Story 4.3: Dynamic Position Sizing

As an operator,
I want position size to vary based on signal conviction,
So that higher-quality signals get larger allocations.

**Acceptance Criteria:**

**Given** a trade-eligible signal with score
**When** position size is calculated
**Then** base position size is retrieved from config (e.g., 2% of capital)
**And** multiplier is applied based on score tier:
- Score >= 0.85: 1.5x multiplier
- Score 0.70-0.84: 1.0x multiplier

**Given** calculated position size
**When** validation is performed
**Then** size does not exceed max position limit (configurable)
**And** size does not exceed available balance
**And** size respects concurrent position limits (FR33)

**Given** insufficient balance for calculated size
**When** trade is attempted
**Then** size is reduced to available amount (if above minimum)
**Or** trade is skipped if below minimum threshold
**And** decision is logged

**Given** position sizing config
**When** operator adjusts via dashboard
**Then** new base size and multipliers take effect immediately

**Technical Notes:**
- FR20: Apply dynamic position sizing based on signal score
- Implement in src/walltrack/core/execution/position_manager.py
- Config stored in Supabase, editable via dashboard

---

### Story 4.4: Exit Strategy Data Model and Presets

As an operator,
I want configurable exit strategies with presets,
So that I can choose how positions are managed based on my risk preference.

**Acceptance Criteria:**

**Given** exit strategy model
**When** strategy is defined
**Then** it includes:
- name: strategy identifier
- take_profit_levels: list of {trigger_multiplier, sell_percentage}
- stop_loss: loss threshold (e.g., 0.5 = -50%)
- trailing_stop: {enabled, activation_multiplier, distance_percentage}
- time_rules: {max_hold_hours, stagnation_exit, stagnation_threshold, stagnation_hours}
- moonbag_pct: percentage kept regardless
- moonbag_stop: stop level for moonbag (or null for ride to zero)

**Given** system initialization
**When** presets are loaded
**Then** five default strategies are available:
- Conservative: 50%@x2, 50%@x3, no trailing, no moonbag
- Balanced: 33%@x2, 33%@x3, trailing (x2, 30%), 34% moonbag
- Moonbag Aggressive: 25%@x2, 25%@x3, no trailing, 50% moonbag ride to zero
- Quick Flip: 100%@x1.5, no trailing, no moonbag
- Diamond Hands: 25%@x5, 25%@x10, trailing (x3, 40%), 50% moonbag

**Given** exit_strategies table in Supabase
**When** custom strategy is created
**Then** strategy is validated and stored
**And** strategy becomes available for assignment

**Technical Notes:**
- FR23: Configurable exit strategies with multiple take-profit levels
- AR19-AR21: Exit strategy system from Architecture
- Implement in src/walltrack/data/models/exit_strategy.py
- Store in Supabase exit_strategies table

---

### Story 4.5: Stop-Loss and Take-Profit Monitoring

As an operator,
I want the system to monitor and execute stop-loss and take-profit levels,
So that positions are closed at predetermined prices.

**Acceptance Criteria:**

**Given** an open position with assigned exit strategy
**When** position is created
**Then** stop-loss price is calculated from entry price and strategy
**And** take-profit levels are calculated for each tier
**And** levels are stored with position

**Given** position monitoring loop
**When** current price is fetched
**Then** price is compared against stop-loss level
**And** price is compared against each take-profit level

**Given** price hits stop-loss
**When** stop-loss is triggered
**Then** full remaining position is sold
**And** trade is recorded with exit_reason = "stop_loss"
**And** position is closed

**Given** price hits take-profit level N
**When** take-profit is triggered
**Then** configured percentage at that level is sold
**And** partial sale is recorded
**And** remaining position continues with next levels

**Given** all take-profit levels hit (except moonbag)
**When** moonbag_pct > 0
**Then** moonbag portion remains open
**And** moonbag follows its own stop (or rides to zero)

**Technical Notes:**
- FR21: Set and monitor stop-loss levels
- FR22: Set and monitor take-profit levels
- Implement in src/walltrack/core/execution/exit_manager.py
- Price monitoring via DexScreener or on-chain polling

---

### Story 4.6: Trailing Stop Execution

As an operator,
I want trailing stops to lock in profits as price rises,
So that I capture more upside while protecting gains.

**Acceptance Criteria:**

**Given** position with trailing stop enabled in strategy
**When** price reaches activation multiplier (e.g., x2)
**Then** trailing stop becomes active
**And** trailing stop level is set at (peak - distance%)

**Given** active trailing stop
**When** price continues rising
**Then** peak price is updated
**And** trailing stop level rises with it (ratchets up)
**And** trailing stop NEVER decreases

**Given** active trailing stop
**When** price drops below trailing stop level
**Then** position is sold (remaining after any take-profits)
**And** trade is recorded with exit_reason = "trailing_stop"
**And** actual exit price vs peak is logged

**Given** trailing stop not yet activated
**When** price drops below regular stop-loss
**Then** regular stop-loss takes precedence
**And** position exits via stop-loss

**Technical Notes:**
- FR25: Execute trailing stop on active positions
- Implement in src/walltrack/core/execution/trailing_stop.py
- Track peak_price per position

---

### Story 4.7: Time-Based Exit Rules

As an operator,
I want time-based exit rules,
So that capital isn't stuck in stagnant positions.

**Acceptance Criteria:**

**Given** position with time_rules in strategy
**When** max_hold_hours is configured
**Then** position age is tracked
**And** if age exceeds max_hold_hours, position is closed
**And** exit_reason = "max_hold_duration"

**Given** stagnation_exit enabled
**When** price movement over stagnation_hours < stagnation_threshold
**Then** position is flagged as stagnant
**And** position is closed
**And** exit_reason = "stagnation"

**Given** time rules are checked
**When** monitoring loop runs
**Then** time checks occur alongside price checks
**And** time-based exits are logged with duration and price movement

**Given** position is profitable but stagnant
**When** stagnation exit triggers
**Then** current profit is captured
**And** capital is freed for new opportunities

**Technical Notes:**
- FR26: Apply time-based exit rules
- Implement in src/walltrack/core/execution/exit_manager.py
- Track position_opened_at timestamp

---

### Story 4.8: Score-Based Strategy Assignment

As an operator,
I want exit strategies automatically assigned based on signal score,
So that high-conviction trades get more aggressive strategies.

**Acceptance Criteria:**

**Given** a new position from a scored signal
**When** exit strategy is assigned
**Then** score-based rules are applied:
- Score >= 0.90: Diamond Hands
- Score 0.80-0.89: Moonbag Aggressive
- Score 0.70-0.79: Balanced (default)

**Given** score-based assignment rules
**When** operator configures custom mapping
**Then** custom score-to-strategy mapping is used
**And** mapping is stored in Supabase config

**Given** operator override
**When** operator manually assigns strategy to position
**Then** manual assignment overrides score-based default
**And** override is logged

**Given** default strategy setting
**When** no score-based rule matches
**Then** configured default strategy is used

**Technical Notes:**
- FR27: Assign exit strategy based on signal score or operator override
- Implement in src/walltrack/core/execution/position_manager.py
- Config stored in Supabase

---

### Story 4.9: Position Tracking and Status

As an operator,
I want all open positions tracked with current status,
So that I have visibility into active trades.

**Acceptance Criteria:**

**Given** a trade is executed
**When** position is created
**Then** position record includes:
- position_id, wallet, token, entry_price, amount, entry_time
- signal_id (link to originating signal)
- exit_strategy_id, current stop/TP levels
- status: "open"

**Given** open position
**When** status is queried
**Then** current price is fetched
**And** unrealized PnL is calculated
**And** current profit multiplier is shown (e.g., x1.5)
**And** time held is displayed

**Given** position is partially closed
**When** take-profit level is hit
**Then** partial_exits array is updated
**And** remaining_amount is recalculated
**And** realized PnL for that portion is recorded

**Given** position is fully closed
**When** final exit occurs
**Then** status changes to "closed"
**And** total realized PnL is calculated
**And** position remains in history

**Technical Notes:**
- FR24: Track all open positions and their current status
- Implement positions table in Supabase
- Create trade_repo.py in src/walltrack/data/supabase/repositories/

---

### Story 4.10: Dashboard - Positions and Trade History

As an operator,
I want to view positions and trade history in the dashboard,
So that I can monitor trading activity.

**Acceptance Criteria:**

**Given** dashboard Positions tab
**When** operator views active positions
**Then** all open positions are listed with:
- Token, entry price, current price, PnL%, time held
- Exit strategy name, next TP level, stop-loss level
**And** positions can be sorted by PnL or entry time

**Given** an open position
**When** operator clicks on it
**Then** detailed view shows all position data
**And** price chart (if available) is displayed
**And** exit strategy can be modified (Story 4.11)

**Given** dashboard Trade History tab
**When** operator views history
**Then** closed trades are listed with:
- Token, entry/exit prices, PnL, duration, exit reason
**And** history can be filtered by date range, token, PnL
**And** pagination handles large datasets (NFR22)

**Given** pending signals view
**When** signals are trade-eligible but not yet executed
**Then** pending signals are shown with score and status
**And** operator can see why signal is pending (if applicable)

**Technical Notes:**
- FR41: View active positions and pending signals
- FR43: View trade history with full details
- Implement in src/walltrack/ui/components/positions.py

---

### Story 4.11: Dashboard - Exit Strategy Management

As an operator,
I want to manage exit strategies in the dashboard,
So that I can create, modify, and assign strategies.

**Acceptance Criteria:**

**Given** Exit Strategies panel in dashboard
**When** operator views strategies
**Then** all available strategies are listed (presets + custom)
**And** each shows: name, TP levels, stop-loss, trailing config, moonbag

**Given** operator creates custom strategy
**When** form is submitted
**Then** strategy is validated (all required fields, valid ranges)
**And** strategy is saved to Supabase
**And** strategy becomes available for assignment

**Given** operator edits existing custom strategy
**When** changes are saved
**Then** existing positions with this strategy are NOT affected
**And** new positions will use updated strategy
**And** operator is warned about this behavior

**Given** an open position
**When** operator changes its exit strategy
**Then** new strategy is applied
**And** stop-loss and TP levels are recalculated
**And** change is logged

**Given** default strategy assignment panel
**When** operator configures score-to-strategy mapping
**Then** mapping is saved
**And** future positions use new mapping

**Technical Notes:**
- FR49: Define custom exit strategies
- FR50: Assign default exit strategy and score-based overrides
- FR51: View and modify exit strategy for active positions
- Implement in src/walltrack/ui/components/exit_strategies.py

---

## Epic 5: Risk Management & Capital Protection

**Epic Goal:** System automatically protects capital with circuit breakers and alerts.

### Story 5.1: Drawdown Circuit Breaker

As an operator,
I want trading to pause automatically when drawdown exceeds threshold,
So that catastrophic losses are prevented.

**Acceptance Criteria:**

**Given** trading is active
**When** drawdown calculation runs
**Then** current drawdown = (peak_capital - current_capital) / peak_capital
**And** peak_capital is the highest value since system start or last reset

**Given** drawdown exceeds threshold (default 20%)
**When** circuit breaker triggers
**Then** all new trades are blocked immediately
**And** existing positions continue to be managed (exits still work)
**And** system status changes to "paused_drawdown"
**And** timestamp and drawdown value are recorded

**Given** circuit breaker is active
**When** new trade-eligible signal arrives
**Then** signal is logged with status "blocked_circuit_breaker"
**And** signal is NOT executed
**And** operator is notified

**Given** drawdown circuit breaker triggered
**When** operator reviews situation
**Then** manual reset is required to resume trading
**And** reset requires confirmation

**Technical Notes:**
- FR28: Pause all trading when drawdown exceeds threshold (20%)
- Implement in src/walltrack/core/risk/circuit_breaker.py
- Track peak_capital in Supabase
- Drawdown threshold configurable via dashboard

---

### Story 5.2: Consecutive Loss Position Size Reduction

As an operator,
I want position size reduced after consecutive losses,
So that losing streaks don't drain capital quickly.

**Acceptance Criteria:**

**Given** trade outcome is recorded
**When** outcome is a loss
**Then** consecutive_loss_count is incremented

**Given** consecutive_loss_count reaches threshold (default 3)
**When** next trade is sized
**Then** position size is reduced by configured factor (default 50%)
**And** reduction is logged with reason

**Given** reduced position sizing is active
**When** a trade is profitable
**Then** consecutive_loss_count resets to 0
**And** position sizing returns to normal
**And** recovery is logged

**Given** consecutive losses continue after reduction
**When** loss count reaches critical threshold (e.g., 5)
**Then** additional reduction or full pause may trigger
**And** operator is alerted

**Technical Notes:**
- FR29: Reduce position size after consecutive losses
- Implement in src/walltrack/core/risk/position_limits.py
- Track consecutive_loss_count per system (not per wallet)

---

### Story 5.3: Win Rate Circuit Breaker

As an operator,
I want trading to halt when win rate drops too low,
So that a broken strategy doesn't continue losing.

**Acceptance Criteria:**

**Given** trade history exists
**When** win rate is calculated
**Then** calculation uses rolling window of N trades (default 50)
**And** win_rate = winning_trades / total_trades in window

**Given** win rate falls below threshold (default 40%)
**When** threshold is breached
**Then** circuit breaker triggers
**And** all new trades are blocked
**And** system status changes to "paused_win_rate"
**And** current win rate and threshold are logged

**Given** win rate circuit breaker active
**When** operator reviews
**Then** recent trade analysis is available
**And** losing patterns can be investigated
**And** manual reset or recalibration is required

**Given** insufficient trade history (< N trades)
**When** win rate is checked
**Then** circuit breaker does not apply yet
**And** system continues with caution flag

**Technical Notes:**
- FR30: Halt trading when win rate falls below threshold over N trades
- Implement in src/walltrack/core/risk/circuit_breaker.py
- Window size and threshold configurable

---

### Story 5.4: Maximum Concurrent Position Limits

As an operator,
I want limits on concurrent open positions,
So that capital isn't over-concentrated.

**Acceptance Criteria:**

**Given** max_concurrent_positions config (default 5)
**When** new trade is about to execute
**Then** current open position count is checked

**Given** open positions < max limit
**When** trade execution proceeds
**Then** trade executes normally
**And** position count increments

**Given** open positions >= max limit
**When** new trade-eligible signal arrives
**Then** trade is blocked with reason "max_positions_reached"
**And** signal is logged but not executed
**And** operator can see queued/blocked signals

**Given** a position closes
**When** position count decreases
**Then** next eligible signal can execute (if any pending)
**And** FIFO order for pending signals (oldest first)

**Given** position limit config
**When** operator adjusts via dashboard
**Then** new limit takes effect immediately
**And** existing positions are not affected

**Technical Notes:**
- FR33: Enforce maximum concurrent position limits
- Implement in src/walltrack/core/risk/position_limits.py
- Consider per-token limits as future enhancement

---

### Story 5.5: Circuit Breaker Alert System

As an operator,
I want to be alerted immediately when circuit breakers trigger,
So that I can take action promptly.

**Acceptance Criteria:**

**Given** any circuit breaker triggers
**When** trigger is detected
**Then** alert is created with:
- Timestamp
- Circuit breaker type (drawdown, win_rate, manual)
- Current values vs thresholds
- Recommended actions

**Given** alert is created
**When** notification is sent
**Then** alert appears in dashboard Alerts panel immediately
**And** (optional) push notification sent if configured
**And** alert is logged to alerts table

**Given** alerts panel in dashboard
**When** operator views alerts
**Then** all recent alerts are listed (newest first)
**And** unacknowledged alerts are highlighted
**And** operator can acknowledge/dismiss alerts

**Given** system issue (not circuit breaker)
**When** critical error occurs (DB connection, API failure)
**Then** system alert is raised
**And** alert type indicates "system_error"
**And** error details are included

**Technical Notes:**
- FR31: Alert operator when circuit breaker triggers
- FR44: Receive alerts for circuit breakers and system issues
- Implement alerts table in Supabase
- Implement in src/walltrack/ui/components/alerts.py

---

### Story 5.6: Manual Pause and Resume Controls

As an operator,
I want to manually pause and resume trading,
So that I have ultimate control over the system.

**Acceptance Criteria:**

**Given** dashboard control panel
**When** operator clicks "Pause Trading"
**Then** confirmation dialog appears
**And** on confirm, system status changes to "paused_manual"
**And** all new trades are blocked
**And** pause timestamp and reason are recorded

**Given** system is paused (any reason)
**When** operator clicks "Resume Trading"
**Then** confirmation dialog appears with current status
**And** if paused due to circuit breaker, warning is shown
**And** on confirm, system status changes to "running"
**And** resume timestamp is recorded

**Given** system is paused
**When** existing positions need management
**Then** exit logic continues to function (stop-loss, take-profit)
**And** only new entries are blocked

**Given** manual pause
**When** operator provides reason
**Then** reason is stored with pause record
**And** reason is visible in system history

**Technical Notes:**
- FR32: Operator can manually pause and resume trading
- Implement in src/walltrack/core/risk/system_state.py
- System state stored in Supabase config table

---

### Story 5.7: Dashboard - System Status and Risk Configuration

As an operator,
I want to view system status and configure risk parameters,
So that I can monitor and control risk settings.

**Acceptance Criteria:**

**Given** dashboard Status panel
**When** operator views status
**Then** current system state is displayed (running, paused_*, etc.)
**And** if paused, reason and timestamp are shown
**And** health indicators show: DB connections, webhook status, last signal time

**Given** dashboard Risk Config panel
**When** operator views settings
**Then** all risk parameters are displayed:
- Drawdown threshold (%)
- Win rate threshold (%)
- Win rate window size (trades)
- Max concurrent positions
- Consecutive loss threshold
- Position size reduction factor

**Given** operator modifies risk parameter
**When** change is saved
**Then** new value is validated (within acceptable ranges)
**And** change takes effect immediately
**And** change is logged with previous and new values

**Given** system health check
**When** component is unhealthy
**Then** status indicator shows warning/error
**And** details are available on hover/click
**And** alert is raised if critical

**Given** last activity timestamps
**When** no signals for extended period (configurable, e.g., 48h)
**Then** "no_signals" warning is displayed
**And** system health check alert is raised

**Technical Notes:**
- FR39: Configure risk parameters
- FR40: View system status (running, paused, health indicators)
- Implement in src/walltrack/ui/components/status.py and config_panel.py
- NFR13: Health check endpoint and alerting

---

## Epic 6: Feedback Loop & Performance Analytics

**Epic Goal:** System continuously improves based on trade outcomes and operator can analyze performance.

### Story 6.1: Trade Outcome Recording

As an operator,
I want all trade outcomes recorded with full details,
So that performance can be analyzed and the system can learn.

**Acceptance Criteria:**

**Given** a position is closed (any exit reason)
**When** outcome is recorded
**Then** trade record includes:
- trade_id, position_id, signal_id
- entry_price, exit_price, amount
- realized_pnl (absolute and percentage)
- duration (time held)
- exit_reason (stop_loss, take_profit, trailing_stop, time_based, manual)
- wallet_address, token_address
- signal_score at entry

**Given** partial exit (take-profit level hit)
**When** partial outcome is recorded
**Then** partial trade record is created
**And** linked to parent position
**And** partial PnL is calculated

**Given** trade is recorded
**When** aggregate metrics are updated
**Then** running totals are recalculated:
- Total PnL
- Win count / Loss count
- Average win / Average loss
- Current win rate

**Given** trades table in Supabase
**When** historical queries are run
**Then** trades can be filtered by date, wallet, token, exit_reason
**And** query performance supports 1 year of data (NFR22)

**Technical Notes:**
- FR34: Record trade outcomes (entry price, exit price, PnL, duration)
- Extend trades table in Supabase
- Link to signals and positions tables
- Implement in src/walltrack/core/feedback/trade_recorder.py

---

### Story 6.2: Wallet Score Updates from Trade Outcomes

As an operator,
I want wallet scores automatically updated based on trade results,
So that wallet quality reflects recent performance.

**Acceptance Criteria:**

**Given** a trade outcome is recorded
**When** wallet score update runs
**Then** wallet's metrics are recalculated:
- Updated win rate (lifetime and rolling)
- Updated average PnL
- Updated trade count

**Given** trade was profitable
**When** score is updated
**Then** wallet score increases (weighted by profit magnitude)
**And** score increase is logged

**Given** trade was a loss
**When** score is updated
**Then** wallet score decreases (weighted by loss magnitude)
**And** if score drops below threshold, wallet is flagged (connects to Story 1.6)

**Given** wallet score update
**When** calculation completes
**Then** score is bounded between 0.0 and 1.0
**And** score history is preserved (for trend analysis)
**And** last_score_update timestamp is set

**Given** multiple trades from same wallet in short period
**When** scores are updated
**Then** each trade contributes to score
**And** batch updates are handled efficiently

**Technical Notes:**
- FR35: Update wallet scores based on trade outcomes
- Implement in src/walltrack/core/feedback/score_updater.py
- Score formula configurable (exponential decay, rolling window, etc.)

---

### Story 6.3: Scoring Model Weight Recalibration

As an operator,
I want the scoring model to recalibrate based on results,
So that the system improves its predictions over time.

**Acceptance Criteria:**

**Given** sufficient trade history (N trades, default 100)
**When** recalibration is triggered
**Then** correlation between each factor score and trade outcome is calculated:
- Wallet score vs actual PnL
- Cluster score vs actual PnL
- Token score vs actual PnL
- Context score vs actual PnL

**Given** recalibration analysis complete
**When** new weights are suggested
**Then** suggested weights are displayed to operator
**And** comparison to current weights is shown
**And** expected improvement is estimated

**Given** operator approves new weights
**When** weights are applied
**Then** scoring model uses new weights
**And** previous weights are archived
**And** recalibration timestamp is recorded

**Given** recalibration suggestion
**When** operator rejects or modifies
**Then** operator can adjust weights manually
**And** custom weights are applied instead

**Given** automatic recalibration mode (optional)
**When** enabled
**Then** weights auto-adjust within bounds
**And** changes are logged for review

**Technical Notes:**
- FR36: Recalibrate scoring model weights based on results
- Implement in src/walltrack/core/feedback/model_calibrator.py
- Use simple correlation analysis initially (ML optimization in V2)

---

### Story 6.4: Signal Accuracy Tracking

As an operator,
I want to track how accurate signals are over time,
So that I can assess system quality.

**Acceptance Criteria:**

**Given** signals that became trades
**When** accuracy is calculated
**Then** metrics include:
- Signal-to-win rate: % of signals that resulted in profitable trades
- Average score of winning signals vs losing signals
- Score threshold effectiveness (what threshold would maximize profit?)

**Given** signals that were NOT traded (below threshold)
**When** retrospective analysis runs (optional)
**Then** simulated outcome is estimated (what would have happened?)
**And** "missed opportunities" are identified
**And** "bullets dodged" are identified

**Given** accuracy tracking over time
**When** trend analysis runs
**Then** accuracy trend is calculated (improving, stable, declining)
**And** trend visualization is available in dashboard

**Given** accuracy by factor
**When** breakdown is requested
**Then** accuracy contribution by each factor is shown
**And** which factors are predictive vs noise is identified

**Technical Notes:**
- FR37: Track signal accuracy over time
- Implement in src/walltrack/core/feedback/accuracy_tracker.py
- Store accuracy metrics in Supabase

---

### Story 6.5: Pattern Analysis and Insights

As an operator,
I want the system to identify patterns in successful vs unsuccessful trades,
So that I can understand what works.

**Acceptance Criteria:**

**Given** trade history
**When** pattern analysis runs
**Then** patterns are identified across dimensions:
- Time of day patterns (best/worst hours)
- Day of week patterns
- Wallet patterns (which wallets perform best)
- Token characteristics (what token attributes correlate with success)
- Cluster patterns (cluster trades vs solo trades)

**Given** pattern is identified
**When** significance is calculated
**Then** statistical confidence is provided
**And** sample size is shown
**And** actionable insight is suggested

**Given** dashboard Pattern Analysis view
**When** operator views patterns
**Then** top patterns are displayed with:
- Pattern description
- Win rate for pattern
- Sample size
- Suggested action

**Given** negative patterns identified
**When** displayed to operator
**Then** warning is highlighted
**And** suggestion to adjust strategy is provided
**And** (optional) auto-adjustment suggestion

**Technical Notes:**
- FR38: Identify patterns in successful vs unsuccessful trades
- Implement in src/walltrack/core/feedback/pattern_analyzer.py
- Run as periodic batch job (daily or on-demand)

---

### Story 6.6: Dashboard - Performance Metrics and Analytics

As an operator,
I want comprehensive performance metrics in the dashboard,
So that I can monitor system profitability.

**Acceptance Criteria:**

**Given** dashboard Performance tab
**When** operator views metrics
**Then** key metrics are displayed:
- Total PnL (absolute and %)
- Win rate (overall and rolling)
- Total trades (wins/losses)
- Average win / Average loss
- Profit factor (gross profit / gross loss)
- Sharpe ratio (if calculable)

**Given** performance over time
**When** charts are displayed
**Then** PnL curve is shown (cumulative over time)
**And** daily/weekly PnL bars are shown
**And** win rate trend line is shown

**Given** date range selector
**When** operator selects range
**Then** all metrics recalculate for selected period
**And** comparison to previous period is available

**Given** breakdown views
**When** operator drills down
**Then** performance by wallet is available
**And** performance by exit strategy is available
**And** performance by time of day is available

**Given** dashboard loads
**When** data is fetched
**Then** response time is < 2 seconds (NFR3)
**And** charts render smoothly

**Technical Notes:**
- FR42: View performance metrics (PnL, win rate, trade count)
- Implement in src/walltrack/ui/components/performance.py
- Use plotly or similar for charts in Gradio

---

### Story 6.7: Backtest Preview

As an operator,
I want to preview how parameter changes would have performed historically,
So that I can make informed adjustments.

**Acceptance Criteria:**

**Given** backtest panel in dashboard
**When** operator configures backtest
**Then** parameters can be adjusted:
- Scoring weights
- Threshold
- Position sizing
- Exit strategy

**Given** backtest parameters set
**When** backtest is run
**Then** historical signals are re-scored with new parameters
**And** simulated trades are calculated
**And** simulated PnL is computed

**Given** backtest completes
**When** results are displayed
**Then** comparison shows:
- Actual performance vs simulated performance
- Number of trades difference
- Win rate difference
- PnL difference

**Given** backtest results
**When** operator reviews
**Then** trade-by-trade comparison is available
**And** "what would have changed" is highlighted

**Given** backtest is satisfactory
**When** operator wants to apply
**Then** "Apply These Settings" button is available
**And** confirmation shows what will change
**And** settings are updated on confirm

**Given** large historical dataset
**When** backtest runs
**Then** progress indicator shows status
**And** backtest completes in reasonable time (< 30 seconds for 6 months)

**Technical Notes:**
- FR47: Run backtest preview on parameter changes
- Implement in src/walltrack/core/feedback/backtester.py
- UI in src/walltrack/ui/components/backtest.py
- Consider caching historical signals for performance

---

## Epic 7: Live Simulation (Paper Trading)

**Goal:** Operator can run the system in live simulation mode, receiving real signals but executing simulated trades without risking capital.

**User Value:** The operator can validate the system's performance in real-time conditions before committing real capital, building confidence and identifying issues without financial risk.

**FRs Covered:** FR55, FR56, FR57, FR58, FR59, FR60

**Includes:**
- Execution mode configuration (live/simulation)
- Simulated trade executor (mock Jupiter)
- Position tracking for simulated trades
- Real-time P&L calculation using market prices
- Dashboard simulation mode view
- Simulation alerts and logging

**Stories:**
- 7.1: Execution Mode Configuration
- 7.2: Simulated Trade Executor
- 7.3: Simulation Position Tracker
- 7.4: Real-Time P&L Calculator
- 7.5: Dashboard Simulation Mode
- 7.6: Simulation Alerts & Logging

---

### Story 7.1: Execution Mode Configuration

As an operator,
I want to configure the system to run in live or simulation mode,
So that I can test the system without risking real capital.

**Acceptance Criteria:**

**Given** the system configuration
**When** EXECUTION_MODE is set to "simulation"
**Then** all trades are simulated (no real swaps)
**And** all signals are processed normally
**And** UI indicates simulation mode clearly

**Given** simulation mode is active
**When** a trade signal is generated
**Then** the signal is processed through the full pipeline
**And** instead of Jupiter execution, simulated execution occurs
**And** position is tracked as simulated

**Given** operator wants to switch modes
**When** mode is changed via config or dashboard
**Then** system restarts in new mode
**And** existing positions are preserved
**And** clear warning is shown when switching to live

**Given** system is in simulation mode
**When** dashboard loads
**Then** prominent "SIMULATION MODE" banner is displayed
**And** all P&L figures are marked as simulated
**And** no real wallet balance changes occur

**Technical Notes:**
- FR55: System can run in simulation mode without executing real trades
- Config: EXECUTION_MODE=live|simulation
- src/walltrack/config/settings.py: execution_mode field
- Inject mode into trade execution service

---

### Story 7.2: Simulated Trade Executor

As an operator,
I want trades to be simulated realistically when in simulation mode,
So that I get accurate performance estimates.

**Acceptance Criteria:**

**Given** simulation mode is active
**When** trade execution is triggered
**Then** SimulatedTradeExecutor is used instead of JupiterExecutor
**And** trade is recorded with simulated=True flag
**And** execution price uses real-time market price

**Given** a buy signal in simulation
**When** simulated trade executes
**Then** current token price is fetched from DexScreener
**And** slippage is simulated (configurable, default 1%)
**And** entry price = market_price * (1 + slippage)
**And** trade record is created

**Given** a sell signal in simulation
**When** simulated trade executes
**Then** current token price is fetched
**And** slippage is simulated
**And** exit price = market_price * (1 - slippage)
**And** P&L is calculated from simulated entry

**Given** simulated trade completes
**When** trade is logged
**Then** all standard trade fields are populated
**And** simulated=True is clearly marked
**And** no blockchain transaction is created

**Technical Notes:**
- FR56: System can simulate trade execution with realistic pricing
- src/walltrack/core/trading/simulated_executor.py
- Interface matches JupiterExecutor for easy swapping
- Uses DexScreener for price data

---

### Story 7.3: Simulation Position Tracker

As an operator,
I want simulated positions to be tracked separately from real positions,
So that simulation data doesn't interfere with live trading.

**Acceptance Criteria:**

**Given** simulation mode is active
**When** a new simulated position is opened
**Then** position is stored with simulated=True
**And** position appears in simulation position list
**And** position does not appear in live position list

**Given** simulated positions exist
**When** position monitoring runs
**Then** stop-loss levels are checked against real prices
**And** take-profit levels are checked against real prices
**And** exits are triggered based on real market conditions

**Given** a simulated position hits stop-loss
**When** exit is triggered
**Then** simulated sell executes at market price
**And** P&L is recorded
**And** position is closed

**Given** switching from simulation to live
**When** mode change occurs
**Then** simulated positions remain in database
**And** simulated positions are excluded from live trading
**And** historical simulation data is preserved

**Technical Notes:**
- FR57: System can track simulated positions separately
- Add simulated: bool field to Position model
- Filter by simulated flag in all queries
- PositionService.get_active(simulated=True/False)

---

### Story 7.4: Real-Time P&L Calculator

As an operator,
I want to see real-time P&L for simulated positions using live market prices,
So that I can evaluate performance as if trades were real.

**Acceptance Criteria:**

**Given** open simulated positions exist
**When** P&L calculation runs
**Then** current market price is fetched for each token
**And** unrealized P&L = (current_price - entry_price) * quantity
**And** P&L is displayed in dashboard

**Given** multiple simulated positions
**When** portfolio P&L is calculated
**Then** total unrealized P&L is summed
**And** total realized P&L (from closed) is summed
**And** overall simulation P&L is displayed

**Given** price data is unavailable
**When** P&L calculation fails for a token
**Then** last known price is used
**And** warning indicates stale price
**And** staleness duration is shown

**Given** P&L refresh interval
**When** interval elapses (default 30s)
**Then** all position prices are updated
**And** P&L values refresh in dashboard
**And** P&L history is logged for tracking

**Technical Notes:**
- FR58: System can calculate real-time P&L for simulated positions
- src/walltrack/core/simulation/pnl_calculator.py
- Use DexScreener/Birdeye for live prices
- Cache prices with 30s TTL

---

### Story 7.5: Dashboard Simulation Mode

As an operator,
I want a dedicated dashboard view for simulation mode,
So that I can monitor simulated trading performance.

**Acceptance Criteria:**

**Given** simulation mode is active
**When** dashboard loads
**Then** "SIMULATION MODE" banner is prominently displayed
**And** all metrics are labeled as simulated
**And** simulation-specific tabs are available

**Given** simulation dashboard
**When** operator views positions tab
**Then** only simulated positions are shown
**And** real-time P&L for each position is displayed
**And** simulated trade history is accessible

**Given** simulation dashboard
**When** operator views performance tab
**Then** simulated win rate is calculated
**And** simulated total P&L is shown
**And** simulated vs actual comparison (if both exist) is available

**Given** simulation mode
**When** operator views signals
**Then** signal processing is identical to live
**And** "Would have traded" indicators are shown
**And** simulation decisions are logged

**Technical Notes:**
- FR59: Operator can view simulation dashboard
- src/walltrack/ui/components/simulation.py
- Reuse existing components with simulation filter
- Add simulation_mode check to all UI components

---

### Story 7.6: Simulation Alerts & Logging

As an operator,
I want simulation activity to be logged and alerts to be generated,
So that I can review simulation performance over time.

**Acceptance Criteria:**

**Given** simulation mode is active
**When** any simulated trade occurs
**Then** detailed log entry is created
**And** log includes: signal, decision, simulated price, P&L
**And** logs are tagged with simulation=True

**Given** circuit breaker would trigger in simulation
**When** threshold is reached
**Then** circuit breaker state is tracked separately
**And** alert is generated (marked as simulation)
**And** operator is notified of simulated circuit breaker

**Given** simulation summary is requested
**When** daily summary runs
**Then** simulation performance report is generated
**And** comparison to live mode (if any) is included
**And** report is sent via configured alerts

**Given** historical simulation data
**When** operator queries logs
**Then** all simulated activity is retrievable
**And** filtering by date range is available
**And** export to CSV is available

**Technical Notes:**
- FR60: System logs and alerts for simulation activity
- Extend existing logging with simulated tag
- src/walltrack/core/simulation/alerts.py
- Separate simulation alert channel optional

---

## Epic 8: Backtesting & Scenario Analysis

**Goal:** Operator can run comprehensive backtests on historical data with multiple scenarios and parameter optimization.

**User Value:** The operator can test trading strategies on historical data, compare multiple parameter configurations, and find optimal settings before deploying changes to live or simulation mode.

**FRs Covered:** FR61, FR62, FR63, FR64, FR65, FR66, FR67

**Includes:**
- Historical data collection and storage
- Backtest engine with timeline replay
- Scenario configuration system
- Batch backtest execution
- Scenario comparison and metrics
- Parameter optimization (grid search)
- Dashboard for multi-scenario analysis

**Stories:**
- 8.1: Historical Data Collector
- 8.2: Backtest Engine Core
- 8.3: Scenario Configuration
- 8.4: Batch Backtest Runner
- 8.5: Scenario Comparison & Metrics
- 8.6: Parameter Optimization
- 8.7: Dashboard Backtest Multi-Scenarios

---

### Story 8.1: Historical Data Collector

As an operator,
I want to collect and store historical signal and price data,
So that I can run backtests on past market conditions.

**Acceptance Criteria:**

**Given** the system is running
**When** signals are processed
**Then** all signal data is stored with timestamp
**And** token prices at signal time are recorded
**And** subsequent price movements are tracked

**Given** historical data collection is enabled
**When** a new token is encountered
**Then** historical price data is fetched (if available)
**And** data is stored in historical_prices table
**And** gaps in data are noted

**Given** price tracking for active signals
**When** price update runs (every 5 minutes for 24h)
**Then** token prices are fetched and stored
**And** data enables P&L calculation at any point
**And** storage is optimized (aggregate after 24h)

**Given** historical data query
**When** backtest requests data for date range
**Then** signals for that range are returned
**And** price data for signal tokens is returned
**And** wallet/cluster state at that time is reconstructable

**Technical Notes:**
- FR61: System can collect and store historical data for backtesting
- Tables: historical_signals, historical_prices
- Store snapshots of scoring context
- Consider data retention policy (6 months default)

---

### Story 8.2: Backtest Engine Core

As an operator,
I want a backtest engine that replays historical signals with configurable parameters,
So that I can see how different settings would have performed.

**Acceptance Criteria:**

**Given** historical data exists for a date range
**When** backtest is initiated with parameters
**Then** signals are replayed in chronological order
**And** each signal is scored with provided parameters
**And** trade decisions are made based on new scores

**Given** a signal during backtest replay
**When** scoring is applied
**Then** wallet score uses historical value (or current if unavailable)
**And** cluster amplification uses historical cluster state
**And** token score uses historical token data

**Given** trade decision in backtest
**When** simulated trade executes
**Then** entry price uses historical price at signal time
**And** exit is determined by strategy and subsequent prices
**And** P&L is calculated from historical prices

**Given** backtest completes
**When** results are compiled
**Then** all simulated trades are listed
**And** aggregate metrics are calculated
**And** comparison to actual results (if any) is available

**Technical Notes:**
- FR62: System can replay historical signals with different parameters
- src/walltrack/core/backtest/engine.py
- BacktestEngine.run(date_range, parameters) -> BacktestResult
- Must handle missing data gracefully

---

### Story 8.3: Scenario Configuration

As an operator,
I want to define backtest scenarios with specific parameter sets,
So that I can organize and reuse test configurations.

**Acceptance Criteria:**

**Given** scenario configuration interface
**When** operator creates a scenario
**Then** scenario has a name and description
**And** all configurable parameters can be set:
  - Scoring weights (wallet, cluster, token, context)
  - Score threshold
  - Position sizing parameters
  - Exit strategy parameters
  - Risk parameters

**Given** scenario is saved
**When** scenario is stored
**Then** scenario is persisted in database
**And** scenario can be loaded for future backtests
**And** scenario can be duplicated and modified

**Given** scenario parameters
**When** displayed in UI
**Then** clear comparison to current live settings
**And** differences are highlighted
**And** scenario validation ensures valid parameter ranges

**Given** multiple scenarios
**When** scenarios are listed
**Then** all saved scenarios are shown
**And** scenarios can be organized by category/tag
**And** scenarios can be imported/exported (JSON)

**Technical Notes:**
- FR63: Operator can define and save backtest scenarios
- Table: backtest_scenarios
- ScenarioConfig Pydantic model
- src/walltrack/core/backtest/scenario.py

---

### Story 8.4: Batch Backtest Runner

As an operator,
I want to run multiple backtest scenarios in batch,
So that I can compare different configurations efficiently.

**Acceptance Criteria:**

**Given** multiple scenarios are selected
**When** batch backtest is started
**Then** all scenarios are queued for execution
**And** progress indicator shows current/total
**And** scenarios run in parallel (configurable workers)

**Given** batch backtest is running
**When** a scenario completes
**Then** results are stored immediately
**And** progress updates in real-time
**And** failed scenarios are logged and skipped

**Given** batch backtest completes
**When** all scenarios finish
**Then** summary of all results is available
**And** comparison view is generated
**And** notification is sent to operator

**Given** long-running batch
**When** operator wants to cancel
**Then** cancel button stops remaining scenarios
**And** completed results are preserved
**And** partial batch can be resumed

**Technical Notes:**
- FR64: System can run multiple backtests in batch
- src/walltrack/core/backtest/batch_runner.py
- Use asyncio for parallel execution
- Store results with batch_id for grouping

---

### Story 8.5: Scenario Comparison & Metrics

As an operator,
I want to compare results across multiple scenarios,
So that I can identify the best performing configuration.

**Acceptance Criteria:**

**Given** multiple backtest results exist
**When** comparison view is opened
**Then** key metrics are shown side-by-side:
  - Total P&L
  - Win rate
  - Total trades
  - Max drawdown
  - Profit factor
  - Sharpe ratio

**Given** comparison table
**When** metrics are displayed
**Then** best value per metric is highlighted
**And** ranking by each metric is available
**And** overall ranking (weighted) is calculated

**Given** detailed comparison
**When** operator drills down
**Then** trade-by-trade differences are shown
**And** divergence points are identified (where scenarios differ)
**And** statistical significance is indicated

**Given** comparison results
**When** operator selects winner
**Then** winning scenario parameters can be applied to live
**And** confirmation shows all changes
**And** audit log records parameter change source

**Technical Notes:**
- FR65: Operator can compare backtest results across scenarios
- src/walltrack/core/backtest/comparison.py
- ScenarioComparison model with all metrics
- Support sorting and filtering

---

### Story 8.6: Parameter Optimization (Grid Search)

As an operator,
I want to automatically search for optimal parameters,
So that I can find the best configuration without manual testing.

**Acceptance Criteria:**

**Given** parameter optimization interface
**When** operator configures search
**Then** parameter ranges can be specified:
  - score_threshold: [0.65, 0.70, 0.75, 0.80]
  - stop_loss_pct: [30, 40, 50]
  - position_size_sol: [0.1, 0.2, 0.3]
**And** total combinations are calculated and shown

**Given** grid search is started
**When** optimization runs
**Then** all parameter combinations are tested
**And** progress shows current/total combinations
**And** early results are displayed as they complete

**Given** optimization completes
**When** results are compiled
**Then** best configuration by target metric is identified
**And** Pareto frontier (multi-objective) is shown
**And** parameter sensitivity analysis is available

**Given** large search space
**When** >100 combinations exist
**Then** warning is shown about execution time
**And** sampling option is available (test subset)
**And** smart search option (Bayesian) is available (future)

**Given** optimization result
**When** best params are identified
**Then** one-click apply to live/simulation is available
**And** comparison to current settings is shown
**And** recommendation confidence is indicated

**Technical Notes:**
- FR66: System can optimize parameters via grid search
- src/walltrack/core/backtest/optimizer.py
- GridSearchOptimizer with configurable objective
- Consider async execution for large searches

---

### Story 8.7: Dashboard Backtest Multi-Scenarios

As an operator,
I want a dashboard interface for backtest scenario management,
So that I can easily run and compare backtests.

**Acceptance Criteria:**

**Given** dashboard backtest tab
**When** operator navigates to it
**Then** three sub-tabs are available:
  - Scenarios (create/edit/manage)
  - Run Backtest (single or batch)
  - Results & Comparison

**Given** Scenarios tab
**When** operator views
**Then** list of saved scenarios is shown
**And** create new scenario button is available
**And** edit/delete/duplicate actions are available

**Given** Run Backtest tab
**When** operator configures run
**Then** date range selector is available
**And** scenario multi-select is available
**And** optimization toggle with parameter ranges is available
**And** "Start Backtest" button launches execution

**Given** backtest is running
**When** progress is displayed
**Then** real-time progress bar shows completion
**And** live results preview as scenarios complete
**And** cancel button is available

**Given** Results tab
**When** completed backtests exist
**Then** list of past batches is shown
**And** selecting a batch shows comparison view
**And** export to CSV/PDF is available

**Given** comparison view in dashboard
**When** results are displayed
**Then** sortable comparison table is shown
**And** charts visualize key metrics
**And** "Apply Best Settings" action is available

**Technical Notes:**
- FR67: Operator can manage backtests via dashboard
- src/walltrack/ui/components/backtest_scenarios.py
- Reuse plotly charts from performance dashboard
- Store backtest results with timestamps for history
