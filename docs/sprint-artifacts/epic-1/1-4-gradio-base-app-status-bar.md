# Story 1.4: Gradio Base App & Status Bar

**Status:** done
**Epic:** 1 - Foundation & Core Infrastructure
**Created:** 2025-12-29
**Sprint Artifacts:** docs/sprint-artifacts/epic-1/

---

## Story

**As an** operator,
**I want** to see the application running with a status bar,
**So that** I know the system is alive at a glance.

---

## ⚠️ VERIFY BEFORE IMPLEMENTATION

**Run these checks FIRST before writing any code:**

```bash
# 1. Check Gradio version (must be 5.x)
uv run python -c "import gradio; print(f'Gradio version: {gradio.__version__}')"

# 2. Check if gr.Sidebar exists
uv run python -c "import gradio as gr; print(f'Sidebar exists: {hasattr(gr, \"Sidebar\")}')"

# 3. Test demo.route() works (create minimal test)
uv run python -c "
import gradio as gr
with gr.Blocks() as demo:
    gr.Markdown('Home')
with demo.route('Test', '/test'):
    gr.Markdown('Test Page')
print('Route API works!')
"

# 4. Check mount_gradio_app signature
uv run python -c "import gradio as gr; help(gr.mount_gradio_app)"
```

**If any check fails, research Gradio 5.x docs before proceeding.**

---

## Acceptance Criteria

### AC1: Gradio App with Theme
- [x] `src/walltrack/ui/app.py` with `gr.Blocks(theme=gr.themes.Soft())`
- [x] App mounts on FastAPI at `/dashboard` path
- [x] Uses CSS design tokens from UX spec (status colors, spacing)
- [x] CSS file loads correctly (verify in browser dev tools)

### AC2: Multipage Navigation with Routes
- [x] 3 pages: Home (`/dashboard`), Explorer (`/dashboard/explorer`), Settings (`/dashboard/settings`)
- [x] Uses `demo.route()` pattern for multipage (NOT gr.Tabs)
- [x] Each page accessible via direct URL
- [x] Navigation links between pages work
- Note: Changed from `/config` to `/settings` because 'config' is reserved by Gradio 6

### AC3: Status Bar with Auto-Refresh
- [x] Status bar component with 30-second auto-refresh
- [x] Shows: Mode, Discovery status, Signals count, Webhooks status, Wallet count
- [x] Uses relative timestamps ("2h ago" not "14:32:00")
- [x] Status indicators: `🟢` healthy, `🟡` warning, `🔴` error
- [x] Displays mode: `🔵 SIMULATION` or `🟢 LIVE`

### AC4: Basic Page Placeholders
- [x] Home page: "System Status" placeholder
- [x] Explorer page: placeholder with 3 sections (Signals, Wallets, Clusters)
- [x] Config page: placeholder with accordion sections
- [x] Each page shows clear "Coming in Story X.X" messages

### AC5: Sidebar Structure (if gr.Sidebar exists)
- [x] Verify `gr.Sidebar` API exists in Gradio 6.x (yes, it exists)
- [x] If exists: `gr.Sidebar(position="right", open=False)` - using native component
- [x] If NOT exists: use `gr.Column` with CSS for sidebar behavior - not needed
- [x] Placeholder context display area
- [x] "Actions" section at bottom

### AC6: Integration Tests
- [x] Gradio app loads without errors
- [x] Status bar renders correctly
- [x] Navigation between pages works
- [x] FastAPI `/api/health` still works after Gradio mount
- [x] Database lifespan events still fire on startup/shutdown

---

## Tasks / Subtasks

### Task 1: Verify Gradio APIs (AC: 1, 2, 5) - DO FIRST
- [ ] 1.1 Run all verification commands from "VERIFY BEFORE IMPLEMENTATION"
- [ ] 1.2 Document which APIs exist/don't exist
- [ ] 1.3 If `gr.Sidebar` doesn't exist, plan CSS alternative
- [ ] 1.4 If `demo.route()` doesn't work, research correct multipage pattern

### Task 2: Create Gradio App Structure (AC: 1, 2)
- [ ] 2.1 Create `src/walltrack/ui/app.py` with `create_dashboard()`
- [ ] 2.2 Implement `gr.Blocks(theme=gr.themes.Soft())` wrapper
- [ ] 2.3 Add multipage routing with `demo.route()`
- [ ] 2.4 Create `src/walltrack/ui/css/tokens.css` with design tokens
- [ ] 2.5 Verify CSS loads correctly

### Task 3: Implement Status Bar (AC: 3)
- [ ] 3.1 Create `src/walltrack/ui/components/status_bar.py`
- [ ] 3.2 Implement `render_status_bar()` returning HTML string
- [ ] 3.3 Implement auto-refresh mechanism (research correct Gradio 5.x pattern)
- [ ] 3.4 Create `get_relative_time()` utility function
- [ ] 3.5 Fetch status from `/api/health` endpoint

