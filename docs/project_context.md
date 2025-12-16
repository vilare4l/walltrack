---
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-15'
---

# Project Context for AI Agents

_Critical rules and patterns for implementing WallTrack. Follow these exactly._

---

## Technology Stack & Versions

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | latest | API framework |
| Gradio | latest | Dashboard |
| Neo4j | latest + async driver | Graph database |
| Supabase | latest | PostgreSQL + Vectors |
| httpx | latest | HTTP client (async) |
| Pydantic | v2 | Data validation |
| structlog | latest | Structured logging |
| tenacity | latest | Retry logic |
| Ruff | latest | Linting + formatting |
| mypy | latest (strict) | Type checking |
| pytest | latest + pytest-asyncio | Testing |
| Docker | latest | Deployment |

---

## Critical Implementation Rules

### Python Rules

- **Always use type hints** — mypy strict mode is enforced
- **Always async** — Never use `asyncio.run()` inside async functions
- **Absolute imports only** — `from walltrack.core.scoring import ...`
- **snake_case everywhere** — Variables, functions, files, modules
- **PascalCase for classes** — `WalletProfile`, `SignalScorer`
- **UPPER_SNAKE for constants** — `MAX_RETRIES`, `DEFAULT_THRESHOLD`

### FastAPI Rules

- **Dependency injection** — Use `Depends()` for shared resources
- **Pydantic models for all I/O** — Never raw dicts in routes
- **Standard response format:**
  ```python
  # Success
  {"data": {...}, "meta": {"timestamp": "..."}}
  # Error
  {"error": {"code": "...", "message": "...", "detail": {...}}}
  ```
- **HMAC validation** — All Helius webhooks must verify signature

### Database Rules

**Neo4j (relationships):**
- Node labels: PascalCase (`Wallet`, `Token`, `Cluster`)
- Relationships: UPPER_SNAKE (`FUNDED_BY`, `SYNCED_BUY`)
- Properties: snake_case (`wallet_address`, `created_at`)

**Supabase (metrics):**
- Tables: snake_case plural (`wallets`, `trades`, `signals`)
- Columns: snake_case (`wallet_address`, `win_rate`)
- Foreign keys: `{table}_id` (`wallet_id`, `trade_id`)

### Logging Rules

- **Always use structlog** with bound context
- **Never string formatting** in log calls
```python
# Correct
log.info("signal_processed", wallet_id=wallet_id, score=score)

# Wrong
log.info(f"Signal processed for {wallet_id}")
```
- **Never log sensitive data** — No private keys, full signatures, API keys

### Error Handling Rules

- **Always use custom exceptions** from `walltrack.core.exceptions`
- **Never bare `raise Exception`**
- **Exception hierarchy:**
  - `WallTrackError` (base)
  - `WalletNotFoundError`
  - `CircuitBreakerOpenError`
  - `InsufficientBalanceError`

### Testing Rules

- **Tests in `tests/`** directory, mirroring src structure
- **Fixtures in `conftest.py`**
- **Async tests** — Use `@pytest.mark.asyncio`
- **Unit tests** — `tests/unit/`
- **Integration tests** — `tests/integration/`

---

## Code Quality Rules

### Ruff Configuration

- Run `ruff check .` before committing
- Run `ruff format .` for formatting
- All imports sorted automatically

### mypy Configuration

- Strict mode enabled
- All functions must have return type annotations
- No `Any` type without explicit justification

---

## Project Structure Rules

```
src/walltrack/
├── api/          # FastAPI routes only
├── core/         # Business logic only
├── data/         # Database access only
├── services/     # External APIs only
├── discovery/    # Wallet discovery only
├── ml/           # ML models only
├── ui/           # Gradio dashboard only
├── config/       # Configuration only
└── scheduler/    # Background tasks only
```

**Boundary rules:**
- `api/` → calls `core/` → calls `data/` and `services/`
- Never call `data/` directly from `api/`
- Never import from `ui/` in backend modules

---

## Critical Don't-Miss Rules

### Security

- **Private keys** — Environment variables ONLY, never in code
- **API keys** — Load via pydantic-settings, never hardcode
- **Webhook validation** — ALWAYS verify Helius HMAC signature
- **.env.example** — Version this, never version `.env`

### Performance

- **Never blocking calls** in async functions
- **Use httpx** for all HTTP requests (async)
- **Connection pooling** — Reuse Neo4j/Supabase clients

### Anti-Patterns

```python
# NEVER do this
asyncio.run(some_async_function())  # Inside async code
from .module import something        # Relative imports
print(f"Debug: {data}")              # Use structlog instead
raise Exception("error")             # Use custom exceptions
wallet_data = {"address": "..."}     # Use Pydantic models
```

### Data Ownership

- **Neo4j owns:** Wallet relationships, clusters, graph data
- **Supabase owns:** Metrics, trade history, scores, config, exit strategies
- **Never duplicate** — Each piece of data has ONE owner

### Exit Strategy Rules

- **Always use ExitStrategy model** — Never hardcode exit logic
- **Exit strategies are configurable** — Stored in Supabase `exit_strategies` table
- **Score-based assignment** — Higher conviction = more aggressive strategy
- **Trailing stop is optional** — Check `trailing_stop.enabled` before applying
- **Moonbag can be zero** — Not all strategies have moonbag

---

## API Patterns

### External Service Clients

All clients in `services/` must:
1. Inherit from `BaseAPIClient`
2. Use `tenacity` for retries (3 retries, exponential backoff)
3. Implement circuit breaker pattern
4. Have a fallback strategy documented

### Retry Configuration

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(httpx.HTTPError)
)
async def api_call(...):
    ...
```

---

_Last updated: 2025-12-15_
