# Story 1.8: Basic Dashboard - Wallet Views

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: ready
- **Priority**: High
- **FR**: FR46, FR48

## User Story

**As an** operator,
**I want** a Gradio dashboard to view and manage wallets,
**So that** I can interact with the system visually.

## Acceptance Criteria

### AC 1: Wallet List View
**Given** the dashboard is launched
**When** operator navigates to Wallets tab
**Then** list of all wallets is displayed with key metrics (address, win rate, PnL, status)
**And** wallets can be sorted by any column
**And** wallets can be filtered by status (active, decay_detected, blacklisted)

### AC 2: Wallet Detail View
**Given** a wallet in the list
**When** operator clicks on it
**Then** detailed profile is displayed (all metrics from Story 1.5)
**And** recent trades are shown
**And** blacklist button is available

### AC 3: Watchlist Management
**Given** the watchlist management view
**When** operator adds a wallet address manually
**Then** wallet is added to watchlist
**And** profiling is triggered automatically
**And** success/error feedback is displayed

### AC 4: Performance
**Given** the dashboard is loaded
**When** data is refreshed
**Then** response time is < 2 seconds (NFR3)

## Technical Specifications

### Main Dashboard

**src/walltrack/ui/dashboard.py:**
```python
"""Main Gradio dashboard application."""

import gradio as gr
import structlog

from walltrack.config.settings import get_settings
from walltrack.ui.components.wallets import create_wallets_tab
from walltrack.ui.components.clusters import create_clusters_tab
from walltrack.ui.components.signals import create_signals_tab
from walltrack.ui.components.positions import create_positions_tab
from walltrack.ui.components.performance import create_performance_tab
from walltrack.ui.components.config_panel import create_config_tab
from walltrack.ui.components.status import create_status_tab

log = structlog.get_logger()


def create_dashboard() -> gr.Blocks:
    """
    Create the main Gradio dashboard.

    Returns:
        Gradio Blocks application
    """
    settings = get_settings()

    with gr.Blocks(
        title="WallTrack Dashboard",
        theme=gr.themes.Soft(),
        css="""
            .wallet-card { padding: 10px; margin: 5px; border-radius: 8px; }
            .metric-positive { color: #10b981; }
            .metric-negative { color: #ef4444; }
            .status-active { background-color: #10b981; }
            .status-decay { background-color: #f59e0b; }
            .status-blacklisted { background-color: #ef4444; }
        """,
    ) as dashboard:
        gr.Markdown("# 🎯 WallTrack Dashboard")
        gr.Markdown("Autonomous Solana Memecoin Trading System")

        with gr.Tabs() as tabs:
            with gr.Tab("📊 Status", id="status"):
                create_status_tab()

            with gr.Tab("👛 Wallets", id="wallets"):
                create_wallets_tab()

            with gr.Tab("🔗 Clusters", id="clusters"):
                create_clusters_tab()

            with gr.Tab("📡 Signals", id="signals"):
                create_signals_tab()

            with gr.Tab("💼 Positions", id="positions"):
                create_positions_tab()

            with gr.Tab("📈 Performance", id="performance"):
                create_performance_tab()

            with gr.Tab("⚙️ Config", id="config"):
                create_config_tab()

    log.info("dashboard_created", debug=settings.debug)

    return dashboard


def launch_dashboard(
    share: bool = False,
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
) -> None:
    """
    Launch the dashboard.

    Args:
        share: Create public share link
        server_name: Server hostname
        server_port: Server port
    """
    dashboard = create_dashboard()
    dashboard.launch(
        share=share,
        server_name=server_name,
        server_port=server_port,
    )
```

### Wallets Tab Component

