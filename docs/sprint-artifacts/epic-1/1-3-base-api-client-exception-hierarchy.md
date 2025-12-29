# Story 1.3: Base API Client & Exception Hierarchy

**Status:** done
**Epic:** 1 - Foundation & Core Infrastructure
**Created:** 2025-12-29
**Sprint Artifacts:** docs/sprint-artifacts/epic-1/

---

## Story

**As a** developer,
**I want** a BaseAPIClient with retry and circuit breaker,
**so that** all external API calls are resilient.

---

## Acceptance Criteria

### AC1: BaseAPIClient Implemented
- [x] `src/walltrack/services/base.py` with `BaseAPIClient` class
- [x] Uses `httpx.AsyncClient` for all HTTP operations
- [x] Supports GET, POST, PUT, DELETE methods
- [x] Configurable timeout and custom headers
- [x] Lazy client initialization (created on first request)
- [x] Proper `close()` method for cleanup

### AC2: Tenacity Retry Strategy
- [x] Retries 3 times with exponential backoff (1s, 2s, 4s)
- [x] Logs each retry attempt via structlog
- [x] Retries on: timeout, connection errors, 5xx server errors, 429 rate limit
- [x] Does NOT retry on: 4xx client errors (400, 401, 403, 404, etc.)
- [x] Note: Jitter is NOT implemented in base version (can be added later)

### AC3: Circuit Breaker Pattern
- [x] `CircuitBreaker` dataclass with CLOSED/OPEN/HALF_OPEN states
- [x] Opens after 5 consecutive failures (configurable via Settings)
- [x] 30 second cooldown before half-open (configurable via Settings)
- [x] Single test request allowed in half-open state
- [x] `CircuitBreakerOpenError` raised when circuit is open
- [x] Thread-safe for single-threaded async (no locks needed)

### AC4: Exception Hierarchy Extended
- [x] Add `CircuitBreakerOpenError` to `src/walltrack/core/exceptions.py`
- [x] Extend existing `ExternalServiceError` with optional `status_code` parameter
- [x] All exceptions inherit from `WallTrackError`
- [x] Clear error messages include service name and context

### AC5: Settings Updated
- [x] Add `circuit_breaker_threshold: int = 5` to Settings class
- [x] Add `circuit_breaker_cooldown: int = 30` to Settings class
- [x] Add field validators: both must be positive integers (> 0)

### AC6: Unit Tests Cover All Paths
- [x] Test retry on transient failure (timeout) then success
- [x] Test NO retry on 4xx errors (400, 401, 403, 404)
- [x] Test retry on 429 rate limit
- [x] Test retry on 5xx errors (500, 502, 503)
- [x] Test circuit breaker opens after threshold failures
- [x] Test circuit breaker cooldown and half-open transition
- [x] Test request fails fast when circuit is open
- [x] Test `close()` method cleans up client
- [x] All tests pass with mocked httpx

---

## Tasks / Subtasks

### Task 1: Update Settings (AC: 5) - DO FIRST
- [x] 1.1 Add `circuit_breaker_threshold` field to Settings class
- [x] 1.2 Add `circuit_breaker_cooldown` field to Settings class
- [x] 1.3 Add `@field_validator` for positive integer validation (using ge=1 constraint)
- [x] 1.4 Update `.env.example` with new optional fields
- [x] 1.5 Run `uv run pytest tests/unit/test_settings.py` ✅ 14/14 passed

### Task 2: Extend Exception Hierarchy (AC: 4)
- [x] 2.1 Add `CircuitBreakerOpenError` to exceptions.py
- [x] 2.2 Update `ExternalServiceError` to accept optional `status_code: int | None = None`
- [x] 2.3 Write unit tests for new/updated exceptions ✅ 16/16 passed
- [x] 2.4 Run `uv run mypy src/walltrack/core/exceptions.py` ✅ Success

### Task 3: Create CircuitBreaker (AC: 3)
- [x] 3.1 Create `src/walltrack/services/base.py`
- [x] 3.2 Implement `CircuitState` enum (CLOSED, OPEN, HALF_OPEN)
- [x] 3.3 Implement `CircuitBreaker` dataclass with state machine
- [x] 3.4 Add structlog logging for state transitions
- [x] 3.5 Write unit tests for circuit breaker state machine ✅ 20/20 passed

### Task 4: Create BaseAPIClient (AC: 1, 2)
- [x] 4.1 Implement `BaseAPIClient` class with lazy `_get_client()`
- [x] 4.2 Implement `_request()` with manual retry loop (NOT tenacity decorator)
- [x] 4.3 Implement retry logic: retry on timeout/5xx/429, fail fast on 4xx
- [x] 4.4 Integrate circuit breaker check before each request
- [x] 4.5 Implement `get()`, `post()`, `put()`, `delete()` methods
- [x] 4.6 Implement `close()` method for cleanup
- [x] 4.7 Write comprehensive unit tests ✅ 23/23 passed

### Task 5: Validation (AC: 6)
- [x] 5.1 Run full test suite: `uv run pytest tests/ -v` ✅ 73/73 story tests passed
- [x] 5.2 Run type checking: `uv run mypy src/walltrack/` ✅ No issues in 34 files
- [x] 5.3 Run linting: `uv run ruff check src/` ✅ All checks passed

