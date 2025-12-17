"""Application entry point."""

import uvicorn

from walltrack.api.app import create_app
from walltrack.config.settings import get_settings

app = create_app()


def main() -> None:
    """Run the application."""
    settings = get_settings()
    uvicorn.run(
        "walltrack.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
