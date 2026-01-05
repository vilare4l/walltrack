# Epic 1: Data Foundation & UI Framework

Operator can visualize the system structure and interact with mockup data, validating the information architecture before connecting real logic. All 9 database tables migrated with comprehensive mock data, complete Gradio UI (Dashboard, Watchlist, Config tabs) displaying mock data with table + sidebar interactions.

### Story 1.1: Database Schema Migration & Mock Data

As an operator,
I want all 9 database tables created with comprehensive mock data,
So that I can validate the complete data structure before implementing business logic.

**Acceptance Criteria:**

**Given** a fresh Supabase database in the walltrack schema
**When** I execute all migration files sequentially
**Then** 7 core tables are created successfully (config, exit_strategies, wallets, tokens, signals, orders, positions)
**And** each table has COMMENT ON TABLE documenting its architectural pattern
**And** each column has COMMENT ON COLUMN documenting its purpose

**Given** the database schema is migrated
**When** I execute the mock data insertion script
**Then** mock data is inserted for 7 core tables:
- `config`: 1 row (singleton pattern)
- `exit_strategies`: 3 templates (conservative, balanced, aggressive)
- `wallets`: 5 wallets (3 simulation mode, 2 live mode) with discovery metrics
- `tokens`: 8 tokens with safety scores (4 safe ≥0.60, 4 unsafe <0.60)
- `signals`: 20 signals across different wallets (10 filtered, 10 processed)
- `positions`: 12 positions (6 open, 6 closed) with PnL data
- `orders`: 18 orders (12 filled, 4 pending, 2 failed)

**And** all foreign key relationships are valid (no orphaned records)
**And** mock data represents realistic scenarios (successful trades, failed trades, filtered signals)

**Given** mock data is inserted
**When** I query each table via Supabase dashboard
**Then** I can view all mock records
**And** I can validate the data structure matches the design guides in `docs/database-design/*.md`

### Story 1.2: Gradio Application Shell & Three-Tab Navigation

As an operator,
I want a functional Gradio application with three-tab navigation (Dashboard, Watchlist, Config),
So that I can access different sections of the system and validate the overall UI structure.

**Acceptance Criteria:**

**Given** the Gradio application is launched via `uv run python src/walltrack/ui/app.py`
**When** the application starts successfully
**Then** a browser window opens at http://127.0.0.1:7860
**And** the application displays the WallTrack title
**And** three tabs are visible: "Dashboard", "Watchlist", "Config"

**Given** the three-tab structure is rendered
**When** I click on the "Dashboard" tab
**Then** the tab becomes active (blue underline indicator)
**And** a placeholder message displays: "Dashboard content will appear here"

**Given** the three-tab structure is rendered
**When** I click on the "Watchlist" tab
**Then** the tab becomes active (blue underline indicator)
**And** a placeholder message displays: "Watchlist content will appear here"

**Given** the three-tab structure is rendered
**When** I click on the "Config" tab
**Then** the tab becomes active (blue underline indicator)
**And** a placeholder message displays: "Config content will appear here"

**Given** the application is running
**When** I navigate between tabs multiple times
**Then** tab switching is smooth and immediate
**And** no errors appear in the browser console
**And** the active tab indicator updates correctly

### Story 1.3: Dashboard Tab - Performance Metrics & Positions Table

As an operator,
I want to view performance metrics and active positions with mock data in the Dashboard tab,
So that I can validate the dashboard layout and data display before connecting real logic.

**Acceptance Criteria:**

**Given** the Dashboard tab is active
**When** the tab content loads
**Then** 4 performance metric cards are displayed in a horizontal row
**And** each metric card shows: Win Rate (🔵 Simulation | 🟠 Live), PnL Total (🔵 Simulation | 🟠 Live), Capital Utilization (🔵 Simulation | 🟠 Live), Active Wallets (🔵 Simulation | 🟠 Live)
**And** metric values are large (H2 24px font size) and clearly readable
**And** metric cards use spacious padding (24px) and comfortable spacing

