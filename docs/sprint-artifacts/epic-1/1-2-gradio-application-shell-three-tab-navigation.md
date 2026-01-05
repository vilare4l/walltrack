# Story 1.2: Gradio Application Shell & Three-Tab Navigation

Status: ready-for-dev

## Story

As an operator,
I want a functional Gradio application with three-tab navigation (Dashboard, Watchlist, Config),
So that I can access different sections of the system and validate the overall UI structure.

## Acceptance Criteria

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

## Tasks / Subtasks

### Task 1: Setup Gradio Project Structure (AC: All)
- [ ] **1.1** Create `src/walltrack/ui/` directory if not exists
  - Verify directory structure: `src/walltrack/ui/`
  - This will contain all Gradio UI code
  - Future stories will add `components/`, `utils/` subdirectories
- [ ] **1.2** Create `src/walltrack/ui/__init__.py` (empty file)
  - Makes `ui` a Python package
  - Allows imports like `from walltrack.ui import app`
- [ ] **1.3** Add Gradio dependency to project
  - Check if `gradio` is in `pyproject.toml`
  - If not, run: `uv add gradio`
  - This will install latest stable Gradio (5.x as of Jan 2025)

### Task 2: Create Custom Theme Module (AC: #1)
- [ ] **2.1** Create `src/walltrack/ui/theme.py`
  - Define `create_walltrack_theme()` function
  - Use `gr.themes.Soft` as base (per architecture docs)
  - Customize colors: Blue primary (Simulation), Amber secondary (Live), Slate neutral
  - Set font: Inter (Google Font)