**src/walltrack/ui/components/wallets.py:**
```python
"""Wallet views and management for Gradio dashboard."""

from datetime import datetime
from typing import Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import Wallet, WalletStatus

log = structlog.get_logger()


# API client for backend communication
def get_api_client() -> httpx.AsyncClient:
    """Get async HTTP client for API calls."""
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=f"http://localhost:{settings.port}",
        timeout=10.0,
    )


async def fetch_wallets(
    status_filter: str | None = None,
    min_score: float = 0.0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch wallets from API."""
    async with get_api_client() as client:
        params = {"limit": limit, "min_score": min_score}
        if status_filter and status_filter != "all":
            params["status"] = status_filter

        response = await client.get("/wallets", params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("wallets", [])


async def fetch_wallet_detail(address: str) -> dict[str, Any] | None:
    """Fetch wallet details from API."""
    async with get_api_client() as client:
        response = await client.get(f"/wallets/{address}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()


async def add_wallet_to_watchlist(address: str) -> tuple[bool, str]:
    """Add wallet to watchlist and trigger profiling."""
    async with get_api_client() as client:
        try:
            response = await client.post(
                f"/wallets/{address}/profile",
                params={"force_update": True},
            )
            response.raise_for_status()
            return True, f"Wallet {address} added and profiled successfully"
        except httpx.HTTPStatusError as e:
            return False, f"Failed to add wallet: {e.response.text}"


async def blacklist_wallet(address: str, reason: str) -> tuple[bool, str]:
    """Blacklist a wallet."""
    async with get_api_client() as client:
        try:
            response = await client.post(
                f"/wallets/{address}/blacklist",
                params={"reason": reason},
            )
            response.raise_for_status()
            return True, f"Wallet {address} blacklisted"
        except httpx.HTTPStatusError as e:
            return False, f"Failed to blacklist: {e.response.text}"


async def unblacklist_wallet(address: str) -> tuple[bool, str]:
    """Remove wallet from blacklist."""
    async with get_api_client() as client:
        try:
            response = await client.delete(f"/wallets/{address}/blacklist")
            response.raise_for_status()
            return True, f"Wallet {address} removed from blacklist"
        except httpx.HTTPStatusError as e:
            return False, f"Failed to remove from blacklist: {e.response.text}"


def wallets_to_dataframe(wallets: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert wallet list to pandas DataFrame for display."""
    if not wallets:
        return pd.DataFrame(columns=[
            "Address", "Status", "Score", "Win Rate", "Total PnL", "Trades", "Last Signal"
        ])

    rows = []
    for w in wallets:
        profile = w.get("profile", {})
        rows.append({
            "Address": w.get("address", "")[:12] + "...",
            "Full Address": w.get("address", ""),
            "Status": w.get("status", "active"),
            "Score": f"{w.get('score', 0):.2%}",
            "Win Rate": f"{profile.get('win_rate', 0):.1%}",
            "Total PnL": f"{profile.get('total_pnl', 0):.2f} SOL",
            "Trades": profile.get("total_trades", 0),
            "Last Signal": w.get("last_signal_at", "-")[:10] if w.get("last_signal_at") else "-",
        })

    return pd.DataFrame(rows)


def format_wallet_detail(wallet: dict[str, Any] | None) -> str:
    """Format wallet details for display."""
    if not wallet:
        return "No wallet selected"

    profile = wallet.get("profile", {})

    return f"""
## Wallet Details

**Address:** `{wallet.get('address', 'N/A')}`

**Status:** {wallet.get('status', 'N/A')}

**Score:** {wallet.get('score', 0):.2%}

---

### Performance Metrics

| Metric | Value |
|--------|-------|
| Win Rate | {profile.get('win_rate', 0):.1%} |
| Total PnL | {profile.get('total_pnl', 0):.2f} SOL |
| Avg PnL/Trade | {profile.get('avg_pnl_per_trade', 0):.4f} SOL |
| Total Trades | {profile.get('total_trades', 0)} |
| Avg Hold Time | {profile.get('avg_hold_time_hours', 0):.1f}h |
| Timing Percentile | {profile.get('timing_percentile', 0.5):.1%} |
| Avg Position | {profile.get('avg_position_size_sol', 0):.4f} SOL |

---

### Discovery Info

| Info | Value |
|------|-------|
| Discovered | {wallet.get('discovered_at', 'N/A')[:10] if wallet.get('discovered_at') else 'N/A'} |
| Discovery Count | {wallet.get('discovery_count', 0)} |
| Last Profiled | {wallet.get('last_profiled_at', 'N/A')[:10] if wallet.get('last_profiled_at') else 'Never'} |
| Last Signal | {wallet.get('last_signal_at', 'N/A')[:10] if wallet.get('last_signal_at') else 'Never'} |

---

### Decay Status

| Status | Value |
|--------|-------|
| Rolling Win Rate | {wallet.get('rolling_win_rate', 'N/A')} |
| Consecutive Losses | {wallet.get('consecutive_losses', 0)} |
| Decay Detected | {wallet.get('decay_detected_at', 'Never')[:10] if wallet.get('decay_detected_at') else 'Never'} |
"""


def create_wallets_tab() -> None:
    """Create the wallets tab UI."""

    with gr.Row():
        with gr.Column(scale=3):
            gr.Markdown("### 👛 Wallet Watchlist")

            with gr.Row():
                status_filter = gr.Dropdown(
                    choices=["all", "active", "decay_detected", "blacklisted", "insufficient_data"],
                    value="all",
                    label="Status Filter",
                    scale=1,
                )
                min_score = gr.Slider(
                    minimum=0,
                    maximum=1,
                    value=0,
                    step=0.05,
                    label="Min Score",
                    scale=1,
                )
                refresh_btn = gr.Button("🔄 Refresh", scale=1)

            wallet_table = gr.Dataframe(
                headers=["Address", "Status", "Score", "Win Rate", "Total PnL", "Trades", "Last Signal"],
                datatype=["str", "str", "str", "str", "str", "number", "str"],
                interactive=False,
                row_count=20,
                col_count=(7, "fixed"),
            )

        with gr.Column(scale=2):
            gr.Markdown("### 📋 Wallet Details")

            selected_address = gr.Textbox(
                label="Selected Wallet",
                placeholder="Click a wallet to view details",
                interactive=False,
            )

            wallet_detail = gr.Markdown("Select a wallet to view details")

            with gr.Row():
                blacklist_reason = gr.Textbox(
                    label="Blacklist Reason",
                    placeholder="Enter reason...",
                    scale=3,
                )
                blacklist_btn = gr.Button("⛔ Blacklist", variant="stop", scale=1)

            unblacklist_btn = gr.Button("✅ Remove from Blacklist", variant="secondary")

    gr.Markdown("---")

    with gr.Row():
        gr.Markdown("### ➕ Add Wallet to Watchlist")

    with gr.Row():
        new_wallet_address = gr.Textbox(
            label="Wallet Address",
            placeholder="Enter Solana wallet address...",
            scale=4,
        )
        add_wallet_btn = gr.Button("Add & Profile", variant="primary", scale=1)

    add_wallet_result = gr.Markdown("")

    # Event handlers

    async def load_wallets(status: str, score: float) -> pd.DataFrame:
        """Load wallets and return DataFrame."""
        status_val = None if status == "all" else status
        wallets = await fetch_wallets(status_filter=status_val, min_score=score)
        return wallets_to_dataframe(wallets)

    async def on_wallet_select(evt: gr.SelectData, df: pd.DataFrame) -> tuple[str, str]:
        """Handle wallet selection."""
        if evt.index[0] < len(df):
            full_address = df.iloc[evt.index[0]].get("Full Address", "")
            if full_address:
                wallet = await fetch_wallet_detail(full_address)
                return full_address, format_wallet_detail(wallet)
        return "", "No wallet selected"

    async def on_add_wallet(address: str) -> tuple[str, pd.DataFrame]:
        """Handle adding new wallet."""
        if not address or len(address) < 32:
            return "❌ Invalid wallet address", pd.DataFrame()

        success, message = await add_wallet_to_watchlist(address)
        symbol = "✅" if success else "❌"

        # Refresh wallet list
        wallets = await fetch_wallets()
        df = wallets_to_dataframe(wallets)

        return f"{symbol} {message}", df

    async def on_blacklist(address: str, reason: str) -> tuple[str, str]:
        """Handle blacklisting wallet."""
        if not address:
            return "No wallet selected", ""
        if not reason:
            return "Please provide a reason", ""

        success, message = await blacklist_wallet(address, reason)

        if success:
            wallet = await fetch_wallet_detail(address)
            return format_wallet_detail(wallet), f"✅ {message}"
        return format_wallet_detail(await fetch_wallet_detail(address)), f"❌ {message}"

    async def on_unblacklist(address: str) -> tuple[str, str]:
        """Handle removing wallet from blacklist."""
        if not address:
            return "No wallet selected", ""

        success, message = await unblacklist_wallet(address)

        if success:
            wallet = await fetch_wallet_detail(address)
            return format_wallet_detail(wallet), f"✅ {message}"
        return format_wallet_detail(await fetch_wallet_detail(address)), f"❌ {message}"

    # Wire up events
    refresh_btn.click(
        fn=load_wallets,
        inputs=[status_filter, min_score],
        outputs=[wallet_table],
    )

    status_filter.change(
        fn=load_wallets,
        inputs=[status_filter, min_score],
        outputs=[wallet_table],
    )

    min_score.change(
        fn=load_wallets,
        inputs=[status_filter, min_score],
        outputs=[wallet_table],
    )

    wallet_table.select(
        fn=on_wallet_select,
        inputs=[wallet_table],
        outputs=[selected_address, wallet_detail],
    )

    add_wallet_btn.click(
        fn=on_add_wallet,
        inputs=[new_wallet_address],
        outputs=[add_wallet_result, wallet_table],
    )

    blacklist_btn.click(
        fn=on_blacklist,
        inputs=[selected_address, blacklist_reason],
        outputs=[wallet_detail, add_wallet_result],
    )

    unblacklist_btn.click(
        fn=on_unblacklist,
        inputs=[selected_address],
        outputs=[wallet_detail, add_wallet_result],
    )

    # Load initial data
    dashboard_load = gr.State(True)
    dashboard_load.change(
        fn=load_wallets,
        inputs=[status_filter, min_score],
        outputs=[wallet_table],
    )
```

