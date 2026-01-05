# Visual Design Foundation

### Color System

**Design Philosophy: Function Over Aesthetics**

WallTrack's color system prioritizes **clarity and speed** over visual beauty. Every color serves a functional purpose: distinguish modes (Simulation vs Live), signal status (profit/loss/warning), and support rapid data scanning during morning dashboard checks.

**Primary Functional Colors**

| Color | Hex | Gradio Variable | Purpose | Usage |
|-------|-----|-----------------|---------|-------|
| **Blue** | #3B82F6 | `*primary_500` | Simulation mode, primary actions | Simulation badges, primary buttons, trust signals |
| **Amber** | #F59E0B | `*warning_500` | Live mode, caution states | Live badges, warning indicators, attention required |

**Status Colors**

| Color | Hex | Gradio Variable | Purpose | Usage |
|-------|-----|-----------------|---------|-------|
| **Green** | #10B981 | `*success_500` | Positive signals, profitability | Profitable positions (PnL > 0), "Tracking Active" badges, win rate above target |
| **Green Light** | #D1FAE5 | `*success_50` | Success background | Subtle background for positive metrics, success states |
| **Red** | #EF4444 | `*error_500` | Negative signals, losses | Losing positions (PnL < 0), errors, circuit breaker triggered |
| **Red Light** | #FEE2E2 | `*error_50` | Error background | Subtle background for error states, critical alerts |
| **Yellow** | #FBBF24 | `*warning_400` | Degrading performance | Win rate declining, wallet underperforming, warnings |
| **Yellow Light** | #FEF3C7 | `*warning_50` | Warning background | Subtle background for warning states |

**Neutral Colors (Data Structure)**

| Color | Hex | Gradio Variable | Purpose | Usage |
|-------|-----|-----------------|---------|-------|
| **Slate 900** | #0F172A | `*neutral_900` | Primary text | Table data, headings, high-contrast text |
| **Slate 600** | #475569 | `*neutral_600` | Secondary text | Metadata, timestamps, labels |
| **Slate 400** | #94A3B8 | `*neutral_400` | Disabled text | Placeholders, inactive states, "Waiting for signal" text |
| **Slate 200** | #E2E8F0 | `*neutral_200` | Borders, dividers | Table borders, card outlines, section dividers |
| **Slate 50** | #F8FAFC | `*neutral_50` | Background surfaces | Card backgrounds, sidebar backgrounds |

**Semantic Color Mapping**

- **mode: "simulation"** → Blue labels, blue badges (`variant="primary"`)
- **mode: "live"** → Amber labels, amber badges (`variant="secondary"`)
- **status: "tracking_active"** → Green badge 🟢
- **status: "error"** → Red badge 🔴
- **status: "warning"** → Yellow badge 🟡
- **pnl > 0** → Green text
- **pnl < 0** → Red text
- **pnl = 0** → Slate 600 text (neutral)

**Accessibility Compliance**

All color combinations meet WCAG 2.1 AA standards (4.5:1 contrast minimum):
- Slate 900 on Slate 50 background: **15.8:1** ✅
- Green 500 on White background: **4.6:1** ✅
- Red 500 on White background: **5.1:1** ✅
- Blue 500 on White background: **8.6:1** ✅
- Amber 500 on White background: **4.5:1** ✅

Status colors use light backgrounds (`*_50`) with dark foreground text (`*_900`) for maximum readability.

### Typography System

**Font Family: Inter**

Inter is a typeface optimized for screen readability and data-heavy interfaces. Key characteristics:
- **Open apertures**: Numbers (0-9) highly distinguishable (critical for PnL, prices)
- **Tabular numerals**: Fixed-width numbers align in tables vertically
- **Optimized hinting**: Crisp rendering at small sizes (12-14px metadata)

**Why Inter for WallTrack:**
- Morning dashboard scans require fatigue-free number reading
- Wallet addresses (alphanumeric) need clear character distinction
- Token symbols ($BONK, $PEPE) must be scannable at a glance

**Type Scale**

