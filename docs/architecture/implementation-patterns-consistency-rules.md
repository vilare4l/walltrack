# Implementation Patterns & Consistency Rules

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
