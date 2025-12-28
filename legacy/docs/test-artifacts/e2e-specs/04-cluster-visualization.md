# E2E Spec 04: Cluster Visualization

> **Priority:** P1
> **Risk:** Medium
> **Dependencies:** Wallets exist in watchlist

---

## Spec Summary

Validate cluster detection display and member visualization.

---

## Test Cases

### TC-04.1: View Cluster List

```python
@pytest.mark.e2e
def test_view_cluster_list(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Display all detected clusters."""
    gradio_locators.click_tab("clusters")

    # Clusters table visible
    clusters_table = dashboard_page.locator("#clusters-table")
    expect(clusters_table).to_be_visible()

    # Check column headers
    headers = ["ID", "Size", "Leader", "Cohesion", "Multiplier"]
    for header in headers:
        expect(clusters_table).to_contain_text(header)
```

### TC-04.2: View Cluster Details

```python
@pytest.mark.e2e
def test_view_cluster_details(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Drill into cluster members."""
    gradio_locators.click_tab("clusters")

    # Click first cluster row
    cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
    cluster_row.click()

    # Member list should appear
    member_list = dashboard_page.locator("#cluster-members-list")
    expect(member_list).to_be_visible(timeout=5_000)

    # Check member info displayed
    expect(member_list).to_contain_text("Wallet")
    expect(member_list).to_contain_text("Connection")
```

### TC-04.3: Cluster Size Filter

```python
@pytest.mark.e2e
def test_cluster_size_filter(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Filter clusters by minimum size."""
    gradio_locators.click_tab("clusters")

    # Find size filter if exists
    size_filter = dashboard_page.locator("#clusters-size-filter")
    if size_filter.is_visible():
        size_filter.fill("5")
        dashboard_page.keyboard.press("Enter")

        # Verify filter applied
        dashboard_page.wait_for_timeout(500)
```

### TC-04.4: Expand Cluster

```python
@pytest.mark.e2e
def test_expand_cluster(
    dashboard_page: Page,
    gradio_locators: GradioLocators
) -> None:
    """Find connected wallets for cluster expansion."""
    gradio_locators.click_tab("clusters")

    # Select cluster
    cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
    cluster_row.click()

    # Click expand button
    expand_btn = dashboard_page.locator("#cluster-expand-btn")
    if expand_btn.is_visible():
        expand_btn.click()

        # Wait for candidates
        candidates = dashboard_page.locator("#cluster-candidates")
        expect(candidates).to_be_visible(timeout=10_000)
```

---

## Locators Required

```python
# Clusters tab locators
clusters_table = "#clusters-table"
cluster_members_list = "#cluster-members-list"
clusters_size_filter = "#clusters-size-filter"
cluster_expand_btn = "#cluster-expand-btn"
cluster_candidates = "#cluster-candidates"
```

---

## Test Data Requirements

- At least one cluster with 3+ members in Neo4j
- Cluster members linked via FUNDED_BY or BUYS_WITH edges

---

## Estimated Duration

- TC-04.1: 3s
- TC-04.2: 5s
- TC-04.3: 3s
- TC-04.4: 10s
- **Total: ~21s**
