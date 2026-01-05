# Design Direction Decision

### Design Directions Explored

**Single Coherent Direction: Data-First Monitoring Interface**

Given WallTrack's constraints (Gradio native components only) and clear functional requirements (monitoring tool, data-heavy, dual-mode clarity), we pursued a **single coherent design direction** rather than exploring multiple visual styles.

**Why Single Direction:**
- **Gradio Constraints**: Limited CSS customization means visual variations are minimal
- **Functional Tool**: Not a brand-exploration product—function > aesthetics
- **Clear Requirements**: All previous steps (1-8) converged on a data-monitoring interface inspired by Notion database views

**Direction Name: "Data Command Center"**

A monitoring-focused interface that prioritizes:
1. **Rapid data scanning** (morning dashboard < 30s)
2. **Dual-mode clarity** (simulation vs live always visible)
3. **Progressive disclosure** (summary → detail on demand)
4. **Notion-inspired familiarity** (table + sidebar + tabs)

### Chosen Direction

**"Data Command Center" — Monitoring-First Interface**

**Core Visual Characteristics:**

1. **Three-Tab Structure (Persistent Navigation)**
   ```
   ┌─────────────────────────────────────────────────────┐
   │  [Dashboard]  [Watchlist]  [Config]                │
   ├─────────────────────────────────────────────────────┤
   │  Tab Content Area (full viewport)                   │
   │                                                      │
   └─────────────────────────────────────────────────────┘
   ```
   - Tabs always visible (gr.Tabs at top)
   - Active tab highlighted (Blue 500 underline)
   - Content area below tabs (no sidebar chrome)

2. **Dashboard Layout (Performance Monitoring)**
   ```
   ┌─────────────────────────────────────────────────────┐
   │  Performance Metrics (4 cards, horizontal row)      │
   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐  │
   │  │ Win Rate│ │PnL Total│ │Cap Util │ │Active W │  │
   │  │  60%    │ │ +150%   │ │  40%    │ │   8     │  │
   │  │ 🔵 3 🟠2│ │🔵+80 🟠70│ │🔵20 🟠20│ │🔵 5 🟠3 │  │
   │  └─────────┘ └─────────┘ └─────────┘ └─────────┘  │
   ├─────────────────────────────────────────────────────┤
   │  Active Positions (gr.Dataframe, dense table)       │
   │  Token │Entry │Current│ PnL  │Mode│Status│Actions  │
   │  ──────┼──────┼───────┼──────┼────┼──────┼─────────│
   │  $BONK │0.012 │ 0.018 │+50% ✅│🔵 │ Open │ [View] │
   │  $PEPE │0.025 │ 0.023 │-8% ❌ │🟠 │ Open │ [View] │
   │  ...   │ ...  │  ...  │ ...  │... │ ...  │  ...   │
   └─────────────────────────────────────────────────────┘
   ```
   - Metrics: 4-card horizontal layout (gr.Row > 4x gr.Column)
   - Dual-mode split: Each metric shows 🔵 Simulation | 🟠 Live
   - Positions table: Dense (48px rows), 7 columns, click row → sidebar

3. **Watchlist Layout (Wallet Curation)**
   ```
   ┌─────────────────────────────────────────────────────────┐
   │  [+ Add Wallet]  [Filter: All ▾]  [Sort: Win Rate ▾]   │
   ├───────────────────────────────┬─────────────────────────┤
   │  Wallets Table (3/4 width)    │ Sidebar (1/4, hidden)  │
   │                               │                         │
   │  Label  │Mode│Status│Signals │ Wallet Detail          │
   │  ───────┼────┼──────┼─────── │ ─────────────────────  │
   │  GMGN#47│🔵 │🟢 Act│   12   │ [Visible on row click] │
   │  Top Wal│🟠 │🟢 Act│   45   │                         │
   │  Test   │🔵 │🔴 Err│    0   │ Performance Charts     │
   │  ...    │... │ ...  │  ...   │ Recent Signals         │
   │         │    │      │        │ [Promote] [Remove]     │
   └───────────────────────────────┴─────────────────────────┘
   ```
   - Action bar: Add Wallet button + Filters (gr.Row with gr.Button + gr.Dropdown)
   - Table + Sidebar: gr.Row(gr.Dataframe(scale=3), gr.Column(scale=1, visible=False))
   - Click row → sidebar appears (gr.Dataframe.select() toggles visible=True)

4. **Config Layout (System Parameters)**
   ```
   ┌─────────────────────────────────────────────────────┐
   │  Configuration Sections (accordion-style)           │
   │                                                      │
   │  ▶ Global Settings                                  │
   │  ▼ Exit Strategies                                  │
   │     Strategy Name: [Scaling Out             ▾]      │
   │     Exit 1: [50%] at [2x]                           │
   │     Exit 2: [50%] at [3x]                           │
   │     Stop Loss: [-20%]                               │
   │     [Save Strategy]                                 │
   │                                                      │
   │  ▶ Risk Limits                                      │
   │  ▶ API Keys                                         │
   └─────────────────────────────────────────────────────┘
   ```
   - Form-based layout (gr.Form for each section)
   - Accordion pattern via gr.Accordion (Gradio native)
   - Comfortable spacing (24px padding, 40px input height)

