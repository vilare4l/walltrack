# E2E Spec 05: Signal Scoring (Epic 14 Simplified)

> **Priority:** P0
> **Risk:** Critical
> **Dependencies:** Webhook received, Wallet in watchlist

---

## Spec Summary

Validate the simplified 2-component signal scoring system.

---

## Epic 14 Scoring Changes

- **Before:** 4-factor weighted system (30+ params)
- **After:** 2-component model (8 params)

```
Final Score = Wallet Score × Cluster Boost
Where:
- Wallet Score = win_rate × 0.6 + pnl_norm × 0.4 (× leader_bonus if leader)
- Cluster Boost = 1.0x to 1.8x
- Threshold = 0.65 (single threshold)
```

---

## Test Cases

### TC-05.1: View Signals Table

```python
@pytest.mark.e2e
def test_signals_table_visible(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Signals table should display recent signals."""
    gradio_locators.click_tab("signals")

    signals_table = dashboard_page.locator("#signals-table")
    expect(signals_table).to_be_visible()

    # Check headers
    headers = ["Time", "Wallet", "Token", "Score", "Boost", "Status"]
    for header in headers:
        expect(signals_table).to_contain_text(header)
```

### TC-05.2: View Signal Score Breakdown

```python
@pytest.mark.e2e
def test_signal_score_breakdown(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Click signal to view score breakdown."""
    gradio_locators.click_tab("signals")

    # Click first signal row
    signal_row = dashboard_page.locator("#signals-table tbody tr").first
    signal_row.click()

    # Wait for details panel
    details = dashboard_page.locator("#signal-details")
    expect(details).to_be_visible(timeout=5_000)

    # Verify Epic 14 simplified breakdown
    expect(details).to_contain_text("Wallet Score")
    expect(details).to_contain_text("Cluster Boost")
    expect(details).to_contain_text("Final Score")
    expect(details).to_contain_text("Token Safe")
```

### TC-05.3: Signal Trade Decision Display

```python
@pytest.mark.e2e
def test_signal_trade_decision(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Verify TRADE/NO TRADE decision displayed."""
    gradio_locators.click_tab("signals")

    # Find signals with different outcomes
    signals_table = dashboard_page.locator("#signals-table")

    # Check for TRADE or NO TRADE indicators
    # At least one should exist
    trade_indicator = signals_table.locator("text=TRADE")
    expect(trade_indicator.first).to_be_visible(timeout=5_000)
```

### TC-05.4: Refresh Signals

```python
@pytest.mark.e2e
def test_refresh_signals(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Refresh button should reload signals."""
    gradio_locators.click_tab("signals")

    refresh_btn = dashboard_page.locator("#signals-refresh-btn")
    expect(refresh_btn).to_be_visible()

    # Click refresh
    refresh_btn.click()

    # Wait for table update
    dashboard_page.wait_for_timeout(1000)

    signals_table = dashboard_page.locator("#signals-table")
    expect(signals_table).to_be_visible()
```

### TC-05.5: Filter Signals by Status

```python
@pytest.mark.e2e
def test_filter_signals_by_status(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter signals by trade decision."""
    gradio_locators.click_tab("signals")

    # Find filter if exists
    filter_dropdown = dashboard_page.locator("#signals-filter")
    if filter_dropdown.is_visible():
        filter_dropdown.click()

        # Select "TRADE" only
        listbox = dashboard_page.get_by_role("listbox")
        listbox.get_by_text("TRADE").click()

        dashboard_page.wait_for_timeout(500)
```

---

## API Integration Test

### TC-05.6: Webhook Triggers Signal Score

```python
@pytest.mark.e2e
async def test_webhook_triggers_signal(
    dashboard_page: Page,
    gradio_locators: GradioLocators,
    api_client: httpx.AsyncClient
) -> None:
    """Sending webhook creates scored signal."""
    # Initial signal count
    gradio_locators.click_tab("signals")
    initial_count = len(
        dashboard_page.locator("#signals-table tbody tr").all()
    )

    # Send webhook
    webhook_payload = {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"test_sig_{uuid4()}",
            "type": "SWAP",
            "feePayer": "WatchlistedWalletAddress",
            "tokenTransfers": [{
                "mint": "ValidTokenMint",
                "toUserAccount": "WatchlistedWalletAddress",
                "tokenAmount": 1000000,
            }]
        }]
    }

    response = await api_client.post(
        "/api/webhooks/helius",
        json=webhook_payload
    )
    assert response.status_code == 200

    # Refresh and verify new signal
    dashboard_page.locator("#signals-refresh-btn").click()
    dashboard_page.wait_for_timeout(2000)

    new_count = len(
        dashboard_page.locator("#signals-table tbody tr").all()
    )
    assert new_count > initial_count
```

---

## Locators Required

```python
# Signals tab locators
signals_table = "#signals-table"
signals_refresh_btn = "#signals-refresh-btn"
signals_filter = "#signals-filter"
signal_details = "#signal-details"
```

---

## Test Data Requirements

- Watchlisted wallet with recent transactions
- Mix of TRADE and NO TRADE signals
- At least one token-rejected signal (honeypot test)

---

## Estimated Duration

- TC-05.1 to 05.5: 20s
- TC-05.6: 10s (API call)
- **Total: ~30s**
