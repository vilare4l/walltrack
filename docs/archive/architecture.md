---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9]
inputDocuments: ['docs/prd.md']
workflowType: 'architecture'
lastStep: 9
project_name: 'walltrack'
user_name: 'Christophe'
date: '2026-01-04'
completed: true
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**

WallTrack implements a 9-feature intelligent copy-trading pipeline for Solana memecoins:

1. **Watchlist Management (FR-1)**: Manual CRUD for wallet addresses with per-wallet mode toggle (simulation/live) and exit strategy defaults
2. **Real-Time Signal Detection (FR-2)**: Helius webhooks deliver swap notifications from watchlist wallets
3. **Token Safety Analysis (FR-3)**: Automated scoring system (4 checks: liquidity ≥$50K, holder distribution, contract analysis, age ≥24h) with configurable threshold (default 0.60)
4. **Position Creation & Management (FR-4)**: Dual-mode execution (simulation = full pipeline without Jupiter API, live = real swaps via Jupiter)
5. **Price Monitoring (FR-5)**: Jupiter Price API V3 (30-60s polling) for exit strategy triggers with ±1% accuracy requirement, DexScreener fallback
6. **Exit Strategy Execution (FR-6)**: Multiple strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) with priority logic and per-wallet/per-position configuration
7. **Wallet Activity Monitoring (FR-7)**: Helius webhooks monitor source wallet sales for mirror-exit triggers
8. **Performance Tracking & Analytics (FR-8)**: Per-wallet win rate, PnL, signal analytics (all/30d/7d/24h) for data-driven curation
9. **System Configuration & Status (FR-9)**: Centralized config UI for capital, risk parameters, safety thresholds, webhook/circuit breaker status

**Architectural Implications:**
- Event-driven architecture required (webhook-triggered pipeline)
- State machine for position lifecycle (created → monitored → exit triggered → closed)
- Multi-strategy exit logic with priority resolution
- Dual-mode execution pattern (simulation/live) without code duplication
- Real-time data flow orchestration across 3 external APIs

**Non-Functional Requirements:**

Critical NFRs shaping architectural decisions:

| NFR | Requirement | Architectural Impact |
|-----|-------------|---------------------|
| **Performance (NFR-1)** | Webhook→execution < 5s (P95) | Async processing, minimal I/O blocking, optimized data layer queries |
| **Reliability (NFR-2)** | ≥95% uptime, auto-restart on crash | Health checks, circuit breakers, graceful degradation, process supervision |
| **Security (NFR-3)** | Private key encryption, zero exposure in logs/UI | Secure key management, input validation, TLS for DB connections |
| **Data Integrity (NFR-4)** | Atomic position lifecycle, audit trail | Database transactions, event sourcing for audit, data validation |
| **Observability (NFR-5)** | Complete visibility into decisions | Structured logging, metrics, dashboard real-time state, queryable history |
| **Maintainability (NFR-6)** | ≥70% test coverage, clear separation of concerns | Layered architecture, dependency injection, comprehensive test suite |
| **Scalability (NFR-7)** | 10-20 wallets, 50-400 signals/day, burst handling | Async processing, database indexing, rate limiting, webhook queue |

**Scale & Complexity:**

- **Primary domain**: Blockchain/Web3 + Fintech (backend-heavy with operator UI)
- **Complexity level**: HIGH
  - Real-time trading system with sub-5s latency requirements
  - Financial data protection and wallet security
  - Multi-API orchestration with failure handling
  - Cryptocurrency regulations (future productization consideration)
  - Fraud prevention (rug detection, honeypot analysis)
- **Estimated architectural components**: 8-10 major components
  - Webhook receiver & signal processor
  - Token safety analyzer
  - Position manager (state machine)
  - Price monitor (polling worker)
  - Exit strategy executor
  - Jupiter swap client (live mode)
  - Performance analytics engine
  - Configuration service
  - Dashboard UI (Gradio)

### Technical Constraints & Dependencies

**Critical External Dependencies (system cannot function without):**
- **Helius API**: Webhook delivery for signal detection + wallet monitoring (SLA impact: missed signals = missed trades)
- **Jupiter API**: Swap execution + price monitoring (SLA impact: cannot execute live trades or monitor prices if down, simulation unaffected)
- **DexScreener API**: Fallback price monitoring if Jupiter Price API unavailable (SLA impact: degraded price monitoring reliability)
- **Supabase**: PostgreSQL for state persistence (SLA impact: system inoperable without database)

