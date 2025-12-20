"""Scoring configuration panel component for dashboard."""

from typing import Any

import gradio as gr
import httpx
import plotly.graph_objects as go

from walltrack.config.settings import get_settings
from walltrack.constants.scoring import (
    DEFAULT_CLUSTER_WEIGHT,
    DEFAULT_CONTEXT_WEIGHT,
    DEFAULT_TOKEN_WEIGHT,
    DEFAULT_WALLET_WEIGHT,
)
from walltrack.constants.threshold import (
    DEFAULT_HIGH_CONVICTION_THRESHOLD,
    DEFAULT_TRADE_THRESHOLD,
)


def create_weights_chart(
    wallet: float,
    cluster: float,
    token: float,
    context: float,
) -> go.Figure:
    """Create pie chart showing weight distribution.

    Args:
        wallet: Wallet weight
        cluster: Cluster weight
        token: Token weight
        context: Context weight

    Returns:
        Plotly figure with pie chart
    """
    labels = [
        f"Wallet ({wallet*100:.0f}%)",
        f"Cluster ({cluster*100:.0f}%)",
        f"Token ({token*100:.0f}%)",
        f"Context ({context*100:.0f}%)",
    ]
    values = [wallet, cluster, token, context]
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#9C27B0"]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                marker={"colors": colors},
                textinfo="label+percent",
                hole=0.4,
            )
        ]
    )

    fig.update_layout(
        title="Score Weight Distribution",
        showlegend=True,
        height=350,
        margin={"t": 50, "b": 50, "l": 50, "r": 50},
    )

    return fig


def calculate_sum(w: float, c: float, t: float, x: float) -> str:
    """Calculate and display current sum.

    Args:
        w: Wallet weight
        c: Cluster weight
        t: Token weight
        x: Context weight

    Returns:
        Formatted sum string
    """
    total = w + c + t + x
    if abs(total - 1.0) < 0.001:
        return f"Total: {total:.3f} (valid)"
    else:
        return f"Total: {total:.3f} (must be 1.0)"


def normalize_weights(
    wallet: float,
    cluster: float,
    token: float,
    context: float,
) -> tuple[float, float, float, float, str, go.Figure]:
    """Normalize weights to sum to 1.0.

    Args:
        wallet: Current wallet weight
        cluster: Current cluster weight
        token: Current token weight
        context: Current context weight

    Returns:
        Tuple of normalized weights, status message, and chart
    """
    total = wallet + cluster + token + context
    if total == 0:
        w, c, t, x = 0.25, 0.25, 0.25, 0.25
        return w, c, t, x, "Normalized to equal weights", create_weights_chart(
            w, c, t, x
        )

    factor = 1.0 / total
    w = round(wallet * factor, 3)
    c = round(cluster * factor, 3)
    t = round(token * factor, 3)
    x = round(context * factor, 3)

    # Adjust for rounding
    diff = 1.0 - (w + c + t + x)
    w = round(w + diff, 3)

    return w, c, t, x, f"Normalized from {total:.3f} to 1.000", create_weights_chart(
        w, c, t, x
    )


async def fetch_current_config() -> dict[str, Any]:
    """Fetch current scoring config from API.

    Returns:
        Current configuration dict
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=f"http://localhost:{settings.port}",
            timeout=5.0,
        ) as client:
            response = await client.get("/api/v1/scoring/config")
            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result
    except Exception:
        pass
    return {
        "weights": {
            "wallet": DEFAULT_WALLET_WEIGHT,
            "cluster": DEFAULT_CLUSTER_WEIGHT,
            "token": DEFAULT_TOKEN_WEIGHT,
            "context": DEFAULT_CONTEXT_WEIGHT,
        }
    }


async def fetch_threshold_config() -> dict[str, Any]:
    """Fetch current threshold config from API.

    Returns:
        Current threshold configuration dict
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=f"http://localhost:{settings.port}",
            timeout=5.0,
        ) as client:
            response = await client.get("/api/v1/threshold/config")
            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                return result
    except Exception:
        pass
    return {
        "trade_threshold": DEFAULT_TRADE_THRESHOLD,
        "high_conviction_threshold": DEFAULT_HIGH_CONVICTION_THRESHOLD,
    }


