"""Dashboard pages package."""

from walltrack.ui.pages.alerts import create_alerts_page
from walltrack.ui.pages.config import create_config_page
from walltrack.ui.pages.exit_strategies import create_exit_strategies_page
from walltrack.ui.pages.explorer import create_explorer_page
from walltrack.ui.pages.home import create_home_page
from walltrack.ui.pages.orders import create_orders_page

__all__ = [
    "create_alerts_page",
    "create_config_page",
    "create_exit_strategies_page",
    "create_explorer_page",
    "create_home_page",
    "create_orders_page",
]
