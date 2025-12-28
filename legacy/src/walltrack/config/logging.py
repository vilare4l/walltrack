"""Logging configuration using structlog."""

import logging
import sys

import structlog

from walltrack.config.settings import get_settings


def configure_logging() -> None:
    """Configure structlog for the application."""
    settings = get_settings()

    # Set log level
    log_level = getattr(logging, settings.log_level)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            # Use JSON in production, pretty print in debug
            structlog.dev.ConsoleRenderer()
            if settings.debug
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for third-party libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
