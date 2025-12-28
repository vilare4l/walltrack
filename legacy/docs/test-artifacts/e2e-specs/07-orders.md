# E2E Spec 07: Order Management

> **Priority:** P0
> **Risk:** Critical
> **Dependencies:** Position exists

---

## Spec Summary

Validate order execution flow: entry, exit, retry, cancel.

---

## Test Cases

### TC-07.1: View Orders List

```python
@pytest.mark.e2e
def test_orders_table_visible(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Orders table should display with correct columns."""
    # Navigate to Orders (may be in Positions tab or separate)
    gradio_locators.click_tab("positions")

    # Look for Orders sub-tab or section
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    orders_table = dashboard_page.locator("#orders-table")
    expect(orders_table).to_be_visible()

    # Check headers
    headers = ["Type", "Token", "Amount", "Status", "Attempts"]
    for header in headers:
        expect(orders_table).to_contain_text(header)
```

### TC-07.2: Filter Orders by Status

```python
@pytest.mark.e2e
def test_filter_orders_by_status(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter orders by execution status."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    # Find status filter
    status_filter = dashboard_page.locator("#orders-status-filter")
    if status_filter.is_visible():
        status_filter.click()

        listbox = dashboard_page.get_by_role("listbox")
        listbox.get_by_text("Filled").click()

        dashboard_page.wait_for_timeout(500)
```

### TC-07.3: Filter Orders by Type

```python
@pytest.mark.e2e
def test_filter_orders_by_type(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter orders by entry/exit type."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    # Find type filter
    type_filter = dashboard_page.locator("#orders-type-filter")
    if type_filter.is_visible():
        type_filter.click()

        listbox = dashboard_page.get_by_role("listbox")
        listbox.get_by_text("Entry").click()

        dashboard_page.wait_for_timeout(500)
```

### TC-07.4: View Order Details

```python
@pytest.mark.e2e
def test_view_order_details(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Click order to view full details."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    # Click first order
    order_row = dashboard_page.locator("#orders-table tbody tr").first
    order_row.click()

    # Details panel should appear
    details = dashboard_page.locator("#order-details")
    expect(details).to_be_visible(timeout=5_000)

    # Check content
    expect(details).to_contain_text("Token")
    expect(details).to_contain_text("Amount")
    expect(details).to_contain_text("Status")
    expect(details).to_contain_text("Created")
```

### TC-07.5: Retry Failed Order

```python
@pytest.mark.e2e
def test_retry_failed_order(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Retry button should be available for failed orders."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    # Filter to failed orders
    status_filter = dashboard_page.locator("#orders-status-filter")
    if status_filter.is_visible():
        status_filter.click()
        listbox = dashboard_page.get_by_role("listbox")
        listbox.get_by_text("Failed").click()
        dashboard_page.wait_for_timeout(500)

    # Find failed order with retry button
    failed_order = dashboard_page.locator("#orders-table tbody tr").first
    if failed_order.is_visible():
        failed_order.click()

        retry_btn = dashboard_page.locator("#order-retry-btn")
        if retry_btn.is_visible():
            retry_btn.click()

            # Verify status changes
            dashboard_page.wait_for_timeout(1000)
            expect(dashboard_page.locator("#order-status")).to_contain_text("Pending")
```

### TC-07.6: Cancel Pending Order

```python
@pytest.mark.e2e
def test_cancel_pending_order(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Cancel button should work for pending orders."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    # Filter to pending orders
    status_filter = dashboard_page.locator("#orders-status-filter")
    if status_filter.is_visible():
        status_filter.click()
        listbox = dashboard_page.get_by_role("listbox")
        listbox.get_by_text("Pending").click()
        dashboard_page.wait_for_timeout(500)

    # Find pending order
    pending_order = dashboard_page.locator("#orders-table tbody tr").first
    if pending_order.is_visible():
        pending_order.click()

        cancel_btn = dashboard_page.locator("#order-cancel-btn")
        if cancel_btn.is_visible():
            cancel_btn.click()

            # Confirm dialog
            confirm = dashboard_page.locator("#confirm-cancel")
            if confirm.is_visible():
                confirm.click()

            # Verify status changes
            dashboard_page.wait_for_timeout(1000)
            expect(dashboard_page.locator("#order-status")).to_contain_text("Cancelled")
```

### TC-07.7: View Order Stats

```python
@pytest.mark.e2e
def test_view_order_stats(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Order statistics panel shows health metrics."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    # Look for stats panel
    stats_panel = dashboard_page.locator("#order-stats")
    if stats_panel.is_visible():
        expect(stats_panel).to_contain_text("Total")
        expect(stats_panel).to_contain_text("Pending")
        expect(stats_panel).to_contain_text("Retry")
```

---

## Simulation Mode Indicator

### TC-07.8: Orders Show Simulation Flag

```python
@pytest.mark.e2e
def test_orders_show_simulation_flag(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Simulated orders should be marked."""
    # Navigate to Orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    orders_table = dashboard_page.locator("#orders-table")

    # Check for simulation indicator (icon or column)
    # This verifies Epic 14 simulation mode is visible
    sim_indicator = orders_table.locator(".simulation-indicator, text=SIM")
    # At least one simulated order should exist in test env
```

---

## Locators Required

```python
# Orders locators
orders_table = "#orders-table"
orders_status_filter = "#orders-status-filter"
orders_type_filter = "#orders-type-filter"
order_details = "#order-details"
order_status = "#order-status"
order_retry_btn = "#order-retry-btn"
order_cancel_btn = "#order-cancel-btn"
confirm_cancel = "#confirm-cancel"
order_stats = "#order-stats"
```

---

## Test Data Requirements

- Mix of order statuses: pending, filled, failed, cancelled
- At least one retryable failed order (attempts < max)
- Orders with is_simulated=true in test environment

---

## Estimated Duration

- TC-07.1 to 07.8: ~30s total
- **Total: ~30s**
