# E2E Spec 06: Position Management

> **Priority:** P0
> **Risk:** Critical
> **Dependencies:** Signal scored with TRADE decision

---

## Spec Summary

Validate position lifecycle: creation, monitoring, strategy change, exit.

---

## Test Cases

### TC-06.1: View Positions Table

```python
@pytest.mark.e2e
def test_positions_table_visible(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Positions table should display with correct columns."""
    gradio_locators.click_tab("positions")

    positions_table = dashboard_page.locator("#positions-table")
    expect(positions_table).to_be_visible()

    # Check headers
    headers = ["Token", "Entry", "Current", "P&L", "Size", "Strategy", "Status"]
    for header in headers:
        expect(positions_table).to_contain_text(header)
```

### TC-06.2: Filter Active Positions

```python
@pytest.mark.e2e
def test_filter_active_positions(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter to show only active positions."""
    gradio_locators.click_tab("positions")

    # Click Active filter
    active_filter = dashboard_page.locator("#positions-filter-active")
    active_filter.click()

    dashboard_page.wait_for_timeout(500)

    # All visible rows should have "active" status
    rows = dashboard_page.locator("#positions-table tbody tr")
    for row in rows.all()[:5]:  # Check first 5
        expect(row).to_contain_text("active")
```

### TC-06.3: Filter Closed Positions

```python
@pytest.mark.e2e
def test_filter_closed_positions(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter to show only closed positions."""
    gradio_locators.click_tab("positions")

    # Click Closed filter
    closed_filter = dashboard_page.locator("#positions-filter-closed")
    closed_filter.click()

    dashboard_page.wait_for_timeout(500)

    # All visible rows should have "closed" status
    rows = dashboard_page.locator("#positions-table tbody tr")
    for row in rows.all()[:5]:  # Check first 5
        expect(row).to_contain_text("closed")
```

### TC-06.4: Open Position Details Sidebar

```python
@pytest.mark.e2e
def test_open_position_details_sidebar(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Click position to open details sidebar."""
    gradio_locators.click_tab("positions")

    # Click first position row
    position_row = dashboard_page.locator("#positions-table tbody tr").first
    position_row.click()

    # Sidebar should appear
    sidebar = dashboard_page.locator("#position-details-sidebar")
    expect(sidebar).to_be_visible(timeout=5_000)

    # Check sidebar content
    sidebar_content = dashboard_page.locator("#sidebar-content")
    expect(sidebar_content).to_contain_text("Performance")
    expect(sidebar_content).to_contain_text("Entry Price")
    expect(sidebar_content).to_contain_text("P&L")
```

### TC-06.5: Active Position Shows Strategy Levels

```python
@pytest.mark.e2e
def test_active_position_strategy_levels(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Active position sidebar shows TP/SL levels."""
    gradio_locators.click_tab("positions")

    # Click Active filter to ensure we get an active position
    dashboard_page.locator("#positions-filter-active").click()
    dashboard_page.wait_for_timeout(500)

    # Click first active position
    position_row = dashboard_page.locator("#positions-table tbody tr").first
    if position_row.is_visible():
        position_row.click()

        sidebar = dashboard_page.locator("#position-details-sidebar")
        expect(sidebar).to_be_visible(timeout=5_000)

        # Should show strategy section
        expect(sidebar).to_contain_text("Strategy")

        # Strategy button visible for active
        strategy_btn = dashboard_page.locator("#sidebar-strategy-btn")
        expect(strategy_btn).to_be_visible()
```

### TC-06.6: Closed Position Shows Exit Details

