# Story 2.7: Dashboard - Cluster Visualization

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: ready
- **Priority**: Medium
- **FR**: FR48

## User Story

**As an** operator,
**I want** to view cluster relationships and members in the dashboard,
**So that** I can understand the network of insider groups.

## Acceptance Criteria

### AC 1: Cluster List View
**Given** the dashboard is open
**When** operator navigates to Clusters tab
**Then** list of all clusters is displayed (id, size, strength, leader count)
**And** clusters can be sorted by size or strength
**And** clusters can be filtered by minimum size

### AC 2: Cluster Detail View
**Given** a cluster is selected
**When** cluster detail view opens
**Then** all member wallets are listed with their role (leader/member)
**And** cluster metrics are displayed (total PnL, avg win rate)
**And** relationship types between members are summarized

### AC 3: Graph Visualization
**Given** the cluster visualization component
**When** operator requests graph view
**Then** a visual representation shows wallets as nodes
**And** relationships (FUNDED_BY, SYNCED_BUY, CO_OCCURS) are shown as edges
**And** leaders are visually distinguished (color/size)

### AC 4: Navigation
**Given** a wallet in cluster view
**When** operator clicks on it
**Then** navigation to wallet detail (from Epic 1) is available

## Technical Notes

- FR48 (cluster part): Cluster analysis view
- Implement in `src/walltrack/ui/components/clusters.py`
- Consider simple network visualization (Gradio + plotly or pyvis)

---

## Technical Specification

### 1. Gradio Clusters Component

