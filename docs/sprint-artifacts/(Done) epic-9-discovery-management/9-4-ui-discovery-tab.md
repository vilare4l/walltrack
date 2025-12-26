# Story 9.4: UI Discovery Tab with Parameters

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: Story 9.2, Story 9.3

## User Story

**As an** operator,
**I want** a Discovery tab in the dashboard,
**So that** I can configure and trigger discovery from the UI.

## Acceptance Criteria

### AC 1: Scheduler Section
**Given** the Discovery tab
**When** I view the scheduler section
**Then** I see enabled/disabled toggle
**And** I see frequency dropdown
**And** I see next run time (if enabled)
**And** I see last run summary

### AC 2: Parameters Section
**Given** the Discovery tab
**When** I view the parameters section
**Then** I see all configurable parameters
**And** each has appropriate input type
**And** current values are displayed
**And** validation errors are shown

### AC 3: Manual Run Section
**Given** the Discovery tab
**When** I click "Run Now"
**Then** discovery starts immediately
**And** button shows loading state
**And** progress/status is displayed
**And** results shown when complete

### AC 4: Live Pumps Section
**Given** the Discovery tab
**When** I click "View Pumps"
**Then** current pumped tokens are fetched
**And** displayed in a table
**And** includes token, volume, change %
**And** auto-refreshes periodically

### AC 5: Save Configuration
**Given** modified parameters
**When** I click "Save"
**Then** configuration is saved
**And** success message is shown
**And** scheduler uses new config

## Technical Specifications

### Discovery Tab Component