**Given** the performance metrics are displayed
**When** I scroll down in the Dashboard tab
**Then** an Active Positions table is visible below the metrics
**And** the table displays 7 columns: Token, Entry, Current, PnL, Mode, Status, Actions
**And** the table shows mock data from the `positions` table (12 positions: 6 open, 6 closed)
**And** Mode column uses color-coded badges: 🔵 Blue (#3B82F6) for simulation, 🟠 Amber (#F59E0B) for live
**And** PnL column shows positive values in green, negative values in red
**And** rows are compact (48px height) for efficient data density

**Given** the Active Positions table is displayed
**When** I view the mock data
**Then** I can see realistic position data: token symbols (e.g., BONK, WIF, MYRO), entry prices, current prices, PnL values
**And** the data matches the mock data inserted in Story 1.1
**And** closed positions are visually distinct from open positions (e.g., grayed out or separate section)

**Given** the Dashboard tab is fully rendered
**When** I resize the browser window
**Then** the layout adapts responsively (desktop 1200px+: full layout, tablet 768-1199px: adjusted, mobile <768px: single column)
**And** all elements remain visible and usable

### Story 1.4: Watchlist Tab - Wallets Table & Action Bar

As an operator,
I want to view the watchlist with wallet performance data and filtering controls,
So that I can validate the watchlist layout and understand wallet curation capabilities.

**Acceptance Criteria:**

**Given** the Watchlist tab is active
**When** the tab content loads
**Then** an action bar is visible at the top with: [+ Add Wallet] button, Filter dropdown, Sort dropdown
**And** the action bar buttons are styled and functional (buttons trigger placeholder actions)

**Given** the action bar is displayed
**When** I view the wallets table below
**Then** the table displays 7 columns: Label, Address, Mode, Status, Signals, Win Rate, PnL
**And** the table shows mock data from the `wallets` and `performance` tables (5 wallets: 3 simulation, 2 live)
**And** the table occupies 3/4 of the width (Notion-inspired layout, leaving space for future sidebar)

**Given** the wallets table is displayed
**When** I view the mock data
**Then** I can see realistic wallet data:
- Label: e.g., "Smart Whale #1", "Degen Trader"
- Address: truncated format (e.g., "7xKX...9bYz")
- Mode: color-coded badges (🔵 Simulation | 🟠 Live)
- Status: Active/Inactive indicators
- Signals: count values (e.g., "127 signals")
- Win Rate: percentage values (e.g., "68.5%")
- PnL: dollar values with color coding (green for profit, red for loss)

**Given** the wallets table is populated
**When** I click on the Filter dropdown
**Then** filter options are displayed: All, Simulation Only, Live Only, Active Only, Inactive Only
**And** selecting a filter updates the table display (placeholder behavior: shows alert message)

**Given** the wallets table is populated
**When** I click on the Sort dropdown
**Then** sort options are displayed: Win Rate (High to Low), PnL (High to Low), Signals (Most to Least), Recently Added
**And** selecting a sort option updates the table display (placeholder behavior: shows alert message)

**Given** the Watchlist tab is fully rendered
**When** I click the [+ Add Wallet] button
**Then** a placeholder action is triggered (e.g., alert: "Add Wallet functionality coming in Epic 2")

### Story 1.5: Config Tab - Accordion Sections & Form Layouts

As an operator,
I want to view system configuration sections with form layouts and mock data,
So that I can validate the config interface structure before implementing actual configuration logic.

**Acceptance Criteria:**

**Given** the Config tab is active
**When** the tab content loads
**Then** three accordion sections are visible: "Exit Strategies", "Risk Limits", "API Keys"
**And** all sections are collapsed by default (progressive disclosure pattern)

**Given** the accordion sections are displayed
**When** I click on the "Exit Strategies" accordion header
**Then** the section expands smoothly
**And** a form is displayed with the following fields (using mock data from `config` table):
- Stop Loss %: number input (default: 20)
- Trailing Stop %: number input (default: 15)
- Scaling Out Levels: text input (default: "25%, 50%, 75%")
- Mirror Exit Enabled: checkbox (default: checked)
**And** form fields have comfortable spacing (24px padding, 40px input height)
**And** a [Save] button is visible at the bottom (placeholder action)

**Given** the accordion sections are displayed
**When** I click on the "Risk Limits" accordion header
**Then** the section expands smoothly
**And** a form is displayed with the following fields (using mock data from `config` table):
- Max Capital Per Trade %: number input (default: 5)
- Max Total Capital %: number input (default: 80)
- Circuit Breaker Loss Threshold %: number input (default: 15)
- Daily Loss Limit USD: number input (default: 500)
**And** form fields have comfortable spacing
**And** a [Save] button is visible at the bottom (placeholder action)

**Given** the accordion sections are displayed
**When** I click on the "API Keys" accordion header
**Then** the section expands smoothly
**And** a form is displayed with the following fields:
- Helius API Key: password input (masked)
- Wallet Private Key: password input (masked)
- DexScreener API Key: password input (masked, optional)
- Jupiter API Key: password input (masked, optional)
**And** webhook status indicator displays: "Connected ✅" or "Disconnected ❌" (using mock data)
**And** last signal timestamp displays (e.g., "Last signal: 2 minutes ago")
**And** a [Save] button is visible at the bottom (placeholder action)

**Given** the Config tab is fully rendered
**When** I click on any [Save] button
**Then** a placeholder action is triggered (e.g., alert: "Configuration save functionality coming in Epic 5")

**Given** multiple accordion sections are expanded
**When** I click on a collapsed section header
**Then** the clicked section expands
**And** previously expanded sections remain open (all sections can be open simultaneously)

### Story 1.6: Interactive Sidebars - Table Click Handlers & Detail Views

As an operator,
I want to click on table rows and see detailed information in a sidebar,
So that I can validate the progressive disclosure pattern (summary visible, details on-demand).

**Acceptance Criteria:**

**Given** I am viewing the Dashboard tab with the Active Positions table
**When** I click on any position row in the table
**Then** a sidebar appears on the right (1/4 width) with position details
**And** the sidebar displays: Token Name, Entry Price, Current Price, Entry Amount, Remaining Amount, Entry Date, Exit Strategy (from `exit_strategy_override` or default), PnL Breakdown (Realized + Unrealized), Transaction History
**And** the sidebar data matches the clicked row (using mock data from `positions` table)
**And** the sidebar has a [Close] button or click-outside-to-close behavior

**Given** the Dashboard sidebar is open
**When** I click the [Close] button or click outside the sidebar
**Then** the sidebar disappears smoothly
**And** the table returns to full width (3/4 of tab content area)

**Given** I am viewing the Watchlist tab with the Wallets table
**When** I click on any wallet row in the table
**Then** a sidebar appears on the right (1/4 width) with wallet details
**And** the sidebar displays: Wallet Label, Full Address (with copy button), Discovery Metrics (Initial Win Rate, Initial Trades, Initial PnL), Current Performance (Win Rate, PnL, Signals All/30d/7d/24h), Recent Signals (last 5 signals with timestamps and outcomes), Action Buttons ([Promote to Live] / [Demote to Simulation], [Remove Wallet])
**And** the sidebar data matches the clicked row (using mock data from `wallets` and `performance` tables)

**Given** the Watchlist sidebar is open
**When** I click on action buttons ([Promote to Live], [Remove Wallet])
**Then** placeholder actions are triggered (e.g., alert: "Wallet promotion functionality coming in Epic 4")

**Given** the Watchlist sidebar is open
**When** I click the [Close] button or click outside the sidebar
**Then** the sidebar disappears smoothly
**And** the table returns to full width (3/4 of tab content area)

**Given** sidebars are implemented on both Dashboard and Watchlist tabs
**When** I switch between tabs with a sidebar open
**Then** the sidebar closes automatically when switching tabs
**And** no sidebar state persists across tab switches

**Given** I am on a mobile viewport (<768px width)
**When** I click on a table row
**Then** the sidebar opens as a fullscreen modal (overlay pattern)
**And** the modal has a clear [Close] button in the top-right corner
**And** scrolling works within the modal content
