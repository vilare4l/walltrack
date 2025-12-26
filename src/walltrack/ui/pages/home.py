"""Home page - answers 'is it working?' in 2 seconds."""

from datetime import datetime
from typing import Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings

log = structlog.get_logger()


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    return settings.api_base_url or f"http://localhost:{settings.port}"


async def fetch_kpis() -> dict[str, Any]:
    """Fetch KPI data for dashboard.

    Returns:
        Dict with KPI values
    """
    base_url = _get_api_base_url()
    kpis = {
        "pnl_today": 0.0,
        "active_positions": 0,
        "signals_today": 0,
        "win_rate": 0.0,
        "trades_today": 0,
    }

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
            # Get health/status for basic metrics
            try:
                resp = await client.get("/health/detailed")
                if resp.status_code == 200:
                    data = resp.json()
                    kpis["active_positions"] = data.get("active_positions", 0)
                    kpis["trades_today"] = data.get("trades_today", 0)
                    kpis["pnl_today"] = data.get("pnl_today", 0.0)
            except Exception:
                pass

            # Get signal count
            try:
                resp = await client.get("/api/signals/stats/today")
                if resp.status_code == 200:
                    data = resp.json()
                    kpis["signals_today"] = data.get("count", 0)
            except Exception:
                pass

    except Exception as e:
        log.warning("fetch_kpis_error", error=str(e))

    return kpis


async def fetch_active_positions() -> list[dict[str, Any]]:
    """Fetch active positions.

    Returns:
        List of position dicts
    """
    base_url = _get_api_base_url()

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
            resp = await client.get("/api/positions/active")
            if resp.status_code == 200:
                data = resp.json()
                positions: list[dict[str, Any]] = data.get("positions", [])
                return positions
    except Exception as e:
        log.warning("fetch_positions_error", error=str(e))

    return []


async def fetch_recent_alerts() -> list[dict[str, Any]]:
    """Fetch recent alerts.

    Returns:
        List of alert dicts
    """
    base_url = _get_api_base_url()

    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=5.0) as client:
            resp = await client.get("/api/alerts/recent", params={"limit": 5})
            if resp.status_code == 200:
                data = resp.json()
                alerts: list[dict[str, Any]] = data.get("alerts", [])
                return alerts
    except Exception:
        pass

    return []


def format_pnl(value: float) -> str:
    """Format PnL value with color."""
    color = "#10b981" if value >= 0 else "#ef4444"
    return f'<span style="color: {color}; font-weight: bold;">{value:+.4f} SOL</span>'