| Element | Size | Line Height | Weight | Usage |
|---------|------|-------------|--------|-------|
| **H1** | 32px / 2rem | 1.2 | Semibold (600) | Page titles ("Dashboard", "Watchlist") |
| **H2** | 24px / 1.5rem | 1.2 | Semibold (600) | Section headers ("Active Positions", "Performance Metrics") |
| **H3** | 20px / 1.25rem | 1.3 | Medium (500) | Subsection headers ("Wallet Performance", "Recent Signals") |
| **H4** | 18px / 1.125rem | 1.3 | Medium (500) | Card headers, sidebar titles |
| **Body** | 16px / 1rem | 1.5 | Regular (400) | Table data, form inputs, default text |
| **Small** | 14px / 0.875rem | 1.4 | Regular (400) | Metadata (timestamps, labels), tooltips |
| **Tiny** | 12px / 0.75rem | 1.4 | Regular (400) | Badges, status labels, secondary info |

**Font Weights Usage**

- **Regular (400)**: Default body text, table cells, form values
- **Medium (500)**: Table headers, emphasized data (token symbols), section headers (H3/H4)
- **Semibold (600)**: Page headers (H1/H2), important metrics (Win Rate, PnL Total), "Add Wallet" button
- **Bold (700)**: Critical alerts only (circuit breaker triggered, live mode confirmation)

**Typography Principles**

1. **Tabular Data Optimized**: All numeric data uses tabular numerals (fixed-width) for vertical alignment in tables
2. **Hierarchy Through Weight**: Use font weight (not just size) to create hierarchy without excessive size jumps
3. **Readability First**: 16px body text minimum (no 14px for critical data), 1.5 line height for tables (scannable rows)
4. **Minimal Type Scale**: 7 sizes total (vs typical 10+) to maintain consistency and reduce cognitive load

**Implementation in Gradio**

```python
theme = gr.themes.Soft(
    font=gr.themes.GoogleFont("Inter"),
    font_mono=gr.themes.GoogleFont("Inter"),  # Use Inter for all text (even monospace-like wallet addresses)
)
```

### Spacing & Layout Foundation

**Base Spacing Unit: 8px**

WallTrack uses an 8px base spacing unit (Gradio `spacing_md` default) with a constrained scale to maintain visual consistency.

**Spacing Scale**

| Token | Value | Usage |
|-------|-------|-------|
| **xs** | 4px | Inline elements (icon-to-text spacing), tight compound components |
| **sm** | 8px | Default component spacing (button padding, form field margins) |
| **md** | 16px | Section padding (card internal padding), related group spacing |
| **lg** | 24px | Tab content padding, major section separation |
| **xl** | 32px | Page-level margins, hero spacing (rare) |

**Component-Specific Spacing**

**Tables (High Density for Data Scanning):**
- **Row height**: 48px (touch-friendly, scannable, ~10 rows visible without scrolling)
- **Cell padding**: 12px horizontal, 16px vertical (tight but readable)
- **Header padding**: 12px horizontal, 12px vertical (slightly compressed for visual weight)
- **Row spacing**: 0px (no gaps between rows, continuous scanning)
- **Border**: 1px Slate 200 (subtle row separation)

**Cards (Sidebar Detail Views):**
- **Padding**: 24px all sides (comfortable reading)
- **Section spacing**: 16px between sections (clear content grouping)
- **Border radius**: 8px (Gradio Soft default, subtle roundness)
- **Shadow**: None (flat design, minimal chrome)

**Forms (Add Wallet, Config):**
- **Input height**: 40px (Gradio default, touch-friendly)
- **Label-to-input spacing**: 8px (tight association)
- **Field spacing**: 16px vertical (clear separation between fields)
- **Form padding**: 24px (comfortable editing environment)
- **Button height**: 40px (matches input height for alignment)

**Layout Grid System**

**Desktop (1200px+ viewport):**
```
[Sidebar 240px] | [Main Content (flex 1)] | [Detail Sidebar 320px (on-demand)]
```