**src/walltrack/ui/components/discovery.py:**
```python
"""Discovery management UI component."""

import asyncio
from typing import Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings
from walltrack.discovery.pump_finder import PumpFinder

log = structlog.get_logger()


async def fetch_discovery_config() -> dict[str, Any]:
    """Fetch current discovery configuration."""
    settings = get_settings()
    base_url = settings.api_base_url or f"http://localhost:{settings.port}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            response = await client.get("/api/discovery/config")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.error("config_fetch_failed", error=str(e))
            return {}


async def save_discovery_config(
    enabled: bool,
    schedule_hours: int,
    min_price_change: float,
    min_volume: float,
    max_age: int,
    early_window: int,
    min_profit: float,
    max_tokens: int,
) -> str:
    """Save discovery configuration."""
    settings = get_settings()
    base_url = settings.api_base_url or f"http://localhost:{settings.port}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            response = await client.put(
                "/api/discovery/config",
                json={
                    "enabled": enabled,
                    "schedule_hours": schedule_hours,
                    "params": {
                        "min_price_change_pct": min_price_change,
                        "min_volume_usd": min_volume,
                        "max_token_age_hours": max_age,
                        "early_window_minutes": early_window,
                        "min_profit_pct": min_profit,
                        "max_tokens": max_tokens,
                    },
                },
            )
            response.raise_for_status()
            return "[OK] Configuration saved successfully"
        except Exception as e:
            return f"[ERROR] Failed to save: {e}"


async def trigger_discovery(
    min_price_change: float,
    min_volume: float,
    max_age: int,
    early_window: int,
    min_profit: float,
    max_tokens: int,
) -> str:
    """Trigger a manual discovery run."""
    settings = get_settings()
    base_url = settings.api_base_url or f"http://localhost:{settings.port}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            response = await client.post(
                "/api/discovery/run",
                json={
                    "min_price_change_pct": min_price_change,
                    "min_volume_usd": min_volume,
                    "max_token_age_hours": max_age,
                    "early_window_minutes": early_window,
                    "min_profit_pct": min_profit,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            data = response.json()
            return f"[OK] Discovery started - Run ID: {data['run_id']}"
        except Exception as e:
            return f"[ERROR] Failed to start: {e}"


async def fetch_pumped_tokens() -> pd.DataFrame:
    """Fetch currently pumped tokens."""
    finder = PumpFinder()
    try:
        tokens = await finder.find_pumped_tokens(
            min_price_change_pct=50.0,
            min_volume_usd=10000.0,
            limit=20,
        )

        if not tokens:
            return pd.DataFrame(
                columns=["Symbol", "Mint", "Volume 24h", "Market Cap"]
            )

        data = []
        for t in tokens:
            data.append({
                "Symbol": t.symbol or "Unknown",
                "Mint": t.mint[:20] + "...",
                "Volume 24h": f"${t.volume_24h:,.0f}",
                "Market Cap": f"${t.current_mcap:,.0f}",
            })

        return pd.DataFrame(data)

    finally:
        await finder.close()


def create_scheduler_section() -> tuple:
    """Create scheduler configuration section."""
    with gr.Group():
        gr.Markdown("## Scheduler")

        with gr.Row():
            enabled = gr.Checkbox(
                label="Auto-discovery enabled",
                value=True,
                interactive=True,
            )
            schedule_hours = gr.Dropdown(
                label="Frequency",
                choices=[1, 2, 4, 6, 12, 24],
                value=6,
                interactive=True,
            )

        with gr.Row():
            next_run = gr.Textbox(
                label="Next run",
                value="Loading...",
                interactive=False,
            )
            last_run = gr.Textbox(
                label="Last run",
                value="Loading...",
                interactive=False,
            )

    return enabled, schedule_hours, next_run, last_run


def create_params_section() -> tuple:
    """Create parameters configuration section."""
    with gr.Group():
        gr.Markdown("## Parameters")

        with gr.Row():
            min_price_change = gr.Number(
                label="Min price change %",
                value=100.0,
                minimum=0,
                maximum=1000,
            )
            min_volume = gr.Number(
                label="Min volume 24h ($)",
                value=50000.0,
                minimum=0,
            )

        with gr.Row():
            max_age = gr.Number(
                label="Max token age (hours)",
                value=72,
                minimum=1,
                maximum=168,
            )
            early_window = gr.Number(
                label="Early window (minutes)",
                value=30,
                minimum=5,
                maximum=120,
            )

        with gr.Row():
            min_profit = gr.Number(
                label="Min profit %",
                value=50.0,
                minimum=0,
                maximum=500,
            )
            max_tokens = gr.Number(
                label="Max tokens per run",
                value=20,
                minimum=1,
                maximum=100,
            )

    return min_price_change, min_volume, max_age, early_window, min_profit, max_tokens


def create_actions_section() -> tuple:
    """Create actions section."""
    with gr.Group():
        gr.Markdown("## Actions")

        with gr.Row():
            save_btn = gr.Button("Save Configuration", variant="secondary")
            run_btn = gr.Button("Run Now", variant="primary")
            pumps_btn = gr.Button("View Pumps", variant="secondary")

        status = gr.Textbox(
            label="Status",
            value="",
            interactive=False,
            lines=2,
        )

    return save_btn, run_btn, pumps_btn, status


def create_pumps_section() -> gr.Dataframe:
    """Create pumped tokens display section."""
    with gr.Group():
        gr.Markdown("## Current Pumps")

        pumps_table = gr.Dataframe(
            headers=["Symbol", "Mint", "Volume 24h", "Market Cap"],
            interactive=False,
            wrap=True,
        )

    return pumps_table


def create_discovery_tab() -> None:
    """Create the discovery tab UI."""
    # Scheduler section
    enabled, schedule_hours, next_run, last_run = create_scheduler_section()

    # Parameters section
    (
        min_price_change,
        min_volume,
        max_age,
        early_window,
        min_profit,
        max_tokens,
    ) = create_params_section()

    # Actions section
    save_btn, run_btn, pumps_btn, status = create_actions_section()

    # Pumps display
    pumps_table = create_pumps_section()

    # Event handlers
    save_btn.click(
        fn=save_discovery_config,
        inputs=[
            enabled,
            schedule_hours,
            min_price_change,
            min_volume,
            max_age,
            early_window,
            min_profit,
            max_tokens,
        ],
        outputs=[status],
    )

    run_btn.click(
        fn=trigger_discovery,
        inputs=[
            min_price_change,
            min_volume,
            max_age,
            early_window,
            min_profit,
            max_tokens,
        ],
        outputs=[status],
    )

    pumps_btn.click(
        fn=fetch_pumped_tokens,
        outputs=[pumps_table],
    )

    # Load initial config
    async def load_config():
        config = await fetch_discovery_config()
        if config:
            params = config.get("params", {})
            return (
                config.get("enabled", True),
                config.get("schedule_hours", 6),
                config.get("next_run_at", "Not scheduled"),
                config.get("last_run_at", "Never"),
                params.get("min_price_change_pct", 100.0),
                params.get("min_volume_usd", 50000.0),
                params.get("max_token_age_hours", 72),
                params.get("early_window_minutes", 30),
                params.get("min_profit_pct", 50.0),
                params.get("max_tokens", 20),
            )
        return (True, 6, "Not scheduled", "Never", 100.0, 50000.0, 72, 30, 50.0, 20)

    # Note: Gradio doesn't support async on_load yet
    # Would need to use a workaround or sync wrapper
```

## Implementation Tasks

- [x] Create discovery.py component
- [x] Implement scheduler section
- [x] Implement parameters section
- [x] Implement actions section
- [x] Implement pumps display
- [x] Add event handlers
- [x] Integrate with dashboard
- [x] Test UI functionality

## Definition of Done

- [x] Tab appears in dashboard
- [x] Scheduler controls work
- [x] Parameters can be edited
- [x] Save persists configuration
- [x] Run Now triggers discovery
- [x] View Pumps shows current tokens
- [x] UI is responsive and intuitive

## Dev Agent Record

### Implementation Notes (2024-12-24)
- Created `discovery.py` component with scheduler and parameters sections
- Implemented async API calls for config, stats, and discovery trigger
- Added pumped tokens display using PumpFinder
- Integrated with dashboard as new Discovery tab
- Added 15 unit tests (all passing)

## File List

### New Files
- `src/walltrack/ui/components/discovery.py` - UI component with all sections
- `tests/unit/ui/components/test_discovery.py` - 15 component tests

### Modified Files
- `src/walltrack/ui/dashboard.py` - Added Discovery tab
