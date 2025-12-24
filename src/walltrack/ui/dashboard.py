"""Main Gradio dashboard application."""

import gradio as gr
import structlog

from walltrack.config.settings import ExecutionMode, get_settings
from walltrack.core.simulation.context import get_execution_mode
from walltrack.ui.components.clusters import create_clusters_tab
from walltrack.ui.components.config_panel import create_config_tab
from walltrack.ui.components.performance import create_performance_tab
from walltrack.ui.components.positions import create_positions_tab
from walltrack.ui.components.signals import create_signals_tab
from walltrack.ui.components.status import create_status_tab
from walltrack.ui.components.wallets import create_wallets_tab

log = structlog.get_logger()


def create_dashboard() -> gr.Blocks:
    """
    Create the main Gradio dashboard.

    Returns:
        Gradio Blocks application
    """
    settings = get_settings()

    mode = get_execution_mode()
    is_simulation = mode == ExecutionMode.SIMULATION

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
        """,
    ) as dashboard:
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

            with gr.Tab("Performance", id="performance", elem_id="tab-performance"):
                create_performance_tab()

            with gr.Tab("Config", id="config", elem_id="tab-config"):
                create_config_tab()

    log.info("dashboard_created", debug=settings.debug)

    result: gr.Blocks = dashboard
    return result


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


if __name__ == "__main__":
    settings = get_settings()
    launch_dashboard(
        server_name=settings.ui_host,
        server_port=settings.ui_port,
    )