**Technology Stack Constraints:**
- Python 3.11+ (operator's learning path)
- Gradio for UI (rapid iteration requirement)
- Supabase free tier initially (cost constraint, can upgrade to $25/month)
- FastAPI for API endpoints (async support needed)

**Data Volume Constraints:**
- Supabase free tier limits: 500MB storage, 2GB bandwidth/month
- Mitigation: 90-day data retention policy, archive old signals/positions

**Development Constraints:**
- Solo operator (Christophe) learning Python
- Code must be approachable, well-documented, testable
- AI-assisted development (Claude Code) = accessible complex infrastructure

### Cross-Cutting Concerns Identified

**Security:**
- Wallet private key management (encryption at rest, no logs/UI exposure)
- API authentication (Helius/Jupiter keys in env variables)
- Input validation (Solana address format checks)
- Audit trail for all wallet operations
- Rate limiting on API endpoints

**Error Handling & Resilience:**
- External API failure handling (Helius/Jupiter/DexScreener)
- Webhook delivery reliability monitoring (48h timeout alert)
- Circuit breakers (max drawdown 20%, win rate < 40%, 3 consecutive losses)
- Retry logic with exponential backoff
- Graceful degradation (use last known price if API unavailable)

**Logging & Observability:**
- Structured logging for all signals, positions, exits, circuit breaker triggers
- Performance metrics (execution latency, API response times)
- Dashboard real-time state view
- Historical logs queryable for debugging
- Transparency = operator trust

**Configuration Management:**
- Hierarchical configuration: System defaults → per-wallet defaults → per-position overrides
- 30+ configurable parameters (trading, risk management, safety analysis, exit strategies)
- Config persistence in Supabase with JSON backup on every change
- Parameter validation and range checks
- Real-time config changes without restart

**Testing Strategy:**
- Unit tests with mocked external APIs (≥70% coverage target)
- Integration tests for data layer and API clients
- E2E tests with Playwright (separate test run to avoid interference)
- Simulation mode as built-in testing environment

**Data Consistency:**
- Atomic database transactions for position lifecycle
- Event sourcing for audit trail
- PnL calculation reconciliation checks
- Price data staleness monitoring (5-minute threshold)

## Starter Template Evaluation

### Primary Technology Domain

**Backend Python + Blockchain/Web3 + Gradio UI** - Highly specialized trading system

### Technical Stack (Defined by PRD)

The project has an established technology stack based on operator learning path and system requirements:

- **Language**: Python 3.11+ (operator's learning journey)
- **API Framework**: FastAPI (async support for webhooks and API orchestration)
- **UI Framework**: Gradio (rapid iteration for operator interface)
- **Database**: Supabase PostgreSQL (free tier → paid as needed)
- **Validation**: Pydantic v2 (type safety throughout)
- **HTTP Client**: httpx (async API clients)
- **Testing**: Pytest (unit + integration + E2E with Playwright)
- **Dependency Management**: uv (modern Python package management)

### Starter Options Considered

**Evaluation Conclusion: No Suitable Starter Template**

Generic Python/FastAPI starters were evaluated but rejected for the following reasons:

1. **Highly Specialized Domain**: Copy-trading blockchain systems are not covered by standard starters
2. **Unique Integration Requirements**: Helius webhooks + Jupiter aggregator (swaps + prices) orchestration
3. **Gradio UI vs. Standard Web**: Most starters assume React/Vue frontend, not Gradio operator interface
4. **Event-Driven Architecture**: Webhook-triggered pipeline with background workers not in standard templates
5. **Dual-Mode Execution Pattern**: Simulation/live mode switching is domain-specific

**Recommendation: Custom Architecture from Scratch**

This approach provides:
- Complete control over event-driven patterns
- Optimized for blockchain/trading domain
- Clear layered architecture for maintainability
- Learning-oriented structure (important for solo operator)

### Selected Approach: Custom Layered Architecture

**Rationale for Custom Approach:**

- **Domain Specialization**: Trading bot + blockchain + multiple APIs requires custom patterns
- **Stack Already Defined**: PRD specifies exact technologies (no flexibility needed from starter)
- **Learning Objective**: Building from scratch provides deeper understanding (operator goal)
- **Testability Requirements**: Custom architecture allows proper dependency injection and mocking
- **AI-Assisted Development**: Claude Code makes custom architecture accessible

**Project Structure:**

```
walltrack/
├── src/walltrack/
│   ├── core/              # Business logic (signal processing, exit strategies)
│   ├── services/          # External API clients (Helius, Jupiter, DexScreener)
│   ├── data/              # Data layer (Supabase repositories, models)
│   │   └── supabase/
│   │       └── migrations/  # SQL migration files
│   ├── workers/           # Background workers (price monitor, webhook processor)
│   ├── ui/                # Gradio dashboard interface
│   └── config/            # Configuration management
├── tests/
│   ├── unit/              # Unit tests with mocks
│   ├── integration/       # Integration tests (DB, API clients)
│   └── e2e/               # Playwright E2E tests (run separately)
├── migrations/            # SQL migrations for Supabase
├── pyproject.toml         # uv dependency management
└── .env.example           # Environment variable template
```

**Architectural Decisions Established by Custom Approach:**

**Language & Runtime:**
- Python 3.11+ with strict type hints (Pydantic models)
- Async-first design (FastAPI + httpx + asyncio workers)
- uv for dependency management (faster than pip/poetry)

**Layered Architecture:**
- **Presentation Layer**: Gradio UI (Dashboard, Watchlist, Config pages)
- **Application Layer**: FastAPI endpoints (webhooks, health checks, API)
- **Business Logic Layer**: Core domain logic (signal filtering, exit strategies, position management)
- **Data Access Layer**: Supabase repositories with Pydantic models
- **External Services Layer**: API clients (Helius, Jupiter, DexScreener)

**Code Organization Patterns:**
- Dependency injection for testability (services injected into business logic)
- Repository pattern for data access (abstract Supabase behind interfaces)
- Service layer for external APIs (centralized error handling, retry logic)
- Event-driven processing (webhook → signal → position pipeline)

**Testing Infrastructure:**
- Unit tests: Mock all external dependencies (API clients, database)
- Integration tests: Real Supabase (local or cloud), mocked external APIs
- E2E tests: Playwright for Gradio UI workflows
- Separate test runs to avoid Playwright interference

**Development Experience:**
- Hot reload: FastAPI dev server + Gradio auto-refresh
- Type safety: Pydantic models + mypy static analysis
- Linting: Ruff (fast Python linter/formatter)
- Debugging: VS Code Python debugger with FastAPI integration

**Configuration Management:**
- Environment variables (.env) for secrets (API keys, database URL)
- Supabase `config` table for runtime configuration
- Hierarchical config (system → wallet → position)
- JSON backup on every config change

**Note:** Project initialization will be manual (create directory structure, install dependencies with uv) rather than using a CLI command. This should be the first implementation task.

---

## Documentation Structure

This architecture document is complemented by detailed design guides and SQL migrations:

### Database Design Guides (`docs/database-design/`)

Each table has a dedicated design guide explaining the "why" behind every field:

- **[README.md](./database-design/README.md)** - Architectural patterns overview + ADRs (Architecture Decision Records)
- **[01-config.md](./database-design/01-config.md)** - Configuration Singleton pattern
- **[02-exit-strategies.md](./database-design/02-exit-strategies.md)** - Catalog pattern (DRY templates)
- **[03-wallets.md](./database-design/03-wallets.md)** - Registry pattern (watchlist)
- **[04-tokens.md](./database-design/04-tokens.md)** - Read-Through Cache pattern
- **[05-signals.md](./database-design/05-signals.md)** - Event Sourcing pattern (immutable)
- **[06-orders.md](./database-design/06-orders.md)** - Command Log pattern (retry mechanism)
- **[07-positions.md](./database-design/07-positions.md)** - Aggregate Root pattern (PnL tracking)
- **[08-performance.md](./database-design/08-performance.md)** - Materialized View pattern (batch refresh)
- **[09-circuit-breaker-events.md](./database-design/09-circuit-breaker-events.md)** - Event Sourcing pattern (audit trail)

**Each design guide contains:**
- Pattern rationale
- Field-by-field "why" explanations
- SQL examples
- Edge cases & FAQ
- Related stories for implementation

### SQL Migrations (`src/walltrack/data/supabase/migrations/`)

Executable SQL scripts with inline documentation (COMMENT ON):

- `000_helper_functions.sql` - Schema + utility functions
- `001_config_table.sql` - Config singleton
- `002_exit_strategies_table.sql` - Exit strategies catalog + default templates
- `003_wallets_table.sql` - Wallets registry
- `004_tokens_table.sql` - Tokens cache
- `005_signals_table.sql` - Signals event log
- `006_orders_table.sql` - Orders transaction log
- `007_positions_table.sql` - Positions tracking
- `008_performance_table.sql` - Performance metrics
- `009_circuit_breaker_events_table.sql` - Circuit breaker audit trail

**Agent workflow:** For any table-related task, read the design guide first, then consult the migration SQL for implementation details.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data architecture & schema design (Supabase PostgreSQL + Pydantic models)
- External API client patterns (Helius, Jupiter, DexScreener)
- Webhook receiver architecture (FastAPI endpoint handling)
- Position state machine design (lifecycle management)
- Secret management approach (environment variables)

**Important Decisions (Shape Architecture):**
- Background worker patterns (price monitor, webhook processor)
- Error handling & retry strategies (external API failures)
- Logging & observability infrastructure (structured logging)
- Testing patterns (unit/integration/E2E separation)
- Configuration management (hierarchical system)

**Deferred Decisions (Post-MVP):**
- Authentication system (personal use only in MVP)
- CI/CD pipeline (manual testing acceptable initially)
- Distributed caching (Supabase sufficient for MVP scale)
- Multi-tenancy architecture (future productization)
- Advanced monitoring/alerting (basic health checks sufficient)

### Data Architecture

**Database: Supabase PostgreSQL (Free tier → Paid)**

**Decision:** Use Supabase managed PostgreSQL with repository pattern abstraction

**Rationale:**
- PRD-specified constraint (Supabase free tier initially)
- Managed service reduces operational overhead for solo operator
- PostgreSQL provides ACID transactions (critical for position lifecycle)
- Free tier limits (500MB storage, 2GB bandwidth/month) sufficient for MVP
- Easy upgrade path to paid tier ($25/month) when needed

**Schema Management:**

**Decision:** Raw SQL migrations in `src/walltrack/data/supabase/migrations/`

**Rationale:**
- Explicit control over schema changes (no ORM magic)
- Version-controlled migration files
- Simple execution (psql or Supabase CLI)
- Learning-oriented (operator understands exact SQL)
- Migration numbering: `001_config_table.sql`, `002_wallets_table.sql`, etc.

**Migration Template:**
```sql
-- Migration: NNN_description.sql
-- Date: YYYY-MM-DD
-- Story: X.Y

CREATE TABLE IF NOT EXISTS walltrack.table_name (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_table_field ON walltrack.table_name(field);

-- Rollback (commented)
-- DROP TABLE IF EXISTS walltrack.table_name;
```

**Data Validation: Pydantic v2**

**Decision:** Pydantic models for all data validation (API requests, database models, external API responses)

**Rationale:**
- Type safety throughout the application
- Automatic validation with clear error messages
- JSON serialization/deserialization built-in
- IDE autocomplete support
- Operator learning Python benefits from explicit types

**Repository Pattern:**

**Decision:** Abstract Supabase behind repository interfaces

**Rationale:**
- Testability (mock repositories in unit tests)
- Separation of concerns (business logic doesn't know about Supabase)
- Future flexibility (could swap database if needed)
- Clear contract for data operations

**Example:**
```python
class WalletRepository(ABC):
    @abstractmethod
    async def get_by_address(self, address: str) -> Wallet | None: ...

    @abstractmethod
    async def create(self, wallet: WalletCreate) -> Wallet: ...

class SupabaseWalletRepository(WalletRepository):
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
```

**Caching Strategy:**

**Decision:** No distributed cache in MVP (defer to V2 if performance bottleneck)

**Rationale:**
- Supabase query performance sufficient for MVP scale (10-20 wallets)
- Premature optimization avoided
- Can add Redis later if needed (token metadata caching likely candidate)
- Complexity reduced for solo operator

### Authentication & Security

**Authentication: None (MVP)**

**Decision:** No authentication system in MVP - localhost-only deployment

**Rationale:**
- Personal use (single operator)
- Localhost deployment (no public exposure)
- Complexity reduction
- Can add auth in V2 if productized (consider Supabase Auth)

**Secret Management: Environment Variables**

**Decision:** Use python-dotenv with `.env` file for all secrets

**Rationale:**
- Simple and explicit
- Industry standard (12-factor app)
- `.env` gitignored (never committed)
- `.env.example` provides template for setup

**Required Secrets:**
```bash
# .env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
HELIUS_API_KEY=xxx
WALLET_PRIVATE_KEY=xxx  # Encrypted or base58 encoded
DEXSCREENER_API_KEY=xxx  # If required
JUPITER_API_KEY=xxx  # If required
```

**Private Key Security:**

**Decision:** Environment variable with additional precautions

**Rationale:**
- Never log private key (custom logging filter)
- Never expose in UI (masked in config page)
- Consider hardware wallet integration in V2
- Audit all code accessing WALLET_PRIVATE_KEY

**Audit Trail:**

**Decision:** Structured logging with structlog for all critical operations

**Rationale:**
- Queryable logs (JSON format)
- Timestamp, level, context included automatically
- Log all: signals received, positions created, trades executed, exits triggered
- Transparency = operator trust (NFR-5)

**Log Structure:**
```python
logger.info(
    "position_created",
    wallet_id=wallet_id,
    token=token_address,
    entry_price=entry_price,
    mode="simulation"
)
```

### API & Communication Patterns

**API Framework: FastAPI**

**Decision:** FastAPI for all HTTP endpoints (webhooks, health checks, metrics)

**Rationale:**
- PRD-specified (async support needed)
- Native async/await support (critical for webhook processing)
- Automatic OpenAPI documentation
- Pydantic integration (request/response validation)
- High performance (Starlette + uvicorn)

**Endpoint Structure:**

**Critical Endpoints:**
- `POST /webhooks/helius` - Receive swap notifications from Helius
- `GET /health` - Health check (webhook status, DB connection, circuit breakers)
- `GET /metrics` - System metrics (Prometheus-compatible optional V2)

**API Error Handling:**

**Decision:** HTTPException for API errors + custom exception hierarchy

**Rationale:**
- FastAPI native exception handling
- HTTP status codes map to business errors
- Consistent error response format

**Error Response Format:**
```json
{
  "error": "SafetyCheckFailed",
  "detail": "Token safety score 0.45 below threshold 0.60",
  "token": "xyz...",
  "timestamp": "2026-01-04T12:00:00Z"
}
```

**External API Client Pattern:**

**Decision:** httpx AsyncClient with retry logic (tenacity) + circuit breaker

**Rationale:**
- Async support (non-blocking API calls)
- Connection pooling (reuse connections)
- Timeout configuration (prevent hanging requests)
- Retry on transient failures (exponential backoff)
- Circuit breaker prevents cascade failures

**Client Example:**
```python
class HeliusClient:
    def __init__(self, api_key: str):
        self.client = httpx.AsyncClient(timeout=10.0)
        self.api_key = api_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get_transaction(self, tx_signature: str) -> Transaction:
        response = await self.client.get(...)
        response.raise_for_status()
        return Transaction(**response.json())
```

**Rate Limiting:**

**Decision:** No rate limiting on webhook endpoint (trusted Helius source), basic rate limiting on metrics endpoint

**Rationale:**
- Helius webhooks are authenticated (signature verification)
- Metrics endpoint low traffic (operator access only)
- Can add rate limiting in V2 if productized

**Communication Between Components:**

**Decision:** Direct function calls (monolithic architecture)

**Rationale:**
- Single Python process (no microservices)
- Dependency injection for component wiring
- Background workers run in asyncio tasks (same process)
- No message queue needed for MVP scale

### Frontend Architecture (Gradio)

**UI Framework: Gradio**

**Decision:** Gradio multi-tab interface (Dashboard, Watchlist, Config)

**Rationale:**
- PRD-specified (rapid iteration for operator interface)
- No JavaScript needed (Python-only)
- Auto-refresh for real-time updates
- Built-in form validation
- Fast development (vs. React + FastAPI)

**Tab Structure:**

1. **Dashboard Tab:**
   - Active positions table (real-time)
   - PnL summary (total, per wallet)
   - Recent signals log
   - Circuit breaker status

2. **Watchlist Tab:**
   - Wallet list (add/remove/edit)
   - Per-wallet config (mode, exit strategies)
   - Performance metrics (win rate, signal counts)

3. **Config Tab:**
   - System parameters (capital, risk %, safety threshold)
   - Webhook status indicator
   - Circuit breaker config

**State Management:**

**Decision:** No complex state management - Gradio handles updates

**Rationale:**
- Gradio auto-refresh on data changes
- No need for React-style state management
- Direct database queries on page load
- Simple and maintainable

**Real-Time Updates:**

**Decision:** Gradio auto-refresh (polling interval: 5-10 seconds)

**Rationale:**
- Sufficient for operator monitoring (not HFT UI)
- No WebSocket complexity needed
- Gradio built-in feature

### Infrastructure & Deployment

**Hosting: Local Machine (Personal Use)**

**Decision:** Deploy on operator's local machine (Linux/Windows)

**Rationale:**
- Personal use only (no public access needed)
- Zero hosting costs
- Full control over environment
- No cloud vendor lock-in

**Process Management:**

**Decision:** systemd (Linux) or Windows Service for auto-restart

**Rationale:**
- Auto-restart on crash (NFR-2: ≥95% uptime)
- Daemon process (runs 24/7)
- Logging to file (systemd journal or Windows Event Log)

**Example systemd Service:**
```ini
[Unit]
Description=WallTrack Copy Trading Bot
After=network.target

[Service]
Type=simple
User=christophe
WorkingDirectory=/home/christophe/walltrack
ExecStart=/home/christophe/walltrack/.venv/bin/uvicorn walltrack.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Logging:**

**Decision:** structlog → rotating file logs (max 100MB, keep 7 days)

**Rationale:**
- Structured JSON logs (queryable)
- File rotation prevents disk fill
- 7-day retention sufficient for debugging
- Can ship to external log aggregator in V2 (e.g., Loki)

**Log Locations:**
- `/var/log/walltrack/app.log` (Linux)
- `C:\ProgramData\walltrack\logs\app.log` (Windows)

**Monitoring:**

**Decision:** Custom health checks exposed via FastAPI `/health` endpoint

**Rationale:**
- Simple HTTP GET for monitoring
- Returns JSON with component status (DB, webhooks, APIs)
- Operator can check manually or use simple monitoring tool (e.g., Uptime Kuma)

**Health Check Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "helius_webhook": "active",
  "last_signal": "2026-01-04T11:55:00Z",
  "circuit_breaker": "inactive",
  "uptime_hours": 72
}
```

**Environment Configuration:**

**Decision:** `.env` file for environment-specific config

**Rationale:**
- Same codebase for dev/prod
- Environment variables control behavior
- No code changes needed for deployment

**Environment Variables:**
```bash
ENV=production  # or development
LOG_LEVEL=INFO  # DEBUG for dev
SUPABASE_URL=...
```

**CI/CD:**

**Decision:** No CI/CD pipeline in MVP - manual testing before deploy

**Rationale:**
- Solo operator (no team collaboration)
- Manual testing acceptable (run pytest before deploy)
- Can add GitHub Actions in V2 if needed
- Reduced complexity for learning operator

**Backup Strategy:**

**Decision:** Supabase automatic backups + manual config JSON backups

**Rationale:**
- Supabase provides daily backups (point-in-time recovery)
- Config exported to JSON on every change (local backup)
- Position/signal data recoverable from Supabase
- No need for separate backup infrastructure

### Decision Impact Analysis

**Implementation Sequence:**

1. **Project Setup** - Create directory structure, uv dependencies, .env template
2. **Database Schema** - Create Supabase migrations (config, wallets, tokens, signals, positions, performance)
3. **Data Layer** - Implement repository pattern + Pydantic models
4. **External API Clients** - Helius, Jupiter, DexScreener clients with retry logic
5. **Core Business Logic** - Signal processor, token safety analyzer, position manager, exit strategy executor
6. **FastAPI Endpoints** - Webhook receiver, health check, metrics
7. **Background Workers** - Price monitor (asyncio task)
8. **Gradio UI** - Dashboard, Watchlist, Config tabs
9. **Testing Infrastructure** - Unit tests, integration tests, E2E tests
10. **Deployment Setup** - systemd service, logging configuration, health monitoring

**Cross-Component Dependencies:**

**Data Layer → Everything:**
- All components depend on repositories for state persistence
- Pydantic models shared across layers

**API Clients → Business Logic:**
- Signal processor depends on Helius client
- Position executor depends on Jupiter client
- Price monitor depends on Jupiter Price client (DexScreener fallback)

**Business Logic → Workers:**
- Price monitor triggers exit strategy executor
- Webhook processor triggers signal processor

**Gradio UI → Data Layer:**
- Dashboard queries repositories for display
- Watchlist CRUD operations call repositories
- Config changes persist to Supabase

**Error Handling → Logging:**
- All exceptions logged via structlog
- Circuit breakers log trigger events
- Audit trail for transparency (NFR-5)

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:** 12 areas where AI agents could make different choices without explicit guidance

**Categories:**
- Naming Conventions (4 conflict points)
- Structure Organization (3 conflict points)
- Format Standards (3 conflict points)
- Process Patterns (2 conflict points)

### Naming Patterns

**Database Naming Conventions:**

**Tables:**
- Format: `snake_case` plural
- Examples: `wallets`, `positions`, `tokens`, `signals`
- Anti-pattern: `Wallet`, `wallet`, `WalletTable`

**Columns:**
- Format: `snake_case`
- Primary keys: `id` (UUID)
- Foreign keys: `{table}_id` (e.g., `wallet_id`, `token_id`)
- Timestamps: `created_at`, `updated_at` (TIMESTAMPTZ)
- Booleans: `is_{property}` or `has_{property}` (e.g., `is_active`, `has_mirror_exit`)
- Anti-pattern: `walletId`, `createdAt`, `active` (camelCase or missing prefix)

**Indexes:**
- Format: `idx_{table}_{column(s)}`
- Examples: `idx_positions_wallet_id`, `idx_signals_created_at`
- Anti-pattern: `positions_wallet_id_index`, `wallet_idx`

**Constraints:**
- Foreign keys: `fk_{source_table}_{target_table}`
- Unique: `uq_{table}_{column(s)}`
- Examples: `fk_positions_wallets`, `uq_wallets_address`

**API Naming Conventions:**

**Endpoints:**
- Format: `/api/{resource}` (plural nouns)
- Examples: `/api/wallets`, `/api/positions`, `/api/tokens`
- Special: `/webhooks/{provider}` (e.g., `/webhooks/helius`)
- Anti-pattern: `/api/wallet`, `/api/getWallets`, `/api/wallet-list`

**Route Parameters:**
- Format: `{parameter_name}` in path
- Examples: `/api/wallets/{wallet_id}`, `/api/positions/{position_id}`
- Anti-pattern: `:walletId`, `<wallet_id>`, `/api/wallets/:id`

**Query Parameters:**
- Format: `snake_case`
- Examples: `?mode=simulation`, `?wallet_id=xxx`, `?start_date=2026-01-01`
- Anti-pattern: `?walletId=xxx`, `?startDate=xxx` (camelCase)

**HTTP Methods:**
- GET: Retrieve resources
- POST: Create resources, trigger actions (webhooks)
- PUT: Full resource update
- PATCH: Partial resource update
- DELETE: Remove resources

**Code Naming Conventions:**

**Python Files:**
- Format: `snake_case.py`
- Examples: `wallet_repository.py`, `helius_client.py`, `token_safety.py`
- Anti-pattern: `WalletRepository.py`, `helius-client.py`, `tokenSafety.py`

**Python Classes:**
- Format: `PascalCase`
- Examples: `WalletRepository`, `HeliusClient`, `TokenSafetyAnalyzer`
- Anti-pattern: `wallet_repository`, `Helius_Client`, `token_safety_analyzer`

**Python Functions/Methods:**
- Format: `snake_case`
- Examples: `get_wallet()`, `create_position()`, `analyze_token_safety()`
- Anti-pattern: `getWallet()`, `createPosition()`, `analyzeTokenSafety()`

**Python Variables:**
- Format: `snake_case`
- Examples: `wallet_id`, `entry_price`, `safety_score`
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`, `DEFAULT_SLIPPAGE`)
- Anti-pattern: `walletId`, `entryPrice`, `safetyScore` (camelCase)

**Pydantic Models:**
- Format: `PascalCase` with descriptive suffix
- Base models: `Wallet`, `Position`, `Token`
- Create models: `WalletCreate`, `PositionCreate`
- Update models: `WalletUpdate`, `PositionUpdate`
- Response models: `WalletResponse`, `PositionResponse`
- Anti-pattern: `WalletModel`, `CreateWallet`, `wallet_response`

### Structure Patterns

**Project Organization:**

**Source Code Structure:**
```
src/walltrack/
├── core/              # Business logic (no external dependencies)
│   ├── signals/       # Signal processing
│   ├── safety/        # Token safety analysis
│   ├── positions/     # Position management
│   └── strategies/    # Exit strategy logic
├── services/          # External API clients
│   ├── helius.py      # Helius API client
│   ├── jupiter.py     # Jupiter API client
│   └── dexscreener.py # DexScreener API client
├── data/              # Data layer
│   ├── models/        # Pydantic models
│   ├── repositories/  # Repository interfaces + implementations
│   └── supabase/      # Supabase-specific code
│       ├── client.py  # Supabase client setup
│       └── migrations/ # SQL migration files
├── workers/           # Background workers
│   ├── price_monitor.py
│   └── webhook_processor.py
├── ui/                # Gradio interface
│   ├── dashboard.py
│   ├── watchlist.py
│   └── config.py
├── config/            # Configuration management
│   ├── settings.py    # Pydantic settings (loads .env)
│   └── logging.py     # Logging configuration
└── main.py            # FastAPI app entry point
```

**Test Organization:**
```
tests/
├── unit/              # Unit tests (mocked dependencies)
│   ├── core/          # Mirror src/walltrack/core structure
│   ├── services/
│   └── data/
├── integration/       # Integration tests (real DB, mocked APIs)
│   ├── repositories/
│   └── clients/
└── e2e/               # End-to-end tests (Playwright)
    └── ui/
```

**File Structure Patterns:**

**Configuration Files:**
- `.env` - Environment variables (gitignored)
- `.env.example` - Template for .env (committed)
- `pyproject.toml` - uv dependencies + project metadata
- `.gitignore` - Standard Python gitignore
- `README.md` - Project documentation

**Migration Files:**
- Location: `src/walltrack/data/supabase/migrations/`
- Naming: `NNN_description.sql` (e.g., `001_config_table.sql`)
- Sequential numbering (001, 002, 003, ...)

**Documentation:**
- `README.md` - Setup and run instructions
- `docs/prd.md` - Product requirements
- `docs/architecture.md` - This document
- Inline docstrings for complex functions (Google style)

### Format Patterns

**API Response Formats:**

**Success Response (200):**
```json
{
  "id": "uuid-here",
  "wallet_address": "...",
  "mode": "simulation",
  "created_at": "2026-01-04T12:00:00Z"
}
```

**Error Response (4xx/5xx):**
```json
{
  "error": "SafetyCheckFailed",
  "detail": "Token safety score 0.45 below threshold 0.60",
  "token": "xyz...",
  "timestamp": "2026-01-04T12:00:00Z"
}
```

**List Response (200):**
```json
{
  "items": [...],
  "total": 10,
  "page": 1,
  "page_size": 20
}
```

**Webhook Payload (Helius → WallTrack):**
```json
{
  "signature": "...",
  "type": "SWAP",
  "source_wallet": "...",
  "token_in": "...",
  "token_out": "...",
  "amount": 1000000,
  "timestamp": "2026-01-04T12:00:00Z"
}
```

**Data Exchange Formats:**

**Date/Time:**
- Format: ISO 8601 strings with timezone
- Example: `"2026-01-04T12:00:00Z"` or `"2026-01-04T12:00:00+00:00"`
- Storage: PostgreSQL `TIMESTAMPTZ`
- Anti-pattern: Unix timestamps, date without timezone

**JSON Field Naming:**
- Format: `snake_case` (Python convention)
- Examples: `wallet_id`, `entry_price`, `created_at`
- Anti-pattern: `walletId`, `entryPrice`, `createdAt` (camelCase)

**Boolean Values:**
- Format: `true`/`false` (JSON standard)
- Storage: PostgreSQL `BOOLEAN`
- Anti-pattern: `1`/`0`, `"true"`/`"false"` (strings)

**Decimal Numbers:**
- Format: JSON number (not string)
- Precision: Use Python `Decimal` for financial calculations
- Storage: PostgreSQL `NUMERIC` for prices/amounts
- Example: `{"price": 0.000123}` not `{"price": "0.000123"}`

**UUID Format:**
- Format: String representation `"550e8400-e29b-41d4-a716-446655440000"`
- Storage: PostgreSQL `UUID` type
- Generation: `gen_random_uuid()` in PostgreSQL or Python `uuid.uuid4()`

### Communication Patterns

**Logging Patterns:**

**Structured Logging (structlog):**
```python
logger.info(
    "position_created",
    wallet_id=wallet_id,
    token=token_address,
    entry_price=entry_price,
    mode="simulation",
    timestamp=datetime.utcnow().isoformat()
)
```

**Log Levels:**
- `DEBUG`: Detailed diagnostic information (dev only)
- `INFO`: General informational messages (signal received, position created)
- `WARNING`: Warning messages (retry attempt, fallback used)
- `ERROR`: Error messages (API failure, validation error)
- `CRITICAL`: Critical errors (circuit breaker triggered, system halt)

**Event Naming:**
- Format: `{entity}_{action}` (past tense)
- Examples: `position_created`, `signal_received`, `exit_triggered`, `circuit_breaker_activated`
- Anti-pattern: `create_position`, `PositionCreated`, `position-created`

**Log Output Format:**
```json
{
  "event": "position_created",
  "level": "info",
  "timestamp": "2026-01-04T12:00:00Z",
  "wallet_id": "uuid",
  "token": "address",
  "entry_price": 0.000123,
  "mode": "simulation"
}
```

**Event System Patterns:**

**Position Lifecycle Events:**
1. `signal_received` - Helius webhook processed
2. `safety_check_passed` or `safety_check_failed`
3. `position_created` - Position entered into DB
4. `price_updated` - Price monitor update
5. `exit_triggered` - Exit strategy condition met
6. `position_closed` - Position finalized with PnL

**Circuit Breaker Events:**
- `circuit_breaker_activated` - Trading halted
- `circuit_breaker_deactivated` - Trading resumed
- Include reason: `{"reason": "max_drawdown_exceeded", "threshold": 0.20, "current": 0.25}`

### Process Patterns

**Error Handling Patterns:**

**Exception Hierarchy:**
```python
class WallTrackError(Exception):
    """Base exception for WallTrack"""
    pass

class APIClientError(WallTrackError):
    """External API client errors"""
    pass

class SafetyCheckError(WallTrackError):
    """Token safety check failures"""
    pass

class PositionError(WallTrackError):
    """Position management errors"""
    pass
```

**Try-Except Pattern:**
```python
try:
    result = await external_api_call()
except httpx.HTTPStatusError as e:
    logger.error("api_request_failed", status_code=e.response.status_code, url=str(e.request.url))
    raise APIClientError(f"API request failed: {e}") from e
except httpx.TimeoutException as e:
    logger.warning("api_timeout", url=str(e.request.url))
    raise APIClientError("API request timeout") from e
```

**Retry Pattern (tenacity):**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def fetch_token_price(token_address: str) -> float:
    response = await jupiter_price_client.get_price(token_address)
    return response.price
```

**Validation Pattern (Pydantic):**
```python
class PositionCreate(BaseModel):
    wallet_id: UUID
    token: str
    entry_price: Decimal
    amount: Decimal
    mode: Literal["simulation", "live"]

    @field_validator("entry_price", "amount")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("must be positive")
        return v
```

**Circuit Breaker Pattern:**
```python
class CircuitBreaker:
    def __init__(self, threshold: float, window_size: int):
        self.threshold = threshold
        self.window_size = window_size
        self.failures: deque = deque(maxlen=window_size)

    def is_open(self) -> bool:
        if len(self.failures) < self.window_size:
            return False
        return sum(self.failures) / len(self.failures) > self.threshold

    def record_failure(self):
        self.failures.append(1)
        if self.is_open():
            logger.critical("circuit_breaker_activated", threshold=self.threshold)
```

### Enforcement Guidelines

**All AI Agents MUST:**

1. **Follow Python PEP 8 conventions** with `snake_case` for functions/variables, `PascalCase` for classes
2. **Use Pydantic models** for all data validation (API requests, database models, external API responses)
3. **Use repository pattern** for database access (never direct Supabase calls from business logic)
4. **Use structured logging** with `structlog` for all events (never plain `print()` statements)
5. **Use tenacity** for retry logic on external API calls (consistent exponential backoff)
6. **Use type hints** throughout (Python 3.11+ syntax with `|` for unions)
7. **Use async/await** for I/O operations (database, API calls, file operations)
8. **Use FastAPI dependency injection** for component wiring (avoid global state)
9. **Use pytest fixtures** for test setup (consistent test structure)
10. **Use `.env` file** for all secrets and environment-specific config (never hardcode)

**Pattern Enforcement:**

**Verification Methods:**
- Linting: `ruff check src/ tests/` (must pass before commit)
- Type checking: `mypy src/` (must pass before commit)
- Tests: `pytest tests/unit tests/integration -v` (must pass before commit)
- Code review: Manual review of patterns adherence

**Documentation:**
- Pattern violations logged as GitHub issues (future)
- Architecture document updated when patterns evolve
- New patterns documented with rationale and examples

**Update Process:**
- Propose pattern change via discussion with user
- Update architecture document with new pattern
- Refactor existing code to match new pattern (if breaking change)
- Communicate pattern change to all future AI agents

### Pattern Examples

**Good Examples:**

**Repository Implementation:**
```python
# src/walltrack/data/repositories/wallet_repository.py
from abc import ABC, abstractmethod
from uuid import UUID
from walltrack.data.models import Wallet, WalletCreate

class WalletRepository(ABC):
    @abstractmethod
    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        pass

    @abstractmethod
    async def create(self, wallet: WalletCreate) -> Wallet:
        pass

class SupabaseWalletRepository(WalletRepository):
    def __init__(self, supabase_client):
        self.client = supabase_client

    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        response = await self.client.table("wallets").select("*").eq("id", str(wallet_id)).execute()
        if not response.data:
            return None
        return Wallet(**response.data[0])

    async def create(self, wallet: WalletCreate) -> Wallet:
        response = await self.client.table("wallets").insert(wallet.model_dump()).execute()
        return Wallet(**response.data[0])
```

**FastAPI Endpoint:**
```python
# src/walltrack/main.py
from fastapi import FastAPI, Depends, HTTPException
from walltrack.data.repositories import WalletRepository
from walltrack.data.models import WalletCreate, WalletResponse

app = FastAPI()

@app.post("/api/wallets", response_model=WalletResponse, status_code=201)
async def create_wallet(
    wallet: WalletCreate,
    repo: WalletRepository = Depends(get_wallet_repository)
) -> WalletResponse:
    try:
        created_wallet = await repo.create(wallet)
        logger.info("wallet_created", wallet_id=created_wallet.id, address=created_wallet.address)
        return WalletResponse(**created_wallet.model_dump())
    except Exception as e:
        logger.error("wallet_creation_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create wallet")
```

**Structured Logging:**
```python
# Good
logger.info(
    "position_created",
    position_id=position.id,
    wallet_id=position.wallet_id,
    token=position.token,
    entry_price=position.entry_price,
    mode=position.mode
)

# Bad - plain print
print(f"Position created: {position.id}")

# Bad - unstructured logging
logger.info(f"Created position {position.id} for wallet {position.wallet_id}")
```

**Anti-Patterns (What to Avoid):**

**Hardcoded Configuration:**
```python
# Bad
HELIUS_API_KEY = "sk_abc123..."
SUPABASE_URL = "https://xxx.supabase.co"

# Good
from walltrack.config.settings import settings
helius_api_key = settings.helius_api_key
supabase_url = settings.supabase_url
```

**Direct Database Access from Business Logic:**
```python
# Bad
async def process_signal(signal_data: dict):
    # Direct Supabase call from business logic
    result = supabase.table("positions").insert(signal_data).execute()
    return result

# Good
async def process_signal(
    signal_data: SignalData,
    position_repo: PositionRepository
):
    position = PositionCreate(...)
    created = await position_repo.create(position)
    return created
```

**Inconsistent Naming:**
```python
# Bad - mixed conventions
class wallet_repository:  # Should be PascalCase
    def getWallet(self, walletId: str):  # Should be snake_case
        return None

# Good - consistent Python conventions
class WalletRepository:
    def get_wallet(self, wallet_id: str) -> Wallet | None:
        return None
```

**Missing Type Hints:**
```python
# Bad
async def create_position(wallet_id, token, price):
    ...

# Good
async def create_position(
    wallet_id: UUID,
    token: str,
    price: Decimal
) -> Position:
    ...
```

## Database Schema Design (Data-First Approach)

### Schema Overview

**Database:** PostgreSQL via Supabase (local instance)
**Schema:** `walltrack` (dedicated schema, not `public`)
**Approach:** Data-first - complete schema design upfront to minimize future migrations

### Entity Relationship Model

**Core Entities:**

1. **config** - System configuration (singleton)
2. **exit_strategies** - Reusable exit strategy templates
3. **wallets** - Watchlist wallets with mode (copy trading configuration)
4. **tokens** - Token metadata cache with safety analysis
5. **signals** - Raw signals from Helius webhooks (audit trail)
6. **orders** - Jupiter swap orders history (buy/sell transactions)
7. **positions** - Trading positions (open/closed) with PnL tracking
8. **performance** - Aggregated wallet performance metrics
9. **circuit_breaker_events** - Circuit breaker activation log

**Relationships:**
```
exit_strategies (1) → (N) wallets
wallets (1) → (N) signals
wallets (1) → (N) positions
wallets (1) → (N) orders
wallets (1) → (1) performance
tokens (1) → (N) signals
tokens (1) → (N) orders
positions (1) → (N) orders
signals (1) → (0-1) positions
orders (1) → (0-1) positions (entry/exit orders)
```

### Complete Table Definitions

**Note:** Full SQL schema is in migration files. This section provides architectural context and design decisions.

#### 1. config (System Configuration)

**📖 Design Guide:** [01-config.md](./database-design/01-config.md)
**🗄️ Migration SQL:** `001_config_table.sql`

**Purpose:** Global system configuration parameters (trading, risk, safety thresholds)

**Pattern:** Configuration Singleton - Only 1 row allowed (enforced by trigger)

**Key Field Groups:**
- **Trading Parameters**: capital, risk_per_trade_percent, position_sizing_mode
- **Risk Management**: stop_loss, trailing_stop, max_drawdown, circuit breaker thresholds
- **Safety Analysis**: token safety score threshold (default 0.60), liquidity/holder/age checks
- **Helius Webhook**: Global webhook config ([ADR-001](./database-design/README.md#adr-001) - ONE webhook for all wallets)
- **System Status**: circuit_breaker_active, webhook_last_signal_at

**Relations:** None (singleton, no FK)

#### 2. exit_strategies (Reusable Exit Strategy Templates)

**📖 Design Guide:** [02-exit-strategies.md](./database-design/02-exit-strategies.md)
**🗄️ Migration SQL:** `002_exit_strategies_table.sql`

**Purpose:** Catalog of reusable exit strategies (DRY pattern - avoid duplicating config across wallets)

**Pattern:** Catalog Pattern - Shared templates with 1:N relationship to wallets

**Key Field Groups:**
- **Stop Loss**: stop_loss_percent (e.g., 20% default)
- **Trailing Stop**: trailing_stop_enabled, trailing_stop_percent, activation_threshold
- **Scaling Out**: 3 levels (sell 50% at 2x, 25% at 3x, 25% ride forever)
- **Mirror Exit**: mirror_exit_enabled (exit when source wallet sells)
- **Usage**: is_default (UNIQUE constraint), is_active

**Key Decisions:**
- **NOT at wallet level**: Strategies are templates, overrides go in `positions.exit_strategy_override` ([ADR-002](./database-design/README.md#adr-002))
- **Default data**: 3 strategies pre-populated (Default, Conservative, Aggressive)

**Relations:**
- `1:N` → wallets (wallets.exit_strategy_id)
- `1:N` → positions (positions.exit_strategy_id)

#### 3. wallets (Watchlist / Copy Trading Configuration)

**📖 Design Guide:** [03-wallets.md](./database-design/03-wallets.md)
**🗄️ Migration SQL:** `003_wallets_table.sql`

**Purpose:** Registry of Solana wallets to monitor (copy-trading sources)

**Pattern:** Registry Pattern - Watchlist configuration with Helius sync tracking

**Key Field Groups:**
- **Identity**: address (Solana base58, 32-44 chars), label (human-readable)
- **Mode**: simulation | live (per-wallet toggle for progressive risk)
- **Exit Strategy**: exit_strategy_id (FK → exit_strategies, required)
- **Discovery Context**: discovery_source (twitter/telegram/scanner/manual), discovery_date, discovery_notes
- **Initial Performance**: initial_win_rate_percent, initial_trades_observed (validation before live mode)
- **Helius Sync**: helius_synced_at, helius_sync_status (pending/synced/error)
- **Status**: is_active (inactive wallets excluded from webhook sync)

**Key Decisions:**
- **ONE global Helius webhook** ([ADR-001](./database-design/README.md#adr-001)) - Batch sync every 5 min updates webhook with all active addresses
- **Strategy overrides at position level** ([ADR-002](./database-design/README.md#adr-002)) - NOT at wallet level, keeps wallet config simple
- **Address validation**: Solana base58 regex constraint (`^[1-9A-HJ-NP-Za-km-z]{32,44}$`)

**Relations:**
- `N:1` → exit_strategies (default strategy for this wallet)
- `1:N` → signals, positions, orders, performance

#### 4. tokens (Token Metadata Cache)

**📖 Design Guide:** [04-tokens.md](./database-design/04-tokens.md)
**🗄️ Migration SQL:** `004_tokens_table.sql`

**Purpose:** Cache token metadata and safety analysis (TTL 1h, avoid re-analyzing)

**Pattern:** Read-Through Cache - Fetch-on-miss, store results, respect TTL

**Key Field Groups:**
- **Identity**: address (unique), symbol, name
- **Safety Score**: safety_score (0.00-1.00), liquidity_usd, holder_distribution_top_10_percent, age_hours
- **Individual Checks**: liquidity_check_passed, holder_check_passed, contract_check_passed, age_check_passed
- **Cache Metadata**: last_analyzed_at (TTL 1h), analysis_source (rugcheck/dexscreener)
- **DEX Info**: dex_name, pair_address

**Key Decisions:**
- **TTL 1h**: Cache invalidation after 1h → re-analyze on next signal
- **Multi-source fallback**: RugCheck primary, DexScreener fallback
- **Safety booleans**: Individual checks stored for debugging/forensics

**Relations:**
- `1:N` → signals, positions, orders

#### 5. signals (Webhook Events Log)

**📖 Design Guide:** [05-signals.md](./database-design/05-signals.md)
**🗄️ Migration SQL:** `005_signals_table.sql`

**Purpose:** Immutable audit trail of all webhook events from Helius (BUY/SELL signals)

**Pattern:** Event Sourcing - Append-only log, never UPDATE, only INSERT

**Key Field Groups:**
- **Identity**: wallet_id (FK → wallets), token_address, transaction_signature (UNIQUE, idempotency)
- **Signal Type**: signal_type (BUY | SELL)
- **Transaction Details**: token_in, token_out, amount_in, amount_out, price
- **Processing**: filtered (boolean), filter_reason (safety_check_failed/circuit_breaker/duplicate)
- **Position Link**: position_created (boolean), position_id (FK → positions, NULL until created)
- **Webhook Metadata**: webhook_received_at, processed_at, processing_duration_ms
- **Raw Data**: raw_payload (JSONB, full Helius webhook for debugging)

**Key Decisions:**
- **Immutable**: Never UPDATE signals, only INSERT new ones
- **Idempotency**: transaction_signature UNIQUE prevents duplicates
- **Processing queue**: filtered=false AND position_created=false → ready for processing

**Relations:**
- `N:1` → wallets, tokens
- `1:0-1` → positions (signal may be filtered, no position created)

#### 6. orders (Jupiter Swap Orders History)

**📖 Design Guide:** [06-orders.md](./database-design/06-orders.md)
**🗄️ Migration SQL:** `006_orders_table.sql`

**Purpose:** Command log of all Jupiter swap orders (buy/sell transactions) with retry mechanism

**Pattern:** Command Log - Track requests/retries, execution details, slippage

**Key Field Groups:**
- **Identity**: wallet_id, token_id, position_id (FK → positions), signal_id
- **Order Type**: order_type (entry | exit_stop_loss | exit_trailing_stop | exit_scaling | exit_mirror | exit_manual)
- **Mode**: mode (simulation | live)
- **Swap Details**: token_in, token_out, amount_in, amount_out_expected, amount_out (actual)
- **Slippage**: slippage_requested_percent (default 3%), slippage_actual_percent (auto-calculated)
- **Status**: status (pending | submitted | executed | failed | cancelled)
- **Execution** (live only): jupiter_quote_id, tx_signature, block_number, priority_fee_lamports
- **Timing**: requested_at, submitted_at, executed_at, execution_duration_ms (auto-calculated trigger)
- **Retry**: retry_count (default 0), max_retries (default 3), error_code, error_message
- **Scaling Context**: scaling_level (1/2/3), scaling_percent

**Key Decisions:**
- **1 position → N orders**: Position can have multiple orders (entry + multiple exits for scaling)
- **Idempotency**: tx_signature for live orders (on-chain tx)
- **Retry logic**: Partial index `idx_orders_pending_retry` for worker queue
- **Auto-calculated fields**: execution_duration_ms via trigger

**Relations:**
- `N:1` → wallets, tokens, positions, signals

#### 7. positions (Trading Positions)

**📖 Design Guide:** [07-positions.md](./database-design/07-positions.md)
**🗄️ Migration SQL:** `007_positions_table.sql`

**Purpose:** Aggregate root tracking position lifecycle (entry → price updates → partial/full exits → PnL)

**Pattern:** Aggregate Root - Central entity for trading positions with PnL tracking (realized/unrealized separation)

**Key Field Groups:**
- **Identity**: wallet_id, token_id, signal_id, mode (simulation | live)
- **Entry**: entry_price, entry_amount, entry_value_usd, entry_timestamp, entry_tx_signature (live only)
- **Current State**: current_amount (decremented on partial exits), current_price, current_pnl_usd, peak_price (trailing stop)
- **PnL Breakdown**:
  - **unrealized_pnl_usd**: PnL of current_amount (still open)
  - **realized_pnl_usd**: PnL from exits already executed (accumulated from orders)
  - **current_pnl_usd**: Total = realized + unrealized
- **Exit**: exit_price (weighted avg), exit_amount (sum of exits), exit_reason (stop_loss/trailing_stop/scaling/mirror/manual)
- **Exit Strategy**: exit_strategy_id (FK → exit_strategies), exit_strategy_override (JSONB, [ADR-002](./database-design/README.md#adr-002))
- **Status**: status (open | closed | error)

**Key Decisions:**
- **Partial exits supported**: current_amount decremented, realized_pnl accumulated
- **Strategy override at position level** ([ADR-002](./database-design/README.md#adr-002)): `exit_strategy_override` JSONB merges with template
- **Partial index on open positions**: `WHERE status = 'open'` for price monitor worker

**Relations:**
- `N:1` → wallets, tokens, signals, exit_strategies
- `1:N` → orders (entry + multiple exit orders)

#### 8. performance (Aggregated Wallet Metrics)

**📖 Design Guide:** [08-performance.md](./database-design/08-performance.md)
**🗄️ Migration SQL:** `008_performance_table.sql`

**Purpose:** Pre-calculated wallet performance metrics (batch refresh daily at 00:00 UTC)

**Pattern:** Materialized View - Avoid expensive real-time aggregations, dashboard reads pre-calculated values

**Key Field Groups:**
- **Win Rate**: total_positions, winning_positions, losing_positions, win_rate (%)
- **PnL**: total_pnl_usd, total_pnl_percent, average_win_usd, average_loss_usd, profit_ratio (avg_win / avg_loss)
- **Rolling Windows**: signal_count_30d/7d/24h, positions_30d/7d/24h (recalculated daily)
- **Best/Worst**: best_trade_pnl_usd/percent, worst_trade_pnl_usd/percent
- **Streaks**: current_win_streak, current_loss_streak, max_win_streak, max_loss_streak
- **Metadata**: last_calculated_at (batch job timestamp)

**Key Decisions:**
- **Daily batch refresh** ([ADR-003](./database-design/README.md#adr-003)): Performance Aggregator Worker runs at 00:00 UTC
- **1:1 with wallets**: wallet_id UNIQUE constraint
- **Fast dashboard queries**: No JOINs, pre-calculated values

**Relations:**
- `1:1` → wallets (wallet_id UNIQUE)

#### 9. circuit_breaker_events (Circuit Breaker Log)

**📖 Design Guide:** [09-circuit-breaker-events.md](./database-design/09-circuit-breaker-events.md)
**🗄️ Migration SQL:** `009_circuit_breaker_events_table.sql`

**Purpose:** Immutable audit trail of circuit breaker activations/deactivations (compliance & forensics)

**Pattern:** Event Sourcing - Event pairs (activated → deactivated), snapshots of metrics/thresholds at trigger time

**Key Field Groups:**
- **Event**: event_type (activated | deactivated)
- **Trigger**: trigger_reason (max_drawdown | min_win_rate | consecutive_losses | manual)
- **Metrics Snapshot**: current_drawdown_percent, current_win_rate, consecutive_losses (at activation moment)
- **Thresholds Snapshot**: max_drawdown_threshold, min_win_rate_threshold, consecutive_loss_threshold (config at activation)
- **Impact**: new_positions_blocked (counter), open_positions_at_activation (snapshot)
- **Metadata**: created_at, deactivated_at (NULL if still active)

**Key Decisions:**
- **Circuit breaker does NOT close existing positions** ([ADR-004](./database-design/README.md#adr-004)): Blocks NEW positions only, existing continue exit strategies
- **Immutable events**: Never UPDATE, only INSERT pairs (activated → deactivated)
- **Snapshots for forensics**: Thresholds + metrics at trigger time (validate calibration)

### Data Retention Strategy

**Approach:** Keep all data in main tables with optimized indexes

**Design Decision:** No archive tables for MVP
- Simpler schema and maintenance
- Partial indexes on recent data for performance
- Can add partitioning later if needed

**Performance Optimization:**
```sql
-- Index for recent signals (last 90 days) - faster queries
CREATE INDEX idx_signals_recent ON walltrack.signals(created_at DESC)
    WHERE created_at > NOW() - INTERVAL '90 days';

-- Index for recent orders (last 90 days)
CREATE INDEX idx_orders_recent ON walltrack.orders(created_at DESC)
    WHERE created_at > NOW() - INTERVAL '90 days';

-- Index for recently closed positions (last 90 days)
CREATE INDEX idx_positions_recent_closed ON walltrack.positions(closed_at DESC)
    WHERE status = 'closed' AND closed_at > NOW() - INTERVAL '90 days';
```

**Future Migration Path (if performance degrades):**
- Option A: Add table partitioning (PostgreSQL 10+)
- Option B: Implement archive tables with monthly job
- Option C: Use TimescaleDB for time-series data

### Migration Files

**Location:** `src/walltrack/data/supabase/migrations/`

**Execution Order:**
1. `000_helper_functions.sql` - Schema + triggers (update_updated_at)
2. `001_config_table.sql` - System configuration (singleton)
3. `002_exit_strategies_table.sql` - Exit strategies catalog + default data
4. `003_wallets_table.sql` - Watchlist registry
5. `004_tokens_table.sql` - Token metadata cache
6. `005_signals_table.sql` - Webhook events log
7. `006_orders_table.sql` - Jupiter swap orders
8. `007_positions_table.sql` - Trading positions
9. `008_performance_table.sql` - Aggregated metrics
10. `009_circuit_breaker_events_table.sql` - Circuit breaker audit trail

**See also:** [Database Design Guides](./database-design/README.md) for rationale and patterns

### Key Design Decisions (Summary)

**Major Architecture Decision Records (ADRs):**
- **[ADR-001](./database-design/README.md#adr-001)**: Helius Global Webhook - ONE webhook for all wallets (not 1 per wallet)
- **[ADR-002](./database-design/README.md#adr-002)**: Exit Strategy Override at Position Level (not wallet level)
- **[ADR-003](./database-design/README.md#adr-003)**: Performance Materialized View (batch refresh daily at 00:00 UTC)
- **[ADR-004](./database-design/README.md#adr-004)**: Circuit Breaker Non-Closing (blocks NEW positions, existing continue)

**Design Patterns Applied:**
1. **Configuration Singleton** (config) - 1 row max, trigger enforcement
2. **Catalog Pattern** (exit_strategies) - Reusable templates, DRY
3. **Registry Pattern** (wallets) - Watchlist configuration
4. **Read-Through Cache** (tokens) - TTL 1h, fetch-on-miss
5. **Event Sourcing** (signals, circuit_breaker_events) - Immutable append-only logs
6. **Command Log** (orders) - Retry mechanism, execution tracking
7. **Aggregate Root** (positions) - PnL tracking, realized/unrealized separation
8. **Materialized View** (performance) - Pre-calculated metrics, batch refresh

**Technical Decisions:**
- **Separation of concerns**: orders (transactions) vs positions (high-level trades)
- **Partial indexes**: `WHERE status = 'open'` for performance (price monitor queries)
- **Timestamps everywhere**: `created_at`, `updated_at` (auto-updated via triggers)
- **UUIDs as PKs**: Distributed-friendly, no auto-increment conflicts
- **CHECK constraints**: Enforce enums at DB level (mode, status, order_type)
- **Cascade deletes**: Delete wallet → cascade delete signals, positions, performance (referential integrity)

## API Rate Limits & Capacity Planning

### Critical Discovery: External API Constraints

**Investigation Context:** Three API rate limits marked "TBD" in PRD (TR-3: External API Integration) were investigated to determine system capacity constraints and upgrade requirements.

**Research Date:** 2026-01-04
**Sources:**
- [Helius API Plans and Rate Limits](https://www.helius.dev/docs/billing/plans-and-rate-limits)
- [Jupiter API Rate Limiting](https://dev.jup.ag/docs/api-rate-limit)
- [DexScreener API Reference](https://docs.dexscreener.com/api/reference)

### 1. Helius API (Webhooks & RPC)

**Free Tier Limits:**

| Resource | Limit | Notes |
|----------|-------|-------|
| **Credits/Month** | 1,000,000 | Increased from 500K (2026 update) |
| **Requests/Second** | 10 req/sec | RPC calls only |
| **API Keys** | 1 key | Sufficient for MVP |
| **Webhooks** | 1 webhook | **Critical constraint** |
| **Support** | Community | No SLA guarantee |

**Webhook Capabilities (CRITICAL DISCOVERY):**

**Single webhook can monitor up to 100,000 wallet addresses simultaneously** ([source](https://x.com/heliuslabs/status/1851348198700339254))

**Enhanced Transactions webhook features:**
- Parses 100+ transaction types (swaps, transfers, NFT trades, etc.)
- Dynamic address list modification via API
- Both BUY and SELL swap events captured in single webhook
- Real-time delivery (<1s latency typical)

**Credit Consumption:**
- **Webhook event**: 1 credit per event delivered to endpoint ([source](https://www.helius.dev/docs/webhooks))
- **Webhook management** (create/edit/delete): 100 credits per operation
- **RPC calls**: Variable (1-10 credits depending on method)

**Architectural Implication:**

✅ **Free tier FULLY SUFFICIENT for MVP** - The 1 webhook limitation is NOT a blocker:
- Can monitor ALL watchlist wallets (10-20 target) with single Enhanced Transactions webhook
- 1M credits/month supports 1M webhook events
- Expected load: 10 wallets × 20 signals/day = 200 events/day = 6,000/month (0.6% of limit)
- Ample headroom for growth (can scale to 50+ wallets on free tier)

**Capacity Calculation:**

```
Free Tier Capacity:
- 1M credits ÷ 1 credit/event = 1M webhook events/month
- 1M events ÷ 30 days = 33,333 events/day
- Target: 10-20 wallets × 5-20 signals/day = 50-400 signals/day
- Headroom: 33,333 ÷ 400 = 83x capacity margin
```

**Upgrade Trigger:**
- If exceeding 900K credits/month consistently (>30K events/day)
- Developer tier: $50/month, 30M credits, 50 req/sec, 5 webhooks

---

#### 1.1 Helius Webhook Lifecycle Management

**Architecture Pattern:** WallTrack uses **ONE global webhook** that monitors ALL active wallets, not one webhook per wallet.

**Rationale:**
- Helius free tier includes 1 webhook → Must monitor all wallets with single webhook
- Cost efficiency: 1 webhook regardless of wallet count (vs N webhooks)
- Simplified management: Single endpoint, single configuration
- Scalability: Can monitor up to 100,000 addresses with one webhook

**Configuration Storage:**

Global webhook config is stored in `config` table (singleton):
```sql
-- In config table
helius_webhook_id TEXT           -- Webhook ID from Helius
helius_webhook_url TEXT          -- Our endpoint URL
helius_webhook_secret TEXT       -- For signature validation
helius_last_sync_at TIMESTAMPTZ  -- Last successful sync
helius_sync_error TEXT           -- Last error (NULL if OK)
```

Per-wallet sync tracking in `wallets` table:
```sql
-- In wallets table
helius_synced_at TIMESTAMPTZ     -- When this wallet was added to webhook
helius_sync_status TEXT          -- 'pending', 'synced', 'error'
```

**Workflow:**

**1. Initial Setup** (one-time, app initialization)
```python
# Create global webhook via Helius API
webhook = helius_client.create_webhook(
    url="https://walltrack.app/api/webhooks/helius",
    events=["SWAP"],
    addresses=[]  # Empty initially
)

# Store in config table
db.execute("""
    UPDATE config
    SET helius_webhook_id = $1,
        helius_webhook_url = $2,
        helius_webhook_secret = $3
""", webhook.id, webhook.url, webhook.secret)
```

**2. Wallet Synchronization** (batch job, every 5 minutes)
```python
async def sync_wallets_to_helius():
    config = get_config()

    # Get all active wallet addresses
    active_addresses = db.query("""
        SELECT address FROM wallets WHERE is_active = true
    """).scalars().all()

    # Update webhook with complete address list
    try:
        helius_client.update_webhook(
            webhook_id=config.helius_webhook_id,
            addresses=active_addresses  # Full replacement
        )

        # Mark wallets as synced
        db.execute("""
            UPDATE wallets
            SET helius_synced_at = NOW(),
                helius_sync_status = 'synced'
            WHERE is_active = true
        """)

        # Update config
        db.execute("""
            UPDATE config
            SET helius_last_sync_at = NOW(),
                helius_sync_error = NULL
        """)

    except HeliusAPIError as e:
        db.execute("""
            UPDATE wallets
            SET helius_sync_status = 'error'
            WHERE is_active = true AND helius_synced_at IS NULL
        """)

        db.execute("""
            UPDATE config SET helius_sync_error = $1
        """, str(e))
```

**3. Adding New Wallet**
```python
# Wallet created with sync_status = 'pending'
wallet = create_wallet(address="...", helius_sync_status='pending')

# Next batch sync (within 5 min) adds it to webhook automatically
```

**4. Deactivating Wallet**
```python
# Mark inactive
deactivate_wallet(wallet_id)

# Next batch sync removes it from webhook address list
```

**5. Signal Reception**
```python
@app.post("/api/webhooks/helius")
async def receive_helius_webhook(request: Request):
    # Validate signature
    validate_signature(request, config.helius_webhook_secret)

    payload = await request.json()
    wallet_address = payload["account"]

    # Lookup wallet in DB
    wallet = db.query("SELECT * FROM wallets WHERE address = $1", wallet_address).first()

    if not wallet or not wallet.is_active:
        return {"status": "ignored"}

    # Update last_signal_at
    db.execute("UPDATE wallets SET last_signal_at = NOW() WHERE id = $1", wallet.id)

    # Process signal
    await process_signal(wallet, payload)

    return {"status": "ok"}
```

**Monitoring & Health Checks:**

```sql
-- Wallets pending sync (should be 0 after 5 min)
SELECT COUNT(*) FROM wallets
WHERE is_active = true AND helius_sync_status = 'pending';

-- Last sync time (should be < 5 min ago)
SELECT helius_last_sync_at, helius_sync_error FROM config;

-- Wallets without signals (potential webhook issues)
SELECT address, label, last_signal_at
FROM wallets
WHERE is_active = true
  AND helius_sync_status = 'synced'
  AND (last_signal_at IS NULL OR last_signal_at < NOW() - INTERVAL '72 hours');
```

**Error Handling:**

- **Sync fails:** Retry on next batch (5 min), log error in `config.helius_sync_error`
- **Webhook down:** Helius retries with exponential backoff, check endpoint health
- **Address limit exceeded:** Upgrade to paid tier (100K limit should never be hit)

---

### 2. Jupiter API (Swap Execution)

**Free Tier Limits:**

| Resource | Limit | Calculation |
|----------|-------|-------------|
| **Requests** | 60 req/60 sec | 1 req/sec average |
| **Burst** | 60 requests | Can burst if under quota |
| **API Keys** | Unlimited | No per-key limit (account-based) |
| **Cost** | Free | Public API |

**Pro Tier Limits (Paid):**

| Tier | Cost | Limit | Use Case |
|------|------|-------|----------|
| **Pro I** | $50/month | ~600 req/min (100/10sec) | Live trading 5-10 wallets |
| **Pro II** | $250/month | ~3,000 req/min (500/10sec) | 20+ wallets |
| **Pro III** | $1,000/month | ~6,000 req/min (1,000/10sec) | High frequency |

**Rate Limit Buckets (Independent):**
- **Price API** (`/price/v3/`): Separate quota
- **Studio API** (`/studio/`): 10 req/10sec (Pro), 100 req/5min (Free)
- **Default**: All other endpoints (swap, quote)

**Architectural Implication:**

✅ **Free tier SUFFICIENT for MVP with intelligent request queuing:**

**Simulation Mode:**
- No Jupiter API calls (skipped in pipeline)
- Free tier irrelevant for simulation

**Live Mode (Primary Architecture Pattern):**
- Minimum 2 calls per trade: 1 quote + 1 swap = 2 req
- Free tier: 60 req/60sec = 1 req/sec average
- **MVP target: 10 wallets × 10 signals/day = 100 trades/day**

**Capacity Calculation:**

```
Free Tier Live Trading Capacity:

Average Load (signals distributed 24h):
- 100 trades/day ÷ 24h = 4.2 trades/hour
- 4.2 trades/h × 2 req/trade = 8.4 req/hour
- Free tier: 60 req/min = 3,600 req/hour
- Headroom: 3,600 ÷ 8.4 = 428x capacity margin ✅

Burst Scenarios (5 wallets trade simultaneously):
- 5 trades × 2 req = 10 requests in ~10 seconds
- With 2-second spacing queue: 10 req over 20 seconds
- Rate: 30 req/min → well within 60 req/min limit ✅

Critical Design: REQUEST QUEUE WITH SPACING
- Queue enforces 2-second minimum between Jupiter calls
- Prevents burst overload (multiple wallets trading simultaneously)
- Free tier viable for 3-5 wallets in live mode
- Upgrade only needed if consistent 429 errors at scale
```

**Progressive Live Trading Strategy:**

**Phase 1 (Weeks 5-8): Test with 1-2 wallets LIVE**
- Select highest-performing simulation wallets
- Rest of watchlist remains in simulation
- Monitor 429 errors (should be zero with queue)

**Phase 2 (Months 3-4): Scale to 3-5 wallets LIVE**
- Add wallets progressively (1 per week)
- Monitor Jupiter request rate
- Free tier sufficient if no consistent 429 errors

**Phase 3 (Months 5+): Upgrade decision**
- Upgrade to Pro I ($50/month) ONLY if:
  - Profitable in live mode (validated revenue)
  - Want 10+ wallets in live simultaneously
  - Hitting 429 errors regularly with queue
  - Missing profitable trades due to queue delays

**Upgrade Trigger (Revised):**
- **NOT immediately** when launching live trading
- ONLY when free tier becomes bottleneck (consistent 429 errors)
- Validates profitability BEFORE spending $50/month

**CRITICAL NOTE:** lite-api.jup.ag deprecated January 31, 2026 - must use new API endpoints

### 2a. Jupiter Price API V3 (Price Monitoring - PRIMARY)

**Why Jupiter for Price Monitoring:**

✅ **Already in stack** - No new dependency (same API as swap execution)
✅ **All tokens covered** - Includes new/low-cap tokens (shitcoins from Pump.fun, Raydium)
✅ **Multi-DEX aggregation** - More reliable than single DEX (averages Raydium, Orca, Pump.fun, etc.)
✅ **Free tier** - No additional cost
✅ **Architectural coherence** - Same data source for pricing AND execution

**Rate Limits:**

| Resource | Limit | Use Case |
|----------|-------|----------|
| **Price API V3** (`/price/v3`) | Separate quota from swap API | Price monitoring (PRIMARY) |
| **Requests** | ~300 req/min estimated | Real-time price polling for exit triggers |
| **Batch Capability** | Up to 100 token addresses per request | Multi-position monitoring |
| **Authentication** | Optional (API key recommended for higher limits) | Public access available |

**Key Endpoints:**

```
GET https://api.jup.ag/price/v3
Query params:
  - ids: Comma-separated token mint addresses (up to 100)
  - vsToken: Optional (defaults to USDC)

Response:
{
  "data": {
    "<token_mint>": {
      "id": "<token_mint>",
      "price": 0.00123456,  // Price in vsToken (USDC)
      "extraInfo": {
        "lastSwappedPrice": {...},
        "quotedPrice": {...}
      }
    }
  },
  "timeTaken": 0.002
}
```

**Architectural Implication:**

✅ **FREE tier SUFFICIENT for MVP:**

**Capacity Calculation:**

```
Price Monitor Capacity (estimated ~300 req/min):

Scenario 1: Individual polling (inefficient)
- 100 active positions × 1 req/position every 30 sec = 200 req/min
- Within estimated limit ✅

Scenario 2: Batch polling (RECOMMENDED)
- 100 positions ÷ 100 addresses/batch = 1 batch
- 1 batch every 30 sec = 2 req/min
- 300 req/min ÷ 2 = 150x capacity margin ✅

Scenario 3: Adaptive polling (BEST)
- Active positions (near trigger): 20 sec polling
- Stable positions: 60 sec polling
- Mixed: ~10 req/min average with 100 positions
- 300 req/min ÷ 10 = 30x capacity margin ✅
```

**Recommended Implementation:**

**Polling Strategy (FREE tier - conservative):**
1. **Batch requests** (up to 100 tokens per call)
2. **Adaptive intervals**:
   - Urgent (near trigger <5%): **20 sec** (protect capital)
   - Active (trailing stop enabled): **30 sec** (monitor closely)
   - Stable (fixed triggers only): **60 sec** (conserve quota)
   - Circuit breaker active: pause polling
3. **Prioritize positions** by urgency (trailing-stop > stop-loss > scaling-out)

**Rationale:**
- Conservative intervals preserve quota for swap bursts
- 20s urgent provides ~3% better exit protection vs 30s
- Average load: ~1.5 req/min (leaves 58.5 req/min for swaps)

**Price Data Quality:**
- Aggregated across all Jupiter-integrated DEXs
- Based on actual swap prices (not orderbook)
- Covers all tradeable SPL tokens (including new launches)
- Latency: <100ms typical

**Implementation Example:**

```python
from walltrack.services.jupiter import JupiterPriceClient

class PriceMonitor:
    def __init__(self):
        self.jupiter = JupiterPriceClient()

    async def monitor_positions_batch(self, positions: list[Position]):
        """Batch price monitoring for active positions"""
        token_addresses = [p.token_address for p in positions]

        # Single batch request for all positions (up to 100)
        prices = await self.jupiter.get_prices_batch(token_addresses)

        for position in positions:
            current_price = prices[position.token_address]
            await self.check_exit_triggers(position, current_price)

    async def adaptive_polling_loop(self):
        """Adaptive polling based on position proximity to triggers"""
        while True:
            active_positions = await self.get_active_positions()

            # Group by urgency
            urgent = [p for p in active_positions if p.near_trigger()]
            stable = [p for p in active_positions if not p.near_trigger()]

            # Monitor urgent positions every 20s
            await self.monitor_positions_batch(urgent)
            await asyncio.sleep(20)

            # Monitor stable positions every 60s
            if time.time() % 60 < 5:  # Every minute
                await self.monitor_positions_batch(stable)
```

**Fallback Strategy:**

```python
async def get_token_price(self, token_address: str) -> float:
    """Price fetching with DexScreener fallback"""
    try:
        # PRIMARY: Jupiter Price API V3
        price = await self.jupiter.get_price(token_address)
        await self.cache.set(f"price:{token_address}", price, ttl=300)
        return price
    except APIError as e:
        logger.warning("jupiter_price_api_unavailable", error=str(e))

        # FALLBACK: DexScreener
        try:
            price = await self.dexscreener.get_price(token_address)
            return price
        except APIError:
            # Last resort: use cached price if recent
            cached = await self.cache.get(f"price:{token_address}")
            if cached and cache_age < 300:  # 5 min threshold
                logger.warning("using_cached_price", age_seconds=cache_age)
                return cached
            raise PriceUnavailableError(token_address)
```

**Upgrade Trigger:**
- No paid tier for Price API specifically
- If hitting rate limits:
  - Increase polling interval to 45-60 sec
  - Reduce concurrent positions
  - Consider upgrading Jupiter account (may increase all quotas)

### 3. DexScreener API (Fallback Price Source)

**Role:** FALLBACK price source if Jupiter Price API unavailable

**Rate Limits (No Authentication Required):**

| Endpoint Type | Limit | Use Case |
|---------------|-------|----------|
| **Token Pairs / DEX Data** | 300 req/min | Price monitoring (FALLBACK) |
| **Profiles / Boosts** | 60 req/min | Not used in MVP |

**Batch Capabilities:**
- Single request can query up to 30 token addresses
- Less efficient than Jupiter (30 vs 100 tokens/request)

**Architectural Implication:**

✅ **Free tier SUFFICIENT as fallback:**

**Fallback Use Case:**

```
Only used if Jupiter Price API fails or returns errors:

Fallback Capacity (300 req/min):
- 100 positions ÷ 30 addresses/batch = 4 batches
- 4 batches every 30 sec = 8 req/min
- 300 req/min ÷ 8 = 37x capacity margin ✅
- Sufficient for fallback scenarios
```

**Implementation Note:**

DexScreener is implemented as **graceful degradation** only:
- NOT used in normal operation (Jupiter handles all price monitoring)
- Activated automatically if Jupiter Price API unavailable
- Same polling intervals as primary (20-60s adaptive)
- Batch requests (30 tokens max per call)
- Automatically switches back to Jupiter when available

**Limitations as Fallback:**
- Smaller batch size (30 vs 100 tokens)
- Single DEX coverage (may miss some new tokens)
- No paid tier for upgrades

### 4. RugCheck API (Token Safety Analysis)

**Rate Limits:**

| Resource | Limit | Use Case |
|----------|-------|----------|
| **API Requests** | Unlimited (free tier) | Token security analysis (PRIMARY) |
| **Authentication** | API Key required | Free account creation at rugcheck.xyz |
| **Response Time** | <2s typical | Comprehensive security report |

**API Capabilities:**

**Core Security Checks (FR-3 Implementation):**
- ✅ **Contract Analysis**: Honeypot detection, mint/freeze authority checks
- ✅ **Liquidity Analysis**: Pool size, trading volume, LP burn/lock status
- ✅ **Holder Distribution**: Wallet concentration, top holders analysis
- ✅ **Token Metadata**: Creation date (for age threshold check)

**Key Endpoints:**
- `GET /tokens/{mint}/report` - Full security report with risk score
- `GET /tokens/{mint}/report/summary` - Quick summary for filtering
- `GET /wallet/{address}/risk` - Wallet risk assessment

**Architectural Implication:**

✅ **FREE tier FULLY SUFFICIENT for MVP:**

**Capacity Calculation:**

```
Token Safety Analysis Load (unlimited requests):

Expected Usage:
- 10-20 watchlist wallets
- 20 signals/wallet/day average
- 200-400 total signals/day
- 1 RugCheck API call per new token (cached after first check)
- Estimated 50-100 unique tokens/day
- 1,500-3,000 API calls/month

Free Tier: No rate limits documented
Cost: $0/month (completely free)
```

**Recommended Implementation:**

**Safety Score Calculation (FR-3):**
```python
async def analyze_token_safety(token_address: str) -> float:
    # Call RugCheck API for comprehensive report
    report = await rugcheck.get_report_summary(token_address)

    # 4 weighted checks (25% each):
    liquidity_score = 1.0 if report.liquidity_usd >= 50000 else 0.0
    holder_score = 1.0 if report.top_10_holder_percent < 80 else 0.0
    contract_score = report.security_score  # Honeypot/rug detection
    age_score = 1.0 if report.age_hours >= 24 else 0.0

    # Weighted average (configurable threshold: 0.60 default)
    return (liquidity_score + holder_score + contract_score + age_score) / 4
```

**Caching Strategy:**
- Cache token reports for 24h (safety scores don't change rapidly)
- Store in `tokens` table (address, safety_score, last_analyzed_at)
- Re-analyze only if last_analyzed_at > 24h old

**Fallback Strategy:**
- If RugCheck API unavailable:
  - Use cached score if available (warn if stale >48h)
  - Option to skip safety check (manual override in config)
  - Alternative: GoPlus Security API (multi-chain, Solana in Beta)

**API Documentation:**
- Swagger: [api.rugcheck.xyz/swagger](https://api.rugcheck.xyz/swagger/index.html)
- Integration Guide: [github.com/degenfrends/solana-rugchecker](https://github.com/degenfrends/solana-rugchecker)

**Research Date:** 2026-01-04
**Sources:**
- [RugCheck API Documentation](https://api.rugcheck.xyz/swagger/index.html)
- [Solana RugChecker GitHub](https://github.com/degenfrends/solana-rugchecker)
- [RugCheck Integration Guide](https://qodex.ai/blog/how-to-get-a-rugcheck-api-key-and-start-using-the-api)

### Architectural Impact Summary

**System Capacity Matrix:**

| Component | Free Tier Limit | MVP Capacity | Bottleneck? | Upgrade Cost |
|-----------|-----------------|--------------|-------------|--------------|
| **Helius Webhooks** | 1M events/month | 10-20 wallets ✅ | NO | $50/mo (if >30K events/day) |
| **Jupiter Swaps** | 60 req/60sec | Simulation: unlimited ✅<br>Live: ~20 trades/min ⚠️ | LIVE MODE | $50/mo Pro I |
| **Jupiter Price** | ~300 req/min (est.) | 100+ positions ✅ | NO | N/A (included with account) |
| **DexScreener Price** | 300 req/min | Fallback only ✅ | NO | N/A (no paid tier) |
| **RugCheck Safety** | Unlimited (free) | 50-100 tokens/day ✅ | NO | $0 (always free) |
| **Supabase DB** | 500MB storage | MVP sufficient ✅ | NO | $25/mo (if needed) |

**Total Cost Scenarios:**

**Simulation Phase (Weeks 1-4):**
- **Cost: $0/month** (all free tiers sufficient)
- Helius: Free tier
- Jupiter Swaps: Not used (simulation)
- Jupiter Price: Free tier (price monitoring)
- DexScreener: Not used (fallback only)
- Supabase: Free tier

**Initial Live Trading (Weeks 5-12):**
- **Cost: $0/month** (free tier with request queue)
- Helius: Free tier (sufficient)
- **Jupiter Swaps: Free tier** - viable with intelligent queue (1-3 wallets live)
- **Jupiter Price: Free tier** - price monitoring (sufficient)
- DexScreener: Fallback only (not actively used)
- Supabase: Free tier (sufficient)

**Scaling Live Trading (Months 4+):**
- **Cost: $0-75/month** (upgrade only if needed)
- Helius: Free tier (still sufficient)
- **Jupiter Swaps: Free OR Pro I ($50/month)** - upgrade only if consistent 429 errors
- **Jupiter Price: Free tier** - included with account (sufficient)
- DexScreener: Fallback only
- Supabase: $0-25/month (optional if storage >400MB)

**Scale Targets:**

| Metric | Free Tiers | With Pro Jupiter | Max Capacity |
|--------|------------|------------------|--------------|
| **Watchlist Wallets** | 10-20 | 20-30 | 100,000 (Helius) |
| **Active Positions** | 100+ | 200+ | 500+ |
| **Trades/Day** | 50-200 (simulation)<br>20-30 (live) | 500-1000 (live) | 5,000+ |
| **Signals/Day** | 400+ | 600+ | 30,000+ |

### Mitigation Strategies

**Rate Limit Handling Patterns:**

**1. Request Queuing (Jupiter) - PRIMARY PATTERN:**

**CRITICAL**: This is not optional - queue is the core architecture for Jupiter integration.

### Swap Priority System

**Priority Hierarchy** (lower number = higher priority):

```python
from enum import IntEnum

class SwapPriority(IntEnum):
    """Swap execution priority levels"""
    CRITICAL = 1   # Mirror-exit: smart wallet sold (danger signal)
    URGENT = 2     # Exit triggers: stop-loss, take-profit, trailing-stop
    NORMAL = 3     # Entry: new position from signal (if circuit breaker inactive)
    LOW = 4        # Scaling-out: partial exit (already in profit)
```

**Rationale:**

1. **CRITICAL (Mirror-Exit)**: Smart wallet knows something you don't → immediate danger
2. **URGENT (Exit Triggers)**: Protect existing capital → limit losses, secure profits
3. **NORMAL (Entry)**: New opportunities → can wait a few seconds
4. **LOW (Scaling-Out)**: Already in profit → lowest urgency

**Circuit Breaker Interaction:**

- Circuit breaker **BLOCKS** new entries (NORMAL priority)
- Circuit breaker **ALLOWS** all exits (CRITICAL, URGENT, LOW)
- Existing positions continue exit strategies normally

**Burst Scenario Protection:**

```
Burst: 5 buy signals arrive + 1 stop-loss triggered simultaneously

Queue order (priority-based):
[1] URGENT: Stop-loss sell (executed first - protects capital)
[2-6] NORMAL: 5 buy signals (executed after exits)

Result:
- Capital protected in 2 seconds (stop-loss)
- Entries execute with 2-sec spacing after (10 additional seconds)
```

### Jupiter Request Queue Implementation

```python
from asyncio import PriorityQueue
from dataclasses import dataclass, field
from datetime import datetime
import time

@dataclass
class SwapRequest:
    """Swap request with priority"""
    priority: SwapPriority
    position_id: str | None  # None for entries
    token_address: str
    action: str  # "buy" or "sell"
    amount: float
    reason: str  # "signal", "stop_loss", "mirror_exit", etc.
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __lt__(self, other):
        """For PriorityQueue: compare by priority then timestamp"""
        if self.priority == other.priority:
            return self.timestamp < other.timestamp
        return self.priority < other.priority


class JupiterRequestQueue:
    """
    Priority-based request queue for Jupiter API free tier.

    Features:
    - Priority-based execution (exits before entries)
    - Rate limit protection (2-sec spacing)
    - Circuit breaker integration (blocks NORMAL priority)
    - Burst handling (queues excess requests)
    """

    def __init__(self, min_spacing_seconds: float = 2.0):
        self.queue = PriorityQueue()
        self.min_spacing = min_spacing_seconds
        self.last_request_time = 0
        self.running = False

    async def enqueue(self, request: SwapRequest):
        """Add swap to priority queue"""
        await self.queue.put(request)

        logger.info(
            "swap_queued",
            priority=request.priority.name,
            action=request.action,
            reason=request.reason,
            queue_size=self.queue.qsize()
        )

    async def start_processing(self):
        """Start background queue processor"""
        self.running = True
        while self.running:
            # Get highest priority request
            request = await self.queue.get()

            try:
                # Enforce rate limit spacing
                now = time.time()
                elapsed = now - self.last_request_time
                if elapsed < self.min_spacing:
                    wait_time = self.min_spacing - elapsed
                    logger.debug("jupiter_queue_spacing", wait_seconds=wait_time)
                    await asyncio.sleep(wait_time)

                # Execute swap
                await self._execute_swap(request)

                # Track execution
                latency = time.time() - request.timestamp.timestamp()
                logger.info(
                    "swap_executed",
                    priority=request.priority.name,
                    action=request.action,
                    latency_seconds=latency,
                    queue_remaining=self.queue.qsize()
                )

            except Exception as e:
                logger.error(
                    "swap_failed",
                    error=str(e),
                    priority=request.priority.name,
                    reason=request.reason
                )
                # TODO: Retry logic or dead-letter queue

            finally:
                self.last_request_time = time.time()
                self.queue.task_done()

    async def _execute_swap(self, request: SwapRequest):
        """Execute Jupiter swap (quote + swap)"""
        # Determine input/output tokens
        if request.action == "buy":
            input_mint = "USDC"  # Or SOL
            output_mint = request.token_address
        else:  # sell
            input_mint = request.token_address
            output_mint = "USDC"

        # Get quote
        quote = await jupiter_client.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=request.amount
        )

        # Execute swap
        result = await jupiter_client.execute_swap(quote)

        # Update position in DB
        if request.position_id:
            await self._update_position(request.position_id, result)
        else:
            await self._create_position(result, request.reason)

        return result

    async def stop_processing(self):
        """Stop queue processor gracefully"""
        self.running = False
        await self.queue.join()  # Wait for pending requests
```

**Usage in Exit Strategy Executor:**

```python
class ExitStrategyExecutor:
    def __init__(self, swap_queue: JupiterRequestQueue):
        self.swap_queue = swap_queue

    async def execute_exit(self, position: Position, trigger: str):
        """Execute exit with appropriate priority"""

        # Determine priority based on trigger
        if trigger == "mirror_exit":
            priority = SwapPriority.CRITICAL
        elif trigger in ["stop_loss", "take_profit", "trailing_stop"]:
            priority = SwapPriority.URGENT
        elif trigger == "scaling_out":
            priority = SwapPriority.LOW
        else:
            priority = SwapPriority.URGENT  # Safe default

        # Create swap request
        request = SwapRequest(
            priority=priority,
            position_id=position.id,
            token_address=position.token_address,
            action="sell",
            amount=position.amount,
            reason=trigger
        )

        # Enqueue (exits ALWAYS allowed, even if circuit breaker active)
        await self.swap_queue.enqueue(request)
```

**Usage in Signal Processor:**

```python
class SignalProcessor:
    def __init__(
        self,
        swap_queue: JupiterRequestQueue,
        circuit_breaker: CircuitBreaker
    ):
        self.swap_queue = swap_queue
        self.circuit_breaker = circuit_breaker

    async def process_signal(self, signal: Signal):
        """Process buy signal - check circuit breaker first"""

        # 1. Circuit breaker check (BLOCKS entries)
        if await self.circuit_breaker.is_active():
            logger.warning(
                "signal_blocked_circuit_breaker",
                signal_id=signal.id,
                reason=await self.circuit_breaker.get_reason()
            )
            return  # ❌ Entry blocked

        # 2. Safety check
        if not await self.safety_analyzer.is_safe(signal.token_address):
            logger.info("signal_rejected_safety", signal_id=signal.id)
            return

        # 3. Enqueue entry (NORMAL priority)
        request = SwapRequest(
            priority=SwapPriority.NORMAL,
            position_id=None,  # Will be created after swap
            token_address=signal.token_address,
            action="buy",
            amount=calculate_position_size(signal.wallet),
            reason="signal"
        )

        await self.swap_queue.enqueue(request)
```

**Configuration:**

```python
# Free tier: 2-second spacing (30 trades/min max)
jupiter_queue = JupiterRequestQueue(min_spacing_seconds=2.0)

# Pro I tier: 0.5-second spacing (120 trades/min)
# jupiter_queue = JupiterRequestQueue(min_spacing_seconds=0.5)
```

**2. Adaptive Polling (Jupiter Price API):**
```python
class AdaptivePriceMonitor:
    async def get_polling_interval(self, position: Position) -> int:
        """Return polling interval based on position urgency"""
        if position.near_stop_loss(threshold=0.05):  # Within 5% of stop
            return 20  # Fast polling
        elif position.has_trailing_stop and position.price_moving:
            return 30  # Moderate polling
        else:
            return 60  # Standard polling
```

**3. Batch Optimization (Jupiter Price API):**
```python
async def fetch_prices_batch(token_addresses: list[str]) -> dict[str, float]:
    """Fetch up to 100 token prices in single API call"""
    batches = [token_addresses[i:i+100] for i in range(0, len(token_addresses), 100)]
    results = {}
    for batch in batches:
        response = await jupiter_price.get_prices(batch)
        results.update(response.data)  # {mint: {"price": float}}
    return results
```

**4. Circuit Breaker (All APIs):**
```python
class APICircuitBreaker:
    """Halt API calls if failure rate exceeds threshold"""
    def __init__(self, failure_threshold: float = 0.5, window: int = 10):
        self.failure_rate_threshold = failure_threshold
        self.recent_calls: deque = deque(maxlen=window)

    def record_call(self, success: bool):
        self.recent_calls.append(1 if success else 0)

    def is_open(self) -> bool:
        if len(self.recent_calls) < self.window:
            return False
        failure_rate = 1 - (sum(self.recent_calls) / len(self.recent_calls))
        return failure_rate > self.failure_rate_threshold
```

**5. Fallback Strategy (Price Data):**
```python
class PriceDataService:
    """Jupiter primary, DexScreener fallback, cache as last resort"""
    async def get_current_price(self, token: str) -> float:
        try:
            # PRIMARY: Jupiter Price API
            price = await jupiter_price.fetch_price(token)
            await cache.set(f"price:{token}", price, ttl=300)
            return price
        except APIError as e:
            logger.warning("jupiter_price_unavailable", token=token, error=str(e))

            # FALLBACK: DexScreener
            try:
                price = await dexscreener.fetch_price(token)
                await cache.set(f"price:{token}", price, ttl=300)
                return price
            except APIError:
                logger.warning("dexscreener_unavailable", token=token)

                # LAST RESORT: Cached price
                cached_price = await cache.get(f"price:{token}")
                if cached_price and cache_age < 300:  # 5 min threshold
                    logger.warning("using_cached_price", age_seconds=cache_age)
                    return cached_price
                raise PriceDataUnavailableError("No fresh or cached price available")
```

### Upgrade Decision Framework

**When to Upgrade Each Service:**

**Helius (Free → Developer $50/month):**
- ❌ NOT NEEDED for MVP (free tier sufficient for 50+ wallets)
- Consider if:
  - Webhook events >900K/month consistently
  - Need faster RPC calls (10 → 100 req/sec)
  - Require dedicated support for production issues

**Jupiter (Free → Pro I $50/month):**
- ✅ **START with FREE TIER using request queue**
- Free tier viable for:
  - Simulation mode (Jupiter not called)
  - Live mode with 1-5 wallets (request queue enforces spacing)
  - Progressive validation before paying
- Upgrade triggers:
  - Consistent 429 errors despite queue spacing
  - Want 10+ wallets in live simultaneously
  - Profitability validated and want faster execution
  - Queue delays causing missed profitable trades

**Supabase (Free → Pro $25/month):**
- ❌ NOT NEEDED initially
- Upgrade triggers:
  - Database size >400MB (approaching 500MB limit)
  - Bandwidth >1.5GB/month (approaching 2GB limit)
  - Need dedicated support or point-in-time recovery >7 days

**Expected Timeline:**

```
Month 1-2 (Simulation): $0/month
├─ Helius Free: Sufficient
├─ Jupiter Swaps Free: Not used (simulation)
├─ Jupiter Price Free: Sufficient (price monitoring)
└─ Supabase Free: Sufficient

Month 3-6 (Initial Live with Queue): $0/month
├─ Helius Free: Still sufficient ✅
├─ Jupiter Swaps Free: 1-3 wallets live with request queue ✅
├─ Jupiter Price Free: Still sufficient ✅
└─ Supabase Free: Still sufficient ✅

Month 7+ (Optional Scaling): $0-75/month
├─ Helius Free: Still sufficient (100K addresses/webhook)
├─ Jupiter: Free OR Pro I $50 (upgrade only if consistent 429s on swaps)
└─ Supabase: Free or Pro $25 (if DB grows)

Year 2 (High Frequency - if profitable): $300+/month
├─ Helius Developer: $50 (if >50 wallets)
├─ Jupiter Pro II: $250 (if high frequency validated profitable)
└─ Supabase Pro: $25
```

### Critical Constraints Summary

**Hard Limits (Cannot Exceed Without Upgrade):**

1. **Jupiter Free Tier: 1 req/sec**
   - Blocks: High-frequency live trading (>30 trades/minute)
   - **Solution: Request queue with 2-sec spacing (PRIMARY)**
   - Enables: 1-5 wallets in live mode without upgrade
   - Upgrade: Only if consistent 429 errors at scale ($50/month Pro I)

2. **Helius Free Tier: 1 webhook**
   - Blocks: Nothing! (can monitor 100K addresses with 1 webhook)
   - Solution: No upgrade needed for MVP
   - Cost Impact: $0

3. **Jupiter Price API: ~300 req/min (estimated)**
   - Blocks: Polling >600 positions without batching
   - Solution: Batch API calls (100 addresses per request)
   - Cost Impact: $0 (included with Jupiter account)

**Soft Limits (Degraded Performance, Workarounds Available):**

1. **Helius 10 req/sec RPC**: Can use public Solana RPC as fallback
2. **Supabase 500MB**: Archive old data, 90-day retention policy
3. **Jupiter Price staleness**: DexScreener fallback + last-known price with 5-minute threshold

**Risk Mitigation:**

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Jupiter swap 429 errors in live mode | HIGH | CRITICAL | Upgrade to Pro I before live launch |
| Jupiter price 429 errors | LOW | MEDIUM | DexScreener fallback, adaptive polling |
| Helius webhook downtime | LOW | HIGH | Monitor webhook status, alert if >30min down |
| Supabase storage limit | LOW | LOW | 90-day data retention, archive old signals |

**Monitoring Requirements:**

**Track these metrics to detect approaching limits:**
- Helius: Webhook events/day (alert if >25K, approaching 30K/day limit)
- Jupiter Swaps: Request count/minute (alert if >50 req/min on free tier)
- Jupiter Price: Request count/minute (alert if >250 req/min, approaching estimated 300)
- Supabase: Database size MB (alert if >400MB, approaching 500MB)

**Implementation in Config:**
```python
class RateLimitMonitor:
    """Track API usage and alert on threshold approach"""
    thresholds = {
        "helius_events_daily": 25000,  # 83% of theoretical max
        "jupiter_swap_requests_per_minute": 50,  # 83% of free tier
        "jupiter_price_requests_per_minute": 250,  # 83% of estimated limit
        "supabase_storage_mb": 400,  # 80% of 500MB limit
    }

    async def check_limits(self):
        for metric, threshold in self.thresholds.items():
            current_value = await self.get_metric(metric)
            if current_value > threshold:
                logger.warning(
                    "rate_limit_threshold_approached",
                    metric=metric,
                    current=current_value,
                    threshold=threshold
                )
```
## Component Architecture

### System Components Overview

WallTrack is composed of 8 main components orchestrated through async workers and FastAPI endpoints:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Gradio UI (Dashboard)                   │
│  - Watchlist management - Config - Positions - Performance      │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼────────────────────────────────────────────┐
│                      FastAPI Application                        │
│  - REST API endpoints - Webhook receiver - Health checks        │
└─────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
      │          │          │          │          │
      ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ ┌──────────────┐
│ Signal   │ │ Token   │ │Position │ │ Price  │ │ Performance  │
│Processor │ │Analyzer │ │ Manager │ │Monitor │ │  Aggregator  │
│ Worker   │ │ Worker  │ │ Worker  │ │ Worker │ │   Worker     │
└────┬─────┘ └────┬────┘ └────┬────┘ └───┬────┘ └──────┬───────┘
     │            │           │          │             │
     └────────────┴───────────┴──────────┴─────────────┘
                          │
                 ┌────────▼─────────┐
                 │  Data Layer      │
                 │ (Supabase PG)    │
                 └──────────────────┘

External APIs:
- Helius (Webhooks + RPC)
- Jupiter (Price + Swap)
- DexScreener (Fallback Price)
- RugCheck (Token Safety)
```

### 1. FastAPI Application (Core Server)

**Responsibilities:**
- REST API endpoints (CRUD wallets, positions, config)
- Helius webhook receiver (`POST /webhooks/helius`)
- Health checks and status endpoints
- Worker lifecycle management

**Key Endpoints:**
```python
# Watchlist Management
POST   /api/v1/wallets              # Add wallet to watchlist
GET    /api/v1/wallets              # List wallets
PUT    /api/v1/wallets/{id}         # Update wallet config
DELETE /api/v1/wallets/{id}         # Remove wallet

# Positions & Orders
GET    /api/v1/positions            # List positions (open/closed)
GET    /api/v1/positions/{id}       # Position details
POST   /api/v1/positions/{id}/exit  # Manual exit

# Config & Status
GET    /api/v1/config               # System config
PUT    /api/v1/config               # Update config
GET    /api/v1/health               # Health check
GET    /api/v1/status               # Workers status

# Webhooks
POST   /webhooks/helius             # Helius webhook receiver
```

**Startup Sequence:**
```python
# src/walltrack/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("starting_walltrack_application")

    # 1. Initialize database connections
    await db.connect()

    # 2. Load config from database
    config = await config_service.load()

    # 3. Start background workers
    await workers.start_all([
        signal_processor,
        token_analyzer,
        position_manager,
        price_monitor,
        performance_aggregator
    ])

    # 4. Sync Helius webhook
    await helius_service.sync_webhook_addresses()

    logger.info("walltrack_ready")

    yield

    # Shutdown
    logger.info("shutting_down_walltrack")
    await workers.stop_all()
    await db.disconnect()

app = FastAPI(lifespan=lifespan)
```

### 2. Signal Processor Worker

**Trigger:** New signal inserted in database (via Helius webhook)
**Frequency:** Event-driven (processes unprocessed signals)
**Responsibility:** Transform raw Helius webhook events into actionable signals

**Processing Pipeline:**
```python
class SignalProcessorWorker:
    """Process incoming signals from Helius webhooks"""

    async def run(self):
        while True:
            # Fetch unprocessed signals
            signals = await db.query(
                "SELECT * FROM walltrack.signals WHERE processed = false ORDER BY created_at LIMIT 10"
            )

            for signal in signals:
                try:
                    # 1. Validate signal (is wallet still active?)
                    wallet = await wallet_repo.get_by_address(signal.source_wallet)
                    if not wallet.is_active:
                        await signal_repo.mark_processed(signal.id, status="ignored_inactive_wallet")
                        continue

                    # 2. Enqueue token safety analysis
                    await token_analyzer.enqueue(
                        token_address=signal.token_out,
                        priority="high" if signal.amount_usd > 1000 else "normal"
                    )

                    # 3. Mark signal as processed
                    await signal_repo.mark_processed(signal.id, status="analyzed")

                    logger.info(
                        "signal_processed",
                        signal_id=signal.id,
                        wallet=wallet.label,
                        token=signal.token_out[:8]
                    )

                except Exception as e:
                    logger.error("signal_processing_failed", signal_id=signal.id, error=str(e))
                    await signal_repo.mark_processed(signal.id, status="error")

            await asyncio.sleep(5)  # Poll every 5 seconds
```

### 3. Token Analyzer Worker

**Trigger:** Token enqueued for analysis (from signal processor)
**Frequency:** Event-driven (processes queue)
**Responsibility:** Fetch token metadata and run safety checks

**Analysis Pipeline:**
```python
class TokenAnalyzerWorker:
    """Analyze tokens for safety (RugCheck + DexScreener)"""

    def __init__(self):
        self.queue = asyncio.Queue()

    async def enqueue(self, token_address: str, priority: str = "normal"):
        await self.queue.put((priority, token_address))

    async def run(self):
        while True:
            priority, token_address = await self.queue.get()

            try:
                # Check if token already cached (TTL 1h)
                token = await token_repo.get_by_address(token_address)
                if token and (datetime.now() - token.last_analyzed_at) < timedelta(hours=1):
                    logger.debug("token_cache_hit", token=token_address[:8])
                    continue

                # 1. RugCheck analysis
                rug_data = await rugcheck_client.analyze(token_address)

                # 2. DexScreener metadata
                dex_data = await dexscreener_client.get_token(token_address)

                # 3. Calculate safety score
                score = self._calculate_safety_score(rug_data, dex_data)

                # 4. Update token cache
                await token_repo.upsert({
                    "address": token_address,
                    "symbol": dex_data.get("symbol"),
                    "name": dex_data.get("name"),
                    "liquidity_usd": dex_data.get("liquidity", {}).get("usd"),
                    "safety_score": score,
                    "is_honeypot": rug_data.get("isHoneypot", False),
                    "has_mint_authority": rug_data.get("hasMintAuthority", False),
                    "holder_count": rug_data.get("holderCount"),
                    "age_hours": self._calculate_age_hours(dex_data),
                    "last_analyzed_at": datetime.now()
                })

                logger.info(
                    "token_analyzed",
                    token=token_address[:8],
                    score=score,
                    safe=score >= 0.60
                )

            except Exception as e:
                logger.error("token_analysis_failed", token=token_address[:8], error=str(e))

            finally:
                self.queue.task_done()
```

### 4. Position Manager Worker

**Trigger:** New signal with safe token + wallet in live mode
**Frequency:** Event-driven
**Responsibility:** Create positions and manage lifecycle (entry → exit)

**Position Lifecycle:**
```python
class PositionManagerWorker:
    """Manage position lifecycle (creation + exit detection)"""

    async def run(self):
        while True:
            # 1. Check for signals ready to create positions
            await self._create_positions_from_signals()

            # 2. Monitor open positions for exit triggers
            await self._check_exit_triggers()

            await asyncio.sleep(10)

    async def _create_positions_from_signals(self):
        """Create positions from processed signals with safe tokens"""
        signals = await db.query("""
            SELECT s.*, t.safety_score, w.mode, w.capital_allocation_percent
            FROM walltrack.signals s
            JOIN walltrack.tokens t ON s.token_out = t.address
            JOIN walltrack.wallets w ON s.source_wallet = w.address
            WHERE s.processed = true
              AND s.position_created = false
              AND t.safety_score >= (SELECT token_safety_threshold FROM walltrack.config)
              AND w.is_active = true
        """)

        for signal in signals:
            try:
                # Calculate position size
                config = await config_service.get()
                position_size_usd = (
                    config.total_capital_usd *
                    signal.wallet.capital_allocation_percent / 100
                )

                # Create position
                position = await position_repo.create({
                    "wallet_id": signal.wallet_id,
                    "token_id": signal.token_id,
                    "signal_id": signal.id,
                    "mode": signal.wallet.mode,  # simulation or live
                    "entry_price": signal.token_out_price,
                    "entry_amount": position_size_usd / signal.token_out_price,
                    "entry_value_usd": position_size_usd,
                    "exit_strategy_id": signal.wallet.default_exit_strategy_id,
                    "status": "open"
                })

                # Execute entry order (if live mode)
                if signal.wallet.mode == "live":
                    await jupiter_client.execute_buy(
                        token_address=signal.token_out,
                        amount_usd=position_size_usd
                    )

                # Mark signal as processed
                await signal_repo.update(signal.id, {"position_created": true})

                logger.info(
                    "position_created",
                    position_id=position.id,
                    mode=signal.wallet.mode,
                    size_usd=position_size_usd
                )

            except Exception as e:
                logger.error("position_creation_failed", signal_id=signal.id, error=str(e))

    async def _check_exit_triggers(self):
        """Check if open positions should exit (strategy triggers)"""
        positions = await position_repo.get_all_open()

        for position in positions:
            try:
                strategy = await exit_strategy_repo.get(position.exit_strategy_id)

                # Merge strategy with position override
                config = {**strategy.dict(), **(position.exit_strategy_override or {})}

                # Check exit conditions
                should_exit, reason = self._evaluate_exit_strategy(position, config)

                if should_exit:
                    await self._execute_exit(position, reason)

            except Exception as e:
                logger.error("exit_check_failed", position_id=position.id, error=str(e))

    def _evaluate_exit_strategy(self, position, config):
        """Evaluate if position should exit based on strategy"""
        # Stop-loss
        if config.get("stop_loss_percent"):
            if position.current_pnl_percent <= -config["stop_loss_percent"]:
                return True, "stop_loss"

        # Trailing stop
        if config.get("trailing_stop_percent"):
            if position.peak_price:
                drawdown_from_peak = (
                    (position.current_price - position.peak_price) / position.peak_price * 100
                )
                if drawdown_from_peak <= -config["trailing_stop_percent"]:
                    return True, "trailing_stop"

        # Scaling out (partial exits at profit levels)
        if config.get("scaling_levels"):
            for level in config["scaling_levels"]:
                if position.current_pnl_percent >= level["profit_percent"]:
                    # Check if this level already executed
                    if not self._is_level_executed(position, level):
                        return True, f"scaling_out_{level['profit_percent']}%"

        return False, None
```

### 5. Price Monitor Worker

**Trigger:** Scheduled (every 30-60s)
**Frequency:** Polling
**Responsibility:** Update current prices for all open positions

**Price Update Pipeline:**
```python
class PriceMonitorWorker:
    """Poll Jupiter Price API to update position prices"""

    async def run(self):
        while True:
            try:
                # Fetch all open positions
                positions = await position_repo.get_all_open()

                if not positions:
                    await asyncio.sleep(60)
                    continue

                # Batch price requests (100 tokens per request)
                token_addresses = list(set(p.token.address for p in positions))

                for batch in self._batch(token_addresses, size=100):
                    try:
                        # Jupiter Price API V3 (batch request)
                        prices = await jupiter_price_client.get_prices(batch)

                        # Update positions
                        for position in positions:
                            if position.token.address in prices:
                                new_price = prices[position.token.address]

                                await position_repo.update_price(
                                    position_id=position.id,
                                    current_price=new_price,
                                    peak_price=max(position.peak_price or 0, new_price)
                                )

                        logger.debug(
                            "prices_updated",
                            count=len(batch),
                            positions_affected=len(positions)
                        )

                    except Exception as e:
                        logger.error("price_batch_update_failed", error=str(e))
                        # Fallback to DexScreener for critical positions
                        await self._fallback_price_update(positions)

                # Wait before next poll
                await asyncio.sleep(30)  # 30s polling interval

            except Exception as e:
                logger.error("price_monitor_worker_failed", error=str(e))
                await asyncio.sleep(60)
```

### 6. Performance Aggregator Worker

**Trigger:** Scheduled (daily at 00:00 UTC)
**Frequency:** Batch (daily)
**Responsibility:** Calculate wallet performance metrics (win rate, PnL, streaks)

**Aggregation Logic:**
```python
class PerformanceAggregatorWorker:
    """Daily batch job to recalculate wallet performance metrics"""

    async def run(self):
        while True:
            # Wait until 00:00 UTC
            await self._wait_until_midnight_utc()

            try:
                wallets = await wallet_repo.get_all_active()

                for wallet in wallets:
                    # Calculate metrics
                    metrics = await self._calculate_wallet_metrics(wallet.id)

                    # Upsert performance record
                    await performance_repo.upsert({
                        "wallet_id": wallet.id,
                        "total_positions": metrics["total_positions"],
                        "winning_positions": metrics["winning_positions"],
                        "losing_positions": metrics["losing_positions"],
                        "win_rate": metrics["win_rate"],
                        "total_pnl_usd": metrics["total_pnl_usd"],
                        "signal_count_30d": metrics["signal_count_30d"],
                        "positions_30d": metrics["positions_30d"],
                        "current_win_streak": metrics["current_win_streak"],
                        "last_calculated_at": datetime.now()
                    })

                    logger.info(
                        "wallet_performance_updated",
                        wallet=wallet.label,
                        win_rate=metrics["win_rate"],
                        total_pnl=metrics["total_pnl_usd"]
                    )

            except Exception as e:
                logger.error("performance_aggregation_failed", error=str(e))
```

---

## Testing Strategy

### Testing Pyramid

```
        ┌─────────────┐
        │     E2E     │  ~10% (Playwright - UI workflows)
        │   (Gradio)  │
        └─────────────┘
      ┌─────────────────┐
      │  Integration    │  ~30% (Real DB + mocked APIs)
      │   (Workers)     │
      └─────────────────┘
    ┌───────────────────────┐
    │    Unit Tests         │  ~60% (Isolated logic + mocks)
    │  (Services/Repos)     │
    └───────────────────────┘
```

### 1. Unit Tests (60% coverage target)

**Scope:** Isolated functions, services, repositories with mocked dependencies

**Location:** `tests/unit/`

**Examples:**
```python
# tests/unit/services/test_token_analyzer.py
@pytest.mark.asyncio
async def test_calculate_safety_score_safe_token():
    analyzer = TokenAnalyzer()

    rug_data = {
        "isHoneypot": False,
        "hasMintAuthority": False,
        "holderCount": 500
    }
    dex_data = {
        "liquidity": {"usd": 75000},
        "createdAt": (datetime.now() - timedelta(days=2)).isoformat()
    }

    score = analyzer._calculate_safety_score(rug_data, dex_data)

    assert score >= 0.75  # Safe token
```

**Key Test Patterns:**
- Mock external APIs (Helius, Jupiter, RugCheck)
- Test business logic in isolation
- Fast execution (<1s per test)

### 2. Integration Tests (30% coverage target)

**Scope:** Workers + Database + Mocked External APIs

**Location:** `tests/integration/`

**Examples:**
```python
# tests/integration/workers/test_signal_processor.py
@pytest.mark.asyncio
async def test_signal_processor_creates_position_for_safe_token(db_session):
    # Setup: Insert wallet + signal + safe token
    wallet = await wallet_repo.create({
        "address": "test_wallet_123",
        "mode": "simulation",
        "is_active": True
    })

    token = await token_repo.create({
        "address": "test_token_456",
        "safety_score": 0.85,  # Safe
        "last_analyzed_at": datetime.now()
    })

    signal = await signal_repo.create({
        "source_wallet": wallet.address,
        "token_out": token.address,
        "processed": False
    })

    # Execute: Run signal processor worker (1 iteration)
    worker = SignalProcessorWorker()
    await worker._process_batch()

    # Assert: Signal processed + position created
    signal_updated = await signal_repo.get(signal.id)
    assert signal_updated.processed == True

    positions = await position_repo.get_by_wallet(wallet.id)
    assert len(positions) == 1
    assert positions[0].mode == "simulation"
```

**Key Test Patterns:**
- Real database (Supabase test instance or local PG)
- Mock external APIs (httpx_mock)
- Test worker orchestration end-to-end

### 3. E2E Tests (10% coverage target)

**Scope:** Complete user workflows through Gradio UI

**Location:** `tests/e2e/`

**Tool:** Playwright

**CRITICAL:** Run E2E tests separately (not with unit/integration)
```bash
# Run unit + integration
uv run pytest tests/unit tests/integration -v

# Run E2E separately
uv run pytest tests/e2e -v
```

**Examples:**
```python
# tests/e2e/test_watchlist_management.py
def test_add_wallet_to_watchlist(page: Page):
    # Navigate to dashboard
    page.goto("http://localhost:7860")

    # Fill wallet form
    page.fill("#wallet_address", "DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK")
    page.fill("#wallet_label", "Test Wallet")
    page.select_option("#wallet_mode", "simulation")

    # Submit
    page.click("button:has-text('Add Wallet')")

    # Verify success
    expect(page.locator(".success-message")).to_contain_text("Wallet added")

    # Verify wallet appears in list
    expect(page.locator("#wallets_table")).to_contain_text("Test Wallet")
```

### Test Data Management

**Strategy:** Factory pattern + database fixtures

```python
# tests/factories.py
class WalletFactory:
    @staticmethod
    async def create(**overrides):
        defaults = {
            "address": f"wallet_{uuid4().hex[:8]}",
            "label": "Test Wallet",
            "mode": "simulation",
            "is_active": True,
            "capital_allocation_percent": 10
        }
        return await wallet_repo.create({**defaults, **overrides})

# tests/conftest.py
@pytest.fixture
async def db_session():
    """Provide clean database for each test"""
    # Setup: Create tables
    await db.execute_migration("000_helper_functions.sql")
    await db.execute_migration("001_config_table.sql")
    # ... all migrations

    yield db

    # Teardown: Drop tables
    await db.execute("DROP SCHEMA walltrack CASCADE")
```

---

## Observability & Monitoring

### Logging Strategy

**Format:** Structured JSON logs (compatible with CloudWatch, Datadog, etc.)

**Pattern:** Consistent key-value pairs

```python
# src/walltrack/core/logging.py
import structlog

logger = structlog.get_logger()

# Good examples (from Implementation Patterns):
logger.info(
    "signal_received",
    wallet=wallet.label,
    token=token_address[:8],
    amount_usd=signal.amount_usd
)

logger.error(
    "swap_failed",
    error=str(e),
    token=token_address[:8],
    priority=request.priority.name
)

logger.warning(
    "rate_limit_threshold_approached",
    metric="helius_events_daily",
    current=25000,
    threshold=30000
)
```

**Log Levels:**
- **DEBUG**: Development only (price updates, cache hits)
- **INFO**: Normal operations (signals processed, positions created)
- **WARNING**: Degraded state (API fallback, approaching rate limits)
- **ERROR**: Failures requiring attention (swap failed, webhook down)

### Metrics to Track

**System Health:**
- Webhook uptime (alerts if >30min down)
- Worker heartbeats (each worker reports alive every 60s)
- Database connection pool (active/idle connections)

**Business Metrics:**
- Signals/day per wallet
- Positions created/day (simulation vs live)
- Win rate (overall + per wallet)
- Total PnL USD

**Performance Metrics:**
- Webhook latency (Helius event → signal processed)
- Position creation latency (signal → position open)
- Price update latency (Jupiter API response time)

**Rate Limit Metrics:**
- Helius events/day (alert at 25K, hard limit 30K)
- Jupiter swap requests/minute (alert at 50, limit 60)
- Jupiter price requests/minute (alert at 250, estimated limit 300)
- Supabase storage MB (alert at 400MB, limit 500MB)

### Dashboard Requirements

**Gradio UI Tabs:**
1. **Overview**: Current positions, total PnL, open orders
2. **Watchlist**: Wallet management + per-wallet performance
3. **Signals**: Recent signals (all/30d/7d/24h) with processing status
4. **Config**: System configuration + API status
5. **Health**: Worker status, API health checks, rate limit usage

**Real-Time Updates:**
- WebSocket for live price updates (every 30s)
- Auto-refresh position table
- Alert banner for circuit breaker activation

---

## Deployment & Operations

### Local Development Setup

```bash
# 1. Clone repo
git clone <repo_url>
cd walltrack

# 2. Install dependencies (uv)
uv sync

# 3. Set environment variables
cp .env.example .env
# Edit .env with API keys

# 4. Run migrations
uv run python scripts/run_migrations.py

# 5. Start application
uv run uvicorn walltrack.main:app --reload --port 8000

# 6. Start Gradio dashboard (separate terminal)
uv run python walltrack/ui/app.py
```

### Environment Variables

```bash
# .env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# External APIs
HELIUS_API_KEY=your-helius-key
JUPITER_API_KEY=your-jupiter-key  # Optional (for Pro tier)
RUGCHECK_API_KEY=your-rugcheck-key  # Optional

# System
LOG_LEVEL=INFO
ENVIRONMENT=development  # or production

# Solana
WALLET_PRIVATE_KEY=<encrypted_or_env_var>  # NEVER commit to git
```

### Production Deployment (Future)

**Hosting Options:**
- **Phase 1 (MVP)**: Local machine (Windows, always-on)
- **Phase 2**: VPS (DigitalOcean $12/month, Ubuntu 22.04)
- **Phase 3**: Docker container on VPS

**Process Management:**
- **Local**: Manual start (`uv run uvicorn ...`)
- **VPS**: systemd service or PM2

**Database Backup:**
- Supabase automatic backups (Pro tier: daily)
- Manual export: `pg_dump walltrack > backup_$(date +%Y%m%d).sql`

### Monitoring & Alerts (Future)

**Uptime Monitoring:**
- Health check endpoint: `GET /api/v1/health`
- External ping: UptimeRobot (free tier, 5min intervals)

**Alert Channels:**
- Email (critical errors only)
- Gradio UI banner (warnings + errors)

**Alert Triggers:**
- Circuit breaker activated (immediate)
- Helius webhook down >30min (immediate)
- Jupiter API 429 errors >10/min (immediate)
- Supabase storage >400MB (daily check)

---

## Security Implementation

### Private Key Management

**CRITICAL:** Wallet private keys must NEVER appear in:
- Logs
- UI (Gradio dashboard)
- Git repository
- Database (store encrypted)

**Implementation:**
```python
# src/walltrack/core/security.py
from cryptography.fernet import Fernet
import os

class WalletKeyManager:
    """Encrypt/decrypt wallet private keys"""

    def __init__(self):
        # Encryption key from environment (NOT in code)
        self.cipher = Fernet(os.environ["WALLET_ENCRYPTION_KEY"].encode())

    def encrypt_private_key(self, private_key: str) -> str:
        """Encrypt private key before storing in database"""
        return self.cipher.encrypt(private_key.encode()).decode()

    def decrypt_private_key(self, encrypted_key: str) -> str:
        """Decrypt private key for swap execution"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()

# Usage:
key_manager = WalletKeyManager()
encrypted = key_manager.encrypt_private_key(user_input_private_key)
await db.execute("INSERT INTO config (wallet_private_key_encrypted) VALUES (?)", [encrypted])
```

**Key Storage:**
- Environment variable: `WALLET_ENCRYPTION_KEY` (generate with `Fernet.generate_key()`)
- NEVER commit encryption key to git
- Use `.env` file (added to `.gitignore`)

### Input Validation

**Solana Address Validation:**
```python
import re

def validate_solana_address(address: str) -> bool:
    """Validate Solana address format (base58, 32-44 chars)"""
    pattern = r"^[1-9A-HJ-NP-Za-km-z]{32,44}$"
    return bool(re.match(pattern, address))

# Use in API endpoints:
@app.post("/api/v1/wallets")
async def add_wallet(address: str):
    if not validate_solana_address(address):
        raise HTTPException(400, "Invalid Solana address format")
    # ...
```

### API Security

**Rate Limiting (Future):**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/webhooks/helius")
@limiter.limit("100/minute")  # Helius webhook spam protection
async def helius_webhook(request: Request):
    # Verify HMAC signature
    signature = request.headers.get("X-Helius-Signature")
    if not verify_webhook_signature(await request.body(), signature):
        raise HTTPException(401, "Invalid webhook signature")
    # ...
```

---

## Performance Optimization

### Database Query Optimization

**Use Indexes (defined in migrations):**
```sql
-- positions table (already in migration)
CREATE INDEX idx_positions_status ON walltrack.positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_last_price_update ON walltrack.positions(last_price_update_at) WHERE status = 'open';
```

**Batch Queries:**
```python
# BAD (N+1 query problem):
for position in positions:
    token = await token_repo.get(position.token_id)

# GOOD (batch prefetch):
positions = await position_repo.get_all_open_with_tokens()  # JOIN in SQL
```

### External API Optimization

**Connection Pooling:**
```python
# src/walltrack/services/base.py
import httpx

class APIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
```

**Caching:**
- Token metadata (TTL 1h, implemented in tokens table)
- Jupiter prices (TTL 30s, in-memory cache)

### Worker Performance

**Async I/O (Non-Blocking):**
```python
# All workers use asyncio for concurrent operations
async def process_batch(signals):
    tasks = [process_signal(s) for s in signals]
    await asyncio.gather(*tasks)  # Process 10 signals concurrently
```

**Queue Size Limits:**
```python
# Prevent memory overflow
self.queue = asyncio.Queue(maxsize=1000)
```

---

### Backup Strategy

**Database:**
- Supabase automatic backups (Pro tier: daily)
- Manual export: `pg_dump walltrack > backup_$(date +%Y%m%d).sql`
- Restore: Supabase dashboard or `pg_restore backup.sql`

**Configuration:**
- `.env` file backup (contains API keys, encryption key)
- Store securely (password manager, encrypted storage)

---

## Next Steps (Implementation Roadmap)

**Phase 1: MVP (Simulation Mode Only)**
1. Database setup (run all migrations)
2. Implement core services (wallet, token, signal repos)
3. Implement workers (signal processor, token analyzer)
4. Basic Gradio UI (watchlist management)
5. Helius webhook integration
6. E2E test: Add wallet → Receive signal → Process → Display

**Phase 2: Live Mode (Real Trading)**
1. Implement position manager worker
2. Implement price monitor worker
3. Jupiter swap integration
4. Exit strategy executor
5. Wallet private key encryption
6. E2E test: Signal → Position → Price update → Exit

**Phase 3: Performance & Analytics**
1. Performance aggregator worker
2. Advanced Gradio dashboard (charts, analytics)
3. Circuit breaker implementation
4. Rate limit monitoring
5. Automated alerts

**Phase 4: Production Readiness**
1. VPS deployment
2. systemd service setup
3. Backup automation
4. Monitoring integration (UptimeRobot)
5. Security audit (key management, input validation)
