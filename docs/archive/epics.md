---
stepsCompleted: ["step-01-validate-prerequisites", "step-02-design-epics", "step-03-create-stories", "step-04-final-validation"]
workflowStatus: "completed"
validationDate: "2026-01-05"
inputDocuments:
  - "docs/prd.md"
  - "docs/architecture.md"
  - "docs/ux-design-specification.md"
  - "docs/database-design/README.md"
  - "docs/database-design/01-config.md"
  - "docs/database-design/02-exit-strategies.md"
  - "docs/database-design/03-wallets.md"
  - "docs/database-design/04-tokens.md"
  - "docs/database-design/05-signals.md"
  - "docs/database-design/06-orders.md"
  - "docs/database-design/07-positions.md"
  - "docs/database-design/08-performance.md"
  - "docs/database-design/09-circuit-breaker-events.md"
---

# walltrack - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for walltrack, decomposing the requirements from the PRD, UX Design, Architecture, and Database Design into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR-1: Watchlist Management**
- Manual CRUD operations for managing wallet addresses in the watchlist
- Users can add/remove/edit wallet addresses
- Each wallet has configurable mode (simulation/live)
- Wallet status visible in Dashboard (signals count, win rate, mode)
- Changes persist in Supabase database

**FR-2: Real-Time Signal Detection**
- Helius webhooks deliver real-time swap notifications for all watchlist wallets
- Swap events trigger signal processing pipeline
- Webhook status visible in Config UI (connected/disconnected, last signal timestamp)
- Signal logs stored in Supabase for audit trail

**FR-3: Token Safety Analysis**
- Automated scoring system to detect rug pulls and honeypots before creating positions
- Safety scoring uses 4 checks: Liquidity (≥$50K), Holder Distribution (top 10 < 80%), Contract Analysis (honeypot detection), Age (≥24h)
- Weighted average score calculated (each check = 25%)
- Configurable threshold (default 0.60)
- Signals below threshold filtered out automatically
- Safety scores logged and visible in UI

**FR-4: Position Creation & Management**
- Create positions automatically from safe signals with dual-mode execution (simulation/live)
- Simulation mode: Full pipeline (signal → position → exit) without Jupiter API execution
- Live mode: Full pipeline WITH Jupiter swap execution
- Position data includes: entry price, amount, source wallet, timestamp, mode
- Positions visible in Dashboard with real-time status

**FR-5: Price Monitoring**
- Track token prices for active positions using Jupiter Price API V3 (primary) and DexScreener API (fallback) to trigger exit strategies
- Polling intervals: 30-60s for all active position tokens
- Price updates logged and trigger exit strategy evaluation
- Accuracy within ±1% of actual market price
- Monitoring continues until position closed

**FR-6: Exit Strategy Execution**
- Multiple exit strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) with per-wallet configuration and per-position overrides
- Stop-loss triggers first (capital protection priority)
- Mirror-exit overrides scaling if source wallet sells
- Trailing-stop activates after profit threshold
- Scaling-out executes at configured levels
- Per-wallet default strategies configurable in UI
- Per-position overrides available in Dashboard

**FR-7: Wallet Activity Monitoring**
- Monitor source wallet sales via Helius webhooks to trigger mirror-exit strategy
- Helius webhooks monitor ALL source wallets for sell events
- Sell events matched against active positions
- Mirror-exit triggers position close if enabled
- Execution logged for audit trail

**FR-8: Performance Tracking & Analytics**
- Track win rate, PnL, and signal analytics per wallet for data-driven curation
- Win rate calculated per wallet: (profitable trades / total trades)
- PnL aggregated per wallet: sum of all closed position profits/losses
- Signal counts tracked with time windows (all/30d/7d/24h)
- Analytics visible in Dashboard with sortable columns
- Historical data persisted in Supabase

**FR-9: System Configuration & Status**
- Centralized configuration interface for system parameters and status monitoring
- Config UI provides: capital amount, risk % per trade, safety threshold
- Webhook status visible (connected/disconnected, last signal)
- Circuit breaker status visible (active/paused, reason)
- Configuration changes persist and apply immediately

### Non-Functional Requirements

**NFR-1: Performance**
- System must execute trades within 5 seconds of signal receipt to capture price before significant movement (P95)
- Webhook → Signal processing → Trade execution < 5 seconds (P95)
- Price monitoring polling: 30-60s intervals (sufficient for position management)
- Dashboard loads < 2 seconds (operator experience)

**NFR-2: Reliability**
- System uptime ≥ 95% to ensure 24/7 opportunity capture
- System restarts automatically on crash
- Health checks monitor critical components (webhooks, API connections, database)
- Alerting for prolonged downtime (>30 minutes)
- Circuit breakers prevent cascade failures

**NFR-3: Security**
- Wallet private keys must be securely managed with no exposure in logs or UI
- Private keys stored encrypted at rest (Supabase encryption or environment variables)
- No private key exposure in logs, error messages, or UI
- Jupiter API calls signed securely without key exposure
- Audit trail for all wallet operations

**NFR-4: Data Integrity**
- All trade execution, PnL, and performance data must be accurate and auditable
- Atomic database transactions for position lifecycle (create → update → close)
- Audit trail for all state changes (signals, positions, exits)
- Data validation on all inputs (wallet addresses, prices, amounts)
- Reconciliation checks for PnL calculations

**NFR-5: Observability**
- Complete visibility into system state and trade decisions for operator trust
- All signals logged with safety scores and filter decisions
- All positions logged with entry/exit details and PnL
- Circuit breaker triggers logged with reason
- Dashboard provides real-time system state view
- Historical logs queryable for debugging

**NFR-6: Maintainability**
- Codebase must be simple, well-documented, and testable for solo operator maintenance
- Test coverage ≥ 70% (unit + integration + E2E)
- Clear separation of concerns (API clients, data layer, business logic)
- Type hints throughout codebase (Pydantic models)
- README with architecture overview and setup instructions

**NFR-7: Scalability**
- System must handle 10-20 watchlist wallets generating 50-400 signals per day
- Webhook processing handles burst of 10 signals within 30 seconds
- Database queries optimized for dashboard load (indexes on wallet_id, timestamp)
- Supabase free tier sufficient for MVP data volumes

**NFR-8: Compliance Readiness (Future)**
- System architecture must support future KYC/AML compliance if productized
- User data model extensible for KYC information
- Audit trail already captures required transaction data
- Architecture supports multi-tenancy (future)

### Additional Requirements

**Architecture Requirements:**

**AR-1: Technology Stack**
- Python 3.11+ with type hints
- FastAPI for API endpoints (async support)
- Pydantic v2 for data validation
- httpx for async HTTP clients
- Supabase (PostgreSQL) for application data
- Helius API for Solana webhooks (swap notifications, wallet monitoring)
- Jupiter API for decentralized swap execution (live mode) + price monitoring (primary)
- DexScreener API for fallback price monitoring
- Gradio for rapid operator interface development
- Pytest for unit + integration tests
- Playwright for E2E UI tests (separate from other tests)
- uv for dependency management

**AR-2: Database Schema Design**
- 9 tables required: config (Configuration Singleton), exit_strategies (Catalog), wallets (Registry), tokens (Read-Through Cache), signals (Event Sourcing), orders (Command Log), positions (Aggregate Root), performance (Materialized View), circuit_breaker_events (Event Sourcing)
- All table creation via SQL migration files in `src/walltrack/data/supabase/migrations/`
- Migrations numbered sequentially (001_config_table.sql, 002_exit_strategies_table.sql, etc.)
- Rollback scripts included as comments in each migration
- Each migration includes COMMENT ON TABLE and COMMENT ON COLUMN for documentation

**AR-3: Project Structure - Custom Layered Architecture**
- src/walltrack/core/ - Business logic (no external dependencies)
- src/walltrack/services/ - External API clients (Helius, Jupiter, DexScreener)
- src/walltrack/data/ - Data layer (Pydantic models, repositories, Supabase migrations)
- src/walltrack/workers/ - Background workers (price monitor, webhook processor)
- src/walltrack/ui/ - Gradio dashboard interface (Dashboard, Watchlist, Config tabs)
- src/walltrack/config/ - Configuration management
- tests/unit/ - Unit tests with mocked dependencies
- tests/integration/ - Integration tests (real DB, mocked APIs)
- tests/e2e/ - Playwright E2E tests (run separately)

**AR-4: Repository Pattern**
- Abstract Supabase behind repository interfaces for testability
- Repository interfaces define contracts for data operations
- Supabase-specific implementations separate from business logic
- Mock repositories in unit tests

**AR-5: External API Client Pattern**
- httpx AsyncClient with retry logic (tenacity) + circuit breaker
- Connection pooling (reuse connections)
- Timeout configuration (prevent hanging requests)
- Retry on transient failures (exponential backoff)
- Consistent error handling across all clients

**AR-6: Secret Management**
- Use python-dotenv with `.env` file for all secrets
- .env gitignored (never committed)
- .env.example provides template for setup
- Required secrets: SUPABASE_URL, SUPABASE_KEY, HELIUS_API_KEY, WALLET_PRIVATE_KEY, DEXSCREENER_API_KEY (if required), JUPITER_API_KEY (if required)

**AR-7: Structured Logging**
- structlog for all critical operations
- JSON format (queryable)
- Log all: signals received, positions created, trades executed, exits triggered
- Custom logging filter to NEVER log private keys

**AR-8: Deployment Strategy**
- Local machine deployment (Linux/Windows)
- systemd (Linux) or Windows Service for auto-restart
- Rotating file logs (max 100MB, keep 7 days)
- Health check endpoint (FastAPI /health)
- No CI/CD pipeline in MVP (manual testing)

**AR-9: Testing Strategy Separation**
- Unit tests with mocked external APIs (≥70% coverage target)
- Integration tests for data layer and API clients
- E2E tests with Playwright (separate test run to avoid interference)
- Testing commands: `uv run pytest tests/unit tests/integration -v` (fast, ~40s) and `uv run pytest tests/e2e -v` (separate, opens browser)

**UX Design Requirements:**