```python
@pytest.mark.e2e
def test_closed_position_exit_details(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Closed position sidebar shows exit type."""
    gradio_locators.click_tab("positions")

    # Click Closed filter
    dashboard_page.locator("#positions-filter-closed").click()
    dashboard_page.wait_for_timeout(500)

    # Click first closed position
    position_row = dashboard_page.locator("#positions-table tbody tr").first
    if position_row.is_visible():
        position_row.click()

        sidebar = dashboard_page.locator("#position-details-sidebar")
        expect(sidebar).to_be_visible(timeout=5_000)

        # Should show exit info
        expect(sidebar).to_contain_text("Exit")

        # Strategy button hidden for closed
        strategy_btn = dashboard_page.locator("#sidebar-strategy-btn")
        expect(strategy_btn).not_to_be_visible()
```

### TC-06.7: Close Sidebar

```python
@pytest.mark.e2e
def test_close_position_sidebar(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Close button should hide sidebar."""
    gradio_locators.click_tab("positions")

    # Open sidebar
    dashboard_page.locator("#positions-table tbody tr").first.click()
    sidebar = dashboard_page.locator("#position-details-sidebar")
    expect(sidebar).to_be_visible(timeout=5_000)

    # Click close button
    close_btn = dashboard_page.locator("#sidebar-close-btn")
    close_btn.click()

    # Sidebar should be hidden
    expect(sidebar).not_to_be_visible()
```

### TC-06.8: Change Exit Strategy

```python
@pytest.mark.e2e
def test_change_exit_strategy(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Change strategy on active position."""
    gradio_locators.click_tab("positions")

    # Filter to active
    dashboard_page.locator("#positions-filter-active").click()
    dashboard_page.wait_for_timeout(500)

    # Open first active position
    position_row = dashboard_page.locator("#positions-table tbody tr").first
    if position_row.is_visible():
        position_row.click()

        # Click Change Strategy button
        strategy_btn = dashboard_page.locator("#sidebar-strategy-btn")
        expect(strategy_btn).to_be_visible()
        strategy_btn.click()

        # Strategy selector should appear
        strategy_modal = dashboard_page.locator("#strategy-selector-modal")
        expect(strategy_modal).to_be_visible(timeout=5_000)
```

---

## Trade History Sub-tab

### TC-06.9: View Trade History

```python
@pytest.mark.e2e
def test_trade_history_tab(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Trade History sub-tab shows closed positions."""
    gradio_locators.click_tab("positions")

    # Click Trade History sub-tab
    history_tab = dashboard_page.get_by_role("tab", name="Trade History")
    history_tab.click()

    # History table visible
    history_table = dashboard_page.locator("#history-table")
    expect(history_table).to_be_visible()
```

### TC-06.10: Filter History by Date

```python
@pytest.mark.e2e
def test_filter_history_by_date(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter history by date range."""
    gradio_locators.click_tab("positions")
    dashboard_page.get_by_role("tab", name="Trade History").click()

    # Set date filters
    date_from = dashboard_page.locator("#history-date-from")
    date_to = dashboard_page.locator("#history-date-to")

    expect(date_from).to_be_visible()
    expect(date_to).to_be_visible()

    # Click search
    search_btn = dashboard_page.locator("#history-search-btn")
    search_btn.click()

    dashboard_page.wait_for_timeout(1000)
```

---

## Locators Required

```python
# Positions tab locators
positions_table = "#positions-table"
positions_refresh_btn = "#positions-refresh-btn"
positions_filter_active = "#positions-filter-active"
positions_filter_closed = "#positions-filter-closed"

# Sidebar locators
position_details_sidebar = "#position-details-sidebar"
sidebar_content = "#sidebar-content"
sidebar_close_btn = "#sidebar-close-btn"
sidebar_strategy_btn = "#sidebar-strategy-btn"
strategy_selector_modal = "#strategy-selector-modal"

# History locators
history_table = "#history-table"
history_date_from = "#history-date-from"
history_date_to = "#history-date-to"
history_pnl_filter = "#history-pnl-filter"
history_search_btn = "#history-search-btn"
```

---

## Test Data Requirements

- At least one active position
- At least one closed position with exit details
- Different exit types (take_profit, stop_loss, manual)

---

## Estimated Duration

- TC-06.1 to 06.10: ~40s total
- **Total: ~40s**