def positions_to_dataframe(positions: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert positions to DataFrame.

    Args:
        positions: List of position dicts

    Returns:
        DataFrame for display
    """
    if not positions:
        return pd.DataFrame(
            columns=["Token", "Entry", "Current", "P&L %", "Time", "Strategy"]
        )

    rows = []
    for p in positions:
        entry_price = p.get("entry_price", 0)
        current_price = p.get("current_price", entry_price)
        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        entry_time = p.get("entry_time")
        if entry_time:
            try:
                dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                hours_held = (datetime.utcnow() - dt.replace(tzinfo=None)).total_seconds() / 3600
                time_display = f"{hours_held:.1f}h" if hours_held < 24 else f"{hours_held/24:.1f}d"
            except Exception:
                time_display = "-"
        else:
            time_display = "-"

        rows.append({
            "Token": p.get("token_symbol") or p.get("token_address", "")[:8],
            "Entry": f"{entry_price:.8f}",
            "Current": f"{current_price:.8f}",
            "P&L %": f"{pnl_pct:+.1f}%",
            "Time": time_display,
            "Strategy": p.get("exit_strategy_id", "default").replace("preset-", ""),
            "_position_data": p,  # Hidden for sidebar
        })

    return pd.DataFrame(rows)


def render_kpi_card(title: str, value: str, subtitle: str = "") -> str:
    """Render a KPI card as HTML.

    Args:
        title: Card title
        value: Main value
        subtitle: Optional subtitle

    Returns:
        HTML string
    """
    return f"""
    <div style="background: white; border-radius: 12px; padding: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center;
                border: 1px solid #e5e7eb;">
        <div style="color: #6b7280; font-size: 0.85em; margin-bottom: 8px;">
            {title}
        </div>
        <div style="font-size: 1.8em; font-weight: bold; color: #111827;">
            {value}
        </div>
        <div style="color: #9ca3af; font-size: 0.8em; margin-top: 4px;">
            {subtitle}
        </div>
    </div>
    """


def render_alerts(alerts: list[dict[str, Any]]) -> str:
    """Render alerts as HTML.

    Args:
        alerts: List of alert dicts

    Returns:
        HTML string
    """
    if not alerts:
        return '<div style="color: #6b7280; padding: 12px;">No recent alerts</div>'

    items = []
    for alert in alerts[:5]:
        alert_type = alert.get("type", "info")
        icon = {"warning": "⚠️", "error": "🔴", "success": "✅"}.get(alert_type, "i")
        items.append(f"""
            <div style="padding: 8px 12px; border-bottom: 1px solid #f3f4f6;">
                {icon} {alert.get("message", "")}
                <span style="color: #9ca3af; font-size: 0.8em; float: right;">
                    {alert.get("timestamp", "")[:16]}
                </span>
            </div>
        """)

    return f"""
    <div style="background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
        {"".join(items)}
    </div>
    """


async def load_home_data() -> tuple[str, str, str, str, pd.DataFrame, str]:
    """Load all home page data.

    Returns:
        Tuple of KPI HTML cards, positions dataframe, alerts HTML
    """
    kpis = await fetch_kpis()
    positions = await fetch_active_positions()
    alerts = await fetch_recent_alerts()

    # KPI cards
    pnl_value = kpis["pnl_today"]
    pnl_display = f"{pnl_value:+.4f}" if pnl_value else "0.0000"
    pnl_color = "#10b981" if pnl_value >= 0 else "#ef4444"

    kpi1 = render_kpi_card("P&L Today", f'<span style="color:{pnl_color}">{pnl_display} SOL</span>')
    kpi2 = render_kpi_card("Active Positions", str(kpis["active_positions"]))
    kpi3 = render_kpi_card("Signals Today", str(kpis["signals_today"]))
    kpi4 = render_kpi_card("Trades Today", str(kpis["trades_today"]))

    # Positions table
    positions_df = positions_to_dataframe(positions)

    # Alerts
    alerts_html = render_alerts(alerts)

    return kpi1, kpi2, kpi3, kpi4, positions_df, alerts_html


def create_home_page(sidebar_state: gr.State) -> None:
    """Create the home page UI.

    Args:
        sidebar_state: Shared state for sidebar context
    """
    # KPI Cards Row
    with gr.Row(equal_height=True):
        kpi1 = gr.HTML(render_kpi_card("P&L Today", "Loading..."))
        kpi2 = gr.HTML(render_kpi_card("Active Positions", "-"))
        kpi3 = gr.HTML(render_kpi_card("Signals Today", "-"))
        kpi4 = gr.HTML(render_kpi_card("Trades Today", "-"))

    gr.Markdown("---")

    # Main content
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### Active Positions")
            positions_table = gr.Dataframe(
                headers=["Token", "Entry", "Current", "P&L %", "Time", "Strategy"],
                interactive=False,
                row_count=10,
                elem_id="home-positions-table",
            )

        with gr.Column(scale=1):
            gr.Markdown("### Recent Alerts")
            alerts_display = gr.HTML(
                '<div style="color: #6b7280;">Loading...</div>'
            )

    # Refresh button
    with gr.Row():
        refresh_btn = gr.Button("Refresh", variant="primary", elem_id="home-refresh-btn")

    # Event handlers
    async def on_refresh() -> tuple[str, str, str, str, pd.DataFrame, str]:
        return await load_home_data()

    refresh_btn.click(
        fn=on_refresh,
        outputs=[kpi1, kpi2, kpi3, kpi4, positions_table, alerts_display],
    )

    # Position selection -> sidebar
    def on_position_select(evt: gr.SelectData, df: pd.DataFrame) -> dict[str, Any]:
        if evt.index[0] < len(df):
            row = df.iloc[evt.index[0]]
            position_data = row.get("_position_data", {})
            if not position_data:
                # Reconstruct minimal data
                position_data = {
                    "token_symbol": row.get("Token", ""),
                    "entry_price": float(row.get("Entry", "0").replace(",", "")),
                    "current_price": float(row.get("Current", "0").replace(",", "")),
                    "exit_strategy_id": row.get("Strategy", "default"),
                }
            return {"type": "position", "data": position_data}
        return {"type": None, "data": None}

    positions_table.select(
        fn=on_position_select,
        inputs=[positions_table],
        outputs=[sidebar_state],
    )
