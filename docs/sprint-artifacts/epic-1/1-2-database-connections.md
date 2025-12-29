# Story 1.2: Database Connections

**Status:** Done
**Epic:** 1 - Foundation & Core Infrastructure
**Created:** 2025-12-29
**Sprint Artifacts:** docs/sprint-artifacts/epic-1/

---

## Story

**As an** operator,
**I want** the system to connect to Supabase and Neo4j,
**so that** data persistence is available for all features.

---

## Acceptance Criteria

### AC1: Supabase Connection Working
- [x] Async Supabase client connects successfully with valid credentials
- [x] Health check query returns OK status
- [x] Connection uses `SecretStr` for API key (never logged)
- [x] `DatabaseConnectionError` raised on connection failure

### AC2: Neo4j Connection Working
- [x] Async Neo4j driver connects successfully with valid credentials
- [x] Simple Cypher query `RETURN 1 as ping` executes without error (uses verify_connectivity)
- [x] Connection uses `SecretStr` for password (never logged)
- [x] `DatabaseConnectionError` raised on connection failure

### AC3: Exception Hierarchy Created
- [x] `src/walltrack/core/exceptions.py` with `WallTrackError` base class
- [x] `DatabaseConnectionError` inherits from `WallTrackError`
- [x] Clear error messages with context (which DB failed)

### AC4: Health Endpoint Extended
- [x] `/api/health` returns database connection status
- [x] Response includes: `supabase: {status}`, `neo4j: {status}`
- [x] Overall status is "ok" only if ALL databases healthy

### AC5: FastAPI Lifecycle Integration
- [x] Database connections established on app startup
- [x] Connections properly closed on app shutdown
- [x] Graceful handling if DB unavailable at startup

---

## Tasks / Subtasks

### Task 1: Exception Hierarchy (AC: 3)
- [x] 1.1 Create `src/walltrack/core/exceptions.py`
- [x] 1.2 Define `WallTrackError` base exception
- [x] 1.3 Define `DatabaseConnectionError(WallTrackError)`
- [x] 1.4 Add other initial exceptions for future stories

### Task 2: Supabase Client (AC: 1, 5)
- [x] 2.1 Create `src/walltrack/data/supabase/client.py`
- [x] 2.2 Implement `SupabaseClient` class with connect/disconnect
- [x] 2.3 Add `health_check()` method
- [x] 2.4 Implement singleton pattern with `get_supabase_client()`
- [x] 2.5 Add tenacity retry on connection methods
- [x] 2.6 Write unit tests for client

### Task 3: Neo4j Client (AC: 2, 5)
- [x] 3.1 Create `src/walltrack/data/neo4j/client.py`
- [x] 3.2 Implement `Neo4jClient` class with connect/disconnect
- [x] 3.3 Add `session()` async context manager
- [x] 3.4 Add `health_check()` method with ping query
- [x] 3.5 Implement singleton pattern with `get_neo4j_client()`
- [x] 3.6 Add tenacity retry on query methods
- [x] 3.7 Write unit tests for client

### Task 4: FastAPI Lifecycle (AC: 5)
- [x] 4.1 Update `main.py` with lifespan context manager
- [x] 4.2 Initialize both clients on startup
- [x] 4.3 Close both clients on shutdown
- [x] 4.4 Handle startup failures gracefully

### Task 5: Health Endpoint Extension (AC: 4)
- [x] 5.1 Update `/api/health` to check both databases
- [x] 5.2 Return detailed status per database
- [x] 5.3 Write integration tests for health endpoint

---

## Dev Notes

### Project Structure (from Story 1-1)

The following structure already exists from Story 1-1:
```
src/walltrack/
├── main.py              # UPDATE: add lifespan
├── config/settings.py   # Already has DB credentials
├── core/
│   └── exceptions.py    # CREATE: exception hierarchy
├── data/
│   ├── supabase/
│   │   └── client.py    # CREATE: async client
│   └── neo4j/
│       └── client.py    # CREATE: async client
└── api/routes/
    └── health.py        # UPDATE: add DB status
```

### Settings Available (from Story 1-1)

From `src/walltrack/config/settings.py`:
```python
# Already defined - DO NOT DUPLICATE
supabase_url: str
supabase_key: SecretStr
neo4j_uri: str = "bolt://localhost:7687"
neo4j_user: str = "neo4j"
neo4j_password: SecretStr
```

### Architectural Constraints (CRITICAL)

| Rule | Requirement |
|------|-------------|
| Layer | `data/` = Database access ONLY |
| Imports | `from walltrack.core.exceptions import DatabaseConnectionError` |
| Async | All methods must be async (no `asyncio.run()` inside) |
| Logging | Use `structlog` with bound context |
| Secrets | Use `.get_secret_value()` only when needed |

### Database Ownership (from architecture.md)

