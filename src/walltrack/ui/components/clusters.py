"""Cluster visualization component."""

import asyncio
import os
from typing import Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings

log = structlog.get_logger()


def _get_api_url() -> str:
    """Get API base URL from environment or settings."""
    # Check for Docker environment variable first
    api_base = os.environ.get("API_BASE_URL")
    if api_base:
        return api_base

    # Fall back to settings
    settings = get_settings()
    return f"http://{settings.host}:{settings.port}"


async def _fetch_clusters() -> list[dict[str, Any]]:
    """Fetch clusters from API."""
    api_url = _get_api_url()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{api_url}/api/clusters")
            if resp.status_code == 200:
                data = resp.json()
                clusters: list[dict[str, Any]] = data.get("clusters", [])
                return clusters
    except Exception as e:
        log.warning("fetch_clusters_error", error=str(e))

    return []


async def _fetch_cluster_details(cluster_id: str) -> dict[str, Any] | None:
    """Fetch cluster details."""
    api_url = _get_api_url()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{api_url}/api/clusters/{cluster_id}")
            if resp.status_code == 200:
                result: dict[str, Any] = resp.json()
                return result
    except Exception as e:
        log.warning("fetch_cluster_details_error", error=str(e))

    return None


async def _run_cluster_discovery() -> str:
    """Run cluster discovery."""
    api_url = _get_api_url()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{api_url}/api/clusters/find")
            if resp.status_code == 200:
                data = resp.json()
                return f"Found {data.get('total', 0)} clusters"
    except Exception as e:
        return f"Error: {e!s}"

    return "No clusters found"


async def _run_cooccurrence_analysis() -> str:
    """Run co-occurrence analysis."""
    api_url = _get_api_url()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{api_url}/api/clusters/analysis/cooccurrence",
                json={},
            )
            if resp.status_code == 200:
                data = resp.json()
                return f"Found {len(data.get('edges', []))} co-occurrence relationships"
    except Exception as e:
        return f"Error: {e!s}"

    return "Analysis complete"


async def _detect_leaders() -> str:
    """Detect leaders for all clusters."""
    api_url = _get_api_url()

    clusters = await _fetch_clusters()
    detected = 0

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            for cluster in clusters:
                resp = await client.post(
                    f"{api_url}/api/clusters/{cluster['id']}/detect-leader"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("leader_address"):
                        detected += 1
    except Exception as e:
        return f"Error: {e!s}"

    return f"Detected leaders for {detected}/{len(clusters)} clusters"


async def _update_multipliers() -> str:
    """Update signal multipliers."""
    api_url = _get_api_url()

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{api_url}/api/clusters/signals/update-multipliers")
            if resp.status_code == 200:
                data = resp.json()
                return f"Updated multipliers for {len(data)} clusters"
    except Exception as e:
        return f"Error: {e!s}"

    return "Multipliers updated"


def _sync_fetch_clusters() -> pd.DataFrame:
    """Sync wrapper for fetching clusters."""
    try:
        clusters = asyncio.get_event_loop().run_until_complete(_fetch_clusters())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        clusters = loop.run_until_complete(_fetch_clusters())

    if not clusters:
        return pd.DataFrame(columns=[
            "ID", "Size", "Cohesion", "Multiplier", "Leader", "Members"
        ])

    rows = []
    for c in clusters:
        leader_addr = c.get("leader_address")
        leader_display = (leader_addr[:16] + "...") if leader_addr else "None"
        rows.append({
            "ID": c.get("id", "")[:8] + "...",
            "Size": c.get("size", 0),
            "Cohesion": f"{c.get('cohesion_score', 0):.2f}",
            "Multiplier": f"{c.get('signal_multiplier', 1.0):.2f}x",
            "Leader": leader_display,
            "Members": ", ".join(
                m.get("wallet_address", "")[:8] + "..."
                for m in (c.get("members") or [])[:3]
            ) + ("..." if len(c.get("members", [])) > 3 else ""),
        })

    return pd.DataFrame(rows)


def _sync_run_discovery() -> tuple[str, pd.DataFrame]:
    """Sync wrapper for running discovery."""
    try:
        result = asyncio.get_event_loop().run_until_complete(_run_cluster_discovery())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_cluster_discovery())

    df = _sync_fetch_clusters()
    return result, df


def _sync_run_cooccurrence() -> str:
    """Sync wrapper for co-occurrence analysis."""
    try:
        return asyncio.get_event_loop().run_until_complete(_run_cooccurrence_analysis())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_run_cooccurrence_analysis())


