# Epic 10: Dashboard UX Redesign

**Goal:** Transform the 8-tab Gradio dashboard into a 3-page Navbar + Sidebar architecture with auto-refresh status bar and contextual drill-down.

**Input Document:** `docs/ux-design-specification.md`

---

## Epic Summary

| Aspect | Before | After |
|--------|--------|-------|
| Navigation | 8 disconnected tabs | 3 pages via `gr.Navbar` |
| Status | Manual refresh | Auto-refresh 30s |
| Drill-down | New tab | Contextual sidebar |
| Context | Lost between tabs | Persistent in sidebar |

---

## Stories

### 10-1: Status Bar with Auto-Refresh

**As** the operator,
**I want** a persistent status bar that auto-refreshes every 30 seconds,
**So that** I know instantly if the system is running without clicking anything.

**Acceptance Criteria:**

- **Given** the dashboard is open
- **When** the page loads
- **Then** a status bar appears at the top showing:
  - Discovery scheduler status (last run, next run)
  - Signal count today
  - Active wallet count
  - Webhook sync status
- **And** the status bar refreshes every 30 seconds automatically

**Technical Notes:**
- Use `gr.HTML(render_status_bar, every=30)`
- Status colors: 🟢 healthy, 🟡 warning, 🔴 error

---

### 10-2: Navbar Implementation

**As** the operator,
**I want** a navigation bar with 3 main pages,
**So that** I can navigate between Home, Explorer, and Config with clear URLs.

**Acceptance Criteria:**

- **Given** the dashboard is open
- **When** I see the navigation
- **Then** there are 3 pages: Home, Explorer, Config
- **And** each page has its own URL route
- **And** clicking a nav item loads the corresponding page

**Technical Notes:**
- Use `gr.Navbar` with `.route()` decorators
- Routes: `/`, `/explorer`, `/config`

---

### 10-3: Sidebar Implementation

**As** the operator,
**I want** a collapsible sidebar that shows context for any selected element,
**So that** I can drill-down without losing my place in the main content.

**Acceptance Criteria:**

- **Given** I am on any page
- **When** I click on a table row (position, wallet, signal)
- **Then** the sidebar opens with detailed context
- **And** the sidebar shows "why" information (discovery source, score breakdown)
- **And** action buttons are available (Blacklist, Re-profile, View related)

**Technical Notes:**
- Use `gr.Sidebar(position="right", width=380, open=False)`
- Use `gr.State` to track selected element across components

---

### 10-4: Home Page

**As** the operator,
**I want** a Home page that answers "is it working?" in 2 seconds,
**So that** I can quickly check system status and active positions.

**Acceptance Criteria:**

- **Given** I navigate to Home
- **When** the page loads
- **Then** I see KPI cards: P&L today, active positions, signals today, win rate
- **And** I see a table of active positions (clickable → sidebar)
- **And** I see recent alerts if any

**Technical Notes:**
- Consolidate Status + Positions + Performance KPIs
- All table rows trigger sidebar on click

---

### 10-5: Explorer Page with Tabs

**As** the operator,
**I want** an Explorer page with tabs for Signals, Wallets, and Clusters,
**So that** I can explore the data flow in one place.

**Acceptance Criteria:**

- **Given** I navigate to Explorer
- **When** the page loads
- **Then** I see 3 tabs: Signals, Wallets, Clusters
- **And** each tab shows the existing component (migrated from old tabs)
- **And** clicking any row opens the sidebar with context

**Technical Notes:**
- Use `gr.Tabs` inside Explorer page
- Migrate existing components: `signals.py`, `wallets.py`, `clusters.py`

---

### 10-6: Config Page Migration

**As** the operator,
**I want** a dedicated Config page for all settings,
**So that** I can adjust parameters in one place.

**Acceptance Criteria:**

- **Given** I navigate to Config
- **When** the page loads
- **Then** I see all configuration options (scoring, thresholds, webhooks, system)
- **And** the existing config panel is migrated here

**Technical Notes:**
- Migrate `config_panel.py` to Config page
- No sidebar needed on this page

---

### 10-7: Drill-Down Integration

**As** the operator,
**I want** every clickable element to show its full context in the sidebar,
**So that** I can understand "why" for any decision.

**Acceptance Criteria:**

- **Given** I click on a position
- **When** the sidebar opens
- **Then** I see: token info, wallet source (clickable), score breakdown, discovery origin

- **Given** I click on a wallet
- **When** the sidebar opens
- **Then** I see: wallet metrics, discovery source, cluster membership, related signals

- **Given** I click on a signal
- **When** the sidebar opens
- **Then** I see: signal details, source wallet, token info, action taken

**Technical Notes:**
- Each entity type needs a `render_context(entity)` function
- Sidebar content updates via `gr.State` and event handlers

---

## Implementation Order

1. **10-2: Navbar** - Structural change first
2. **10-3: Sidebar** - Core drill-down mechanism
3. **10-1: Status Bar** - Top-level feedback
4. **10-4: Home Page** - Primary landing
5. **10-5: Explorer Page** - Migrate existing components
6. **10-6: Config Page** - Simple migration
7. **10-7: Drill-Down** - Wire everything together

---

## Definition of Done

- [ ] All 8 old tabs removed
- [ ] Navbar with 3 pages working
- [ ] Sidebar opens on any table row click
- [ ] Status bar auto-refreshes every 30s
- [ ] All existing functionality preserved
- [ ] E2E tests updated for new structure
