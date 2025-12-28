# E2E Spec 02: Token Discovery

> **Priority:** P1
> **Risk:** High
> **Dependencies:** Dashboard loads

---

## Spec Summary

Validate token discovery flow from address input to wallet extraction.

---

## Test Cases

### TC-02.1: Discover Token by Address

```python
@pytest.mark.e2e
def test_discover_token_by_address(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """User enters token mint and triggers discovery."""
    gradio_locators.click_tab("discovery")

    # Enter valid token
    token_input = dashboard_page.locator("#discovery-token-input")
    token_input.fill("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263")  # BONK

    # Click discover
    discover_btn = dashboard_page.locator("#discovery-discover-btn")
    discover_btn.click()

    # Wait for results
    dashboard_page.wait_for_selector(
        "#discovery-results-table tr",
        timeout=30_000
    )

    # Verify token info displayed
    results = dashboard_page.locator("#discovery-results-table")
    expect(results).to_be_visible()
```

### TC-02.2: Token Discovery Error Handling

```python
@pytest.mark.e2e
def test_token_discovery_invalid_address(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Invalid token address shows error."""
    gradio_locators.click_tab("discovery")

    # Enter invalid token
    token_input = dashboard_page.locator("#discovery-token-input")
    token_input.fill("invalid_token_address_12345")

    # Click discover
    discover_btn = dashboard_page.locator("#discovery-discover-btn")
    discover_btn.click()

    # Verify error message
    # Gradio may show toast or inline error
    error = dashboard_page.locator(".gr-toast-error, #discovery-error")
    expect(error).to_be_visible(timeout=5_000)
```

### TC-02.3: Discover Wallets from Token

```python
@pytest.mark.e2e
def test_discover_wallets_from_token(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Extract profitable wallets from token launch."""
    gradio_locators.click_tab("discovery")

    # Configure discovery params
    early_window = dashboard_page.locator("#discovery-early-window")
    # Default is 30 min, leave as is

    min_profit = dashboard_page.locator("#discovery-min-profit")
    # Default is 50%, leave as is

    # Start wallet discovery (assumes token already entered)
    start_btn = dashboard_page.locator("#discovery-start-btn")
    start_btn.click()

    # Wait for wallet results (may take 30-60s)
    wallet_results = dashboard_page.locator("#discovery-wallet-results tr")
    expect(wallet_results.first).to_be_visible(timeout=60_000)
```

### TC-02.4: Add Discovered Wallet to Watchlist

```python
@pytest.mark.e2e
def test_add_discovered_wallet_to_watchlist(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Select wallet and add to monitoring."""
    # Assumes wallet discovery completed
    wallet_results = dashboard_page.locator("#discovery-wallet-results tr")
    first_wallet = wallet_results.first
    first_wallet.click()

    # Click add to watchlist
    add_btn = dashboard_page.locator("#discovery-add-wallet-btn")
    add_btn.click()

    # Verify confirmation
    confirm = dashboard_page.locator(".gr-toast-success, #discovery-success")
    expect(confirm).to_be_visible(timeout=5_000)

    # Navigate to Wallets tab and verify
    gradio_locators.click_tab("wallets")
    wallets_table = dashboard_page.locator("#wallets-table")
    expect(wallets_table).to_contain_text("...")  # Wallet address partial
```

---

## Test Data

```python
# Valid tokens for discovery
DISCOVERY_TOKENS = [
    {
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK",
        "expected_wallets": True,
    },
]
```

---

## Locators Required

```python
# Discovery tab locators
discovery_token_input = "#discovery-token-input"
discovery_discover_btn = "#discovery-discover-btn"
discovery_results_table = "#discovery-results-table"
discovery_early_window = "#discovery-early-window"
discovery_min_profit = "#discovery-min-profit"
discovery_start_btn = "#discovery-start-btn"
discovery_wallet_results = "#discovery-wallet-results"
discovery_add_wallet_btn = "#discovery-add-wallet-btn"
```

---

## Estimated Duration

- TC-02.1: 10s
- TC-02.2: 5s
- TC-02.3: 60s (API calls)
- TC-02.4: 10s
- **Total: ~85s**
