"""Simulation mode dashboard component."""

from decimal import Decimal
from typing import Any

import gradio as gr

from walltrack.core.simulation.pnl_calculator import (
    PortfolioPnL,
    get_pnl_calculator,
)
from walltrack.models.position import Position
from walltrack.services.position_service import get_position_service


def create_simulation_banner() -> gr.HTML:
    """Create simulation mode banner.

    Returns:
        Gradio HTML component with prominent simulation banner
    """
    return gr.HTML(
        value="""
        <div style="
            background: linear-gradient(90deg, #ff6b6b, #ffa500);
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(255, 107, 107, 0.3);
        ">
            🔬 SIMULATION MODE - Trades are NOT real
        </div>
        """,
        visible=True,
    )


async def get_simulation_positions_data() -> list[dict[str, Any]]:
    """Get simulated positions for display.

    Returns:
        List of position data dicts for the table
    """
    position_service = await get_position_service()
    pnl_calc = await get_pnl_calculator()

    positions = await position_service.get_active_positions(simulated=True)

    result = []
    for pos in positions:
        try:
            # Get current price for P&L calculation
            price_cache = await pnl_calc._get_current_price(pos.token_address)
            current_price = price_cache.price

            # Calculate P&L
            entry_value = Decimal(str(pos.entry_price)) * Decimal(
                str(pos.current_amount_tokens)
            )
            current_value = current_price * Decimal(str(pos.current_amount_tokens))
            unrealized_pnl = current_value - entry_value
            pnl_percent = (
                (unrealized_pnl / entry_value * 100) if entry_value > 0 else Decimal(0)
            )

            stale_indicator = " ⚠️" if price_cache.is_stale else ""

            result.append({
                "Token": pos.token_address[:8] + "...",
                "Entry Price": f"${pos.entry_price:.6f}",
                "Current Price": f"${current_price:.6f}{stale_indicator}",
                "Amount": f"{pos.current_amount_tokens:.2f}",
                "Unrealized P&L": f"${unrealized_pnl:.2f}",
                "P&L %": f"{pnl_percent:.1f}%",
                "Status": "SIMULATED",
            })
        except Exception:
            result.append({
                "Token": pos.token_address[:8] + "...",
                "Entry Price": f"${pos.entry_price:.6f}",
                "Current Price": "N/A",
                "Amount": f"{pos.current_amount_tokens:.2f}",
                "Unrealized P&L": "N/A",
                "P&L %": "N/A",
                "Status": "SIMULATED ⚠️",
            })

    return result


async def get_simulation_summary() -> dict[str, Any]:
    """Get simulation performance summary.

    Returns:
        Dict with portfolio P&L summary data
    """
    pnl_calc = await get_pnl_calculator()
    portfolio: PortfolioPnL = await pnl_calc.calculate_portfolio_pnl(simulated=True)

    return {
        "total_pnl": float(portfolio.total_pnl),
        "unrealized_pnl": float(portfolio.total_unrealized_pnl),
        "realized_pnl": float(portfolio.total_realized_pnl),
        "position_count": portfolio.position_count,
        "stale_prices": portfolio.positions_with_stale_prices,
    }


def format_positions_for_table(positions: list[Position]) -> list[list[Any]]:
    """Format positions as table rows.

    Args:
        positions: List of Position objects

    Returns:
        List of row data for Gradio table
    """
    rows = []
    for pos in positions:
        rows.append([
            pos.token_address[:8] + "...",
            f"${pos.entry_price:.6f}",
            f"{pos.current_amount_tokens:.2f}",
            pos.status.value,
            "SIMULATED",
        ])
    return rows


def create_simulation_panel() -> gr.Blocks:
    """Create simulation dashboard panel.

    Returns:
        Gradio Blocks component with simulation dashboard
    """
    with gr.Blocks() as panel:
        # Banner
        create_simulation_banner()

        # Summary metrics row
        with gr.Row():
            total_pnl = gr.Number(
                label="Total P&L (Simulated)",
                value=0,
                interactive=False,
            )
            unrealized_pnl = gr.Number(
                label="Unrealized P&L",
                value=0,
                interactive=False,
            )
            realized_pnl = gr.Number(
                label="Realized P&L",
                value=0,
                interactive=False,
            )
            position_count = gr.Number(
                label="Open Positions",
                value=0,
                interactive=False,
                precision=0,
            )

        # Stale price warning
        stale_warning = gr.HTML(
            value="",
            visible=False,
        )

        # Tabs
        with gr.Tabs():
            with gr.Tab("Positions"):
                positions_table = gr.Dataframe(
                    headers=[
                        "Token",
                        "Entry Price",
                        "Current Price",
                        "Amount",
                        "Unrealized P&L",
                        "P&L %",
                        "Status",
                    ],
                    label="Simulated Positions",
                    interactive=False,
                )

            with gr.Tab("Trade History"):
                gr.Dataframe(
                    headers=[
                        "Time",
                        "Token",
                        "Side",
                        "Amount",
                        "Price",
                        "P&L",
                        "Status",
                    ],
                    label="Simulated Trades",
                    interactive=False,
                )

        # Refresh button
        refresh_btn = gr.Button("🔄 Refresh Data", variant="primary")

        async def refresh_all() -> tuple:
            """Refresh all simulation data."""
            summary = await get_simulation_summary()
            positions = await get_simulation_positions_data()

            # Format stale warning
            stale_count = summary.get("stale_prices", 0)
            stale_html = ""
            stale_visible = False
            if stale_count > 0:
                stale_html = f"""
                <div style="
                    background: #fff3cd;
                    color: #856404;
                    padding: 10px;
                    border-radius: 4px;
                    margin: 10px 0;
                ">
                    ⚠️ {stale_count} position(s) have stale prices
                </div>
                """
                stale_visible = True

            return (
                summary["total_pnl"],
                summary["unrealized_pnl"],
                summary["realized_pnl"],
                summary["position_count"],
                positions,
                gr.update(value=stale_html, visible=stale_visible),
            )

        refresh_btn.click(
            fn=refresh_all,
            outputs=[
                total_pnl,
                unrealized_pnl,
                realized_pnl,
                position_count,
                positions_table,
                stale_warning,
            ],
        )

    return panel