def _sync_detect_leaders() -> tuple[str, pd.DataFrame]:
    """Sync wrapper for detecting leaders."""
    try:
        result = asyncio.get_event_loop().run_until_complete(_detect_leaders())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_detect_leaders())

    df = _sync_fetch_clusters()
    return result, df


def _sync_update_multipliers() -> tuple[str, pd.DataFrame]:
    """Sync wrapper for updating multipliers."""
    try:
        result = asyncio.get_event_loop().run_until_complete(_update_multipliers())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_update_multipliers())

    df = _sync_fetch_clusters()
    return result, df


def create_clusters_tab() -> None:
    """Create the clusters tab UI."""
    gr.Markdown("## Cluster Analysis")
    gr.Markdown(
        "Analyze wallet relationships to identify coordinated groups. "
        "Clusters are formed from funding relationships, synchronized buying, "
        "and co-occurrence patterns."
    )

    with gr.Row():
        with gr.Column(scale=2):
            # Cluster list
            cluster_table = gr.Dataframe(
                headers=["ID", "Size", "Cohesion", "Multiplier", "Leader", "Members"],
                label="Detected Clusters",
                interactive=False,
            )

        with gr.Column(scale=1):
            # Actions panel
            gr.Markdown("### Actions")

            discover_btn = gr.Button("Discover Clusters", variant="primary")
            cooccurrence_btn = gr.Button("Analyze Co-occurrence")
            leader_btn = gr.Button("Detect Leaders")
            multiplier_btn = gr.Button("Update Multipliers")
            refresh_btn = gr.Button("Refresh")

            action_status = gr.Textbox(
                label="Status",
                interactive=False,
                lines=2,
            )

    with gr.Row(), gr.Column():
        gr.Markdown("### Cluster Statistics")
        with gr.Row():
            total_clusters = gr.Number(
                label="Total Clusters",
                value=0,
                interactive=False,
            )
            avg_cohesion = gr.Number(
                label="Avg Cohesion",
                value=0.0,
                interactive=False,
                precision=2,
            )
            avg_size = gr.Number(
                label="Avg Size",
                value=0.0,
                interactive=False,
                precision=1,
            )
            with_leader = gr.Number(
                label="With Leader",
                value=0,
                interactive=False,
            )

    with gr.Row(), gr.Column():
        gr.Markdown("### Relationship Analysis")
        gr.Markdown("""
            **Relationship Types:**
            - **FUNDED_BY**: SOL transfers between wallets
            - **BUYS_WITH**: Synchronized buying within 5-minute window
            - **CO_OCCURS**: Appearing together on same token launches
            - **MEMBER_OF**: Cluster membership
            """)

    def update_stats(df: pd.DataFrame) -> tuple[int, float, float, int]:
        """Update cluster statistics."""
        if df.empty:
            return 0, 0.0, 0.0, 0

        total = len(df)
        avg_coh = df["Cohesion"].astype(float).mean() if "Cohesion" in df else 0.0
        avg_sz = df["Size"].mean() if "Size" in df else 0.0
        leaders = sum(1 for ldr in df["Leader"] if ldr != "None") if "Leader" in df else 0

        return total, avg_coh, avg_sz, leaders

    # Event handlers
    def on_refresh() -> tuple[pd.DataFrame, int, float, float, int]:
        df = _sync_fetch_clusters()
        stats = update_stats(df)
        return df, *stats

    def on_discover() -> tuple[str, pd.DataFrame, int, float, float, int]:
        status, df = _sync_run_discovery()
        stats = update_stats(df)
        return status, df, *stats

    def on_cooccurrence() -> str:
        return _sync_run_cooccurrence()

    def on_detect_leaders() -> tuple[str, pd.DataFrame, int, float, float, int]:
        status, df = _sync_detect_leaders()
        stats = update_stats(df)
        return status, df, *stats

    def on_update_multipliers() -> tuple[str, pd.DataFrame, int, float, float, int]:
        status, df = _sync_update_multipliers()
        stats = update_stats(df)
        return status, df, *stats

    # Wire up events
    refresh_btn.click(
        fn=on_refresh,
        outputs=[cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )

    discover_btn.click(
        fn=on_discover,
        outputs=[action_status, cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )

    cooccurrence_btn.click(
        fn=on_cooccurrence,
        outputs=[action_status],
    )

    leader_btn.click(
        fn=on_detect_leaders,
        outputs=[action_status, cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )

    multiplier_btn.click(
        fn=on_update_multipliers,
        outputs=[action_status, cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )

    # Load initial data
    cluster_table.value = _sync_fetch_clusters()
