# Design System Foundation

### Design System Choice

**Selected Approach: Custom Gradio Theme (gr.themes.Soft-based)**

WallTrack utilise un thème Gradio personnalisé basé sur `gr.themes.Soft`, offrant l'équilibre optimal entre rapidité de développement et contrôle des aspects visuels critiques pour un outil de trading intelligence.

**Core Theme Components:**

- **Base Theme**: `gr.themes.Soft` - optimisé pour lisibilité de données
- **Primary Hue**: Blue - évoque confiance et professionnalisme
- **Secondary Hue**: Slate - neutre, minimise distraction
- **Custom Variables**: Couleurs dual-mode et statuts métier

### Rationale for Selection

**1. Technical Constraints Alignment**

- Gradio natif uniquement → thème Gradio natif
- Solo operator → configuration simple, pas de design system externe
- Python-centric stack → configuration programmatique directe

**2. Speed vs Control Trade-off**

- **Speed**: `gr.themes.Soft` fournit defaults éprouvés (accessibilité, responsive, contraste)
- **Control**: Customization ciblée des couleurs critiques (dual-mode, statuts)
- **Balance**: 30 lignes de config vs 0 lignes (default) ou 500+ lignes (full custom)

**3. Dual-Mode Visual Distinction**

- **Simulation Mode**: Blue/cyan tones (évoque "test", "sandbox")
- **Live Mode**: Orange/amber accents (évoque "attention", "real money")
- **Status Indicators**:
  - Green: Positive signals, profitable positions
  - Yellow: Warnings, degrading performance
  - Red: Errors, losses, circuit breakers

**4. Data Readability Priority**

- High-density data displays (tables, metrics dashboards)
- `gr.themes.Soft` optimized for text/number legibility
- Light background with high contrast text
- Generous whitespace for scanning

**5. Future-Proof Flexibility**

- Easy to adjust colors without touching component code
- Can migrate to fully custom theme later if needed
- Gradio theme API stable and well-documented

### Implementation Approach

**Theme Module Structure:**

```python
# src/walltrack/ui/theme.py

import gradio as gr

def create_walltrack_theme():
    """
    Creates WallTrack custom Gradio theme.

    Design Principles:
    - Clarity over aesthetics
    - Dual-mode visual distinction
    - Status color consistency
    - Data readability first
    """
    theme = gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),  # Clean, readable
        spacing_size=gr.themes.sizes.spacing_md,
        radius_size=gr.themes.sizes.radius_sm,
    ).set(
        # Dual-mode colors (applied via component props)
        button_primary_background_fill="*primary_500",
        button_secondary_background_fill="*warning_500",

        # Status colors
        color_accent_soft="*success_50",
        stat_background_fill="*warning_50",
        error_background_fill="*error_50",

        # Table/data optimization
        table_border_color="*neutral_200",
        table_row_focus="*primary_50",
    )

    return theme

# Usage in app
# with gr.Blocks(theme=create_walltrack_theme()) as app:
```

**Color System Documentation:**

| Color Variable | Usage | RGB/Hex |
|---|---|---|
| `*primary_500` | Simulation buttons, primary actions | Blue #3B82F6 |
| `*warning_500` | Live mode indicators, caution states | Amber #F59E0B |
| `*success_50/500` | Profitable positions, positive signals | Green #10B981 |
| `*error_50/500` | Losses, errors, circuit breakers | Red #EF4444 |
| `*neutral_200` | Borders, dividers | Slate #E2E8F0 |

**Component-Level Application:**

```python
# Example: Dual-mode button styling
with gr.Row():
    if mode == "simulation":
        execute_btn = gr.Button("Execute (Simulation)", variant="primary")
    else:
        execute_btn = gr.Button("Execute (LIVE)", variant="secondary")

# Example: Status-based metric display
with gr.Row():
    if win_rate >= 0.60:
        gr.Markdown(f"✅ **Win Rate: {win_rate:.1%}**")
    elif win_rate >= 0.50:
        gr.Markdown(f"⚠️ **Win Rate: {win_rate:.1%}**")
    else:
        gr.Markdown(f"❌ **Win Rate: {win_rate:.1%}**")
```

**Integration Points:**

1. **Application Bootstrap**: `src/walltrack/ui/app.py` imports and applies theme
2. **Component Library**: `src/walltrack/ui/components/` use theme variables via props
3. **Status Displays**: Health indicators, signal badges use theme status colors
4. **Mode Switching**: UI updates button variants based on `mode` config

### Customization Strategy

**MVP Phase (Current):**

- ✅ Base `gr.themes.Soft` theme
- ✅ Dual-mode color distinction (blue simulation, amber live)
- ✅ Status color palette (green/yellow/red)
- ✅ Typography (Inter font)
- ⬜ Fine-tuning spacing/radius if needed

**Post-MVP Enhancements:**

1. **Dark Mode** (optional, low priority)
   - Create `create_walltrack_theme_dark()` variant
   - User preference toggle in Config tab
   - Preserves dual-mode distinction with adjusted luminance

2. **Advanced Status Colors** (if signals complexity increases)
   - Gradations beyond green/yellow/red
   - Signal strength visualization (opacity, saturation)

3. **Custom CSS Overrides** (only if Gradio theme API insufficient)
   - Inject via `gr.Blocks(css="...")`
   - Target specific classes for fine control
   - Document all overrides for maintenance

**Non-Goals (YAGNI):**

- ❌ External design system (Material, Ant, etc.) - incompatible avec Gradio natif
- ❌ Component library beyond Gradio - adds complexity, no benefit
- ❌ Complex theming engine - solo operator, simple is better
- ❌ Brand identity system - internal tool, function > form

**Maintenance Approach:**

- **Version Pin**: Pin Gradio version to avoid breaking theme changes
- **Theme File Ownership**: `theme.py` is single source of truth
- **Color Constants**: Document all custom colors with purpose
- **Test Theme**: Visual regression testing via Playwright screenshots (Dashboard, Watchlist, Config tabs)

