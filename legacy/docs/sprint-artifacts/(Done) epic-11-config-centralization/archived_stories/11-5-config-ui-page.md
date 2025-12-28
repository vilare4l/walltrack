# Story 11.5: Configuration UI Page

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 8
- **Depends on**: Story 11-4 (Config API)

## User Story

**As a** system operator,
**I want** une page Config complète dans le dashboard,
**So that** je peux visualiser et modifier toutes les configurations.

## Acceptance Criteria

### AC 1: Tabbed Navigation
**Given** je navigue vers la page Config
**When** elle se charge
**Then** je vois des onglets pour chaque domaine:
- Trading | Scoring | Discovery | Cluster | Risk | Exit | API

### AC 2: Config Display
**Given** je suis sur un onglet
**When** je regarde le contenu
**Then** je vois:
- Badge du status actuel (Active, Draft, Default)
- Version number
- Tableau des paramètres avec nom, valeur, description
- Bouton "Edit" (crée un draft si aucun)

### AC 3: Edit Mode
**Given** je clique sur "Edit"
**When** le mode édition s'active
**Then** les champs deviennent éditables
**And** je vois un bouton "Save Draft"
**And** je vois un bouton "Discard"

### AC 4: Save Draft
**Given** j'ai modifié des valeurs
**When** je clique sur "Save Draft"
**Then** les modifications sont sauvegardées
**And** un toast confirme la sauvegarde
**And** je reste en mode édition

### AC 5: Activate Draft
**Given** un draft existe avec des modifications
**When** je clique sur "Activate"
**Then** une confirmation est demandée
**And** après confirmation, la config devient active
**And** un toast confirme l'activation
**And** je repasse en mode lecture

### AC 6: Discard Draft
**Given** je suis en mode édition
**When** je clique sur "Discard"
**Then** une confirmation est demandée
**And** après confirmation, le draft est supprimé
**And** je repasse en mode lecture avec la config active

## Technical Specifications

### Config Page

