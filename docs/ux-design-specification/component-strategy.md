# Component Strategy

### Design System Components

**Gradio Native Components:**
WallTrack s'appuie sur les composants natifs Gradio `v4.0+` pour garantir stabilité et maintenabilité:

- **Structure**: `gr.Tabs` (3 tabs), `gr.Column/Row` (layout grid), `gr.Accordion` (expansion)
- **Data Display**: `gr.Dataframe` (tables interactives), `gr.Markdown` (content riche), `gr.JSON` (debug)
- **Form Controls**: `gr.Textbox`, `gr.Dropdown`, `gr.Button`, `gr.Radio`, `gr.Slider`
- **Feedback Built-in**: `gr.Info()`, `gr.Warning()`, `gr.Error()` ([alert modals](https://www.gradio.app/guides/alerts))

**Custom Components (PyPI):**
- **[gradio-modal](https://pypi.org/project/gradio-modal/)** `v0.1.0`: Popup modal pour confirmations critiques (promote to Live, close position)
  ```bash
  pip install gradio-modal
  ```

**Aucun gap critique identifié** - l'écosystème Gradio couvre 100% de nos besoins UX.

### Custom Components

**1. MetricCard (Composite)**
- **Purpose**: Afficher une métrique clé dashboard (Win Rate, PnL, Positions, Signals)
- **Composition**: `gr.Column` + 3× `gr.Markdown` (titre, valeur principale, breakdown Sim/Live)
- **States**: Default, Updated (via `.update()`)
- **Variants**: Single value, Dual-mode breakdown
- **Accessibility**: Hiérarchie h3 → valeur → détail

**2. WalletCard (Composite)**
- **Purpose**: Afficher détail wallet dans sidebar
- **Composition**: `gr.Column` + `gr.Markdown` (address, win_rate, pnl, mode badge)
- **States**: Default, Loading (emoji spinner)
- **Variants**: Compact (liste), Detailed (sidebar)
- **Accessibility**: Semantic headings, emoji + text status

**3. ConfirmationDialog (gradio-modal)**
- **Purpose**: Confirmer actions critiques Live mode
- **Composition**: `Modal(visible=False)` + `gr.Markdown` (message) + 2× `gr.Button` (annuler/confirmer)
- **States**: Hidden, Visible
- **Variants**: Info (🔵), Warning (🟡), Danger (🔴) via emoji
- **Accessibility**: Focus trap, ESC close, click-outside dismiss, `allow_user_close=True`
- **Interaction**:
  ```python
  show_btn.click(lambda: Modal(visible=True), None, modal)
  confirm_btn.click(execute_action, inputs, outputs)
  ```

**4. StatusBadge (Markdown)**
- **Purpose**: Indicateur visuel mode/state/health
- **Composition**: `gr.Markdown` avec emoji + text
- **Variants**:
  - **Mode**: 🔵 Simulation | 🟠 Live
  - **State**: 🟢 Active | 🟡 Paused | 🔴 Error
  - **Health**: ✅ OK | ⚠️ Degraded | ❌ Down
- **Accessibility**: Emoji + text (pas juste couleur)

### Component Implementation Strategy

**Architecture Pattern:**
```python
# walltrack/ui/components/__init__.py
def create_metric_card(title, value, sim_value, live_value):
    with gr.Column(scale=1, elem_classes=["metric-card"]) as card:
        gr.Markdown(f"### {title}")
        gr.Markdown(f"**{value}**", elem_classes=["metric-value"])
        gr.Markdown(f"🔵 {sim_value} | 🟠 {live_value}")
    return card

# Usage in dashboard.py
from walltrack.ui.components import create_metric_card

with gr.Row():
    win_rate_card = create_metric_card("Win Rate", "60%", "65% Sim", "55% Live")
    pnl_card = create_metric_card("PnL Total", "+150%", "+80% Sim", "+70% Live")
```

**Design Tokens Integration:**
- Tous les composants utilisent le custom theme `gr.themes.Soft` avec tokens sémantiques
- Couleurs: `*primary_500` (blue sim), `*warning_500` (amber live), `*success_500`, `*error_500`
- Spacing: Via `gr.Column(scale=...)` et `gr.Row()` (8px base unit)

**Testing Strategy:**
- Unit tests: Tester les factories Python (input → output HTML structure)
- Integration tests: Tester les interactions (click → modal visible)
- E2E tests: Playwright pour user journeys complets

### Implementation Roadmap

**Phase 1 - Core Components (MVP - Semaine 1):**
- `create_metric_card()` - Dashboard 4 metrics
- `create_status_badge()` - Mode/State indicators
- `create_wallet_card()` - Sidebar detail view
- **Delivery**: Dashboard tab fonctionnel avec métriques + statuts

**Phase 2 - Interaction Components (Semaine 2):**
- `create_confirmation_dialog()` (gradio-modal) - Live mode safety
- `gr.Info()` / `gr.Warning()` integration - Toast feedback
- **Delivery**: Add wallet flow + Promote to Live flow sécurisés

**Phase 3 - Enhancement (Future):**
- TableFilters composite (`gr.Dropdown` + `gr.Textbox`) - Watchlist filtering
- ChartCard (`gr.Plot`) - Performance graphs (si demandé)
- **Delivery**: Optimisations UX post-MVP

**Priorisation:** Phase 1 + 2 couvrent 100% des user journeys critiques (< 30s workflows).