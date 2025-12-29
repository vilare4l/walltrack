"""
Wait Helpers

Polling and condition-waiting utilities.
Inspired by Cypress recurse pattern.
"""

from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def wait_for_condition(
    action: Callable[[], T],
    condition: Callable[[T], bool],
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.5,
    error_message: str = "Condition not met within timeout",
) -> T:
    """
    Poll an action until condition is met.

    Args:
        action: Function to call repeatedly
        condition: Function that returns True when condition is met
        timeout_seconds: Maximum time to wait
        poll_interval_seconds: Time between polls
        error_message: Message for timeout error

    Returns:
        The result of action() when condition is met

    Raises:
        TimeoutError: If condition not met within timeout

    Example:
        # Wait for API to return status "ready"
        result = wait_for_condition(
            action=lambda: api.get_status(),
            condition=lambda r: r["status"] == "ready",
            timeout_seconds=30.0
        )
    """
    start_time = time.time()
    last_result: T | None = None

    while time.time() - start_time < timeout_seconds:
        last_result = action()

        if condition(last_result):
            return last_result

        time.sleep(poll_interval_seconds)

    raise TimeoutError(f"{error_message}. Last result: {last_result}")
