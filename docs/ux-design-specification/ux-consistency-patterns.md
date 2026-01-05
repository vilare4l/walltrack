# UX Consistency Patterns

### Button Hierarchy

**When to Use:**
- Primary actions: Confirm, Execute (simulation), Save
- Secondary actions: Execute Live (danger variant), Promote to Live
- Tertiary actions: Cancel, View details, Refresh

**Visual Design:**
```python
# Primary (Blue) - Simulation actions, Safe operations
gr.Button("Add to Watchlist", variant="primary")  # Blue #3B82F6

# Secondary (Amber) - Live mode actions, Warning context
gr.Button("Promote to Live", variant="secondary")  # Amber #F59E0B

# Tertiary (Slate) - Navigation, Cancel
gr.Button("Cancel", variant="stop")  # Neutral slate
```

**Behavior:**
- **Simulation buttons**: Direct execution, toast feedback (`gr.Info("Wallet added to simulation")`)
- **Live buttons**: Always require confirmation modal before execution
- **Loading states**: Button becomes disabled with text "Processing..." during async operations

**Accessibility:**
- All buttons have clear text labels (no icon-only buttons)
- Keyboard navigation: Tab order follows visual hierarchy (Primary → Secondary → Tertiary)
- Focus indicators: Visible outline on keyboard focus

**Mobile Considerations:**
- Minimum touch target: 44px height (Gradio default)
- Button text wraps on narrow screens (via `gr.Button(..., size="lg")`)

**Variants:**
- **Default**: Blue primary, Amber secondary
- **Danger context** (Live confirmations): Red primary `variant="primary"` with red emoji 🔴
- **Disabled state**: Automatically styled by Gradio with reduced opacity

### Feedback Patterns

**When to Use:**
- **Toast (gr.Info/Warning)**: Quick feedback for non-blocking actions (< 3s duration)
- **Status Badge**: Persistent state display (Mode, Health, Position status)
- **Confirmation Modal**: Blocking feedback before critical actions (Live mode)

**Visual Design:**
```python
# Toast Notifications
gr.Info("✅ Wallet added to watchlist (Simulation)")  # Success
gr.Warning("⚠️ Position closed with -5% PnL")  # Warning
gr.Error("❌ Failed to connect to RPC")  # Error

# Status Badges (Markdown)
gr.Markdown("🔵 Simulation")  # Mode: Simulation
gr.Markdown("🟠 Live")  # Mode: Live
gr.Markdown("🟢 Active | 🔴 Error | 🟡 Paused")  # State badges

# Confirmation Modal
with Modal(visible=False) as confirm_modal:
    gr.Markdown("## 🔴 Promote to Live Mode?")
    gr.Markdown("This will trade with **real capital**. Are you sure?")
```

**Behavior:**
- **Toast duration**: 3-5s auto-dismiss (Gradio default)
- **Modal persistence**: User must explicitly confirm or cancel (ESC key, X button, or click outside)
- **Badge updates**: Real-time via `.update()` on state changes

**Accessibility:**
- Toasts: Announce via ARIA live region (Gradio built-in)
- Modals: Focus trap, keyboard navigation (Enter = confirm, ESC = cancel)
- Badges: Emoji + text (not color-only, WCAG 2.1 AA compliant)

**Mobile Considerations:**
- Toasts: Full-width on mobile (Gradio auto-responsive)
- Modals: Bottom sheet style on narrow screens (Gradio default behavior)

**Variants:**
- **Success**: ✅ Green emoji + `gr.Info()`
- **Warning**: ⚠️ Amber emoji + `gr.Warning()`
- **Error**: ❌ Red emoji + `gr.Error()`
- **Info**: 🔵 Blue emoji + `gr.Info()`

### Navigation Patterns

**When to Use:**
- **Tabs** (`gr.Tabs`): Top-level navigation between Dashboard, Watchlist, Config
- **Table → Sidebar**: Drill-down from list view to detail view
- **Accordion** (`gr.Accordion`): Expand/collapse sections in Config tab