async def update_weights(
    wallet: float,
    cluster: float,
    token: float,
    context: float,
) -> tuple[str, go.Figure | None]:
    """Update scoring weights via API.

    Args:
        wallet: New wallet weight
        cluster: New cluster weight
        token: New token weight
        context: New context weight

    Returns:
        Tuple of status message and updated chart
    """
    # Validate sum
    total = wallet + cluster + token + context
    if abs(total - 1.0) > 0.001:
        return f"Error: Weights must sum to 1.0 (current sum: {total:.3f})", None

    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=f"http://localhost:{settings.port}",
            timeout=5.0,
        ) as client:
            response = await client.put(
                "/api/v1/scoring/config/weights",
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
                detail = response.json().get("detail", "Unknown error")
                return f"Error: {detail}", None

    except Exception as e:
        return f"Error updating weights: {e}", None


async def update_threshold(
    trade_threshold: float,
    high_conviction: float,
) -> str:
    """Update threshold config via API.

    Args:
        trade_threshold: New trade threshold
        high_conviction: New high conviction threshold

    Returns:
        Status message
    """
    if high_conviction <= trade_threshold:
        return "Error: High conviction threshold must be > trade threshold"

    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=f"http://localhost:{settings.port}",
            timeout=5.0,
        ) as client:
            response = await client.put(
                "/api/v1/threshold/config",
                json={
                    "trade_threshold": trade_threshold,
                    "high_conviction_threshold": high_conviction,
                },
            )

            if response.status_code == 200:
                return "Threshold updated successfully! Changes take effect immediately."
            else:
                detail = response.json().get("detail", "Unknown error")
                return f"Error: {detail}"

    except Exception as e:
        return f"Error updating threshold: {e}"


async def reset_to_defaults() -> tuple[
    float, float, float, float, float, float, str, go.Figure
]:
    """Reset weights and thresholds to defaults.

    Returns:
        Tuple of default values and status
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=f"http://localhost:{settings.port}",
            timeout=5.0,
        ) as client:
            await client.post("/api/v1/scoring/config/reset")
    except Exception:
        pass

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
        DEFAULT_TRADE_THRESHOLD,
        DEFAULT_HIGH_CONVICTION_THRESHOLD,
        "Reset to default values!",
        fig,
    )


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
    """Calculate preview score with given inputs.

    Args:
        win_rate: Wallet win rate (0-1)
        pnl: Average PnL percentage
        timing: Timing percentile (0-1)
        is_leader: Whether wallet is cluster leader
        cluster_size: Number of wallets in cluster
        liquidity: Token liquidity in USD
        market_cap: Token market cap in USD
        age_minutes: Token age in minutes

    Returns:
        Formatted markdown with score breakdown
    """
    # Wallet score calculation
    pnl_normalized = max(0, min(1, (pnl + 100) / 600))
    wallet_base = win_rate * 0.35 + pnl_normalized * 0.25 + timing * 0.25 + 0.5 * 0.15
    leader_bonus = 0.15 if is_leader else 0
    wallet_score = min(1, wallet_base + leader_bonus)

    # Cluster score
    cluster_score = min(1, 0.5 + cluster_size * 0.05) if cluster_size > 1 else 0.5

    # Token score
    liq_score = min(1, max(0, (liquidity - 1000) / 49000))
    mcap_score = min(1, max(0.2, (market_cap - 10000) / 490000))
    age_penalty = 0.3 * max(0, (5 - age_minutes) / 5) if age_minutes < 5 else 0
    token_score = max(0, liq_score * 0.3 + mcap_score * 0.25 + 0.5 * 0.45 - age_penalty)

    # Context score (fixed for preview)
    context_score = 0.7

    # Final score
    final = (
        wallet_score * DEFAULT_WALLET_WEIGHT
        + cluster_score * DEFAULT_CLUSTER_WEIGHT
        + token_score * DEFAULT_TOKEN_WEIGHT
        + context_score * DEFAULT_CONTEXT_WEIGHT
    )

    # Eligibility
    if final >= DEFAULT_HIGH_CONVICTION_THRESHOLD:
        eligibility = "HIGH CONVICTION (1.5x position)"
    elif final >= DEFAULT_TRADE_THRESHOLD:
        eligibility = "TRADE ELIGIBLE (1.0x position)"
    else:
        eligibility = "BELOW THRESHOLD (no trade)"

    # Calculate contributions for cleaner output
    w_contrib = wallet_score * DEFAULT_WALLET_WEIGHT
    c_contrib = cluster_score * DEFAULT_CLUSTER_WEIGHT
    t_contrib = token_score * DEFAULT_TOKEN_WEIGHT
    x_contrib = context_score * DEFAULT_CONTEXT_WEIGHT

    return f"""
