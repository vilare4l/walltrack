"""System status component for dashboard."""

from datetime import datetime
from typing import Any

import gradio as gr
import httpx

from walltrack.config.settings import get_settings


async def fetch_system_status() -> dict[str, Any]:
    """Fetch system health status from API."""
    settings = get_settings()
    # Use api_base_url if set, otherwise fall back to localhost:port
    base_url = settings.api_base_url or f"http://localhost:{settings.port}"
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=5.0,
    ) as client:
        try:
            # Use detailed health check for service status
            response = await client.get("/health/detailed")
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }


def format_status(status: dict[str, Any]) -> str:
    """Format status for display."""
    overall = status.get("status", "unknown")
    if overall == "healthy":
        indicator = "✅"
    elif overall == "error":
        indicator = "❌"
    else:
        indicator = "⚠️"

    # Parse components from detailed health check
    components = status.get("components", {})
    neo4j_info = components.get("neo4j", {})
    supabase_info = components.get("supabase", {})

    neo4j_healthy = neo4j_info.get("healthy", False)
    supabase_healthy = supabase_info.get("healthy", False)

    neo4j_status = "✅ Connected" if neo4j_healthy else "❌ Disconnected"
    supabase_status = "✅ Connected" if supabase_healthy else "❌ Disconnected"

    # Execution mode
    exec_mode = status.get("execution_mode", "unknown").upper()
    mode_emoji = "🧪" if exec_mode == "SIMULATION" else "🔴"

    return f"""
# System Status {indicator}

**Overall:** {overall.upper()}

**Execution Mode:** {mode_emoji} {exec_mode}

**Last Check:** {status.get('timestamp', 'N/A')}

---

## Services

| Service | Status |
|---------|--------|
| Neo4j | {neo4j_status} |
| Supabase | {supabase_status} |
| API | ✅ Running |

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
        refresh_btn = gr.Button("Refresh Status", variant="primary")

    async def load_status() -> str:
        """Load and format status."""
        status = await fetch_system_status()
        return format_status(status)

    refresh_btn.click(
        fn=load_status,
        outputs=[status_display],
    )
