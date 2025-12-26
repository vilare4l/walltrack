"""Discovery management UI component."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings
from walltrack.discovery.pump_finder import PumpFinder

log = structlog.get_logger()


def _get_api_base_url() -> str:
    """Get the base URL for API calls."""
    settings = get_settings()
    if settings.api_base_url:
        return settings.api_base_url
    return f"http://localhost:{settings.port}"


async def fetch_discovery_config() -> dict[str, Any]:
    """Fetch current discovery configuration from API."""
    base_url = _get_api_base_url()

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            response = await client.get("/api/discovery/config")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.error("config_fetch_failed", error=str(e))
            return {}


async def load_initial_config() -> tuple[
    bool, int, str, str, float, float, int, int, float, int
]:
    """Load initial configuration values for the UI."""
    config = await fetch_discovery_config()
    
    if not config:
        # Return defaults if config fetch fails
        return (
            True,  # enabled
            6,  # schedule_hours
            "Not available",  # next_run
            "Never",  # last_run
            100.0,  # min_price_change
            50000.0,  # min_volume
            72,  # max_age
            30,  # early_window
            50.0,  # min_profit
            20,  # max_tokens
        )
    
    # Format next_run and last_run
    next_run_str = _format_datetime(config.get("next_run"))
    last_run_str = _format_datetime(config.get("last_run"))
    
    params = config.get("params", {})
    
    return (
        config.get("enabled", True),
        config.get("schedule_hours", 6),
        next_run_str,
        last_run_str,
        params.get("min_price_change_pct", 100.0),
        params.get("min_volume_usd", 50000.0),
        params.get("max_token_age_hours", 72),
        params.get("early_window_minutes", 30),
        params.get("min_profit_pct", 50.0),
        params.get("max_tokens", 20),
    )


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
    """Save discovery configuration via API."""
    base_url = _get_api_base_url()

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            response = await client.put(
                "/api/discovery/config",
                json={
                    "enabled": enabled,
                    "schedule_hours": int(schedule_hours),
                    "params": {
                        "min_price_change_pct": float(min_price_change),
                        "min_volume_usd": float(min_volume),
                        "max_token_age_hours": int(max_age),
                        "early_window_minutes": int(early_window),
                        "min_profit_pct": float(min_profit),
                        "max_tokens": int(max_tokens),
                    },
                },
            )
            response.raise_for_status()
            return "Configuration saved successfully"
        except Exception as e:
            log.error("config_save_failed", error=str(e))
            return f"Failed to save: {e}"


async def trigger_discovery(
    min_price_change: float,
    min_volume: float,
    max_age: int,
    early_window: int,
    min_profit: float,
    max_tokens: int,
) -> str:
    """Trigger a manual discovery run via API."""
    base_url = _get_api_base_url()

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            response = await client.post(
                "/api/discovery/run",
                json={
                    "min_price_change_pct": float(min_price_change),
                    "min_volume_usd": float(min_volume),
                    "max_token_age_hours": int(max_age),
                    "early_window_minutes": int(early_window),
                    "min_profit_pct": float(min_profit),
                    "max_tokens": int(max_tokens),
                },
            )
            response.raise_for_status()
            data = response.json()
            return f"Discovery started - Run ID: {data['run_id']}"
        except Exception as e:
            log.error("discovery_trigger_failed", error=str(e))
            return f"Failed to start discovery: {e}"


async def fetch_pumped_tokens() -> pd.DataFrame:
    """Fetch currently pumped tokens from Birdeye API."""
    try:
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
                data.append(
                    {
                        "Symbol": t.symbol or "Unknown",
                        "Mint": t.mint[:16] + "..." if len(t.mint) > 16 else t.mint,
                        "Volume 24h": f"${t.volume_24h:,.0f}",
                        "Market Cap": f"${t.current_mcap:,.0f}",
                    }
                )

            return pd.DataFrame(data)

        finally:
            await finder.close()

    except Exception as e:
        log.error("pumps_fetch_failed", error=str(e))
        return pd.DataFrame(
            {"Error": [str(e)]},
        )


async def fetch_discovery_stats(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Fetch discovery statistics from API."""
    base_url = _get_api_base_url()

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            params: dict[str, str] = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await client.get("/api/discovery/stats", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log.error("stats_fetch_failed", error=str(e))
            return {}


def format_stats_display(stats: dict[str, Any]) -> str:
    """Format statistics for markdown display."""
    if not stats:
        return "No statistics available"

    total_runs = stats.get("total_runs", 0)
    successful = stats.get("successful_runs", 0)
    success_rate = (successful / total_runs * 100) if total_runs > 0 else 0
    last_run = stats.get("last_run_at", "")

    return f"""### Discovery Statistics

| Metric | Value |
|--------|-------|
| Total Runs | {total_runs} |
| Successful | {successful} |
| Failed | {stats.get('failed_runs', 0)} |
| Success Rate | {success_rate:.1f}% |
| Total Wallets Discovered | {stats.get('total_wallets_discovered', 0)} |
| Total Wallets Updated | {stats.get('total_wallets_updated', 0)} |
| Avg Wallets/Run | {stats.get('avg_wallets_per_run', 0):.1f} |
| Avg Duration | {stats.get('avg_duration_seconds', 0):.1f}s |
| Last Run | {last_run[:16].replace('T', ' ') if last_run else 'Never'} |
"""


async def fetch_discovery_history(
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
) -> pd.DataFrame:
    """Fetch discovery run history from API."""
    base_url = _get_api_base_url()

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            params: dict[str, str | int] = {"page": page, "page_size": 10}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await client.get("/api/discovery/runs", params=params)
            response.raise_for_status()
            data = response.json()

            runs = data.get("runs", [])
            if not runs:
                return pd.DataFrame(
                    columns=["Date", "Tokens", "New", "Updated", "Duration", "Status"]
                )

            rows = []
            for run in runs:
                started = run.get("started_at", "")[:16].replace("T", " ")
                rows.append(
                    {
                        "Date": started,
                        "Tokens": run.get("tokens_analyzed", 0),
                        "New": run.get("new_wallets", 0),
                        "Updated": run.get("updated_wallets", 0),
                        "Duration": f"{run.get('duration_seconds', 0):.1f}s",
                        "Status": run.get("status", "unknown").upper(),
                    }
                )

            return pd.DataFrame(rows)

        except Exception as e:
            log.error("history_fetch_failed", error=str(e))
            return pd.DataFrame(
                columns=["Date", "Tokens", "New", "Updated", "Duration", "Status"]
            )


def _format_datetime(dt_str: str | None) -> str:
    """Format datetime string for display."""
    if not dt_str:
        return "Never"
    try:
        # Handle ISO format with Z suffix
        formatted_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(formatted_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return dt_str or "Never"


async def load_history_and_stats(
    start: str, end: str, page: int
) -> tuple[str, pd.DataFrame, str, int]:
    """Load history and stats with date filter and pagination."""
    start_val = start if start else None
    end_val = end if end else None

    stats = await fetch_discovery_stats(start_val, end_val)
    history = await fetch_discovery_history(start_val, end_val, page)

    return (
        format_stats_display(stats),
        history,
        f"Page {page}",
        page,
    )


async def go_prev_page(
    start: str, end: str, page: int
) -> tuple[str, pd.DataFrame, str, int]:
    """Go to previous page."""
    new_page = max(1, page - 1)
    return await load_history_and_stats(start, end, new_page)


async def go_next_page(
    start: str, end: str, page: int
) -> tuple[str, pd.DataFrame, str, int]:
    """Go to next page."""
    new_page = page + 1
    return await load_history_and_stats(start, end, new_page)


async def apply_filter(start: str, end: str) -> tuple[str, pd.DataFrame, str, int]:
    """Apply date filter and reset to page 1."""
    return await load_history_and_stats(start, end, 1)


def _create_config_section() -> tuple[
    gr.Checkbox,
    gr.Dropdown,
    gr.Textbox,
    gr.Textbox,
    gr.Number,
    gr.Number,
    gr.Number,
    gr.Number,
    gr.Number,
    gr.Number,
    gr.Button,
    gr.Button,
    gr.Textbox,
]:
    """Create the configuration section UI."""
    gr.Markdown("## Scheduler Configuration")

    with gr.Group():
        enabled = gr.Checkbox(
            label="Auto-discovery enabled",
            value=True,
            interactive=True,
        )
        schedule_hours = gr.Dropdown(
            label="Run frequency (hours)",
            choices=[1, 2, 4, 6, 12, 24],
            value=6,
            interactive=True,
        )

    with gr.Group():
        next_run = gr.Textbox(
            label="Next scheduled run",
            value="Loading...",
            interactive=False,
        )
        last_run = gr.Textbox(
            label="Last run",
            value="Loading...",
            interactive=False,
        )

    gr.Markdown("## Discovery Parameters")

    with gr.Group():
        min_price_change = gr.Number(
            label="Min price change (%)",
            value=100.0,
            minimum=0,
            maximum=1000,
            step=10,
        )
        min_volume = gr.Number(
            label="Min 24h volume ($)",
            value=50000.0,
            minimum=0,
            step=1000,
        )
        max_age = gr.Number(
            label="Max token age (hours)",
            value=72,
            minimum=1,
            maximum=168,
            step=1,
        )
        early_window = gr.Number(
            label="Early window (minutes)",
            value=30,
            minimum=5,
            maximum=120,
            step=5,
        )
        min_profit = gr.Number(
            label="Min profit (%)",
            value=50.0,
            minimum=0,
            maximum=500,
            step=5,
        )
        max_tokens = gr.Number(
            label="Max tokens per run",
            value=20,
            minimum=1,
            maximum=100,
            step=1,
        )

    with gr.Row():
        save_btn = gr.Button("Save Config", variant="secondary")
        run_btn = gr.Button("Run Now", variant="primary")

    status = gr.Textbox(
        label="Status",
        value="",
        interactive=False,
        lines=2,
    )

    return (
        enabled,
        schedule_hours,
        next_run,
        last_run,
        min_price_change,
        min_volume,
        max_age,
        early_window,
        min_profit,
        max_tokens,
        save_btn,
        run_btn,
        status,
    )


def _create_history_section() -> tuple[
    gr.Textbox,
    gr.Textbox,
    gr.Button,
    gr.Markdown,
    gr.Dataframe,
    gr.Button,
    gr.Textbox,
    gr.Button,
    gr.State,
]:
    """Create the history and statistics section UI."""
    gr.Markdown("---")
    gr.Markdown("## History & Statistics")

    with gr.Row():
        start_date = gr.Textbox(
            label="Start Date (YYYY-MM-DD)",
            value="",
            placeholder="Leave empty for all",
            scale=1,
        )
        end_date = gr.Textbox(
            label="End Date (YYYY-MM-DD)",
            value="",
            placeholder="Leave empty for all",
            scale=1,
        )
        filter_btn = gr.Button("Filter", variant="secondary", scale=1)

    with gr.Row():
        with gr.Column(scale=1):
            stats_display = gr.Markdown("Loading statistics...")

        with gr.Column(scale=2):
            history_table = gr.Dataframe(
                headers=["Date", "Tokens", "New", "Updated", "Duration", "Status"],
                interactive=False,
                wrap=True,
            )

            with gr.Row():
                prev_btn = gr.Button("← Previous", variant="secondary", scale=1)
                page_info = gr.Textbox(
                    value="Page 1",
                    interactive=False,
                    show_label=False,
                    scale=1,
                )
                next_btn = gr.Button("Next →", variant="secondary", scale=1)

    current_page = gr.State(value=1)

    return (
        start_date,
        end_date,
        filter_btn,
        stats_display,
        history_table,
        prev_btn,
        page_info,
        next_btn,
        current_page,
    )


def create_discovery_tab() -> None:
    """Create the discovery management tab UI."""
    with gr.Row():
        # Left column: Configuration
        with gr.Column(scale=1):
            (
                enabled,
                schedule_hours,
                next_run,
                last_run,
                min_price_change,
                min_volume,
                max_age,
                early_window,
                min_profit,
                max_tokens,
                save_btn,
                run_btn,
                status,
            ) = _create_config_section()
            
            # Add refresh config button
            refresh_config_btn = gr.Button("🔄 Refresh Config", variant="secondary", size="sm")

        # Right column: Pumped Tokens
        with gr.Column(scale=1):
            gr.Markdown("## Current Pumped Tokens")

            pumps_table = gr.Dataframe(
                headers=["Symbol", "Mint", "Volume 24h", "Market Cap"],
                interactive=False,
            )

            refresh_pumps_btn = gr.Button("Refresh Pumps", variant="secondary")

    # History and Statistics Section (full width)
    (
        start_date,
        end_date,
        filter_btn,
        stats_display,
        history_table,
        prev_btn,
        page_info,
        next_btn,
        current_page,
    ) = _create_history_section()

    # Refresh config button handler
    refresh_config_btn.click(
        fn=load_initial_config,
        outputs=[
            enabled,
            schedule_hours,
            next_run,
            last_run,
            min_price_change,
            min_volume,
            max_age,
            early_window,
            min_profit,
            max_tokens,
        ],
    )

    # Event handlers for configuration
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

    refresh_pumps_btn.click(
        fn=fetch_pumped_tokens,
        outputs=[pumps_table],
    )

    # Event handlers for history and stats
    filter_btn.click(
        fn=apply_filter,
        inputs=[start_date, end_date],
        outputs=[stats_display, history_table, page_info, current_page],
    )

    prev_btn.click(
        fn=go_prev_page,
        inputs=[start_date, end_date, current_page],
        outputs=[stats_display, history_table, page_info, current_page],
    )

    next_btn.click(
        fn=go_next_page,
        inputs=[start_date, end_date, current_page],
        outputs=[stats_display, history_table, page_info, current_page],
    )
