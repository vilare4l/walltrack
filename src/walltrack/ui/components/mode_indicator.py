"""Execution mode indicator for dashboard."""

import gradio as gr

from walltrack.config.settings import ExecutionMode
from walltrack.core.simulation.context import get_execution_mode


def get_mode_html() -> str:
    """Get HTML for mode indicator.

    Returns:
        HTML string for the mode indicator badge
    """
    mode = get_execution_mode()

    if mode == ExecutionMode.SIMULATION:
        return """
        <div style="
            display: inline-block;
            background: #ff6b6b;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        ">
            🔬 SIMULATION
        </div>
        """
    return """
    <div style="
        display: inline-block;
        background: #4caf50;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
    ">
        🔴 LIVE
    </div>
    """


def create_mode_indicator() -> gr.HTML:
    """Create mode indicator component.

    Returns:
        Gradio HTML component with mode indicator
    """
    return gr.HTML(value=get_mode_html())