### Status Tab Component

**src/walltrack/ui/components/status.py:**
```python
"""System status component for dashboard."""

from datetime import datetime
from typing import Any

import gradio as gr
import httpx

from walltrack.config.settings import get_settings


async def fetch_system_status() -> dict[str, Any]:
    """Fetch system health status from API."""
    settings = get_settings()
    async with httpx.AsyncClient(
        base_url=f"http://localhost:{settings.port}",
        timeout=5.0,
    ) as client:
        try:
            response = await client.get("/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


def format_status(status: dict[str, Any]) -> str:
    """Format status for display."""
    overall = status.get("status", "unknown")
    emoji = "🟢" if overall == "healthy" else "🔴" if overall == "error" else "🟡"

    services = status.get("services", {})
    neo4j_status = "🟢" if services.get("neo4j") == "connected" else "🔴"
    supabase_status = "🟢" if services.get("supabase") == "connected" else "🔴"

    return f"""
# System Status

**Overall:** {emoji} {overall.upper()}

**Last Check:** {status.get('timestamp', 'N/A')}

---

## Services

| Service | Status |
|---------|--------|
| Neo4j | {neo4j_status} {services.get('neo4j', 'unknown')} |
| Supabase | {supabase_status} {services.get('supabase', 'unknown')} |
| API | 🟢 Running |

---

## Trading Status

| Metric | Value |
|--------|-------|
| Circuit Breaker | {status.get('circuit_breaker', 'N/A')} |
| Active Positions | {status.get('active_positions', 0)} |
| Today's Trades | {status.get('trades_today', 0)} |
| Today's PnL | {status.get('pnl_today', 0):.4f} SOL |

---

## Wallet Stats

| Metric | Value |
|--------|-------|
| Total Wallets | {status.get('total_wallets', 0)} |
| Active Wallets | {status.get('active_wallets', 0)} |
| Decay Detected | {status.get('decay_wallets', 0)} |
| Blacklisted | {status.get('blacklisted_wallets', 0)} |
"""


def create_status_tab() -> None:
    """Create the status tab UI."""

    status_display = gr.Markdown("Loading system status...")

    with gr.Row():
        refresh_btn = gr.Button("🔄 Refresh Status", variant="primary")
        auto_refresh = gr.Checkbox(label="Auto-refresh (30s)", value=True)

    async def load_status() -> str:
        """Load and format status."""
        status = await fetch_system_status()
        return format_status(status)

    refresh_btn.click(
        fn=load_status,
        outputs=[status_display],
    )

    # Auto-refresh every 30 seconds
    status_display.every(
        30,
        fn=load_status,
        outputs=[status_display],
    )
```

