# Starter Template Evaluation

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
