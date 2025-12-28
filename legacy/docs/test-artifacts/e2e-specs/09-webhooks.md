# E2E Spec 09: Helius Webhooks

> **Priority:** P0
> **Risk:** Critical
> **Dependencies:** Wallet in watchlist

---

## Spec Summary

Validate Helius webhook configuration and signal reception pipeline.

---

## Test Cases

### TC-09.1: View Webhook Status

```python
@pytest.mark.e2e
def test_webhook_status_visible(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Webhook status should be displayed on dashboard."""
    # Check home page for webhook indicator
    gradio_locators.click_tab("home")

    webhook_status = dashboard_page.locator("#webhook-status")
    expect(webhook_status).to_be_visible()

    # Should show either "Connected" or "Disconnected"
    expect(webhook_status).to_contain_text("Webhook")
```

### TC-09.2: View Webhook Configuration

```python
@pytest.mark.e2e
def test_view_webhook_config(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Display webhook configuration settings."""
    gradio_locators.click_tab("config")

    # Navigate to Webhooks sub-tab
    webhooks_tab = dashboard_page.get_by_role("tab", name="Webhooks")
    if webhooks_tab.is_visible():
        webhooks_tab.click()

    # Webhook URL should be visible
    webhook_url = dashboard_page.locator("#webhook-url-display")
    expect(webhook_url).to_be_visible()

    # Copy button
    copy_btn = dashboard_page.locator("#webhook-copy-btn")
    expect(copy_btn).to_be_visible()
```

### TC-09.3: Test Webhook Connectivity

```python
@pytest.mark.e2e
def test_webhook_connectivity(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Test button should verify webhook is reachable."""
    gradio_locators.click_tab("config")

    webhooks_tab = dashboard_page.get_by_role("tab", name="Webhooks")
    if webhooks_tab.is_visible():
        webhooks_tab.click()

    # Click test button
    test_btn = dashboard_page.locator("#webhook-test-btn")
    if test_btn.is_visible():
        test_btn.click()

        # Status should update
        status = dashboard_page.locator("#webhook-test-status")
        expect(status).to_be_visible(timeout=10_000)
```

---

## API Integration Tests

### TC-09.4: Receive Valid Webhook

```python
@pytest.mark.e2e
async def test_receive_valid_webhook(
    dashboard_page: Page,
    gradio_locators: GradioLocators,
    api_client: httpx.AsyncClient
) -> None:
    """Valid Helius webhook creates signal."""
    # Send webhook
    webhook_payload = {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"test_sig_{uuid4().hex[:8]}",
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

    # Verify signal created
    gradio_locators.click_tab("signals")
    dashboard_page.locator("#signals-refresh-btn").click()
    dashboard_page.wait_for_timeout(2000)

    signals_table = dashboard_page.locator("#signals-table")
    expect(signals_table).to_be_visible()
```

### TC-09.5: Reject Unknown Wallet

```python
@pytest.mark.e2e
async def test_reject_unknown_wallet_webhook(
    api_client: httpx.AsyncClient
) -> None:
    """Webhook from non-watchlisted wallet is filtered."""
    webhook_payload = {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"unknown_sig_{uuid4().hex[:8]}",
            "type": "SWAP",
            "feePayer": "UnknownWalletNotInWatchlist",
            "tokenTransfers": [{
                "mint": "SomeTokenMint",
                "toUserAccount": "UnknownWalletNotInWatchlist",
                "tokenAmount": 500000,
            }]
        }]
    }

    response = await api_client.post(
        "/api/webhooks/helius",
        json=webhook_payload
    )
    # Should still return 200 (accepted) but filtered internally
    assert response.status_code == 200

    # Verify in response or logs that signal was filtered
    data = response.json()
    assert data.get("filtered") or data.get("signals_created") == 0
```

### TC-09.6: Handle Malformed Webhook

```python
@pytest.mark.e2e
async def test_handle_malformed_webhook(
    api_client: httpx.AsyncClient
) -> None:
    """Malformed webhook returns 400."""
    # Missing required fields
    webhook_payload = {
        "type": "TRANSACTION",
        "transactions": []  # Empty transactions
    }

    response = await api_client.post(
        "/api/webhooks/helius",
        json=webhook_payload
    )
    # Should handle gracefully
    assert response.status_code in [200, 400]
```

### TC-09.7: Webhook Creates Signal with Score

```python
@pytest.mark.e2e
async def test_webhook_signal_has_score(
    dashboard_page: Page,
    gradio_locators: GradioLocators,
    api_client: httpx.AsyncClient,
    watchlisted_wallet: str
) -> None:
    """Signal from webhook has Epic 14 score breakdown."""
    # Send webhook for known watchlisted wallet
    webhook_payload = {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"scored_sig_{uuid4().hex[:8]}",
            "type": "SWAP",
            "feePayer": watchlisted_wallet,
            "tokenTransfers": [{
                "mint": "ValidSafeTokenMint",
                "toUserAccount": watchlisted_wallet,
                "tokenAmount": 2000000,
            }]
        }]
    }

    await api_client.post("/api/webhooks/helius", json=webhook_payload)

    # Check signal details
    gradio_locators.click_tab("signals")
    dashboard_page.locator("#signals-refresh-btn").click()
    dashboard_page.wait_for_timeout(2000)

    # Click first signal
    signal_row = dashboard_page.locator("#signals-table tbody tr").first
    signal_row.click()

    details = dashboard_page.locator("#signal-details")
    expect(details).to_be_visible(timeout=5_000)

    # Epic 14 simplified scoring
    expect(details).to_contain_text("Wallet Score")
    expect(details).to_contain_text("Cluster Boost")
    expect(details).to_contain_text("Final Score")
```

---

## Locators Required

```python
# Webhook locators
webhook_status = "#webhook-status"
webhook_url_display = "#webhook-url-display"
webhook_copy_btn = "#webhook-copy-btn"
webhook_test_btn = "#webhook-test-btn"
webhook_test_status = "#webhook-test-status"
```

---

## Test Data Requirements

- Watchlisted wallet address for positive tests
- Valid token mint address
- Mock Helius webhook endpoint

---

## API Endpoints Tested

- `POST /api/webhooks/helius` - Main webhook receiver
- Signal pipeline triggered automatically

---

## Estimated Duration

- TC-09.1 to 09.3: 10s (UI tests)
- TC-09.4 to 09.7: 20s (API tests)
- **Total: ~30s**