```python
# src/walltrack/ui/components/clusters.py
"""Cluster visualization component for Gradio dashboard."""
import gradio as gr
import plotly.graph_objects as go
import httpx
from typing import Optional
import pandas as pd

from walltrack.core.config import settings


API_BASE = f"http://localhost:{settings.api_port}"


async def fetch_clusters(min_size: int = 2, sort_by: str = "size") -> list[dict]:
    """Fetch clusters from API."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/clusters/",
            params={"limit": 100},
            timeout=10.0,
        )
        response.raise_for_status()
        clusters = response.json()

        # Filter by min size
        clusters = [c for c in clusters if c["size"] >= min_size]

        # Sort
        if sort_by == "size":
            clusters.sort(key=lambda x: x["size"], reverse=True)
        elif sort_by == "strength":
            clusters.sort(key=lambda x: x["strength"], reverse=True)

        return clusters


async def fetch_cluster_detail(cluster_id: str) -> dict:
    """Fetch cluster details including members."""
    async with httpx.AsyncClient() as client:
        # Get cluster info
        cluster_response = await client.get(
            f"{API_BASE}/clusters/{cluster_id}",
            timeout=10.0,
        )
        cluster_response.raise_for_status()
        cluster = cluster_response.json()

        # Get members
        members_response = await client.get(
            f"{API_BASE}/clusters/{cluster_id}/members",
            timeout=10.0,
        )
        members_response.raise_for_status()
        members = members_response.json()

        # Get leaders
        leaders_response = await client.get(
            f"{API_BASE}/leaders/cluster/{cluster_id}",
            timeout=10.0,
        )
        if leaders_response.status_code == 200:
            leaders = leaders_response.json()
        else:
            leaders = []

        return {
            "cluster": cluster,
            "members": members,
            "leaders": leaders,
        }


async def fetch_cluster_relationships(cluster_id: str) -> dict:
    """Fetch relationship data for cluster graph visualization."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/clusters/{cluster_id}/relationships",
            timeout=15.0,
        )
        if response.status_code == 200:
            return response.json()
        return {"nodes": [], "edges": []}


def create_cluster_list_dataframe(clusters: list[dict]) -> pd.DataFrame:
    """Create DataFrame for cluster list display."""
    data = []
    for c in clusters:
        data.append({
            "ID": c["id"][:8] + "...",
            "Full ID": c["id"],
            "Size": c["size"],
            "Strength": f"{c['strength']:.2f}",
            "Leader": c.get("leader_address", "None")[:8] + "..." if c.get("leader_address") else "None",
            "Status": c.get("status", "active"),
        })
    return pd.DataFrame(data)


def create_members_dataframe(members: list[dict], leaders: list[dict]) -> pd.DataFrame:
    """Create DataFrame for member list display."""
    leader_addresses = {l["wallet_address"] for l in leaders}

    data = []
    for m in members:
        is_leader = m["wallet_address"] in leader_addresses
        leader_info = next(
            (l for l in leaders if l["wallet_address"] == m["wallet_address"]),
            {}
        )

        data.append({
            "Address": m["wallet_address"][:12] + "...",
            "Full Address": m["wallet_address"],
            "Role": "🏆 Leader" if is_leader else "Member",
            "Leader Score": f"{leader_info.get('leader_score', 0):.2f}" if is_leader else "-",
            "Contribution": f"{m.get('contribution_score', 0):.2f}",
            "Joined": m.get("joined_at", "")[:10] if m.get("joined_at") else "-",
        })

    # Sort leaders first
    data.sort(key=lambda x: (x["Role"] != "🏆 Leader", -float(x["Leader Score"].replace("-", "0"))))
    return pd.DataFrame(data)


def create_cluster_graph(nodes: list[dict], edges: list[dict]) -> go.Figure:
    """
    Create a network graph visualization using Plotly.

    Args:
        nodes: List of node dicts with 'id', 'label', 'is_leader', etc.
        edges: List of edge dicts with 'source', 'target', 'type', 'weight'

    Returns:
        Plotly figure with network visualization
    """
    if not nodes:
        # Return empty figure
        fig = go.Figure()
        fig.add_annotation(
            text="No cluster data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            height=500,
            paper_bgcolor="#1a1a2e",
            plot_bgcolor="#1a1a2e",
        )
        return fig

    # Create simple circular layout
    import math
    n = len(nodes)
    node_positions = {}
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / n
        node_positions[node["id"]] = (math.cos(angle), math.sin(angle))

    # Create edge traces
    edge_traces = []
    edge_colors = {
        "FUNDED_BY": "#ff6b6b",
        "SYNCED_BUY": "#4ecdc4",
        "CO_OCCURS": "#ffe66d",
    }

    for edge in edges:
        if edge["source"] in node_positions and edge["target"] in node_positions:
            x0, y0 = node_positions[edge["source"]]
            x1, y1 = node_positions[edge["target"]]
            edge_type = edge.get("type", "CO_OCCURS")
            color = edge_colors.get(edge_type, "#666666")

            edge_traces.append(go.Scatter(
                x=[x0, x1, None],
                y=[y0, y1, None],
                mode="lines",
                line=dict(width=max(1, edge.get("weight", 1) * 0.5), color=color),
                hoverinfo="text",
                hovertext=f"{edge_type}: {edge.get('weight', 1)}",
                showlegend=False,
            ))

    # Create node trace
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_sizes = []

    for node in nodes:
        x, y = node_positions[node["id"]]
        node_x.append(x)
        node_y.append(y)
        node_text.append(f"{node.get('label', node['id'][:8])}")

        # Leader = larger & different color
        if node.get("is_leader"):
            node_colors.append("#ffd700")  # Gold for leaders
            node_sizes.append(25)
        else:
            node_colors.append("#6c5ce7")  # Purple for members
            node_sizes.append(15)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        textfont=dict(size=10, color="white"),
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color="white"),
        ),
        hoverinfo="text",
        hovertext=[f"Address: {n['id'][:16]}..." for n in nodes],
    )

    # Create figure
    fig = go.Figure(data=[*edge_traces, node_trace])

    # Add legend for edge types
    for edge_type, color in edge_colors.items():
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            line=dict(width=3, color=color),
            name=edge_type,
        ))

    fig.update_layout(
        title="Cluster Relationship Graph",
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(0,0,0,0.5)",
            font=dict(color="white"),
        ),
        height=500,
        hovermode="closest",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#1a1a2e",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        font=dict(color="white"),
    )

    return fig


def create_clusters_component() -> gr.Blocks:
    """Create the complete clusters Gradio component."""

    with gr.Blocks() as clusters_component:
        gr.Markdown("## 🔗 Cluster Analysis")

        with gr.Row():
            with gr.Column(scale=1):
                min_size_slider = gr.Slider(
                    minimum=2,
                    maximum=20,
                    value=2,
                    step=1,
                    label="Minimum Cluster Size",
                )
                sort_dropdown = gr.Dropdown(
                    choices=["size", "strength"],
                    value="size",
                    label="Sort By",
                )
                refresh_btn = gr.Button("🔄 Refresh", variant="primary")

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Clusters")
                cluster_table = gr.Dataframe(
                    headers=["ID", "Size", "Strength", "Leader", "Status"],
                    datatype=["str", "number", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                )

            with gr.Column(scale=2):
                gr.Markdown("### Cluster Details")

                with gr.Tabs():
                    with gr.Tab("Members"):
                        selected_cluster_id = gr.Textbox(
                            label="Selected Cluster",
                            placeholder="Click a cluster to view details",
                            interactive=False,
                        )
                        members_table = gr.Dataframe(
                            headers=["Address", "Role", "Leader Score", "Contribution", "Joined"],
                            datatype=["str", "str", "str", "str", "str"],
                            interactive=False,
                            wrap=True,
                        )

                    with gr.Tab("Graph View"):
                        cluster_graph = gr.Plot(label="Relationship Graph")

                    with gr.Tab("Metrics"):
                        with gr.Row():
                            metric_size = gr.Number(label="Members", interactive=False)
                            metric_strength = gr.Number(label="Strength", interactive=False)
                            metric_leaders = gr.Number(label="Leaders", interactive=False)

        # State to store full cluster IDs
        cluster_ids_state = gr.State([])

        async def load_clusters(min_size: int, sort_by: str):
            """Load cluster list."""
            try:
                clusters = await fetch_clusters(min_size, sort_by)
                df = create_cluster_list_dataframe(clusters)
                # Store full IDs for selection
                full_ids = [c["id"] for c in clusters]
                return df[["ID", "Size", "Strength", "Leader", "Status"]], full_ids
            except Exception as e:
                return pd.DataFrame(), []

        async def load_cluster_detail(evt: gr.SelectData, cluster_ids: list):
            """Load cluster details when row is selected."""
            if not cluster_ids or evt.index[0] >= len(cluster_ids):
                return "", pd.DataFrame(), go.Figure(), 0, 0, 0

            cluster_id = cluster_ids[evt.index[0]]

            try:
                detail = await fetch_cluster_detail(cluster_id)
                relationships = await fetch_cluster_relationships(cluster_id)

                members_df = create_members_dataframe(
                    detail["members"],
                    detail["leaders"]
                )

                # Create graph
                graph_fig = create_cluster_graph(
                    relationships.get("nodes", []),
                    relationships.get("edges", [])
                )

                cluster = detail["cluster"]

                return (
                    cluster_id[:16] + "...",
                    members_df[["Address", "Role", "Leader Score", "Contribution", "Joined"]],
                    graph_fig,
                    cluster.get("size", 0),
                    round(cluster.get("strength", 0), 2),
                    len(detail["leaders"]),
                )
            except Exception as e:
                return cluster_id[:16], pd.DataFrame(), go.Figure(), 0, 0, 0

        # Wire up events
        refresh_btn.click(
            fn=load_clusters,
            inputs=[min_size_slider, sort_dropdown],
            outputs=[cluster_table, cluster_ids_state],
        )

        min_size_slider.change(
            fn=load_clusters,
            inputs=[min_size_slider, sort_dropdown],
            outputs=[cluster_table, cluster_ids_state],
        )

        sort_dropdown.change(
            fn=load_clusters,
            inputs=[min_size_slider, sort_dropdown],
            outputs=[cluster_table, cluster_ids_state],
        )

        cluster_table.select(
            fn=load_cluster_detail,
            inputs=[cluster_ids_state],
            outputs=[
                selected_cluster_id,
                members_table,
                cluster_graph,
                metric_size,
                metric_strength,
                metric_leaders,
            ],
        )

        # Load on start
        clusters_component.load(
            fn=load_clusters,
            inputs=[min_size_slider, sort_dropdown],
            outputs=[cluster_table, cluster_ids_state],
        )

    return clusters_component


# Export for dashboard integration
__all__ = ["create_clusters_component"]
```

