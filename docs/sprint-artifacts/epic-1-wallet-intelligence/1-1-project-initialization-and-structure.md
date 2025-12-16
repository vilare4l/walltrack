# Story 1.1: Project Initialization and Structure

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: ready
- **Priority**: Critical (Foundation)
- **FR**: Foundation for all FRs

## User Story

**As a** developer,
**I want** the project properly initialized with correct structure,
**So that** all subsequent development follows consistent patterns.

## Acceptance Criteria

### AC 1: Project Initialization
**Given** a fresh development environment
**When** the project is initialized with uv
**Then** all dependencies are installed correctly
**And** the virtual environment is created
**And** the project can be run locally

### AC 2: Directory Structure
**Given** the initialized project
**When** the structure is created
**Then** all directories match the architecture specification
**And** __init__.py files exist in all packages
**And** the layered architecture is respected (api → core → data/services)

### AC 3: Development Tools
**Given** the project structure
**When** development tools run
**Then** ruff lint passes with no errors
**And** mypy strict mode passes
**And** pytest discovers test directories

## Technical Specifications

### Initialization Commands

```bash
# Create project directory
mkdir -p walltrack && cd walltrack

# Initialize with uv
uv init

# Add production dependencies
uv add fastapi uvicorn[standard] gradio neo4j supabase httpx \
    pydantic-settings apscheduler xgboost scikit-learn \
    structlog tenacity python-dotenv

# Add development dependencies
uv add --dev pytest pytest-asyncio pytest-cov ruff mypy \
    httpx-mock types-python-dateutil
```

### pyproject.toml Configuration

```toml
[project]
name = "walltrack"
version = "0.1.0"
description = "Autonomous Solana memecoin trading system"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "gradio>=4.15.0",
    "neo4j>=5.17.0",
    "supabase>=2.3.0",
    "httpx>=0.26.0",
    "pydantic-settings>=2.1.0",
    "apscheduler>=3.10.4",
    "xgboost>=2.0.3",
    "scikit-learn>=1.4.0",
    "structlog>=24.1.0",
    "tenacity>=8.2.3",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.2.0",
    "mypy>=1.8.0",
    "httpx-mock>=0.0.7",
    "types-python-dateutil>=2.8.19",
]

[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501"]

[tool.ruff.isort]
known-first-party = ["walltrack"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/walltrack"]
```

### Complete Directory Structure