### Preview Results

**Final Score: {final:.4f}**
**Eligibility: {eligibility}**

| Factor | Score | Weight | Contribution |
|--------|-------|--------|--------------|
| Wallet | {wallet_score:.3f} | 30% | {w_contrib:.3f} |
| Cluster | {cluster_score:.3f} | 25% | {c_contrib:.3f} |
| Token | {token_score:.3f} | 25% | {t_contrib:.3f} |
| Context | {context_score:.3f} | 20% | {x_contrib:.3f} |
"""


async def fetch_recent_signals() -> list[list[str]]:
    """Fetch recent signals for analysis.

    Returns:
        List of signal rows for display
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            base_url=f"http://localhost:{settings.port}",
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
                        f"{s.get('cluster_score', 0):.3f}",
                        f"{s.get('token_score', 0):.3f}",
                        f"{s.get('context_score', 0):.3f}",
                        s.get("eligibility_status", ""),
                    ]
                    for s in signals
                ]
    except Exception:
        pass
    return []


def create_config_tab() -> None:  # noqa: PLR0915
    """Create the config tab UI with scoring configuration."""
    gr.Markdown("## Scoring Configuration")
    gr.Markdown(
        "Adjust the weights for signal scoring factors. Changes take effect immediately."
    )

    with gr.Tabs():
        # Score Weights Tab
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
                        value="Total: 1.000 (valid)",
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

            # Event handlers for sum display
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
                    weights_chart,
                ],
            )

            apply_btn.click(
                fn=update_weights,
                inputs=[wallet_slider, cluster_slider, token_slider, context_slider],
                outputs=[status_text, weights_chart],
            )

        # Trade Threshold Tab
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
                    gr.Markdown("### Reset")
                    reset_btn = gr.Button(
                        "Reset All to Defaults",
                        variant="secondary",
                    )

            threshold_apply_btn.click(
                fn=update_threshold,
                inputs=[trade_threshold_slider, high_conviction_slider],
                outputs=[threshold_status],
            )

            reset_btn.click(
                fn=reset_to_defaults,
                outputs=[
                    wallet_slider,
                    cluster_slider,
                    token_slider,
                    context_slider,
                    trade_threshold_slider,
                    high_conviction_slider,
                    status_text,
                    weights_chart,
                ],
            )

        # Score Preview Tab
        with gr.TabItem("Score Preview"):
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
                    cluster_size = gr.Slider(
                        1, 20, value=1, step=1, label="Cluster Size"
                    )
                    liquidity = gr.Slider(0, 100000, value=10000, label="Liquidity USD")
                    market_cap = gr.Slider(
                        0, 1000000, value=100000, label="Market Cap USD"
                    )
                    age_minutes = gr.Slider(
                        0, 60, value=30, label="Token Age (minutes)"
                    )

            calculate_btn = gr.Button("Calculate Preview Score", variant="primary")

            result_display = gr.Markdown("")

            calculate_btn.click(
                fn=calculate_preview_score,
                inputs=[
                    win_rate,
                    pnl,
                    timing,
                    is_leader,
                    cluster_size,
                    liquidity,
                    market_cap,
                    age_minutes,
                ],
                outputs=[result_display],
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

            refresh_signals_btn.click(
                fn=fetch_recent_signals,
                outputs=[signal_table],
            )
