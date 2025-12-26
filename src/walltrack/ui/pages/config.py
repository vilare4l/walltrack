"""Config page - all settings in one place."""

import gradio as gr

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
from walltrack.ui.components.config_panel import (
    calculate_preview_score,
    calculate_sum,
    create_weights_chart,
    fetch_recent_signals,
    normalize_weights,
    update_threshold,
    update_weights,
)


def create_config_page() -> None:
    """Create the config page UI with all settings."""
    gr.Markdown("## Configuration")
    gr.Markdown(
        "Adjust scoring weights, thresholds, and other system settings. "
        "Changes take effect immediately."
    )

    with gr.Tabs(elem_id="config-tabs"):
        # ========== SCORE WEIGHTS TAB ==========
        with gr.TabItem("Score Weights", id="weights"):
            _create_weights_section()

        # ========== THRESHOLDS TAB ==========
        with gr.TabItem("Thresholds", id="thresholds"):
            _create_thresholds_section()

        # ========== SCORE PREVIEW TAB ==========
        with gr.TabItem("Score Preview", id="preview"):
            _create_preview_section()

        # ========== SIGNAL ANALYSIS TAB ==========
        with gr.TabItem("Signal Analysis", id="analysis"):
            _create_analysis_section()


def _create_weights_section() -> (
    tuple[gr.Slider, gr.Slider, gr.Slider, gr.Slider, gr.Textbox, gr.Plot]
):
    """Create score weights configuration section."""
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
                elem_id="config-wallet-weight",
            )

            cluster_slider = gr.Slider(
                minimum=0.0,
                maximum=0.5,
                value=DEFAULT_CLUSTER_WEIGHT,
                step=0.01,
                label="Cluster Score Weight",
                info="Cluster activity amplification",
                elem_id="config-cluster-weight",
            )

            token_slider = gr.Slider(
                minimum=0.0,
                maximum=0.5,
                value=DEFAULT_TOKEN_WEIGHT,
                step=0.01,
                label="Token Score Weight",
                info="Liquidity, market cap, holders",
                elem_id="config-token-weight",
            )

            context_slider = gr.Slider(
                minimum=0.0,
                maximum=0.5,
                value=DEFAULT_CONTEXT_WEIGHT,
                step=0.01,
                label="Context Score Weight",
                info="Time of day, market conditions",
                elem_id="config-context-weight",
            )

            sum_display = gr.Textbox(
                label="Weight Sum",
                value="Total: 1.000 (valid)",
                interactive=False,
                elem_id="config-weight-sum",
            )

            with gr.Row():
                normalize_btn = gr.Button(
                    "Normalize to 1.0",
                    variant="secondary",
                    elem_id="config-normalize-btn",
                )
                apply_btn = gr.Button(
                    "Apply Weights",
                    variant="primary",
                    elem_id="config-apply-weights-btn",
                )

            status_text = gr.Textbox(
                label="Status",
                value="",
                interactive=False,
                elem_id="config-weights-status",
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

    # Event handlers
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

    return wallet_slider, cluster_slider, token_slider, context_slider, status_text, weights_chart


def _create_thresholds_section() -> None:
    """Create threshold configuration section."""
    gr.Markdown("### Signal Score Thresholds")
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
                elem_id="config-trade-threshold",
            )

            high_conviction_slider = gr.Slider(
                minimum=0.7,
                maximum=0.95,
                value=DEFAULT_HIGH_CONVICTION_THRESHOLD,
                step=0.01,
                label="High Conviction Threshold",
                info="Signals above this get 1.5x position size",
                elem_id="config-high-conviction",
            )

            with gr.Row():
                threshold_apply_btn = gr.Button(
                    "Apply Thresholds",
                    variant="primary",
                    elem_id="config-apply-threshold-btn",
                )
                gr.Button(
                    "Reset All to Defaults",
                    variant="secondary",
                    elem_id="config-reset-btn",
                )

            threshold_status = gr.Textbox(
                label="Status",
                value="",
                interactive=False,
                elem_id="config-threshold-status",
            )

        with gr.Column():
            gr.Markdown("### Position Sizing Tiers")
            gr.Markdown("""
| Score Range | Conviction | Position Size |
|-------------|------------|---------------|
| >= 0.85 | High | 1.5x base |
| 0.70 - 0.84 | Standard | 1.0x base |
| < 0.70 | None | No Trade |
""")

    threshold_apply_btn.click(
        fn=update_threshold,
        inputs=[trade_threshold_slider, high_conviction_slider],
        outputs=[threshold_status],
    )

    # Note: Reset needs to output to weight sliders too
    # This is simplified - full implementation would need shared state


def _create_preview_section() -> None:
    """Create score preview/calculator section."""
    gr.Markdown("### Score Calculator")
    gr.Markdown("Test how different inputs affect the final score.")

    with gr.Row():
        with gr.Column():
            gr.Markdown("#### Wallet Factors")
            win_rate = gr.Slider(0, 1, value=0.6, label="Win Rate")
            pnl = gr.Slider(-100, 500, value=50, label="Avg PnL %")
            timing = gr.Slider(0, 1, value=0.5, label="Timing Percentile")
            is_leader = gr.Checkbox(label="Is Cluster Leader")

        with gr.Column():
            gr.Markdown("#### Token/Cluster Factors")
            cluster_size = gr.Slider(1, 20, value=1, step=1, label="Cluster Size")
            liquidity = gr.Slider(0, 100000, value=10000, label="Liquidity USD")
            market_cap = gr.Slider(0, 1000000, value=100000, label="Market Cap USD")
            age_minutes = gr.Slider(0, 60, value=30, label="Token Age (minutes)")

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


def _create_analysis_section() -> None:
    """Create signal analysis section."""
    gr.Markdown("### Recent Signal Scores")
    gr.Markdown("Analyze score distribution of recent signals.")

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
        elem_id="config-signals-table",
    )

    refresh_signals_btn.click(
        fn=fetch_recent_signals,
        outputs=[signal_table],
    )
