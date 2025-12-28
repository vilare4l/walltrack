---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - 'docs/prd.md'
  - 'docs/analysis/product-brief-walltrack-2025-12-15.md'
workflowType: 'ux-design'
lastStep: 14
status: complete
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-28'
---

# UX Design Specification - WallTrack

**Author:** Christophe + Sally (UX Designer)
**Date:** 2025-12-28
**Context:** Simplified architecture aligned with 4-phase development

---

## Executive Summary

### Project Vision

WallTrack is a **strategic intelligence system** for autonomous memecoin trading. The operator must be able to:

1. **Understand** the real-time flow: Signal → Wallet → Score → Position
2. **Explore** each link with explanatory drill-down ("why this decision?")
3. **Configure** system parameters with confidence

### Target User

**Persona: Christophe — The Robot Operator**

| Attribute | Reality |
|-----------|---------|
| **Usage frequency** | Multiple times per day |
| **Primary mode** | Exploration + Understanding |
| **Critical need** | Decision traceability |
| **Core question** | "Why did the system do this?" |

**What the user actually wants:**
- "Is it running?"
- "Is it profitable?"
- "Where do these positions come from?"
- "Why was this wallet selected?"

### Key Design Challenges

1. **Opaque Flow** — User cannot trace the reasoning behind each decision
2. **Disconnected Navigation** — No contextual drill-down (click wallet → see associated signals)
3. **No Synthesis** — No "Home Dashboard" answering essential questions in 5 seconds
4. **Background Process Visibility** — "Is discovery still running?"

### Design Opportunities

1. **Explanatory Drill-Down** — Each signal/position answers "why?" in one click
2. **Contextual Navigation** — Each element (wallet, signal, position) becomes an entry point to its connections
3. **Synthetic Dashboard** — Answer "is it working?" in 5 seconds with visual KPIs
4. **Process Visibility** — Status bar showing all background processes

---

## Core UX Principles

### Principle 1: Real-Time Flow, Not Archaeology

The entry point is **current action**, not history:

```
              REAL-TIME (entry point)
                       │
                       ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  SIGNAL  │───▶│  WALLET  │───▶│  SCORE   │───▶│ POSITION │
│ Incoming │    │  Source  │    │ Decision │    │  Active  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │
      │               └──── DRILL-DOWN: "Why this wallet?"
      │                            │
      │                            ▼
      │               ┌─────────────────────────┐
      │               │ CONTEXT (info, not UI)  │
      │               │ • Discovered on pump X  │
      │               │ • Win rate 78%          │
      │               │ • Decay status: OK      │
      │               │ • Cluster with Y, Z     │
      │               └─────────────────────────┘
      │
      └──── Origin (pump) is CONTEXT INFO
            not the navigation starting point
```

### Principle 2: Two Navigation Modes

| Mode | Entry point | Question | Usage |
|------|-------------|----------|-------|
| **Operational** | Signal / Position | "Why this decision?" | Daily |
| **Exploration** | Discovery / Wallet | "What did we find?" | Occasional |

### Principle 3: Synthesis First, Details on Demand

- **Home** = answers in 5 seconds
- **Explorer** = depth on demand

---

## Architecture: 3 Pages + Sidebar

**From 8 disconnected tabs → 3 coherent spaces:**

| Space | Icon | Function | Main Content |
|-------|------|----------|--------------|
| **Home** | 🏠 | Instant synthesis | System status, P&L, alerts, active positions with drill-down |
| **Explorer** | 🔍 | Flow navigation | Signals → Wallets → Clusters with explanatory context |
| **Config** | ⚙️ | Parameters | Scoring, thresholds, webhooks, system settings |

### Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│  [gr.Navbar]  Home  |  Explorer  |  Config                      │
├─────────────────────────────────────────────────────────────────┤
│  [Status Bar - gr.HTML every=30]                                │
│  🟢 Discovery: 2h ago │ 🟢 Signals: 12 today │ 143 wallets      │
├─────────────────────────────────────────────────────────────────┤
│                                                         ┌───────┤
│  [Main Content]                                         │ Side  │
│                                                         │ bar   │
│  HOME: KPIs + Active positions (clickable)              │       │
│  EXPLORER: Tabs (Signals/Wallets/Clusters)              │ Con-  │
│  CONFIG: Settings, thresholds, webhooks                 │ text  │
│                                                         │       │
│  Click element → Sidebar opens with context             │ Sel.  │
│                                                         │       │
└─────────────────────────────────────────────────────────┴───────┘
```

---

## Core User Experience

### Defining Experience

The fundamental WallTrack experience is **instant understanding**:

| Question | Target time | Entry point |
|----------|-------------|-------------|
| "Is it running?" | < 2 sec | Home - System status |
| "Is it profitable?" | < 5 sec | Home - P&L KPIs |
| "Why this position?" | 1 click | Position → Drill-down |
| "Where does this wallet come from?" | 1 click | Wallet → Discovery context |

**Core Loop:**
```
Signal (real-time) → "Why?" → Source wallet → "Why this one?" → Score + Clusters + Decay
```

### Platform Strategy

| Aspect | Choice | Justification |
|--------|--------|---------------|
| **Platform** | Web (Gradio) | Existing infrastructure |
| **Device** | Desktop-first | Trading = large screen |
| **Input** | Mouse + Keyboard | Precision for data exploration |
| **Responsive** | Not priority | Desktop-only usage |

### Effortless Interactions

**What must be invisible:**

1. **System status** — Always visible without action (badge/indicator)
2. **Contextual navigation** — Click element = see its connections
3. **Explanatory drill-down** — Each decision answers "why?"
4. **Refresh** — Real-time, no manual refresh button

**What must be explicit:**

1. **Destructive actions** — Blacklist, stop position (confirmation)
2. **Strategy modifications** — Parameter changes (preview impact)

### Critical Success Moments

| Moment | Success criterion | Risk if failed |
|--------|-------------------|----------------|
| **Dashboard open** | "I know if it works" in 2 sec | Anxiety, over-checking |
| **Position click** | I understand the full decision chain | Loss of trust |
| **First wallet drill-down** | "Ah, I understand why it's there" | Frustration, black box feeling |

---

## Desired Emotional Response

### Primary Emotional Goals

| Emotion | Manifestation | Anti-pattern |
|---------|---------------|--------------|
| **Confidence** | "I know it's running" | Permanent doubt, over-checking |
| **Control** | "I can intervene if needed" | Helplessness facing automation |
| **Understanding** | "I know why this decision" | Opaque black box |

**Emotional hierarchy:**
1. **Serenity** — System works, I can go about my day
2. **Satisfied curiosity** — Each question finds its answer in 1 click
3. **Mastery feeling** — I understand the logic, I can adjust it

### Background Processes Visibility

**Processes to make visible:**

| Process | Critical info | Emotion if absent |
|---------|---------------|-------------------|
| **Discovery Scheduler** | Last run, next run, wallets found | "Is it still searching?" |
| **Signal Pipeline** | Signals received today, last processed | "Are webhooks arriving?" |
| **Profiling Jobs** | Wallets pending, last profiled | "Is scoring up to date?" |
| **Webhook Sync** | Wallets monitored, Helius status | "Are we watching everyone?" |

**Design implication — Permanent status bar:**

```
┌─────────────────────────────────────────────────────┐
│  🟢 Discovery: 2h ago (next: 4h)  │  143 wallets   │
│  🟢 Signals: 12 today (last: 14:32)                │
│  🟢 Webhooks: sync OK                              │
└─────────────────────────────────────────────────────┘
```

→ Answers "is it alive?" without clicking.

### Design Implications

| Target emotion | UX translation |
|----------------|----------------|
| **"It's alive"** | Background process status bar always visible |
| **Confidence** | Relative timestamps "2h ago" rather than absolute dates |
| **Understanding** | Each element clickable to its context |
| **Calm** | Clean layout, clear hierarchy, no overload |
| **Control** | Explicit actions + manual trigger buttons |
| **Satisfied curiosity** | Drill-down answers "why" in 1 level max |

### Anti-Patterns to Avoid

- ❌ Long loading spinners (anxiety)
- ❌ Tables without explanation (opacity)
- ❌ Actions without confirmation (loss of control)
- ❌ Data without temporal context (confusion)
- ❌ No feedback on background processes ("is it dead?")

---

## Page Specifications

### Page 1: Home

**Purpose:** Instant synthesis — "Is everything OK?" in 5 seconds

**Components:**

| Component | Type | Content |
|-----------|------|---------|
| **System Status** | KPI Cards | Mode (Simulation/Live), Circuit Breaker status |
| **Performance** | KPI Cards | Today P&L, Win Rate, Active Positions count |
| **Active Positions** | Clickable Table | Token, Entry, Current, P&L%, Wallet source |
| **Recent Signals** | Feed | Last 5 signals with score, clickable |
| **Alerts** | Notification area | Circuit breaker triggers, webhook failures |

**Interactions:**
- Click position → Sidebar with full context
- Click signal → Sidebar with wallet + token context
- Click alert → Sidebar with details + suggested action

### Page 2: Explorer

**Purpose:** Navigate the intelligence flow — Signals, Wallets, Clusters

**Sub-navigation:** `gr.Tabs`

| Tab | Content | Key Features |
|-----|---------|--------------|
| **Signals** | All signals received | Filter by score, date, wallet |
| **Wallets** | Tracked wallets | Filter by status, score, **decay flag** |
| **Clusters** | Wallet groups | Cluster leader, member count, avg score |

**Wallet Table Columns:**

| Column | Description |
|--------|-------------|
| Address | Truncated with copy |
| Score | Current wallet score |
| Win Rate | Historical win rate |
| **Decay Status** | 🟢 OK / 🟡 Flagged / 🔴 Downgraded |
| Signals | Count of signals generated |
| Cluster | Cluster membership |

**Decay Status Logic (from PRD):**

| Status | Condition | Visual |
|--------|-----------|--------|
| **OK** | Normal performance | 🟢 Green |
| **Flagged** | Win rate < 40% (20 trades) | 🟡 Amber + "Review" badge |
| **Downgraded** | 3 consecutive losses | 🔴 Red + reduced score |
| **Dormant** | No activity 30+ days | ⚪ Gray + "Dormant" badge |

**Interactions:**
- Click any row → Sidebar with full context
- Sidebar shows: origin discovery, metrics, cluster relations, signal history

### Page 3: Config

**Purpose:** System configuration

**Sections:**

| Section | Content |
|---------|---------|
| **Trading** | Mode (Simulation/Live), Capital, Risk % |
| **Scoring** | Threshold, Weights (Wallet 35%, Cluster 25%, Token 25%, Timing 15%) |
| **Position Sizing** | Base size, High conviction multiplier (1.5x) |
| **Circuit Breakers** | Drawdown limit (20%), Consecutive loss action |
| **Webhooks** | Helius status, Sync button |
| **Discovery** | Last run, Manual trigger, Schedule |

---

## Sidebar Specification

### Behavior

- **Position:** Right side, 380px width
- **Default:** Closed (`open=False`)
- **Trigger:** Click on any table row
- **Persistence:** Stays open across page navigation

### Context Types

**1. Position Context:**
```
┌─────────────────────────────────┐
│ Position: ABC...                │
│ ─────────────────────           │
│ Token: XYZ                      │
│ Entry: 0.0012 SOL               │
│ Current: 0.0016 SOL (+33%)      │
│ ─────────────────────           │
│ 📍 Signal Source                │
│ Wallet: xyz... (score 82%)  [→] │
│ Signal received: 2h ago         │
│ Score breakdown:                │
│ • Wallet: 0.29/0.35             │
│ • Cluster: 0.20/0.25            │
│ • Token: 0.18/0.25              │
│ • Timing: 0.12/0.15             │
│ ─────────────────────           │
│ [Close Position]                │
└─────────────────────────────────┘
```

**2. Wallet Context:**
```
┌─────────────────────────────────┐
│ Wallet: xyz...                  │
│ ─────────────────────           │
│ Score: 82%                      │
│ Win Rate: 78%                   │
│ Decay Status: 🟢 OK             │
│ ─────────────────────           │
│ 📍 Discovery Origin             │
│ Found on: Pump ABC (2025-12-15) │
│ Method: Top buyer analysis      │
│ ─────────────────────           │
│ 📊 Cluster                      │
│ Member of: Cluster #7 (5 wallets)│
│ Role: Leader                    │
│ ─────────────────────           │
│ [Blacklist] [Re-profile]        │
└─────────────────────────────────┘
```

**3. Signal Context:**
```
┌─────────────────────────────────┐
│ Signal: ABC...                  │
│ ─────────────────────           │
│ Token: XYZ                      │
│ Score: 0.82                     │
│ Received: 2h ago                │
│ Status: Position created        │
│ ─────────────────────           │
│ 📍 Source Wallet                │
│ Wallet: xyz... (score 82%)  [→] │
│ ─────────────────────           │
│ Score Breakdown:                │
│ • Wallet: 0.29/0.35             │
│ • Cluster: 0.20/0.25            │
│ • Token: 0.18/0.25              │
│ • Timing: 0.12/0.15             │
│ ─────────────────────           │
│ [View Position] [View Wallet]   │
└─────────────────────────────────┘
```

---

## Gradio Implementation

### Component Architecture

```python
import gradio as gr

