"""Integration tests for Gradio dashboard."""

import pytest
from fastapi.testclient import TestClient


# Session-scoped fixture to create the entire app once
# This avoids the issue of Gradio routes being registered multiple times
@pytest.fixture(scope="session")
def app_with_dashboard():
    """Create FastAPI app with Gradio mounted once for all tests."""
    from walltrack.main import create_app

    return create_app()


class TestDashboardIntegration:
    """Tests for Gradio dashboard integration with FastAPI."""

    def test_app_created_with_dashboard(self, app_with_dashboard) -> None:
        """
        Given: FastAPI app with Gradio mounted
        When: App is created
        Then: No exceptions are raised
        """
        assert app_with_dashboard is not None

    def test_health_endpoint_still_works(self, app_with_dashboard) -> None:
        """
        Given: FastAPI app with Gradio mounted
        When: Health endpoint is called
        Then: Returns 200 OK
        """
        client = TestClient(app_with_dashboard)
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_dashboard_path_accessible(self, app_with_dashboard) -> None:
        """
        Given: FastAPI app with Gradio mounted at /dashboard
        When: Dashboard path is accessed
        Then: Returns 200 OK (Gradio serves the page)
        """
        client = TestClient(app_with_dashboard)
        response = client.get("/dashboard")

        # Gradio returns HTML page
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestPagePlaceholders:
    """Tests for page placeholder content."""

    def test_home_page_renders(self) -> None:
        """
        Given: Home page module
        When: render() is called in Blocks context
        Then: No exceptions are raised
        """
        import gradio as gr

        from walltrack.ui.pages import home

        with gr.Blocks():
            home.render()

    def test_explorer_page_renders(self) -> None:
        """
        Given: Explorer page module
        When: render() is called in Blocks context
        Then: No exceptions are raised
        """
        import gradio as gr

        from walltrack.ui.pages import explorer

        with gr.Blocks():
            explorer.render()

    def test_config_page_renders(self) -> None:
        """
        Given: Config page module
        When: render() is called in Blocks context
        Then: No exceptions are raised
        """
        import gradio as gr

        from walltrack.ui.pages import config

        with gr.Blocks():
            config.render()


class TestSidebar:
    """Tests for sidebar component."""

    def test_sidebar_creates(self) -> None:
        """
        Given: create_sidebar() function
        When: Called in Blocks context
        Then: Returns sidebar, state, and display components
        """
        import gradio as gr

        from walltrack.ui.components.sidebar import create_sidebar

        with gr.Blocks():
            sidebar, context_state, context_display = create_sidebar()

        assert sidebar is not None
        assert context_state is not None
        assert context_display is not None

    def test_update_sidebar_context_with_none(self) -> None:
        """
        Given: update_sidebar_context() function
        When: Called with None
        Then: Returns default message
        """
        from walltrack.ui.components.sidebar import update_sidebar_context

        result = update_sidebar_context(None)
        assert "Select an element" in result

    def test_update_sidebar_context_with_data(self) -> None:
        """
        Given: update_sidebar_context() function
        When: Called with context dictionary
        Then: Returns formatted markdown
        """
        from walltrack.ui.components.sidebar import update_sidebar_context

        context = {"Name": "Test", "Value": 123}
        result = update_sidebar_context(context)

        assert "Name" in result
        assert "Test" in result
        assert "Value" in result
