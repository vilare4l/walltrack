"""Daily simulation summary generator."""

from datetime import UTC, datetime

import httpx
import structlog

from walltrack.config.settings import get_settings
from walltrack.core.simulation.pnl_calculator import get_pnl_calculator
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


async def generate_daily_summary() -> dict:
    """Generate daily simulation summary.

    Returns:
        Dictionary containing:
        - date: Today's date
        - trades_count: Total trades today
        - wins: Winning trades
        - losses: Losing trades
        - win_rate: Win percentage
        - total_pnl: Total P&L
        - realized_pnl: Realized P&L
        - unrealized_pnl: Unrealized P&L
        - open_positions: Number of open positions
    """
    supabase = await get_supabase_client()
    pnl_calc = await get_pnl_calculator()

    # Get today's date
    today = datetime.now(UTC).date().isoformat()

    # Get today's trades
    trades = await supabase.select(
        table="simulation_events",
        filters={"event_type": "trade_executed"},
    )

    # Filter to today's trades (simple filter since we may not have date index)
    today_trades = [
        t for t in trades
        if t.get("executed_at", "").startswith(today)
        or t.get("created_at", "").startswith(today)
    ]

    # Calculate wins and losses
    wins = sum(1 for t in today_trades if t.get("pnl", 0) > 0)
    losses = sum(1 for t in today_trades if t.get("pnl", 0) < 0)
    trades_count = len(today_trades)

    # Calculate win rate
    win_rate = (wins / trades_count * 100) if trades_count > 0 else 0.0

    # Get portfolio P&L
    portfolio = await pnl_calc.calculate_portfolio_pnl(simulated=True)

    summary = {
        "date": today,
        "trades_count": trades_count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": float(portfolio.total_pnl),
        "realized_pnl": float(portfolio.total_realized_pnl),
        "unrealized_pnl": float(portfolio.total_unrealized_pnl),
        "open_positions": portfolio.position_count,
    }

    log.info(
        "daily_summary_generated",
        date=today,
        trades=trades_count,
        win_rate=win_rate,
        total_pnl=float(portfolio.total_pnl),
    )

    return summary


async def send_summary_alert(summary: dict) -> None:
    """Send daily summary alert via configured channels.

    Args:
        summary: Summary dictionary from generate_daily_summary()
    """
    settings = get_settings()

    # Format message
    message = _format_summary_message(summary)

    # Send to Discord if configured
    if settings.discord_webhook_url:
        await _send_discord_alert(settings.discord_webhook_url, message)

    # Send to Telegram if configured
    if settings.telegram_bot_token and settings.telegram_chat_id:
        await _send_telegram_alert(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            message,
        )

    log.info(
        "summary_alert_sent",
        date=summary.get("date"),
        discord=bool(settings.discord_webhook_url),
        telegram=bool(settings.telegram_bot_token),
    )


def _format_summary_message(summary: dict) -> str:
    """Format summary as readable message.

    Args:
        summary: Summary dictionary

    Returns:
        Formatted message string
    """
    pnl_emoji = "+" if summary.get("total_pnl", 0) >= 0 else ""

    return f"""
Daily Simulation Summary - {summary.get('date', 'N/A')}

Trades: {summary.get('trades_count', 0)}
Wins: {summary.get('wins', 0)} | Losses: {summary.get('losses', 0)}
Win Rate: {summary.get('win_rate', 0):.1f}%

P&L Summary:
  Total: {pnl_emoji}${summary.get('total_pnl', 0):.2f}
  Realized: ${summary.get('realized_pnl', 0):.2f}
  Unrealized: ${summary.get('unrealized_pnl', 0):.2f}

Open Positions: {summary.get('open_positions', 0)}
""".strip()


async def _send_discord_alert(webhook_url: str, message: str) -> None:
    """Send alert to Discord webhook.

    Args:
        webhook_url: Discord webhook URL
        message: Message to send
    """
    async with httpx.AsyncClient() as client:
        await client.post(
            webhook_url,
            json={"content": f"```\n{message}\n```"},
        )


async def _send_telegram_alert(
    bot_token: str,
    chat_id: str,
    message: str,
) -> None:
    """Send alert to Telegram.

    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        message: Message to send
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": f"```\n{message}\n```",
                "parse_mode": "Markdown",
            },
        )
