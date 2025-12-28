"""Auto-refresh status bar component."""

from datetime import datetime
from typing import Any

import httpx
import structlog

from walltrack.config.settings import get_settings

log = structlog.get_logger()


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    return settings.api_base_url or f"http://localhost:{settings.port}"


async def fetch_status_data() -> dict[str, Any]:
    """Fetch all status data for the status bar.

    Returns:
        Dict with status information
    """
    base_url = _get_api_base_url()

    status = {
        "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
        "discovery": {"status": "unknown", "last_run": None, "next_run": None},
        "signals_today": 0,
        "active_wallets": 0,
        "webhook_status": "unknown",
        "execution_mode": "unknown",
        "api_healthy": False,
    }

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
            # Health check
            try:
                health_resp = await client.get("/health/detailed")
                if health_resp.status_code == 200:
                    health = health_resp.json()
                    status["api_healthy"] = health.get("status") == "healthy"
                    status["execution_mode"] = health.get("execution_mode", "unknown")
            except Exception:
                pass

            # Discovery status
            try:
                disc_resp = await client.get("/api/discovery/status")
                if disc_resp.status_code == 200:
                    disc = disc_resp.json()
                    status["discovery"] = {
                        "status": "running" if disc.get("is_running") else "idle",
                        "last_run": disc.get("last_run_at"),
                        "next_run": disc.get("next_run_at"),
                    }
            except Exception:
                pass

            # Wallet count
            try:
                wallet_resp = await client.get("/api/wallets", params={"limit": 1})
                if wallet_resp.status_code == 200:
                    wallet_data = wallet_resp.json()
                    status["active_wallets"] = wallet_data.get("total", 0)
            except Exception:
                pass

            # Signal count today
            try:
                signal_resp = await client.get("/api/signals/stats/today")
                if signal_resp.status_code == 200:
                    signal_data = signal_resp.json()
                    status["signals_today"] = signal_data.get("count", 0)
            except Exception:
                pass

            # Webhook status
            try:
                wh_resp = await client.get("/webhooks/helius/status")
                if wh_resp.status_code == 200:
                    wh_data = wh_resp.json()
                    status["webhook_status"] = "synced" if wh_data.get("synced") else "pending"
            except Exception:
                pass

    except Exception as e:
        log.warning("status_bar_fetch_error", error=str(e))

    return status


def render_status_bar(status: dict[str, Any] | None = None) -> str:
    """Render the status bar HTML.

    Args:
        status: Status data dict (if None, shows loading)

    Returns:
        HTML string for status bar
    """
    if not status:
        return """
        <div style="display: flex; justify-content: space-between; align-items: center;
                    padding: 8px 16px; background: #f3f4f6; border-radius: 8px;
                    font-size: 0.9em; margin-bottom: 16px;">
            <span>Loading status...</span>
        </div>
        """

    # Status indicators
    api_indicator = "🟢" if status.get("api_healthy") else "🔴"
    discovery_status = status.get("discovery", {})
    disc_status = discovery_status.get("status")
    disc_indicator = "🟢" if disc_status == "idle" else "🟡" if disc_status == "running" else "⚪"
    webhook_indicator = "🟢" if status.get("webhook_status") == "synced" else "🟡"

    # Execution mode
    exec_mode = status.get("execution_mode", "unknown").upper()
    mode_colors = {"SIMULATION": "#f59e0b", "LIVE": "#10b981"}
    mode_color = mode_colors.get(exec_mode, "#6b7280")

    # Format times
    last_run = discovery_status.get("last_run")
    next_run = discovery_status.get("next_run")
    last_run_display = last_run[:16].replace("T", " ") if last_run else "Never"
    next_run_display = next_run[:16].replace("T", " ") if next_run else "Not scheduled"

    return f"""
    <div style="display: flex; justify-content: space-between; align-items: center;
                padding: 10px 16px; background: linear-gradient(90deg, #f8fafc 0%, #f1f5f9 100%);
                border-radius: 8px; font-size: 0.85em; margin-bottom: 16px;
                border: 1px solid #e2e8f0; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">

        <div style="display: flex; gap: 24px; align-items: center;">
            <span title="API Status">
                {api_indicator} <strong>API</strong>
            </span>
            <span title="Discovery: Last {last_run_display}, Next {next_run_display}">
                {disc_indicator} <strong>Discovery</strong>
                <span style="color: #64748b; font-size: 0.9em;">({last_run_display})</span>
            </span>
            <span title="Webhook Status">
                {webhook_indicator} <strong>Webhook</strong>
            </span>
        </div>

        <div style="display: flex; gap: 24px; align-items: center;">
            <span>
                <strong>{status.get("signals_today", 0)}</strong>
                <span style="color: #64748b;">signals today</span>
            </span>
            <span>
                <strong>{status.get("active_wallets", 0)}</strong>
                <span style="color: #64748b;">wallets</span>
            </span>
            <span style="background: {mode_color}; color: white; padding: 2px 8px;
                         border-radius: 4px; font-weight: bold; font-size: 0.85em;">
                {exec_mode}
            </span>
            <span style="color: #94a3b8; font-size: 0.85em;">
                {status.get("timestamp", "")}
            </span>
        </div>
    </div>
    """


async def get_status_bar_html() -> str:
    """Fetch status and render HTML.

    Returns:
        Rendered status bar HTML
    """
    try:
        status = await fetch_status_data()
        return render_status_bar(status)
    except Exception as e:
        log.error("status_bar_render_error", error=str(e))
        return render_status_bar(None)
