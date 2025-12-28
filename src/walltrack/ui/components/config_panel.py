"""Simplified scoring configuration panel component.

Epic 14 Simplification:
- Single threshold (0.65) instead of dual thresholds
- ~8 parameters instead of 30+
- Removed pie chart for 4-factor weights
- Simple bar chart for wallet score composition
"""

from typing import Any

import gradio as gr
import httpx
import plotly.graph_objects as go

from walltrack.config.settings import get_settings
from walltrack.constants.scoring import (
    DEFAULT_LEADER_BONUS,
    DEFAULT_MAX_CLUSTER_BOOST,
    DEFAULT_MIN_CLUSTER_BOOST,
    DEFAULT_PNL_NORMALIZE_MAX,
    DEFAULT_PNL_NORMALIZE_MIN,
    DEFAULT_TRADE_THRESHOLD,
    DEFAULT_WALLET_PNL_WEIGHT,
    DEFAULT_WALLET_WIN_RATE_WEIGHT,
)


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    return settings.api_base_url or f"http://localhost:{settings.port}"


def create_scoring_chart(win_rate_weight: float, pnl_weight: float) -> go.Figure:
    """Create bar chart showing wallet score composition.

    Args:
        win_rate_weight: Weight for win rate (0-1)
        pnl_weight: Weight for PnL (0-1)

    Returns:
        Plotly figure with horizontal bar chart
    """
    fig = go.Figure(
        data=[
            go.Bar(
                x=[win_rate_weight, pnl_weight],
                y=["Win Rate", "PnL"],
                orientation="h",
                marker_color=["#4CAF50", "#2196F3"],
                text=[f"{win_rate_weight*100:.0f}%", f"{pnl_weight*100:.0f}%"],
                textposition="inside",
            )
        ]
    )

    fig.update_layout(
        title="Wallet Score Composition",
        xaxis_title="Weight",
        yaxis_title="Factor",
        height=200,
        margin={"t": 40, "b": 30, "l": 80, "r": 20},
        xaxis={"range": [0, 1]},
    )

    return fig


def validate_wallet_weights(win_rate: float, pnl: float) -> str:
    """Validate wallet weights sum to 1.0.

    Args:
        win_rate: Win rate weight
        pnl: PnL weight

    Returns:
        Validation message
    """
    total = win_rate + pnl
    if abs(total - 1.0) < 0.001:
        return f"Total: {total:.2f} (valid)"
    return f"Total: {total:.2f} (should be 1.0)"


async def fetch_current_config() -> dict[str, Any]:
    """Fetch current scoring config from API.

    Returns:
        Current configuration dict
    """
    try:
        async with httpx.AsyncClient(
            base_url=_get_api_base_url(),
            timeout=5.0,
        ) as client:
            response = await client.get("/api/v1/scoring/config")
            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result
    except Exception:
        pass

    # Return defaults
    return {
        "trade_threshold": DEFAULT_TRADE_THRESHOLD,
        "wallet_win_rate_weight": DEFAULT_WALLET_WIN_RATE_WEIGHT,
        "wallet_pnl_weight": DEFAULT_WALLET_PNL_WEIGHT,
        "leader_bonus": DEFAULT_LEADER_BONUS,
        "pnl_normalize_min": DEFAULT_PNL_NORMALIZE_MIN,
        "pnl_normalize_max": DEFAULT_PNL_NORMALIZE_MAX,
        "min_cluster_boost": DEFAULT_MIN_CLUSTER_BOOST,
        "max_cluster_boost": DEFAULT_MAX_CLUSTER_BOOST,
    }