### 2. API Endpoint for Cluster Relationships

```python
# src/walltrack/api/routes/clusters.py (addition)
"""Additional cluster API endpoint for relationships."""

@router.get("/{cluster_id}/relationships")
async def get_cluster_relationships(
    cluster_id: str,
    service: ClusterService = Depends(get_cluster_service),
) -> dict:
    """
    Get nodes and edges for cluster graph visualization.
    """
    try:
        # Get members
        members = await service.get_cluster_members(cluster_id)

        # Get leaders
        leaders = await service.get_cluster_leaders(cluster_id)
        leader_addresses = {l.wallet_address for l in leaders}

        # Create nodes
        nodes = [
            {
                "id": m.wallet_address,
                "label": m.wallet_address[:8],
                "is_leader": m.wallet_address in leader_addresses,
            }
            for m in members
        ]

        # Get relationships between members
        edges = await service.get_cluster_edges(cluster_id)

        return {
            "nodes": nodes,
            "edges": [
                {
                    "source": e["source"],
                    "target": e["target"],
                    "type": e["type"],
                    "weight": e.get("weight", 1),
                }
                for e in edges
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. Cluster Edge Query in Service

```python
# src/walltrack/core/services/cluster_service.py (addition)
"""Additional method for cluster edges."""

async def get_cluster_edges(self, cluster_id: str) -> list[dict]:
    """Get all relationship edges between cluster members."""
    query = """
    MATCH (w1:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})<-[:MEMBER_OF]-(w2:Wallet)
    WHERE w1.address < w2.address
    OPTIONAL MATCH (w1)-[f:FUNDED_BY]-(w2)
    OPTIONAL MATCH (w1)-[s:SYNCED_BUY]-(w2)
    OPTIONAL MATCH (w1)-[o:CO_OCCURS]-(w2)
    WITH w1.address AS source, w2.address AS target,
         CASE WHEN f IS NOT NULL THEN {type: 'FUNDED_BY', weight: COALESCE(f.strength, 0.5)} ELSE null END AS funded,
         CASE WHEN s IS NOT NULL THEN {type: 'SYNCED_BUY', weight: s.sync_count} ELSE null END AS synced,
         CASE WHEN o IS NOT NULL THEN {type: 'CO_OCCURS', weight: o.count} ELSE null END AS cooccur
    UNWIND [funded, synced, cooccur] AS edge
    WHERE edge IS NOT NULL
    RETURN source, target, edge.type AS type, edge.weight AS weight
    """

    result = await self.neo4j.execute_read(query, {"cluster_id": cluster_id})

    return [
        {
            "source": r["source"],
            "target": r["target"],
            "type": r["type"],
            "weight": r["weight"],
        }
        for r in result
    ]

