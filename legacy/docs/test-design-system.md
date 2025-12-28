# System-Level Test Design: WallTrack

**Date:** 2025-12-16
**Author:** Christophe (via TEA Agent - Murat)
**Status:** Draft
**Mode:** System-Level (Phase 3 - Pre-Implementation Testability Review)

---

## Executive Summary

This document defines the test architecture and testability requirements for WallTrack before implementation begins. It ensures the architecture supports comprehensive testing across all quality dimensions.

**Project Context:**
- **Domain:** Backend Automation (Crypto Trading)
- **Complexity:** HIGH
- **Stack:** Python 3.11+, FastAPI, Gradio, Neo4j, Supabase, AsyncIO
- **Requirements:** 48 FRs across 8 domains, 23 NFRs

**Testability Verdict:** PASS with CONCERNS (4 items to address in Sprint 0)

---

## Testability Assessment

### Controllability: PASS

| Criterion | Status | Evidence |
|-----------|--------|----------|
| System state controllable | ✅ | FastAPI routes for seeding, Pydantic models for validation |
| External dependencies mockable | ✅ | BaseAPIClient abstraction, dependency injection via FastAPI |
| Error conditions triggerable | ✅ | Circuit breaker pattern, fallback strategies documented |
| Database state resettable | ⚠️ | Dual-DB (Neo4j + Supabase) but cleanup strategy not documented |

**Recommendation:** Implement fixture-based cleanup in `tests/conftest.py` with transaction rollback (Supabase) and node cleanup (Neo4j).

### Observability: PASS

| Criterion | Status | Evidence |
|-----------|--------|----------|
| System state inspectable | ✅ | structlog JSON logging with bound context (wallet_id, signal_score, trade_id) |
| Test results deterministic | ⚠️ | Async pipeline may have timing variations |
| NFRs measurable | ✅ | Explicit thresholds: <5s signal-to-trade, <500ms webhook, <100ms DB |
| Health checks available | ✅ | `/health` endpoint documented |

**Recommendation:** Use `pytest-timeout` and deterministic waits in async tests.

### Reliability: CONCERNS

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Tests isolated | ✅ | Layered architecture enables component isolation |
| Failures reproducible | ⚠️ | External API mocking strategy not specified |
| Components loosely coupled | ✅ | Service abstraction layer, clear boundaries |
| UI testable | ❌ | Gradio components lack `elem_id` for Playwright selectors |

**Critical Concern:** Gradio UI testing requires `elem_id` attributes on all interactive components.

---

## Architecturally Significant Requirements (ASRs)

Requirements that drive architecture AND pose testability challenges:

### High-Priority ASRs (Score >= 6)

| ASR ID | Category | Requirement | Prob | Impact | Score | Test Challenge |
|--------|----------|-------------|------|--------|-------|----------------|
| ASR-001 | PERF | Signal-to-trade latency < 5s | 2 | 3 | **6** | Async timing, external API latency |
| ASR-002 | PERF | Webhook processing < 500ms | 2 | 3 | **6** | Load testing, pipeline efficiency |
| ASR-003 | SEC | Helius HMAC signature validation | 3 | 3 | **9** | Signature generation, rejection paths |
| ASR-004 | SEC | Private keys environment-only | 3 | 3 | **9** | Secret leak detection in logs/errors |
| ASR-005 | DATA | Zero data loss on failures | 2 | 3 | **6** | Transaction atomicity, recovery testing |

### Medium-Priority ASRs (Score 3-5)

| ASR ID | Category | Requirement | Prob | Impact | Score | Test Challenge |
|--------|----------|-------------|------|--------|-------|----------------|
| ASR-006 | TECH | Circuit breaker: 5 failures -> 30s cooldown | 2 | 2 | 4 | State machine transitions |
| ASR-007 | BUS | Configurable exit strategies | 2 | 2 | 4 | Strategy combinations, edge cases |
| ASR-008 | OPS | 95% uptime (24/7) | 2 | 2 | 4 | Health checks, graceful degradation |
| ASR-009 | TECH | Fallback strategies for all external APIs | 2 | 2 | 4 | Fallback trigger conditions |

