"""Main Gradio dashboard application.

Creates the WallTrack dashboard with multipage routing.
"""

from pathlib import Path

import gradio as gr
import structlog

from walltrack.ui.components.sidebar import create_sidebar
from walltrack.ui.components.status_bar import create_status_bar
from walltrack.ui.pages import config, explorer, home, tokens, wallets

log = structlog.get_logger(__name__)

CSS_PATH = Path(__file__).parent / "css" / "tokens.css"


def create_dashboard() -> gr.Blocks:
    """Create the WallTrack dashboard with multipage routing.

    Returns:
        Gradio Blocks application with routes configured.
    """
    # Load custom CSS
    custom_css = ""
    if CSS_PATH.exists():
        custom_css = CSS_PATH.read_text()
        log.debug("dashboard_css_loaded", path=str(CSS_PATH))

    # Create Blocks without deprecated constructor params (Gradio 6.0+)
    with gr.Blocks(title="WallTrack") as app:
        pass

    # Set theme and CSS as properties (Gradio 6.0 pattern)
    app.theme = gr.themes.Soft()
    app.css = custom_css

    with app:
        # Create sidebar (shared across pages)
        _sidebar, _context_state, _context_display = create_sidebar()

        # Status bar at top
        create_status_bar()

        # Home page content (default route)
        home.render()

    # Additional pages via routing
    with app.route("Tokens", "/tokens"):
        # Sidebar for tokens page
        create_sidebar()
        create_status_bar()
        tokens.render()

    with app.route("Wallets", "/wallets"):
        # Sidebar for wallets page
        create_sidebar()
        create_status_bar()
        wallets.render()

    with app.route("Explorer", "/explorer"):
        # Sidebar for explorer page
        create_sidebar()
        create_status_bar()
        explorer.render()

    with app.route("Settings", "/settings"):
        # Sidebar for settings page
        create_sidebar()
        create_status_bar()
        config.render()

    log.info("dashboard_created", routes=["home", "tokens", "wallets", "explorer", "settings"])

    return app  # type: ignore[no-any-return]