async def get_cluster_leaders(self, cluster_id: str) -> list:
    """Get leaders for a cluster (wrapper for leader identifier)."""
    from walltrack.core.services.leader_identifier import LeaderIdentifier
    # This would typically be injected
    result = await self.neo4j.execute_read(
        """
        MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster {id: $cluster_id})
        WHERE r.is_leader = true
        RETURN w.address AS wallet_address, r.leader_score AS leader_score
        ORDER BY r.leader_score DESC
        """,
        {"cluster_id": cluster_id}
    )

    return [
        type("Leader", (), {
            "wallet_address": r["wallet_address"],
            "leader_score": r["leader_score"],
        })()
        for r in result
    ]
```

### 4. Dashboard Integration

```python
# src/walltrack/ui/dashboard.py (update)
"""Update dashboard to include clusters tab."""
import gradio as gr

from walltrack.ui.components.wallets import create_wallets_component
from walltrack.ui.components.status import create_status_component
from walltrack.ui.components.clusters import create_clusters_component


def create_dashboard() -> gr.Blocks:
    """Create the main WallTrack dashboard."""

    with gr.Blocks(
        title="WallTrack Dashboard",
        theme=gr.themes.Soft(
            primary_hue="purple",
            secondary_hue="blue",
        ),
        css="""
        .gradio-container { max-width: 1400px; margin: auto; }
        .dark { background-color: #1a1a2e; }
        """
    ) as dashboard:
        gr.Markdown(
            """
            # 🎯 WallTrack Dashboard
            Autonomous Solana Memecoin Trading System
            """
        )

        with gr.Tabs():
            with gr.Tab("📊 Status"):
                create_status_component()

            with gr.Tab("👛 Wallets"):
                create_wallets_component()

            with gr.Tab("🔗 Clusters"):
                create_clusters_component()

            with gr.Tab("📡 Signals"):
                gr.Markdown("*Signal tracking coming in Epic 3*")

            with gr.Tab("💰 Positions"):
                gr.Markdown("*Position management coming in Epic 4*")

            with gr.Tab("📈 Performance"):
                gr.Markdown("*Performance analytics coming in Epic 6*")

            with gr.Tab("⚙️ Config"):
                gr.Markdown("*Configuration panel coming in Epic 5*")

    return dashboard
