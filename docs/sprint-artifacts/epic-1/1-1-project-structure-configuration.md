# Story 1.1: Project Structure & Configuration

**Status:** Done
**Epic:** 1 - Foundation & Core Infrastructure
**Created:** 2025-12-29
**Sprint Artifacts:** docs/sprint-artifacts/epic-1/

---

## Story

**As a** developer,
**I want** a clean, well-organized project structure with configuration management,
**so that** I can develop efficiently with clear boundaries between layers.

---

## Acceptance Criteria

### AC1: Project Structure Created
- [x] Directory structure matches architecture.md specification exactly
- [x] All `__init__.py` files created for Python packages
- [x] `pyproject.toml` configured with uv dependencies
- [x] `.gitignore` includes standard Python + env patterns

### AC2: Configuration System Working
- [x] `src/walltrack/config/settings.py` with pydantic-settings
- [x] `.env.example` template with all required variables
- [x] Settings loads from environment variables
- [x] Validation fails gracefully with clear error messages

### AC3: Base Application Skeleton
- [x] `src/walltrack/main.py` creates FastAPI app
- [x] Health check endpoint at `/api/health` returns `{"status": "ok"}`
- [x] Application starts without errors
- [x] Imports work: `from walltrack.config import get_settings`

### AC4: Development Tools Configured
- [x] Ruff configured in `pyproject.toml`
- [x] mypy configured with strict mode
- [x] pytest configured with asyncio support
- [x] `uv run pytest` passes with at least 1 test

### AC5: Docker Ready (Optional but Recommended)
- [x] `Dockerfile` for production build
- [x] `docker-compose.yml` for local development
- [x] Container builds successfully (health check updated to /api/health)

---

## Tasks / Subtasks

### Task 1: Initialize Project Structure (AC: 1)
- [x] 1.1 Create directory tree from architecture.md
- [x] 1.2 Create all `__init__.py` files
- [x] 1.3 Create `pyproject.toml` with dependencies
- [x] 1.4 Run `uv sync` to install dependencies
- [x] 1.5 Create `.gitignore`

### Task 2: Configuration System (AC: 2)
- [x] 2.1 Create `src/walltrack/config/__init__.py`
- [x] 2.2 Create `src/walltrack/config/settings.py` with pydantic-settings
- [x] 2.3 Create `.env.example` with all variables
- [x] 2.4 Test settings loading

### Task 3: Base Application (AC: 3)
- [x] 3.1 Create `src/walltrack/main.py` with FastAPI
- [x] 3.2 Create `src/walltrack/api/routes/health.py`
- [x] 3.3 Register health route
- [x] 3.4 Test application starts

### Task 4: Development Tools (AC: 4)
- [x] 4.1 Configure Ruff in pyproject.toml
- [x] 4.2 Configure mypy in pyproject.toml
- [x] 4.3 Configure pytest in pyproject.toml
- [x] 4.4 Create `tests/conftest.py`
- [x] 4.5 Create `tests/unit/test_health.py`
- [x] 4.6 Verify all tools pass

### Task 5: Docker Setup (AC: 5)
- [x] 5.1 Create Dockerfile
- [x] 5.2 Create docker-compose.yml
- [x] 5.3 Test container build

---

## Dev Notes

### Project Structure (from architecture.md)

```
walltrack/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── Dockerfile
├── docker-compose.yml
│
├── src/
│   └── walltrack/
│       ├── __init__.py
│       ├── main.py              # FastAPI + Gradio mount
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py      # pydantic-settings
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   └── health.py
│       │   └── webhooks/
│       │       └── __init__.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── exceptions.py    # (Story 1.3)
│       │   ├── discovery/
│       │   │   └── __init__.py
│       │   ├── wallets/
│       │   │   └── __init__.py
│       │   ├── cluster/
│       │   │   └── __init__.py
│       │   ├── scoring/
│       │   │   └── __init__.py
│       │   ├── positions/
│       │   │   └── __init__.py
│       │   ├── execution/
│       │   │   └── __init__.py
│       │   └── risk/
│       │       └── __init__.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── models/
│       │   │   └── __init__.py
│       │   ├── neo4j/
│       │   │   └── __init__.py
│       │   └── supabase/
│       │       └── __init__.py
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── base.py          # (Story 1.3)
│       │   ├── helius/
│       │   │   └── __init__.py
│       │   ├── jupiter/
│       │   │   └── __init__.py
│       │   ├── dexscreener/
│       │   │   └── __init__.py
│       │   └── solana/
│       │       └── __init__.py
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── pages/
│       │   │   └── __init__.py
│       │   └── components/
│       │       └── __init__.py
│       │
│       └── scheduler/
│           └── __init__.py
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── unit/
    │   └── __init__.py
    └── integration/
        └── __init__.py
```

