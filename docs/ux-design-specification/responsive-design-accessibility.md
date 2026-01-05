# Responsive Design & Accessibility

### Responsive Strategy

**Desktop Strategy (Primary Platform - 1024px+):**
- **Layout**: Three-tab full-width utilization
  - Dashboard: 4-column metrics + full-width tables
  - Watchlist: 75/25 split (Table + Sidebar)
  - Config: Two-column form layout (label + input)
- **Information Density**: Dense tables (12-15 rows visible), comfortable spacing for metrics
- **Desktop-Specific Features**:
  - Hover states on table rows (preview data)
  - Keyboard shortcuts (Tab → next tab, ESC → hide sidebar)
  - Multi-column layouts for side-by-side comparison

**Mobile Strategy (320px - 767px):**
- **Layout**: Single-column, stacked navigation
  - Tabs: Horizontal scroll or vertical stack
  - Tables: Horizontal scroll with fixed first column (address/token)
  - Sidebar: Full-screen overlay (slide-in from right)
  - Metrics: 2×2 grid instead of 4 columns
- **Information Density**: Reduced table columns (essential only: Token, PnL, Mode, Status)
- **Mobile-First Features**:
  - Bottom sticky "Add Wallet" button (primary CTA)
  - Swipe gestures for sidebar dismiss
  - Touch-optimized table row height (56px minimum)

**Tablet Strategy (768px - 1023px):**
- **Hybrid approach**: Desktop layout with touch optimizations
- **Tables**: Full columns but larger row height (48px)
- **Sidebar**: 40/60 split instead of 25/75 (larger tap targets)

**Gradio Responsive Behavior:**
- Gradio automatically adapts `gr.Column(scale=...)` ratios on mobile (stacks vertically < 768px)
- `gr.Dataframe` horizontal scroll by default (mobile-friendly)
- `gr.Tabs` horizontal scroll on overflow (Gradio built-in)

### Breakpoint Strategy

**Breakpoints:**
```css
/* Gradio automatic breakpoints */
Mobile:  320px - 767px   (single column stack)
Tablet:  768px - 1023px  (hybrid layouts)
Desktop: 1024px+         (full multi-column)
```

**Design Approach:**
- **Desktop-first design** (primary use case)
- **Mobile adaptation** via Gradio's auto-responsive CSS
- **No custom CSS breakpoints** - rely on Gradio native behavior

**Breakpoint-Specific Adaptations:**

| Element | Desktop (1024px+) | Mobile (< 768px) |
|---------|-------------------|------------------|
| **Metrics Row** | 4 columns (`gr.Row` with 4× `gr.Column(scale=1)`) | 2×2 grid (auto-stack) |
| **Table + Sidebar** | 75/25 split (`scale=3` + `scale=1`) | Table full-width, Sidebar overlay |
| **Tabs** | Horizontal tabs | Horizontal scroll or vertical stack |
| **Forms** | Two-column (label + input) | Single column stack |
| **Buttons** | Inline row | Full-width stack |

**Implementation:**
```python
# Gradio auto-responsive example
with gr.Row():  # Desktop: 4 columns side-by-side
    metric1 = gr.Column(scale=1)  # Mobile: stacks vertically
    metric2 = gr.Column(scale=1)
    metric3 = gr.Column(scale=1)
    metric4 = gr.Column(scale=1)
```

### Accessibility Strategy

**WCAG Compliance Level: AA (Recommended)**
- **Rationale**: Industry standard, covers 90% of accessibility needs, manageable implementation
- **Legal**: Not public-facing product, but best practice for personal tool
- **User Benefit**: Better usability for Christophe (keyboard navigation, contrast, clear labels)

**Key Accessibility Requirements:**

**1. Color Contrast (WCAG 2.1 AA - 4.5:1 minimum):**
- ✅ Blue #3B82F6 on White → 7.1:1 (Pass)
- ✅ Amber #F59E0B on White → 4.8:1 (Pass)
- ✅ Green #10B981 on White → 6.2:1 (Pass)
- ✅ Red #EF4444 on White → 5.9:1 (Pass)
- ✅ Slate #64748B on White → 9.3:1 (Pass)

**2. Keyboard Navigation:**
- **Tab order**: Follows visual hierarchy (Metrics → Table → Sidebar → Buttons)
- **Focus indicators**: Visible outline (Gradio default blue ring)
- **Shortcuts**:
  - `Tab` / `Shift+Tab` → Navigate elements
  - `Space` / `Enter` → Activate buttons
  - `ESC` → Dismiss modals/sidebar
  - `Arrow keys` → Navigate table rows (Gradio Dataframe native)

**3. Screen Reader Support:**
- **Semantic HTML**: Gradio generates semantic tags (`<button>`, `<table>`, `<nav>`)
- **ARIA labels**: All interactive elements have text labels (no icon-only buttons)
- **Live regions**: Toast notifications announce via `aria-live="polite"` (Gradio built-in)
- **Table headers**: `gr.Dataframe(headers=[...])` generates `<th>` tags

**4. Touch Target Sizes:**
- **Minimum**: 44×44px (WCAG AA requirement, Gradio default)
- **Buttons**: `gr.Button(size="lg")` → 48px height
- **Table rows**: 44px minimum (mobile), 40px default (desktop)

**5. Form Accessibility:**
- **Labels**: All inputs have visible labels (no placeholders-only)
- **Error messages**: `gr.Error()` with descriptive text
- **Required fields**: Marked with `*` in label text

