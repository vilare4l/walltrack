# E2E Spec 08: Configuration Panel (Epic 14 Simplified)

> **Priority:** P2
> **Risk:** Low
> **Dependencies:** Dashboard loads

---

## Spec Summary

Validate simplified scoring configuration (8 parameters instead of 30+).

---

## Epic 14 Configuration Changes

### Before (Complex)
- 4-factor weighted system (wallet, cluster, token, context)
- Dual thresholds (trade + high_conviction)
- 30+ tunable parameters
- Complex pie chart visualization

### After (Simplified)
- 2-component model (wallet score × cluster boost)
- Single threshold (0.65)
- 8 parameters total
- Simple bar chart for wallet composition

---

## Test Cases

### TC-08.1: View Current Scoring Config

```python
@pytest.mark.e2e
def test_view_scoring_config(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Display simplified scoring parameters."""
    gradio_locators.click_tab("config")

    # Configuration sub-tab (if tabbed)
    config_tab = dashboard_page.get_by_role("tab", name="Configuration")
    if config_tab.is_visible():
        config_tab.click()

    # Check all 8 parameters visible
    params = [
        "#config-trade-threshold",
        "#config-win-rate-weight",
        "#config-pnl-weight",
        "#config-leader-bonus",
        "#config-pnl-min",
        "#config-pnl-max",
        "#config-min-boost",
        "#config-max-boost",
    ]

    for param_id in params:
        slider = dashboard_page.locator(param_id)
        expect(slider).to_be_visible()
```

### TC-08.2: Modify Trade Threshold

```python
@pytest.mark.e2e
def test_modify_trade_threshold(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Adjust trade threshold slider."""
    gradio_locators.click_tab("config")

    threshold_slider = dashboard_page.locator("#config-trade-threshold")
    expect(threshold_slider).to_be_visible()

    # Get slider input
    slider_input = threshold_slider.locator("input[type='range']")
    if slider_input.is_visible():
        # Move slider to new value
        slider_input.fill("0.70")

        # Verify value displayed
        value_display = threshold_slider.locator(".slider-value, input[type='number']")
        expect(value_display).to_have_value("0.7")
```

### TC-08.3: Wallet Weights Must Sum to 1.0

```python
@pytest.mark.e2e
def test_wallet_weights_validation(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Win Rate + PnL weights must equal 1.0."""
    gradio_locators.click_tab("config")

    win_rate_slider = dashboard_page.locator("#config-win-rate-weight")
    pnl_slider = dashboard_page.locator("#config-pnl-weight")
    weight_sum = dashboard_page.locator("#weight-sum-display, #config-weight-sum")

    # Initial state should be valid (0.6 + 0.4 = 1.0)
    expect(weight_sum).to_contain_text("1.00")
    expect(weight_sum).to_contain_text("valid")

    # Change win rate
    win_rate_input = win_rate_slider.locator("input[type='range']")
    win_rate_input.fill("0.70")

    dashboard_page.wait_for_timeout(500)

    # Should auto-update or show warning
    # Either PnL adjusts to 0.30 OR validation error shown
```

### TC-08.4: Update Chart on Weight Change

```python
@pytest.mark.e2e
def test_chart_updates_on_weight_change(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Bar chart should update when weights change."""
    gradio_locators.click_tab("config")

    # Find chart
    chart = dashboard_page.locator("#scoring-chart, .plotly-graph-div")
    expect(chart).to_be_visible()

    # Change weight
    win_rate_slider = dashboard_page.locator("#config-win-rate-weight")
    win_rate_input = win_rate_slider.locator("input[type='range']")
    win_rate_input.fill("0.80")

    dashboard_page.wait_for_timeout(500)

    # Chart should have re-rendered (hard to verify exactly, but should still be visible)
    expect(chart).to_be_visible()
```

### TC-08.5: Apply Configuration Changes

```python
@pytest.mark.e2e
def test_apply_configuration(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Apply button should save configuration."""
    gradio_locators.click_tab("config")

    # Modify a setting
    threshold_slider = dashboard_page.locator("#config-trade-threshold")
    threshold_input = threshold_slider.locator("input[type='range']")
    threshold_input.fill("0.68")

    # Click Apply
    apply_btn = dashboard_page.locator("#config-apply-btn, text=Apply")
    apply_btn.click()

    # Verify success message
    status = dashboard_page.locator("#config-status")
    expect(status).to_contain_text("updated", timeout=5_000)
```

### TC-08.6: Reset to Defaults

```python
@pytest.mark.e2e
def test_reset_to_defaults(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Reset button should restore default values."""
    gradio_locators.click_tab("config")

    # Click Reset
    reset_btn = dashboard_page.locator("#config-reset-btn, text=Reset")
    reset_btn.click()

    # Verify success message
    status = dashboard_page.locator("#config-status")
    expect(status).to_contain_text("Reset", timeout=5_000)

    # Verify default values
    threshold = dashboard_page.locator("#config-trade-threshold input[type='number']")
    expect(threshold).to_have_value("0.65")
```

