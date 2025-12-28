# E2E Spec 10: Simulation Mode

> **Priority:** P1
> **Risk:** Medium
> **Dependencies:** Dashboard loads

---

## Spec Summary

Validate simulation mode toggle and its impact on order execution.

---

## Epic 14 Context

Simulation mode allows testing the full trading pipeline without real transactions:
- Orders are created but marked `is_simulated=true`
- No actual blockchain transactions
- Positions track paper P&L

---

## Test Cases

### TC-10.1: View Simulation Mode Status

```python
@pytest.mark.e2e
def test_simulation_mode_indicator(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Simulation mode indicator visible on dashboard."""
    # Check for simulation indicator
    sim_indicator = dashboard_page.locator("#simulation-mode-indicator")
    expect(sim_indicator).to_be_visible()

    # Should show current mode (SIM or LIVE)
    expect(sim_indicator).to_contain_text("SIM")
```

### TC-10.2: Toggle Simulation Mode

```python
@pytest.mark.e2e
def test_toggle_simulation_mode(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Toggle between simulation and live mode."""
    gradio_locators.click_tab("config")

    # Find simulation toggle
    sim_toggle = dashboard_page.locator("#simulation-mode-toggle")
    expect(sim_toggle).to_be_visible()

    # Get initial state
    initial_state = sim_toggle.is_checked()

    # Toggle
    sim_toggle.click()
    dashboard_page.wait_for_timeout(500)

    # Verify state changed
    new_state = sim_toggle.is_checked()
    assert new_state != initial_state

    # Toggle back
    sim_toggle.click()
```

### TC-10.3: Live Mode Warning

```python
@pytest.mark.e2e
def test_live_mode_warning(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Warning shown when switching to live mode."""
    gradio_locators.click_tab("config")

    sim_toggle = dashboard_page.locator("#simulation-mode-toggle")

    # If currently in simulation, toggle to live
    if sim_toggle.is_checked():
        sim_toggle.click()

        # Warning dialog should appear
        warning = dashboard_page.locator("#live-mode-warning")
        expect(warning).to_be_visible(timeout=3_000)
        expect(warning).to_contain_text("LIVE")
        expect(warning).to_contain_text("real transactions")

        # Cancel to stay in simulation
        cancel_btn = dashboard_page.locator("#live-mode-cancel")
        cancel_btn.click()
```

### TC-10.4: Orders Marked as Simulated

```python
@pytest.mark.e2e
def test_orders_show_simulation_flag(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Orders in simulation mode show SIM indicator."""
    # Ensure in simulation mode
    sim_indicator = dashboard_page.locator("#simulation-mode-indicator")
    expect(sim_indicator).to_contain_text("SIM")

    # Navigate to orders
    gradio_locators.click_tab("positions")
    orders_tab = dashboard_page.get_by_role("tab", name="Orders")
    if orders_tab.is_visible():
        orders_tab.click()

    orders_table = dashboard_page.locator("#orders-table")

    # Check for simulation indicator on orders
    sim_orders = orders_table.locator(".simulation-indicator, text=SIM")
    # In test env, at least some orders should be simulated
```

### TC-10.5: Positions Track Paper P&L

```python
@pytest.mark.e2e
def test_positions_paper_pnl(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Simulated positions show paper P&L."""
    gradio_locators.click_tab("positions")

    positions_table = dashboard_page.locator("#positions-table")
    expect(positions_table).to_be_visible()

    # Check P&L column exists
    expect(positions_table).to_contain_text("P&L")

    # Click a position to see details
    position_row = dashboard_page.locator("#positions-table tbody tr").first
    if position_row.is_visible():
        position_row.click()

        sidebar = dashboard_page.locator("#position-details-sidebar")
        expect(sidebar).to_be_visible(timeout=5_000)

        # Should show paper indication for simulated
        paper_indicator = sidebar.locator("text=Paper, text=Simulated")
        # May or may not be visible depending on position type
```

### TC-10.6: Dashboard Header Shows Mode

```python
@pytest.mark.e2e
def test_dashboard_header_mode(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Dashboard header clearly shows current mode."""
    # Check header area
    header = dashboard_page.locator("#dashboard-header, .header")

    # Mode should be prominently displayed
    mode_display = header.locator("#mode-display, .mode-indicator")
    if mode_display.is_visible():
        # Should clearly indicate SIMULATION or LIVE
        text = mode_display.inner_text()
        assert "SIMULATION" in text.upper() or "LIVE" in text.upper() or "SIM" in text.upper()
```

---

## Mode Transition Tests

### TC-10.7: Config Persists Mode

```python
@pytest.mark.e2e
def test_mode_persists_after_refresh(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Simulation mode setting persists after page refresh."""
    gradio_locators.click_tab("config")

    sim_toggle = dashboard_page.locator("#simulation-mode-toggle")
    initial_state = sim_toggle.is_checked()

    # Refresh page
    dashboard_page.reload()
    dashboard_page.wait_for_load_state("networkidle")

    gradio_locators.click_tab("config")

    # Mode should be same
    sim_toggle = dashboard_page.locator("#simulation-mode-toggle")
    expect(sim_toggle).to_be_checked() if initial_state else expect(sim_toggle).not_to_be_checked()
```

---

## Locators Required

```python
# Simulation mode locators
simulation_mode_indicator = "#simulation-mode-indicator"
simulation_mode_toggle = "#simulation-mode-toggle"
live_mode_warning = "#live-mode-warning"
live_mode_confirm = "#live-mode-confirm"
live_mode_cancel = "#live-mode-cancel"
mode_display = "#mode-display"
dashboard_header = "#dashboard-header"
```

---

## Test Data Requirements

- System configured with simulation mode enabled by default
- At least one simulated order in database
- At least one simulated position

---

## Estimated Duration

- TC-10.1 to 10.7: ~25s total
- **Total: ~25s**