```
walltrack/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
│
├── src/
│   └── walltrack/
│       ├── __init__.py
│       ├── main.py                   # Entry point
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── dependencies.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── webhooks.py
│       │   │   ├── health.py
│       │   │   ├── wallets.py
│       │   │   ├── signals.py
│       │   │   ├── trades.py
│       │   │   └── config.py
│       │   └── middleware/
│       │       ├── __init__.py
│       │       ├── hmac_validation.py
│       │       └── error_handler.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── exceptions.py
│       │   ├── scoring/
│       │   │   ├── __init__.py
│       │   │   ├── signal_scorer.py
│       │   │   ├── wallet_scorer.py
│       │   │   └── weights.py
│       │   ├── risk/
│       │   │   ├── __init__.py
│       │   │   ├── circuit_breaker.py
│       │   │   ├── position_limits.py
│       │   │   └── system_state.py
│       │   ├── execution/
│       │   │   ├── __init__.py
│       │   │   ├── position_manager.py
│       │   │   ├── exit_manager.py
│       │   │   ├── trailing_stop.py
│       │   │   └── trade_executor.py
│       │   └── feedback/
│       │       ├── __init__.py
│       │       ├── trade_recorder.py
│       │       ├── score_updater.py
│       │       ├── accuracy_tracker.py
│       │       ├── pattern_analyzer.py
│       │       ├── model_calibrator.py
│       │       └── backtester.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── wallet.py
│       │   │   ├── signal.py
│       │   │   ├── trade.py
│       │   │   ├── position.py
│       │   │   ├── cluster.py
│       │   │   ├── exit_strategy.py
│       │   │   └── config.py
│       │   ├── neo4j/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   ├── queries/
│       │   │   │   ├── __init__.py
│       │   │   │   ├── wallet.py
│       │   │   │   └── cluster.py
│       │   │   └── schemas.py
│       │   └── supabase/
│       │       ├── __init__.py
│       │       ├── client.py
│       │       ├── repositories/
│       │       │   ├── __init__.py
│       │       │   ├── wallet_repo.py
│       │       │   ├── trade_repo.py
│       │       │   ├── signal_repo.py
│       │       │   ├── position_repo.py
│       │       │   └── config_repo.py
│       │       └── migrations/
│       │           └── 001_initial.sql
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── helius/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   ├── webhook_manager.py
│       │   │   └── models.py
│       │   ├── jupiter/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── models.py
│       │   ├── dexscreener/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── models.py
│       │   ├── birdeye/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── models.py
│       │   └── solana/
│       │       ├── __init__.py
│       │       ├── rpc_client.py
│       │       └── wallet_client.py
│       │
│       ├── discovery/
│       │   ├── __init__.py
│       │   ├── scanner.py
│       │   ├── profiler.py
│       │   └── decay_detector.py
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── dashboard.py
│       │   ├── components/
│       │   │   ├── __init__.py
│       │   │   ├── wallets.py
│       │   │   ├── clusters.py
│       │   │   ├── signals.py
│       │   │   ├── positions.py
│       │   │   ├── performance.py
│       │   │   ├── config_panel.py
│       │   │   ├── exit_strategies.py
│       │   │   ├── status.py
│       │   │   ├── alerts.py
│       │   │   └── backtest.py
│       │   └── charts.py
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   └── logging.py
│       │
│       └── scheduler/
│           ├── __init__.py
│           ├── jobs.py
│           └── tasks/
│               ├── __init__.py
│               ├── discovery_task.py
│               ├── decay_check_task.py
│               └── cleanup_task.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── test_scoring.py
│   │   │   ├── test_circuit_breaker.py
│   │   │   └── test_position_manager.py
│   │   └── services/
│   │       ├── __init__.py
│   │       └── test_base_client.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_neo4j.py
│   │   ├── test_supabase.py
│   │   └── test_helius.py
│   └── e2e/
│       ├── __init__.py
│       └── test_signal_flow.py
│
└── scripts/
    ├── setup_neo4j.py
    ├── setup_supabase.py
    └── seed_data.py
```

### Base Files Content

**src/walltrack/__init__.py:**
```python
"""WallTrack - Autonomous Solana memecoin trading system."""

__version__ = "0.1.0"
```

**src/walltrack/main.py:**
```python
"""Application entry point."""

import uvicorn
from walltrack.api.app import create_app
from walltrack.config.settings import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "walltrack.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
```

**src/walltrack/core/exceptions.py:**
```python
"""Custom exceptions for WallTrack."""


class WallTrackError(Exception):
    """Base exception for all WallTrack errors."""

    pass


class WalletNotFoundError(WallTrackError):
    """Raised when a wallet is not found."""

    pass


class SignalProcessingError(WallTrackError):
    """Raised when signal processing fails."""

    pass


class TradeExecutionError(WallTrackError):
    """Raised when trade execution fails."""

    pass


class CircuitBreakerOpenError(WallTrackError):
    """Raised when circuit breaker is open."""

    pass


class InsufficientBalanceError(WallTrackError):
    """Raised when balance is insufficient for trade."""

    pass


class ConfigurationError(WallTrackError):
    """Raised when configuration is invalid."""

    pass


class DatabaseConnectionError(WallTrackError):
    """Raised when database connection fails."""

    pass
```

**.env.example:**

> **Note:** See `/.env.example` at project root for the complete configuration file with all variables documented.

Key sections include:
- Application settings (DEBUG, HOST, PORT)
- Neo4j connection (localai stack integration)
- Supabase/PostgreSQL connection
- Helius API (webhooks)
- Jupiter API (swaps)
- DexScreener/Birdeye (token data)
- Solana RPC and trading wallet
- Trading configuration (position limits, thresholds)
- Risk management parameters
- Exit strategy defaults

```bash
# Quick reference - essential variables
NEO4J_URI=bolt://localhost:7687
SUPABASE_URL=http://localhost:54321
HELIUS_API_KEY=your_helius_key_here
TRADING_WALLET_PRIVATE_KEY=your_base58_private_key_here
```

