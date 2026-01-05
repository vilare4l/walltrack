# Requirements Inventory

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
- Core exit strategies (stop-loss, trailing-stop, scaling-out) with per-wallet configuration and per-position overrides
- Stop-loss triggers first (capital protection priority)
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
**FR-6 (Exit Strategy Execution):** Epic 3 - Core exit strategies with priority logic (stop-loss, trailing-stop, scaling-out)
**FR-7 (Wallet Activity Monitoring):** Epic 4 - Source wallet sell detection + mirror-exit execution
**FR-8 (Performance Tracking & Analytics):** Epic 4 - Per-wallet metrics and data-driven curation
**FR-9 (System Configuration & Status):** Epic 5 - Centralized config + health monitoring
