"""Price chart component with entry/exit annotations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import plotly.graph_objects as go


def _parse_timestamp(ts: str | datetime) -> datetime:
    """Parse timestamp to datetime."""
    if isinstance(ts, str):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ts


def _add_price_line(fig: go.Figure, price_history: list[dict[str, Any]]) -> None:
    """Add main price line trace to figure."""
    times = []
    prices = []

    for point in price_history:
        times.append(_parse_timestamp(point.get("timestamp")))
        prices.append(float(point.get("price", 0)))

    fig.add_trace(
        go.Scatter(
            x=times,
            y=prices,
            mode="lines",
            name="Price",
            line={"color": "#2196F3", "width": 2},
            hovertemplate="<b>Price:</b> $%{y:.8f}<br><b>Time:</b> %{x}<extra></extra>",
        )
    )


def _add_entry_point(fig: go.Figure, entry_price: float, entry_time: str) -> None:
    """Add entry point marker and line to figure."""
    entry_dt = _parse_timestamp(entry_time)

    fig.add_trace(
        go.Scatter(
            x=[entry_dt],
            y=[entry_price],
            mode="markers+text",
            name="Entry",
            marker={"size": 15, "color": "blue", "symbol": "circle"},
            text=["Entry"],
            textposition="top center",
            hovertemplate=(
                f"<b>Entry</b><br>Price: ${entry_price:.8f}<br>Time: %{{x}}<extra></extra>"
            ),
        )
    )

    fig.add_hline(
        y=entry_price,
        line_dash="dash",
        line_color="blue",
        annotation_text="Entry",
        annotation_position="right",
    )


def _add_actual_exits(
    fig: go.Figure, actual_exits: list[dict[str, Any]], entry_price: float
) -> None:
    """Add actual exit markers to figure."""
    exit_times = []
    exit_prices = []
    exit_texts = []
    exit_hovers = []

    for ex in actual_exits:
        exit_times.append(_parse_timestamp(ex.get("timestamp")))

        price = float(ex.get("price", 0))
        exit_prices.append(price)

        label = ex.get("label", ex.get("type", "Exit"))
        exit_texts.append(label)

        pnl = ((price - entry_price) / entry_price) * 100 if entry_price else 0
        exit_hovers.append(
            f"<b>{label}</b><br>Price: ${price:.8f}<br>"
            f"P&L: {pnl:+.2f}%<br>Time: %{{x}}<extra></extra>"
        )

    fig.add_trace(
        go.Scatter(
            x=exit_times,
            y=exit_prices,
            mode="markers+text",
            name="Actual Exit",
            marker={"size": 15, "color": "green", "symbol": "circle"},
            text=exit_texts,
            textposition="bottom center",
            hovertemplate=exit_hovers[0] if len(exit_hovers) == 1 else None,
        )
    )


# Colors for simulated exits
SIMULATION_COLORS = ["#FF9800", "#9C27B0", "#E91E63", "#00BCD4", "#8BC34A"]


def _add_simulated_exits(
    fig: go.Figure, simulated_exits: dict[str, list[dict[str, Any]]]
) -> None:
    """Add simulated exit markers to figure."""
    color_idx = 0

    for strategy_name, exits in simulated_exits.items():
        if not exits:
            continue

        sim_times = []
        sim_prices = []
        sim_texts = []

        for ex in exits:
            sim_times.append(_parse_timestamp(ex.get("timestamp")))
            price = float(ex.get("price", 0))
            sim_prices.append(price)
            sim_texts.append(ex.get("label", strategy_name))

        fig.add_trace(
            go.Scatter(
                x=sim_times,
                y=sim_prices,
                mode="markers+text",
                name=f"{strategy_name} (sim)",
                marker={
                    "size": 12,
                    "color": SIMULATION_COLORS[color_idx % len(SIMULATION_COLORS)],
                    "symbol": "diamond",
                },
                text=sim_texts,
                textposition="top center",
            )
        )

        color_idx += 1


def _add_strategy_levels(
    fig: go.Figure, strategy_levels: dict[str, list[dict[str, Any]]]
) -> None:
    """Add strategy level horizontal lines to figure."""
    level_colors = {
        "take_profit": "green",
        "stop_loss": "red",
        "trailing_stop": "orange",
    }

    for _strategy_name, levels in strategy_levels.items():
        for level in levels:
            price = float(level.get("price", 0))
            level_type = level.get("type", "")
            label = level.get("label", level_type)
            color = level_colors.get(level_type, "gray")

            fig.add_hline(
                y=price,
                line_dash="dot",
                line_color=color,
                annotation_text=label,
                annotation_position="right",
                opacity=0.5,
            )


def _apply_chart_layout(fig: go.Figure, title: str) -> None:
    """Apply standard chart layout settings."""
    fig.update_layout(
        title={"text": title, "x": 0.5},
        xaxis_title="Time",
        yaxis_title="Price",
        hovermode="x unified",
        legend={
            "yanchor": "top",
            "y": 0.99,
            "xanchor": "left",
            "x": 0.01,
            "bgcolor": "rgba(255,255,255,0.8)",
        },
        template="plotly_white",
        height=500,
    )
    fig.update_yaxes(tickformat=".8f")


def create_price_chart(
    price_history: list[dict[str, Any]],
    entry_price: float,
    entry_time: str,
    actual_exits: list[dict[str, Any]] | None = None,
    simulated_exits: dict[str, list[dict[str, Any]]] | None = None,
    strategy_levels: dict[str, list[dict[str, Any]]] | None = None,
    title: str = "Position Price Chart",
) -> go.Figure:
    """Create interactive price chart with annotations.

    Args:
        price_history: List of {timestamp, price} dicts
        entry_price: Entry price
        entry_time: Entry timestamp string
        actual_exits: List of actual exit events {timestamp, price, type, label}
        simulated_exits: Dict of strategy_name -> list of exit events
        strategy_levels: Dict of strategy_name -> list of levels {price, type, label}
        title: Chart title

    Returns:
        Plotly Figure
    """
    fig = go.Figure()

    if price_history:
        _add_price_line(fig, price_history)

    _add_entry_point(fig, entry_price, entry_time)

    if actual_exits:
        _add_actual_exits(fig, actual_exits, entry_price)

    if simulated_exits:
        _add_simulated_exits(fig, simulated_exits)

    if strategy_levels:
        _add_strategy_levels(fig, strategy_levels)

    _apply_chart_layout(fig, title)

    return fig


# Colors for comparison chart
COMPARISON_COLORS = ["#FF5722", "#9C27B0", "#3F51B5", "#009688", "#FF9800"]


def create_comparison_chart(
    price_history: list[dict[str, Any]],
    entry_price: float,
    entry_time: str,
    comparison_results: list[dict[str, Any]],
) -> go.Figure:
    """Create chart specifically for strategy comparison.

    Shows price line with multiple strategy exit points.

    Args:
        price_history: Price history data
        entry_price: Entry price
        entry_time: Entry time
        comparison_results: List of {strategy_name, exit_time, exit_price, pnl_pct, exit_types}

    Returns:
        Plotly Figure
    """
    fig = create_price_chart(
        price_history=price_history,
        entry_price=entry_price,
        entry_time=entry_time,
        title="Strategy Comparison",
    )

    for idx, result in enumerate(comparison_results):
        strategy_name = result.get("strategy_name", f"Strategy {idx + 1}")
        exit_time = result.get("exit_time")
        exit_price = result.get("exit_price", entry_price)
        pnl_pct = result.get("pnl_pct", 0)
        exit_types = result.get("exit_types", [])

        if not exit_time:
            continue

        exit_dt = _parse_timestamp(exit_time)

        fig.add_trace(
            go.Scatter(
                x=[exit_dt],
                y=[exit_price],
                mode="markers",
                name=f"{strategy_name} ({pnl_pct:+.1f}%)",
                marker={
                    "size": 14,
                    "color": COMPARISON_COLORS[idx % len(COMPARISON_COLORS)],
                    "symbol": "diamond",
                    "line": {"width": 2, "color": "white"},
                },
                hovertemplate=(
                    f"<b>{strategy_name}</b><br>"
                    f"Exit: ${exit_price:.8f}<br>"
                    f"P&L: {pnl_pct:+.2f}%<br>"
                    f'Types: {", ".join(exit_types)}<br>'
                    f"Time: %{{x}}<extra></extra>"
                ),
            )
        )

    return fig


def create_mini_chart(
    price_history: list[dict[str, Any]],
    entry_price: float,
    current_price: float | None = None,
    height: int = 150,
) -> go.Figure:
    """Create mini sparkline chart for position cards.

    Args:
        price_history: Price history data
        entry_price: Entry price
        current_price: Current price (optional)
        height: Chart height in pixels

    Returns:
        Plotly Figure (compact)
    """
    fig = go.Figure()

    if price_history:
        times = [_parse_timestamp(p["timestamp"]) for p in price_history]
        prices = [float(p["price"]) for p in price_history]

        # Determine color based on P&L
        final_price = current_price or prices[-1]
        color = "#4CAF50" if final_price >= entry_price else "#F44336"

        # Parse color for rgba
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        fig.add_trace(
            go.Scatter(
                x=times,
                y=prices,
                mode="lines",
                line={"color": color, "width": 1.5},
                fill="tozeroy",
                fillcolor=f"rgba({r},{g},{b},0.1)",
                hoverinfo="skip",
            )
        )

        # Entry line
        fig.add_hline(y=entry_price, line_dash="dot", line_color="gray", opacity=0.5)

    fig.update_layout(
        showlegend=False,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        height=height,
        xaxis={"visible": False},
        yaxis={"visible": False},
        template="plotly_white",
    )

    return fig
