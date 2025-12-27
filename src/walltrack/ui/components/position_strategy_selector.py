"""Position strategy selector component."""

import gradio as gr
import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategyService,
    get_exit_strategy_service,
)
from walltrack.services.exit.strategy_assigner import (
    ExitStrategyAssigner,
    get_exit_strategy_assigner,
)

logger = structlog.get_logger(__name__)


class PositionStrategySelectorComponent:
    """Component for selecting/changing position exit strategy."""

    def __init__(self) -> None:
        self.strategy_service: ExitStrategyService | None = None
        self.assigner: ExitStrategyAssigner | None = None

    async def initialize(self) -> None:
        """Initialize services."""
        self.strategy_service = await get_exit_strategy_service()
        self.assigner = await get_exit_strategy_assigner()

    async def get_strategies_choices(self) -> list[tuple[str, str]]:
        """Get active strategies for dropdown."""
        if not self.strategy_service:
            await self.initialize()

        assert self.strategy_service is not None
        strategies = await self.strategy_service.list_all()

        # Filter to only active strategies
        active = [s for s in strategies if s.status == "active"]

        return [(f"{s.name} (v{s.version})", s.id) for s in active]

    async def change_strategy(
        self,
        position_id: str,
        strategy_id: str | None,
    ) -> tuple[bool, str]:
        """
        Change the exit strategy for a position.

        Returns:
            Tuple of (success, message)
        """
        if not strategy_id:
            return False, "Select a strategy"

        if not self.assigner:
            await self.initialize()

        assert self.assigner is not None

        try:
            success = await self.assigner.change_position_strategy(
                position_id=position_id,
                new_strategy_id=strategy_id,
            )

            if success:
                return True, "Strategy changed successfully"
            return False, "Failed to change strategy"

        except Exception as e:
            logger.error("change_strategy_error", error=str(e))
            return False, f"Error: {e}"


def create_position_strategy_selector(position_id: str) -> gr.Blocks:
    """
    Create strategy selector for a position.

    Args:
        position_id: The position ID to manage

    Returns:
        Gradio Blocks component
    """
    component = PositionStrategySelectorComponent()

    with gr.Blocks() as selector:
        gr.Markdown("### Exit Strategy")

        strategy_dropdown = gr.Dropdown(
            label="Exit Strategy",
            choices=[],
        )

        with gr.Row():
            change_btn = gr.Button("Change Strategy", variant="primary", size="sm")
            refresh_btn = gr.Button("Refresh", size="sm")

        status_text = gr.Textbox(label="Status", interactive=False)

        # Store position_id in state
        position_state = gr.State(value=position_id)

        async def load_strategies() -> gr.Dropdown:
            choices = await component.get_strategies_choices()
            return gr.update(choices=choices)

        async def do_change_strategy(
            strategy_id: str | None,
            pos_id: str,
        ) -> str:
            _, message = await component.change_strategy(pos_id, strategy_id)
            return message

        # Wire up events
        selector.load(load_strategies, [], [strategy_dropdown])
        refresh_btn.click(load_strategies, [], [strategy_dropdown])
        change_btn.click(
            do_change_strategy,
            [strategy_dropdown, position_state],
            [status_text],
        )

    return selector


def create_inline_strategy_selector(
    position_id_input: gr.Component,
) -> tuple[gr.Dropdown, gr.Button, gr.Textbox]:
    """
    Create inline strategy selector components.

    Args:
        position_id_input: Component containing position ID

    Returns:
        Tuple of (dropdown, button, status_text)
    """
    component = PositionStrategySelectorComponent()

    strategy_dropdown = gr.Dropdown(
        label="Exit Strategy",
        choices=[],
        scale=2,
    )

    change_btn = gr.Button("Change", variant="primary", size="sm", scale=1)

    status_text = gr.Textbox(
        label="",
        interactive=False,
        scale=1,
        show_label=False,
    )

    async def load_strategies() -> gr.Dropdown:
        choices = await component.get_strategies_choices()
        return gr.update(choices=choices)

    async def do_change_strategy(
        strategy_id: str | None,
        position_id: str,
    ) -> str:
        if not position_id:
            return "No position selected"
        _, message = await component.change_strategy(position_id, strategy_id)
        return message

    # Load strategies on component creation
    strategy_dropdown.attach_load_event(load_strategies, [])

    change_btn.click(
        do_change_strategy,
        [strategy_dropdown, position_id_input],
        [status_text],
    )

    return strategy_dropdown, change_btn, status_text
