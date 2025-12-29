"""
Page Objects

Page Object Model (POM) for WallTrack Gradio dashboard.
Encapsulates page interactions and locators.

Usage:
    from tests.support.page_objects import HomePage, ExplorerPage

    home = HomePage(page)
    home.navigate()
    home.assert_status_bar_visible()

Pattern:
    - One class per page/major component
    - Methods for actions (click, fill)
    - Properties for locators
    - Assertions as methods
"""

# Page objects will be added as UI is built
# Example imports:
# from tests.support.page_objects.home_page import HomePage
# from tests.support.page_objects.explorer_page import ExplorerPage
# from tests.support.page_objects.config_page import ConfigPage