```

### 5. Unit Tests

```python
# tests/unit/ui/components/test_clusters.py
"""Tests for clusters UI component."""
import pytest
from unittest.mock import AsyncMock, patch
import pandas as pd

from walltrack.ui.components.clusters import (
    create_cluster_list_dataframe,
    create_members_dataframe,
    create_cluster_graph,
)


class TestCreateClusterListDataframe:
    """Tests for create_cluster_list_dataframe."""

    def test_creates_dataframe(self):
        """Should create DataFrame from cluster list."""
        clusters = [
            {
                "id": "abc123def456",
                "size": 5,
                "strength": 0.75,
                "leader_address": "leader123addr",
                "status": "active",
            }
        ]

        df = create_cluster_list_dataframe(clusters)

        assert len(df) == 1
        assert df.iloc[0]["Size"] == 5
        assert "0.75" in df.iloc[0]["Strength"]

    def test_handles_empty_list(self):
        """Should return empty DataFrame for empty list."""
        df = create_cluster_list_dataframe([])
        assert len(df) == 0


class TestCreateMembersDataframe:
    """Tests for create_members_dataframe."""

    def test_identifies_leaders(self):
        """Should mark leaders in the DataFrame."""
        members = [
            {"wallet_address": "wallet1", "contribution_score": 0.5},
            {"wallet_address": "wallet2", "contribution_score": 0.3},
        ]
        leaders = [
            {"wallet_address": "wallet1", "leader_score": 0.8},
        ]

        df = create_members_dataframe(members, leaders)

        assert "🏆 Leader" in df.iloc[0]["Role"]
        assert df.iloc[1]["Role"] == "Member"

    def test_sorts_leaders_first(self):
        """Should sort leaders to top of list."""
        members = [
            {"wallet_address": "member1", "contribution_score": 0.9},
            {"wallet_address": "leader1", "contribution_score": 0.5},
        ]
        leaders = [
            {"wallet_address": "leader1", "leader_score": 0.8},
        ]

        df = create_members_dataframe(members, leaders)

        assert "🏆 Leader" in df.iloc[0]["Role"]


class TestCreateClusterGraph:
    """Tests for create_cluster_graph."""

    def test_creates_graph_with_nodes(self):
        """Should create Plotly figure with nodes."""
        nodes = [
            {"id": "node1", "label": "N1", "is_leader": True},
            {"id": "node2", "label": "N2", "is_leader": False},
        ]
        edges = [
            {"source": "node1", "target": "node2", "type": "FUNDED_BY", "weight": 1},
        ]

        fig = create_cluster_graph(nodes, edges)

        assert fig is not None
        assert len(fig.data) > 0

    def test_handles_empty_nodes(self):
        """Should return empty figure for no nodes."""
        fig = create_cluster_graph([], [])

        assert fig is not None
        # Check for annotation indicating no data
        assert len(fig.layout.annotations) > 0

    def test_different_colors_for_leaders(self):
        """Leaders should have different visual treatment."""
        nodes = [
            {"id": "leader", "label": "L", "is_leader": True},
            {"id": "member", "label": "M", "is_leader": False},
        ]

        fig = create_cluster_graph(nodes, [])

        # Find the node trace (last scatter trace)
        node_trace = [t for t in fig.data if t.mode and "markers" in t.mode][-1]

        # Leaders should have gold color (#ffd700)
        assert "#ffd700" in node_trace.marker.color
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/ui/components/clusters.py`
- [ ] Implement cluster list view with sorting/filtering
- [ ] Implement cluster detail view
- [ ] Add member list with roles
- [ ] Implement graph visualization component
- [ ] Add wallet navigation links

## Definition of Done

- [ ] Cluster list displays with sorting/filtering
- [ ] Cluster details accessible on click
- [ ] Graph visualization renders relationships
- [ ] Navigation to wallet details works
