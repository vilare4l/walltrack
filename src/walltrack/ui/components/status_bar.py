"""Status bar component with auto-refresh.

Displays system status information including:
- Mode (SIMULATION/LIVE)
- System health
- Discovery status
- Signal counts
- Wallet status (connected/not connected)
"""

from datetime import UTC, datetime

import gradio as gr
import structlog

from walltrack.config import get_settings
from walltrack.core.wallet import truncate_address
from walltrack.ui import run_async_with_client

log = structlog.get_logger(__name__)


def get_relative_time(dt: datetime) -> str:
    """Convert datetime to relative string like '2h ago'.

    Args:
        dt: Datetime to convert (must be timezone-aware).

    Returns:
        Human-readable relative time string.
    """
    now = datetime.now(UTC)
    diff = now - dt

    seconds = diff.total_seconds()
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    else:
        return f"{int(seconds / 86400)}d ago"


def get_trading_wallet_status() -> str | None:
    """Get trading wallet status for status bar display.

    Returns:
        Truncated wallet address if connected, None otherwise.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _get(client):
            repo = ConfigRepository(client)
            return await repo.get_trading_wallet()

        address = run_async_with_client(_get)
        if address:
            return truncate_address(address)
        return None
    except Exception as e:
        log.debug("status_bar_wallet_check_failed", error=str(e))
        return None


def get_token_count() -> int:
    """Get total discovered token count for status bar display.

    Returns:
        Total number of tokens in database, 0 on error.
    """
    try:
        from walltrack.data.supabase.repositories.token_repo import (  # noqa: PLC0415
            TokenRepository,
        )

        async def _get(client):
            repo = TokenRepository(client)
            return await repo.get_count()

        return run_async_with_client(_get)
    except Exception as e:
        log.debug("status_bar_token_count_failed", error=str(e))
        return 0


def get_wallet_count() -> int:
    """Get total discovered wallet count for status bar display.

    Returns:
        Total number of wallets in database, 0 on error.
    """
    try:
        from walltrack.data.repositories.wallet_repository import (  # noqa: PLC0415
            WalletRepository,
        )

        async def _get(client):
            repo = WalletRepository(supabase_client=client.client)
            wallets = await repo.list_wallets(limit=10000)  # Get all for count
            return len(wallets)

        return run_async_with_client(_get)
    except Exception as e:
        log.debug("status_bar_wallet_count_failed", error=str(e))
        return 0


def get_discovery_status() -> tuple[str, str]:
    """Get discovery status for status bar display.

    Returns:
        Tuple of (last_discovery_relative, next_run_relative).
        Example: ("2h ago", "2h")
    """
    try:
        from walltrack.data.supabase.repositories.token_repo import (  # noqa: PLC0415
            TokenRepository,
        )
        from walltrack.scheduler.jobs import get_next_run_time  # noqa: PLC0415

        # Get last discovery time from most recently updated token
        async def _get_last_checked(client):
            repo = TokenRepository(client)
            return await repo.get_latest_checked_time()

        last_checked = run_async_with_client(_get_last_checked)

        # Format last discovery time
        if last_checked:
            dt = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
            last_str = get_relative_time(dt)
        else:
            last_str = "never"

        # Format next run time
        next_run = get_next_run_time()
        if next_run:
            dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            diff = dt - now
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() / 3600)
                if hours > 0:
                    next_str = f"{hours}h"
                else:
                    minutes = int(diff.total_seconds() / 60)
                    next_str = f"{minutes}m"
            else:
                next_str = "soon"
        else:
            next_str = "--"

        return (last_str, next_str)

    except Exception as e:
        log.debug("discovery_status_failed", error=str(e))
        return ("--", "--")


def get_system_status() -> dict[str, object]:
    """Get system status by checking database client singletons directly.

    This avoids HTTP self-calls which can cause issues during startup
    and adds unnecessary latency.

    Returns:
        Status dictionary with health information.
    """
    # Import client modules to check singleton state (intentional late import)
    import walltrack.data.neo4j.client as neo4j_module  # noqa: PLC0415
    import walltrack.data.supabase.client as supabase_module  # noqa: PLC0415

    supabase_connected = supabase_module._supabase_client is not None
    neo4j_connected = neo4j_module._neo4j_client is not None

    all_healthy = supabase_connected and neo4j_connected
    overall_status = "ok" if all_healthy else "degraded"

    return {
        "status": overall_status,
        "databases": {
            "supabase": {"healthy": supabase_connected},
            "neo4j": {"healthy": neo4j_connected},
        },
    }


def render_status_html() -> str:
    """Render status bar as HTML string.

    Returns:
        HTML string containing the status bar.
    """
    settings = get_settings()
    status = get_system_status()

    # Determine overall health
    db_healthy = status.get("status") == "ok"
    health_icon = "\U0001F7E2" if db_healthy else "\U0001F534"  # Green/Red circle

    # Mode indicator (settings.trading_mode has default "simulation" in Settings model)
    mode = settings.trading_mode.upper()
    mode_icon = "\U0001F7E2" if mode == "LIVE" else "\U0001F535"  # Green for live, Blue for sim

    # Wallet status (Story 1.5)
    wallet_address = get_trading_wallet_status()
    if wallet_address:
        wallet_icon = "\U0001F7E2"  # Green circle
        wallet_text = f"Wallet: {wallet_address}"
    else:
        wallet_icon = "\U0001F534"  # Red circle
        wallet_text = "Wallet: Not Connected"

    # Discovery status (Story 2.1 + 2.2)
    last_discovery, next_run = get_discovery_status()
    token_count = get_token_count()
    # Green if has tokens, Yellow if none
    discovery_icon = "\U0001F7E2" if token_count > 0 else "\U0001F7E1"

    # Wallet count (Story 3.1)
    wallet_count = get_wallet_count()
    # Green if has wallets, Yellow if none
    wallets_icon = "\U0001F7E2" if wallet_count > 0 else "\U0001F7E1"

    # Use CSS classes from tokens.css - no inline styles needed
    return f"""
    <div id="status-bar">
        <span>{mode_icon} <strong>{mode}</strong></span>
        <span>{health_icon} System: {status.get('status', 'unknown')}</span>
        <span>{wallet_icon} {wallet_text}</span>
        <span>{discovery_icon} Tokens: {token_count}</span>
        <span>{wallets_icon} Wallets: {wallet_count}</span>
        <span>{discovery_icon} Discovery: {last_discovery} (next: {next_run})</span>
        <span>\U0001F7E2 Signals: 0 today</span>
    </div>
    """


def create_status_bar() -> gr.HTML:
    """Create status bar with auto-refresh.

    Returns:
        Gradio HTML component with 30-second auto-refresh.
    """
    return gr.HTML(
        value=render_status_html,
        every=30,  # Refresh every 30 seconds
        elem_id="status-bar",
    )