### Dashboard Entry Point

**src/walltrack/main.py (updated):**
```python
"""Application entry point."""

import asyncio
import threading

import uvicorn

from walltrack.api.app import create_app
from walltrack.config.settings import get_settings
from walltrack.ui.dashboard import create_dashboard

app = create_app()


def run_dashboard(port: int = 7860) -> None:
    """Run Gradio dashboard in background thread."""
    dashboard = create_dashboard()
    dashboard.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,
        prevent_thread_lock=True,
    )


if __name__ == "__main__":
    settings = get_settings()

    # Start dashboard in background thread
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        kwargs={"port": 7860},
        daemon=True,
    )
    dashboard_thread.start()

    # Run FastAPI
    uvicorn.run(
        "walltrack.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
```

### Component Stubs

**src/walltrack/ui/components/clusters.py:**
```python
"""Cluster visualization component stub."""

import gradio as gr


def create_clusters_tab() -> None:
    """Create the clusters tab UI (placeholder for Epic 2)."""
    gr.Markdown("## 🔗 Cluster Analysis")
    gr.Markdown("*Cluster visualization will be implemented in Epic 2*")
```

**src/walltrack/ui/components/signals.py:**
```python
"""Signals component stub."""

import gradio as gr


def create_signals_tab() -> None:
    """Create the signals tab UI (placeholder for Epic 3)."""
    gr.Markdown("## 📡 Signal Feed")
    gr.Markdown("*Signal processing will be implemented in Epic 3*")
```