**.gitignore:**
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/

# uv
.uv/
uv.lock

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local
.env.*.local

# Testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/

# Logs
*.log
logs/

# ML models
*.pkl
*.joblib
src/walltrack/ml/models/*.model

# OS
.DS_Store
Thumbs.db
```

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uv", "run", "uvicorn", "walltrack.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**docker-compose.yml:**

> **Note:** See `/docker-compose.yml` at project root for the complete configuration.

```yaml
# Usage:
#   Development (standalone):  docker compose up -d
#   With localai stack:        docker compose -f docker-compose.yml -f docker-compose.override.yml up -d

services:
  walltrack:
    build: .
    container_name: walltrack-app
    ports:
      - "${PORT:-8000}:8000"      # FastAPI
      - "${UI_PORT:-7860}:7860"   # Gradio Dashboard
    env_file: .env
    volumes:
      - ./src:/app/src:ro         # Hot reload in dev
    restart: unless-stopped

  walltrack-monitor:
    build: .
    container_name: walltrack-monitor
    command: ["python", "-m", "walltrack.scheduler.jobs"]
    env_file: .env
    depends_on:
      walltrack:
        condition: service_healthy
    restart: unless-stopped
```

**docker-compose.override.yml:**

> **Note:** See `/docker-compose.override.yml` for localai stack integration.

This file connects WallTrack to the external `localai_default` network where shared infrastructure runs:
- **Neo4j** (`localai-neo4j-1`) - Graph database for wallet clusters
- **PostgreSQL** (`localai-postgres-1`) - Transactional data via Supabase
- **Redis** (`localai-redis-1`) - Optional job queue
- **MinIO** (`localai-minio-1`) - Optional S3 storage

```yaml
services:
  walltrack:
    networks:
      - walltrack_network
      - localai_default    # Connect to shared infrastructure
    environment:
      - NEO4J_URI=bolt://localai-neo4j-1:7687
      - DATABASE_URL=postgresql://postgres:postgres@localai-postgres-1:5432/postgres
      - REDIS_HOST=localai-redis-1

networks:
  localai_default:
    external: true
```

**tests/conftest.py:**
```python
"""Shared pytest fixtures."""

import pytest
from unittest.mock import AsyncMock

from walltrack.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    """Provide test settings."""
    return Settings(
        debug=True,
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test_password",
        supabase_url="https://test.supabase.co",
        supabase_key="test_key",
        helius_api_key="test_helius_key",
        helius_webhook_secret="test_webhook_secret",
        trading_wallet_private_key="test_private_key",
    )


@pytest.fixture
def mock_neo4j_client() -> AsyncMock:
    """Provide mock Neo4j client."""
    return AsyncMock()


@pytest.fixture
def mock_supabase_client() -> AsyncMock:
    """Provide mock Supabase client."""
    return AsyncMock()
```

## Implementation Tasks

- [ ] Run `uv init` and configure pyproject.toml
- [ ] Create complete directory structure with all __init__.py files
- [ ] Copy `.env.example` from project root (already created)
- [ ] Create .gitignore
- [ ] Verify `docker-compose.yml` (already created at project root)
- [ ] Verify `docker-compose.override.yml` for localai integration (already created)
- [ ] Create Dockerfile
- [ ] Create src/walltrack/__init__.py
- [ ] Create src/walltrack/main.py
- [ ] Create src/walltrack/core/exceptions.py
- [ ] Create tests/conftest.py
- [ ] Verify ruff lint passes
- [ ] Verify mypy strict passes
- [ ] Verify pytest discovers tests
- [ ] Test Docker build: `docker compose build`
- [ ] Test Docker run with localai: `docker compose -f docker-compose.yml -f docker-compose.override.yml up -d`

## Definition of Done

- [ ] `uv sync` installs all dependencies without errors
- [ ] All directories and __init__.py files exist
- [ ] `ruff check src/` passes with no errors
- [ ] `mypy src/` passes with no errors
- [ ] `pytest --collect-only` discovers test directories
- [ ] Application starts with `uv run uvicorn walltrack.main:app`
- [ ] Docker image builds successfully
- [ ] Container connects to Neo4j and PostgreSQL via localai network