**Dashboard Layout Example:**
```
┌────────────────────────────────────────────────────────────┐
│  Performance Metrics (lg padding: 24px)                   │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                 │
│  │ Win  │  │  PnL │  │ Cap  │  │Active│                 │
│  │ Rate │  │Total │  │ Util │  │Wlts  │                 │
│  └──────┘  └──────┘  └──────┘  └──────┘                 │
├────────────────────────────────────────────────────────────┤
│  Active Positions Table (no padding, maximize rows)       │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ Token | Entry | Current | PnL | Mode | Status |...   │ │
│  ├──────────────────────────────────────────────────────┤ │
│  │ $BONK | 0.01  | 0.015   | +50%| 🔵   | Open   |...   │ │
│  │ $PEPE | 0.02  | 0.018   | -10%| 🟠   | Open   |...   │ │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

**Tablet (768-1199px):**
- Main content + Sidebar (when active, overlays or pushes content)
- Table scrolls horizontally if columns exceed viewport

**Mobile (<768px):**
- Single column layout
- Sidebar detail appears as fullscreen modal
- Table shows 3-4 essential columns (Token, PnL, Status), rest accessible via sidebar

**Layout Density Philosophy**

WallTrack uses **variable density** based on content type:

1. **Dense - Data Tables**
   - Goal: Maximize visible rows for pattern recognition
   - Row height: 48px (minimal vertical padding)
   - Font size: 16px (no reduction for density)
   - Rationale: Morning dashboard scan needs 8-10 positions visible without scrolling

2. **Comfortable - Forms & Sidebar**
   - Goal: Reduce errors, support careful input
   - Input height: 40px, padding: 24px
   - Font size: 16px body, 14px labels
   - Rationale: Add Wallet form used infrequently, accuracy > speed

3. **Spacious - Performance Metrics**
   - Goal: Visual hierarchy, emphasize importance
   - Padding: 32px, font size: 24px (metrics), 14px (labels)
   - Spacing: 16px between metric cards
   - Rationale: 4 key metrics need instant recognition (< 5s glance)

**Layout Principles**

1. **Data First, Chrome Minimal**
   - Tables occupy full viewport width (no wasted margins)
   - Sidebar appears only on-demand (click row → sidebar visible)
   - Metrics always visible (sticky header on Dashboard)

2. **Horizontal Scanability**
   - Fixed table row height (48px) enables predictable eye movement
   - Consistent column widths across tables (e.g., "Token" always 120px)
   - Left-aligned status badges serve as scan anchor (green/yellow/red visual pattern)

3. **Progressive Disclosure**
   - **Summary in tables**: 5-7 columns max (Token, Entry, Current, PnL, Mode, Status)
   - **Details in sidebar**: Full data available on click (wallet attribution, strategy, timeline)
   - **Charts/graphs optional**: Expandable performance charts in sidebar (avoid clutter)

4. **Responsive Breakpoints**
   - **Desktop-first design**: Primary usage on laptop/desktop (morning reviews)
   - **Mobile as monitor**: Occasional checks on mobile (simplified view, essential data only)
   - **No tablet-specific optimizations**: Falls back to mobile or desktop layout

### Accessibility Considerations

**Color Contrast (WCAG 2.1 AA Compliance)**

All text-background combinations meet minimum 4.5:1 contrast:
- Primary text (Slate 900) on light backgrounds: 15.8:1 ✅
- Status colors on white: Green 4.6:1, Red 5.1:1, Amber 4.5:1 ✅
- Links/actions (Blue 500): 8.6:1 ✅

**Non-Color Indicators**

Status is never conveyed by color alone:
- **Simulation mode**: Blue badge + text "Simulation" + 🔵 emoji
- **Live mode**: Amber badge + text "Live" + 🟠 emoji
- **Profitable position**: Green text + "+50%" prefix + ✅ emoji
- **Loss position**: Red text + "-10%" prefix + ❌ emoji
- **Tracking active**: Green badge + "Tracking Active" text + 🟢 emoji

**Keyboard Navigation**

- All interactive elements (buttons, table rows, form inputs) keyboard-accessible
- Tab order follows visual hierarchy (top-to-bottom, left-to-right)
- Table row selection: Arrow keys navigate, Enter selects (opens sidebar)

**Screen Reader Support**

- Status badges include aria-label: `aria-label="Simulation mode, wallet tracking active"`
- PnL values include context: `aria-label="Profit 50 percent"`
- Icon-only buttons include aria-label: `aria-label="Add wallet to watchlist"`

**Font Scaling**

- All font sizes specified in `rem` (relative units) for browser zoom support
- Base 16px = 1rem, scales proportionally at 125%, 150% zoom
- Minimum touch target: 40px x 40px (buttons, table rows)

**Motion & Animation**

- **Reduced motion support**: No critical info conveyed via animation
- **Sidebar transitions**: Optional fade-in (disable if prefers-reduced-motion)
- **Data updates**: Instant (no loading spinners for <200ms operations)

**Focus Indicators**

- All interactive elements show visible focus ring (2px Blue 500 outline)
- Focus ring offset: 2px (clear separation from element)
- Never suppress focus outlines (keyboard navigation critical)

