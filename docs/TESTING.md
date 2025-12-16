# WallTrack Testing Guide

This document defines testing conventions, patterns, and requirements for WallTrack.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Factories](#factories)
- [Gradio UI Testing](#gradio-ui-testing)
- [Conventions](#conventions)

---

## Quick Start

```bash
# Install dependencies
uv sync --extra test --extra dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=walltrack --cov-report=html

# Run specific test levels
uv run pytest -m unit          # Fast, no external deps
uv run pytest -m integration   # Requires DB
uv run pytest -m e2e           # Full system
```

---

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── factories/               # Test data factories
│   ├── wallet.py
│   ├── signal.py
│   └── trade.py
├── unit/                    # Fast, isolated tests
│   └── core/
│       ├── test_scoring.py
│       ├── test_circuit_breaker.py
│       └── test_exit_manager.py
├── integration/             # DB/service tests
│   ├── neo4j/
│   │   └── test_wallet_queries.py
│   └── supabase/
│       └── test_trade_repo.py
└── e2e/                     # Full system tests
    └── gradio/
        └── test_dashboard_flows.py
```

---

## Running Tests

### By Level

```bash
# Unit tests only (fast feedback)
uv run pytest -m unit

# Integration tests (requires Docker services)
uv run pytest -m integration

# E2E tests (requires full system)
uv run pytest -m e2e

# Skip slow tests
uv run pytest -m "not slow"
```

### With Coverage

```bash
# Check coverage meets 80% threshold
uv run pytest --cov=walltrack --cov-fail-under=80

# Generate HTML report
uv run pytest --cov=walltrack --cov-report=html
open htmlcov/index.html
```

### CI Pipeline

```bash
# Full CI check
uv run ruff check src/
uv run mypy src/walltrack --strict
uv run pytest --cov=walltrack --cov-fail-under=80
```

---

## Factories

We use `factory_boy` for test data generation. All factories are in `tests/factories/`.

### Basic Usage

```python
from tests.factories import WalletFactory, SignalFactory, TradeFactory

# Create a basic wallet
wallet = WalletFactory()

# Create with specific attributes
wallet = WalletFactory(score=0.95, status=WalletStatus.ACTIVE)

# Use traits for common scenarios
wallet = WalletFactory(high_performer=True)      # High score + metrics
wallet = WalletFactory(blacklisted=True)         # Blacklisted status
wallet = WalletFactory(with_metrics=True)        # Include metrics

# Create signals
signal = SignalFactory(high_score=True)          # Above 0.7 threshold
signal = SignalFactory(low_score=True)           # Below threshold
signal = SignalFactory(executed=True)            # Processed with trade

# Create trades
trade = TradeFactory(filled_win=True)            # Winning trade
trade = TradeFactory(filled_loss=True)           # Losing trade
trade = TradeFactory(with_moonbag=True)          # Has moonbag remaining
```

### Batch Creation

```python
# Create multiple instances
wallets = WalletFactory.create_batch(10)
wallets = WalletFactory.create_batch(5, high_performer=True)
```

---

## Gradio UI Testing

### elem_id Convention (CRITICAL)

All Gradio components MUST have `elem_id` for Playwright selectors.

**Format:** `{section}-{component}-{action}`

**Examples:**
```python
# In ui/components/config_panel.py
gr.Slider(
    label="Minimum Score Threshold",
    elem_id="config-score-slider",      # ✅ Required
    value=0.7
)

gr.Button(
    "Save Configuration",
    elem_id="config-save-btn"           # ✅ Required
)

gr.Dropdown(
    label="Exit Strategy",
    elem_id="config-exit-dropdown",     # ✅ Required
    choices=["conservative", "balanced", "aggressive"]
)
```

### Section Prefixes

| Section | Prefix | Example |
|---------|--------|---------|
| Configuration | `config-` | `config-score-slider` |
| Positions | `positions-` | `positions-table` |
| Trades | `trades-` | `trades-history-table` |
| Alerts | `alerts-` | `alerts-dismiss-btn` |
| Wallets | `wallets-` | `wallets-add-input` |
| Analytics | `analytics-` | `analytics-pnl-chart` |
| Backtest | `backtest-` | `backtest-run-btn` |

### Playwright Test Example

```python
# tests/e2e/gradio/test_config_panel.py
import pytest
from playwright.async_api import Page, expect

@pytest.mark.e2e
async def test_config_save_updates_threshold(page: Page):
    """Test that saving config updates the score threshold."""
    await page.goto("http://localhost:7860")

    # Use elem_id selectors (stable)
    slider = page.locator("#config-score-slider input")
    save_btn = page.locator("#config-save-btn")

    # Interact
    await slider.fill("0.8")
    await save_btn.click()

    # Assert
    await expect(page.locator(".toast-success")).to_be_visible()
```

### Common Gradio Component elem_ids

```python
# Text Input
gr.Textbox(label="Wallet Address", elem_id="wallets-address-input")

# Slider
gr.Slider(label="Score", elem_id="config-score-slider", minimum=0, maximum=1)

# Dropdown
gr.Dropdown(label="Strategy", elem_id="config-strategy-dropdown")

# Button
gr.Button("Save", elem_id="config-save-btn")
gr.Button("Refresh", elem_id="positions-refresh-btn")

# Table/Dataframe
gr.Dataframe(elem_id="positions-table")
gr.Dataframe(elem_id="trades-history-table")

# Checkbox
gr.Checkbox(label="Enable", elem_id="config-enable-checkbox")

# Radio
gr.Radio(label="Mode", elem_id="config-mode-radio")

# Plot
gr.Plot(elem_id="analytics-pnl-chart")
```

---

## Conventions

### Test Naming

```
test_{unit_under_test}_{scenario}_{expected_outcome}
```

**Examples:**
```python
def test_calculate_signal_score_with_high_win_rate_returns_above_threshold():
    ...

def test_circuit_breaker_after_5_failures_opens():
    ...

def test_webhook_without_hmac_rejects_with_401():
    ...
```

### Test ID Format

```
{EPIC}.{STORY}-{LEVEL}-{SEQ}
```

**Examples:**
- `1.3-UNIT-001` (Epic 1, Story 3, Unit test #1)
- `3.2-INT-005` (Epic 3, Story 2, Integration test #5)
- `6.1-E2E-001` (Epic 6, Story 1, E2E test #1)

### Markers

```python
@pytest.mark.unit
def test_pure_function():
    """Fast, no external dependencies."""
    ...

@pytest.mark.integration
async def test_database_query():
    """Requires DB connection."""
    ...

@pytest.mark.e2e
async def test_user_flow():
    """Full system test."""
    ...

@pytest.mark.slow
def test_performance_benchmark():
    """Takes >10s, skip with -m 'not slow'."""
    ...
```

### Async Tests

```python
import pytest

@pytest.mark.unit
async def test_async_function():
    """pytest-asyncio handles async automatically."""
    result = await some_async_function()
    assert result is not None
```

### Fixtures

```python
# Use factory fixtures
def test_wallet_score(wallet_factory):
    wallet = wallet_factory(score=0.9)
    assert wallet.score >= 0.7

# Use mock fixtures
def test_helius_integration(mock_helius_client):
    mock_helius_client.verify_signature.return_value = True
    # Test code...

# Use DB fixtures (integration only)
@pytest.mark.integration
async def test_wallet_query(neo4j_session):
    result = await neo4j_session.run("MATCH (w:Wallet) RETURN w")
    # Assertions...
```

---

## Quality Gates

### Pre-Commit

- [ ] All unit tests pass
- [ ] Coverage >= 80%
- [ ] mypy strict: 0 errors
- [ ] ruff: 0 violations

### Pre-Merge (PR)

- [ ] All unit + integration tests pass
- [ ] Coverage >= 80%
- [ ] No new security issues (bandit)

### Pre-Release

- [ ] All tests pass (unit + integration + E2E)
- [ ] P0 tests: 100% pass rate
- [ ] P1 tests: >= 95% pass rate
- [ ] No high-risk items unmitigated

---

## Troubleshooting

### Tests Can't Find Modules

```bash
# Ensure package is installed in dev mode
uv sync --extra test
```

### Neo4j Connection Fails

```bash
# Start Neo4j with Docker
docker-compose up -d neo4j

# Or skip integration tests
uv run pytest -m "not integration"
```

### Gradio Tests Timeout

```python
# Increase timeout for slow UI
@pytest.mark.timeout(30)
async def test_slow_ui_operation():
    ...
```

### Flaky Async Tests

```python
# Use explicit waits instead of sleep
await page.wait_for_selector("#element-id")
await expect(locator).to_be_visible(timeout=5000)
```

---

## References

- [Test Design Document](./test-design-system.md)
- [Architecture Document](./architecture.md)
- [pytest Documentation](https://docs.pytest.org/)
- [Playwright Python](https://playwright.dev/python/)
- [factory_boy](https://factoryboy.readthedocs.io/)