with gr.Blocks(theme=gr.themes.Soft()) as app:
    # Global navbar
    gr.Navbar(main_page_name="WallTrack", value=[
        ("Home", "/"),
        ("Explorer", "/explorer"),
        ("Config", "/config"),
    ])

    # Status bar - auto-refresh 30s
    gr.HTML(render_status_bar, every=30, elem_id="status-bar")

    # Global sidebar - context display
    with gr.Sidebar(position="right", width=380, open=False):
        selected_context = gr.State(None)
        context_display = gr.Markdown("Select an element...")
        with gr.Accordion("Actions", open=True):
            action_buttons = gr.Column()  # Dynamic based on context

@app.route("/")
def home_page():
    with gr.Row():
        # KPI Cards
        gr.HTML(render_kpis)
    with gr.Row():
        # Active positions table
        positions_table = gr.Dataframe(
            headers=["Token", "Entry", "Current", "P&L%", "Wallet"],
            elem_id="positions-table"
        )
        positions_table.select(fn=show_position_context, outputs=[context_display])
    with gr.Row():
        # Recent signals
        signals_feed = gr.Dataframe(elem_id="signals-feed")

@app.route("/explorer")
def explorer_page():
    with gr.Tabs():
        with gr.Tab("Signals"):
            signals_table = gr.Dataframe(elem_id="all-signals")
        with gr.Tab("Wallets"):
            wallets_table = gr.Dataframe(
                headers=["Address", "Score", "Win Rate", "Decay", "Signals", "Cluster"],
                elem_id="wallets-table"
            )
        with gr.Tab("Clusters"):
            clusters_table = gr.Dataframe(elem_id="clusters-table")