**Visual Design:**
```python
# Tab Navigation
with gr.Tabs() as tabs:
    with gr.Tab("Dashboard"):  # Default selected
        # Dashboard content
    with gr.Tab("Watchlist"):
        # Watchlist content
    with gr.Tab("Config"):
        # Config content

# Table → Sidebar Pattern
with gr.Row():
    positions_table = gr.Dataframe(scale=3)  # 75% width

    with gr.Column(scale=1, visible=False) as detail_sidebar:
        gr.Markdown("## Position Detail")
        # Detail content

# Event: Click row → Show sidebar
positions_table.select(
    fn=lambda row: gr.Column(visible=True),
    outputs=detail_sidebar
)
```

**Behavior:**
- **Tabs**: Click to switch, active tab highlighted (Gradio default blue underline)
- **Sidebar**: Appears on right with smooth transition (Gradio automatic)
- **Accordion**: Click header to expand/collapse, only one open at a time

**Accessibility:**
- Tabs: Arrow keys navigate between tabs, Space/Enter to activate
- Sidebar: ESC key hides sidebar, returns focus to table
- Accordion: Keyboard navigation with Space/Enter to toggle

**Mobile Considerations:**
- **Tabs**: Horizontal scroll on narrow screens (Gradio responsive)
- **Sidebar**: Overlays table at 100% width on mobile (< 768px)
- **Accordion**: Full-width expand/collapse

**Variants:**
- **Default Navigation**: Tabs for top-level, Table → Sidebar for drill-down
- **Simplified Navigation** (mobile): Single column layout, tabs stack vertically

### Modal Patterns

**When to Use:**
- **Confirmation**: Before destructive/critical actions (Promote to Live, Close position)
- **Form Input**: Not used in WallTrack MVP (Add wallet uses inline form)
- **Detail View**: Not used (sidebar pattern preferred for details)

**Visual Design:**
```python
from gradio_modal import Modal

# Confirmation Modal Structure
with Modal(visible=False, allow_user_close=True) as confirm_modal:
    # Header with emoji context
    gr.Markdown("## 🔴 Confirmer l'Action?")

    # Body with detailed warning
    action_description = gr.Markdown()

    # Button row (Cancel + Confirm)
    with gr.Row():
        cancel_btn = gr.Button("Annuler", variant="secondary")
        confirm_btn = gr.Button("Confirmer", variant="primary")

# Trigger modal
promote_btn.click(
    fn=lambda: Modal(visible=True),
    outputs=confirm_modal
)
```

**Behavior:**
- **Show**: Click trigger button → Modal appears with backdrop
- **Dismiss**: ESC key, X button, or click outside (if `allow_user_close=True`)
- **Confirm**: Execute action → Modal hides → Toast feedback
- **Cancel**: Modal hides → No action taken

**Accessibility:**
- **Focus trap**: Tab cycles only within modal (Gradio Modal built-in)
- **Keyboard**: ESC to cancel, Enter to confirm (primary button)
- **Screen readers**: Modal title announced on show

**Mobile Considerations:**
- **Full-screen modal** on narrow screens (< 768px)
- **Bottom sheet style** with swipe-down to dismiss (gradio-modal default)

**Variants:**
- **Info Modal**: 🔵 Blue header, informational content
- **Warning Modal**: 🟡 Amber header, caution required
- **Danger Modal**: 🔴 Red header, destructive action (Live mode)

### Empty States

**When to Use:**
- **No data**: Watchlist empty, No active positions, No signals today
- **First-time setup**: Fresh install, No config set
- **Error state**: Failed to load data, RPC disconnected

**Visual Design:**
```python
# Empty Watchlist
with gr.Column(elem_classes=["empty-state"]):
    gr.Markdown("### 📭 No Wallets in Watchlist")
    gr.Markdown("Add your first smart money wallet to start tracking.")
    add_wallet_btn = gr.Button("+ Add Wallet", variant="primary")

# No Active Positions
gr.Markdown("### 💤 No Active Positions")
gr.Markdown("Positions will appear here when wallets make trades.")

# Error State
gr.Markdown("### ❌ Failed to Load Data")
gr.Markdown("Check your RPC connection in Config tab.")
retry_btn = gr.Button("Retry", variant="secondary")
```

