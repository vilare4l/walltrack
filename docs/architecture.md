---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - 'docs/prd.md'
  - 'docs/ux-design-specification.md'
  - 'legacy/project_context.md'
  - 'docs/architecture_legacy.md'
  - 'docs/rebuild-v2-notes.md'
workflowType: 'architecture'
lastStep: 8
status: 'complete'
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-29'
hasProjectContext: true
version: '2.0'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
44 functional requirements across 8 domains covering the complete trading automation lifecycle:
- Token Discovery & Surveillance (3 FRs): Manual discovery, scheduled refresh, dashboard visibility
- Wallet Intelligence (6 FRs): Discovery from tokens, profiling, decay detection, blacklisting
- Cluster Analysis (6 FRs): Graph relationships, synchronized patterns, leader identification
- Signal Processing (6 FRs): Real-time webhooks, filtering, multi-factor scoring
- Position & Order Management (7 FRs): Position creation, sizing, entry/exit orders, execution modes
- Risk Management (4 FRs): Circuit breakers, position limits, automated pause
- Operator Dashboard (9 FRs): Config, monitoring, alerts, performance views
- Trading Wallet (3 FRs): Connection, balance, validation

**Non-Functional Requirements:**
- Performance: <5s signal-to-trade, <500ms webhook processing, <100ms DB queries
- Security: Environment-only secrets, webhook signature validation, no sensitive logging
- Reliability: 95% uptime, 24/7 availability, zero data loss
- Integration: Fallback strategies for all external APIs

