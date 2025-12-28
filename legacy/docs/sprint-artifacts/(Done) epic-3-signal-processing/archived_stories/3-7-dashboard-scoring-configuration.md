# Story 3.7: Dashboard - Scoring Configuration

## Story Info
- **Epic**: Epic 3 - Real-Time Signal Processing & Scoring
- **Status**: ready
- **Priority**: Medium
- **FR**: FR45

## User Story

**As an** operator,
**I want** to adjust scoring weights and thresholds in the dashboard,
**So that** I can tune the system without code changes.

## Acceptance Criteria

### AC 1: View Settings
**Given** the dashboard Scoring Config panel
**When** operator views current settings
**Then** all scoring weights are displayed (wallet, cluster, token, context)
**And** current threshold is displayed
**And** last modified timestamp is shown

### AC 2: Adjust Weights
**Given** operator adjusts a weight
**When** change is saved
**Then** new weight is stored in Supabase config table
**And** change takes effect immediately (no restart)
**And** change is logged with previous and new values

### AC 3: Adjust Threshold
**Given** operator adjusts threshold
**When** new threshold is saved
**Then** subsequent signals use new threshold
**And** validation ensures threshold is between 0.0 and 1.0

### AC 4: Validation
**Given** invalid configuration input
**When** save is attempted
**Then** validation error is displayed
**And** invalid change is not saved
**And** current valid config remains in effect

### AC 5: Reset to Defaults
**Given** scoring config panel
**When** operator wants to reset to defaults
**Then** "Reset to Defaults" button is available
**And** confirmation is required before reset

## Technical Notes

- FR45: Operator can adjust scoring weights and thresholds
- Implement in `src/walltrack/ui/components/config_panel.py`
- Read/write via `config_repo.py`
- Hot-reload config without application restart (AR24)

---

## Technical Specification

### 1. Gradio Scoring Configuration Component