**src/walltrack/ui/components/positions.py:**
```python
"""Positions component stub."""

import gradio as gr


def create_positions_tab() -> None:
    """Create the positions tab UI (placeholder for Epic 4)."""
    gr.Markdown("## 💼 Open Positions")
    gr.Markdown("*Position management will be implemented in Epic 4*")
```

**src/walltrack/ui/components/performance.py:**
```python
"""Performance analytics component stub."""

import gradio as gr


def create_performance_tab() -> None:
    """Create the performance tab UI (placeholder for Epic 6)."""
    gr.Markdown("## 📈 Performance Analytics")
    gr.Markdown("*Performance analytics will be implemented in Epic 6*")
```

**src/walltrack/ui/components/config_panel.py:**
```python
"""Configuration panel component stub."""

import gradio as gr


def create_config_tab() -> None:
    """Create the config tab UI (placeholder)."""
    gr.Markdown("## ⚙️ Configuration")
    gr.Markdown("*Configuration panel will be implemented in later stories*")
```

### Unit Tests

**tests/unit/ui/test_wallets_component.py:**
```python
"""Tests for wallet UI component."""

import pytest
from unittest.mock import AsyncMock, patch
import pandas as pd

from walltrack.ui.components.wallets import (
    wallets_to_dataframe,
    format_wallet_detail,
)


class TestWalletsToDataframe:
    """Tests for wallets_to_dataframe function."""

    def test_empty_wallets(self) -> None:
        """Test with empty wallet list."""
        df = wallets_to_dataframe([])
        assert len(df) == 0
        assert "Address" in df.columns

    def test_wallet_formatting(self) -> None:
        """Test wallet data formatting."""
        wallets = [
            {
                "address": "ABC123XYZ789DEF456GHI012JKL345MNO678",
                "status": "active",
                "score": 0.75,
                "profile": {
                    "win_rate": 0.6,
                    "total_pnl": 10.5,
                    "total_trades": 25,
                },
                "last_signal_at": "2024-01-15T10:30:00",
            }
        ]

        df = wallets_to_dataframe(wallets)

        assert len(df) == 1
        assert "..." in df.iloc[0]["Address"]  # Truncated
        assert df.iloc[0]["Status"] == "active"
        assert "75.00%" in df.iloc[0]["Score"]


class TestFormatWalletDetail:
    """Tests for format_wallet_detail function."""

    def test_none_wallet(self) -> None:
        """Test with None wallet."""
        result = format_wallet_detail(None)
        assert "No wallet selected" in result

    def test_wallet_formatting(self) -> None:
        """Test wallet detail formatting."""
        wallet = {
            "address": "TEST_ADDRESS_123",
            "status": "active",
            "score": 0.8,
            "profile": {
                "win_rate": 0.65,
                "total_pnl": 15.5,
                "total_trades": 30,
                "avg_pnl_per_trade": 0.5,
                "avg_hold_time_hours": 2.5,
                "timing_percentile": 0.3,
                "avg_position_size_sol": 0.1,
            },
            "discovered_at": "2024-01-01T00:00:00",
            "discovery_count": 3,
            "rolling_win_rate": 0.6,
            "consecutive_losses": 1,
        }

        result = format_wallet_detail(wallet)

        assert "TEST_ADDRESS_123" in result
        assert "active" in result
        assert "65.0%" in result
        assert "15.50 SOL" in result
```

## Implementation Tasks

- [ ] Create `src/walltrack/ui/dashboard.py`
- [ ] Create `src/walltrack/ui/components/wallets.py`
- [ ] Create `src/walltrack/ui/components/status.py`
- [ ] Create component stubs (clusters, signals, positions, performance, config_panel)
- [ ] Implement wallet list view with sorting/filtering
- [ ] Implement wallet detail view
- [ ] Add manual wallet addition
- [ ] Add blacklist button
- [ ] Update main.py to launch dashboard
- [ ] Ensure < 2s response time
- [ ] Write unit tests

## Definition of Done

- [ ] Dashboard launches successfully
- [ ] Wallet list displays with sorting/filtering
- [ ] Wallet details accessible on click
- [ ] Manual wallet addition works
- [ ] Blacklist/unblacklist works from UI
- [ ] Response time < 2 seconds
- [ ] All unit tests pass
- [ ] mypy and ruff pass
