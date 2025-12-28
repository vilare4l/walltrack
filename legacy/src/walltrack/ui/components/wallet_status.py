"""Trading wallet status component for dashboard.

Displays:
- Connection status with indicator
- SOL balance with refresh
- Token balances (open positions)
- Safe mode controls
"""

from typing import Any

import gradio as gr
import httpx

from walltrack.config.settings import get_settings


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    return settings.api_base_url or f"http://localhost:{settings.port}"

async def fetch_wallet_status() -> dict[str, Any]:
    """Fetch wallet status from API."""
    async with httpx.AsyncClient(
        base_url=_get_api_base_url(),
        timeout=5.0,
    ) as client:
        try:
            response = await client.get("/api/v1/wallet/status")
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "error": str(e),
                "safe_mode": True,
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "error": str(e),
                "safe_mode": True,
            }


async def fetch_balance(refresh: bool = False) -> dict[str, Any]:
    """Fetch wallet balance from API."""
    async with httpx.AsyncClient(
        base_url=_get_api_base_url(),
        timeout=10.0,
    ) as client:
        try:
            response = await client.get(
                "/api/v1/wallet/balance",
                params={"refresh": refresh},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except Exception as e:
            return {
                "error": str(e),
                "sol_balance_ui": 0,
                "tokens": [],
            }


async def validate_wallet_signing() -> dict[str, Any]:
    """Validate wallet signing capability."""
    async with httpx.AsyncClient(
        base_url=_get_api_base_url(),
        timeout=10.0,
    ) as client:
        try:
            response = await client.post("/api/v1/wallet/validate")
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except Exception as e:
            return {"success": False, "error": str(e), "latency_ms": 0}


async def toggle_safe_mode(enabled: bool) -> dict[str, Any]:
    """Toggle safe mode."""
    async with httpx.AsyncClient(
        base_url=_get_api_base_url(),
        timeout=5.0,
    ) as client:
        try:
            response = await client.post(
                "/api/v1/wallet/safe-mode",
                json={"enabled": enabled},
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except Exception as e:
            return {"error": str(e)}


async def exit_safe_mode_api() -> dict[str, Any]:
    """Attempt to exit safe mode."""
    async with httpx.AsyncClient(
        base_url=_get_api_base_url(),
        timeout=10.0,
    ) as client:
        try:
            response = await client.post("/api/v1/wallet/safe-mode/exit")
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}


def format_status_indicator(status: str, safe_mode: bool) -> str:
    """Format status as colored indicator."""
    if safe_mode:
        return "[SAFE MODE] Trading Blocked"
    elif status == "connected":
        return "[CONNECTED]"
    elif status == "validating":
        return "[VALIDATING...]"
    elif status == "error":
        return "[ERROR]"
    else:
        return "[DISCONNECTED]"


def format_balance_display(balance: dict[str, Any]) -> str:
    """Format balance for display."""
    if "error" in balance:
        return f"**Error:** {balance['error']}"

    sol = balance.get("sol_balance_ui", 0)
    total = balance.get("total_value_sol", 0)
    token_count = balance.get("token_count", 0)
    sufficient = balance.get("has_sufficient_sol", False)
    last_updated = balance.get("last_updated", "Unknown")

    status_icon = "[OK]" if sufficient else "[LOW]"

    return f"""
### Balance Summary {status_icon}

| Metric | Value |
|--------|-------|
| SOL Balance | {sol:.4f} SOL |
| Total Value | {total:.4f} SOL |
| Open Positions | {token_count} tokens |
| Last Updated | {last_updated} |
"""


def format_tokens_table(tokens: list[dict[str, Any]]) -> list[list[str]]:
    """Format token balances as table data."""
    if not tokens:
        return [["No tokens", "-", "-"]]

    return [
        [
            t.get("mint_address", "")[:8] + "...",
            f"{t.get('ui_amount', 0):.4f}",
            f"{t.get('estimated_value_sol', 'N/A')} SOL"
            if t.get("estimated_value_sol")
            else "N/A",
        ]
        for t in tokens
    ]


def create_wallet_status_tab() -> None:
    """Create the trading wallet status tab UI."""
    gr.Markdown("## Trading Wallet")

    with gr.Row():
        with gr.Column(scale=2):
            # Status section
            status_display = gr.Markdown("Loading wallet status...")
            public_key_display = gr.Textbox(
                label="Wallet Address",
                interactive=False,
                max_lines=1,
            )

            with gr.Row():
                refresh_status_btn = gr.Button("Refresh Status", size="sm")
                validate_btn = gr.Button("Validate Signing", size="sm")

            # Validation result
            validation_result = gr.JSON(label="Validation Result", visible=False)

        with gr.Column(scale=2):
            # Balance section
            balance_display = gr.Markdown("Loading balance...")

            refresh_balance_btn = gr.Button("Refresh Balance", size="sm")

    # Token balances table
    gr.Markdown("### Token Balances (Open Positions)")
    tokens_table = gr.Dataframe(
        headers=["Token", "Amount", "Value"],
        datatype=["str", "str", "str"],
        interactive=False,
    )

    # Safe mode controls
    gr.Markdown("### Safe Mode Controls")
    with gr.Row():
        safe_mode_toggle = gr.Checkbox(
            label="Safe Mode (Block All Trades)",
            value=False,
        )
        exit_safe_mode_btn = gr.Button(
            "Exit Safe Mode",
            variant="primary",
            size="sm",
        )
    safe_mode_status = gr.Markdown("")

    # Event handlers
    async def update_status() -> tuple[str, str, bool]:
        """Update wallet status display."""
        try:
            status = await fetch_wallet_status()
            indicator = format_status_indicator(
                status.get("status", "disconnected"),
                status.get("safe_mode", False),
            )
            status_text = f"""
### Status: {indicator}

| Field | Value |
|-------|-------|
| Ready for Trading | {'Yes' if status.get('is_ready_for_trading') else 'No'} |
| Last Validated | {status.get('last_validated', 'Never')} |
| Error | {status.get('error_message', 'None')} |
"""
            return (
                status_text,
                status.get("public_key", "Not connected"),
                status.get("safe_mode", False),
            )
        except Exception as e:
            return f"### Status: [ERROR]\n\n{e}", "", False

    async def update_balance() -> tuple[str, list[list[str]]]:
        """Update balance display."""
        try:
            balance = await fetch_balance(refresh=True)
            display = format_balance_display(balance)
            tokens = format_tokens_table(balance.get("tokens", []))
            return display, tokens
        except Exception as e:
            return f"### Balance Error: {e}", []

    async def do_validate() -> dict[str, Any]:
        """Perform signing validation."""
        try:
            result = await validate_wallet_signing()
            return gr.update(value=result, visible=True)
        except Exception as e:
            return gr.update(value={"error": str(e)}, visible=True)

    async def do_toggle_safe_mode(enabled: bool) -> str:
        """Handle safe mode toggle."""
        try:
            result = await toggle_safe_mode(enabled)
            if "error" in result:
                return f"Error: {result['error']}"
            return f"Safe mode: {'ENABLED' if result.get('safe_mode') else 'DISABLED'}"
        except Exception as e:
            return f"Error: {e}"

    async def do_exit_safe_mode() -> tuple[str, bool]:
        """Handle exit safe mode request."""
        try:
            result = await exit_safe_mode_api()
            if result.get("success"):
                return "[OK] Successfully exited safe mode", False
            else:
                return f"[FAILED] {result.get('error', 'Unknown error')}", True
        except Exception as e:
            return f"[ERROR] {e}", True

    # Wire up events
    refresh_status_btn.click(
        fn=update_status,
        outputs=[status_display, public_key_display, safe_mode_toggle],
    )

    refresh_balance_btn.click(
        fn=update_balance,
        outputs=[balance_display, tokens_table],
    )

    validate_btn.click(
        fn=do_validate,
        outputs=[validation_result],
    )

    safe_mode_toggle.change(
        fn=do_toggle_safe_mode,
        inputs=[safe_mode_toggle],
        outputs=[safe_mode_status],
    )

    exit_safe_mode_btn.click(
        fn=do_exit_safe_mode,
        outputs=[safe_mode_status, safe_mode_toggle],
    )
