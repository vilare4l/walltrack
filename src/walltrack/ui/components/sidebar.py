"""Sidebar component for contextual information.

Provides a right-side panel for displaying:
- Selected item details
- Context-specific actions
- Quick actions
"""

import gradio as gr


def create_sidebar() -> tuple[gr.Sidebar, gr.State, gr.Markdown]:
    """Create the sidebar with context display area.

    Returns:
        Tuple of (sidebar, context_state, context_display).
    """
    context_state = gr.State(value=None)

    with gr.Sidebar(
        position="right",
        open=False,
    ) as sidebar:
        gr.Markdown("## Context")

        context_display = gr.Markdown(
            value="*Select an element to view details*",
            elem_id="sidebar-context",
        )

        gr.Markdown("---")
        gr.Markdown("### Actions")
        gr.Markdown("*Actions will appear based on selection*")

    return sidebar, context_state, context_display


def update_sidebar_context(context: dict[str, object] | None) -> str:
    """Update sidebar context display.

    Args:
        context: Dictionary with context information or None.

    Returns:
        Markdown string for display.
    """
    if context is None:
        return "*Select an element to view details*"

    lines = []
    for key, value in context.items():
        lines.append(f"**{key}**: {value}")

    return "\n\n".join(lines) if lines else "*No details available*"