| Database | Owns |
|----------|------|
| **Neo4j** | Wallet nodes, FUNDED_BY edges, SYNCED_BUY edges, clusters |
| **Supabase** | Wallet metrics, trades, signals, config, performance |

---

## Technical Requirements

### Supabase Client Pattern

```python
"""src/walltrack/data/supabase/client.py"""

from supabase._async.client import AsyncClient
from supabase._async.client import create_client as create_async_client

class SupabaseClient:
    """Async Supabase client wrapper."""

    def __init__(self) -> None:
        self._client: AsyncClient | None = None
        self._settings = get_settings()

    async def connect(self) -> None:
        """Establish connection."""
        if self._client is not None:
            return
        try:
            self._client = await create_async_client(
                self._settings.supabase_url,
                self._settings.supabase_key.get_secret_value(),
            )
            log.info("supabase_connected", url=self._settings.supabase_url)
        except Exception as e:
            log.error("supabase_connection_failed", error=str(e))
            raise DatabaseConnectionError(f"Supabase: {e}") from e

    async def health_check(self) -> dict[str, Any]:
        """Check connection health."""
        if self._client is None:
            return {"status": "disconnected", "healthy": False}
        return {"status": "connected", "healthy": True}

# Singleton pattern
async def get_supabase_client() -> SupabaseClient:
    """Get or create singleton."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
        await _supabase_client.connect()
    return _supabase_client
```

### Neo4j Client Pattern

```python
"""src/walltrack/data/neo4j/client.py"""

from neo4j import AsyncDriver, AsyncGraphDatabase

class Neo4jClient:
    """Async Neo4j client with connection management."""

    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self._settings = get_settings()

    async def connect(self) -> None:
        """Establish connection."""
        if self._driver is not None:
            return
        try:
            self._driver = AsyncGraphDatabase.driver(
                self._settings.neo4j_uri,
                auth=(
                    self._settings.neo4j_user,
                    self._settings.neo4j_password.get_secret_value(),
                ),
            )
            await self._driver.verify_connectivity()
            log.info("neo4j_connected", uri=self._settings.neo4j_uri)
        except Exception as e:
            log.error("neo4j_connection_failed", error=str(e))
            raise DatabaseConnectionError(f"Neo4j: {e}") from e

    async def health_check(self) -> dict[str, Any]:
        """Check connection with ping query."""
        if self._driver is None:
            return {"status": "disconnected", "healthy": False}
        try:
            await self._driver.verify_connectivity()
            return {"status": "connected", "healthy": True}
        except Exception as e:
            return {"status": "error", "healthy": False, "error": str(e)}
```

### FastAPI Lifespan Pattern

```python
"""src/walltrack/main.py - UPDATE"""

from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    try:
        await get_supabase_client()
        await get_neo4j_client()
    except DatabaseConnectionError as e:
        log.error("startup_failed", error=str(e))
        # Continue anyway - health check will show status

    yield

    # Shutdown
    await close_supabase_client()
    await close_neo4j_client()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    # ... routes
    return app
```

### Extended Health Response

```python
"""Response format for /api/health"""
{
    "status": "ok",  # or "degraded" if any DB down
    "version": "2.0.0",
    "databases": {
        "supabase": {"status": "connected", "healthy": true},
        "neo4j": {"status": "connected", "healthy": true}
    }
}
```

---

## Testing Requirements

### Unit Tests Required

```python
"""tests/unit/test_supabase_client.py"""
# Test connection with mocked supabase
# Test health_check returns correct format
# Test singleton pattern works
# Test DatabaseConnectionError raised on failure

"""tests/unit/test_neo4j_client.py"""
# Test connection with mocked neo4j driver
# Test health_check with ping query
# Test singleton pattern works
# Test DatabaseConnectionError raised on failure
```

### Integration Tests Required

```python
"""tests/integration/test_database_health.py"""
# Test /api/health returns DB status
# Test overall status is "ok" only if all healthy
# Test graceful degradation if one DB down
```

### Validation Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run only database tests
uv run pytest tests/ -v -k "supabase or neo4j"

# Type checking
uv run mypy src/walltrack/data/

# Start app and test health
uv run uvicorn walltrack.main:app --reload
curl http://localhost:8000/api/health
```

---

## References

| Source | Section | Relevance |
|--------|---------|-----------|
| [architecture.md](../../architecture.md) | Data Architecture | Neo4j vs Supabase ownership |
| [architecture.md](../../architecture.md) | API & Communication Patterns | tenacity retry, circuit breaker |
| [architecture.md](../../architecture.md) | Implementation Patterns | Naming, logging with structlog |
| [epics.md](../../epics.md) | Story 1.2 | Acceptance criteria |
| Story 1-1 | Dev Notes | Settings patterns, create_app() |

---

## Legacy Reference

### Patterns to REPRODUCE (Validated in V1)

**1. Singleton with async getter**
```python
_client: Client | None = None

