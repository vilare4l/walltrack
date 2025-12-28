"""Main Gradio dashboard application with multipage navigation."""

import gradio as gr
import structlog

from walltrack.config.settings import ExecutionMode, get_settings
from walltrack.core.simulation.context import get_execution_mode
from walltrack.ui.components.clusters import create_clusters_tab
from walltrack.ui.components.config_panel import create_config_tab
from walltrack.ui.components.discovery import create_discovery_tab
from walltrack.ui.components.positions import create_positions_tab
from walltrack.ui.components.sidebar import create_sidebar_state, update_sidebar_content
from walltrack.ui.components.signals import create_signals_tab
from walltrack.ui.components.status import create_status_tab
from walltrack.ui.components.status_bar import get_status_bar_html
from walltrack.ui.components.wallets import create_wallets_tab
from walltrack.ui.pages.config import create_config_page
from walltrack.ui.pages.exit_strategies import create_exit_strategies_page
from walltrack.ui.pages.explorer import create_explorer_page
from walltrack.ui.pages.home import create_home_page
from walltrack.ui.pages.orders import create_orders_page

log = structlog.get_logger()

# Custom CSS for the dashboard
DASHBOARD_CSS = """
    .wallet-card { padding: 10px; margin: 5px; border-radius: 8px; }
    .metric-positive { color: #10b981; }
    .metric-negative { color: #ef4444; }
    .status-active { background-color: #10b981; }
    .status-decay { background-color: #f59e0b; }
    .status-blacklisted { background-color: #ef4444; }
    .simulation-banner {
        background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
        color: white;
        padding: 12px 20px;
        text-align: center;
        font-weight: bold;
        font-size: 1.1em;
        border-radius: 8px;
        margin-bottom: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .live-banner {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 12px 20px;
        text-align: center;
        font-weight: bold;
        font-size: 1.1em;
        border-radius: 8px;
        margin-bottom: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
"""


def create_dashboard() -> gr.Blocks:  # noqa: PLR0915
    """
    Create the main Gradio dashboard with multipage navigation.

    Returns:
        Gradio Blocks application
    """
    settings = get_settings()

    with gr.Blocks(title="WallTrack Dashboard") as demo:
        # Navbar for page navigation
        gr.Navbar(
            value=[],
            main_page_name="Home",
            visible=True,
            elem_id="main-navbar",
        )

        # Header
        gr.Markdown("# WallTrack Dashboard", elem_id="dashboard-title")
        gr.Markdown("Autonomous Solana Memecoin Trading System", elem_id="dashboard-subtitle")

        # Status Bar with auto-refresh (every 30 seconds)
        status_bar = gr.HTML(
            value="<div>Loading status...</div>",
            every=30,
            elem_id="status-bar",
        )
        status_bar.change(fn=get_status_bar_html, outputs=[status_bar])

        # Shared sidebar state
        sidebar_state = create_sidebar_state()

        # Main content area with sidebar
        with gr.Row():
            # Main content column
            with gr.Column(scale=3):
                # Home page content (main page)
                create_home_page(sidebar_state)

            # Contextual sidebar
            with gr.Sidebar(
                position="right",
                width=380,
                open=False,
                label="Details",
                elem_id="context-sidebar",
            ):
                sidebar_content = gr.Markdown(
                    "### No Selection\n\nClick on any row to view details.",
                    elem_id="sidebar-content",
                )

        # Update sidebar when state changes
        sidebar_state.change(
            fn=update_sidebar_content,
            inputs=[sidebar_state],
            outputs=[sidebar_content],
        )

    # ========== EXPLORER PAGE ==========
    with demo.route("Explorer"):
        gr.Navbar(
            value=[],
            main_page_name="Home",
            visible=True,
        )

        gr.Markdown("# WallTrack Dashboard", elem_id="dashboard-title")
        gr.Markdown("Autonomous Solana Memecoin Trading System", elem_id="dashboard-subtitle")

        # Status Bar
        explorer_status_bar = gr.HTML(
            value="<div>Loading status...</div>",
            every=30,
            elem_id="explorer-status-bar",
        )
        explorer_status_bar.change(fn=get_status_bar_html, outputs=[explorer_status_bar])

        # Shared sidebar state for Explorer
        explorer_sidebar_state = create_sidebar_state()

        with gr.Row():
            with gr.Column(scale=3):
                create_explorer_page(explorer_sidebar_state)

            with gr.Sidebar(
                position="right",
                width=380,
                open=False,
                label="Details",
                elem_id="explorer-sidebar",
            ):
                explorer_sidebar_content = gr.Markdown(
                    "### No Selection\n\nClick on any row to view details.",
                )

        explorer_sidebar_state.change(
            fn=update_sidebar_content,
            inputs=[explorer_sidebar_state],
            outputs=[explorer_sidebar_content],
        )

    # ========== ORDERS PAGE ==========
    with demo.route("Orders"):
        gr.Navbar(
            value=[],
            main_page_name="Home",
            visible=True,
        )

        gr.Markdown("# WallTrack Dashboard", elem_id="dashboard-title")
        gr.Markdown("Autonomous Solana Memecoin Trading System", elem_id="dashboard-subtitle")

        # Status Bar
        orders_status_bar = gr.HTML(
            value="<div>Loading status...</div>",
            every=30,
            elem_id="orders-status-bar",
        )
        orders_status_bar.change(fn=get_status_bar_html, outputs=[orders_status_bar])

        # Shared sidebar state for Orders
        orders_sidebar_state = create_sidebar_state()

        with gr.Row():
            with gr.Column(scale=3):
                create_orders_page(orders_sidebar_state)

            with gr.Sidebar(
                position="right",
                width=380,
                open=False,
                label="Order Details",
                elem_id="orders-sidebar",
            ):
                orders_sidebar_content = gr.Markdown(
                    "### No Selection\n\nClick on any order to view details.",
                )

        orders_sidebar_state.change(
            fn=update_sidebar_content,
            inputs=[orders_sidebar_state],
            outputs=[orders_sidebar_content],
        )

    # ========== CONFIG PAGE ==========
    with demo.route("Settings"):
        gr.Navbar(
            value=[],
            main_page_name="Home",
            visible=True,
        )

        gr.Markdown("# WallTrack Dashboard", elem_id="dashboard-title")
        gr.Markdown("Autonomous Solana Memecoin Trading System", elem_id="dashboard-subtitle")

        # Status Bar (no sidebar on config page)
        config_status_bar = gr.HTML(
            value="<div>Loading status...</div>",
            every=30,
            elem_id="config-status-bar",
        )
        config_status_bar.change(fn=get_status_bar_html, outputs=[config_status_bar])

        create_config_page()

    # ========== EXIT STRATEGIES PAGE ==========
    with demo.route("Exit Strategies"):
        gr.Navbar(
            value=[],
            main_page_name="Home",
            visible=True,
        )

        gr.Markdown("# WallTrack Dashboard", elem_id="dashboard-title")
        gr.Markdown("Autonomous Solana Memecoin Trading System", elem_id="dashboard-subtitle")

        # Status Bar
        exit_strategies_status_bar = gr.HTML(
            value="<div>Loading status...</div>",
            every=30,
            elem_id="exit-strategies-status-bar",
        )
        exit_strategies_status_bar.change(
            fn=get_status_bar_html, outputs=[exit_strategies_status_bar]
        )

        create_exit_strategies_page()

    log.info("dashboard_created", debug=settings.debug, multipage=True)

    result: gr.Blocks = demo
    return result


