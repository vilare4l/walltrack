"""Home page for WallTrack dashboard.

Displays system status overview and key metrics.
"""

import gradio as gr


def render() -> None:
    """Render the home page content.

    Creates the main dashboard view with system status
    and placeholder sections for future metrics.
    """
    with gr.Column():
        gr.Markdown(
            """
            # WallTrack Dashboard

            Welcome to WallTrack - Autonomous Trading Intelligence for Solana Memecoins.

            ## System Status

            *Coming in Story 2.x - Token Discovery & Surveillance*

            ---

            ### Quick Stats
            - **Mode**: SIMULATION
            - **Active Wallets**: 0
            - **Signals Today**: 0
            - **Open Positions**: 0

            ---

            ### Recent Activity

            *No activity yet. Discovery will begin in Story 2.1.*
            """
        )
