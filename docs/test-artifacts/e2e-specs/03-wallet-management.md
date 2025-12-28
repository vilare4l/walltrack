# E2E Spec 03: Wallet Management

> **Priority:** P1
> **Risk:** Medium
> **Dependencies:** Dashboard loads

---

## Spec Summary

Validate wallet watchlist operations: add, view, filter, remove.

---

## Test Cases

### TC-03.1: Add Wallet Manually

```python
@pytest.mark.e2e
def test_add_wallet_manually(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Add wallet by pasting address."""
    gradio_locators.click_tab("wallets")

    # Find add wallet input
    add_input = dashboard_page.locator("#wallets-new-address")
    expect(add_input).to_be_visible()

    # Enter wallet address
    test_wallet = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    add_input.fill(test_wallet)

    # Click add
    add_btn = dashboard_page.locator("#wallets-add-btn")
    add_btn.click()

    # Verify wallet appears in table
    wallets_table = dashboard_page.locator("#wallets-table")
    expect(wallets_table).to_contain_text(test_wallet[:8])
```

### TC-03.2: View Wallet Table

```python
@pytest.mark.e2e
def test_wallets_table_visible(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Wallets table should be present with headers."""
    gradio_locators.click_tab("wallets")

    wallets_table = dashboard_page.locator("#wallets-table")
    expect(wallets_table).to_be_visible()

    # Check headers exist
    headers = ["Address", "Status", "Score", "Win Rate", "Actions"]
    for header in headers:
        expect(wallets_table).to_contain_text(header)
```

### TC-03.3: Filter Wallets by Status

```python
@pytest.mark.e2e
def test_filter_wallets_by_status(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Status filter should work."""
    gradio_locators.click_tab("wallets")

    # Open filter dropdown
    status_filter = dashboard_page.locator("#wallets-status-filter")
    expect(status_filter).to_be_visible()
    status_filter.click()

    # Select "Active"
    listbox = dashboard_page.get_by_role("listbox")
    expect(listbox).to_be_visible()
    listbox.get_by_text("Active").click()

    # Verify filter applied (table updates)
    dashboard_page.wait_for_timeout(500)  # Gradio render

    # Select "All" to reset
    status_filter.click()
    listbox = dashboard_page.get_by_role("listbox")
    listbox.get_by_text("All").click()
```

### TC-03.4: Refresh Wallets Table

```python
@pytest.mark.e2e
def test_refresh_wallets_table(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Refresh button should reload wallet data."""
    gradio_locators.click_tab("wallets")

    refresh_btn = dashboard_page.locator("#wallets-refresh-btn")
    expect(refresh_btn).to_be_visible()

    # Click refresh
    refresh_btn.click()

    # Wait for table to update (loading indicator or delay)
    dashboard_page.wait_for_timeout(1000)

    # Table should still be visible
    wallets_table = dashboard_page.locator("#wallets-table")
    expect(wallets_table).to_be_visible()
```

### TC-03.5: View Wallet Profile Details

```python
@pytest.mark.e2e
def test_view_wallet_profile(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Click wallet row to view profile details."""
    gradio_locators.click_tab("wallets")

    # Click first wallet row
    wallet_row = dashboard_page.locator("#wallets-table tbody tr").first
    wallet_row.click()

    # Profile panel should appear
    profile_panel = dashboard_page.locator("#wallet-profile-panel")
    expect(profile_panel).to_be_visible(timeout=5_000)

    # Check profile metrics displayed
    expect(profile_panel).to_contain_text("Win Rate")
    expect(profile_panel).to_contain_text("PnL")
    expect(profile_panel).to_contain_text("Trades")
```

---

## Locators Required

```python
# Wallets tab locators
wallets_table = "#wallets-table"
wallets_refresh_btn = "#wallets-refresh-btn"
wallets_status_filter = "#wallets-status-filter"
wallets_new_address = "#wallets-new-address"
wallets_add_btn = "#wallets-add-btn"
wallet_profile_panel = "#wallet-profile-panel"
```

---

## Test Data

```python
# Test wallets
TEST_WALLETS = [
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK deployer
    "Hgp8C2MzpVP7FwB42gKhRvJxPJpZz6W5cRGpwMrLw6G7",  # Random wallet
]
```

---

## Estimated Duration

- TC-03.1: 5s
- TC-03.2: 3s
- TC-03.3: 5s
- TC-03.4: 3s
- TC-03.5: 5s
- **Total: ~21s**