**Behavior:**
- **Empty data**: Show helpful message + CTA button (if applicable)
- **Error state**: Show error message + Retry button + Link to Config
- **No CTA needed**: Informational empty states (e.g., "No signals today")

**Accessibility:**
- Clear heading (h3) for screen readers
- Descriptive text explaining why empty
- Actionable CTA with verb ("Add Wallet" not "Click here")

**Mobile Considerations:**
- **Center-aligned** empty states on mobile
- **Full-width CTA buttons** for easy tapping

**Variants:**
- **Empty + CTA**: Watchlist, Config sections
- **Empty + Informational**: No signals, No errors today
- **Error + Retry**: Failed data loads, RPC issues

### Loading States

**When to Use:**
- **Table refresh**: Fetching latest positions/wallets/signals
- **Metric update**: Recalculating dashboard metrics
- **Form submission**: Adding wallet, Adjusting strategy

**Visual Design:**
```python
# Table Loading
positions_table = gr.Dataframe(
    value=[[" ⏳ Loading positions..."]],  # Placeholder row
    headers=["Status"]
)

# Metric Card Loading
gr.Markdown("### Win Rate")
gr.Markdown("**⏳ Calculating...**")

# Button Loading
submit_btn = gr.Button("Adding...", interactive=False)  # During async operation
```

**Behavior:**
- **Immediate feedback**: Show loading state within 100ms of user action
- **Skeleton loaders**: Table shows "Loading..." row instead of blank
- **Button states**: Disabled + text change ("Submit" → "Submitting...")
- **Completion**: Replace loading state with actual data + toast confirmation

**Accessibility:**
- **ARIA live region**: Announce "Loading" state to screen readers
- **Loading text**: Visible text, not just spinners
- **Timeout handling**: If > 10s, show error + Retry option

**Mobile Considerations:**
- **Full-width loading indicators** on mobile
- **Touch-friendly Retry buttons** if timeout occurs

**Variants:**
- **Inline loading** (table rows, metrics): ⏳ emoji + "Loading..." text
- **Button loading**: Disabled state + "Processing..." text
- **Full-screen loading** (initial app load): Gradio default loading overlay

### Design System Integration

**Custom Theme Integration:**
Tous les patterns utilisent le custom theme `gr.themes.Soft` avec tokens sémantiques:

```python
# walltrack/ui/theme.py
def create_walltrack_theme():
    theme = gr.themes.Soft(
        primary_hue="blue",      # Simulation actions
        secondary_hue="slate",   # Neutral/tertiary
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),
    ).set(
        button_primary_background_fill="*primary_500",  # Blue
        button_secondary_background_fill="*warning_500",  # Amber (Live)
        color_accent_soft="*success_50",  # Green success states
        stat_background_fill="*warning_50",  # Amber highlights
        error_background_fill="*error_50",  # Red error states
    )
    return theme
```

**Pattern → Component Mapping:**
- **Button Hierarchy**: `gr.Button(variant="primary|secondary|stop")`
- **Feedback Toast**: `gr.Info()`, `gr.Warning()`, `gr.Error()` (native Gradio)
- **Feedback Modal**: `gradio-modal` (PyPI package)
- **Status Badge**: `gr.Markdown()` with emoji + color text
- **Navigation**: `gr.Tabs`, `gr.Accordion`, `gr.Column(visible=...)`
- **Empty States**: `gr.Markdown()` with structured content
- **Loading States**: `gr.Dataframe()` placeholders, `gr.Button(interactive=False)`

**Accessibility Compliance:**
- All patterns meet **WCAG 2.1 AA** (4.5:1 contrast minimum)
- Keyboard navigation for all interactive elements
- Screen reader support via semantic HTML (Gradio automatic)
- Focus indicators visible on all focusable elements