def create_legacy_dashboard() -> gr.Blocks:
    """
    Create the legacy 8-tab dashboard (for backwards compatibility).

    Returns:
        Gradio Blocks application with tabs
    """
    settings = get_settings()
    mode = get_execution_mode()
    is_simulation = mode == ExecutionMode.SIMULATION

    with gr.Blocks(title="WallTrack Dashboard (Legacy)") as dashboard:
        gr.Markdown("# WallTrack Dashboard", elem_id="dashboard-title")
        gr.Markdown("Autonomous Solana Memecoin Trading System", elem_id="dashboard-subtitle")

        # Execution Mode Banner
        if is_simulation:
            gr.HTML(
                '<div class="simulation-banner">'
                "SIMULATION MODE - All trades are simulated, no real transactions"
                "</div>",
                elem_id="mode-banner",
            )
        else:
            gr.HTML(
                '<div class="live-banner">'
                "LIVE MODE - Real transactions enabled"
                "</div>",
                elem_id="mode-banner",
            )

        with gr.Tabs(elem_id="main-tabs"):
            with gr.Tab("Status", id="status", elem_id="tab-status"):
                create_status_tab()

            with gr.Tab("Wallets", id="wallets", elem_id="tab-wallets"):
                create_wallets_tab()

            with gr.Tab("Clusters", id="clusters", elem_id="tab-clusters"):
                create_clusters_tab()

            with gr.Tab("Signals", id="signals", elem_id="tab-signals"):
                create_signals_tab()

            with gr.Tab("Positions", id="positions", elem_id="tab-positions"):
                create_positions_tab()

            with gr.Tab("Discovery", id="discovery", elem_id="tab-discovery"):
                create_discovery_tab()

            with gr.Tab("Config", id="config", elem_id="tab-config"):
                create_config_tab()

    log.info("legacy_dashboard_created", debug=settings.debug)

    result: gr.Blocks = dashboard
    return result


def launch_dashboard(
    share: bool = False,
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
    legacy: bool = False,
) -> None:
    """
    Launch the dashboard.

    Args:
        share: Create public share link
        server_name: Server hostname
        server_port: Server port
        legacy: Use legacy 8-tab layout instead of multipage
    """
    dashboard = create_legacy_dashboard() if legacy else create_dashboard()
    dashboard.launch(
        share=share,
        server_name=server_name,
        server_port=server_port,
        theme=gr.themes.Soft(),
        css=DASHBOARD_CSS,
    )


if __name__ == "__main__":
    settings = get_settings()
    launch_dashboard(
        server_name=settings.ui_host,
        server_port=settings.ui_port,
    )