### Dependencies (pyproject.toml)

```toml
[project]
name = "walltrack"
version = "2.0.0"
description = "WallTrack V2 - Autonomous Trading Intelligence"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "gradio>=5.0.0",
    "neo4j>=5.26.0",
    "supabase>=2.10.0",
    "httpx>=0.28.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "apscheduler>=3.10.0",
    "structlog>=24.4.0",
    "tenacity>=9.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Settings Template (settings.py)

```python
"""Application settings using pydantic-settings."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """WallTrack V2 configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # Application
    app_name: str = Field(default="WallTrack", description="Application name")
    app_version: str = Field(default="2.0.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # Database - Supabase
    supabase_url: str = Field(description="Supabase project URL")
    supabase_key: SecretStr = Field(description="Supabase API key")

    # Database - Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: SecretStr = Field(description="Neo4j password")

    # External APIs (minimal for Story 1.1)
    helius_api_key: SecretStr = Field(default=SecretStr(""), description="Helius API key")

    # Trading mode (to be used in later stories)
    trading_mode: str = Field(default="simulation", description="simulation | live")

    @field_validator("neo4j_uri")
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        """Validate Neo4j URI format."""
        if not v.startswith(("bolt://", "neo4j://", "neo4j+s://")):
            raise ValueError("Neo4j URI must start with bolt://, neo4j://, or neo4j+s://")
        return v

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate Supabase URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Supabase URL must start with http:// or https://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()
```

### Environment Variables (.env.example)

```bash
# Application
DEBUG=false

# Server
HOST=0.0.0.0
PORT=8000

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# External APIs
HELIUS_API_KEY=your-helius-key

# Trading
TRADING_MODE=simulation
```

### Architectural Boundaries (CRITICAL)

| Layer | Rule | Example |
|-------|------|---------|
| `api/` | Routes ONLY | `@router.get("/health")` |
| `core/` | Business logic ONLY | `SignalScorer`, `PositionManager` |
| `data/` | Database access ONLY | `WalletRepository`, `Neo4jClient` |
| `services/` | External APIs ONLY | `HeliusClient`, `JupiterClient` |

**Import Direction:**
```
api/ → core/ → data/ + services/
```

**Never:**
- Import from `api/` in `core/`
- Import from `ui/` in backend
- Use relative imports

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `signal_scorer.py` |
| Classes | PascalCase | `SignalScorer` |
| Functions | snake_case | `calculate_score` |
| Constants | UPPER_SNAKE | `MAX_RETRIES` |

---

## Testing Requirements

### Unit Test Example (tests/unit/test_health.py)

```python
import pytest
from fastapi.testclient import TestClient

from walltrack.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

### Validation Commands

```bash
# Install dependencies
uv sync

# Run linting
uv run ruff check src/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest tests/ -v

# Start application (manual test)
uv run uvicorn walltrack.main:app --reload
```

---

## References

| Source | Section | Relevance |
|--------|---------|-----------|
| [architecture.md](../../architecture.md) | Project Structure & Boundaries | Full directory tree |
| [architecture.md](../../architecture.md) | Implementation Patterns | Naming, imports |
| [architecture.md](../../architecture.md) | Core Architectural Decisions | pydantic-settings choice |
| [prd.md](../../prd.md) | Technical Architecture | Stack overview |

---

## Legacy Reference

### Fichiers analysés
| Fichier | Lignes | Pertinence |
|---------|--------|------------|
| `legacy/src/walltrack/config/settings.py` | 288 | Configuration pydantic-settings |
| `legacy/src/walltrack/main.py` | 24 | Pattern entry point |

### Patterns à REPRODUIRE (V1 → V2)

**1. `@lru_cache` sur `get_settings()` (performance)**
```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

**2. `SecretStr` pour les secrets (sécurité)**
```python
from pydantic import SecretStr

neo4j_password: SecretStr = Field(default=SecretStr(""), description="Neo4j password")
supabase_key: SecretStr = Field(default=SecretStr(""), description="Supabase API key")
```

**3. `field_validator` pour validation custom**
```python
from pydantic import field_validator

@field_validator("neo4j_uri")
@classmethod
def validate_neo4j_uri(cls, v: str) -> str:
    if not v.startswith(("bolt://", "neo4j://")):
        raise ValueError("Neo4j URI must start with bolt:// or neo4j://")
    return v
```

**4. Pattern `create_app()` factory (main.py)**
```python
from walltrack.api.app import create_app
app = create_app()
```

**5. Champs avec `Field(description=...)` pour auto-documentation**

### Anti-patterns à ÉVITER (erreurs V1)

| Anti-pattern | Problème V1 | Solution V2 |
|--------------|-------------|-------------|
| Settings géant (288 lignes) | Tout dans un fichier | Commencer minimal, ajouter par story |
| Trading config dans Settings | Non modifiable sans restart | Config dynamique dans Supabase (Story 1.2) |
| Champs dupliqués | `api_base_url` apparaît 2x | Revue de code stricte |

### Structure legacy à comparer

```
legacy/src/walltrack/           V2 simplifié:
├── api/                        ├── api/
├── config/                     ├── config/
├── constants/          ❌      (intégrer dans config)
├── core/                       ├── core/
├── data/                       ├── data/
├── discovery/          ❌      (move to core/discovery/)
├── models/             ❌      (move to data/models/)
├── scheduler/                  ├── scheduler/
├── services/                   ├── services/
└── ui/                         └── ui/
```

---

## Dev Agent Record

### Context Reference
- Epic: 1 - Foundation & Core Infrastructure
- Story: 1.1 - Project Structure & Configuration
- Previous Story: None (first story)

### Agent Model Used
Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List
- Created complete src/walltrack directory structure with all __init__.py files
- Implemented pydantic-settings configuration with validation (neo4j_uri, supabase_url)
- Created FastAPI application with /api/health endpoint
- Wrote 8 unit tests covering settings and health endpoint
- All dev tools configured and passing: Ruff, Mypy (strict), Pytest
- Updated Dockerfile and docker-compose.yml health checks to /api/health
- Used red-green-refactor cycle throughout implementation
- Pattern decisions: @lru_cache for settings, SecretStr for secrets, create_app() factory

### File List
**New files created:**
- src/walltrack/__init__.py
- src/walltrack/main.py
- src/walltrack/config/__init__.py
- src/walltrack/config/settings.py
- src/walltrack/api/__init__.py
- src/walltrack/api/routes/__init__.py
- src/walltrack/api/routes/health.py
- src/walltrack/api/webhooks/__init__.py
- src/walltrack/core/__init__.py
- src/walltrack/core/discovery/__init__.py
- src/walltrack/core/wallets/__init__.py
- src/walltrack/core/cluster/__init__.py
- src/walltrack/core/scoring/__init__.py
- src/walltrack/core/positions/__init__.py
- src/walltrack/core/execution/__init__.py
- src/walltrack/core/risk/__init__.py
- src/walltrack/data/__init__.py
- src/walltrack/data/models/__init__.py
- src/walltrack/data/neo4j/__init__.py
- src/walltrack/data/supabase/__init__.py
- src/walltrack/services/__init__.py
- src/walltrack/services/helius/__init__.py
- src/walltrack/services/jupiter/__init__.py
- src/walltrack/services/dexscreener/__init__.py
- src/walltrack/services/solana/__init__.py
- src/walltrack/ui/__init__.py
- src/walltrack/ui/pages/__init__.py
- src/walltrack/ui/components/__init__.py
- src/walltrack/scheduler/__init__.py
- tests/unit/__init__.py
- tests/unit/test_settings.py
- tests/unit/test_health.py
- tests/integration/__init__.py

**Modified files:**
- pyproject.toml (version 0.1.0 → 2.0.0)
- Dockerfile (health check /health → /api/health)
- docker-compose.yml (health check /health → /api/health)

---

## Success Criteria Summary

**Story is DONE when:**
1. `uv sync` completes without errors
2. `uv run ruff check src/` passes
3. `uv run mypy src/` passes
4. `uv run pytest tests/` passes (≥1 test)
5. `curl http://localhost:8000/api/health` returns `{"status": "ok"}`

---

_Story generated by SM Agent (Bob) - 2025-12-29_
_Ultimate context engine analysis completed - comprehensive developer guide created_