**Scale & Complexity:**
- Primary domain: Backend Automation (Fintech/Crypto Trading)
- Complexity level: HIGH (capital at risk, real-time requirements)
- Target scale: Personal system (single operator)
- Estimated architectural components: 8-10 core modules (simplified from V1's 19+)

### Technical Constraints & Dependencies

| Constraint | Specification |
|------------|---------------|
| Private Key Storage | Environment variables only, never in code or logs |
| Webhook Security | Helius HMAC signature verification required |
| External APIs | Helius, Jupiter, DexScreener, Solana RPC (all with fallbacks) |
| Dual Database | Neo4j (relationships) + Supabase (metrics, config) |
| Rebuild Context | V2 simplification - clear boundaries between services/ and core/ |

### Cross-Cutting Concerns Identified

1. **Async Pipeline** - All components must be non-blocking (httpx, async Neo4j driver)
2. **Error Handling** - Custom exceptions hierarchy, tenacity retry on external calls
3. **Logging & Observability** - structlog with bound context, no sensitive data
4. **Configuration Management** - Static (env) + Dynamic (Supabase table)
5. **API Abstraction** - BaseAPIClient with circuit breaker for all external services
6. **Validation Step-by-Step** - Each feature validated (UI + E2E test) before next

### Legacy Code Analysis

**Patterns to preserve from V1:**

| Pattern | Source | Description |
|---------|--------|-------------|
| BaseAPIClient | `legacy/src/walltrack/services/base.py` | httpx async + circuit breaker (5 failures → 30s) + exponential retry |
| Exception Hierarchy | `legacy/src/walltrack/core/exceptions.py` | WallTrackError base + 11 specific exceptions |
| DrawdownCircuitBreaker | `legacy/src/walltrack/core/risk/circuit_breaker.py` | Peak tracking + Supabase persistence + manual reset |
| Data Layer Structure | `legacy/src/walltrack/data/` | models/ + neo4j/ + supabase/ separation |

**Anti-patterns to avoid (V1 problems):**

| Problem | Impact | V2 Solution |
|---------|--------|-------------|
| 70+ files in services/ | Confusion, duplication | services/ = 4 API clients ONLY |
| Duplicate modules (scoring, risk, cluster) | Inconsistent behavior | Single source of truth in core/ |
| Blurred boundaries | "Where does this go?" | Clear layer separation |

## Starter Template Evaluation

### Primary Technology Domain

Backend Automation System (Python) - Autonomous trading system, not a traditional web application.

### Starter Options Considered

| Option | Verdict |
|--------|---------|
| Generic web starters (Next.js, T3) | Not applicable - wrong domain |
| Cookiecutter Python | Too generic, doesn't fit trading system needs |
| FastAPI templates | Partial fit, but missing multi-DB, Gradio components |
| **Custom layered structure** | Best fit - tailored to WallTrack requirements |

### Selected Approach: Custom Layered Python Structure

**Rationale for Selection:**
- Project has specific multi-database needs (Neo4j + Supabase)
- Stack already validated in V1 (keep what works)
- No existing template matches exact requirements
- Rebuild V2 simplifies structure, not stack

**Initialization Command:**

```bash
uv add fastapi uvicorn gradio neo4j supabase httpx pydantic-settings apscheduler structlog tenacity
uv add --dev pytest pytest-asyncio ruff mypy
```

### Architectural Decisions Provided by Structure

**Language & Runtime:**
- Python 3.11+ with strict type hints
- AsyncIO throughout for non-blocking operations

**Package Management:**
- uv for fast, reliable dependency management

**Code Quality:**
- Ruff for linting and formatting
- mypy strict mode for type checking

**Project Organization:**
- Layered architecture: api → core → data/services
- Clear separation of concerns
- Dependency injection friendly

**Deployment:**
- Docker containerization
- VPS deployment (24/7 operation)
- Environment-based configuration (pydantic-settings)

**Note:** Project structure setup should be the first implementation step.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Data layer architecture (Neo4j + Supabase separation of concerns)
- Security patterns (secrets management, webhook validation)
- Async communication patterns (httpx, tenacity)

**Important Decisions (Shape Architecture):**
- Logging strategy (structlog)
- Configuration management (Supabase-based)
- Validation patterns (Pydantic v2)

**Deferred Decisions (Post-MVP):**
- ML-based scoring (XGBoost)
- Advanced monitoring (Prometheus, Grafana)
- Multi-environment configuration

### Data Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Neo4j Driver | `neo4j` official async | Mature, well-documented, native async support |
| Supabase Client | `supabase-py` async | PostgreSQL + RPC integration |
| Data Validation | Pydantic v2 | FastAPI integration, strong typing, automatic serialization |
| DB Sync Strategy | Single Source of Truth | Neo4j owns relationships/clusters, Supabase owns metrics/history |

**Data Ownership:**
- **Neo4j**: Wallet nodes, FUNDED_BY edges, SYNCED_BUY edges, cluster membership
- **Supabase PostgreSQL**: Wallet metrics, trade history, signal logs, performance scores, config

### Security Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Secrets Management | `.env` + pydantic-settings | Simple, sufficient for personal system |
| Webhook Validation | HMAC signature verification | Industry standard, Helius-supported |
| Private Key Storage | Environment variables only | Never in code, logs, or version control |

### API & Communication Patterns

| Decision | Choice | Rationale |
|----------|--------|-----------|
| HTTP Client | `httpx` async | Modern, clean API, native async, timeout/retry friendly |
| Retry Strategy | `tenacity` | Exponential backoff, jitter, configurable conditions |
| Circuit Breaker | Custom implementation | Simple state machine, no external dependency |

**External API Abstraction:**
```
services/
├── base.py          # BaseAPIClient with retry, circuit breaker
├── helius/          # Webhook management (fallback: RPC polling)
├── jupiter/         # Swap execution (fallback: Raydium)
├── dexscreener/     # Token data (fallback: Birdeye)
└── solana/          # RPC client (multi-provider rotation)
```

**Retry Configuration:**
- Max retries: 3
- Exponential backoff: 1s, 2s, 4s
- Jitter: ±500ms
- Circuit breaker threshold: 5 failures → 30s cooldown

### Infrastructure & Deployment

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Logging | `structlog` JSON output | Structured logs, automatic context binding |
| Runtime Config | Supabase `config` table | Dashboard-editable, no restart required |
| Deployment | Docker on VPS | 24/7 operation, easy updates |

**Logging Strategy:**
- JSON format for machine parsing
- Bound context: `wallet_id`, `signal_score`, `trade_id`
- Log levels: DEBUG (dev), INFO (prod), WARNING (alerts)
- No sensitive data in logs (redact private keys, full signatures)

**Configuration Layers:**
1. **Static** (pydantic-settings): DB connections, API keys, secrets
2. **Dynamic** (Supabase table): Scoring thresholds, position sizes, circuit breaker limits

### Decision Impact Analysis

**Implementation Sequence:**
1. Project structure + pydantic-settings configuration
2. Supabase connection + models
3. Neo4j connection + graph queries
4. httpx clients with tenacity retry
5. FastAPI webhook endpoint with HMAC validation
6. structlog integration
7. Gradio dashboard with config management

**Cross-Component Dependencies:**
- All services depend on configuration layer
- API layer depends on data layer
- Core logic depends on services abstraction
- Dashboard depends on all layers for visibility

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Addressed:** 15 areas standardized for AI agent consistency

### Naming Patterns

**Database Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Supabase tables | snake_case plural | `wallets`, `trades`, `signals` |
| Supabase columns | snake_case | `wallet_address`, `created_at` |
| Foreign keys | `{table}_id` | `wallet_id`, `trade_id` |
| Neo4j Labels | PascalCase | `Wallet`, `Token`, `Cluster` |
| Neo4j Relationships | UPPER_SNAKE | `FUNDED_BY`, `SYNCED_BUY` |
| Neo4j Properties | snake_case | `wallet_address`, `discovery_date` |

**Code Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `signal_scorer.py`, `wallet_repo.py` |
| Classes | PascalCase | `WalletProfile`, `SignalScorer` |
| Functions | snake_case | `get_wallet_score`, `process_signal` |
| Variables | snake_case | `wallet_id`, `signal_data` |
| Constants | UPPER_SNAKE | `MAX_RETRIES`, `DEFAULT_THRESHOLD` |

**API Naming Conventions:**

| Element | Convention | Example |
|---------|------------|---------|
| Endpoints | snake_case plural | `/api/wallets`, `/api/signals` |
| Query params | snake_case | `?wallet_id=...&min_score=...` |
| JSON fields | snake_case | `{"wallet_address": "...", "win_rate": 0.78}` |

### Structure Patterns

**V2 Boundary Rules:**
- `services/` = External API clients ONLY (4 services max)
- `core/` = Business logic ONLY
- `data/` = Database access ONLY
- `api/` = FastAPI routes ONLY

**Import Rules:**
- Absolute imports only: `from walltrack.core.scoring import ...`
- Never relative imports

### Format Patterns

**API Response Structure:**

Success:
```json
{"data": {...}, "meta": {"timestamp": "2025-12-29T10:30:00Z"}}
```

Error:
```json
{"error": {"code": "WALLET_NOT_FOUND", "message": "...", "detail": {...}}}
```

**Data Format Rules:**
- Dates: ISO 8601 strings (`2025-12-29T10:30:00Z`)
- Nulls: Explicit (never omit field)
- Booleans: `true`/`false` (JSON), `True`/`False` (Python)

### Communication Patterns

**Logging Rules:**
- Always use structlog with bound context
- Never string formatting in log calls
- Event format: `log.info("event_name", key=value)`

**Event Naming:** `{domain}_{action}` snake_case
- `signal_received`, `position_opened`, `circuit_breaker_triggered`

### Process Patterns

**Error Handling:**
- All exceptions inherit from `WallTrackError`
- Custom exceptions for each error type
- Never bare `raise Exception`

**Retry Pattern:**
- Use `tenacity` for external API calls
- Max 3 retries, exponential backoff (1s, 2s, 4s)
- Circuit breaker after 5 consecutive failures

### Enforcement Guidelines

**All AI Agents MUST:**
1. Follow naming conventions exactly as specified
2. Place code in correct layer (services/ vs core/)
3. Use Pydantic models for all data structures
4. Log with structlog, never print() or f-string logs
5. Use custom exceptions from walltrack.core.exceptions

**Anti-Patterns to Reject:**
- `asyncio.run()` inside async functions
- Relative imports
- Raw dictionaries instead of Pydantic models
- String-formatted log messages
- Generic `Exception` raises

## Project Structure & Boundaries

### Complete Project Directory Structure

```
walltrack/
├── pyproject.toml           # uv dependencies
├── .env.example             # Environment template
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
│       ├── config/              # Configuration
│       │   ├── __init__.py
│       │   └── settings.py      # pydantic-settings
│       │
│       ├── api/                 # FastAPI routes ONLY
│       │   ├── __init__.py
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── health.py    # Health check endpoint
│       │   │   ├── wallets.py   # Wallet API
│       │   │   └── config.py    # Config API
│       │   └── webhooks/
│       │       ├── __init__.py
│       │       └── helius.py    # Helius webhook handler
│       │
│       ├── core/                # Business logic ONLY
│       │   ├── __init__.py
│       │   ├── exceptions.py    # WallTrackError hierarchy
│       │   │
│       │   ├── discovery/       # Token & Wallet Discovery
│       │   │   ├── __init__.py
│       │   │   ├── token_discovery.py
│       │   │   └── wallet_discovery.py
│       │   │
│       │   ├── wallets/         # Wallet Intelligence
│       │   │   ├── __init__.py
│       │   │   ├── profiler.py
│       │   │   ├── decay_detector.py
│       │   │   └── blacklist.py
│       │   │
│       │   ├── cluster/         # Cluster Analysis
│       │   │   ├── __init__.py
│       │   │   ├── analyzer.py
│       │   │   ├── sync_detector.py
│       │   │   └── leader_detection.py
│       │   │
│       │   ├── scoring/         # Signal Scoring
│       │   │   ├── __init__.py
│       │   │   ├── signal_scorer.py
│       │   │   ├── wallet_scorer.py
│       │   │   └── weights.py
│       │   │
│       │   ├── positions/       # Position Management
│       │   │   ├── __init__.py
│       │   │   ├── position_manager.py
│       │   │   └── sizing.py
│       │   │
│       │   ├── execution/       # Order Execution
│       │   │   ├── __init__.py
│       │   │   ├── exit_manager.py
│       │   │   └── trailing_stop.py
│       │   │
│       │   └── risk/            # Risk Management
│       │       ├── __init__.py
│       │       ├── circuit_breaker.py
│       │       └── limits.py
│       │
│       ├── data/                # Database access ONLY
│       │   ├── __init__.py
│       │   │
│       │   ├── models/          # Pydantic models (shared)
│       │   │   ├── __init__.py
│       │   │   ├── wallet.py
│       │   │   ├── signal.py
│       │   │   ├── position.py
│       │   │   ├── trade.py
│       │   │   ├── config.py
│       │   │   └── risk.py
│       │   │
│       │   ├── neo4j/           # Neo4j access
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── queries/
│       │   │       ├── __init__.py
│       │   │       ├── wallet.py
│       │   │       └── cluster.py
│       │   │
│       │   └── supabase/        # Supabase access
│       │       ├── __init__.py
│       │       ├── client.py
│       │       └── repositories/
│       │           ├── __init__.py
│       │           ├── wallet_repo.py
│       │           ├── signal_repo.py
│       │           ├── position_repo.py
│       │           ├── trade_repo.py
│       │           └── config_repo.py
│       │
│       ├── services/            # External APIs ONLY (4 max)
│       │   ├── __init__.py
│       │   ├── base.py          # BaseAPIClient
│       │   │
│       │   ├── helius/          # Helius API
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   ├── webhook_manager.py
│       │   │   └── models.py
│       │   │
│       │   ├── jupiter/         # Jupiter API
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── models.py
│       │   │
│       │   ├── dexscreener/     # DexScreener API
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   └── models.py
│       │   │
│       │   └── solana/          # Solana RPC
│       │       ├── __init__.py
│       │       ├── rpc_client.py
│       │       └── wallet_client.py
│       │
│       ├── ui/                  # Gradio dashboard
│       │   ├── __init__.py
│       │   ├── app.py           # Gradio Blocks main
│       │   ├── pages/
│       │   │   ├── __init__.py
│       │   │   ├── home.py
│       │   │   ├── explorer.py
│       │   │   └── config.py
│       │   └── components/
│       │       ├── __init__.py
│       │       ├── status_bar.py
│       │       └── sidebar.py
│       │
│       └── scheduler/           # APScheduler jobs
│           ├── __init__.py
│           └── jobs.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   │
│   ├── unit/
│   │   ├── core/
│   │   │   ├── test_scoring.py
│   │   │   └── test_risk.py
│   │   └── services/
│   │       └── test_base_client.py
│   │
│   └── integration/
│       ├── test_neo4j.py
│       └── test_supabase.py
│
├── docs/
│   ├── prd.md
│   ├── architecture.md          # This document
│   ├── ux-design-specification.md
│   └── rebuild-v2-notes.md
│
└── legacy/                      # V1 code (reference only)
    └── ...
```

### Architectural Boundaries

**Layer Rules:**
- `api/` → calls `core/` → calls `data/` and `services/`
- Never call `data/` directly from `api/`
- Never import from `ui/` in backend modules
- `services/` = 4 external API clients ONLY

**Data Flow:**
```
Signal → api/webhooks → core/scoring → data/repos → services/jupiter → data/repos
```

**Boundary Diagram:**
```
External Request
     │
     ▼
┌─────────────────┐
│  api/webhooks/  │  ← Helius webhooks (HMAC validated)
│  api/routes/    │  ← Internal API calls
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     core/*      │  ← Business logic (stateless)
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌──────────┐
│ data/ │ │services/ │
│       │ │          │
│Neo4j  │ │Helius    │
│Supa   │ │Jupiter   │
└───────┘ └──────────┘
```

### Requirements to Structure Mapping

| Build Step | Primary Module | Data Layer |
|------------|----------------|------------|
| 1. Discovery tokens | `core/discovery/` | `tokens` (Supabase) |
| 2. Surveillance | `scheduler/`, `services/dexscreener/` | `tokens.last_checked` |
| 3. Discovery wallets | `core/discovery/`, `services/helius/` | `wallets`, `Wallet` (Neo4j) |
| 4. Profiling + Clustering | `core/wallets/`, `core/cluster/` | `wallets`, Neo4j edges |
| 5. Webhooks Helius | `api/webhooks/`, `services/helius/` | `webhooks` |
| 6. Scoring signals | `core/scoring/` | `signals` |
| 7. Positions | `core/positions/` | `positions`, `trades` |
| 8. Orders | `core/execution/`, `services/jupiter/` | `orders` |

### File Count Summary

| Layer | Files | Purpose |
|-------|-------|---------|
| api/ | ~6 | Routes + webhooks |
| core/ | ~15 | Business logic |
| data/ | ~15 | DB access |
| services/ | ~12 | External APIs |
| ui/ | ~8 | Dashboard |
| **Total** | **~56** | vs V1's 100+ |

## Architecture Validation

### Coherence Check

**All decisions work together:**

| Aspect | Status | Details |
|--------|--------|---------|
| Naming Consistency | ✅ | snake_case throughout Python, PascalCase for Neo4j labels |
| Layer Boundaries | ✅ | Clear separation: api → core → data/services |
| Data Flow | ✅ | Request → Webhook → Core → DB → Response |
| Error Handling | ✅ | WallTrackError hierarchy + tenacity retry |
| Logging | ✅ | structlog JSON with bound context |
| Configuration | ✅ | Static (.env) + Dynamic (Supabase) |

**No contradictions found:** All patterns align with the rebuild-v2-notes simplification goals.

### Requirements Coverage

**44 Functional Requirements - All Addressed:**

| Domain | FRs | Covered By |
|--------|-----|------------|
| Token Discovery & Surveillance | 3 | `core/discovery/`, `scheduler/` |
| Wallet Intelligence | 6 | `core/wallets/`, `data/neo4j/` |
| Cluster Analysis | 6 | `core/cluster/`, `data/neo4j/` |
| Signal Processing | 6 | `core/scoring/`, `api/webhooks/` |
| Position & Order Management | 7 | `core/positions/`, `core/execution/` |
| Risk Management | 4 | `core/risk/` |
| Operator Dashboard | 9 | `ui/pages/`, `api/routes/` |
| Trading Wallet | 3 | `services/solana/`, `config/` |

**Non-Functional Requirements - All Addressed:**

| NFR | Solution |
|-----|----------|
| <5s signal-to-trade | Async throughout, no blocking calls |
| <500ms webhook processing | httpx async + circuit breaker |
| <100ms DB queries | Index strategy + Neo4j projections |
| Environment-only secrets | pydantic-settings, never in code |
| Webhook validation | HMAC signature verification |
| 95% uptime | Circuit breaker + fallback APIs |

### Implementation Readiness

**AI Agents can implement consistently:**

1. **Project structure is unambiguous** - Each file has a clear location
2. **Naming conventions are explicit** - No guessing required
3. **Layer rules are enforceable** - Import patterns prevent violations
4. **Patterns have examples** - BaseAPIClient, exceptions, logging all documented
5. **Build sequence is defined** - 8 steps, each validatable

**Critical Files to Create First:**
1. `src/walltrack/config/settings.py` - Everything depends on config
2. `src/walltrack/core/exceptions.py` - Error handling foundation
3. `src/walltrack/services/base.py` - All external calls use this
4. `src/walltrack/data/supabase/client.py` - Data layer foundation

### Validation Summary

| Criterion | Result |
|-----------|--------|
| Coherence | ✅ All decisions compatible |
| Coverage | ✅ 44 FRs + NFRs addressed |
| Readiness | ✅ Implementation-ready |
| Simplification | ✅ ~56 files vs V1's 100+ |

**Architecture Status: VALIDATED** - Ready for implementation phase.

---

## Next Steps

### Implementation Sequence

L'architecture V2 est prête. Voici la séquence de reconstruction recommandée:

| Étape | Module | Validation |
|-------|--------|------------|
| 1 | Project structure + config | `pytest tests/` passes |
| 2 | Supabase connection | Health check endpoint |
| 3 | Neo4j connection | Graph queries work |
| 4 | Token Discovery (manuel) | UI affiche tokens |
| 5 | Token Surveillance | Scheduler fonctionne |
| 6 | Wallet Discovery | Wallets extraits des tokens |
| 7 | Profiling + Clustering | Neo4j edges créés |
| 8 | Webhooks Helius | Signals reçus |
| 9 | Scoring signals | Scores calculés |
| 10 | Positions | Positions créées |
| 11 | Orders | Exécution Jupiter |

### Key V1 → V2 Changes

| Aspect | V1 | V2 |
|--------|----|----|
| services/ files | 70+ | 12 (4 API clients) |
| Total files | 100+ | ~56 |
| Boundary clarity | Blurred | Clear layers |
| Duplicate modules | Yes (scoring, risk, cluster) | No duplication |

### Document References

- **PRD**: `docs/prd.md` - 44 functional requirements
- **UX Spec**: `docs/ux-design-specification.md` - 3 pages + sidebar
- **Rebuild Notes**: `docs/rebuild-v2-notes.md` - V1 problems & V2 goals
- **Legacy Code**: `legacy/src/` - Reference for patterns

### Legacy Reference (Inspiration Only)

> **IMPORTANT:** Le code legacy sert uniquement d'inspiration. V2 repart d'une base vierge.
> Ne pas copier/coller le code V1 - s'en inspirer pour comprendre les décisions.
> Les migrations SQL seront recréées au fil du développement V2.

#### Database Schema (Référence)

**Location:** `legacy/src/walltrack/data/supabase/migrations/`

Concepts à reprendre (pas les fichiers):
- Schema `walltrack` prefix
- Table `config` avec JSONB pour valeurs dynamiques
- Trigger `updated_at` automatique

**Config defaults pour V2:**
```
scoring_weights: {"wallet": 0.30, "cluster": 0.25, "token": 0.25, "context": 0.20}
score_threshold: 0.70
high_conviction_threshold: 0.85
drawdown_threshold_pct: 20.0
max_concurrent_positions: 5
```

#### Gradio Patterns (Référence)

**Location:** `legacy/src/walltrack/ui/dashboard.py`

Patterns validés à s'inspirer:

| Pattern | Concept |
|---------|---------|
| Multipage routing | `demo.route("PageName")` |
| Status bar refresh | `gr.HTML(every=30)` auto-update |
| Contextual sidebar | `gr.Sidebar(position="right")` |

**V1 avait 5 pages → V2 simplifie à 3 pages** (selon UX spec)

---

_Architecture Document V2.0 - Completed 2025-12-29_

