# E2E Spec 01: Dashboard Navigation

> **Priority:** P2
> **Risk:** Low
> **Dependencies:** None

---

## Spec Summary

Validate dashboard loads and all navigation tabs are functional.

---

## Test Cases

### TC-01.1: Dashboard Cold Start

```python
@pytest.mark.e2e
def test_dashboard_cold_start(dashboard_page: Page) -> None:
    """Dashboard should load and display main structure."""
    # Title visible
    title = dashboard_page.locator("#dashboard-title")
    expect(title).to_be_visible()
    expect(title).to_contain_text("WallTrack Dashboard")

    # Subtitle visible
    subtitle = dashboard_page.locator("#dashboard-subtitle")
    expect(subtitle).to_be_visible()
    expect(subtitle).to_contain_text("Solana Memecoin")
```

### TC-01.2: All Tabs Visible

```python
@pytest.mark.e2e
def test_main_tabs_visible(dashboard_page: Page) -> None:
    """All main navigation tabs should be visible."""
    tab_names = [
        "Status", "Wallets", "Clusters", "Signals",
        "Positions", "Discovery", "Config"
    ]
    for tab_name in tab_names:
        tab = dashboard_page.get_by_role("tab", name=tab_name)
        expect(tab).to_be_visible()
```

### TC-01.3: Tab Navigation Round-Trip

```python
@pytest.mark.e2e
def test_tab_navigation_round_trip(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Should navigate through all tabs and back."""
    # Navigate through all tabs
    gradio_locators.click_tab("wallets")
    expect(gradio_locators.wallets_refresh_btn).to_be_visible()

    gradio_locators.click_tab("clusters")
    # Clusters tab content check

    gradio_locators.click_tab("signals")
    # Signals tab content check

    gradio_locators.click_tab("positions")
    expect(gradio_locators.positions_refresh_btn).to_be_visible()

    gradio_locators.click_tab("discovery")
    # Discovery tab content check

    gradio_locators.click_tab("config")
    expect(gradio_locators.config_apply_weights_btn).to_be_visible()

    # Back to status
    gradio_locators.click_tab("status")
```

---

## Locators Required

```python
# conftest.py additions
class GradioLocators:
    # Navigation
    def click_tab(self, tab_name: str) -> None

    # Tab content checks
    @property
    def wallets_refresh_btn(self)

    @property
    def positions_refresh_btn(self)

    @property
    def config_apply_weights_btn(self)
```

---

## Estimated Duration

- Setup: 5s (page load)
- Tests: 15s total
- Total: ~20s
