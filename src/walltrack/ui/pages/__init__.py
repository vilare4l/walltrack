"""Dashboard pages package."""

from walltrack.ui.pages.config import create_config_page
from walltrack.ui.pages.explorer import create_explorer_page
from walltrack.ui.pages.home import create_home_page

__all__ = ["create_config_page", "create_explorer_page", "create_home_page"]
