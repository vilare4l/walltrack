# Story 12.8: UI - Price Chart Component

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 5
- **Depends on**: Story 12-4 (Price History)

## User Story

**As a** the operator,
**I want** un graphique de prix avec annotations,
**So that** je visualise clairement les points d'entrée/sortie.

## Acceptance Criteria

### AC 1: Display Price History
**Given** un historique de prix
**When** le graphique s'affiche
**Then** je vois:
- Courbe de prix (ligne)
- Point d'entrée (●) avec label
- Points de sortie réels (●) avec labels (TP1, TP2, SL, etc.)
- Ligne horizontale pour les niveaux TP/SL

### AC 2: Show Simulated Exits
**Given** des simulations sont ajoutées
**When** le graphique se met à jour
**Then** je vois:
- Points simulés (◆) en couleurs différentes par stratégie
- Légende avec les stratégies

### AC 3: Interactive Tooltips
**Given** je survole un point
**When** le tooltip s'affiche
**Then** je vois: Prix, Date/Heure, Type (Entry/TP1/SL...), P&L à ce point

### AC 4: Responsive Design
**Given** le graphique s'affiche
**When** la fenêtre est redimensionnée
**Then** le graphique s'adapte

### AC 5: Export Capability
**Given** un graphique est affiché
**When** je clique sur export
**Then** je peux télécharger l'image

## Technical Specifications

### Price Chart Component