**Visual Hierarchy:**
- **Primary**: Performance metrics (large text, spacious cards)
- **Secondary**: Active positions table (dense, scannable)
- **Tertiary**: Sidebar details, metadata (comfortable, detailed)

**Color Application:**
- **Blue (#3B82F6)**: Simulation badges, primary buttons, default state
- **Amber (#F59E0B)**: Live badges, caution actions, "Promote to Live" button
- **Green (#10B981)**: Positive PnL, "Tracking Active" status, profitable positions
- **Red (#EF4444)**: Negative PnL, errors, circuit breaker alerts
- **Slate**: Text (900), metadata (600), borders (200), backgrounds (50)

**Typography Application:**
- **H1 (32px)**: Tab names ("Dashboard", "Watchlist", "Config")
- **H2 (24px)**: Section headers ("Performance Metrics", "Active Positions")
- **H3 (20px)**: Sidebar headers ("Wallet Performance", "Recent Signals")
- **Body (16px)**: Table data, form inputs, default text
- **Small (14px)**: Metadata (timestamps, labels, tooltips)
- **Tiny (12px)**: Badges ("🔵 Simulation", "🟢 Tracking Active")

### Design Rationale

**Why "Data Command Center" Works for WallTrack:**

1. **Aligns with Core Experience ("Discover → Add → Autopilot")**
   - Dashboard shows autopilot results (positions opened automatically)
   - Watchlist shows curation interface (add/remove wallets)
   - Config defines autopilot behavior (exit strategies, risk limits)
   - User never manually trades—UI reflects this (no "Buy"/"Sell" buttons on Dashboard)

2. **Supports Dual-Mode Mental Model**
   - Blue/Amber color coding omnipresent (every table row, every metric card)
   - Metrics split by mode (Win Rate: 🔵 60% Sim | 🟠 55% Live)
   - No confusion about "which mode am I in?"—always visible

3. **Optimized for Morning Dashboard Scan (< 30s)**
   - Performance metrics visible immediately (no scrolling)
   - 4 key numbers large and colorful (Win Rate, PnL, Cap Util, Active Wallets)
   - Active positions table dense (8-10 rows visible without scrolling)
   - Status badges left-aligned (scan anchor: 🟢🟢🔴🟢 pattern = quick health check)

4. **Progressive Disclosure Reduces Overwhelm**
   - **Summary**: Table shows 5-7 essential columns (Token, Entry, PnL, Mode, Status)
   - **Details**: Click row → Sidebar shows full data (wallet attribution, strategy, timeline, charts)
   - **Advanced**: Config tab hidden until needed (< 5% of daily interactions)
   - Operator builds mental model: "Tables for scanning, Sidebar for deep dives"

5. **Notion Familiarity Reduces Learning Curve**
   - User already knows Notion: Click row → See details in sidebar
   - WallTrack adaptation: Click position row → See position lifecycle, wallet info, strategy
   - No documentation needed—pattern is intuitive

6. **Gradio Constraints as Features**
   - Limited CSS means forced simplicity (can't over-design)
   - Native components enforce accessibility (keyboard nav, screen reader support built-in)
   - Responsive by default (mobile view works without custom breakpoints)
   - Fast development (< 500 lines of Python for full UI)

7. **Scales with Future Complexity**
   - **Phase 1 (MVP)**: 3 tabs, 2 tables (Dashboard Positions, Watchlist Wallets)
   - **Phase 2**: Add Signals tab (audit trail), Tokens tab (research view)
   - **Phase 3**: Add Charts to sidebar (performance trends, wallet comparison)
   - **Phase 4**: Add Gallery views (alternative to tables for visual users)
   - Architecture supports addition without redesign

### Implementation Approach

**Gradio Component Mapping:**

| UI Element | Gradio Component | Props/Config |
|------------|------------------|--------------|
| **Tab Navigation** | `gr.Tabs()` + `gr.Tab()` | Default Gradio tabs, no custom styling |
| **Performance Metrics** | 4x `gr.Markdown()` in `gr.Row()` | Markdown with emoji + numbers, spacious padding |
| **Positions Table** | `gr.Dataframe(interactive=True)` | Dense rows (48px), 7 columns, click selects |
| **Watchlist Table** | `gr.Dataframe(interactive=True)` | Same as positions, different columns |
| **Sidebar Detail** | `gr.Column(visible=False)` | Hidden by default, toggle on table.select() |
| **Add Wallet Form** | `gr.Form()` | Pre-filled defaults (Mode: Sim, Strategy: Preset 1) |
| **Action Buttons** | `gr.Button()` | Standard Gradio buttons, variant="primary"/"secondary" |
| **Config Sections** | `gr.Accordion()` | Collapsible sections for organized settings |

**Layout Implementation Pattern:**

```python
import gradio as gr
from walltrack.ui.theme import create_walltrack_theme

with gr.Blocks(theme=create_walltrack_theme()) as app:

    with gr.Tabs():

        # ─────────────────────────────────────────────────
        # DASHBOARD TAB
        # ─────────────────────────────────────────────────
        with gr.Tab("Dashboard"):

            # Performance Metrics (4 cards)
            with gr.Row():
                gr.Markdown("### Win Rate\n**60%**\n🔵 65% Sim | 🟠 55% Live")
                gr.Markdown("### PnL Total\n**+150%**\n🔵 +80% Sim | 🟠 +70% Live")
                gr.Markdown("### Cap Utilization\n**40%**\n🔵 20% Sim | 🟠 20% Live")
                gr.Markdown("### Active Wallets\n**8**\n🔵 5 Sim | 🟠 3 Live")

            # Active Positions Table + Sidebar
            with gr.Row():
                positions_table = gr.Dataframe(
                    headers=["Token", "Entry", "Current", "PnL", "Mode", "Status"],
                    interactive=True,
                    scale=3
                )

                with gr.Column(scale=1, visible=False) as position_sidebar:
                    gr.Markdown("## Position Detail")
                    position_detail_md = gr.Markdown()
                    gr.Button("Close Position")

            # Event: Click row → Show sidebar
            positions_table.select(
                fn=show_position_detail,
                outputs=[position_sidebar, position_detail_md]
            )

        # ─────────────────────────────────────────────────
        # WATCHLIST TAB
        # ─────────────────────────────────────────────────
        with gr.Tab("Watchlist"):

            # Action Bar
            with gr.Row():
                add_wallet_btn = gr.Button("+ Add Wallet", variant="primary")
                filter_dropdown = gr.Dropdown(["All", "Simulation Only", "Live Only"])
                sort_dropdown = gr.Dropdown(["Win Rate", "PnL", "Signals Count"])

            # Wallets Table + Sidebar
            with gr.Row():
                wallets_table = gr.Dataframe(
                    headers=["Label", "Address", "Mode", "Status", "Signals", "Win Rate", "PnL"],
                    interactive=True,
                    scale=3
                )

                with gr.Column(scale=1, visible=False) as wallet_sidebar:
                    gr.Markdown("## Wallet Performance")
                    wallet_detail_md = gr.Markdown()
                    with gr.Row():
                        gr.Button("Promote to Live", variant="secondary")
                        gr.Button("Remove Wallet")

            # Event: Click row → Show sidebar
            wallets_table.select(
                fn=show_wallet_detail,
                outputs=[wallet_sidebar, wallet_detail_md]
            )

        # ─────────────────────────────────────────────────
        # CONFIG TAB
        # ─────────────────────────────────────────────────
        with gr.Tab("Config"):

            with gr.Accordion("Exit Strategies", open=True):
                with gr.Form():
                    strategy_name = gr.Dropdown(["Scaling Out", "Mirror Exit", "Custom"])
                    exit_1_pct = gr.Slider(0, 100, value=50, label="Exit 1 %")
                    exit_1_mult = gr.Slider(1, 10, value=2, label="Exit 1 Multiplier")
                    save_btn = gr.Button("Save Strategy")

            with gr.Accordion("Risk Limits", open=False):
                # Risk limit form fields...
                pass

app.launch()
```

**Component State Management:**

- **Sidebar visibility**: Controlled via `.select()` event on tables
- **Form pre-filling**: Default values in component props (e.g., `value=50`)
- **Table updates**: Real-time via Gradio `.change()` events (websocket updates)
- **Dual-mode filtering**: Dropdown triggers `.change()` → re-render table with filtered data

**Responsive Behavior:**

- **Desktop (1200px+)**: Full 3-column layout (Metrics row + Table + Sidebar)
- **Tablet (768-1199px)**: Table + Sidebar (sidebar overlays on click)
- **Mobile (<768px)**: Single column, sidebar fullscreen modal, tables show 3-4 columns

**Performance Optimizations:**

- **Lazy load sidebar content**: Only fetch wallet/position details on row click
- **Paginated tables**: Limit to 50 rows, pagination via Gradio's built-in support
- **Debounced filters**: Wait 300ms after dropdown change before re-rendering
- **Cached metrics**: Performance metrics update every 60s (not on every table interaction)

**Testing Strategy:**

- **Visual regression**: Playwright screenshots of 3 tabs (Desktop, Tablet, Mobile)
- **Interaction testing**: E2E tests for Add Wallet flow, Position detail view, Config save
- **Accessibility**: Keyboard navigation tests (Tab, Arrow keys, Enter)
- **Dual-mode clarity**: Manual testing with both Sim and Live data to verify color coding

**Implementation Phases:**

1. **Phase 1 (Week 1)**: Dashboard tab (metrics + positions table), basic theme
2. **Phase 2 (Week 2)**: Watchlist tab (wallets table + add wallet form + sidebar)
3. **Phase 3 (Week 3)**: Config tab (exit strategies form + risk limits)
4. **Phase 4 (Week 4)**: Polish (sidebar charts, advanced filters, responsive testing)

This design direction provides a **clear, implementable path** from UX spec to working Gradio app while respecting all constraints and supporting the core "Discover → Add → Autopilot" experience.