async def update_config(
    trade_threshold: float,
    win_rate_weight: float,
    pnl_weight: float,
    leader_bonus: float,
    pnl_min: float,
    pnl_max: float,
    min_boost: float,
    max_boost: float,
) -> tuple[str, go.Figure | None]:
    """Update scoring configuration via API.

    Args:
        trade_threshold: Single trade threshold
        win_rate_weight: Weight for win rate in wallet score
        pnl_weight: Weight for PnL in wallet score
        leader_bonus: Multiplier for cluster leaders
        pnl_min: Min PnL for normalization
        pnl_max: Max PnL for normalization
        min_boost: Minimum cluster boost
        max_boost: Maximum cluster boost

    Returns:
        Tuple of status message and updated chart
    """
    # Validate wallet weights
    total = win_rate_weight + pnl_weight
    if abs(total - 1.0) > 0.01:
        return f"Error: Win Rate + PnL weights must equal 1.0 (current: {total:.2f})", None

    # Validate cluster boost range
    if min_boost > max_boost:
        return "Error: Min cluster boost must be <= max cluster boost", None

    try:
        async with httpx.AsyncClient(
            base_url=_get_api_base_url(),
            timeout=5.0,
        ) as client:
            response = await client.put(
                "/api/v1/scoring/config",
                json={
                    "trade_threshold": trade_threshold,
                    "wallet_win_rate_weight": win_rate_weight,
                    "wallet_pnl_weight": pnl_weight,
                    "leader_bonus": leader_bonus,
                    "pnl_normalize_min": pnl_min,
                    "pnl_normalize_max": pnl_max,
                    "min_cluster_boost": min_boost,
                    "max_cluster_boost": max_boost,
                },
            )

            if response.status_code == 200:
                fig = create_scoring_chart(win_rate_weight, pnl_weight)
                return "Configuration updated! Changes take effect immediately.", fig
            else:
                detail = response.json().get("detail", "Unknown error")
                return f"Error: {detail}", None

    except Exception as e:
        return f"Error updating config: {e}", None


async def reset_to_defaults() -> tuple[
    float, float, float, float, float, float, float, float, str, go.Figure
]:
    """Reset all configuration to defaults.

    Returns:
        Tuple of default values and status
    """
    try:
        async with httpx.AsyncClient(
            base_url=_get_api_base_url(),
            timeout=5.0,
        ) as client:
            await client.post("/api/v1/scoring/config/reset")
    except Exception:
        pass

    fig = create_scoring_chart(
        DEFAULT_WALLET_WIN_RATE_WEIGHT,
        DEFAULT_WALLET_PNL_WEIGHT,
    )

    return (
        DEFAULT_TRADE_THRESHOLD,
        DEFAULT_WALLET_WIN_RATE_WEIGHT,
        DEFAULT_WALLET_PNL_WEIGHT,
        DEFAULT_LEADER_BONUS,
        DEFAULT_PNL_NORMALIZE_MIN,
        DEFAULT_PNL_NORMALIZE_MAX,
        DEFAULT_MIN_CLUSTER_BOOST,
        DEFAULT_MAX_CLUSTER_BOOST,
        "Reset to default values!",
        fig,
    )


def calculate_preview_score(
    win_rate: float,
    pnl: float,
    is_leader: bool,
    cluster_boost: float,
    win_rate_weight: float,
    pnl_weight: float,
    leader_bonus: float,
    trade_threshold: float,
) -> str:
    """Calculate preview score with given inputs.

    Args:
        win_rate: Wallet win rate (0-1)
        pnl: Average PnL percentage
        is_leader: Whether wallet is cluster leader
        cluster_boost: Cluster boost multiplier
        win_rate_weight: Weight for win rate
        pnl_weight: Weight for PnL
        leader_bonus: Leader bonus multiplier
        trade_threshold: Trade eligibility threshold

    Returns:
        Formatted markdown with score breakdown
    """
    # Normalize PnL to 0-1 range
    pnl_norm = max(0.0, min(1.0, (pnl - DEFAULT_PNL_NORMALIZE_MIN) /
                           (DEFAULT_PNL_NORMALIZE_MAX - DEFAULT_PNL_NORMALIZE_MIN)))

    # Calculate wallet score
    wallet_base = win_rate * win_rate_weight + pnl_norm * pnl_weight
    if is_leader:
        wallet_base *= leader_bonus
    wallet_score = min(1.0, wallet_base)

    # Apply cluster boost
    final_score = min(1.0, wallet_score * cluster_boost)

    # Eligibility decision
    if final_score >= trade_threshold:
        eligibility = f"TRADE ELIGIBLE ({cluster_boost:.2f}x position)"
        eligibility_color = "green"
    else:
        eligibility = "BELOW THRESHOLD (no trade)"
        eligibility_color = "red"

    return f"""
### Preview Results

**Final Score: {final_score:.4f}**
<span style="color:{eligibility_color}">**{eligibility}**</span>

| Component | Value | Contribution |
|-----------|-------|--------------|
| Win Rate | {win_rate:.2f} | x{win_rate_weight:.2f} = {win_rate * win_rate_weight:.3f} |
| PnL (normalized) | {pnl_norm:.2f} | x{pnl_weight:.2f} = {pnl_norm * pnl_weight:.3f} |
| Leader Bonus | {'Yes' if is_leader else 'No'} | x{leader_bonus if is_leader else 1.0:.2f} |
| **Wallet Score** | | **{wallet_score:.4f}** |
| Cluster Boost | | x{cluster_boost:.2f} |
| **Final Score** | | **{final_score:.4f}** |

Threshold: {trade_threshold:.2f} | Position Size Multiplier: {cluster_boost:.2f}x
"""