**src/walltrack/ui/pages/config.py:**
```python
"""Configuration management page."""

import gradio as gr
from typing import Optional


def create_config_page():
    """Create the configuration management page."""

    with gr.Column() as config_page:
        gr.Markdown("# Configuration")

        # Status bar
        with gr.Row():
            current_status = gr.Textbox(
                label="Status",
                value="Active",
                interactive=False,
                scale=1
            )
            current_version = gr.Number(
                label="Version",
                precision=0,
                interactive=False,
                scale=1
            )
            last_updated = gr.Textbox(
                label="Last Updated",
                interactive=False,
                scale=2
            )

        # Tabs for each config domain
        with gr.Tabs() as config_tabs:
            # Trading Tab
            with gr.TabItem("Trading") as trading_tab:
                trading_content = create_trading_config_tab()

            # Scoring Tab
            with gr.TabItem("Scoring") as scoring_tab:
                scoring_content = create_scoring_config_tab()

            # Discovery Tab
            with gr.TabItem("Discovery") as discovery_tab:
                discovery_content = create_discovery_config_tab()

            # Cluster Tab
            with gr.TabItem("Cluster") as cluster_tab:
                cluster_content = create_cluster_config_tab()

            # Risk Tab
            with gr.TabItem("Risk") as risk_tab:
                risk_content = create_risk_config_tab()

            # Exit Tab
            with gr.TabItem("Exit") as exit_tab:
                exit_content = create_exit_config_tab()

            # API Tab
            with gr.TabItem("API") as api_tab:
                api_content = create_api_config_tab()

    return config_page


def create_trading_config_tab():
    """Create trading configuration tab content."""

    with gr.Column() as tab_content:
        # Position Sizing Section
        gr.Markdown("### Position Sizing")

        with gr.Row():
            base_position_pct = gr.Number(
                label="Base Position %",
                info="Percentage of capital per trade",
                precision=2,
                interactive=False
            )
            max_position_sol = gr.Number(
                label="Max Position (SOL)",
                info="Maximum position size",
                precision=4,
                interactive=False
            )
            min_position_sol = gr.Number(
                label="Min Position (SOL)",
                info="Minimum position size",
                precision=4,
                interactive=False
            )

        with gr.Row():
            sizing_mode = gr.Dropdown(
                choices=["risk_based", "fixed_percent"],
                label="Sizing Mode",
                interactive=False
            )
            risk_per_trade_pct = gr.Number(
                label="Risk Per Trade %",
                info="For risk-based sizing",
                precision=2,
                interactive=False
            )
            high_conviction_mult = gr.Number(
                label="High Conviction Multiplier",
                precision=2,
                interactive=False
            )

        # Thresholds Section
        gr.Markdown("### Thresholds")

        with gr.Row():
            score_threshold = gr.Number(
                label="Score Threshold",
                info="Minimum score to trade",
                precision=3,
                interactive=False
            )
            high_conviction_threshold = gr.Number(
                label="High Conviction Threshold",
                info="Score for high conviction",
                precision=3,
                interactive=False
            )

        # Limits Section
        gr.Markdown("### Limits")

        with gr.Row():
            max_concurrent = gr.Number(
                label="Max Concurrent Positions",
                precision=0,
                interactive=False
            )
            daily_loss_limit = gr.Number(
                label="Daily Loss Limit %",
                precision=2,
                interactive=False
            )
            daily_loss_enabled = gr.Checkbox(
                label="Daily Loss Limit Enabled",
                interactive=False
            )

        # Concentration Section
        gr.Markdown("### Concentration Limits")

        with gr.Row():
            max_token_pct = gr.Number(
                label="Max Token %",
                precision=2,
                interactive=False
            )
            max_cluster_pct = gr.Number(
                label="Max Cluster %",
                precision=2,
                interactive=False
            )
            max_pos_per_cluster = gr.Number(
                label="Max Positions/Cluster",
                precision=0,
                interactive=False
            )

        # Slippage Section
        gr.Markdown("### Slippage")

        with gr.Row():
            slippage_entry = gr.Number(
                label="Entry Slippage (bps)",
                precision=0,
                interactive=False
            )
            slippage_exit = gr.Number(
                label="Exit Slippage (bps)",
                precision=0,
                interactive=False
            )

        # Action Buttons
        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", variant="primary", visible=False)
            discard_btn = gr.Button("Discard", variant="stop", visible=False)
            activate_btn = gr.Button("Activate", variant="primary", visible=False)

        # Status message
        status_message = gr.Textbox(
            label="",
            interactive=False,
            visible=False
        )

    return {
        "base_position_pct": base_position_pct,
        "max_position_sol": max_position_sol,
        "min_position_sol": min_position_sol,
        "sizing_mode": sizing_mode,
        "risk_per_trade_pct": risk_per_trade_pct,
        "high_conviction_mult": high_conviction_mult,
        "score_threshold": score_threshold,
        "high_conviction_threshold": high_conviction_threshold,
        "max_concurrent": max_concurrent,
        "daily_loss_limit": daily_loss_limit,
        "daily_loss_enabled": daily_loss_enabled,
        "max_token_pct": max_token_pct,
        "max_cluster_pct": max_cluster_pct,
        "max_pos_per_cluster": max_pos_per_cluster,
        "slippage_entry": slippage_entry,
        "slippage_exit": slippage_exit,
        "edit_btn": edit_btn,
        "save_btn": save_btn,
        "discard_btn": discard_btn,
        "activate_btn": activate_btn,
        "status_message": status_message,
    }


def create_scoring_config_tab():
    """Create scoring configuration tab."""
    with gr.Column() as tab:
        gr.Markdown("### Score Weights")

        with gr.Row():
            wallet_weight = gr.Number(label="Wallet Weight", precision=3, interactive=False)
            timing_weight = gr.Number(label="Timing Weight", precision=3, interactive=False)
            market_weight = gr.Number(label="Market Weight", precision=3, interactive=False)
            cluster_weight = gr.Number(label="Cluster Weight", precision=3, interactive=False)

        gr.Markdown("### Wallet Scoring")

        with gr.Row():
            wr_weight = gr.Number(label="Win Rate Weight", precision=3, interactive=False)
            pnl_weight = gr.Number(label="Avg PnL Weight", precision=3, interactive=False)
            consistency_weight = gr.Number(label="Consistency Weight", precision=3, interactive=False)

        # Edit buttons
        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", visible=False)
            activate_btn = gr.Button("Activate", visible=False)

    return tab


def create_discovery_config_tab():
    """Create discovery configuration tab."""
    with gr.Column() as tab:
        gr.Markdown("### Discovery Runs")

        with gr.Row():
            run_interval = gr.Number(label="Run Interval (min)", precision=0, interactive=False)
            max_wallets = gr.Number(label="Max Wallets/Run", precision=0, interactive=False)
            min_age = gr.Number(label="Min Wallet Age (days)", precision=0, interactive=False)

        gr.Markdown("### Wallet Criteria")

        with gr.Row():
            min_win_rate = gr.Number(label="Min Win Rate", precision=3, interactive=False)
            min_trades = gr.Number(label="Min Trades", precision=0, interactive=False)
            min_pnl = gr.Number(label="Min Avg PnL %", precision=2, interactive=False)

        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", visible=False)
            activate_btn = gr.Button("Activate", visible=False)

    return tab


def create_cluster_config_tab():
    """Create cluster configuration tab."""
    with gr.Column() as tab:
        gr.Markdown("### Clustering")

        with gr.Row():
            min_size = gr.Number(label="Min Cluster Size", precision=0, interactive=False)
            max_size = gr.Number(label="Max Cluster Size", precision=0, interactive=False)
            similarity = gr.Number(label="Similarity Threshold", precision=3, interactive=False)

        gr.Markdown("### Sync Detection")

        with gr.Row():
            sync_window = gr.Number(label="Sync Window (min)", precision=0, interactive=False)
            token_overlap = gr.Number(label="Token Overlap", precision=3, interactive=False)

        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", visible=False)
            activate_btn = gr.Button("Activate", visible=False)

    return tab


def create_risk_config_tab():
    """Create risk configuration tab."""
    with gr.Column() as tab:
        gr.Markdown("### Circuit Breaker")

        with gr.Row():
            cb_enabled = gr.Checkbox(label="Enabled", interactive=False)
            cb_threshold = gr.Number(label="Loss Threshold %", precision=2, interactive=False)
            cb_cooldown = gr.Number(label="Cooldown (min)", precision=0, interactive=False)

        gr.Markdown("### Drawdown")

        with gr.Row():
            max_dd = gr.Number(label="Max Drawdown %", precision=2, interactive=False)
            dd_lookback = gr.Number(label="Lookback (days)", precision=0, interactive=False)

        gr.Markdown("### Order Retry")

        with gr.Row():
            max_attempts = gr.Number(label="Max Attempts", precision=0, interactive=False)
            retry_delay = gr.Number(label="Base Delay (s)", precision=0, interactive=False)
            retry_mult = gr.Number(label="Delay Multiplier", precision=2, interactive=False)

        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", visible=False)
            activate_btn = gr.Button("Activate", visible=False)

    return tab


def create_exit_config_tab():
    """Create exit configuration tab."""
    with gr.Column() as tab:
        gr.Markdown("### Default Strategy Assignments")

        with gr.Row():
            standard_strategy = gr.Dropdown(label="Standard Strategy", interactive=False)
            hc_strategy = gr.Dropdown(label="High Conviction Strategy", interactive=False)

        gr.Markdown("### Time Limits")

        with gr.Row():
            max_hold = gr.Number(label="Max Hold (hours)", precision=0, interactive=False)
            stagnation_hours = gr.Number(label="Stagnation (hours)", precision=0, interactive=False)
            stagnation_threshold = gr.Number(label="Stagnation %", precision=2, interactive=False)

        gr.Markdown("### Price History")

        with gr.Row():
            collection_interval = gr.Number(label="Collection Interval (s)", precision=0, interactive=False)
            retention_days = gr.Number(label="Retention (days)", precision=0, interactive=False)

        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", visible=False)
            activate_btn = gr.Button("Activate", visible=False)

    return tab


def create_api_config_tab():
    """Create API configuration tab."""
    with gr.Column() as tab:
        gr.Markdown("### Rate Limits (requests/min)")

        with gr.Row():
            dexscreener_rpm = gr.Number(label="DexScreener", precision=0, interactive=False)
            birdeye_rpm = gr.Number(label="Birdeye", precision=0, interactive=False)
            jupiter_rpm = gr.Number(label="Jupiter", precision=0, interactive=False)
            helius_rpm = gr.Number(label="Helius", precision=0, interactive=False)

        gr.Markdown("### Timeouts")

        with gr.Row():
            api_timeout = gr.Number(label="API Timeout (s)", precision=0, interactive=False)
            rpc_timeout = gr.Number(label="RPC Timeout (s)", precision=0, interactive=False)

        gr.Markdown("### Caching")

        with gr.Row():
            price_ttl = gr.Number(label="Price Cache TTL (s)", precision=0, interactive=False)
            token_ttl = gr.Number(label="Token Info TTL (s)", precision=0, interactive=False)

        with gr.Row():
            edit_btn = gr.Button("Edit", variant="secondary")
            save_btn = gr.Button("Save Draft", visible=False)
            activate_btn = gr.Button("Activate", visible=False)

    return tab
```

