"""E2E tests for Story 3.2 - Wallet Performance Analysis UI.

Tests the following components:
- Explorer Wallets table shows performance metrics columns
- Sidebar Performance Metrics section displays when wallet is selected
- Config page Performance Analysis Criteria section
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def explorer_page_url():
    """Return the Explorer page URL."""
    return "http://localhost:7861/"  # Adjust port if different


def test_wallets_table_shows_performance_columns(page: Page, explorer_page_url):
    """Test that Wallets table displays performance metric columns.

    AC6: Explorer table shows: Address, Score, Win Rate, PnL, Trades columns.

    Steps:
        1. Navigate to Explorer page
        2. Click Wallets tab
        3. Verify table headers include: Score, Win Rate, PnL, Entry Delay, Trades, Confidence
    """
    # Navigate to Explorer page
    page.goto(explorer_page_url)

    # Wait for page to load
    page.wait_for_load_state("networkidle")

    # Click "Wallets" tab
    wallets_tab = page.get_by_role("tab", name="Wallets")
    wallets_tab.click()

    # Wait for table to render
    page.wait_for_timeout(1000)

    # Verify table exists
    table = page.locator("table").first
    expect(table).to_be_visible()

    # Verify performance metric columns are present in headers
    # Headers: Address, First Seen, Discovered From, Status, Watchlist Score, Score, Win Rate, PnL, Entry Delay, Trades, Confidence, Decay Status
    headers_text = table.locator("thead").inner_text()

    assert "Score" in headers_text, "Score column not found in Wallets table"
    assert "Win Rate" in headers_text, "Win Rate column not found in Wallets table"
    assert "PnL" in headers_text, "PnL column not found in Wallets table"
    assert "Entry Delay" in headers_text, "Entry Delay column not found in Wallets table"
    assert "Trades" in headers_text, "Trades column not found in Wallets table"
    assert "Confidence" in headers_text, "Confidence column not found in Wallets table"


def test_sidebar_performance_metrics_display(page: Page, explorer_page_url):
    """Test that sidebar displays Performance Metrics when wallet is selected.

    AC6: Clicking a row shows detailed sidebar with metric breakdown.

    Steps:
        1. Navigate to Explorer page
        2. Click Wallets tab
        3. Click first wallet row
        4. Verify sidebar opens
        5. Verify "Performance Metrics" section is visible
        6. Verify metrics displayed: Win Rate, Total PnL, Entry Delay, Total Trades, Confidence, Last Updated
    """
    # Navigate to Explorer page
    page.goto(explorer_page_url)
    page.wait_for_load_state("networkidle")

    # Click "Wallets" tab
    wallets_tab = page.get_by_role("tab", name="Wallets")
    wallets_tab.click()
    page.wait_for_timeout(1000)

    # Find the table
    table = page.locator("table").first
    expect(table).to_be_visible()

    # Click first wallet row (index 0)
    first_row = table.locator("tbody tr").first
    first_row.click()

    # Wait for sidebar to open
    page.wait_for_timeout(1500)

    # Verify sidebar opened and contains "Wallet Details"
    sidebar = page.locator("div.svelte-1uel4wn")  # Gradio sidebar class
    sidebar_text = sidebar.inner_text()

    # Verify "Performance Metrics" section header
    assert "Performance Metrics" in sidebar_text, "Performance Metrics section not found in sidebar"

    # Verify individual metrics are displayed
    assert "Win Rate" in sidebar_text, "Win Rate metric not found in sidebar"
    assert "Total PnL" in sidebar_text, "Total PnL metric not found in sidebar"
    assert "Entry Delay" in sidebar_text, "Entry Delay metric not found in sidebar"
    assert "Total Trades" in sidebar_text, "Total Trades metric not found in sidebar"
    assert "Confidence" in sidebar_text, "Confidence metric not found in sidebar"
    assert "Last Updated" in sidebar_text, "Last Updated timestamp not found in sidebar"


def test_sidebar_performance_metrics_table_format(page: Page, explorer_page_url):
    """Test that Performance Metrics are displayed in table format.

    Steps:
        1. Navigate to Explorer page
        2. Click Wallets tab
        3. Click first wallet row
        4. Verify Performance Metrics section uses table format (| Metric | Value |)
    """
    # Navigate to Explorer page
    page.goto(explorer_page_url)
    page.wait_for_load_state("networkidle")

    # Click "Wallets" tab
    wallets_tab = page.get_by_role("tab", name="Wallets")
    wallets_tab.click()
    page.wait_for_timeout(1000)

    # Click first wallet row
    first_row = page.locator("table tbody tr").first
    first_row.click()
    page.wait_for_timeout(1500)

    # Get sidebar content
    sidebar = page.locator("div.svelte-1uel4wn")
    sidebar_text = sidebar.inner_text()

    # Verify table structure (markdown table has "| Metric | Value |" pattern)
    # The markdown renderer converts to HTML table
    assert "Metric" in sidebar_text, "Table header 'Metric' not found"
    assert "Value" in sidebar_text, "Table header 'Value' not found"


def test_config_performance_criteria_accordion(page: Page, explorer_page_url):
    """Test that Config page has Performance Analysis Criteria accordion.

    AC7 (Config UI): Config page shows Performance Analysis Criteria section.

    Steps:
        1. Navigate to root (redirects to Config)
        2. Wait for Config page to load
        3. Find "Performance Analysis Criteria" accordion
        4. Verify it's initially closed
        5. Click to open
        6. Verify "Min Profit % for Win Rate" slider is visible
    """
    # Navigate to root (redirects to Config page)
    page.goto("http://localhost:7861/")
    page.wait_for_load_state("networkidle")

    # Wait for Config page to render
    page.wait_for_timeout(2000)

    # Find "Performance Analysis Criteria" accordion
    accordion = page.get_by_text("Performance Analysis Criteria")
    expect(accordion).to_be_visible()

    # Click to open accordion
    accordion.click()
    page.wait_for_timeout(1000)

    # Verify slider is visible
    min_profit_slider = page.get_by_label("Min Profit % for Win Rate")
    expect(min_profit_slider).to_be_visible()

    # Verify button is visible
    update_btn = page.get_by_role("button", name="Update Performance Criteria")
    expect(update_btn).to_be_visible()


def test_config_performance_criteria_update(page: Page, explorer_page_url):
    """Test updating performance criteria via Config page.

    AC7 (Config UI): Changes can be saved and status message is displayed.

    Steps:
        1. Navigate to Config page
        2. Open "Performance Analysis Criteria" accordion
        3. Adjust "Min Profit %" slider to 15%
        4. Click "Update Performance Criteria" button
        5. Verify success status message appears
        6. Verify message contains "Min Profit for Win: 15%"
    """
    # Navigate to Config page
    page.goto("http://localhost:7861/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Open "Performance Analysis Criteria" accordion
    accordion = page.get_by_text("Performance Analysis Criteria")
    accordion.click()
    page.wait_for_timeout(1000)

    # Find and adjust slider to 15%
    # Gradio Slider is tricky - we'll use keyboard input
    slider_container = page.get_by_label("Min Profit % for Win Rate")
    slider_input = slider_container.locator("input[type='number']")

    # Clear and set value to 15
    slider_input.click()
    slider_input.fill("15")
    page.wait_for_timeout(500)

    # Click "Update Performance Criteria" button
    update_btn = page.get_by_role("button", name="Update Performance Criteria")
    update_btn.click()

    # Wait for async update to complete
    page.wait_for_timeout(2000)

    # Find status textbox
    status_textbox = page.locator("textarea").filter(has_text="Performance criteria")

    # Verify status textbox exists and contains success message
    expect(status_textbox).to_be_visible()
    status_text = status_textbox.input_value()

    assert "✅" in status_text or "Performance criteria updated" in status_text, \
        f"Expected success message, got: {status_text}"
    assert "15" in status_text, \
        f"Expected '15%' in status message, got: {status_text}"


def test_config_performance_criteria_default_value(page: Page, explorer_page_url):
    """Test that Min Profit slider has correct default value.

    AC2: Default min_profit_percent is 10%.

    Steps:
        1. Navigate to Config page
        2. Open "Performance Analysis Criteria" accordion
        3. Verify slider default value is 10
    """
    # Navigate to Config page
    page.goto("http://localhost:7861/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # Open "Performance Analysis Criteria" accordion
    accordion = page.get_by_text("Performance Analysis Criteria")
    accordion.click()
    page.wait_for_timeout(1000)

    # Find slider input
    slider_container = page.get_by_label("Min Profit % for Win Rate")
    slider_input = slider_container.locator("input[type='number']")

    # Verify default value is 10
    default_value = slider_input.input_value()
    assert default_value == "10", f"Expected default value 10, got: {default_value}"
