# Core Architectural Decisions

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