---

## Test Levels Strategy

### Recommended Distribution

```
┌─────────────────────────────────────────────────────────────┐
│                      E2E (15%)                              │
│   Gradio dashboard flows, webhook-to-trade critical path    │
│   Tools: Playwright                                         │
├─────────────────────────────────────────────────────────────┤
│                  Integration (35%)                          │
│   Neo4j queries, Supabase repos, API client contracts       │
│   Tools: pytest-asyncio, respx (httpx mocking)              │
├─────────────────────────────────────────────────────────────┤
│                      Unit (50%)                             │
│   Scoring logic, circuit breaker, exit strategies, models   │
│   Tools: pytest, factory-boy                                │
└─────────────────────────────────────────────────────────────┘
```

### Rationale

| Level | % | Rationale for WallTrack |
|-------|---|-------------------------|
| **Unit** | 50% | Backend automation = heavy business logic (scoring, exits, risk) |
| **Integration** | 35% | Dual-DB architecture (Neo4j + Supabase) requires interaction testing |
| **E2E** | 15% | Gradio UI is operator dashboard, not customer-facing → targeted flows |

### Test Level Assignment by Module

| Module | Unit | Integration | E2E |
|--------|------|-------------|-----|
| `core/scoring/` | ✅ Primary | - | - |
| `core/risk/` | ✅ Primary | - | - |
| `core/execution/` | ✅ Primary | ⚠️ Trade flow | - |
| `core/feedback/` | ✅ Primary | - | - |
| `data/models/` | ✅ Primary | - | - |
| `data/neo4j/` | - | ✅ Primary | - |
| `data/supabase/` | - | ✅ Primary | - |
| `services/*` | - | ✅ Primary | - |
| `api/routes/webhooks` | - | ✅ Primary | ✅ E2E flow |
| `ui/` | - | - | ✅ Primary |

---

## NFR Testing Approach

### Security (SEC) - P0

**Tools:** pytest, bandit (static analysis)

**Test Scenarios:**
```
tests/unit/api/test_hmac_validation.py
├── test_valid_hmac_signature_passes
├── test_invalid_hmac_signature_rejects_401
├── test_missing_hmac_header_rejects_401
├── test_expired_timestamp_rejects_401 (if applicable)
└── test_replay_attack_prevention

tests/unit/core/test_security.py
├── test_private_key_not_logged_on_error
├── test_wallet_address_redacted_in_logs
└── test_api_keys_not_exposed_in_exceptions
```

**Pass Criteria:**
- 100% security tests green
- 0 secrets detected in logs (validated via log capture in tests)
- bandit scan: 0 high-severity issues

### Performance (PERF) - P1

**Tools:** pytest with timing assertions, k6 (post-MVP for load testing)

**Test Scenarios:**
```
tests/integration/test_performance.py
├── test_webhook_processing_under_500ms
├── test_signal_scoring_under_100ms
├── test_neo4j_query_under_100ms
└── test_supabase_query_under_100ms

tests/e2e/test_critical_path.py
└── test_webhook_to_trade_under_5s
```

**Pass Criteria:**
- p95 webhook processing < 500ms
- p95 signal-to-trade < 5s
- p95 DB queries < 100ms

**Post-MVP (k6):**
```javascript
// tests/load/webhook-load.k6.js
export const options = {
  thresholds: {
    http_req_duration: ['p(95)<500'],
    errors: ['rate<0.01'],
  },
};
```

### Reliability (REL) - P1

**Tools:** pytest-asyncio, mocks for error injection