async def get_client() -> Client:
    global _client
    if _client is None:
        _client = Client()
        await _client.connect()
    return _client
```

**2. structlog with bound context**
```python
import structlog
log = structlog.get_logger()

log.info("neo4j_connected", uri=uri)
log.error("connection_failed", error=str(e))
```

**3. tenacity retry decorator**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
)
async def execute_query(...):
    ...
```

**4. Async context manager for sessions**
```python
@asynccontextmanager
async def session(self) -> AsyncGenerator[AsyncSession, None]:
    session = self._driver.session()
    try:
        yield session
    finally:
        await session.close()
```

### Anti-patterns to AVOID

| Anti-pattern | Problem | Solution |
|--------------|---------|----------|
| `asyncio.run()` inside async | Blocks event loop | Use `await` directly |
| Bare `except:` | Catches SystemExit | Use `except Exception:` |
| Print secrets | Security risk | Use `SecretStr`, never log |
| Global mutable without lock | Race conditions | Use module-level singleton pattern |

### Legacy Files Analyzed

| File | Lines | Pattern Extracted |
|------|-------|-------------------|
| `legacy/src/walltrack/data/supabase/client.py` | 183 | SupabaseClient class, singleton |
| `legacy/src/walltrack/data/neo4j/client.py` | 182 | Neo4jClient class, session context |
| `legacy/src/walltrack/core/exceptions.py` | 79 | WallTrackError hierarchy |

---

## Dev Agent Record

### Context Reference
- Epic: 1 - Foundation & Core Infrastructure
- Story: 1.2 - Database Connections
- Previous Story: 1.1 - Project Structure & Configuration (status: review)

### Previous Story Intelligence

**From Story 1-1:**
- Project structure created with all `__init__.py` files
- Settings already includes: `supabase_url`, `supabase_key`, `neo4j_uri`, `neo4j_user`, `neo4j_password`
- Pattern: `get_settings()` with `@lru_cache`
- Pattern: `create_app()` factory in main.py
- All dev tools passing: Ruff, Mypy (strict), Pytest

**Files to UPDATE:**
- `src/walltrack/main.py` - Add lifespan
- `src/walltrack/api/routes/health.py` - Add DB status

**Files to CREATE:**
- `src/walltrack/core/exceptions.py`
- `src/walltrack/data/supabase/client.py`
- `src/walltrack/data/neo4j/client.py`

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List
1. **Task 1 Complete:** Exception hierarchy created with WallTrackError base, DatabaseConnectionError, ConfigurationError, ValidationError, ExternalServiceError
2. **Task 2 Complete:** SupabaseClient with async connect/disconnect, health_check (with actual auth verification), singleton pattern, tenacity retry on connect
3. **Task 3 Complete:** Neo4jClient with async connect/disconnect, session context manager, health_check with verify_connectivity, singleton pattern, tenacity retry on connect and execute_query
4. **Task 4 Complete:** FastAPI lifespan in main.py connects both DBs on startup, closes on shutdown, graceful degradation if DB unavailable
5. **Task 5 Complete:** Health endpoint extended with database status, returns ok/degraded based on both DB health
6. **Code Review Fixes:** Added retry to Neo4j connect(), added real health verification to Supabase, removed dead code from health.py, fixed test isolation in conftest.py

### File List
**Created:**
- `src/walltrack/core/exceptions.py` - Exception hierarchy
- `src/walltrack/data/supabase/client.py` - Supabase async client
- `src/walltrack/data/neo4j/client.py` - Neo4j async client
- `tests/unit/test_exceptions.py` - Exception tests
- `tests/unit/test_supabase_client.py` - Supabase client tests
- `tests/unit/test_neo4j_client.py` - Neo4j client tests
- `tests/unit/test_lifespan.py` - Lifespan management tests
- `tests/integration/test_database_health.py` - Health endpoint integration tests

**Modified:**
- `src/walltrack/main.py` - Added lifespan context manager
- `src/walltrack/api/routes/health.py` - Extended with DB status
- `tests/unit/test_health.py` - Updated for new health response format
- `tests/conftest.py` - Added singleton reset fixture for test isolation

---

## Success Criteria Summary

**Story is DONE when:**
1. `uv run pytest tests/` passes with database client tests
2. `uv run mypy src/` passes without errors
3. `/api/health` returns `{"status": "ok", "databases": {...}}`
4. Both Neo4j and Supabase show "connected" status
5. App starts gracefully even if one DB is unavailable
6. Code review passes (use fresh context LLM)

---

_Story generated by SM Agent (Bob) - 2025-12-29_
_Ultimate context engine analysis completed - comprehensive developer guide created_
