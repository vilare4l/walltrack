# WallTrack E2E Tests

End-to-end tests for the WallTrack Gradio dashboard using Playwright.

## Setup

### Prerequisites

1. **Install test dependencies:**
   ```bash
   uv sync --extra test
   ```

2. **Install Playwright browsers:**
   ```bash
   uv run playwright install chromium
   ```

## Running Tests

### Start the Dashboard

Before running E2E tests, start the Gradio dashboard:

```bash
uv run python -m walltrack.ui.dashboard
```

The dashboard runs on `http://localhost:7865` by default (configured via `UI_PORT` in `.env`).

### Run E2E Tests

```bash
# Headless mode (CI)
uv run pytest tests/e2e -m e2e

# Headed mode (visual debugging)
HEADED=1 uv run pytest tests/e2e -m e2e

# Slow motion (debugging)
SLOW_MO=500 uv run pytest tests/e2e -m e2e

# Single test
uv run pytest tests/e2e/gradio/test_dashboard.py::TestDashboardLoads::test_dashboard_title_visible -m e2e
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRADIO_HOST` | `localhost` | Dashboard host |
| `GRADIO_PORT` | `7865` | Dashboard port (matches UI_PORT in .env) |
| `HEADED` | `0` | Set to `1` for visual mode |
| `SLOW_MO` | `0` | Slow motion delay in ms |

## Test Structure

```
tests/e2e/
├── conftest.py              # Playwright fixtures for Gradio
├── README.md                # This file
└── gradio/
    ├── __init__.py
    └── test_dashboard.py    # Dashboard E2E tests
```

## Fixtures

### `dashboard_page`

Navigates to the dashboard and waits for it to load:

```python
def test_example(dashboard_page):
    dashboard_page.locator("#tab-wallets").click()
```

### `gradio_locators`

Helper class for common element interactions:

```python
def test_navigation(dashboard_page, gradio_locators):
    gradio_locators.click_tab("wallets")
    gradio_locators.wallets_refresh_btn.click()
```

## Selector Strategy

All interactive Gradio components use `elem_id` attributes following the convention:

```
{section}-{component}-{action}

Examples:
- #tab-wallets           (main tab)
- #wallets-refresh-btn   (button in wallets section)
- #config-wallet-weight  (slider in config section)
- #positions-table       (table in positions section)
```

## Writing New Tests

1. **Use `@pytest.mark.e2e`** to mark E2E tests:
   ```python
   import pytest

   pytestmark = pytest.mark.e2e
   ```

2. **Use `expect()` for assertions:**
   ```python
   from playwright.sync_api import expect

   def test_button_visible(dashboard_page, gradio_locators):
       gradio_locators.click_tab("wallets")
       expect(gradio_locators.wallets_refresh_btn).to_be_visible()
   ```

3. **Add new locators to `GradioLocators`** class in `conftest.py`

## Troubleshooting

### Tests fail with "Element not found"

1. Check the dashboard is running on the correct port
2. Verify the element has an `elem_id` attribute
3. Run in headed mode to see what's happening

### Tests are flaky

1. Add explicit waits after tab navigation
2. Use `expect()` with built-in retries
3. Increase timeout if Gradio is slow to load

### Browser installation issues

```bash
# Reinstall browsers
uv run playwright install --force chromium
```

## CI Integration

See `.github/workflows/e2e.yml` for CI configuration (to be created in `*ci` workflow).