### Task 4: Create Page Placeholders (AC: 4)
- [ ] 4.1 Create `src/walltrack/ui/pages/home.py`
- [ ] 4.2 Create `src/walltrack/ui/pages/explorer.py`
- [ ] 4.3 Create `src/walltrack/ui/pages/config.py`
- [ ] 4.4 Wire pages with `demo.route()`

### Task 5: Implement Sidebar (AC: 5)
- [ ] 5.1 Based on Task 1 verification, implement sidebar
- [ ] 5.2 If `gr.Sidebar`: use native component
- [ ] 5.3 If no `gr.Sidebar`: use `gr.Column` + CSS positioning
- [ ] 5.4 Add placeholder context and actions area

### Task 6: FastAPI Integration (AC: 1, 6)
- [ ] 6.1 Update `main.py` with correct Gradio mount pattern
- [ ] 6.2 Verify lifespan events still work (DB connections)
- [ ] 6.3 Test both `/api/health` and `/dashboard` work
- [ ] 6.4 Test startup/shutdown logs appear

### Task 7: Testing (AC: 6)
- [ ] 7.1 Create `tests/unit/ui/__init__.py`
- [ ] 7.2 Create `tests/unit/ui/test_status_bar.py`
- [ ] 7.3 Create `tests/integration/test_dashboard.py`
- [ ] 7.4 Run `uv run pytest tests/ -v`

---

## Dev Notes

### Files to CREATE
```
src/walltrack/ui/
├── app.py                  # Main Gradio app with routes
├── css/
│   └── tokens.css          # Design tokens
├── components/
│   ├── __init__.py
│   ├── status_bar.py       # Status bar component
│   └── sidebar.py          # Sidebar component
└── pages/
    ├── __init__.py
    ├── home.py             # Home page
    ├── explorer.py         # Explorer page
    └── config.py           # Config page

tests/unit/ui/
├── __init__.py
└── test_status_bar.py
```

### Files to UPDATE
- `src/walltrack/main.py` - Mount Gradio at `/dashboard`

### Architecture Rules

| Rule | Requirement |
|------|-------------|
| Layer | `ui/` = Gradio components ONLY |
| Data fetching | Call `/api/health` endpoint, NOT direct DB access |
| State | Use `gr.State` for sidebar context |
| CSS | Load from package path using `Path(__file__)` |

---

## Technical Patterns

### Gradio Multipage App Pattern (app.py)

```python
"""Main Gradio dashboard application."""

from pathlib import Path
import gradio as gr

from walltrack.ui.components.status_bar import create_status_bar
from walltrack.ui.pages import home, explorer, config

CSS_PATH = Path(__file__).parent / "css" / "tokens.css"


def create_dashboard() -> gr.Blocks:
    """Create the WallTrack dashboard with multipage routing."""

    # Load CSS
    custom_css = CSS_PATH.read_text() if CSS_PATH.exists() else ""

    with gr.Blocks(
        theme=gr.themes.Soft(),
        title="WallTrack",
        css=custom_css
    ) as app:
        # Status bar at top (shared across all pages)
        create_status_bar()

        # Home page content
        home.render()

    # Additional pages via routing
    with app.route("Explorer", "/explorer"):
        create_status_bar()  # Repeat status bar on each page
        explorer.render()

    with app.route("Config", "/config"):
        create_status_bar()
        config.render()

    return app
```

### Status Bar Pattern (status_bar.py)

```python
"""Status bar component with auto-refresh."""

from datetime import datetime, timezone
import gradio as gr
import httpx


def get_relative_time(dt: datetime) -> str:
    """Convert datetime to relative string like '2h ago'."""
    now = datetime.now(timezone.utc)
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    else:
        return f"{int(seconds / 86400)}d ago"


def fetch_status() -> dict:
    """Fetch status from health endpoint (sync for Gradio)."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("http://localhost:8000/api/health")
            return response.json()
    except Exception:
        return {"status": "error", "databases": {}}


def render_status_html() -> str:
    """Render status bar as HTML string."""
    status = fetch_status()

    # Determine overall health
    db_healthy = status.get("status") == "ok"
    health_icon = "🟢" if db_healthy else "🔴"

    return f"""
    <div id="status-bar" style="
        display: flex;
        gap: 24px;
        padding: 8px 16px;
        background: #f8fafc;
        border-bottom: 1px solid #e2e8f0;
        font-size: 0.875rem;
        flex-wrap: wrap;
    ">
        <span>🔵 <strong>SIMULATION</strong></span>
        <span>{health_icon} System: {status.get('status', 'unknown')}</span>
        <span>🟢 Discovery: --</span>
        <span>🟢 Signals: 0 today</span>
        <span>📊 0 wallets</span>
    </div>
    """


def create_status_bar() -> gr.HTML:
    """Create status bar with auto-refresh."""
    return gr.HTML(
        value=render_status_html,
        every=30,  # Refresh every 30 seconds
        elem_id="status-bar"
    )
```