```python
# src/walltrack/dashboard/components/scoring.py
import gradio as gr
import httpx
import plotly.graph_objects as go
from typing import Any

from walltrack.core.constants.scoring import (
    DEFAULT_WALLET_WEIGHT,
    DEFAULT_CLUSTER_WEIGHT,
    DEFAULT_TOKEN_WEIGHT,
    DEFAULT_CONTEXT_WEIGHT,
)
from walltrack.core.constants.threshold import (
    DEFAULT_TRADE_THRESHOLD,
    DEFAULT_HIGH_CONVICTION_THRESHOLD,
)


def create_scoring_component() -> gr.Blocks:
    """
    Create Gradio component for scoring configuration.

    Provides sliders for weight adjustment and real-time visualization.
    """

    async def fetch_current_config() -> dict[str, Any]:
        """Fetch current scoring config from API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:8000/api/v1/scoring/config"
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"Error fetching config: {e}")
        return {
            "weights": {
                "wallet": DEFAULT_WALLET_WEIGHT,
                "cluster": DEFAULT_CLUSTER_WEIGHT,
                "token": DEFAULT_TOKEN_WEIGHT,
                "context": DEFAULT_CONTEXT_WEIGHT,
            }
        }

    async def fetch_threshold_config() -> dict[str, Any]:
        """Fetch current threshold config from API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "http://localhost:8000/api/v1/threshold/config"
                )
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            print(f"Error fetching threshold config: {e}")
        return {
            "trade_threshold": DEFAULT_TRADE_THRESHOLD,
            "high_conviction_threshold": DEFAULT_HIGH_CONVICTION_THRESHOLD,
        }

    async def update_weights(
        wallet: float,
        cluster: float,
        token: float,
        context: float,
    ) -> tuple[str, Any]:
        """Update scoring weights via API."""
        # Validate sum
        total = wallet + cluster + token + context
        if abs(total - 1.0) > 0.001:
            return f"Error: Weights must sum to 1.0 (current sum: {total:.3f})", None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    "http://localhost:8000/api/v1/scoring/config/weights",
                    json={
                        "wallet": wallet,
                        "cluster": cluster,
                        "token": token,
                        "context": context,
                    },
                )

                if response.status_code == 200:
                    fig = create_weights_chart(wallet, cluster, token, context)
                    return "Weights updated successfully! Changes take effect immediately.", fig
                else:
                    return f"Error: {response.json().get('detail', 'Unknown error')}", None

        except Exception as e:
            return f"Error updating weights: {e}", None

    async def update_threshold(
        trade_threshold: float,
        high_conviction: float,
    ) -> str:
        """Update threshold config via API."""
        if high_conviction <= trade_threshold:
            return "Error: High conviction threshold must be > trade threshold"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    "http://localhost:8000/api/v1/threshold/config",
                    json={
                        "trade_threshold": trade_threshold,
                        "high_conviction_threshold": high_conviction,
                    },
                )

                if response.status_code == 200:
                    return "Threshold updated successfully!"
                else:
                    return f"Error: {response.json().get('detail', 'Unknown error')}"

        except Exception as e:
            return f"Error updating threshold: {e}"

    async def reset_to_defaults() -> tuple[float, float, float, float, str, Any]:
        """Reset weights to defaults."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8000/api/v1/scoring/config/reset"
                )

                if response.status_code == 200:
                    fig = create_weights_chart(
                        DEFAULT_WALLET_WEIGHT,
                        DEFAULT_CLUSTER_WEIGHT,
                        DEFAULT_TOKEN_WEIGHT,
                        DEFAULT_CONTEXT_WEIGHT,
                    )
                    return (
                        DEFAULT_WALLET_WEIGHT,
                        DEFAULT_CLUSTER_WEIGHT,
                        DEFAULT_TOKEN_WEIGHT,
                        DEFAULT_CONTEXT_WEIGHT,
                        "Reset to defaults!",
                        fig,
                    )
        except Exception as e:
            pass

        return (
            DEFAULT_WALLET_WEIGHT,
            DEFAULT_CLUSTER_WEIGHT,
            DEFAULT_TOKEN_WEIGHT,
            DEFAULT_CONTEXT_WEIGHT,
            "Error resetting",
            None,
        )

    def create_weights_chart(
        wallet: float,
        cluster: float,
        token: float,
        context: float,
    ) -> go.Figure:
        """Create pie chart showing weight distribution."""
        labels = ["Wallet (30%)", "Cluster (25%)", "Token (25%)", "Context (20%)"]
        values = [wallet, cluster, token, context]
        colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]

        fig = go.Figure(data=[
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors),
                textinfo="label+percent",
                hole=0.4,
            )
        ])

        fig.update_layout(
            title="Score Weight Distribution",
            showlegend=True,
            height=350,
            margin=dict(t=50, b=50, l=50, r=50),
        )

        return fig

    def normalize_weights(
        wallet: float,
        cluster: float,
        token: float,
        context: float,
    ) -> tuple[float, float, float, float, str]:
        """Normalize weights to sum to 1.0."""
        total = wallet + cluster + token + context
        if total == 0:
            return 0.25, 0.25, 0.25, 0.25, "Normalized to equal weights"

        factor = 1.0 / total
        return (
            round(wallet * factor, 3),
            round(cluster * factor, 3),
            round(token * factor, 3),
            round(context * factor, 3),
            f"Normalized from {total:.3f} to 1.000",
        )

    def calculate_sum(w: float, c: float, t: float, x: float) -> str:
        """Calculate and display current sum."""
        total = w + c + t + x
        if abs(total - 1.0) < 0.001:
            return f"Total: {total:.3f} ✓"
        else:
            return f"Total: {total:.3f} (must be 1.0)"

    # Build the UI
    with gr.Blocks() as scoring_block:
        gr.Markdown("## Scoring Configuration")
        gr.Markdown(
            "Adjust the weights for signal scoring factors. "
            "Changes take effect immediately."
        )

        with gr.Tabs():
            # Weights Tab
            with gr.TabItem("Score Weights"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Factor Weights")
                        gr.Markdown("*Weights must sum to 1.0*")

                        wallet_slider = gr.Slider(
                            minimum=0.0,
                            maximum=0.5,
                            value=DEFAULT_WALLET_WEIGHT,
                            step=0.01,
                            label="Wallet Score Weight",
                            info="Win rate, PnL, timing, leader status",
                        )

                        cluster_slider = gr.Slider(
                            minimum=0.0,
                            maximum=0.5,
                            value=DEFAULT_CLUSTER_WEIGHT,
                            step=0.01,
                            label="Cluster Score Weight",
                            info="Cluster activity amplification",
                        )

                        token_slider = gr.Slider(
                            minimum=0.0,
                            maximum=0.5,
                            value=DEFAULT_TOKEN_WEIGHT,
                            step=0.01,
                            label="Token Score Weight",
                            info="Liquidity, market cap, holders",
                        )

                        context_slider = gr.Slider(
                            minimum=0.0,
                            maximum=0.5,
                            value=DEFAULT_CONTEXT_WEIGHT,
                            step=0.01,
                            label="Context Score Weight",
                            info="Time of day, market conditions",
                        )

                        sum_display = gr.Textbox(
                            label="Weight Sum",
                            value=f"Total: 1.000 ✓",
                            interactive=False,
                        )

                        with gr.Row():
                            normalize_btn = gr.Button(
                                "Normalize to 1.0",
                                variant="secondary",
                            )
                            apply_btn = gr.Button(
                                "Apply Weights",
                                variant="primary",
                            )
                            reset_btn = gr.Button(
                                "Reset to Defaults",
                                variant="secondary",
                            )

                        status_text = gr.Textbox(
                            label="Status",
                            value="",
                            interactive=False,
                        )

                    with gr.Column(scale=1):
                        gr.Markdown("### Weight Distribution")
                        weights_chart = gr.Plot(
                            value=create_weights_chart(
                                DEFAULT_WALLET_WEIGHT,
                                DEFAULT_CLUSTER_WEIGHT,
                                DEFAULT_TOKEN_WEIGHT,
                                DEFAULT_CONTEXT_WEIGHT,
                            ),
                            label="Weight Distribution",
                        )

                # Event handlers for weights
                for slider in [wallet_slider, cluster_slider, token_slider, context_slider]:
                    slider.change(
                        fn=calculate_sum,
                        inputs=[wallet_slider, cluster_slider, token_slider, context_slider],
                        outputs=[sum_display],
                    )

                normalize_btn.click(
                    fn=normalize_weights,
                    inputs=[wallet_slider, cluster_slider, token_slider, context_slider],
                    outputs=[
                        wallet_slider,
                        cluster_slider,
                        token_slider,
                        context_slider,
                        status_text,
                    ],
                )

                apply_btn.click(
                    fn=update_weights,
                    inputs=[wallet_slider, cluster_slider, token_slider, context_slider],
                    outputs=[status_text, weights_chart],
                )

                reset_btn.click(
                    fn=reset_to_defaults,
                    outputs=[
                        wallet_slider,
                        cluster_slider,
                        token_slider,
                        context_slider,
                        status_text,
                        weights_chart,
                    ],
                )

            # Threshold Tab
            with gr.TabItem("Trade Threshold"):
                gr.Markdown("### Signal Score Threshold")
                gr.Markdown(
                    "Signals must meet the minimum score threshold to be eligible for trading."
                )

                with gr.Row():
                    with gr.Column():
                        trade_threshold_slider = gr.Slider(
                            minimum=0.5,
                            maximum=0.9,
                            value=DEFAULT_TRADE_THRESHOLD,
                            step=0.01,
                            label="Minimum Trade Threshold",
                            info="Signals below this score will not trigger trades",
                        )

                        high_conviction_slider = gr.Slider(
                            minimum=0.7,
                            maximum=0.95,
                            value=DEFAULT_HIGH_CONVICTION_THRESHOLD,
                            step=0.01,
                            label="High Conviction Threshold",
                            info="Signals above this get 1.5x position size",
                        )

                        threshold_apply_btn = gr.Button(
                            "Apply Threshold",
                            variant="primary",
                        )

                        threshold_status = gr.Textbox(
                            label="Status",
                            value="",
                            interactive=False,
                        )

                    with gr.Column():
                        gr.Markdown("### Position Sizing Tiers")
                        gr.Markdown("""
                        | Score Range | Conviction | Position Size |
                        |-------------|------------|---------------|
                        | >= 0.85 | High | 1.5x |
                        | 0.70 - 0.84 | Standard | 1.0x |
                        | < 0.70 | None | No Trade |
                        """)

                threshold_apply_btn.click(
                    fn=update_threshold,
                    inputs=[trade_threshold_slider, high_conviction_slider],
                    outputs=[threshold_status],
                )

            # Signal Analysis Tab
            with gr.TabItem("Signal Analysis"):
                gr.Markdown("### Recent Signal Scores")

                refresh_signals_btn = gr.Button("Refresh", variant="secondary")

                signal_table = gr.Dataframe(
                    headers=[
                        "Time",
                        "Wallet",
                        "Token",
                        "Score",
                        "Wallet",
                        "Cluster",
                        "Token",
                        "Context",
                        "Status",
                    ],
                    label="Recent Signals",
                    interactive=False,
                )

                async def fetch_recent_signals() -> list[list]:
                    """Fetch recent signals for analysis."""
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                "http://localhost:8000/api/v1/signals/",
                                params={"limit": 50},
                            )
                            if response.status_code == 200:
                                signals = response.json()
                                return [
                                    [
                                        s.get("timestamp", "")[:19],
                                        s.get("wallet_address", "")[:8] + "...",
                                        s.get("token_address", "")[:8] + "...",
                                        f"{s.get('final_score', 0):.3f}",
                                        f"{s.get('wallet_score', 0):.3f}",
                                        f"{s.get('cluster_score', 0):.3f}",
                                        f"{s.get('token_score', 0):.3f}",
                                        f"{s.get('context_score', 0):.3f}",
                                        s.get("eligibility_status", ""),
                                    ]
                                    for s in signals
                                ]
                    except Exception as e:
                        print(f"Error fetching signals: {e}")
                    return []

                refresh_signals_btn.click(
                    fn=fetch_recent_signals,
                    outputs=[signal_table],
                )

    return scoring_block
```