**Test Scenarios:**
```
tests/unit/core/risk/test_circuit_breaker.py
├── test_circuit_opens_after_5_failures
├── test_circuit_closes_after_30s_cooldown
├── test_half_open_state_on_success
└── test_fallback_triggered_when_open

tests/integration/test_resilience.py
├── test_helius_failure_triggers_rpc_fallback
├── test_jupiter_failure_triggers_raydium_fallback
├── test_dexscreener_failure_triggers_birdeye_fallback
└── test_graceful_degradation_on_db_failure
```

**Pass Criteria:**
- All fallback paths validated
- Circuit breaker state transitions correct
- Graceful degradation (no crashes on external failures)

### Maintainability (MAINT) - P2

**Tools:** pytest-cov, mypy, ruff

**CI Integration:**
```yaml
# .github/workflows/ci.yml
- name: Type check
  run: uv run mypy src/walltrack --strict

- name: Lint
  run: uv run ruff check src/

- name: Test with coverage
  run: uv run pytest --cov=walltrack --cov-fail-under=80
```

**Pass Criteria:**
- Test coverage >= 80%
- mypy strict: 0 errors
- ruff: 0 violations

---

## Test Environment Requirements

### Local Development

| Component | Local Setup |
|-----------|-------------|
| Neo4j | Docker: `neo4j:5-community` |
| Supabase | Docker: `supabase/postgres` or Supabase local CLI |
| External APIs | Mocked via `respx` |

### CI Environment

```yaml
services:
  neo4j:
    image: neo4j:5-community
    env:
      NEO4J_AUTH: neo4j/testpassword
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: testpassword
```

### Test Data Strategy

**Factories (pytest-factoryboy):**
```python
# tests/factories/wallet.py
class WalletFactory(factory.Factory):
    class Meta:
        model = Wallet

    address = factory.Faker('hexify', text='^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
    score = factory.Faker('pyfloat', min_value=0, max_value=1)
    win_rate = factory.Faker('pyfloat', min_value=0, max_value=1)
```

**Fixtures (conftest.py):**
```python
@pytest.fixture
async def neo4j_session(neo4j_driver):
    async with neo4j_driver.session() as session:
        yield session
        # Cleanup: delete test data
        await session.run("MATCH (n:Wallet) WHERE n.test = true DELETE n")

@pytest.fixture
async def supabase_client():
    client = create_client(TEST_URL, TEST_KEY)
    yield client
    # Cleanup handled by transaction rollback
```

---

## Testability Concerns

### TC-001: Gradio UI Missing Test IDs (CRITICAL)

**Problem:** Gradio components don't have `elem_id` attributes, making Playwright selectors fragile.

**Impact:** E2E tests will rely on text/CSS selectors that break on UI changes.

**Recommendation:**
```python
# ui/components/config_panel.py
gr.Slider(
    label="Minimum Score Threshold",
    elem_id="config-min-score",  # ADD THIS
    value=0.7
)
gr.Button(
    "Save Configuration",
    elem_id="config-save-btn"  # ADD THIS
)
```

**Owner:** Dev team during Epic 1
**Deadline:** Before Epic 6 (first E2E tests)

### TC-002: No Test Factory Pattern

**Problem:** No factory pattern documented, leading to verbose test setup.

**Impact:** Test duplication, maintenance burden.

**Recommendation:** Add `factory-boy` to test dependencies, create `tests/factories/`.

### TC-003: Async Cleanup Not Specified

**Problem:** No cleanup strategy for Neo4j/Supabase test data.

**Impact:** Tests may pollute each other, non-deterministic failures.

**Recommendation:** Implement cleanup fixtures in `conftest.py` (see Test Data Strategy above).

### TC-004: External API Mocking Strategy

**Problem:** No mocking strategy for httpx clients documented.

**Impact:** Tests may hit real APIs (slow, flaky, rate-limited).

**Recommendation:** Use `respx` for httpx mocking:
```python
@pytest.fixture
def mock_helius(respx_mock):
    respx_mock.post("https://api.helius.xyz/v0/webhooks").respond(json={"id": "test"})
    yield respx_mock
```