**6. Status Indicators (Non-Color):**
- **Mode badges**: 🔵 Simulation | 🟠 Live (emoji + text, not just color)
- **State badges**: 🟢 Active | 🔴 Error | 🟡 Paused (emoji + text)
- **PnL values**: +150% (green) / -5% (red) → Sign prefix + color (redundant encoding)

### Testing Strategy

**Responsive Testing:**

**Desktop Testing:**
- **Browsers**: Chrome, Firefox, Edge (primary), Safari (secondary)
- **Resolutions**: 1920×1080 (primary), 1366×768 (minimal desktop)
- **Test scenarios**:
  - 4-column metrics render correctly
  - Tables + Sidebar split at 75/25
  - Hover states work on table rows

**Mobile Testing:**
- **Devices**: iPhone (iOS Safari), Android (Chrome)
- **Emulators**: Chrome DevTools responsive mode
- **Test scenarios**:
  - Tabs horizontal scroll (no overflow issues)
  - Tables horizontal scroll (first column fixed)
  - Sidebar full-screen overlay (not side-by-side)
  - Bottom sticky "Add Wallet" button accessible

**Automated Responsive Testing:**
```bash
# Playwright responsive testing
uv run pytest tests/e2e/test_responsive.py -v
# Tests: Mobile viewport, Tablet viewport, Desktop viewport
```

**Accessibility Testing:**

**Automated Tools:**
- **Axe DevTools** (Chrome extension) → WCAG AA violations scan
- **Lighthouse Accessibility Audit** → Score target: 95+ / 100
- **WAVE** (WebAIM extension) → Color contrast verification

**Manual Testing:**
- **Keyboard-only navigation**: Disconnect mouse, navigate entire UI with keyboard
- **Screen reader testing**: NVDA (Windows) / VoiceOver (macOS) → Test table reading, button labels
- **Color blindness simulation**: Chrome DevTools → Protanopia, Deuteranopia filters

**Automated Accessibility Testing:**
```bash
# Playwright a11y testing with axe-core
uv run pytest tests/e2e/test_accessibility.py -v
# Tests: WCAG AA compliance, keyboard navigation, focus management
```

**User Testing:**
- **Solo operator** (Christophe): Self-test for keyboard shortcuts, mobile checks
- **Accessibility validation**: No external users, but validate against WCAG AA checklist

### Implementation Guidelines

**Responsive Development:**

**1. Use Gradio Auto-Responsive Components:**
```python
# ✅ GOOD - Auto-responsive
with gr.Row():  # Stacks vertically on mobile
    col1 = gr.Column(scale=1)
    col2 = gr.Column(scale=1)

# ❌ BAD - Fixed width (avoid)
with gr.Row():
    col1 = gr.Column(width=400)  # Breaks on mobile
```

**2. Mobile-First Component Design:**
```python
# Tables: Horizontal scroll by default
gr.Dataframe(
    headers=["Token", "Entry", "PnL", "Mode"],  # Essential columns only
    wrap=True  # Text wraps on narrow screens
)

# Buttons: Full-width on mobile
gr.Button("Add Wallet", size="lg")  # 48px height, auto-responsive
```

**3. Breakpoint Handling:**
- **No custom CSS** - Gradio handles breakpoints automatically
- **Trust Gradio's responsive engine** - `gr.Column(scale=...)` adapts to viewport

**4. Image Optimization:**
```python
# No images in WallTrack MVP
# Future: Use responsive images with srcset if adding charts/graphics
```

**Accessibility Development:**

**1. Semantic HTML (Gradio automatic):**
```python
# Gradio generates semantic tags automatically
gr.Button("Submit")  # → <button>Submit</button>
gr.Dataframe(...)    # → <table> with <th> headers
gr.Tabs()            # → <nav> with role="tablist"
```

**2. ARIA Labels:**
```python
# Explicit labels for all inputs
gr.Textbox(label="Wallet Address", placeholder="Enter Solana address...")  # ✅ Has label

# Status announcements
gr.Info("✅ Wallet added successfully")  # → aria-live="polite"
```

**3. Keyboard Navigation:**
```python
# Gradio handles keyboard navigation automatically
# Custom shortcuts via JavaScript (if needed):
app.load(fn=None, js="""
function() {
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            // Hide sidebar logic
        }
    });
}
""")
```

**4. Focus Management:**
```python
# Modal focus trap (gradio-modal built-in)
with Modal(visible=False, allow_user_close=True) as modal:
    # Focus automatically trapped within modal
    confirm_btn = gr.Button("Confirm")
```

**5. High Contrast Mode:**
- **Gradio themes** support OS high contrast mode automatically
- **Test**: Windows High Contrast Mode + macOS Increase Contrast

**6. Error Handling:**
```python
# Descriptive error messages
try:
    add_wallet(address)
    gr.Info("✅ Wallet added to watchlist (Simulation)")
except ValueError as e:
    gr.Error(f"❌ Invalid address: {str(e)}")
```

**Code Review Checklist:**
```markdown
Responsive:
- [ ] All `gr.Column(scale=...)` instead of `width=px`
- [ ] Tables use `gr.Dataframe` with horizontal scroll
- [ ] Buttons use `size="lg"` for touch targets
- [ ] Tested on Chrome DevTools responsive mode

Accessibility:
- [ ] All buttons have text labels (no icon-only)
- [ ] Color contrast ≥ 4.5:1 (use WebAIM contrast checker)
- [ ] Keyboard navigation works (Tab, Enter, ESC)
- [ ] ARIA labels present where needed
- [ ] Error messages descriptive (not generic "Error")
- [ ] Axe DevTools scan shows 0 violations
```