async def fetch_recent_signals() -> list[list[str]]:
    """Fetch recent signals for analysis.

    Returns:
        List of signal rows for display
    """
    try:
        async with httpx.AsyncClient(
            base_url=_get_api_base_url(),
            timeout=5.0,
        ) as client:
            response = await client.get(
                "/api/v1/signals/",
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
                        f"{s.get('cluster_boost', 1.0):.2f}x",
                        s.get("eligibility_status", ""),
                    ]
                    for s in signals
                ]
    except Exception:
        pass
    return []


def create_config_tab() -> None:
    """Create the simplified config tab UI."""
    gr.Markdown("## Scoring Configuration")
    gr.Markdown(
        "Configure the simplified 2-component scoring model. "
        "Changes take effect immediately."
    )

    with gr.Tabs():
        # Main Configuration Tab
        with gr.TabItem("Configuration"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Trade Threshold")
                    threshold_slider = gr.Slider(
                        minimum=0.5,
                        maximum=0.9,
                        value=DEFAULT_TRADE_THRESHOLD,
                        step=0.01,
                        label="Trade Threshold",
                        info="Signals must score >= this to trigger trades",
                    )

                    gr.Markdown("### Wallet Score Weights")
                    gr.Markdown("*Must sum to 1.0*")

                    win_rate_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=DEFAULT_WALLET_WIN_RATE_WEIGHT,
                        step=0.05,
                        label="Win Rate Weight",
                        info="Weight for wallet win rate (0-1)",
                    )

                    pnl_slider = gr.Slider(
                        minimum=0.0,
                        maximum=1.0,
                        value=DEFAULT_WALLET_PNL_WEIGHT,
                        step=0.05,
                        label="PnL Weight",
                        info="Weight for normalized PnL (0-1)",
                    )

                    weight_sum_display = gr.Textbox(
                        label="Weight Sum",
                        value="Total: 1.00 (valid)",
                        interactive=False,
                    )

                    gr.Markdown("### Leader & Cluster Boost")

                    leader_slider = gr.Slider(
                        minimum=1.0,
                        maximum=2.0,
                        value=DEFAULT_LEADER_BONUS,
                        step=0.05,
                        label="Leader Bonus Multiplier",
                        info="Wallet score multiplier for cluster leaders",
                    )

                    min_boost_slider = gr.Slider(
                        minimum=1.0,
                        maximum=1.5,
                        value=DEFAULT_MIN_CLUSTER_BOOST,
                        step=0.05,
                        label="Min Cluster Boost",
                        info="Minimum cluster participation boost",
                    )

                    max_boost_slider = gr.Slider(
                        minimum=1.0,
                        maximum=2.5,
                        value=DEFAULT_MAX_CLUSTER_BOOST,
                        step=0.1,
                        label="Max Cluster Boost",
                        info="Maximum cluster participation boost",
                    )

                with gr.Column(scale=1):
                    gr.Markdown("### PnL Normalization Range")
                    pnl_min_slider = gr.Slider(
                        minimum=-500.0,
                        maximum=0.0,
                        value=DEFAULT_PNL_NORMALIZE_MIN,
                        step=10,
                        label="PnL Min (%)",
                        info="PnL values at or below this map to 0",
                    )

                    pnl_max_slider = gr.Slider(
                        minimum=100.0,
                        maximum=1000.0,
                        value=DEFAULT_PNL_NORMALIZE_MAX,
                        step=50,
                        label="PnL Max (%)",
                        info="PnL values at or above this map to 1",
                    )

                    gr.Markdown("### Wallet Score Composition")
                    scoring_chart = gr.Plot(
                        value=create_scoring_chart(
                            DEFAULT_WALLET_WIN_RATE_WEIGHT,
                            DEFAULT_WALLET_PNL_WEIGHT,
                        ),
                        label="Score Composition",
                    )

                    with gr.Row():
                        apply_btn = gr.Button("Apply Changes", variant="primary")
                        reset_btn = gr.Button("Reset to Defaults", variant="secondary")

                    status_text = gr.Textbox(
                        label="Status",
                        value="",
                        interactive=False,
                    )

            # Event handlers
            for slider in [win_rate_slider, pnl_slider]:
                slider.change(
                    fn=validate_wallet_weights,
                    inputs=[win_rate_slider, pnl_slider],
                    outputs=[weight_sum_display],
                )

            # Update chart when weights change
            for slider in [win_rate_slider, pnl_slider]:
                slider.change(
                    fn=create_scoring_chart,
                    inputs=[win_rate_slider, pnl_slider],
                    outputs=[scoring_chart],
                )

            apply_btn.click(
                fn=update_config,
                inputs=[
                    threshold_slider,
                    win_rate_slider,
                    pnl_slider,
                    leader_slider,
                    pnl_min_slider,
                    pnl_max_slider,
                    min_boost_slider,
                    max_boost_slider,
                ],
                outputs=[status_text, scoring_chart],
            )

            reset_btn.click(
                fn=reset_to_defaults,
                outputs=[
                    threshold_slider,
                    win_rate_slider,
                    pnl_slider,
                    leader_slider,
                    pnl_min_slider,
                    pnl_max_slider,
                    min_boost_slider,
                    max_boost_slider,
                    status_text,
                    scoring_chart,
                ],
            )

        # Score Preview Tab
        with gr.TabItem("Score Preview"):
            gr.Markdown("## Scoring Preview")
            gr.Markdown("Test how different inputs affect the final score.")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Wallet Inputs")
                    preview_win_rate = gr.Slider(
                        0, 1, value=0.6, label="Win Rate", step=0.05
                    )
                    preview_pnl = gr.Slider(
                        -100, 500, value=50, label="Avg PnL %", step=10
                    )
                    preview_is_leader = gr.Checkbox(label="Is Cluster Leader")

                with gr.Column():
                    gr.Markdown("### Cluster Context")
                    preview_cluster_boost = gr.Slider(
                        1.0, 1.8, value=1.0, label="Cluster Boost", step=0.1
                    )

            calculate_btn = gr.Button("Calculate Score", variant="primary")
            result_display = gr.Markdown("")

            calculate_btn.click(
                fn=calculate_preview_score,
                inputs=[
                    preview_win_rate,
                    preview_pnl,
                    preview_is_leader,
                    preview_cluster_boost,
                    win_rate_slider,
                    pnl_slider,
                    leader_slider,
                    threshold_slider,
                ],
                outputs=[result_display],
            )

        # Signal Analysis Tab
        with gr.TabItem("Signal Analysis"):
            gr.Markdown("### Recent Signal Scores")
            gr.Markdown("*Simplified view: Final Score = Wallet Score × Cluster Boost*")

            refresh_signals_btn = gr.Button("Refresh", variant="secondary")

            signal_table = gr.Dataframe(
                headers=[
                    "Time",
                    "Wallet",
                    "Token",
                    "Score",
                    "Wallet",
                    "Boost",
                    "Status",
                ],
                label="Recent Signals",
                interactive=False,
            )

            refresh_signals_btn.click(
                fn=fetch_recent_signals,
                outputs=[signal_table],
            )
