"""Gradio UI module."""

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from supabase._async.client import AsyncClient
from supabase._async.client import create_client as create_async_client
from supabase.lib.client_options import AsyncClientOptions

from walltrack.config.settings import get_settings

T = TypeVar("T")


class _UISupabaseClient:
    """Minimal Supabase client wrapper for UI operations.

    Provides the same interface as SupabaseClient (`.client` property)
    but creates a fresh connection for each use to avoid event loop conflicts.
    """

    def __init__(self, async_client: AsyncClient) -> None:
        self._client = async_client

    @property
    def client(self) -> AsyncClient:
        """Return the underlying AsyncClient."""
        return self._client


async def _create_fresh_client() -> _UISupabaseClient:
    """Create a fresh Supabase client wrapper for UI operations.

    This avoids singleton issues when running in different threads/loops.
    """
    settings = get_settings()
    options = AsyncClientOptions(schema=settings.postgres_schema)
    async_client = await create_async_client(
        settings.supabase_url,
        settings.supabase_key.get_secret_value(),
        options=options,
    )
    return _UISupabaseClient(async_client)


def run_async_with_client(
    fn: Callable[[Any], Awaitable[T]],
) -> T:
    """Run async function with a fresh Supabase client.

    Creates a dedicated thread with its own event loop and client
    to avoid conflicts with Gradio's running event loop and the
    main singleton client.

    Args:
        fn: Async function that takes a Supabase client and returns a result.

    Returns:
        Result of the function.

    Raises:
        Exception: Any exception raised by the function.

    Example:
        >>> from walltrack.ui import run_async_with_client
        >>> result = run_async_with_client(
        ...     lambda client: TokenRepository(client).get_all()
        ... )
    """
    result: T | None = None
    exception: Exception | None = None

    def _thread_target() -> None:
        nonlocal result, exception

        async def _run() -> T:
            client = await _create_fresh_client()
            return await fn(client)

        try:
            result = asyncio.run(_run())
        except Exception as e:
            exception = e

    thread = threading.Thread(target=_thread_target)
    thread.start()
    thread.join(timeout=30)

    if thread.is_alive():
        raise TimeoutError("Async operation timed out after 30 seconds")

    if exception is not None:
        raise exception

    return result  # type: ignore[return-value]