**UXR-1: Dual-Mode Visual Clarity**
- Clear visual distinction between simulation and live modes across all UI elements
- Color coding: Blue (#3B82F6) for simulation, Amber (#F59E0B) for live
- Mode badges visible in every table row and metric card
- No confusion about "which mode am I in?"—always visible

**UXR-2: Dashboard Performance Metrics**
- 4 key metrics at-a-glance: Win Rate, PnL Total, Capital Utilization, Active Wallets
- Each metric split by mode (🔵 Simulation | 🟠 Live)
- Large text, spacious cards (H2 24px for metric values)
- Metrics visible immediately without scrolling

**UXR-3: Three-Tab Navigation Structure**
- Persistent tab navigation: Dashboard, Watchlist, Config
- Active tab highlighted (Blue 500 underline)
- Gradio gr.Tabs() implementation

**UXR-4: Dashboard Layout - Monitoring First**
- Performance Metrics (4 cards, horizontal row using gr.Row)
- Active Positions Table (gr.Dataframe, dense 48px rows, 7 columns: Token, Entry, Current, PnL, Mode, Status, Actions)
- Table + Sidebar pattern: Click row → Sidebar appears with position detail
- Sidebar hidden by default, toggle on table.select()

**UXR-5: Watchlist Layout - Curation Interface**
- Action bar: [+ Add Wallet] button + Filter dropdown + Sort dropdown
- Wallets Table (3/4 width): Label, Address, Mode, Status, Signals, Win Rate, PnL
- Sidebar (1/4 width, hidden): Wallet Performance, Recent Signals, [Promote] [Remove] buttons
- Click row → Show wallet detail sidebar

**UXR-6: Config Layout - Accordion Sections**
- Accordion-style sections using gr.Accordion: Exit Strategies, Risk Limits, API Keys
- Form-based layout (gr.Form for each section)
- Comfortable spacing (24px padding, 40px input height)

**UXR-7: Progressive Disclosure Pattern**
- Summary always visible (table with essential columns)
- Details on-demand (click row → sidebar with comprehensive data)
- No information overload in default view
- Advanced settings hidden in Config tab (< 5% of daily interactions)

**UXR-8: Transparency Indicators**
- Safety scores visible for each signal
- Exit trigger reasoning accessible on-demand
- Performance attribution showing which wallet/strategy succeeded
- Audit trails for verification
- "Why?" accessible without clutter

**UXR-9: Responsive Behavior**
- Desktop (1200px+): Full 3-column layout
- Tablet (768-1199px): Table + Sidebar (sidebar overlays on click)
- Mobile (<768px): Single column, sidebar fullscreen modal

**Database Design Requirements:**

**DBR-1: Architectural Patterns Implementation**
- Configuration Singleton pattern for `config` table (1 row only)
- Catalog pattern for `exit_strategies` (DRY templates, reusable)
- Registry pattern for `wallets` (watchlist with discovery + performance baseline)
- Read-Through Cache pattern for `tokens` (safety analysis cache with TTL invalidation)
- Event Sourcing pattern for `signals` and `circuit_breaker_events` (immutable audit trail)
- Command Log pattern for `orders` (retry mechanism)
- Aggregate Root pattern for `positions` (PnL tracking central with separation realized/unrealized)
- Materialized View pattern for `performance` (batch refresh daily)

**DBR-2: ADR-001 - Helius Global Webhook**
- Context: Helius ne permet pas 1 webhook par wallet
- Decision: Un seul webhook global pour tous les wallets
- Implementation: Batch sync toutes les 5min pour mettre à jour la liste d'adresses surveillées
- Field tracking: `wallets.helius_synced_at`, `wallets.helius_sync_status`

**DBR-3: ADR-002 - Exit Strategy Override au niveau Position**
- Context: Besoin de flexibilité par position, pas par wallet
- Decision: `exit_strategy_override` (JSONB) dans `positions`, pas dans `wallets`
- Rationale: Immutabilité (snapshot à création position) + override granulaire
- Avoid: Changing wallet strategy affecting open positions

**DBR-4: ADR-003 - Performance Materialized View**
- Context: Calculs temps réel trop coûteux pour dashboard
- Decision: Précalcul quotidien des métriques agrégées (fenêtres glissantes)
- Consequence: Dashboard ultra-rapide, mais données refresh 1x/jour
- Acceptable for: Operator daily review workflow

**DBR-5: ADR-004 - Circuit Breaker Non-Closing**
- Context: Protéger contre pertes excessives sans panic selling
- Decision: Circuit breaker bloque NOUVELLES positions, continue exit strategies sur positions ouvertes
- Rationale: Risk management sans force liquidation
- Fields: `circuit_breaker_events` table with event_type, triggered_at, reason

**DBR-6: Wallet Discovery & Performance Baseline**
- Capture initial metrics at wallet discovery: `initial_win_rate_percent`, `initial_trades_observed`, `initial_pnl_usd`
- Purpose: Detect fake wallets (wash trading) by comparing initial vs actual performance after 30 days
- Query pattern: Compare `initial_win_rate_percent` with `performance.win_rate` to flag degradation

**DBR-7: Token Safety Cache with Multi-Source Fallback**
- Primary source: RugCheck API
- Secondary: Helius Metadata API
- Tertiary: DexScreener API
- Cache invalidation: TTL > 1h (memecoin data doesn't change rapidly once analyzed)
- Fields: `tokens.safety_score`, `tokens.analyzed_at`, `tokens.data_source`

**DBR-8: Signal Filtering & Audit Trail**
- All signals logged (even filtered ones) for transparency
- Fields: `signals.filtered`, `signals.filter_reason` (e.g., "safety_score_below_threshold", "duplicate_signal")
- Purpose: Operator can audit WHY signals were rejected

**DBR-9: Orders Retry Mechanism**
- Track execution attempts: `orders.retry_count`, `orders.last_error`
- Max retries: 3 attempts with exponential backoff
- Final state: `orders.status` = 'failed' if all retries exhausted
- Purpose: Handle transient Jupiter API failures without losing trades

**DBR-10: Position PnL Separation**
- Realized PnL: `positions.realized_pnl_usd` (locked in from partial exits)
- Unrealized PnL: Calculated on-demand from `current_price` vs `entry_price`
- Formula: `realized_pnl_usd = SUM((exit_price - entry_price) * exit_amount)` for all partial exits

### FR Coverage Map

**FR-1 (Watchlist Management):** Epic 2 - Smart Money Discovery & Token Safety
**FR-2 (Real-Time Signal Detection):** Epic 2 - Helius webhooks integration
**FR-3 (Token Safety Analysis):** Epic 2 - Multi-source safety scoring (RugCheck → Helius → DexScreener)
**FR-4 (Position Creation & Management):** Epic 3 - Dual-mode position lifecycle (simulation/live)
**FR-5 (Price Monitoring):** Epic 3 - Jupiter Price API V3 + DexScreener fallback
**FR-6 (Exit Strategy Execution):** Epic 3 - 4 strategies with priority logic (stop-loss, trailing-stop, scaling-out, mirror-exit)
**FR-7 (Wallet Activity Monitoring):** Epic 4 - Mirror-exit triggers via Helius
**FR-8 (Performance Tracking & Analytics):** Epic 4 - Per-wallet metrics and data-driven curation
**FR-9 (System Configuration & Status):** Epic 5 - Centralized config + health monitoring

## Epic List

### Epic 1: Data Foundation & UI Framework
Operator can visualize the system structure and interact with mockup data, validating the information architecture before connecting real logic. All 9 database tables migrated with comprehensive mock data, complete Gradio UI (Dashboard, Watchlist, Config tabs) displaying mock data with table + sidebar interactions.

**FRs covered:** Foundation for ALL (FR-1 to FR-9)
**Additional Requirements:** AR-2 (Database Schema), AR-3 (Project Structure), DBR-1 to DBR-10 (All DB patterns & ADRs), UXR-1 to UXR-9 (All UI layouts)

### Epic 2: Smart Money Discovery & Token Safety
Operator can discover smart money wallets via GMGN, add them to watchlist, receive real-time swap signals via Helius webhooks, and automatically filter unsafe tokens before any positions are created.

**FRs covered:** FR-1 (Watchlist Management), FR-2 (Real-Time Signal Detection), FR-3 (Token Safety Analysis)
**Additional Requirements:** AR-5 (External API Client Pattern), DBR-2 (ADR-001 Helius Global Webhook), DBR-7 (Token Safety Cache), DBR-8 (Signal Filtering & Audit Trail)

### Epic 3: Automated Position Management & Exit Strategies
Operator can automatically create positions from safe signals (dual-mode: simulation + live), monitor prices in real-time via Jupiter Price API V3 and DexScreener fallback, and execute sophisticated exit strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) without manual trading.

**FRs covered:** FR-4 (Position Creation & Management), FR-5 (Price Monitoring), FR-6 (Exit Strategy Execution)
**Additional Requirements:** AR-5 (Jupiter + DexScreener clients), DBR-3 (ADR-002 Exit Strategy Override), DBR-9 (Orders Retry Mechanism), DBR-10 (Position PnL Separation)

### Epic 4: Wallet Intelligence & Performance Analytics
Operator can monitor source wallet activity for mirror-exit triggers, track performance per wallet (win rate, PnL, signal counts all/30d/7d/24h), and make data-driven curation decisions (remove underperformers, promote high-performers to live mode).

**FRs covered:** FR-7 (Wallet Activity Monitoring), FR-8 (Performance Tracking & Analytics)
**Additional Requirements:** DBR-4 (ADR-003 Performance Materialized View), DBR-6 (Wallet Discovery & Performance Baseline for fake wallet detection)

### Epic 5: System Configuration & Risk Management
Operator can configure all system parameters (capital, risk limits, safety thresholds, exit strategy templates), monitor system health (webhook status, circuit breakers), and receive automated protection against excessive losses via circuit breakers.

**FRs covered:** FR-9 (System Configuration & Status)
**NFRs covered:** NFR-2 (Reliability via circuit breakers), NFR-5 (Observability via structured logging)
**Additional Requirements:** AR-7 (Structured Logging), AR-8 (Deployment Strategy), DBR-5 (ADR-004 Circuit Breaker Non-Closing)

## Epic 1: Data Foundation & UI Framework

Operator can visualize the system structure and interact with mockup data, validating the information architecture before connecting real logic. All 9 database tables migrated with comprehensive mock data, complete Gradio UI (Dashboard, Watchlist, Config tabs) displaying mock data with table + sidebar interactions.

### Story 1.1: Database Schema Migration & Mock Data

As an operator,
I want all 9 database tables created with comprehensive mock data,
So that I can validate the complete data structure before implementing business logic.

**Acceptance Criteria:**

**Given** a fresh Supabase database in the walltrack schema
**When** I execute all migration files sequentially
**Then** all 9 tables are created successfully (config, exit_strategies, wallets, tokens, signals, orders, positions, performance, circuit_breaker_events)
**And** each table has COMMENT ON TABLE documenting its architectural pattern
**And** each column has COMMENT ON COLUMN documenting its purpose

**Given** the database schema is migrated
**When** I execute the mock data insertion script
**Then** mock data is inserted for all 9 tables:
- `config`: 1 row (singleton pattern)
- `exit_strategies`: 3 templates (conservative, balanced, aggressive)
- `wallets`: 5 wallets (3 simulation mode, 2 live mode) with discovery metrics
- `tokens`: 8 tokens with safety scores (4 safe ≥0.60, 4 unsafe <0.60)
- `signals`: 20 signals across different wallets (10 filtered, 10 processed)
- `positions`: 12 positions (6 open, 6 closed) with PnL data
- `orders`: 18 orders (12 filled, 4 pending, 2 failed)
- `performance`: 5 rows (1 per wallet) with win_rate, pnl, signal counts
- `circuit_breaker_events`: 3 events (2 triggered, 1 reset)

**And** all foreign key relationships are valid (no orphaned records)
**And** mock data represents realistic scenarios (successful trades, failed trades, filtered signals, circuit breaker triggers)

**Given** mock data is inserted
**When** I query each table via Supabase dashboard
**Then** I can view all mock records
**And** I can validate the data structure matches the design guides in `docs/database-design/*.md`

### Story 1.2: Gradio Application Shell & Three-Tab Navigation

As an operator,
I want a functional Gradio application with three-tab navigation (Dashboard, Watchlist, Config),
So that I can access different sections of the system and validate the overall UI structure.

**Acceptance Criteria:**

**Given** the Gradio application is launched via `uv run python src/walltrack/ui/app.py`
**When** the application starts successfully
**Then** a browser window opens at http://127.0.0.1:7860
**And** the application displays the WallTrack title
**And** three tabs are visible: "Dashboard", "Watchlist", "Config"

**Given** the three-tab structure is rendered
**When** I click on the "Dashboard" tab
**Then** the tab becomes active (blue underline indicator)
**And** a placeholder message displays: "Dashboard content will appear here"

**Given** the three-tab structure is rendered
**When** I click on the "Watchlist" tab
**Then** the tab becomes active (blue underline indicator)
**And** a placeholder message displays: "Watchlist content will appear here"

**Given** the three-tab structure is rendered
**When** I click on the "Config" tab
**Then** the tab becomes active (blue underline indicator)
**And** a placeholder message displays: "Config content will appear here"

**Given** the application is running
**When** I navigate between tabs multiple times
**Then** tab switching is smooth and immediate
**And** no errors appear in the browser console
**And** the active tab indicator updates correctly

### Story 1.3: Dashboard Tab - Performance Metrics & Positions Table

As an operator,
I want to view performance metrics and active positions with mock data in the Dashboard tab,
So that I can validate the dashboard layout and data display before connecting real logic.

**Acceptance Criteria:**

**Given** the Dashboard tab is active
**When** the tab content loads
**Then** 4 performance metric cards are displayed in a horizontal row
**And** each metric card shows: Win Rate (🔵 Simulation | 🟠 Live), PnL Total (🔵 Simulation | 🟠 Live), Capital Utilization (🔵 Simulation | 🟠 Live), Active Wallets (🔵 Simulation | 🟠 Live)
**And** metric values are large (H2 24px font size) and clearly readable
**And** metric cards use spacious padding (24px) and comfortable spacing

**Given** the performance metrics are displayed
**When** I scroll down in the Dashboard tab
**Then** an Active Positions table is visible below the metrics
**And** the table displays 7 columns: Token, Entry, Current, PnL, Mode, Status, Actions
**And** the table shows mock data from the `positions` table (12 positions: 6 open, 6 closed)
**And** Mode column uses color-coded badges: 🔵 Blue (#3B82F6) for simulation, 🟠 Amber (#F59E0B) for live
**And** PnL column shows positive values in green, negative values in red
**And** rows are compact (48px height) for efficient data density

**Given** the Active Positions table is displayed
**When** I view the mock data
**Then** I can see realistic position data: token symbols (e.g., BONK, WIF, MYRO), entry prices, current prices, PnL values
**And** the data matches the mock data inserted in Story 1.1
**And** closed positions are visually distinct from open positions (e.g., grayed out or separate section)

**Given** the Dashboard tab is fully rendered
**When** I resize the browser window
**Then** the layout adapts responsively (desktop 1200px+: full layout, tablet 768-1199px: adjusted, mobile <768px: single column)
**And** all elements remain visible and usable

### Story 1.4: Watchlist Tab - Wallets Table & Action Bar

As an operator,
I want to view the watchlist with wallet performance data and filtering controls,
So that I can validate the watchlist layout and understand wallet curation capabilities.

**Acceptance Criteria:**

**Given** the Watchlist tab is active
**When** the tab content loads
**Then** an action bar is visible at the top with: [+ Add Wallet] button, Filter dropdown, Sort dropdown
**And** the action bar buttons are styled and functional (buttons trigger placeholder actions)

**Given** the action bar is displayed
**When** I view the wallets table below
**Then** the table displays 7 columns: Label, Address, Mode, Status, Signals, Win Rate, PnL
**And** the table shows mock data from the `wallets` and `performance` tables (5 wallets: 3 simulation, 2 live)
**And** the table occupies 3/4 of the width (Notion-inspired layout, leaving space for future sidebar)

**Given** the wallets table is displayed
**When** I view the mock data
**Then** I can see realistic wallet data:
- Label: e.g., "Smart Whale #1", "Degen Trader"
- Address: truncated format (e.g., "7xKX...9bYz")
- Mode: color-coded badges (🔵 Simulation | 🟠 Live)
- Status: Active/Inactive indicators
- Signals: count values (e.g., "127 signals")
- Win Rate: percentage values (e.g., "68.5%")
- PnL: dollar values with color coding (green for profit, red for loss)

**Given** the wallets table is populated
**When** I click on the Filter dropdown
**Then** filter options are displayed: All, Simulation Only, Live Only, Active Only, Inactive Only
**And** selecting a filter updates the table display (placeholder behavior: shows alert message)

**Given** the wallets table is populated
**When** I click on the Sort dropdown
**Then** sort options are displayed: Win Rate (High to Low), PnL (High to Low), Signals (Most to Least), Recently Added
**And** selecting a sort option updates the table display (placeholder behavior: shows alert message)

**Given** the Watchlist tab is fully rendered
**When** I click the [+ Add Wallet] button
**Then** a placeholder action is triggered (e.g., alert: "Add Wallet functionality coming in Epic 2")

### Story 1.5: Config Tab - Accordion Sections & Form Layouts

As an operator,
I want to view system configuration sections with form layouts and mock data,
So that I can validate the config interface structure before implementing actual configuration logic.

**Acceptance Criteria:**

**Given** the Config tab is active
**When** the tab content loads
**Then** three accordion sections are visible: "Exit Strategies", "Risk Limits", "API Keys"
**And** all sections are collapsed by default (progressive disclosure pattern)

**Given** the accordion sections are displayed
**When** I click on the "Exit Strategies" accordion header
**Then** the section expands smoothly
**And** a form is displayed with the following fields (using mock data from `config` table):
- Stop Loss %: number input (default: 20)
- Trailing Stop %: number input (default: 15)
- Scaling Out Levels: text input (default: "25%, 50%, 75%")
- Mirror Exit Enabled: checkbox (default: checked)
**And** form fields have comfortable spacing (24px padding, 40px input height)
**And** a [Save] button is visible at the bottom (placeholder action)

**Given** the accordion sections are displayed
**When** I click on the "Risk Limits" accordion header
**Then** the section expands smoothly
**And** a form is displayed with the following fields (using mock data from `config` table):
- Max Capital Per Trade %: number input (default: 5)
- Max Total Capital %: number input (default: 80)
- Circuit Breaker Loss Threshold %: number input (default: 15)
- Daily Loss Limit USD: number input (default: 500)
**And** form fields have comfortable spacing
**And** a [Save] button is visible at the bottom (placeholder action)

**Given** the accordion sections are displayed
**When** I click on the "API Keys" accordion header
**Then** the section expands smoothly
**And** a form is displayed with the following fields:
- Helius API Key: password input (masked)
- Wallet Private Key: password input (masked)
- DexScreener API Key: password input (masked, optional)
- Jupiter API Key: password input (masked, optional)
**And** webhook status indicator displays: "Connected ✅" or "Disconnected ❌" (using mock data)
**And** last signal timestamp displays (e.g., "Last signal: 2 minutes ago")
**And** a [Save] button is visible at the bottom (placeholder action)

**Given** the Config tab is fully rendered
**When** I click on any [Save] button
**Then** a placeholder action is triggered (e.g., alert: "Configuration save functionality coming in Epic 5")

**Given** multiple accordion sections are expanded
**When** I click on a collapsed section header
**Then** the clicked section expands
**And** previously expanded sections remain open (all sections can be open simultaneously)

### Story 1.6: Interactive Sidebars - Table Click Handlers & Detail Views

As an operator,
I want to click on table rows and see detailed information in a sidebar,
So that I can validate the progressive disclosure pattern (summary visible, details on-demand).

**Acceptance Criteria:**

**Given** I am viewing the Dashboard tab with the Active Positions table
**When** I click on any position row in the table
**Then** a sidebar appears on the right (1/4 width) with position details
**And** the sidebar displays: Token Name, Entry Price, Current Price, Entry Amount, Remaining Amount, Entry Date, Exit Strategy (from `exit_strategy_override` or default), PnL Breakdown (Realized + Unrealized), Transaction History
**And** the sidebar data matches the clicked row (using mock data from `positions` table)
**And** the sidebar has a [Close] button or click-outside-to-close behavior

**Given** the Dashboard sidebar is open
**When** I click the [Close] button or click outside the sidebar
**Then** the sidebar disappears smoothly
**And** the table returns to full width (3/4 of tab content area)

**Given** I am viewing the Watchlist tab with the Wallets table
**When** I click on any wallet row in the table
**Then** a sidebar appears on the right (1/4 width) with wallet details
**And** the sidebar displays: Wallet Label, Full Address (with copy button), Discovery Metrics (Initial Win Rate, Initial Trades, Initial PnL), Current Performance (Win Rate, PnL, Signals All/30d/7d/24h), Recent Signals (last 5 signals with timestamps and outcomes), Action Buttons ([Promote to Live] / [Demote to Simulation], [Remove Wallet])
**And** the sidebar data matches the clicked row (using mock data from `wallets` and `performance` tables)

**Given** the Watchlist sidebar is open
**When** I click on action buttons ([Promote to Live], [Remove Wallet])
**Then** placeholder actions are triggered (e.g., alert: "Wallet promotion functionality coming in Epic 4")

**Given** the Watchlist sidebar is open
**When** I click the [Close] button or click outside the sidebar
**Then** the sidebar disappears smoothly
**And** the table returns to full width (3/4 of tab content area)

**Given** sidebars are implemented on both Dashboard and Watchlist tabs
**When** I switch between tabs with a sidebar open
**Then** the sidebar closes automatically when switching tabs
**And** no sidebar state persists across tab switches

**Given** I am on a mobile viewport (<768px width)
**When** I click on a table row
**Then** the sidebar opens as a fullscreen modal (overlay pattern)
**And** the modal has a clear [Close] button in the top-right corner
**And** scrolling works within the modal content

## Epic 2: Smart Money Discovery & Token Safety

Operator can discover smart money wallets via GMGN, add them to watchlist, receive real-time swap signals via Helius webhooks, and automatically filter unsafe tokens before any positions are created.

### Story 2.1: Watchlist CRUD Operations - Add, Edit, Remove Wallets

As an operator,
I want to manually add, edit, and remove wallet addresses from my watchlist,
So that I can curate my list of smart money wallets to monitor.

**Acceptance Criteria:**

**Given** I am on the Watchlist tab
**When** I click the [+ Add Wallet] button
**Then** a modal form appears with fields: Wallet Address (required), Label (optional), Mode (dropdown: Simulation/Live, default: Simulation), Initial Win Rate % (number), Initial Trades Observed (number), Initial PnL USD (number)
**And** the form has [Save] and [Cancel] buttons

**Given** the Add Wallet modal is open
**When** I enter a valid Solana wallet address (58 characters, base58) and click [Save]
**Then** the wallet is inserted into the `wallets` table with status='active', helius_sync_status='pending'
**And** the modal closes
**And** the wallets table refreshes showing the new wallet
**And** a success message displays: "Wallet added successfully"

**Given** the Add Wallet modal is open
**When** I enter an invalid wallet address and click [Save]
**Then** a validation error displays: "Invalid Solana address format"
**And** the form does not submit
**And** the modal remains open for correction

**Given** I have a wallet in my watchlist
**When** I click on the wallet row in the table and then click [Edit] in the sidebar
**Then** an Edit Wallet modal appears pre-filled with the wallet's current data
**And** I can modify: Label, Mode, Initial metrics
**And** I cannot modify: Wallet Address (read-only)

**Given** the Edit Wallet modal is open with modified data
**When** I click [Save]
**Then** the wallet record is updated in the `wallets` table
**And** the modal closes
**And** the wallets table refreshes showing the updated data
**And** a success message displays: "Wallet updated successfully"

**Given** I have a wallet in my watchlist
**When** I click on the wallet row and then click [Remove Wallet] in the sidebar
**Then** a confirmation dialog appears: "Are you sure you want to remove this wallet? This action cannot be undone."
**And** the dialog has [Confirm] and [Cancel] buttons

**Given** the Remove Wallet confirmation dialog is open
**When** I click [Confirm]
**Then** the wallet record is deleted from the `wallets` table (hard delete or status='deleted')
**And** the dialog closes
**And** the wallets table refreshes without the deleted wallet
**And** a success message displays: "Wallet removed successfully"

### Story 2.2: Helius Webhook Registration & Global Address Monitoring

As an operator,
I want Helius to monitor all my active watchlist wallets via a global webhook,
So that I receive real-time swap notifications for all tracked addresses.

**Acceptance Criteria:**

**Given** the system is configured with a valid HELIUS_API_KEY in .env
**When** the application starts
**Then** a background worker initializes and checks if a global webhook exists in the `config` table
**And** if no webhook exists, the worker calls Helius API to create a new webhook with type='enhanced' and transactionTypes=['SWAP']
**And** the webhook URL is set to the application's public endpoint (e.g., https://walltrack.app/webhooks/helius)
**And** the webhook_id is stored in `config.helius_webhook_id`

**Given** a global Helius webhook is registered
**When** a new wallet is added to the watchlist (status='active')
**Then** a background sync worker triggers within 30 seconds
**And** the worker retrieves all active wallet addresses from the `wallets` table
**And** the worker calls Helius API to update the webhook's accountAddresses list with all active addresses
**And** the wallet's `helius_synced_at` timestamp is updated
**And** the wallet's `helius_sync_status` is set to 'synced'

**Given** multiple wallets are added/removed/deactivated within 5 minutes
**When** the scheduled batch sync runs (every 5 minutes)
**Then** all address list changes are batched into a single Helius API call
**And** the webhook's accountAddresses list is updated once with the complete active wallet list
**And** all affected wallets have their `helius_synced_at` and `helius_sync_status` updated

**Given** the Helius webhook sync fails (API error, network issue)
**When** the sync worker encounters the error
**Then** the error is logged with structured logging (level: ERROR, context: webhook_sync)
**And** the affected wallets have `helius_sync_status` set to 'failed'
**And** the worker retries the sync after exponential backoff (1min, 2min, 5min)

**Given** I am on the Config tab in the API Keys section
**When** I view the webhook status indicator
**Then** it displays "Connected ✅" if the webhook is registered and responding
**And** it displays "Disconnected ❌" if the webhook registration failed or is inactive
**And** the last sync timestamp is shown (e.g., "Last synced: 3 minutes ago")

### Story 2.3: Webhook Signal Reception & Storage

As an operator,
I want all swap signals from Helius webhooks to be captured and stored,
So that I have a complete audit trail of all detected trading activity.

**Acceptance Criteria:**

**Given** the Helius webhook is registered and monitoring active wallets
**When** a monitored wallet executes a SWAP transaction on Solana
**Then** Helius sends a POST request to the webhook endpoint with transaction details
**And** the webhook handler receives: transaction signature, wallet address, token mint addresses (input/output), amounts, timestamp

**Given** the webhook handler receives a valid swap signal
**When** the signal is processed
**Then** a new record is inserted into the `signals` table with: source_wallet_address, token_mint (output token), amount_usd (estimated), detected_at (timestamp), filtered=false, filter_reason=null, raw_webhook_data (JSONB)
**And** the signal is logged with structured logging (level: INFO, event: signal_received)

**Given** the webhook handler receives a duplicate signal (same tx_signature)
**When** the signal is processed
**Then** the duplicate is detected by checking existing `signals.raw_webhook_data->>'signature'`
**And** a new record is still inserted with filtered=true, filter_reason='duplicate_signal'
**And** the duplicate is logged with structured logging (level: WARN, event: duplicate_signal)

**Given** the webhook handler receives an invalid or malformed payload
**When** the signal is processed
**Then** the handler logs the error with structured logging (level: ERROR, event: invalid_webhook_payload, payload: truncated_data)
**And** the handler returns HTTP 400 Bad Request to Helius
**And** no signal record is created in the database

**Given** signals are being stored in the `signals` table
**When** I view the Dashboard tab
**Then** the last signal timestamp is displayed in the performance metrics area
**And** the timestamp updates in real-time (or near real-time with <1min delay) as new signals arrive

**Given** I am viewing the Watchlist tab wallet sidebar
**When** I click on a wallet row
**Then** the sidebar displays "Recent Signals" showing the last 5 signals for that wallet
**And** each signal shows: Token symbol, Amount USD, Timestamp (relative, e.g., "2 minutes ago"), Filtered status (Yes/No)

### Story 2.4: Token Safety Analysis - Multi-Source Scoring

As an operator,
I want tokens to be automatically analyzed for safety risks using multiple data sources,
So that I avoid creating positions on rug pulls or honeypots.

**Acceptance Criteria:**

**Given** a new signal is received and stored in the `signals` table
**When** the signal processing pipeline checks the token_mint
**Then** the system queries the `tokens` table for an existing safety analysis
**And** if the token exists and `analyzed_at` is < 1 hour old, the cached score is used
**And** if the token does not exist or cache is stale, a new analysis is triggered

**Given** a token requires safety analysis
**When** the analysis worker executes
**Then** the worker attempts to fetch data from RugCheck API (primary source)
**And** if RugCheck returns valid data, the worker calculates 4 check scores:
- Liquidity Check: ≥$50K = 1.0, <$50K = 0.0
- Holder Distribution: Top 10 holders < 80% = 1.0, ≥80% = 0.0
- Contract Analysis: No honeypot flags = 1.0, honeypot detected = 0.0
- Age Check: ≥24h = 1.0, <24h = 0.0
**And** the overall safety_score is calculated as weighted average: (Liquidity * 0.25) + (Holder * 0.25) + (Contract * 0.25) + (Age * 0.25)

**Given** RugCheck API fails or returns incomplete data
**When** the analysis worker detects the failure
**Then** the worker falls back to Helius Metadata API (secondary source)
**And** if Helius returns valid data, partial scoring is performed (e.g., only Liquidity + Age, missing Contract/Holder checks)
**And** the safety_score is calculated with available checks weighted proportionally

**Given** both RugCheck and Helius APIs fail
**When** the analysis worker detects the failure
**Then** the worker falls back to DexScreener API (tertiary source)
**And** if DexScreener returns valid data, minimal scoring is performed (Liquidity + basic metadata)
**And** the safety_score is calculated with available data

**Given** all three data sources fail (RugCheck, Helius, DexScreener)
**When** the analysis worker exhausts all retries
**Then** the token is inserted into `tokens` table with safety_score=0.0, data_source='none', analyzed_at=NOW()
**And** the failure is logged with structured logging (level: ERROR, event: token_analysis_failed, token_mint: address)

**Given** a token safety analysis completes successfully
**When** the analysis result is ready
**Then** a record is inserted/updated in the `tokens` table with: token_mint (PK), safety_score (0.0-1.0), analyzed_at (timestamp), data_source (rugcheck/helius/dexscreener), metadata (JSONB with raw API response)
**And** the success is logged with structured logging (level: INFO, event: token_analyzed, safety_score: value)

**Given** I am viewing token data in the Dashboard sidebar (position details)
**When** I click on a position row
**Then** the sidebar displays the token's safety score (e.g., "Safety Score: 0.75/1.00")
**And** the score is color-coded: Green (≥0.60), Yellow (0.40-0.59), Red (<0.40)
**And** the data source is indicated (e.g., "Source: RugCheck")

### Story 2.5: Signal Filtering Logic & Audit Trail

As an operator,
I want signals for unsafe tokens to be automatically filtered out,
So that positions are only created for tokens meeting my safety threshold.

**Acceptance Criteria:**

**Given** a signal has been received and the token safety analysis is complete
**When** the signal filtering logic executes
**Then** the system retrieves the safety threshold from the `config` table (default: 0.60)
**And** the system compares the token's `safety_score` against the threshold

**Given** a token's safety_score is ≥ the threshold (e.g., 0.75 ≥ 0.60)
**When** the filtering logic evaluates the signal
**Then** the signal record is updated with filtered=false, filter_reason=null
**And** the signal is marked as ready for position creation
**And** the approval is logged with structured logging (level: INFO, event: signal_approved, safety_score: value)

**Given** a token's safety_score is < the threshold (e.g., 0.45 < 0.60)
**When** the filtering logic evaluates the signal
**Then** the signal record is updated with filtered=true, filter_reason='safety_score_below_threshold'
**And** the signal is NOT forwarded to the position creation pipeline
**And** the rejection is logged with structured logging (level: WARN, event: signal_filtered, safety_score: value, threshold: value)

**Given** signals are being filtered automatically
**When** I view the Watchlist tab wallet sidebar
**Then** the "Recent Signals" section shows filtered signals with a visual indicator (e.g., 🚫 icon or strikethrough)
**And** I can see the filter_reason for each filtered signal (e.g., "Filtered: Safety score below threshold")

**Given** I want to audit why signals were filtered
**When** I query the `signals` table (via admin tools or future reporting feature)
**Then** I can filter by filtered=true and view all rejected signals with their filter_reason
**And** I can analyze filtering patterns (e.g., "50% of signals filtered due to low liquidity")

**Given** I am on the Config tab in the Risk Limits section
**When** I view the Safety Threshold field
**Then** the current threshold is displayed (e.g., 0.60)
**And** I can adjust the threshold value (range: 0.00 to 1.00)
**And** saving the new threshold updates the `config` table
**And** future signals use the updated threshold immediately

## Epic 3: Automated Position Management & Exit Strategies

Operator can automatically create positions from safe signals (dual-mode: simulation + live), monitor prices in real-time via Jupiter Price API V3 and DexScreener fallback, and execute sophisticated exit strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) without manual trading.

### Story 3.1: Position Creation from Safe Signals - Dual-Mode Execution

As an operator,
I want positions to be automatically created from safe signals in both simulation and live modes,
So that I can validate strategies in simulation before risking real capital.

**Acceptance Criteria:**

**Given** a signal has passed safety filtering (filtered=false) and the source wallet is active
**When** the position creation pipeline processes the signal
**Then** the system checks the source wallet's mode (simulation/live) from the `wallets` table
**And** the system retrieves the default exit strategy for the wallet from the `exit_strategies` table (via `wallets.default_exit_strategy_id`)
**And** the system calculates the position size: (config.max_capital_per_trade_percent / 100) * config.total_capital_usd

**Given** the source wallet is in simulation mode
**When** a position is created
**Then** a new record is inserted into the `positions` table with: token_id (FK to tokens), source_wallet_id (FK to wallets), entry_price_usd (from signal), amount_tokens (calculated), mode='simulation', status='open', opened_at=NOW(), exit_strategy_override=NULL (uses default)
**And** NO Jupiter API call is made (simulation mode = no real trades)
**And** a new record is inserted into the `orders` table with: position_id (FK), type='entry', status='simulated', amount_tokens (same as position), price_usd (entry price), executed_at=NOW()
**And** the position creation is logged with structured logging (level: INFO, event: position_created, mode: simulation)

**Given** the source wallet is in live mode
**When** a position is created
**Then** a Jupiter API swap call is executed: input_mint=SOL/USDC, output_mint=token_mint, amount=position_size_usd
**And** if the Jupiter API call succeeds, a new record is inserted into the `positions` table with mode='live', status='open'
**And** a new record is inserted into the `orders` table with type='entry', status='filled', tx_signature (from Jupiter response)
**And** the position creation is logged with structured logging (level: INFO, event: position_created, mode: live, tx_signature: value)

**Given** the Jupiter API call fails (timeout, slippage too high, network error)
**When** the position creation worker encounters the error
**Then** the system retries the Jupiter API call up to 3 times with exponential backoff (5s, 15s, 30s)
**And** if all retries fail, a new record is inserted into the `orders` table with type='entry', status='failed', last_error (error message), retry_count=3
**And** NO position is created in the `positions` table
**And** the failure is logged with structured logging (level: ERROR, event: position_creation_failed, mode: live, error: message)

**Given** positions are being created from signals
**When** I view the Dashboard tab Active Positions table
**Then** new positions appear in the table within <5 seconds of signal receipt (NFR-1: P95 latency)
**And** simulation positions display with 🔵 Blue mode badge
**And** live positions display with 🟠 Amber mode badge
**And** I can see: Token symbol, Entry price, Current price (placeholder until price monitoring), PnL (initially $0.00), Status (Open)

**Given** the system is creating multiple positions concurrently (burst of 10 signals within 30s)
**When** the position creation pipeline processes the queue
**Then** all positions are created sequentially (to avoid race conditions on config/wallet data)
**And** the total processing time is <30 seconds for 10 positions (NFR-7: scalability)
**And** each position creation is logged independently

### Story 3.2: Real-Time Price Monitoring - Jupiter & DexScreener Fallback

As an operator,
I want token prices for active positions to be monitored continuously,
So that exit strategies can be triggered based on current market conditions.

**Acceptance Criteria:**

**Given** the system has active positions (status='open') in the `positions` table
**When** the price monitoring worker starts
**Then** the worker queries the `positions` table for all open positions
**And** the worker extracts unique token_ids to create a polling list
**And** the worker schedules polling at 30-60 second intervals for each token

**Given** a token requires price polling
**When** the price monitoring worker executes for that token
**Then** the worker calls Jupiter Price API V3 with token_mint address
**And** if Jupiter returns a valid price, the price is stored temporarily in memory (cache)
**And** the worker updates all positions for that token with current_price_usd (calculated field or cached value)
**And** the price fetch is logged with structured logging (level: DEBUG, event: price_fetched, source: jupiter, price: value)

**Given** Jupiter Price API V3 fails or returns an error
**When** the price monitoring worker detects the failure
**Then** the worker immediately falls back to DexScreener API
**And** the worker calls DexScreener API with token_mint address
**And** if DexScreener returns a valid price, the price is used and logged (level: WARN, event: price_fallback, source: dexscreener)
**And** if DexScreener also fails, the worker logs the error (level: ERROR, event: price_fetch_failed, token: mint) and retries after 60 seconds

**Given** price monitoring is active for all open positions
**When** I view the Dashboard tab Active Positions table
**Then** the "Current" column updates every 30-60 seconds with the latest fetched price
**And** the "PnL" column recalculates automatically: (current_price - entry_price) * amount_tokens
**And** PnL values are color-coded: Green for profit, Red for loss

**Given** a position's current price changes
**When** the price update triggers exit strategy evaluation
**Then** the worker checks all configured exit strategies for that position (stop-loss, trailing-stop, scaling-out)
**And** if any exit condition is met, the exit execution pipeline is triggered (implemented in later stories)

**Given** the price monitoring worker is running
**When** a position is closed (status='closed')
**Then** the worker removes that position from the polling list
**And** no further price fetches occur for that token (unless other positions remain open)

### Story 3.3: Stop-Loss & Trailing-Stop Exit Strategies

As an operator,
I want stop-loss and trailing-stop strategies to protect my capital and lock in profits,
So that I minimize losses and capture gains automatically.

**Acceptance Criteria:**

**Given** a position is open and price monitoring is active
**When** the exit strategy evaluation worker checks stop-loss conditions
**Then** the worker retrieves the stop-loss threshold from the position's exit strategy (exit_strategy_override or default)
**And** the worker calculates the loss percentage: ((current_price - entry_price) / entry_price) * 100
**And** if the loss percentage ≤ -stop_loss_percent (e.g., -20%), the stop-loss is triggered

**Given** a stop-loss condition is met
**When** the exit execution pipeline runs
**Then** the position is marked for exit with exit_reason='stop_loss'
**And** the system calculates the exit amount: 100% of remaining_amount_tokens (full exit)
**And** if the position is in simulation mode, an order is created with type='exit', status='simulated', executed_at=NOW()
**And** if the position is in live mode, a Jupiter API swap call is executed: input_mint=token_mint, output_mint=SOL/USDC, amount=remaining_amount_tokens
**And** the position's status is updated to 'closed', closed_at=NOW(), realized_pnl_usd=(exit_price - entry_price) * amount_tokens

**Given** a position is open and has reached a profit threshold
**When** the trailing-stop strategy is evaluated
**Then** the worker checks if the position is profitable: current_price > entry_price
**And** if profitable, the worker retrieves the trailing_stop_percent from the exit strategy
**And** the worker tracks the peak_price (highest price since position opened) in memory or position metadata
**And** the worker calculates the trailing-stop trigger: peak_price - (peak_price * trailing_stop_percent / 100)
**And** if current_price ≤ trailing_stop_trigger, the trailing-stop is activated

**Given** a trailing-stop condition is met
**When** the exit execution pipeline runs
**Then** the position is marked for exit with exit_reason='trailing_stop'
**And** the exit process follows the same logic as stop-loss (100% exit, dual-mode execution)
**And** the position is closed with realized_pnl_usd reflecting the profit captured

**Given** stop-loss and trailing-stop strategies are active
**When** both conditions are evaluated for a position
**Then** the stop-loss is checked FIRST (capital protection priority, FR-6)
**And** if stop-loss triggers, trailing-stop is ignored
**And** if stop-loss does NOT trigger and position is profitable, trailing-stop is evaluated

**Given** exit strategies are executing
**When** I view the Dashboard sidebar for a closed position
**Then** the sidebar displays: Exit Reason (e.g., "Stop-Loss @ -20%"), Exit Price, Exit Date, Realized PnL
**And** I can see the full transaction history: Entry order → Exit order with timestamps and prices

### Story 3.4: Scaling-Out Exit Strategy

As an operator,
I want to scale out of positions at predefined profit levels,
So that I can lock in partial profits while maintaining exposure to further upside.

**Acceptance Criteria:**

**Given** a position is open and profitable
**When** the scaling-out strategy is evaluated
**Then** the worker retrieves the scaling levels from the exit strategy (e.g., "25% at +50%, 50% at +100%, 75% at +150%")
**And** the worker parses the scaling configuration into a list of (profit_percent, exit_percent) tuples

**Given** scaling levels are configured for a position
**When** the current price crosses a scaling level threshold
**Then** the worker calculates the profit percentage: ((current_price - entry_price) / entry_price) * 100
**And** if profit_percent ≥ scaling_level_threshold (e.g., +50%), the scaling exit is triggered

**Given** a scaling-out condition is met
**When** the exit execution pipeline runs
**Then** the position is marked for PARTIAL exit with exit_reason='scaling_out_level_N'
**And** the system calculates the exit amount: (scaling_exit_percent / 100) * original_amount_tokens (e.g., 25% of original)
**And** if the position is in simulation mode, an order is created with type='exit', status='simulated', amount_tokens=exit_amount
**And** if the position is in live mode, a Jupiter API swap call is executed for the partial amount
**And** the position's remaining_amount_tokens is updated: original_amount - exit_amount
**And** the position's realized_pnl_usd is updated: realized_pnl_usd + ((exit_price - entry_price) * exit_amount)
**And** the position status remains 'open' (partial exit, not full close)

**Given** a position has executed a partial scaling exit
**When** the price continues to rise and crosses the next scaling level
**Then** the next scaling exit is triggered using the ORIGINAL amount_tokens as the basis (not remaining amount)
**And** the exit amount is calculated: (next_scaling_percent / 100) * original_amount_tokens
**And** the process repeats until all scaling levels are exhausted or the position is fully closed

**Given** multiple scaling exits occur for a position
**When** I view the Dashboard sidebar for that position
**Then** the sidebar displays: Multiple exit orders with timestamps, amounts, and prices
**And** the "PnL Breakdown" section shows: Realized PnL (from scaling exits), Unrealized PnL (from remaining amount)
**And** the "Remaining Amount" field shows the current remaining_amount_tokens

**Given** a position has scaled out at multiple levels
**When** another exit strategy triggers (e.g., stop-loss, mirror-exit)
**Then** the exit applies to the remaining_amount_tokens only (not the original amount)
**And** the position is fully closed with status='closed'

### Story 3.5: Exit Strategy Execution Engine - Priority Logic & Order Creation

As an operator,
I want all exit strategies to execute in the correct priority order with proper error handling,
So that capital protection takes precedence and trades execute reliably.

**Acceptance Criteria:**

**Given** price monitoring is active for an open position
**When** the exit strategy evaluation worker runs (every 30-60s)
**Then** the worker evaluates exit conditions in the following priority order:
1. Stop-Loss (highest priority, capital protection)
2. Mirror-Exit (if source wallet sold, override other strategies except stop-loss)
3. Trailing-Stop (profit protection)
4. Scaling-Out (profit taking)
**And** only the FIRST triggered condition executes (no multiple simultaneous exits)

**Given** an exit condition is triggered
**When** the exit execution engine creates an order
**Then** a new record is inserted into the `orders` table with: position_id (FK), type='exit', amount_tokens (full or partial), price_usd (current market price), status='pending', retry_count=0

**Given** an exit order is in 'pending' status for a simulation position
**When** the order worker processes the order
**Then** the order status is immediately updated to 'simulated' (no API call required)
**And** the order's executed_at timestamp is set to NOW()
**And** the position is updated accordingly (partial or full close)

**Given** an exit order is in 'pending' status for a live position
**When** the order worker processes the order
**Then** the worker calls Jupiter API to execute the swap: input_mint=token_mint, output_mint=SOL/USDC, amount=order.amount_tokens
**And** if Jupiter API succeeds, the order status is updated to 'filled', tx_signature is stored, slippage_percent is calculated and stored
**And** the position is updated with new remaining_amount_tokens and realized_pnl_usd

**Given** a Jupiter API call fails during exit order execution
**When** the order worker encounters the error
**Then** the worker retries the API call up to 3 times with exponential backoff (5s, 15s, 30s)
**And** the order's retry_count is incremented with each attempt
**And** if all retries fail, the order status is set to 'failed', last_error is stored
**And** the position remains 'open' (exit did not complete)
**And** the failure is logged with structured logging (level: ERROR, event: exit_order_failed, position_id: value, error: message)

**Given** exit orders are being processed
**When** I view the Dashboard sidebar for a position with a failed exit order
**Then** the sidebar displays a warning: "Exit order failed - manual intervention required"
**And** I can see the error details: Retry count, Last error message, Last attempt timestamp
**And** I have an option to [Retry Order] manually (placeholder for future enhancement)

**Given** mirror-exit is enabled for a position (configured in exit strategy)
**When** the source wallet executes a sell transaction (detected via Helius webhook in Epic 4)
**Then** the mirror-exit takes priority over scaling-out and trailing-stop (but NOT over stop-loss)
**And** a 100% exit is triggered with exit_reason='mirror_exit'
**And** the position is closed immediately following the source wallet's sell signal

## Epic 4: Wallet Intelligence & Performance Analytics

Operator can monitor source wallet activity for mirror-exit triggers, track performance per wallet (win rate, PnL, signal counts all/30d/7d/24h), and make data-driven curation decisions (remove underperformers, promote high-performers to live mode).

### Story 4.1: Source Wallet Sell Detection for Mirror-Exit

As an operator,
I want to detect when source wallets sell tokens I'm holding,
So that I can automatically exit positions via mirror-exit strategy.

**Acceptance Criteria:**

**Given** Helius webhook is monitoring all active wallets (configured in Epic 2)
**When** a monitored wallet executes a SELL transaction (swap from token to SOL/USDC)
**Then** the webhook handler receives the transaction with: wallet address, token_mint (input token being sold), amount, timestamp, signature

**Given** a source wallet sell signal is received
**When** the signal processing pipeline executes
**Then** the system queries the `positions` table for open positions matching: source_wallet_id = wallet AND token_id = sold_token AND status='open'
**And** if matching positions exist, the system checks each position's exit strategy for mirror_exit_enabled=true

**Given** a matching position has mirror-exit enabled
**When** the mirror-exit logic evaluates the position
**Then** the system triggers a 100% exit with exit_reason='mirror_exit'
**And** the exit follows priority logic from Story 3.5 (stop-loss can still override if triggered first)
**And** an exit order is created in the `orders` table with type='exit', amount_tokens=remaining_amount_tokens

**Given** mirror-exit is triggered for a live position
**When** the exit order is processed
**Then** a Jupiter API swap is executed immediately (same logic as other exit strategies)
**And** the position is closed with status='closed', closed_at=NOW(), exit_reason='mirror_exit'
**And** the exit is logged with structured logging (level: INFO, event: mirror_exit_triggered, source_wallet: address, token: mint)

**Given** mirror-exit is triggered for a simulation position
**When** the exit order is processed
**Then** the order is marked as 'simulated' (no API call)
**And** the position is closed with the simulated exit price (current market price at time of trigger)

**Given** I am viewing the Dashboard sidebar for a closed position
**When** the position was closed via mirror-exit
**Then** the sidebar displays: Exit Reason="Mirror-Exit (Source wallet sold)", Exit Price, Exit Date
**And** I can see the source wallet's sell transaction signature in the transaction history

**Given** multiple positions match a source wallet sell signal
**When** the mirror-exit logic processes all matching positions
**Then** all positions with mirror_exit_enabled=true are closed simultaneously
**And** each exit is logged independently
**And** if any exit fails (Jupiter API error), it is retried independently without affecting other exits

### Story 4.2: Performance Metrics Calculation - Win Rate, PnL, Signal Counts

As an operator,
I want to track win rate, PnL, and signal counts per wallet,
So that I can evaluate which wallets generate profitable signals.

**Acceptance Criteria:**

**Given** positions have been opened and closed for a wallet
**When** the performance calculation worker runs (triggered on position close or daily batch)
**Then** the worker queries all closed positions for the wallet from the `positions` table
**And** the worker calculates: total_trades = COUNT(closed positions), winning_trades = COUNT(positions WHERE realized_pnl_usd > 0), win_rate = (winning_trades / total_trades) * 100

**Given** the win rate calculation is complete
**When** the worker updates the `performance` table
**Then** the worker inserts or updates the record for the wallet with: wallet_id (FK), win_rate_percent (calculated), last_updated_at=NOW()

**Given** positions have PnL data
**When** the performance calculation worker aggregates PnL
**Then** the worker calculates: total_pnl_usd = SUM(realized_pnl_usd) for all closed positions
**And** the worker updates the `performance` table with: total_pnl_usd (aggregated value)

**Given** signals have been received for a wallet
**When** the performance calculation worker counts signals
**Then** the worker queries the `signals` table for all signals WHERE source_wallet_id = wallet
**And** the worker calculates signal counts with time windows:
- signals_all = COUNT(all signals)
- signals_30d = COUNT(signals WHERE detected_at >= NOW() - INTERVAL '30 days')
- signals_7d = COUNT(signals WHERE detected_at >= NOW() - INTERVAL '7 days')
- signals_24h = COUNT(signals WHERE detected_at >= NOW() - INTERVAL '24 hours')
**And** the worker updates the `performance` table with all signal count fields

**Given** I am viewing the Watchlist tab
**When** the wallets table loads
**Then** the table displays performance metrics for each wallet: Win Rate (e.g., "68.5%"), PnL (e.g., "+$1,250.00" in green), Signals (e.g., "127 signals")
**And** the metrics update after each position close (near real-time) or at least daily

**Given** I click on a wallet row in the Watchlist tab
**When** the wallet sidebar opens
**Then** the sidebar displays detailed performance breakdown:
- Current Performance: Win Rate, Total PnL, Total Trades
- Signal Counts: All-time, 30d, 7d, 24h
- Comparison: Initial metrics (from discovery) vs Current metrics

### Story 4.3: Performance Materialized View - Daily Batch Refresh

As an operator,
I want performance metrics to be pre-calculated daily for fast dashboard loading,
So that I can view analytics without waiting for real-time calculations.

**Acceptance Criteria:**

**Given** the system has accumulated position and signal data
**When** the daily batch refresh worker runs (scheduled at 00:00 UTC)
**Then** the worker recalculates ALL performance metrics for ALL wallets from scratch
**And** the worker uses the same logic as Story 4.2 (win rate, PnL, signal counts)
**And** the worker updates the `performance` table with refreshed data for all wallets
**And** the refresh is logged with structured logging (level: INFO, event: performance_refresh_complete, wallets_updated: count, duration_ms: value)

**Given** the batch refresh is running
**When** individual position closes occur during the refresh
**Then** the real-time update logic (from Story 4.2) is temporarily suspended
**And** the batch refresh completes without conflicts (uses transaction isolation or locking)
**And** after batch completion, real-time updates resume for new position closes

**Given** the batch refresh completes
**When** I view the Watchlist tab or Dashboard tab
**Then** all performance metrics reflect the refreshed data (up to midnight UTC)
**And** the Dashboard loads in <2 seconds (NFR-1: performance target)

**Given** the batch refresh fails (database error, timeout)
**When** the worker encounters the error
**Then** the error is logged with structured logging (level: ERROR, event: performance_refresh_failed, error: message)
**And** the worker retries the refresh after 1 hour
**And** the previous day's performance data remains visible (stale but available)

**Given** I want to manually trigger a performance refresh (for testing or debugging)
**When** I access the Config tab (future enhancement: manual refresh button)
**Then** a [Refresh Performance] button is available
**And** clicking it triggers an immediate batch refresh
**And** a progress indicator shows the refresh status

### Story 4.4: Wallet Promotion & Demotion - Mode Switching

As an operator,
I want to promote high-performing simulation wallets to live mode and demote underperformers,
So that I can gradually scale my capital to proven winners.

**Acceptance Criteria:**

**Given** I am viewing the Watchlist tab wallet sidebar
**When** I click on a wallet row for a simulation wallet
**Then** the sidebar displays a [Promote to Live] button
**And** the button is enabled if the wallet has sufficient track record (e.g., ≥10 closed trades, win_rate ≥ 60%)

**Given** I click the [Promote to Live] button
**When** the promotion action executes
**Then** a confirmation dialog appears: "Promote [Wallet Label] to Live mode? Future positions will execute real trades."
**And** the dialog has [Confirm] and [Cancel] buttons

**Given** I confirm the promotion
**When** the update executes
**Then** the wallet's mode is updated in the `wallets` table: mode='live'
**And** the wallets table refreshes showing the updated mode (🟠 Amber badge)
**And** a success message displays: "Wallet promoted to Live mode"
**And** the promotion is logged with structured logging (level: INFO, event: wallet_promoted, wallet_id: value)

**Given** I am viewing a live wallet in the sidebar
**When** the wallet is underperforming (e.g., win_rate < 50% after 20 trades)
**Then** the sidebar displays a [Demote to Simulation] button
**And** the button is always enabled (operator can demote at any time)

**Given** I click the [Demote to Simulation] button and confirm
**When** the demotion executes
**Then** the wallet's mode is updated: mode='simulation'
**And** the wallets table refreshes showing the updated mode (🔵 Blue badge)
**And** a success message displays: "Wallet demoted to Simulation mode"
**And** the demotion is logged with structured logging (level: INFO, event: wallet_demoted, wallet_id: value)

**Given** a wallet's mode is changed (promotion or demotion)
**When** new signals are received for that wallet
**Then** new positions are created in the updated mode (simulation or live)
**And** existing open positions remain in their original mode (no retroactive changes)

**Given** I have multiple wallets with different performance levels
**When** I view the Watchlist tab
**Then** I can sort by Win Rate or PnL to identify top performers and underperformers
**And** the sidebar provides clear action buttons based on current mode and performance

### Story 4.5: Fake Wallet Detection & Curation Insights

As an operator,
I want to detect fake wallets (wash trading) by comparing initial vs actual performance,
So that I can remove wallets that were inflated during discovery.

**Acceptance Criteria:**

**Given** a wallet was added with initial discovery metrics (initial_win_rate_percent, initial_trades_observed, initial_pnl_usd)
**When** the wallet has 30+ days of tracked activity (created_at ≥ NOW() - INTERVAL '30 days')
**Then** the performance analysis worker compares: initial_win_rate_percent vs performance.win_rate_percent

**Given** the performance comparison reveals significant degradation
**When** the worker detects: (initial_win_rate - current_win_rate) ≥ 20% (e.g., 80% initial → 55% current)
**Then** the wallet is flagged as "potential fake" in the wallet sidebar
**And** a warning indicator displays in the Watchlist table (e.g., ⚠️ icon next to wallet label)

**Given** I am viewing a flagged wallet in the sidebar
**When** the sidebar loads
**Then** the sidebar displays: Warning="Significant performance drop detected. Initial: 80%, Current: 55%"
**And** the sidebar shows: Comparison table (Initial Metrics vs Current Metrics)
**And** the sidebar provides a [Remove Wallet] button for easy curation

**Given** I want to audit all flagged wallets
**When** I view the Watchlist tab
**Then** I can filter by "Flagged Wallets" (if filter implemented) or sort by performance drop
**And** flagged wallets are visually distinct (warning icon, yellow highlight)

**Given** I decide to remove a flagged wallet
**When** I click [Remove Wallet] and confirm
**Then** the wallet is deleted from the `wallets` table (same logic as Story 2.1)
**And** all associated signals remain in the database (audit trail preserved)
**And** all closed positions remain in the database (historical PnL preserved)
**And** all open positions are closed immediately with exit_reason='wallet_removed' (cleanup)

**Given** fake wallet detection is active
**When** the performance refresh worker runs (daily batch)
**Then** the worker recalculates degradation for all wallets with ≥30 days history
**And** flagged wallets are updated in the database (flag stored in `wallets` table or derived on-demand)
**And** the detection is logged with structured logging (level: WARN, event: fake_wallet_detected, wallet_id: value, degradation_percent: value)

## Epic 5: System Configuration & Risk Management

Operator can configure all system parameters (capital, risk limits, safety thresholds, exit strategy templates), monitor system health (webhook status, circuit breakers), and receive automated protection against excessive losses via circuit breakers.

### Story 5.1: System Configuration Management - Capital, Risk Limits, Safety

As an operator,
I want to configure all system parameters in the Config tab,
So that I can control capital allocation, risk exposure, and safety thresholds.

**Acceptance Criteria:**

**Given** I am on the Config tab in the "Risk Limits" accordion section
**When** I view the form fields
**Then** I see the following fields pre-filled with current values from the `config` table:
- Total Capital USD: number input (e.g., 10000)
- Max Capital Per Trade %: number input (e.g., 5)
- Max Total Capital %: number input (e.g., 80)
- Circuit Breaker Loss Threshold %: number input (e.g., 15)
- Daily Loss Limit USD: number input (e.g., 500)
- Safety Score Threshold: number input (range 0.00-1.00, e.g., 0.60)

**Given** the Risk Limits form is displayed
**When** I modify any field value and click [Save]
**Then** the system validates the input (e.g., Total Capital > 0, percentages in valid range)
**And** if validation passes, the `config` table is updated with new values
**And** a success message displays: "Configuration saved successfully"
**And** the update is logged with structured logging (level: INFO, event: config_updated, fields: changed_fields)

**Given** I enter invalid values (e.g., negative capital, percentage > 100)
**When** I click [Save]
**Then** validation errors display next to the invalid fields
**And** the form does not submit
**And** the `config` table is not modified

**Given** the configuration is updated
**When** new positions are created
**Then** the system uses the updated values immediately (e.g., new max_capital_per_trade_percent for position sizing)
**And** existing open positions are not affected (configuration is immutable at position creation)

**Given** I am on the Config tab in the "Exit Strategies" accordion section
**When** I view the default exit strategy fields
**Then** I see fields for: Stop Loss %, Trailing Stop %, Scaling Out Levels (text), Mirror Exit Enabled (checkbox)
**And** the fields are pre-filled with values from the `config` table or a default exit strategy template

**Given** I modify exit strategy defaults and click [Save]
**When** the update executes
**Then** the default exit strategy is updated in the `config` table or linked `exit_strategies` template
**And** future positions use the updated defaults (unless overridden at position level)

**Given** the Config tab is loaded
**When** I navigate between accordion sections (Risk Limits, Exit Strategies, API Keys)
**Then** all unsaved changes are preserved within the current session
**And** a warning displays if I navigate away with unsaved changes: "You have unsaved changes. Discard?"

### Story 5.2: Exit Strategy Templates - Create, Edit, Delete

As an operator,
I want to create reusable exit strategy templates,
So that I can apply different strategies to different wallets or positions.

**Acceptance Criteria:**

**Given** I am on the Config tab in the "Exit Strategies" section
**When** I click [+ Create Template] button
**Then** a modal form appears with fields:
- Template Name: text input (required, e.g., "Conservative", "Aggressive")
- Stop Loss %: number input (default: 20)
- Trailing Stop %: number input (default: 15)
- Scaling Out Levels: text input (e.g., "25% at +50%, 50% at +100%, 75% at +150%")
- Mirror Exit Enabled: checkbox (default: checked)

**Given** the Create Template modal is open
**When** I enter a template name and configure strategy parameters, then click [Save]
**Then** a new record is inserted into the `exit_strategies` table with: name (template name), stop_loss_percent, trailing_stop_percent, scaling_out_config (JSONB), mirror_exit_enabled
**And** the modal closes
**And** the template appears in a templates list in the Config tab
**And** a success message displays: "Template created successfully"

**Given** I have created multiple exit strategy templates
**When** I view the templates list in the Config tab
**Then** I see all templates with: Name, Stop Loss %, Trailing Stop %, Actions ([Edit], [Delete], [Set as Default])

**Given** I click [Edit] on a template
**When** the Edit Template modal opens
**Then** the modal is pre-filled with the template's current values
**And** I can modify any field and click [Save] to update the `exit_strategies` table

**Given** I click [Delete] on a template
**When** the confirmation dialog appears
**Then** the dialog warns: "Delete template [Name]? This will not affect existing positions using this template."
**And** if I confirm, the template is deleted from the `exit_strategies` table (soft delete or hard delete)
**And** wallets using this template as default revert to the system default template

**Given** I click [Set as Default] on a template
**When** the action executes
**Then** the `config` table is updated with: default_exit_strategy_id = template_id
**And** all NEW wallets added to the watchlist use this template by default
**And** existing wallets are not affected (they retain their configured default)

**Given** I am adding a new wallet (Story 2.1)
**When** the Add Wallet modal is displayed
**Then** I see an "Exit Strategy" dropdown with all available templates
**And** the default template is pre-selected
**And** I can choose a different template for this wallet

### Story 5.3: Circuit Breaker Logic - Automatic Position Blocking

As an operator,
I want the system to automatically block new positions when losses exceed thresholds,
So that I prevent catastrophic capital loss during adverse market conditions.

**Acceptance Criteria:**

**Given** positions are being closed throughout the day
**When** the circuit breaker evaluation worker runs (after each position close or every 5 minutes)
**Then** the worker calculates the daily loss: SUM(realized_pnl_usd) for all positions closed today (WHERE closed_at >= TODAY)
**And** the worker retrieves the circuit breaker threshold from the `config` table: circuit_breaker_loss_threshold_percent, daily_loss_limit_usd

**Given** the daily loss exceeds the USD threshold
**When** the circuit breaker logic evaluates: daily_loss_usd < -daily_loss_limit_usd (e.g., -$550 < -$500)
**Then** the circuit breaker is TRIGGERED
**And** a new record is inserted into the `circuit_breaker_events` table with: event_type='triggered', triggered_at=NOW(), reason='daily_loss_limit_exceeded', loss_amount_usd (daily loss)

**Given** the daily loss exceeds the percentage threshold
**When** the circuit breaker logic evaluates: (daily_loss_usd / total_capital_usd) * 100 < -circuit_breaker_loss_threshold_percent (e.g., -15.5% < -15%)
**Then** the circuit breaker is TRIGGERED
**And** a new record is inserted into the `circuit_breaker_events` table with event_type='triggered', reason='percentage_loss_threshold_exceeded', loss_percent (daily loss %)

**Given** the circuit breaker is triggered
**When** a new signal passes safety filtering and is ready for position creation
**Then** the position creation pipeline checks the circuit breaker status
**And** if a 'triggered' event exists with no corresponding 'reset' event, position creation is BLOCKED
**And** the signal is logged as filtered with filter_reason='circuit_breaker_active'
**And** the block is logged with structured logging (level: WARN, event: position_blocked_circuit_breaker, signal_id: value)

**Given** the circuit breaker is active (triggered)
**When** open positions reach their exit conditions
**Then** exit strategies continue to execute normally (ADR-004: Circuit Breaker Non-Closing)
**And** positions are closed to preserve remaining capital
**And** NO new positions are created until the circuit breaker is reset

**Given** the circuit breaker is active
**When** I view the Dashboard tab
**Then** a prominent warning banner displays: "⚠️ Circuit Breaker Active - New positions blocked. Daily loss: -$550 (-15.5%)"
**And** the banner has a [View Details] button that shows circuit breaker events

**Given** the circuit breaker is active
**When** I view the Config tab
**Then** the Circuit Breaker status indicator shows: "Active 🔴" with trigger reason and timestamp
**And** a [Reset Circuit Breaker] button is available for manual reset

### Story 5.4: Circuit Breaker Reset & Event Logging

As an operator,
I want to manually reset the circuit breaker or have it auto-reset daily,
So that I can resume trading after addressing the underlying issues.

**Acceptance Criteria:**

**Given** the circuit breaker is active (triggered event exists)
**When** I click [Reset Circuit Breaker] in the Config tab
**Then** a confirmation dialog appears: "Reset circuit breaker and resume position creation?"
**And** the dialog has [Confirm] and [Cancel] buttons

**Given** I confirm the circuit breaker reset
**When** the reset executes
**Then** a new record is inserted into the `circuit_breaker_events` table with: event_type='reset', triggered_at=NOW(), reason='manual_reset', reset_by='operator'
**And** the reset is logged with structured logging (level: INFO, event: circuit_breaker_reset, reason: manual)
**And** position creation is re-enabled immediately
**And** a success message displays: "Circuit breaker reset successfully"

**Given** the circuit breaker is active
**When** the daily reset worker runs (scheduled at 00:00 UTC, beginning of new trading day)
**Then** the worker checks for active circuit breaker events (triggered with no matching reset)
**And** if found, the worker automatically inserts a 'reset' event with reason='automatic_daily_reset'
**And** the reset is logged with structured logging (level: INFO, event: circuit_breaker_auto_reset)

**Given** I want to audit circuit breaker history
**When** I view the Config tab Circuit Breaker section
**Then** I see a history table showing all circuit breaker events:
- Event Type (Triggered/Reset)
- Timestamp
- Reason (daily_loss_limit_exceeded, percentage_loss_threshold_exceeded, manual_reset, automatic_daily_reset)
- Loss Amount/Percent (for triggered events)
**And** the table shows the last 30 days of events

**Given** the circuit breaker has been triggered and reset multiple times
**When** I analyze the event history
**Then** I can identify patterns (e.g., "Circuit breaker triggered 3 times in past 7 days")
**And** I can make informed decisions about adjusting thresholds or pausing live trading

### Story 5.5: System Health Monitoring & Status Indicators

As an operator,
I want to monitor system health across all critical components,
So that I can quickly identify and resolve issues affecting trading operations.

**Acceptance Criteria:**

**Given** I am on the Config tab in the "API Keys" section
**When** the tab loads
**Then** I see status indicators for all critical services:
- Helius Webhook: "Connected ✅" or "Disconnected ❌" with last signal timestamp
- Supabase Database: "Connected ✅" or "Error ❌" with connection status
- Jupiter API: "Operational ✅" or "Degraded ⚠️" based on recent API call success rate
- DexScreener API: "Operational ✅" or "Degraded ⚠️" based on recent API call success rate

**Given** the Helius webhook is connected and receiving signals
**When** the status indicator updates
**Then** it displays: "Connected ✅ | Last signal: 2 minutes ago"
**And** the timestamp updates in real-time (or near real-time)

**Given** the Helius webhook has not received signals for >30 minutes
**When** the health check worker evaluates the status
**Then** the indicator changes to: "Warning ⚠️ | No signals for 35 minutes"
**And** a warning is logged with structured logging (level: WARN, event: webhook_silence_detected, duration_minutes: value)

**Given** the Jupiter API has failed >20% of calls in the past hour
**When** the health check worker evaluates the status
**Then** the indicator changes to: "Degraded ⚠️ | 25% failure rate (past hour)"
**And** the degradation is logged with structured logging (level: WARN, event: api_degraded, service: jupiter, failure_rate: value)

**Given** I want to refresh system health status manually
**When** I click a [Refresh Status] button in the Config tab
**Then** the system executes health checks for all services immediately
**And** all status indicators update with current data
**And** a timestamp displays: "Last checked: just now"

**Given** critical system errors occur (database connection lost, all API sources down)
**When** the health check worker detects the errors
**Then** the errors are logged with structured logging (level: ERROR, event: critical_system_failure, component: value)
**And** a critical alert banner displays across all UI tabs: "🚨 Critical Error: [Component] unavailable"
**And** the system continues to operate in degraded mode (e.g., no new positions, existing positions monitored)

**Given** I am on the Dashboard tab
**When** the application loads
**Then** I see a System Health summary widget showing:
- Overall Status: "Healthy ✅" or "Degraded ⚠️" or "Critical 🔴"
- Active Positions: count
- Webhook Status: Connected/Disconnected
- Circuit Breaker Status: Inactive/Active
**And** clicking the widget navigates to the Config tab for detailed status