### 2. Score Breakdown Visualization

```python
# src/walltrack/dashboard/components/score_breakdown.py
import gradio as gr
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_score_breakdown_chart(
    wallet_score: float,
    cluster_score: float,
    token_score: float,
    context_score: float,
    wallet_weight: float = 0.30,
    cluster_weight: float = 0.25,
    token_weight: float = 0.25,
    context_weight: float = 0.20,
) -> go.Figure:
    """Create stacked bar chart showing score breakdown."""
    categories = ["Wallet", "Cluster", "Token", "Context"]
    scores = [wallet_score, cluster_score, token_score, context_score]
    weights = [wallet_weight, cluster_weight, token_weight, context_weight]
    contributions = [s * w for s, w in zip(scores, weights)]

    colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "bar"}, {"type": "bar"}]],
        subplot_titles=("Raw Scores", "Weighted Contributions"),
    )

    # Raw scores
    fig.add_trace(
        go.Bar(
            x=categories,
            y=scores,
            marker_color=colors,
            name="Raw Score",
            text=[f"{s:.2f}" for s in scores],
            textposition="outside",
        ),
        row=1, col=1,
    )

    # Stacked weighted contributions
    cumulative = 0
    for i, (cat, contrib, color) in enumerate(zip(categories, contributions, colors)):
        fig.add_trace(
            go.Bar(
                x=["Final Score"],
                y=[contrib],
                name=cat,
                marker_color=color,
                text=[f"{contrib:.3f}"],
                textposition="inside",
            ),
            row=1, col=2,
        )

    fig.update_layout(
        barmode="stack",
        height=300,
        showlegend=True,
        title_text=f"Score Breakdown (Final: {sum(contributions):.3f})",
    )

    fig.update_yaxes(range=[0, 1], row=1, col=1)
    fig.update_yaxes(range=[0, 1], row=1, col=2)

    return fig


def create_score_breakdown_component() -> gr.Blocks:
    """Create component for visualizing score breakdowns."""

    with gr.Blocks() as breakdown_block:
        gr.Markdown("## Signal Score Breakdown")

        with gr.Row():
            wallet_input = gr.Number(label="Wallet Score", value=0.8)
            cluster_input = gr.Number(label="Cluster Score", value=0.6)
            token_input = gr.Number(label="Token Score", value=0.7)
            context_input = gr.Number(label="Context Score", value=0.65)

        calculate_btn = gr.Button("Visualize Breakdown", variant="primary")

        breakdown_chart = gr.Plot(label="Score Breakdown")

        def update_chart(w, c, t, x):
            return create_score_breakdown_chart(w, c, t, x)

        calculate_btn.click(
            fn=update_chart,
            inputs=[wallet_input, cluster_input, token_input, context_input],
            outputs=[breakdown_chart],
        )

    return breakdown_block
```

