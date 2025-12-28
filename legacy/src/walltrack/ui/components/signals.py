"""Signals component for dashboard."""

from datetime import datetime, timedelta
from typing import Any

import gradio as gr
import pandas as pd


async def fetch_recent_signals() -> list[dict[str, Any]]:
    """Fetch recent signals from database."""
    from walltrack.data.supabase.client import get_supabase_client

    try:
        supabase = await get_supabase_client()

        # Get signals from last 24 hours
        since = (datetime.utcnow() - timedelta(hours=24)).isoformat()

        response = await (
            supabase.table("historical_signals")
            .select("*")
            .gte("timestamp", since)
            .order("timestamp", desc=True)
            .limit(100)
            .execute()
        )

        return response.data or []
    except Exception as e:
        return [{"error": str(e)}]


def format_signals_table(signals: list[dict[str, Any]]) -> pd.DataFrame:
    """Format signals as DataFrame for display."""
    if not signals or "error" in signals[0]:
        return pd.DataFrame({"Message": ["No signals found or error loading"]})

    rows = []
    for sig in signals:
        rows.append({
            "Time": sig.get("timestamp", "")[:19],
            "Token": sig.get("token_address", "")[:8] + "...",
            "Wallet": sig.get("wallet_address", "")[:8] + "...",
            "Score": f"{sig.get('score', 0):.2f}",
            "Amount": f"{sig.get('amount_sol', 0):.4f} SOL",
            "Type": sig.get("signal_type", "buy"),
        })

    return pd.DataFrame(rows)


def create_signals_tab() -> None:
    """Create the signals tab UI."""
    gr.Markdown("## Signal Feed")
    gr.Markdown("Real-time trading signals from wallet analysis")

    with gr.Row():
        refresh_btn = gr.Button("🔄 Refresh Signals", variant="primary")
        auto_refresh = gr.Checkbox(label="Auto-refresh (30s)", value=False)

    with gr.Row():
        with gr.Column(scale=3):
            signals_table = gr.Dataframe(
                headers=["Time", "Token", "Wallet", "Score", "Amount", "Type"],
                label="Recent Signals (24h)",
                interactive=False,
            )

        with gr.Column(scale=1):
            gr.Markdown("### Signal Stats")
            total_signals = gr.Markdown("**Total:** -")
            avg_score = gr.Markdown("**Avg Score:** -")
            unique_tokens = gr.Markdown("**Tokens:** -")
            unique_wallets = gr.Markdown("**Wallets:** -")

    async def load_signals():
        """Load and format signals."""
        signals = await fetch_recent_signals()
        df = format_signals_table(signals)

        if "error" not in signals[0] if signals else True:
            total = len(signals)
            scores = [s.get("score", 0) for s in signals if s.get("score")]
            avg = sum(scores) / len(scores) if scores else 0
            tokens = len(set(s.get("token_address", "") for s in signals))
            wallets = len(set(s.get("wallet_address", "") for s in signals))

            return (
                df,
                f"**Total:** {total}",
                f"**Avg Score:** {avg:.2f}",
                f"**Tokens:** {tokens}",
                f"**Wallets:** {wallets}",
            )

        return df, "**Total:** -", "**Avg Score:** -", "**Tokens:** -", "**Wallets:** -"

    refresh_btn.click(
        fn=load_signals,
        outputs=[signals_table, total_signals, avg_score, unique_tokens, unique_wallets],
    )