**src/walltrack/ui/components/price_chart.py:**
```python
"""Price chart component with entry/exit annotations."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_price_chart(
    price_history: list[dict],
    entry_price: float,
    entry_time: str,
    actual_exits: list[dict] = None,
    simulated_exits: dict[str, list[dict]] = None,
    strategy_levels: dict[str, list[dict]] = None,
    title: str = "Position Price Chart",
) -> go.Figure:
    """
    Create interactive price chart with annotations.

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

    # Parse price history
    if price_history:
        times = []
        prices = []

        for point in price_history:
            ts = point.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            times.append(ts)
            prices.append(float(point.get("price", 0)))

        # Main price line
        fig.add_trace(go.Scatter(
            x=times,
            y=prices,
            mode='lines',
            name='Price',
            line=dict(color='#2196F3', width=2),
            hovertemplate='<b>Price:</b> $%{y:.8f}<br><b>Time:</b> %{x}<extra></extra>',
        ))

    # Entry point
    entry_dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00")) if isinstance(entry_time, str) else entry_time

    fig.add_trace(go.Scatter(
        x=[entry_dt],
        y=[entry_price],
        mode='markers+text',
        name='Entry',
        marker=dict(size=15, color='blue', symbol='circle'),
        text=['Entry'],
        textposition='top center',
        hovertemplate=f'<b>Entry</b><br>Price: ${entry_price:.8f}<br>Time: %{{x}}<extra></extra>',
    ))

    # Entry horizontal line
    if price_history:
        fig.add_hline(
            y=entry_price,
            line_dash="dash",
            line_color="blue",
            annotation_text="Entry",
            annotation_position="right",
        )

    # Actual exits
    if actual_exits:
        exit_times = []
        exit_prices = []
        exit_texts = []
        exit_hovers = []

        for ex in actual_exits:
            ts = ex.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            exit_times.append(ts)

            price = float(ex.get("price", 0))
            exit_prices.append(price)

            label = ex.get("label", ex.get("type", "Exit"))
            exit_texts.append(label)

            pnl = ((price - entry_price) / entry_price) * 100
            exit_hovers.append(
                f'<b>{label}</b><br>Price: ${price:.8f}<br>P&L: {pnl:+.2f}%<br>Time: %{{x}}<extra></extra>'
            )

        fig.add_trace(go.Scatter(
            x=exit_times,
            y=exit_prices,
            mode='markers+text',
            name='Actual Exit',
            marker=dict(size=15, color='green', symbol='circle'),
            text=exit_texts,
            textposition='bottom center',
            hovertemplate=exit_hovers[0] if len(exit_hovers) == 1 else None,
        ))

    # Simulated exits (different colors per strategy)
    colors = ['#FF9800', '#9C27B0', '#E91E63', '#00BCD4', '#8BC34A']
    color_idx = 0

    if simulated_exits:
        for strategy_name, exits in simulated_exits.items():
            if not exits:
                continue

            sim_times = []
            sim_prices = []
            sim_texts = []

            for ex in exits:
                ts = ex.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                sim_times.append(ts)

                price = float(ex.get("price", 0))
                sim_prices.append(price)

                label = ex.get("label", strategy_name)
                sim_texts.append(label)

            fig.add_trace(go.Scatter(
                x=sim_times,
                y=sim_prices,
                mode='markers+text',
                name=f'{strategy_name} (sim)',
                marker=dict(
                    size=12,
                    color=colors[color_idx % len(colors)],
                    symbol='diamond',
                ),
                text=sim_texts,
                textposition='top center',
            ))

            color_idx += 1

    # Strategy level lines
    if strategy_levels:
        for strategy_name, levels in strategy_levels.items():
            for level in levels:
                price = float(level.get("price", 0))
                level_type = level.get("type", "")
                label = level.get("label", level_type)

                color = {
                    "take_profit": "green",
                    "stop_loss": "red",
                    "trailing_stop": "orange",
                }.get(level_type, "gray")

                fig.add_hline(
                    y=price,
                    line_dash="dot",
                    line_color=color,
                    annotation_text=label,
                    annotation_position="right",
                    opacity=0.5,
                )

    # Layout
    fig.update_layout(
        title=dict(text=title, x=0.5),
        xaxis_title="Time",
        yaxis_title="Price",
        hovermode='x unified',
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)",
        ),
        template="plotly_white",
        height=500,
    )

    # Y-axis formatting
    fig.update_yaxes(tickformat=".8f")

    return fig


def create_comparison_chart(
    price_history: list[dict],
    entry_price: float,
    entry_time: str,
    comparison_results: list[dict],
) -> go.Figure:
    """
    Create chart specifically for strategy comparison.

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

    # Add comparison exit points
    colors = ['#FF5722', '#9C27B0', '#3F51B5', '#009688', '#FF9800']

    for idx, result in enumerate(comparison_results):
        strategy_name = result.get("strategy_name", f"Strategy {idx+1}")
        exit_time = result.get("exit_time")
        exit_price = result.get("exit_price", entry_price)
        pnl_pct = result.get("pnl_pct", 0)
        exit_types = result.get("exit_types", [])

        if exit_time:
            if isinstance(exit_time, str):
                exit_time = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))

            fig.add_trace(go.Scatter(
                x=[exit_time],
                y=[exit_price],
                mode='markers',
                name=f'{strategy_name} ({pnl_pct:+.1f}%)',
                marker=dict(
                    size=14,
                    color=colors[idx % len(colors)],
                    symbol='diamond',
                    line=dict(width=2, color='white'),
                ),
                hovertemplate=(
                    f'<b>{strategy_name}</b><br>'
                    f'Exit: ${exit_price:.8f}<br>'
                    f'P&L: {pnl_pct:+.2f}%<br>'
                    f'Types: {", ".join(exit_types)}<br>'
                    f'Time: %{{x}}<extra></extra>'
                ),
            ))

    return fig


def create_mini_chart(
    price_history: list[dict],
    entry_price: float,
    current_price: float = None,
    height: int = 150,
) -> go.Figure:
    """
    Create mini sparkline chart for position cards.

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
        times = [datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
                 if isinstance(p["timestamp"], str) else p["timestamp"]
                 for p in price_history]
        prices = [float(p["price"]) for p in price_history]

        # Determine color based on P&L
        final_price = current_price or prices[-1]
        color = '#4CAF50' if final_price >= entry_price else '#F44336'

        fig.add_trace(go.Scatter(
            x=times,
            y=prices,
            mode='lines',
            line=dict(color=color, width=1.5),
            fill='tozeroy',
            fillcolor=f'rgba({int(color[1:3], 16)},{int(color[3:5], 16)},{int(color[5:7], 16)},0.1)',
            hoverinfo='skip',
        ))

        # Entry line
        fig.add_hline(y=entry_price, line_dash="dot", line_color="gray", opacity=0.5)

    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        template="plotly_white",
    )

    return fig
```

## Implementation Tasks

- [ ] Create create_price_chart() function
- [ ] Add price line with hover info
- [ ] Add entry point marker
- [ ] Add actual exit markers
- [ ] Add simulated exit markers with colors
- [ ] Add strategy level lines
- [ ] Create create_comparison_chart()
- [ ] Create create_mini_chart() for cards
- [ ] Configure responsive layout
- [ ] Test with Gradio gr.Plot
- [ ] Write tests

## Definition of Done

- [ ] Price chart displays correctly
- [ ] Entry point visible
- [ ] Exit points marked correctly
- [ ] Simulated exits in different colors
- [ ] Tooltips show details
- [ ] Chart is responsive
- [ ] Mini chart works for cards

## File List

### New Files
- `src/walltrack/ui/components/price_chart.py` - Chart component

### Modified Files
- `src/walltrack/ui/components/whatif_modal.py` - Use chart component
