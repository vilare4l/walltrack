"""Backtest dashboard component for Gradio."""

from decimal import Decimal, InvalidOperation
from typing import Any

import plotly.express as px
import plotly.graph_objects as go

from walltrack.core.backtest.batch import BatchRun
from walltrack.core.backtest.comparison import ScenarioSummary
from walltrack.core.backtest.scenario import Scenario


def format_scenario_for_display(scenario: Scenario) -> dict[str, Any]:
    """Format a scenario for table display.

    Args:
        scenario: Scenario to format.

    Returns:
        Dictionary with display values.
    """
    return {
        "ID": str(scenario.id)[:8],
        "Name": scenario.name,
        "Category": scenario.category.value,
        "Threshold": float(scenario.score_threshold),
        "Position Size": float(scenario.base_position_sol),
        "Stop Loss": f"{float(scenario.exit_strategy.stop_loss_pct) * 100:.0f}%",
        "Preset": "Yes" if scenario.is_preset else "No",
    }


def format_batch_for_display(batch: BatchRun) -> dict[str, Any]:
    """Format a batch for table display.

    Args:
        batch: BatchRun to format.

    Returns:
        Dictionary with display values.
    """
    return {
        "ID": str(batch.id)[:8],
        "Name": batch.name,
        "Scenarios": len(batch.scenario_ids),
        "Status": batch.status.value,
        "Date Range": f"{batch.start_date.date()} - {batch.end_date.date()}",
        "Created": batch.created_at.strftime("%Y-%m-%d %H:%M"),
    }


def create_comparison_chart_data(results: list[dict]) -> dict[str, list]:
    """Create data structure for comparison chart.

    Args:
        results: List of result dictionaries with name, total_pnl, win_rate.

    Returns:
        Dictionary with names, pnls, and win_rates lists.
    """
    if not results:
        return {"names": [], "pnls": [], "win_rates": []}

    return {
        "names": [r["name"] for r in results],
        "pnls": [r["total_pnl"] for r in results],
        "win_rates": [r["win_rate"] * 100 for r in results],
    }


def create_comparison_chart(results: list[dict]) -> go.Figure:
    """Create comparison bar chart.

    Args:
        results: List of result dictionaries.

    Returns:
        Plotly figure with comparison chart.
    """
    if not results:
        return go.Figure()

    chart_data = create_comparison_chart_data(results)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Total P&L",
            x=chart_data["names"],
            y=chart_data["pnls"],
            marker_color="rgb(55, 83, 109)",
        )
    )

    fig.add_trace(
        go.Bar(
            name="Win Rate %",
            x=chart_data["names"],
            y=chart_data["win_rates"],
            marker_color="rgb(26, 118, 255)",
            yaxis="y2",
        )
    )

    fig.update_layout(
        title="Scenario Comparison",
        xaxis_title="Scenario",
        yaxis={"title": "P&L ($)"},
        yaxis2={"title": "Win Rate %", "overlaying": "y", "side": "right"},
        barmode="group",
        template="plotly_dark",
    )

    return fig


def create_equity_chart(equity_curves: dict[str, list]) -> go.Figure:
    """Create equity curve comparison chart.

    Args:
        equity_curves: Dictionary of scenario name to equity curve data.

    Returns:
        Plotly figure with equity curves.
    """
    fig = go.Figure()

    if not equity_curves:
        fig.update_layout(
            title="Equity Curves",
            template="plotly_dark",
        )
        return fig

    colors = px.colors.qualitative.Plotly

    for i, (name, curve) in enumerate(equity_curves.items()):
        times = [c["timestamp"] for c in curve]
        values = [c["equity"] for c in curve]

        fig.add_trace(
            go.Scatter(
                x=times,
                y=values,
                mode="lines",
                name=name,
                line={"color": colors[i % len(colors)]},
            )
        )

    fig.update_layout(
        title="Equity Curves",
        xaxis_title="Time",
        yaxis_title="Equity",
        template="plotly_dark",
    )

    return fig


def format_comparison_table_data(summaries: list[ScenarioSummary]) -> list[dict]:
    """Format comparison summaries for table display.

    Args:
        summaries: List of ScenarioSummary objects.

    Returns:
        List of dictionaries for table display.
    """
    return [
        {
            "Scenario": s.scenario_name,
            "Total P&L": float(s.metrics.total_pnl),
            "Win Rate": float(s.metrics.win_rate),
            "Trades": s.metrics.total_trades,
            "Max DD": float(s.metrics.max_drawdown_pct),
            "Profit Factor": float(s.metrics.profit_factor),
            "Rank": s.overall_rank,
        }
        for s in summaries
    ]


def parse_parameter_range(text: str) -> list[Decimal]:
    """Parse comma-separated parameter range.

    Args:
        text: Comma-separated string of values.

    Returns:
        List of Decimal values.
    """
    try:
        values = [Decimal(v.strip()) for v in text.split(",") if v.strip()]
        return values
    except InvalidOperation:
        return []


def validate_scenario_form(
    name: str,
    score_threshold: float,
    wallet_weight: float,
    cluster_weight: float,
    token_weight: float,
    context_weight: float,
) -> list[str]:
    """Validate scenario form inputs.

    Args:
        name: Scenario name.
        score_threshold: Score threshold value.
        wallet_weight: Wallet weight.
        cluster_weight: Cluster weight.
        token_weight: Token weight.
        context_weight: Context weight.

    Returns:
        List of error messages (empty if valid).
    """
    errors = []

    if not name or not name.strip():
        errors.append("Name is required")

    if not 0 < score_threshold < 1:
        errors.append("Score threshold must be between 0 and 1")

    total_weight = wallet_weight + cluster_weight + token_weight + context_weight
    if abs(total_weight - 1.0) > 0.001:
        errors.append(f"Scoring weights must sum to 1.0 (current: {total_weight:.3f})")

    return errors
