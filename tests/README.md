# WallTrack Test Suite

Production-ready test infrastructure for WallTrack using **pytest** and **Playwright**.

## Quick Start

```bash
# Install test dependencies
uv sync --group test

# Install Playwright browsers (first time only)
uv run playwright install

# Run all tests
uv run pytest

# Run only E2E tests
uv run pytest -m e2e

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/e2e/test_example.py -v
```

## Directory Structure

```
tests/
├── conftest.py              # Main fixtures (Playwright, env config)
├── e2e/                     # End-to-end tests (Playwright)
│   └── test_example.py      # Example tests and templates
├── support/                 # Test infrastructure
│   ├── fixtures/            # Reusable test fixtures
│   ├── factories/           # Data factories (Faker + Factory-boy)
│   │   ├── wallet_factory.py
│   │   ├── token_factory.py
│   │   └── signal_factory.py
│   ├── helpers/             # Pure function utilities
│   │   ├── wait_helpers.py
│   │   └── format_helpers.py
│   └── page_objects/        # Page Object Model (when UI is built)
└── README.md                # This file
```

## Test Categories

| Marker | Description | Command |
|--------|-------------|---------|
| `e2e` | End-to-end Playwright tests | `pytest -m e2e` |
| `smoke` | Quick validation tests | `pytest -m smoke` |
| `slow` | Long-running tests | `pytest -m "not slow"` to skip |
| `integration` | DB/service integration | `pytest -m integration` |
| `unit` | Fast unit tests | `pytest -m unit` |

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Test environment
TEST_ENV=local              # local | staging

# URLs (override defaults)
BASE_URL=http://localhost:7860
API_URL=http://localhost:8000
```

### Timeouts (standardized)

| Timeout | Value | Description |
|---------|-------|-------------|
| Action | 15s | click, fill, etc. |
| Navigation | 30s | page.goto |
| Expect | 10s | assertions |
| Test | 60s | overall test |

## Writing Tests

### 1. Use Given-When-Then Format

```python
def test_user_can_login(self, page: Page, base_url: str) -> None:
    """
    GIVEN the app is running
    WHEN I enter valid credentials
    THEN I am logged in successfully
    """
    page.goto(base_url)
    page.fill("[data-testid='email']", "test@example.com")
    page.click("[data-testid='login-button']")
    expect(page.locator("[data-testid='user-menu']")).to_be_visible()
```

### 2. Use Data Factories

```python
from tests.support.factories import WalletFactory

def test_wallet_display(self) -> None:
    # Generate test data
    wallet = WalletFactory.build(win_rate=0.85)

    # Use specialized factories for specific scenarios
    from tests.support.factories.wallet_factory import HighPerformanceWalletFactory
    high_perf = HighPerformanceWalletFactory.build()
```

### 3. Use Fixtures

```python
@pytest.fixture
def authenticated_page(page: Page, base_url: str) -> Page:
    """Page fixture with logged-in user."""
    page.goto(f"{base_url}/login")
    page.fill("[data-testid='email']", "test@example.com")
    page.fill("[data-testid='password']", "password123")
    page.click("[data-testid='login-button']")
    return page
```

### 4. Selector Strategy

Always use `data-testid` attributes:

```python
# Good
page.locator("[data-testid='submit-button']")

# Avoid
page.locator(".btn-primary")  # CSS class (brittle)
page.locator("//button[text()='Submit']")  # XPath (fragile)
```

## Data Factories

### Available Factories

| Factory | Description |
|---------|-------------|
| `WalletFactory` | Basic wallet with random data |
| `HighPerformanceWalletFactory` | High win rate wallet |
| `DecayedWalletFactory` | Wallet with decay issues |
| `TokenFactory` | Basic token |
| `NewTokenFactory` | Token < 24h old |
| `MatureTokenFactory` | Token > 7 days old |
| `SignalFactory` | Basic signal |
| `ActionableSignalFactory` | Signal with score >= 0.70 |
| `HighConvictionSignalFactory` | Signal with score >= 0.85 |

### Usage Patterns

```python
# Single item
wallet = WalletFactory.build()

# With overrides
wallet = WalletFactory.build(win_rate=0.95)

# Batch generation
wallets = WalletFactory.build_batch(10)
```

## Helper Functions

### Wait Helpers

```python
from tests.support.helpers import wait_for_condition

# Poll until condition is met
result = wait_for_condition(
    action=lambda: api.get_status(),
    condition=lambda r: r["status"] == "ready",
    timeout_seconds=30.0
)
```

### Format Helpers

```python
from tests.support.helpers import format_sol_amount, truncate_address

format_sol_amount(1.2345)  # "1.2345 SOL"
truncate_address("AbCd...long...WxYz")  # "AbCd...WxYz"
```

## Running in CI

```yaml
# GitHub Actions example
- name: Install dependencies
  run: uv sync --group test

- name: Install Playwright browsers
  run: uv run playwright install --with-deps chromium

- name: Run tests
  run: uv run pytest -m e2e --headed=false
  env:
    TEST_ENV: staging
    CI: true
```

## Debugging

### Run in headed mode (see browser)

```bash
HEADED=true uv run pytest tests/e2e/test_example.py -v
```

### Slow motion (slow down interactions)

Modify `browser_type_launch_args` in `conftest.py`:
```python
"slow_mo": 500  # 500ms between actions
```

### Take screenshots on failure

Screenshots are automatically saved to `test-results/screenshots/` on failure.

### Use Playwright Trace Viewer

```bash
# Generate trace
PWDEBUG=1 uv run pytest tests/e2e/test_example.py

# View trace
uv run playwright show-trace trace.zip
```

## Best Practices

### Do's

- Use `data-testid` for selectors
- Use factories for test data
- Use Given-When-Then format in docstrings
- Run tests in CI on every push
- Keep tests independent (no shared state)
- Clean up after tests

### Don'ts

- Hard-code waits (`time.sleep(3)`)
- Use CSS class selectors
- Share state between tests
- Commit `.env` files
- Skip cleanup on failure

## Knowledge Base References

This test infrastructure follows patterns from:

- **fixture-architecture.md** - Pure function -> fixture composition
- **data-factories.md** - Faker-based factories with auto-cleanup
- **playwright-config.md** - Timeout standards, artifact capture
- **test-quality.md** - Test design principles

---

*Framework scaffolded by TEA (Test Architect) workflow - BMAD Method v6*