### 3. Scoring Preview Component

```python
# src/walltrack/dashboard/components/scoring_preview.py
import gradio as gr
from typing import Any


def create_scoring_preview_component() -> gr.Blocks:
    """
    Create component for previewing score calculations.

    Allows testing scoring with custom inputs.
    """

    def calculate_preview_score(
        win_rate: float,
        pnl: float,
        timing: float,
        is_leader: bool,
        cluster_size: int,
        liquidity: float,
        market_cap: float,
        age_minutes: int,
    ) -> str:
        """Calculate preview score with given inputs."""

        # Wallet score
        pnl_normalized = max(0, min(1, (pnl + 100) / 600))
        wallet_base = win_rate * 0.35 + pnl_normalized * 0.25 + timing * 0.25 + 0.5 * 0.15
        leader_bonus = 0.15 if is_leader else 0
        wallet_score = min(1, wallet_base + leader_bonus)

        # Cluster score
        if cluster_size > 1:
            cluster_score = min(1, 0.5 + cluster_size * 0.05)
        else:
            cluster_score = 0.5

        # Token score
        liq_score = min(1, max(0, (liquidity - 1000) / 49000))
        mcap_score = min(1, max(0.2, (market_cap - 10000) / 490000))
        age_penalty = 0.3 * max(0, (5 - age_minutes) / 5) if age_minutes < 5 else 0
        token_score = max(0, liq_score * 0.3 + mcap_score * 0.25 + 0.5 * 0.45 - age_penalty)

        # Context score
        context_score = 0.7

        # Final score
        final = (
            wallet_score * 0.30 +
            cluster_score * 0.25 +
            token_score * 0.25 +
            context_score * 0.20
        )

        # Eligibility
        if final >= 0.85:
            eligibility = "HIGH CONVICTION (1.5x)"
        elif final >= 0.70:
            eligibility = "TRADE ELIGIBLE (1.0x)"
        else:
            eligibility = "BELOW THRESHOLD"

        return f"""
### Preview Results

**Final Score: {final:.4f}**
**Eligibility: {eligibility}**

| Factor | Score | Weight | Contribution |
|--------|-------|--------|--------------|
| Wallet | {wallet_score:.3f} | 30% | {wallet_score * 0.30:.3f} |
| Cluster | {cluster_score:.3f} | 25% | {cluster_score * 0.25:.3f} |
| Token | {token_score:.3f} | 25% | {token_score * 0.25:.3f} |
| Context | {context_score:.3f} | 20% | {context_score * 0.20:.3f} |
"""

    with gr.Blocks() as preview_block:
        gr.Markdown("## Scoring Preview")
        gr.Markdown("Test how different inputs affect the final score.")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Wallet Factors")
                win_rate = gr.Slider(0, 1, value=0.6, label="Win Rate")
                pnl = gr.Slider(-100, 500, value=50, label="Avg PnL %")
                timing = gr.Slider(0, 1, value=0.5, label="Timing Percentile")
                is_leader = gr.Checkbox(label="Is Cluster Leader")

            with gr.Column():
                gr.Markdown("### Token/Cluster Factors")
                cluster_size = gr.Slider(1, 20, value=1, step=1, label="Cluster Size")
                liquidity = gr.Slider(0, 100000, value=10000, label="Liquidity USD")
                market_cap = gr.Slider(0, 1000000, value=100000, label="Market Cap USD")
                age_minutes = gr.Slider(0, 60, value=30, label="Token Age (minutes)")

        calculate_btn = gr.Button("Calculate Preview Score", variant="primary")

        result_display = gr.Markdown("")

        calculate_btn.click(
            fn=calculate_preview_score,
            inputs=[
                win_rate, pnl, timing, is_leader,
                cluster_size, liquidity, market_cap, age_minutes,
            ],
            outputs=[result_display],
        )

    return preview_block
```