@app.route("/config")
def config_page():
    with gr.Accordion("Trading", open=True):
        mode = gr.Radio(["Simulation", "Live"], label="Mode")
        capital = gr.Number(label="Capital (SOL)")
    with gr.Accordion("Scoring", open=True):
        threshold = gr.Slider(0.5, 1.0, value=0.70, label="Score Threshold")
    # ... more config sections
```

### CSS Design Tokens

```css
:root {
  /* Status Colors */
  --status-healthy: #10b981;
  --status-warning: #f59e0b;
  --status-error: #ef4444;
  --status-neutral: #6b7280;
  --status-dormant: #9ca3af;

  /* Semantic Colors */
  --color-positive: #10b981;
  --color-negative: #ef4444;
  --color-info: #3b82f6;

  /* Decay Status */
  --decay-ok: #10b981;
  --decay-flagged: #f59e0b;
  --decay-downgraded: #ef4444;
  --decay-dormant: #9ca3af;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;

  /* Typography */
  --font-mono: monospace;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
}

/* Status Indicators */
.status-healthy { color: var(--status-healthy); }
.status-warning { color: var(--status-warning); }
.status-error { color: var(--status-error); }

/* Decay Badges */
.decay-ok { background: var(--decay-ok); color: white; }
.decay-flagged { background: var(--decay-flagged); color: white; }
.decay-downgraded { background: var(--decay-downgraded); color: white; }
.decay-dormant { background: var(--decay-dormant); color: white; }

