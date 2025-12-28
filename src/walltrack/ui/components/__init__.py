"""UI component modules."""

from walltrack.ui.components.change_strategy_modal import (
    apply_strategy_change,
    calculate_preview,
    create_change_strategy_modal,
    fetch_strategy,
    format_preview_markdown,
)
from walltrack.ui.components.change_strategy_modal import (
    fetch_position as fetch_position_for_strategy,
)
from walltrack.ui.components.change_strategy_modal import (
    fetch_strategies as fetch_strategies_for_change,
)
from walltrack.ui.components.change_strategy_modal import (
    open_modal as open_change_strategy_modal,
)
from walltrack.ui.components.position_details_sidebar import (
    create_position_details_sidebar,
    fetch_position_details,
    open_sidebar,
    render_active_position,
    render_closed_position,
)
from walltrack.ui.components.positions_list import (
    create_positions_list,
    format_active_positions,
    format_closed_positions,
    format_duration,
    format_exit_type,
    format_pnl_colored,
    load_positions_data,
)
from walltrack.ui.components.price_chart import (
    create_comparison_chart,
    create_mini_chart,
    create_price_chart,
)

__all__ = [
    # change_strategy_modal
    "apply_strategy_change",
    "calculate_preview",
    "create_change_strategy_modal",
    # price_chart
    "create_comparison_chart",
    "create_mini_chart",
    # position_details_sidebar
    "create_position_details_sidebar",
    # positions_list
    "create_positions_list",
    "create_price_chart",
    "fetch_position_details",
    "fetch_position_for_strategy",
    "fetch_strategies_for_change",
    "fetch_strategy",
    "format_active_positions",
    "format_closed_positions",
    "format_duration",
    "format_exit_type",
    "format_pnl_colored",
    "format_preview_markdown",
    "load_positions_data",
    "open_change_strategy_modal",
    "open_sidebar",
    "render_active_position",
    "render_closed_position",
]