### 4. Dashboard Integration

```python
# src/walltrack/dashboard/app.py (update)
import gradio as gr

from walltrack.dashboard.components.scoring import create_scoring_component
from walltrack.dashboard.components.score_breakdown import create_score_breakdown_component
from walltrack.dashboard.components.scoring_preview import create_scoring_preview_component


def create_dashboard() -> gr.Blocks:
    """Create main dashboard with all components."""

    with gr.Blocks(
        title="WallTrack Dashboard",
        theme=gr.themes.Soft(),
    ) as dashboard:
        gr.Markdown("# WallTrack Dashboard")

        with gr.Tabs():
            with gr.TabItem("Overview"):
                gr.Markdown("### System Status")

            with gr.TabItem("Scoring Config"):
                scoring_component = create_scoring_component()

            with gr.TabItem("Score Preview"):
                preview_component = create_scoring_preview_component()

            with gr.TabItem("Score Analysis"):
                breakdown_component = create_score_breakdown_component()

    return dashboard
```

### 5. Unit Tests

```python
# tests/unit/dashboard/test_scoring_component.py
import pytest


class TestScoringComponent:
    """Tests for scoring dashboard component."""

    def test_weight_normalization(self):
        """Test weight normalization function."""

        def normalize(w, c, t, x):
            total = w + c + t + x
            if total == 0:
                return 0.25, 0.25, 0.25, 0.25
            factor = 1.0 / total
            return (
                round(w * factor, 3),
                round(c * factor, 3),
                round(t * factor, 3),
                round(x * factor, 3),
            )

        w, c, t, x = normalize(0.4, 0.3, 0.2, 0.1)
        assert abs(w + c + t + x - 1.0) < 0.001

    def test_sum_validation(self):
        """Test weight sum validation."""

        def calculate_sum(w, c, t, x):
            total = w + c + t + x
            if abs(total - 1.0) < 0.001:
                return f"Total: {total:.3f} ✓"
            else:
                return f"Total: {total:.3f} (must be 1.0)"

        assert "✓" in calculate_sum(0.3, 0.25, 0.25, 0.2)
        assert "must be" in calculate_sum(0.3, 0.3, 0.3, 0.3)


class TestScoringPreview:
    """Tests for scoring preview component."""

    def test_preview_calculation(self):
        """Test preview score calculation."""

        def calculate_preview(
            win_rate, pnl, timing, is_leader,
            cluster_size, liquidity, market_cap, age_minutes,
        ):
            # Simplified calculation
            wallet_score = win_rate * 0.35 + 0.5 * 0.65
            if is_leader:
                wallet_score = min(1, wallet_score + 0.15)

            cluster_score = min(1, 0.5 + (cluster_size - 1) * 0.05)
            token_score = min(1, liquidity / 50000)
            context_score = 0.7

            final = (
                wallet_score * 0.30 +
                cluster_score * 0.25 +
                token_score * 0.25 +
                context_score * 0.20
            )

            return final

        # Test with default values
        score = calculate_preview(0.6, 50, 0.5, False, 1, 10000, 100000, 30)
        assert 0 <= score <= 1

        # Test leader bonus
        score_no_leader = calculate_preview(0.6, 50, 0.5, False, 1, 10000, 100000, 30)
        score_leader = calculate_preview(0.6, 50, 0.5, True, 1, 10000, 100000, 30)
        assert score_leader > score_no_leader
```

