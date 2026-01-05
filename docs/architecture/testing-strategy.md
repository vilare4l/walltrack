# Testing Strategy

### Testing Pyramid

```
        ┌─────────────┐
        │     E2E     │  ~10% (Playwright - UI workflows)
        │   (Gradio)  │
        └─────────────┘
      ┌─────────────────┐
      │  Integration    │  ~30% (Real DB + mocked APIs)
      │   (Workers)     │
      └─────────────────┘
    ┌───────────────────────┐
    │    Unit Tests         │  ~60% (Isolated logic + mocks)
    │  (Services/Repos)     │
    └───────────────────────┘
```

### 1. Unit Tests (60% coverage target)

**Scope:** Isolated functions, services, repositories with mocked dependencies

**Location:** `tests/unit/`

**Examples:**
```python
# tests/unit/services/test_token_analyzer.py
@pytest.mark.asyncio
async def test_calculate_safety_score_safe_token():
    analyzer = TokenAnalyzer()

    rug_data = {
        "isHoneypot": False,
        "hasMintAuthority": False,
        "holderCount": 500
    }
    dex_data = {
        "liquidity": {"usd": 75000},
        "createdAt": (datetime.now() - timedelta(days=2)).isoformat()
    }

    score = analyzer._calculate_safety_score(rug_data, dex_data)

    assert score >= 0.75  # Safe token
```

**Key Test Patterns:**
- Mock external APIs (Helius, Jupiter, RugCheck)
- Test business logic in isolation
- Fast execution (<1s per test)

### 2. Integration Tests (30% coverage target)

**Scope:** Workers + Database + Mocked External APIs

**Location:** `tests/integration/`

**Examples:**
```python
# tests/integration/workers/test_signal_processor.py
@pytest.mark.asyncio
async def test_signal_processor_creates_position_for_safe_token(db_session):
    # Setup: Insert wallet + signal + safe token
    wallet = await wallet_repo.create({
        "address": "test_wallet_123",
        "mode": "simulation",
        "is_active": True
    })

    token = await token_repo.create({
        "address": "test_token_456",
        "safety_score": 0.85,  # Safe
        "last_analyzed_at": datetime.now()
    })

    signal = await signal_repo.create({
        "source_wallet": wallet.address,
        "token_out": token.address,
        "processed": False
    })

    # Execute: Run signal processor worker (1 iteration)
    worker = SignalProcessorWorker()
    await worker._process_batch()

    # Assert: Signal processed + position created
    signal_updated = await signal_repo.get(signal.id)
    assert signal_updated.processed == True

    positions = await position_repo.get_by_wallet(wallet.id)
    assert len(positions) == 1
    assert positions[0].mode == "simulation"
```

**Key Test Patterns:**
- Real database (Supabase test instance or local PG)
- Mock external APIs (httpx_mock)
- Test worker orchestration end-to-end

### 3. E2E Tests (10% coverage target)

**Scope:** Complete user workflows through Gradio UI

**Location:** `tests/e2e/`

**Tool:** Playwright

**CRITICAL:** Run E2E tests separately (not with unit/integration)
```bash
# Run unit + integration
uv run pytest tests/unit tests/integration -v

# Run E2E separately
uv run pytest tests/e2e -v
```

**Examples:**
```python
# tests/e2e/test_watchlist_management.py
def test_add_wallet_to_watchlist(page: Page):
    # Navigate to dashboard
    page.goto("http://localhost:7860")

    # Fill wallet form
    page.fill("#wallet_address", "DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK")
    page.fill("#wallet_label", "Test Wallet")
    page.select_option("#wallet_mode", "simulation")

    # Submit
    page.click("button:has-text('Add Wallet')")

    # Verify success
    expect(page.locator(".success-message")).to_contain_text("Wallet added")

    # Verify wallet appears in list
    expect(page.locator("#wallets_table")).to_contain_text("Test Wallet")
```

### Test Data Management

**Strategy:** Factory pattern + database fixtures

```python
# tests/factories.py
class WalletFactory:
    @staticmethod
    async def create(**overrides):
        defaults = {
            "address": f"wallet_{uuid4().hex[:8]}",
            "label": "Test Wallet",
            "mode": "simulation",
            "is_active": True,
            "capital_allocation_percent": 10
        }
        return await wallet_repo.create({**defaults, **overrides})

# tests/conftest.py
@pytest.fixture
async def db_session():
    """Provide clean database for each test"""
    # Setup: Create tables
    await db.execute_migration("000_helper_functions.sql")
    await db.execute_migration("001_config_table.sql")
    # ... all migrations

    yield db

    # Teardown: Drop tables
    await db.execute("DROP SCHEMA walltrack CASCADE")
```

---