### FastAPI Mount Pattern (main.py update)

```python
# Add these imports at top of main.py
import gradio as gr
from walltrack.ui.app import create_dashboard

# Update create_app() function - add AFTER existing code, BEFORE return
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        description="Autonomous Trading Intelligence for Solana Memecoins",
        version=settings.app_version,
        lifespan=lifespan,
    )

    # Register API routes
    application.include_router(health.router, prefix="/api")

    # Mount Gradio dashboard
    # ⚠️ Mount AFTER registering API routes
    dashboard = create_dashboard()
    application = gr.mount_gradio_app(
        app=application,
        blocks=dashboard,
        path="/dashboard"
    )

    return application
```

### Sidebar Alternative (if gr.Sidebar doesn't exist)

```python
"""Sidebar using gr.Column + CSS if gr.Sidebar unavailable."""

def create_sidebar_column() -> tuple[gr.Column, gr.Markdown]:
    """Create sidebar using Column with CSS positioning."""

    with gr.Column(
        elem_id="sidebar",
        visible=False,  # Start hidden
        scale=0,
        min_width=380
    ) as sidebar:
        context = gr.Markdown("Select an element...")
        gr.Markdown("### Actions")
        gr.Markdown("*Actions will appear here*")

    return sidebar, context

# CSS to add for sidebar positioning
SIDEBAR_CSS = """
#sidebar {
    position: fixed;
    right: 0;
    top: 0;
    height: 100vh;
    width: 380px;
    background: white;
    border-left: 1px solid #e2e8f0;
    padding: 16px;
    overflow-y: auto;
    z-index: 1000;
}
"""
```

### CSS Design Tokens (tokens.css)

```css
:root {
  /* Status Colors */
  --status-healthy: #10b981;
  --status-warning: #f59e0b;
  --status-error: #ef4444;
  --status-neutral: #6b7280;

  /* Mode Colors */
  --mode-simulation: #3b82f6;
  --mode-live: #10b981;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
}

#status-bar {
  display: flex;
  gap: var(--space-lg);
  padding: var(--space-sm) var(--space-md);
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.875rem;
}
```

---

## UX Requirements (from ux-design-specification.md)

### Status Bar Content

| Element | Format | Example |
|---------|--------|---------|
| Mode | Badge | `🔵 SIMULATION` or `🟢 LIVE` |
| System | Health status | `🟢 System: ok` |
| Discovery | Relative time | `🟢 Discovery: 2h ago` |
| Signals | Today count | `🟢 Signals: 12 today` |
| Wallets | Count | `📊 143 wallets` |

### Navigation Structure

```
/dashboard          → Home (default)
/dashboard/explorer → Explorer page
/dashboard/config   → Config page
```

---

## Test Requirements

| Test Case | Expected |
|-----------|----------|
| Gradio app creates | No exceptions |
| Status bar renders | Valid HTML returned |
| `get_relative_time("2h ago")` | Correct formatting |
| Page routes exist | 3 routes registered |
| FastAPI mount | `/dashboard` accessible |
| Health endpoint | `/api/health` still returns 200 |
| Lifespan fires | Startup/shutdown logs appear |

---

## Previous Story Patterns

| Pattern | Source | Usage |
|---------|--------|-------|
| `get_settings()` | Story 1-1 | Get mode (simulation/live) |
| Health endpoint | Story 1-2 | `/api/health` for status |
| structlog | Story 1-2 | Log dashboard events |
| httpx sync | New | Fetch status (sync for Gradio) |

---

## Dependencies

### Required Gradio Version
```toml
# pyproject.toml - already present
gradio>=5.0.0
```

### Story Dependencies
- Story 1.1: Project structure (`ui/` folder exists)
- Story 1.2: Health endpoint (`/api/health`) for status data

---

## Success Criteria

**Story DONE when:**
1. All "VERIFY BEFORE IMPLEMENTATION" checks pass
2. `http://localhost:8000/dashboard` loads Gradio app
3. Status bar shows with 30s auto-refresh
4. Navigation to `/dashboard/explorer` and `/dashboard/config` works
5. `/api/health` still works (not broken by Gradio mount)
6. `uv run pytest tests/ -v` passes
7. Startup logs show DB connections still working

---

_Story generated by SM Agent (Bob) - 2025-12-29_
_Quality Competition fixes applied - Gradio 5.x API verified_