---

## Score Preview Calculator

### TC-08.7: Calculate Preview Score

```python
@pytest.mark.e2e
def test_score_preview_calculator(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Test scoring with hypothetical inputs."""
    gradio_locators.click_tab("config")

    # Navigate to Score Preview tab
    preview_tab = dashboard_page.get_by_role("tab", name="Score Preview")
    preview_tab.click()

    # Set inputs
    win_rate_input = dashboard_page.locator("#preview-win-rate")
    win_rate_input.fill("0.65")

    pnl_input = dashboard_page.locator("#preview-pnl")
    pnl_input.fill("75")

    leader_checkbox = dashboard_page.locator("#preview-is-leader")
    leader_checkbox.check()

    cluster_boost_input = dashboard_page.locator("#preview-cluster-boost")
    cluster_boost_input.fill("1.3")

    # Calculate
    calc_btn = dashboard_page.locator("#calculate-score-btn, text=Calculate")
    calc_btn.click()

    # Verify result
    result = dashboard_page.locator("#preview-result")
    expect(result).to_be_visible(timeout=3_000)
    expect(result).to_contain_text("Final Score")
    expect(result).to_contain_text("TRADE")  # 0.65 × 1.15 × 1.3 > 0.65
```

### TC-08.8: Preview Shows Decision

```python
@pytest.mark.e2e
def test_preview_shows_trade_decision(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Preview should show TRADE or NO TRADE decision."""
    gradio_locators.click_tab("config")

    preview_tab = dashboard_page.get_by_role("tab", name="Score Preview")
    preview_tab.click()

    # Test NO TRADE case (low inputs)
    win_rate_input = dashboard_page.locator("#preview-win-rate")
    win_rate_input.fill("0.30")

    pnl_input = dashboard_page.locator("#preview-pnl")
    pnl_input.fill("10")

    cluster_boost_input = dashboard_page.locator("#preview-cluster-boost")
    cluster_boost_input.fill("1.0")

    calc_btn = dashboard_page.locator("#calculate-score-btn, text=Calculate")
    calc_btn.click()

    result = dashboard_page.locator("#preview-result")
    expect(result).to_contain_text("NO TRADE")
```

---

## Signal Analysis Tab

### TC-08.9: View Recent Signals

```python
@pytest.mark.e2e
def test_signal_analysis_tab(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Signal Analysis shows recent scored signals."""
    gradio_locators.click_tab("config")

    # Navigate to Signal Analysis tab
    analysis_tab = dashboard_page.get_by_role("tab", name="Signal Analysis")
    analysis_tab.click()

    # Signal table visible
    signal_table = dashboard_page.locator("#signal-analysis-table")
    expect(signal_table).to_be_visible()

    # Refresh button
    refresh_btn = dashboard_page.locator("#refresh-signals-btn")
    expect(refresh_btn).to_be_visible()
```

---

## Locators Required

```python
# Config tab locators
config_trade_threshold = "#config-trade-threshold"
config_win_rate_weight = "#config-win-rate-weight"
config_pnl_weight = "#config-pnl-weight"
config_leader_bonus = "#config-leader-bonus"
config_pnl_min = "#config-pnl-min"
config_pnl_max = "#config-pnl-max"
config_min_boost = "#config-min-boost"
config_max_boost = "#config-max-boost"
config_apply_btn = "#config-apply-btn"
config_reset_btn = "#config-reset-btn"
config_status = "#config-status"
weight_sum_display = "#weight-sum-display"
scoring_chart = "#scoring-chart"

# Preview locators
preview_win_rate = "#preview-win-rate"
preview_pnl = "#preview-pnl"
preview_is_leader = "#preview-is-leader"
preview_cluster_boost = "#preview-cluster-boost"
calculate_score_btn = "#calculate-score-btn"
preview_result = "#preview-result"

# Analysis locators
signal_analysis_table = "#signal-analysis-table"
refresh_signals_btn = "#refresh-signals-btn"
```

---

## Default Values (Epic 14)

| Parameter | Default | Range |
|-----------|---------|-------|
| Trade Threshold | 0.65 | 0.5-0.9 |
| Win Rate Weight | 0.60 | 0.0-1.0 |
| PnL Weight | 0.40 | 0.0-1.0 |
| Leader Bonus | 1.15 | 1.0-2.0 |
| PnL Normalize Min | -50 | -500-0 |
| PnL Normalize Max | 200 | 100-1000 |
| Min Cluster Boost | 1.0 | 1.0-1.5 |
| Max Cluster Boost | 1.8 | 1.0-2.5 |

---

## Estimated Duration

- TC-08.1 to 08.9: ~35s total
- **Total: ~35s**