### Config Page Handlers

**src/walltrack/ui/pages/config_handlers.py:**
```python
"""Event handlers for config page."""

import httpx
from typing import Any


async def load_config(table: str) -> dict:
    """Load configuration for a table."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://localhost:8000/api/config/{table}")
        if response.status_code == 200:
            return response.json()
    return {}


async def create_draft(table: str) -> dict:
    """Create a draft from active config."""
    async with httpx.AsyncClient() as client:
        response = await client.post(f"http://localhost:8000/api/config/{table}/draft")
        return response.json()


async def update_draft(table: str, data: dict, reason: str = None) -> dict:
    """Update draft with new values."""
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            f"http://localhost:8000/api/config/{table}/draft",
            json={"data": data, "reason": reason}
        )
        return response.json()


async def activate_draft(table: str, reason: str = None) -> dict:
    """Activate the current draft."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/config/{table}/activate",
            json={"reason": reason}
        )
        return response.json()


async def delete_draft(table: str) -> bool:
    """Delete/discard the current draft."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"http://localhost:8000/api/config/{table}/draft")
        return response.status_code == 200


def toggle_edit_mode(is_editing: bool):
    """Toggle between edit and view mode."""
    return {
        "edit_btn": gr.update(visible=not is_editing),
        "save_btn": gr.update(visible=is_editing),
        "discard_btn": gr.update(visible=is_editing),
        "activate_btn": gr.update(visible=is_editing),
        # Make fields interactive
        "fields_interactive": is_editing,
    }
```

## Implementation Tasks

- [x] Create config page layout with tabs
- [x] Create trading config tab
- [x] Create scoring config tab
- [x] Create discovery config tab
- [x] Create cluster config tab
- [x] Create risk config tab
- [x] Create exit config tab
- [x] Create API config tab
- [x] Implement load_config handler
- [x] Implement edit mode toggle
- [x] Implement save draft handler
- [x] Implement activate handler
- [x] Implement discard handler
- [x] Add confirmation dialogs
- [x] Add toast notifications
- [x] Wire up events

## Definition of Done

- [x] All 7 config tabs created
- [x] View mode shows current values
- [x] Edit mode allows modifications
- [x] Draft saves correctly
- [x] Activation with confirmation
- [x] Discard with confirmation
- [x] Toast notifications

## File List

### New Files
- `src/walltrack/ui/pages/config.py` - Config page
- `src/walltrack/ui/pages/config_handlers.py` - Event handlers

### Modified Files
- `src/walltrack/ui/app.py` - Add config page to navigation