---

## Dev Notes

### Files to CREATE
- `src/walltrack/services/base.py` - CircuitBreaker + BaseAPIClient
- `tests/unit/services/__init__.py`
- `tests/unit/services/test_circuit_breaker.py`
- `tests/unit/services/test_base_client.py`

### Files to UPDATE
- `src/walltrack/config/settings.py` - Add circuit breaker fields + validators
- `src/walltrack/core/exceptions.py` - Add CircuitBreakerOpenError, update ExternalServiceError

### Architecture Rules (from architecture.md)

| Rule | Requirement |
|------|-------------|
| Layer | `services/` = External APIs ONLY |
| Imports | Absolute: `from walltrack.core.exceptions import ...` |
| Async | All methods async, never `asyncio.run()` inside async |
| HTTP | `httpx.AsyncClient` only |
| Logging | `structlog` event-based: `log.info("event_name", key=value)` |

### Retry Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| Max retries | 3 | Fixed |
| Backoff | 1s, 2s, 4s | Exponential (2^attempt) capped at 4s |
| Circuit threshold | 5 | From Settings |
| Cooldown | 30s | From Settings |

### HTTP Status Retry Matrix

| Status | Retry? | Reason |
|--------|--------|--------|
| 2xx | N/A | Success |
| 400, 401, 403, 404 | NO | Client error, won't change |
| 429 | YES | Rate limit, will recover |
| 500, 502, 503 | YES | Server error, may recover |
| Timeout | YES | Transient |
| Connection error | YES | Transient |

---

## Technical Patterns

### Settings Update Pattern

```python
# Add to Settings class in config/settings.py

# Circuit Breaker
circuit_breaker_threshold: int = Field(
    default=5, ge=1, description="Failures before circuit opens"
)
circuit_breaker_cooldown: int = Field(
    default=30, ge=1, description="Seconds before half-open"
)
```

### Exception Update Pattern

```python
# Add to exceptions.py

class CircuitBreakerOpenError(WallTrackError):
    """Raised when circuit breaker is open."""
    pass

# UPDATE existing ExternalServiceError to add status_code
class ExternalServiceError(WallTrackError):
    """Raised when an external service call fails."""
    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None
    ) -> None:
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service}: {message}")
```

### CircuitBreaker Core Logic

```python
@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    cooldown_seconds: int = 30
    failure_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = datetime.utcnow() - self.last_failure_time
            if elapsed > timedelta(seconds=self.cooldown_seconds):
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN allows test request
```

### BaseAPIClient Request Pattern

```python
async def _request(self, method: str, path: str, max_retries: int = 3, **kwargs) -> httpx.Response:
    self._circuit_breaker.raise_if_open()
    client = await self._get_client()

    for attempt in range(max_retries):
        try:
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            self._circuit_breaker.record_success()
            return response
        except httpx.HTTPStatusError as e:
            # 4xx (except 429) = no retry, fail immediately
            if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                raise ExternalServiceError(
                    self.base_url, str(e), e.response.status_code
                ) from e
            # 429 or 5xx = retry
            self._circuit_breaker.record_failure()
        except (httpx.TimeoutException, httpx.RequestError):
            self._circuit_breaker.record_failure()

        if attempt < max_retries - 1:
            await asyncio.sleep(min(2 ** attempt, 4))

    raise ExternalServiceError(self.base_url, "Max retries exceeded")
```

---

## Test Requirements Summary

| Test Case | Expected |
|-----------|----------|
| GET success | 200 returned |
| Timeout then success | Retry, return 200 |
| 404 error | Fail immediately, no retry |
| 429 then success | Retry, return 200 |
| 500 then success | Retry, return 200 |
| 5 failures | Circuit opens |
| Circuit open | `CircuitBreakerOpenError` raised |
| After cooldown | Half-open, allows test request |
| `close()` called | Client closed properly |

---

## Previous Story Patterns (from 1-1, 1-2)

| Pattern | Usage |
|---------|-------|
| `@lru_cache` on `get_settings()` | Already implemented |
| `SecretStr` for secrets | Use for API keys |
| `@field_validator` | Use for circuit breaker validation |
| structlog with bound context | `log.info("event", key=value)` |
| Singleton pattern | Per-client instance, not global |

---

## Legacy Reference (V1 → V2)

**Reproduce from `legacy/src/walltrack/services/base.py`:**
- CircuitBreaker dataclass with state machine
- BaseAPIClient with lazy httpx client
- Manual retry loop with exponential backoff

**Avoid V1 anti-patterns:**
- Don't use `asyncio.run()` inside async
- Don't use `datetime.now()` (use `datetime.utcnow()`)
- Don't retry all errors (fail fast on 4xx)

---

## Success Criteria

**Story DONE when:**
1. `uv run pytest tests/unit/services/ -v` - All tests pass
2. `uv run mypy src/walltrack/` - No type errors
3. `uv run ruff check src/` - No lint errors
4. Circuit breaker opens after 5 failures
5. BaseAPIClient retries correctly per HTTP status matrix
6. Settings validation rejects threshold=0 or cooldown=-1

---

_Story generated by SM Agent (Bob) - 2025-12-29_
_Quality Competition improvements applied - optimized for LLM dev agent consumption_
