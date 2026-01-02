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


def get_workers_status() -> dict:
    """Get autonomous workers status for monitoring (Story 3.5.6).

    Returns:
        Dict with 'discovery', 'profiling', 'decay' keys.
        Each contains: running, last_run, processed_count, error_count, current_state.
    """
    try:
        import sys  # noqa: PLC0415

        # Only access workers if main module is already loaded (avoid import during UI construction)
        main_module = sys.modules.get("walltrack.main")
        if not main_module:
            # App not started yet, return stopped status
            return {
                "discovery": {"current_state": "stopped"},
                "profiling": {"current_state": "stopped"},
                "decay": {"current_state": "stopped"},
            }

        # Get all three workers status
        discovery_status = None
        if hasattr(main_module, "wallet_discovery_worker") and main_module.wallet_discovery_worker:
            discovery_status = main_module.wallet_discovery_worker.get_status()

        profiling_status = None
        if hasattr(main_module, "wallet_profiling_worker") and main_module.wallet_profiling_worker:
            profiling_status = main_module.wallet_profiling_worker.get_status()

        decay_status = None
        if hasattr(main_module, "wallet_decay_worker") and main_module.wallet_decay_worker:
            decay_status = main_module.wallet_decay_worker.get_status()

        return {
            "discovery": discovery_status or {"current_state": "stopped"},
            "profiling": profiling_status or {"current_state": "stopped"},
            "decay": decay_status or {"current_state": "stopped"},
        }
    except Exception as e:
        log.debug("workers_status_fetch_failed", error=str(e))
        return {
            "discovery": {"current_state": "unknown"},
            "profiling": {"current_state": "unknown"},
            "decay": {"current_state": "unknown"},
        }


def get_worker_health_icon(status: dict, poll_interval_seconds: int) -> str:
    """Determine health icon for worker based on status (Story 3.5.6).

    Args:
        status: Worker status dict from get_status()
        poll_interval_seconds: Expected poll interval (e.g., 120 for discovery)

    Returns:
        Icon string: "🟢" (healthy) | "🟡" (warning) | "🔴" (error)
    """
    state = status.get("current_state", "unknown")

    # Red: Stopped, error, unknown, or not implemented
    if state in ("stopped", "error", "unknown", "not_implemented"):
        return "🔴"

    # Red: Has errors in last run
    if status.get("error_count", 0) > 0:
        return "🔴"

    # Check last run time
    last_run = status.get("last_run")
    if last_run:
        now = datetime.now(UTC)
        seconds_since = (now - last_run).total_seconds()

        # Green: Last run within 2× poll interval
        if seconds_since < poll_interval_seconds * 2:
            return "🟢"

        # Yellow: Last run within 5× poll interval
        if seconds_since < poll_interval_seconds * 5:
            return "🟡"

        # Red: Last run > 5× poll interval (likely crashed)
        return "🔴"

    # Yellow: No last run yet (starting or idle)
    return "🟡"


def format_worker_status(status: dict, worker_name: str) -> str:
    """Format worker status for display in Status Bar (Story 3.5.6).

    Args:
        status: Worker status dict
        worker_name: "Discovery" | "Profiling" | "Decay"

    Returns:
        Compact status string (e.g., "5m ago (12 wallets)")
    """
    state = status.get("current_state", "unknown")

    # Handle special states
    if state == "stopped":
        return "stopped"
    if state == "error":
        error_count = status.get("error_count", 0)
        return f"error ({error_count} failures)"
    if state == "unknown":
        return "unavailable"
    if state == "processing":
        return "running..."

    # For all workers, show last run + processed count
    last_run = status.get("last_run")
    if last_run:
        relative = get_relative_time(last_run)
        processed = status.get("processed_count", 0)
        if processed > 0:
            return f"{relative} ({processed})"
        return f"{relative} (idle)"

    return "idle"


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
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )

        async def _get(client):
            repo = WalletRepository(client=client)
            wallets = await repo.get_all(limit=10000)  # Get all for count
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

    # Workers status (Story 3.5.6)
    workers = get_workers_status()

    discovery_worker_icon = get_worker_health_icon(workers["discovery"], poll_interval_seconds=120)
    discovery_worker_text = format_worker_status(workers["discovery"], "Discovery")

    profiling_icon = get_worker_health_icon(workers["profiling"], poll_interval_seconds=60)
    profiling_text = format_worker_status(workers["profiling"], "Profiling")

    decay_icon = get_worker_health_icon(workers["decay"], poll_interval_seconds=14400)
    decay_text = format_worker_status(workers["decay"], "Decay")

    # Use CSS classes from tokens.css - no inline styles needed
    return f"""
    <div id="status-bar">
        <span>{mode_icon} <strong>{mode}</strong></span>
        <span>{health_icon} System: {status.get('status', 'unknown')}</span>
        <span>{wallet_icon} {wallet_text}</span>
        <span>{discovery_icon} Tokens: {token_count}</span>
        <span>{wallets_icon} Wallets: {wallet_count}</span>
        <span>{discovery_icon} Discovery: {last_discovery} (next: {next_run})</span>
        <span>{discovery_worker_icon} Discovery Worker: {discovery_worker_text}</span>
        <span>{profiling_icon} Profiling Worker: {profiling_text}</span>
        <span>{decay_icon} Decay: {decay_text}</span>
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
