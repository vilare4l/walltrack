"""Configuration module for WallTrack.

Usage:
    from walltrack.config import get_settings

    settings = get_settings()  # Cached singleton
    print(settings.app_name)

Note:
    We intentionally don't export a module-level `settings` instance
    because that would fail on import if required env vars aren't set.
    Use `get_settings()` to get the cached instance at runtime.
"""

from walltrack.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