- [ ] **2.2** Configure theme tokens for consistency
  - `primary_hue="blue"` (Simulation actions, #3B82F6)
  - `secondary_hue="slate"` (Neutral elements)
  - `neutral_hue="slate"` (Background, borders)
  - `font=gr.themes.GoogleFont("Inter")` (Modern sans-serif)
- [ ] **2.3** Set custom color overrides for Live mode actions
  - `button_secondary_background_fill="*warning_500"` (Amber #F59E0B for Live buttons)
  - `stat_background_fill="*warning_50"` (Amber highlights for Live metrics)
  - Ensure accessibility: WCAG 2.1 AA contrast (4.5:1 minimum)
- [ ] **2.4** Add theme docstring explaining color semantics
  - Blue = Simulation mode (safe, default)
  - Amber = Live mode (warning, requires confirmation)
  - Green = Success states
  - Red = Error states

### Task 3: Create Main Gradio Application (AC: #1, #2, #3, #4, #5)
- [ ] **3.1** Create `src/walltrack/ui/app.py` with basic structure
  - Import Gradio: `import gradio as gr`
  - Import custom theme: `from walltrack.ui.theme import create_walltrack_theme`
  - Define `create_app()` function that returns `gr.Blocks` instance
- [ ] **3.2** Implement three-tab structure using `gr.Tabs()` and `gr.Tab()`
  - Create `gr.Blocks()` with custom theme
  - Use `with gr.Tabs():` context for tab container
  - Create three tabs: "Dashboard", "Watchlist", "Config" (in that order)
  - Each tab uses `with gr.Tab("TabName"):` context
- [ ] **3.3** Add placeholder content to each tab
  - **Dashboard**: `gr.Markdown("Dashboard content will appear here")`
  - **Watchlist**: `gr.Markdown("Watchlist content will appear here")`
  - **Config**: `gr.Markdown("Config content will appear here")`
  - Ensure exact placeholder text matches acceptance criteria
- [ ] **3.4** Add WallTrack title header above tabs
  - Use `gr.Markdown("# WallTrack")` or `gr.HTML("<h1>WallTrack</h1>")`
  - Position: Top of application, before tabs
  - Style: Large heading (H1), center-aligned
- [ ] **3.5** Configure launch settings
  - Server name: `0.0.0.0` (accessible from localhost and network)
  - Server port: `7860` (default Gradio port, matches AC)
  - Share: `False` (local development only)
  - Debug: `True` (show detailed errors during development)

### Task 4: Implement Application Entry Point (AC: #1)
- [ ] **4.1** Add `if __name__ == "__main__":` block to `app.py`
  - Call `create_app()` to get Gradio Blocks instance
  - Call `.launch()` with configured parameters
  - Ensure app starts immediately when running `python src/walltrack/ui/app.py`
- [ ] **4.2** Configure `.launch()` parameters
  - `server_name="0.0.0.0"` (listen on all interfaces)
  - `server_port=7860` (matches acceptance criteria URL)
  - `share=False` (no public Gradio link)
  - `debug=True` (enable detailed error messages)
  - `show_api=False` (hide API documentation for MVP)
- [ ] **4.3** Add optional environment variable support for port
  - Read `UI_PORT` from environment (from .env: `UI_PORT=7865`)
  - Fallback to 7860 if not set
  - Note: .env shows 7865, but AC requires 7860 - use AC value for now

### Task 5: Test Application Locally (AC: All)
- [ ] **5.1** Run application: `uv run python src/walltrack/ui/app.py`
  - Verify terminal output shows: "Running on local URL: http://127.0.0.1:7860"
  - Verify browser auto-opens at http://127.0.0.1:7860
  - Check for any startup errors in terminal
- [ ] **5.2** Test tab navigation functionality
  - Click each tab (Dashboard, Watchlist, Config) in order
  - Verify blue underline indicator appears on active tab
  - Verify placeholder content displays correctly in each tab
  - Click tabs in random order, verify switching is smooth
- [ ] **5.3** Verify browser console has no errors
  - Open browser DevTools (F12)
  - Check Console tab for JavaScript errors
  - Expected: No red error messages
  - If theme bug occurs (known Gradio issue), verify tabs still function
- [ ] **5.4** Test graceful shutdown
  - Press Ctrl+C in terminal
  - Verify app stops cleanly
  - Verify no "port already in use" error on restart

### Task 6: Verify Theme Application Across Tabs (AC: #5)
- [ ] **6.1** Visual inspection of theme consistency
  - Check if all tabs use same theme (Soft with Blue primary)
  - Verify tab underline color matches primary blue (#3B82F6)
  - Check background colors consistent across tabs
- [ ] **6.2** Test for known Gradio theme bug
  - Switch between tabs multiple times
  - Check if theme degrades on second/third tabs
  - Document if bug occurs (known issue: [GitHub #10436](https://github.com/gradio-app/gradio/issues/10436))
  - If bug occurs, note as limitation and continue (not blocking for MVP)

### Task 7: Create Basic E2E Test (AC: All)
- [ ] **7.1** Create `tests/e2e/test_ui_tabs.py` (if test infrastructure exists)
  - Use Playwright to launch app
  - Navigate to http://127.0.0.1:7860
  - Verify page title contains "WallTrack"
  - Verify 3 tabs visible: Dashboard, Watchlist, Config
- [ ] **7.2** Test tab switching via Playwright
  - Click Dashboard tab → verify "Dashboard content will appear here"
  - Click Watchlist tab → verify "Watchlist content will appear here"
  - Click Config tab → verify "Config content will appear here"
  - Verify no console errors
- [ ] **7.3** Add screenshot capture for visual regression
  - Capture screenshot of each tab
  - Save to `tests/e2e/screenshots/` (for future visual comparison)
  - Optional: Use Playwright's `expect(page).to_have_screenshot()` if desired

### Task 8: Document Application Structure (AC: #1, #5)
- [ ] **8.1** Update CLAUDE.md with new UI structure
  - Document `src/walltrack/ui/` directory purpose
  - Explain app.py entry point
  - Explain theme.py module
  - Note that this is MVP UI shell (content in future stories)
- [ ] **8.2** Add README.md to `src/walltrack/ui/` (optional)
  - Explain UI architecture (Gradio-based)
  - Document how to run: `uv run python src/walltrack/ui/app.py`
  - Explain tab structure and purpose of each tab
  - Link to Epic 1 stories for roadmap
- [ ] **8.3** Add completion notes to this story file
  - List all created files
  - Document any deviations from plan
  - Note any issues encountered and resolutions
  - Update sprint-status.yaml to mark story as done

## Dev Notes

### Architectural Patterns to Follow

**Critical Architecture Decisions:**
- **[UX-001]** Notion-Inspired Tab Navigation - Flat structure, no deep hierarchies (3 main tabs only)
- **[UX-002]** Gradio Native Components Only - No custom JavaScript/React components (maintainability)
- **[UX-003]** Database-First UI Philosophy - UI directly reflects Supabase schema (transparency)
- **[UX-004]** Progressive Disclosure - Summary visible (tabs), details on-demand (future sidebars)

**Design Patterns Applied:**
1. **Tab-Based Navigation** (Notion pattern) - 3 top-level tabs for operator workflow phases
2. **Custom Theme Singleton** (UX consistency) - Single theme instance, consistent color semantics
3. **Placeholder Pattern** (MVP) - Stub content in each tab, replaced in future stories

### Technology Stack

**Gradio Framework (Latest as of Jan 2025):**
- **Version**: Gradio 5.0+ (installed via `uv add gradio`)
- **Theme System**: `gr.themes.Soft` with custom color tokens
- **Built-in Themes**: `Base()`, `Default()`, `Origin()` (we use `Soft`)
- **Known Bug**: Theme may not apply to all tabs ([GitHub #10436](https://github.com/gradio-app/gradio/issues/10436))
  - **Mitigation**: Test theme on all tabs, document if occurs
  - **Impact**: Visual inconsistency (non-blocking for MVP)

**Theme Configuration:**
```python
# src/walltrack/ui/theme.py
import gradio as gr

def create_walltrack_theme():
    """Create WallTrack custom theme with Notion-inspired colors"""
    theme = gr.themes.Soft(
        primary_hue="blue",      # Simulation mode actions (#3B82F6)
        secondary_hue="slate",   # Neutral elements
        neutral_hue="slate",     # Backgrounds, borders
        font=gr.themes.GoogleFont("Inter"),  # Modern sans-serif
    ).set(
        # Custom overrides for Live mode (Amber warnings)
        button_secondary_background_fill="*warning_500",  # Amber #F59E0B
        stat_background_fill="*warning_50",  # Amber highlights
        color_accent_soft="*success_50",  # Green success states
        error_background_fill="*error_50",  # Red error states
    )
    return theme
```

**Application Structure:**
```python
# src/walltrack/ui/app.py
import gradio as gr
from walltrack.ui.theme import create_walltrack_theme

def create_app():
    """Create main Gradio application with 3-tab navigation"""
    theme = create_walltrack_theme()

    with gr.Blocks(theme=theme, title="WallTrack") as app:
        # Title header
        gr.Markdown("# WallTrack")

        # Three-tab structure
        with gr.Tabs():
            with gr.Tab("Dashboard"):
                gr.Markdown("Dashboard content will appear here")

            with gr.Tab("Watchlist"):
                gr.Markdown("Watchlist content will appear here")

            with gr.Tab("Config"):
                gr.Markdown("Config content will appear here")

    return app

if __name__ == "__main__":
    app = create_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,  # Matches AC (not .env port 7865)
        share=False,
        debug=True,
        show_api=False
    )
```

### File Structure Requirements

**Files to Create:**
```
src/walltrack/ui/
├── __init__.py          # Empty package marker (Task 1.2)
├── theme.py             # Custom theme module (Task 2)
└── app.py               # Main Gradio application (Task 3-4)
```

**Test Files to Create (if E2E infrastructure exists):**
```
tests/e2e/
├── test_ui_tabs.py      # Playwright E2E test (Task 7)
└── screenshots/         # Visual regression screenshots
```

**IMPORTANT:** This story does NOT create FastAPI backend. That comes in later stories. This is UI shell only.

### Previous Story Intelligence (Story 1.1 Learnings)

**What Worked Well:**
- ✅ Directory creation with `mkdir -p` (works cross-platform)
- ✅ V2 rebuild context clear: `src/` is new codebase, `legacy/` is docs only
- ✅ PowerShell commands work with proper syntax
- ✅ Verification queries useful for testing

**Patterns to Reuse:**
- Create directory structure first: `mkdir -p src/walltrack/ui`
- Test immediately after implementation: Run app → verify output
- Document deviations: If .env port (7865) conflicts with AC port (7860), use AC value and document

**Potential Issues to Avoid:**
- **Port conflicts**: If port 7860 already in use, app won't start
  - **Solution**: Check with `netstat -an | findstr 7860` before running
  - **Fallback**: Use port 7865 from .env if 7860 fails
- **Theme bug**: Gradio may not apply theme to all tabs (known issue)
  - **Solution**: Test on all tabs, document if occurs, non-blocking for MVP
- **Browser auto-open**: May fail in headless environments (Docker, SSH)
  - **Solution**: Add `inbrowser=False` parameter if needed

**Git Intelligence (Story 1.1 Commits):**
- Story 1.1 created 12 files (migrations + docs)
- Used consistent naming: `NNN_description.sql` pattern
- Followed V2 rebuild structure: Created files in `src/`, not `legacy/`
- PowerShell-specific syntax handled correctly

### Latest Technical Information (Web Research Jan 2025)

**Gradio 5.0 Updates:**
- **New Default Theme**: Vibrant orange primary (we override with Blue via `Soft` theme)
- **Theme Setup**: Pass `theme=` to `gr.Blocks(theme=...)` constructor
- **Tab Context Manager**: Use `with gr.Tab('name'):` for tab content
- **Known Issue**: Monochrome/custom themes may not apply to all tabs ([GitHub #10436](https://github.com/gradio-app/gradio/issues/10436))
  - **Impact**: If bug occurs, tabs 2-3 may use default theme instead of custom
  - **Mitigation**: Test theme on all tabs, document if occurs
  - **Not Blocking**: Functionality still works, only visual inconsistency

**Gradio Best Practices (2025):**
- Use `gr.Blocks()` for custom layouts (not `gr.Interface()`)
- Pass `title="AppName"` to set browser tab title
- Use `gr.Markdown()` for rich text content (supports emoji, formatting)
- Use `gr.Tab()` within `gr.Tabs()` for multi-tab layouts
- Set `debug=True` during development for detailed error messages
- Use `show_api=False` to hide API docs for user-facing apps

**Sources:**
- [Gradio Themes Guide](https://www.gradio.app/guides/themes)
- [Gradio Blocks Docs](https://www.gradio.app/4.44.1/docs/gradio/blocks)
- [Theming Guide](https://www.gradio.app/guides/theming-guide)
- [Controlling Layout](https://www.gradio.app/guides/controlling-layout)
- [GitHub Issue #10436](https://github.com/gradio-app/gradio/issues/10436) - Theme bug with multiple tabs

### Testing Standards

**Manual Testing Checklist:**
```bash
# 1. Start application
uv run python src/walltrack/ui/app.py

# Expected output:
# Running on local URL:  http://127.0.0.1:7860
# Browser should auto-open

# 2. Visual verification
# - See "WallTrack" title at top
# - See 3 tabs: Dashboard, Watchlist, Config
# - Dashboard tab selected by default (blue underline)
# - Placeholder text visible: "Dashboard content will appear here"

# 3. Tab navigation test
# - Click Watchlist tab
#   → Tab becomes active (blue underline)
#   → Placeholder: "Watchlist content will appear here"
# - Click Config tab
#   → Tab becomes active (blue underline)
#   → Placeholder: "Config content will appear here"
# - Click Dashboard tab again
#   → Tab becomes active (blue underline)
#   → Original placeholder visible

# 4. Browser console check
# - Open DevTools (F12)
# - Check Console tab
# - Verify: No red error messages

# 5. Shutdown test
# - Press Ctrl+C in terminal
# - Verify: Clean shutdown
# - Restart app
# - Verify: No "port in use" error
```

**E2E Test Structure (Playwright):**
```python
# tests/e2e/test_ui_tabs.py
import pytest
from playwright.sync_api import Page, expect

def test_gradio_app_loads(page: Page):
    """Test Gradio app launches and displays 3 tabs"""
    page.goto("http://127.0.0.1:7860")

    # Verify title
    expect(page).to_have_title("WallTrack")

    # Verify tabs visible
    expect(page.locator("text=Dashboard")).to_be_visible()
    expect(page.locator("text=Watchlist")).to_be_visible()
    expect(page.locator("text=Config")).to_be_visible()

def test_tab_navigation(page: Page):
    """Test clicking tabs shows correct placeholder content"""
    page.goto("http://127.0.0.1:7860")

    # Click Watchlist tab
    page.click("text=Watchlist")
    expect(page.locator("text=Watchlist content will appear here")).to_be_visible()

    # Click Config tab
    page.click("text=Config")
    expect(page.locator("text=Config content will appear here")).to_be_visible()

    # Click Dashboard tab
    page.click("text=Dashboard")
    expect(page.locator("text=Dashboard content will appear here")).to_be_visible()
```

**Verification Queries (None for this story - UI only):**
Story 1.1 used SQL verification queries. Story 1.2 is UI-only, no database queries needed.

### Project Structure Notes

**V2 Rebuild Context (CRITICAL):**
- `legacy/` contains V1 code - **DO NOT MODIFY** - reference only
- `src/walltrack/` is being built incrementally - Story 1.1 created `data/`, Story 1.2 creates `ui/`
- Future stories will add: `services/`, `workers/`, `core/` directories
- UI is independent module - runs standalone without backend (for now)

**Alignment with Planned Architecture:**
```
src/walltrack/
├── data/              # ✅ Created in Story 1.1 (migrations, models, repos)
├── ui/                # 🆕 THIS STORY creates UI module
│   ├── __init__.py    # Package marker
│   ├── theme.py       # Custom Gradio theme
│   ├── app.py         # Main application entry point
│   └── components/    # Future: Reusable UI components (Story 1.3+)
├── services/          # Future: API clients (Helius, Jupiter, etc.)
├── workers/           # Future: Background workers (Epic 2+)
├── core/              # Future: Business logic, exceptions
└── main.py            # Future: FastAPI application (Epic 2+)
```

**Why UI Before Backend:**
Epic 1 validates UI structure with mock data (from Story 1.1) before connecting live services (Epic 2+). This allows operator to see complete UI layout and navigation flow before implementing business logic.

### References

**Source Documents (Critical to review):**
- [Epic 1 Story 1.2](docs/epics/epic-1-data-foundation-ui-framework.md#story-12) - Complete acceptance criteria
- [Component Architecture](docs/architecture/component-architecture.md) - Gradio UI port, FastAPI structure
- [UX Pattern Analysis](docs/ux-design-specification/ux-pattern-analysis-inspiration.md) - Notion-inspired patterns, tab navigation
- [UX Consistency Patterns](docs/ux-design-specification/ux-consistency-patterns.md) - Button hierarchy, theme, feedback patterns
- [Story 1.1 Completed](docs/sprint-artifacts/epic-1/1-1-database-schema-migration-mock-data.md) - Database ready with mock data

**Gradio Documentation (Latest 2025):**
- [Gradio Themes Guide](https://www.gradio.app/guides/themes) - Theme customization
- [Gradio Blocks Docs](https://www.gradio.app/4.44.1/docs/gradio/blocks) - Blocks API reference
- [Controlling Layout](https://www.gradio.app/guides/controlling-layout) - Tabs, columns, rows
- [GitHub Issue #10436](https://github.com/gradio-app/gradio/issues/10436) - Known theme bug with multiple tabs

**UX Design Principles (Applied):**
- **Transparency Builds Trust** - Clear tab labels, visible navigation
- **Effortless Interactions** - 1-click tab switching, no deep hierarchies
- **Data Over Gut Feeling** - Structured layout for future data displays
- **Progressive Disclosure** - Placeholder content (summary), future sidebars (details)

## Dev Agent Record

### Context Reference

<!-- Story context created by Scrum Master (Bob) via *create-story workflow -->
<!-- Mode: YOLO (automated, no elicitation) -->

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

- Sprint Status: `docs/sprint-artifacts/sprint-status.yaml`
- Epic File: `docs/epics/epic-1-data-foundation-ui-framework.md`
- Architecture Docs: `docs/architecture/component-architecture.md`
- UX Docs: `docs/ux-design-specification/`
- Previous Story: `docs/sprint-artifacts/epic-1/1-1-database-schema-migration-mock-data.md`

### Completion Notes List

**Story Context Engine Analysis Completed:**
- ✅ Loaded Epic 1 Story 1.2 with complete acceptance criteria (BDD format)
- ✅ Loaded Component Architecture (Gradio port 7865, FastAPI structure)
- ✅ Loaded UX Pattern Analysis (Notion-inspired tab navigation)
- ✅ Loaded UX Consistency Patterns (Theme, buttons, feedback)
- ✅ Loaded Story 1.1 completion notes (database ready, learnings extracted)
- ✅ Web research completed: Gradio 5.0 latest, theme setup, known bug
- ✅ Identified V2 rebuild context: `src/` is new codebase, `ui/` module created in this story
- ✅ Identified critical patterns: Tab-based navigation (Notion), Gradio native components, custom theme
- ✅ Identified tech stack: Gradio 5.0+, `gr.themes.Soft`, Inter font, Blue/Amber color scheme
- ✅ Created 8 tasks with detailed subtasks for complete implementation
- ✅ Provided code examples for theme.py and app.py
- ✅ Provided manual testing checklist and E2E test structure
- ✅ Documented known Gradio theme bug and mitigation strategy

**Ultimate Developer Implementation Guide Created:**
This story file contains EVERYTHING needed to implement the Gradio UI shell without errors, omissions, or architectural violations. The developer now has:
- Complete task breakdown (8 tasks, 25+ subtasks)
- Exact file paths and structure (`src/walltrack/ui/`)
- Full code examples for theme.py and app.py
- Manual testing checklist and E2E test structure
- Known bug documentation with mitigation
- All UX patterns and architecture decisions referenced
- Previous story learnings applied (V2 rebuild, PowerShell syntax)
- Latest Gradio 5.0 best practices included

**Next Step:** Developer executes `dev-story` workflow to implement all tasks and mark story as done.

### File List

**Files to be created by developer:**
- `src/walltrack/ui/__init__.py` (empty package marker)
- `src/walltrack/ui/theme.py` (custom Gradio theme)
- `src/walltrack/ui/app.py` (main application entry point)
- `tests/e2e/test_ui_tabs.py` (optional Playwright test)
- `tests/e2e/screenshots/` (optional visual regression)