/* Metric Display */
.metric-positive { color: var(--color-positive); font-weight: 600; }
.metric-negative { color: var(--color-negative); font-weight: 600; }
```

---

## User Journeys

### Journey 1: Status Check (Daily)

```
Christophe opens WallTrack
        ↓
Status bar visible immediately
🟢 Discovery OK │ 🟢 12 signals │ 3 positions
        ↓
"It's running" ✓ (< 2 sec)
        ↓
Optional: click position → sidebar context
```

### Journey 2: Explanatory Drill-Down

```
Sees a position on Home
        ↓
Clicks the row
        ↓
Sidebar opens:
• Token: ABC...
• Wallet: xyz... (score 82%) ← clickable
• Why this wallet?
  - Discovered on pump XYZ
  - Win rate 78%
  - Decay: 🟢 OK
  - Cluster with 3 others
        ↓
Understands the decision ✓
        ↓
Optional: [Blacklist] [View Wallet]
```

### Journey 3: Wallet Exploration with Decay Check

```
Navbar → Explorer
        ↓
Tab "Wallets"
        ↓
Sees table with Decay column
🟢 OK | 🟡 Flagged | 🔴 Downgraded
        ↓
Filters by "Flagged" to review
        ↓
Clicks flagged wallet → Sidebar context
        ↓
Sees: "Win rate dropped to 38% over last 20 trades"
        ↓
Decision: [Blacklist] or wait
```

---

## Alignment with PRD

### 4 Phases Coverage

| Phase | UX Support |
|-------|------------|
| **Phase 1: Discovery** | Explorer tab (Wallets, Clusters), Discovery status in status bar |
| **Phase 2: Signal Pipeline** | Signals tab, Home positions, Drill-down context |
| **Phase 3: Order Management** | Home positions with P&L, Config for exit strategies |
| **Phase 4: Live** | Mode toggle in Config, visual distinction Live vs Simulation |

### 11 Features Visibility

| Feature | Where visible |
|---------|---------------|
| Token Discovery | Status bar "Discovery: Xh ago" |
| Token Surveillance | Status bar "next: Xh" |
| Wallet Discovery | Explorer → Wallets tab |
| Wallet Profiling | Sidebar wallet context (score, metrics) |
| **Wallet Decay Detection** | Wallets table Decay column + Sidebar |
| Clustering | Explorer → Clusters tab + Sidebar relations |
| Helius Webhooks | Config → Webhooks section |
| Signal Scoring | Sidebar score breakdown |
| Position Management | Home positions table |
| Order Entry | Positions with entry price |
| Order Exit | Positions with current/P&L |

### Execution Modes

| Mode | Visual Indicator |
|------|------------------|
| **Simulation** | Status bar: "🔵 SIMULATION MODE" |
| **Live** | Status bar: "🟢 LIVE" with capital balance |

---

## Implementation Priority

### P0 (MVP)

| Component | Why critical |
|-----------|--------------|
| Status bar auto-refresh | "Is it alive?" |
| Navbar 3 pages | Core navigation |
| Sidebar drill-down | Core experience |
| Clickable tables | Entry point for context |
| Decay column in Wallets | Wallet health visibility |

### P1 (Next)

| Component | Why important |
|-----------|---------------|
| Actions in sidebar | Blacklist, re-profile |
| Keyboard shortcuts | Power user efficiency |
| Advanced filters | Data exploration |
| Performance charts | Visual P&L trends |

---

## Document Status

**UX Design Specification - WallTrack**
- Date: 2025-12-28
- Author: Christophe + Sally (UX Designer)
- Status: Complete
- Aligned with: PRD (4 phases, 11 features)

Ready for wireframe creation.