---

## Recommendations for Sprint 0

### 1. Test Dependencies (Add to pyproject.toml)

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "pytest-timeout>=2.2",
    "respx>=0.20",
    "factory-boy>=3.3",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --tb=short"
```

### 2. Test Structure (Align with Architecture)

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── factories/
│   ├── __init__.py
│   ├── wallet.py
│   ├── signal.py
│   └── trade.py
├── unit/
│   ├── __init__.py
│   └── core/
│       ├── test_scoring.py
│       ├── test_circuit_breaker.py
│       ├── test_exit_manager.py
│       └── test_position_manager.py
├── integration/
│   ├── __init__.py
│   ├── neo4j/
│   │   └── test_wallet_queries.py
│   ├── supabase/
│   │   └── test_trade_repo.py
│   └── services/
│       └── test_helius_client.py
└── e2e/
    ├── __init__.py
    └── gradio/
        └── test_dashboard_flows.py
```

### 3. CI Pipeline (Initial)

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      neo4j:
        image: neo4j:5-community
        env:
          NEO4J_AUTH: neo4j/test
        ports:
          - 7687:7687
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --extra test
      - run: uv run pytest --cov=walltrack --cov-fail-under=80
      - run: uv run mypy src/walltrack --strict
      - run: uv run ruff check src/
```

### 4. Gradio elem_id Convention

All Gradio components must include `elem_id` following this pattern:
```
{section}-{component}-{action}

Examples:
- config-score-slider
- config-save-btn
- positions-table
- alerts-dismiss-btn
```

---

## Quality Gate Criteria (Pre-Implementation)

### Gate Decision: PASS with CONCERNS

| Criterion | Status | Details |
|-----------|--------|---------|
| Controllability | ✅ PASS | DI, mockable services |
| Observability | ✅ PASS | structlog, health checks |
| Reliability | ⚠️ CONCERNS | UI testability (TC-001) |
| NFR Testability | ✅ PASS | All NFRs measurable |
| ASR Coverage | ✅ PASS | All critical ASRs testable |

### Conditions for Implementation Start

- [ ] TC-001 acknowledged: Gradio `elem_id` pattern documented
- [ ] TC-002 acknowledged: Factory pattern included in Sprint 0
- [ ] TC-003 acknowledged: Cleanup fixtures planned for conftest.py
- [ ] TC-004 acknowledged: `respx` added to test dependencies

---

## Next Steps

1. **Sprint 0 / Epic 1:** Implement test infrastructure per recommendations
2. **Epic 1-5:** Unit and integration tests written alongside features
3. **Post-Epic 6:** TEA Agent returns for `*framework` workflow (Playwright setup)
4. **Post-Epic 8:** TEA Agent returns for `*automate` + `*trace` (full E2E suite + quality gate)

---

## Appendix

### Test Naming Convention

```
test_{unit_under_test}_{scenario}_{expected_outcome}

Examples:
- test_calculate_signal_score_with_high_win_rate_returns_above_threshold
- test_circuit_breaker_after_5_failures_opens
- test_webhook_without_hmac_rejects_with_401
```

### Test ID Format

```
{EPIC}.{STORY}-{LEVEL}-{SEQ}

Examples:
- 1.3-UNIT-001  (Epic 1, Story 3, Unit test #1)
- 3.2-INT-005   (Epic 3, Story 2, Integration test #5)
- 6.1-E2E-001   (Epic 6, Story 1, E2E test #1)
```

### Knowledge Base References

- `nfr-criteria.md` - NFR validation approach
- `test-levels-framework.md` - Test level selection guidance
- `risk-governance.md` - Risk classification and scoring
- `test-quality.md` - Quality standards

---

**Generated by:** TEA Agent (Murat) - Test Architect
**Workflow:** `*test-design` (System-Level Mode)
**Version:** 4.0 (BMad v6)