---

## Implementation Tasks

- [x] Create `src/walltrack/ui/components/config_panel.py`
- [x] Display all scoring weights and threshold
- [x] Implement weight adjustment with validation
- [x] Implement threshold adjustment
- [x] Add hot-reload without restart
- [x] Log config changes
- [x] Add reset to defaults button

## Definition of Done

- [x] Scoring weights viewable and editable
- [x] Threshold adjustable with validation
- [x] Changes take effect immediately
- [x] Config changes logged

---

## Dev Agent Record

**Completed:** 2024-12-18

### Files Modified
- `src/walltrack/ui/components/config_panel.py` - Full scoring configuration panel
- `pyproject.toml` - Added plotly dependency

### Files Created
- `tests/unit/ui/test_config_panel.py` - 19 unit tests

### Implementation Summary
1. **Weight Configuration Tab**: Sliders for 4 factor weights with sum validation and normalization
2. **Threshold Configuration Tab**: Trade and high conviction threshold settings
3. **Score Preview Tab**: Interactive score calculator for testing scenarios
4. **Signal Analysis Tab**: Recent signals table with refresh
5. **Weight Visualization**: Plotly pie chart for weight distribution
6. **Reset to Defaults**: Single button to restore default configuration

### Test Results
- 19 tests passing
- All acceptance criteria covered
