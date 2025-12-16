# Story 4.10: Dashboard - Positions and Trade History

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR41, FR43

## User Story

**As an** operator,
**I want** to view positions and trade history in the dashboard,
**So that** I can monitor trading activity.

## Acceptance Criteria

### AC 1: Active Positions View
**Given** dashboard Positions tab
**When** operator views active positions
**Then** all open positions are listed with:
- Token, entry price, current price, PnL%, time held
- Exit strategy name, next TP level, stop-loss level
**And** positions can be sorted by PnL or entry time

### AC 2: Position Detail
**Given** an open position
**When** operator clicks on it
**Then** detailed view shows all position data
**And** price chart (if available) is displayed
**And** exit strategy can be modified (Story 4.11)

### AC 3: Trade History
**Given** dashboard Trade History tab
**When** operator views history
**Then** closed trades are listed with:
- Token, entry/exit prices, PnL, duration, exit reason
**And** history can be filtered by date range, token, PnL
**And** pagination handles large datasets (NFR22)

### AC 4: Pending Signals
**Given** pending signals view
**When** signals are trade-eligible but not yet executed
**Then** pending signals are shown with score and status
**And** operator can see why signal is pending (if applicable)

## Technical Notes

- FR41: View active positions and pending signals
- FR43: View trade history with full details
- Implement in `src/walltrack/ui/components/positions.py`

## Implementation Tasks

- [ ] Create `src/walltrack/ui/components/positions.py`
- [ ] Implement active positions list with sorting
- [ ] Implement position detail view
- [ ] Create trade history view with filtering
- [ ] Add pagination for large datasets
- [ ] Show pending signals view

## Definition of Done

- [ ] Active positions displayed with key metrics
- [ ] Position details accessible
- [ ] Trade history filterable and paginated
- [ ] Pending signals visible

---

## Technical Specifications

### Gradio Dashboard Component

```python
# src/walltrack/ui/components/positions.py
"""Positions and trade history dashboard component."""

import gradio as gr
import pandas as pd
from datetime import datetime
from decimal import Decimal

from walltrack.core.execution.position_status import get_position_status_service
from walltrack.core.execution.models.position import PositionStatus
from walltrack.data.supabase.repositories.trade_repo import get_trade_repo
from walltrack.data.supabase.repositories.signal_repo import get_signal_repo


async def load_active_positions() -> pd.DataFrame:
    """Load active positions for display."""
    service = get_position_status_service()
    statuses = await service.get_all_open_positions()

    if not statuses:
        return pd.DataFrame(columns=[
            "Token", "Entry Price", "Current Price", "PnL %",
            "Multiplier", "Time Held", "Strategy", "Status"
        ])

    data = []
    for s in statuses:
        pnl_str = f"+{s.unrealized_pnl_percentage:.1f}%" if s.unrealized_pnl_percentage >= 0 else f"{s.unrealized_pnl_percentage:.1f}%"
        mult_str = f"x{s.multiplier:.2f}"

        hours = s.time_held_hours
        if hours < 1:
            time_str = f"{int(hours * 60)}m"
        elif hours < 24:
            time_str = f"{hours:.1f}h"
        else:
            time_str = f"{hours / 24:.1f}d"

        data.append({
            "id": s.position.id,
            "Token": s.position.token_symbol or s.position.token_mint[:8],
            "Entry Price": f"${float(s.position.entry_price):.6f}",
            "Current Price": f"${float(s.current_price):.6f}",
            "PnL %": pnl_str,
            "Multiplier": mult_str,
            "Time Held": time_str,
            "Strategy": s.position.exit_strategy_id.replace("preset-", ""),
            "Status": "🌙 Moonbag" if s.position.is_moonbag else s.position.status.value,
        })

    return pd.DataFrame(data)


async def load_position_detail(position_id: str) -> dict:
    """Load detailed position information."""
    if not position_id:
        return {}

    service = get_position_status_service()
    status = await service.get_position_status(position_id)

    if not status:
        return {"error": "Position not found"}

    p = status.position

    return {
        "token": p.token_symbol or p.token_mint,
        "token_mint": p.token_mint,
        "entry_price": float(p.entry_price),
        "current_price": float(status.current_price),
        "entry_amount": float(p.entry_amount),
        "remaining_amount": float(p.remaining_amount),
        "entry_time": p.entry_time.strftime("%Y-%m-%d %H:%M UTC"),
        "time_held_hours": status.time_held_hours,
        "unrealized_pnl": float(status.unrealized_pnl),
        "unrealized_pnl_pct": float(status.unrealized_pnl_percentage),
        "realized_pnl": float(status.realized_pnl),
        "realized_pnl_pct": float(status.realized_pnl_percentage),
        "total_pnl": float(status.total_pnl),
        "multiplier": float(status.multiplier),
        "stop_loss_price": float(status.stop_loss_price) if status.stop_loss_price else None,
        "next_tp_level": status.next_tp_level,
        "trailing_stop_active": status.trailing_stop_active,
        "trailing_stop_level": float(status.trailing_stop_level) if status.trailing_stop_level else None,
        "partial_exits": [
            {
                "time": pe.exit_time.strftime("%Y-%m-%d %H:%M"),
                "amount": float(pe.amount_sold),
                "price": float(pe.exit_price),
                "pnl": float(pe.realized_pnl),
                "reason": pe.exit_reason,
            }
            for pe in p.partial_exits
        ],
        "signal_id": p.signal_id,
        "signal_score": float(p.signal_score),
        "exit_strategy_id": p.exit_strategy_id,
    }


async def load_trade_history(
    date_from: str | None = None,
    date_to: str | None = None,
    token_filter: str | None = None,
    pnl_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[pd.DataFrame, int]:
    """Load trade history with filtering and pagination."""
    repo = await get_trade_repo()

    offset = (page - 1) * page_size
    positions = await repo.get_closed_positions(limit=page_size, offset=offset)

    if not positions:
        return pd.DataFrame(columns=[
            "Token", "Entry", "Exit", "PnL %", "Duration", "Exit Reason", "Date"
        ]), 0

    data = []
    for p in positions:
        # Apply filters
        if token_filter and token_filter.lower() not in (p.token_symbol or p.token_mint).lower():
            continue

        _, avg_pnl_pct = p.calculate_realized_pnl()

        if pnl_filter == "Profitable" and avg_pnl_pct < 0:
            continue
        if pnl_filter == "Loss" and avg_pnl_pct >= 0:
            continue

        duration_hours = (p.closed_at - p.entry_time).total_seconds() / 3600 if p.closed_at else 0

        if duration_hours < 1:
            duration_str = f"{int(duration_hours * 60)}m"
        elif duration_hours < 24:
            duration_str = f"{duration_hours:.1f}h"
        else:
            duration_str = f"{duration_hours / 24:.1f}d"

        pnl_str = f"+{avg_pnl_pct:.1f}%" if avg_pnl_pct >= 0 else f"{avg_pnl_pct:.1f}%"

        data.append({
            "id": p.id,
            "Token": p.token_symbol or p.token_mint[:8],
            "Entry": f"${float(p.entry_price):.6f}",
            "Exit": f"${float(p.final_exit_price):.6f}" if p.final_exit_price else "-",
            "PnL %": pnl_str,
            "Duration": duration_str,
            "Exit Reason": p.final_exit_reason or "-",
            "Date": p.closed_at.strftime("%Y-%m-%d") if p.closed_at else "-",
        })

    # Get total count for pagination
    all_closed = await repo.get_closed_positions(limit=1000)
    total_count = len(all_closed)

    return pd.DataFrame(data), total_count


async def load_pending_signals() -> pd.DataFrame:
    """Load pending signals that are trade-eligible."""
    repo = await get_signal_repo()
    signals = await repo.get_pending_signals()

    if not signals:
        return pd.DataFrame(columns=[
            "Token", "Score", "Source", "Time", "Status", "Pending Reason"
        ])

    data = []
    for s in signals:
        data.append({
            "id": s.id,
            "Token": s.token_symbol or s.token_mint[:8],
            "Score": f"{float(s.score):.2f}",
            "Source": s.source,
            "Time": s.created_at.strftime("%H:%M:%S"),
            "Status": s.status,
            "Pending Reason": s.pending_reason or "Awaiting execution",
        })

    return pd.DataFrame(data)


def format_position_detail(detail: dict) -> str:
    """Format position detail for display."""
    if not detail or "error" in detail:
        return "Select a position to view details"

    lines = [
        f"## {detail['token']}",
        f"**Token Mint:** `{detail['token_mint']}`",
        "",
        "### Entry",
        f"- **Price:** ${detail['entry_price']:.6f}",
        f"- **Amount:** {detail['entry_amount']:.2f}",
        f"- **Time:** {detail['entry_time']}",
        f"- **Signal Score:** {detail['signal_score']:.2f}",
        "",
        "### Current Status",
        f"- **Current Price:** ${detail['current_price']:.6f}",
        f"- **Remaining:** {detail['remaining_amount']:.2f}",
        f"- **Multiplier:** x{detail['multiplier']:.2f}",
        f"- **Time Held:** {detail['time_held_hours']:.1f} hours",
        "",
        "### PnL",
        f"- **Unrealized:** ${detail['unrealized_pnl']:.2f} ({detail['unrealized_pnl_pct']:+.1f}%)",
        f"- **Realized:** ${detail['realized_pnl']:.2f} ({detail['realized_pnl_pct']:+.1f}%)",
        f"- **Total:** ${detail['total_pnl']:.2f}",
        "",
        "### Exit Strategy",
        f"- **Strategy:** {detail['exit_strategy_id']}",
        f"- **Stop Loss:** ${detail['stop_loss_price']:.6f}" if detail.get('stop_loss_price') else "- **Stop Loss:** Not set",
        f"- **Next TP Level:** {detail['next_tp_level']}" if detail.get('next_tp_level') is not None else "- **Next TP Level:** All triggered",
    ]

    if detail.get('trailing_stop_active'):
        lines.append(f"- **Trailing Stop:** Active at ${detail['trailing_stop_level']:.6f}")

    if detail.get('partial_exits'):
        lines.extend(["", "### Partial Exits"])
        for i, pe in enumerate(detail['partial_exits']):
            lines.append(f"{i+1}. {pe['time']} - {pe['amount']:.2f} @ ${pe['price']:.6f} ({pe['reason']})")

    return "\n".join(lines)


def create_positions_panel() -> gr.Blocks:
    """Create the positions and trade history panel."""

    with gr.Blocks() as panel:
        gr.Markdown("# Positions & Trade History")

        with gr.Tabs():
            # Active Positions Tab
            with gr.Tab("Active Positions"):
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh", size="sm")

                positions_table = gr.Dataframe(
                    label="Open Positions",
                    headers=["Token", "Entry Price", "Current Price", "PnL %", "Multiplier", "Time Held", "Strategy", "Status"],
                    interactive=False,
                )

                gr.Markdown("---")
                gr.Markdown("### Position Detail")

                with gr.Row():
                    position_id_input = gr.Textbox(
                        label="Position ID",
                        placeholder="Select from table or enter ID",
                    )
                    load_detail_btn = gr.Button("Load Detail")

                position_detail = gr.Markdown("Select a position to view details")

                with gr.Row():
                    change_strategy_btn = gr.Button("Change Strategy", variant="secondary")
                    close_position_btn = gr.Button("Close Position", variant="stop")

                # Event handlers
                refresh_btn.click(
                    fn=load_active_positions,
                    outputs=positions_table,
                )

                load_detail_btn.click(
                    fn=lambda pid: format_position_detail(load_position_detail(pid)),
                    inputs=position_id_input,
                    outputs=position_detail,
                )

            # Trade History Tab
            with gr.Tab("Trade History"):
                with gr.Row():
                    date_from = gr.Textbox(label="From Date", placeholder="YYYY-MM-DD")
                    date_to = gr.Textbox(label="To Date", placeholder="YYYY-MM-DD")
                    token_filter = gr.Textbox(label="Token Filter")
                    pnl_filter = gr.Dropdown(
                        label="PnL Filter",
                        choices=["All", "Profitable", "Loss"],
                        value="All",
                    )

                with gr.Row():
                    search_btn = gr.Button("Search", variant="primary")
                    page_num = gr.Number(label="Page", value=1, minimum=1)
                    total_pages = gr.Textbox(label="Total", interactive=False)

                history_table = gr.Dataframe(
                    label="Closed Trades",
                    headers=["Token", "Entry", "Exit", "PnL %", "Duration", "Exit Reason", "Date"],
                    interactive=False,
                )

                def search_history(date_from, date_to, token, pnl, page):
                    df, total = load_trade_history(date_from, date_to, token, pnl, int(page))
                    pages = (total // 20) + 1
                    return df, f"of {pages}"

                search_btn.click(
                    fn=search_history,
                    inputs=[date_from, date_to, token_filter, pnl_filter, page_num],
                    outputs=[history_table, total_pages],
                )

            # Pending Signals Tab
            with gr.Tab("Pending Signals"):
                pending_refresh_btn = gr.Button("🔄 Refresh", size="sm")

                pending_table = gr.Dataframe(
                    label="Signals Awaiting Execution",
                    headers=["Token", "Score", "Source", "Time", "Status", "Pending Reason"],
                    interactive=False,
                )

                pending_refresh_btn.click(
                    fn=load_pending_signals,
                    outputs=pending_table,
                )

        # Auto-load on panel display
        panel.load(fn=load_active_positions, outputs=positions_table)

    return panel
```

### API Routes for Positions

```python
# src/walltrack/api/routes/position_routes.py
"""Position API routes."""

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from walltrack.core.execution.position_status import (
    get_position_status_service,
    PositionStatusService,
)
from walltrack.core.execution.models.position import (
    PositionStatusResponse,
    PositionSummary,
)
from walltrack.data.supabase.repositories.trade_repo import get_trade_repo

router = APIRouter(prefix="/positions", tags=["positions"])


class PositionListResponse(BaseModel):
    """Response for position list."""

    positions: list[PositionSummary]
    total: int


class TradeHistoryParams(BaseModel):
    """Query parameters for trade history."""

    date_from: Optional[str] = None
    date_to: Optional[str] = None
    token: Optional[str] = None
    pnl_type: Optional[str] = None  # "profitable" | "loss"
    page: int = 1
    page_size: int = 20


@router.get("/")
async def list_positions(
    wallet_id: Optional[str] = None,
    service: PositionStatusService = Depends(get_position_status_service),
) -> PositionListResponse:
    """List all open positions with summaries."""
    summaries = await service.get_position_summaries(wallet_id)

    return PositionListResponse(
        positions=summaries,
        total=len(summaries),
    )


@router.get("/{position_id}")
async def get_position(
    position_id: str,
    service: PositionStatusService = Depends(get_position_status_service),
) -> PositionStatusResponse:
    """Get detailed position status."""
    status = await service.get_position_status(position_id)

    if not status:
        raise HTTPException(status_code=404, detail="Position not found")

    return status


@router.get("/history/")
async def get_trade_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    wallet_id: Optional[str] = None,
) -> dict:
    """Get paginated trade history."""
    repo = await get_trade_repo()

    offset = (page - 1) * page_size
    positions = await repo.get_closed_positions(
        wallet_id=wallet_id,
        limit=page_size,
        offset=offset,
    )

    return {
        "trades": [
            {
                "id": p.id,
                "token": p.token_symbol or p.token_mint[:8],
                "entry_price": float(p.entry_price),
                "exit_price": float(p.final_exit_price) if p.final_exit_price else None,
                "pnl_percentage": float(p.calculate_realized_pnl()[1]),
                "exit_reason": p.final_exit_reason,
                "entry_time": p.entry_time.isoformat(),
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            }
            for p in positions
        ],
        "page": page,
        "page_size": page_size,
        "has_more": len(positions) == page_size,
    }


@router.post("/{position_id}/close")
async def close_position(
    position_id: str,
    reason: str = "manual",
) -> dict:
    """Manually close a position."""
    from walltrack.core.execution.position_manager import get_position_manager

    manager = await get_position_manager()

    try:
        position = await manager.close_position(position_id, reason)
        return {
            "status": "closed",
            "position_id": position.id,
            "final_pnl": float(position.calculate_realized_pnl()[0]),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

### Database Queries Optimization

```sql
-- Optimized views for dashboard queries

-- Active positions summary view
CREATE OR REPLACE VIEW active_positions_summary AS
SELECT
    p.id,
    p.token_mint,
    p.token_symbol,
    p.entry_price,
    p.entry_amount,
    p.remaining_amount,
    p.entry_time,
    p.status,
    p.exit_strategy_id,
    p.signal_score,
    EXTRACT(EPOCH FROM (NOW() - p.entry_time)) / 3600 as hours_held,
    CASE
        WHEN p.remaining_amount < p.entry_amount * 0.5 THEN true
        ELSE false
    END as is_moonbag
FROM positions p
WHERE p.status != 'closed'
ORDER BY p.entry_time DESC;

-- Trade history with calculated PnL
CREATE OR REPLACE VIEW trade_history_summary AS
SELECT
    p.id,
    p.token_mint,
    p.token_symbol,
    p.entry_price,
    p.final_exit_price,
    p.entry_time,
    p.closed_at,
    p.final_exit_reason,
    EXTRACT(EPOCH FROM (p.closed_at - p.entry_time)) / 3600 as duration_hours,
    CASE
        WHEN p.entry_price > 0 THEN
            ((p.final_exit_price - p.entry_price) / p.entry_price) * 100
        ELSE 0
    END as pnl_percentage
FROM positions p
WHERE p.status = 'closed'
ORDER BY p.closed_at DESC;

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_positions_status_entry ON positions(status, entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_positions_closed_date ON positions(closed_at DESC) WHERE status = 'closed';
```

### Unit Tests

```python
# tests/unit/ui/test_positions_dashboard.py
"""Tests for positions dashboard component."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from walltrack.ui.components.positions import (
    load_active_positions,
    load_position_detail,
    load_trade_history,
    format_position_detail,
)


@pytest.fixture
def mock_position_status():
    return MagicMock(
        position=MagicMock(
            id="pos-001",
            token_symbol="TEST",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            entry_amount=Decimal("1000"),
            remaining_amount=Decimal("500"),
            entry_time=datetime.utcnow() - timedelta(hours=5),
            exit_strategy_id="preset-balanced",
            signal_id="sig-001",
            signal_score=Decimal("0.85"),
            partial_exits=[],
            is_moonbag=False,
            status=MagicMock(value="partially_closed"),
        ),
        current_price=Decimal("1.50"),
        unrealized_pnl=Decimal("250"),
        unrealized_pnl_percentage=Decimal("50"),
        realized_pnl=Decimal("500"),
        realized_pnl_percentage=Decimal("100"),
        total_pnl=Decimal("750"),
        multiplier=Decimal("1.50"),
        time_held_hours=5.0,
        stop_loss_price=Decimal("0.70"),
        next_tp_level=1,
        trailing_stop_active=False,
        trailing_stop_level=None,
    )


class TestLoadActivePositions:
    """Test loading active positions."""

    @pytest.mark.asyncio
    async def test_empty_positions(self):
        """Test loading when no positions exist."""
        with patch("walltrack.ui.components.positions.get_position_status_service") as mock:
            mock.return_value.get_all_open_positions = AsyncMock(return_value=[])

            df = await load_active_positions()

            assert df.empty
            assert "Token" in df.columns

    @pytest.mark.asyncio
    async def test_positions_formatted(self, mock_position_status):
        """Test positions are correctly formatted."""
        with patch("walltrack.ui.components.positions.get_position_status_service") as mock:
            mock.return_value.get_all_open_positions = AsyncMock(
                return_value=[mock_position_status]
            )

            df = await load_active_positions()

            assert len(df) == 1
            assert df.iloc[0]["Token"] == "TEST"
            assert "+50.0%" in df.iloc[0]["PnL %"]
            assert "x1.50" in df.iloc[0]["Multiplier"]


class TestFormatPositionDetail:
    """Test position detail formatting."""

    def test_format_basic_detail(self):
        """Test basic detail formatting."""
        detail = {
            "token": "TEST",
            "token_mint": "TOKEN123",
            "entry_price": 1.0,
            "current_price": 1.5,
            "entry_amount": 1000,
            "remaining_amount": 500,
            "entry_time": "2024-01-01 12:00 UTC",
            "signal_score": 0.85,
            "time_held_hours": 5.0,
            "unrealized_pnl": 250,
            "unrealized_pnl_pct": 50,
            "realized_pnl": 500,
            "realized_pnl_pct": 100,
            "total_pnl": 750,
            "multiplier": 1.5,
            "stop_loss_price": 0.70,
            "next_tp_level": 1,
            "trailing_stop_active": False,
            "exit_strategy_id": "preset-balanced",
        }

        result = format_position_detail(detail)

        assert "## TEST" in result
        assert "Entry" in result
        assert "$1.000000" in result
        assert "x1.50" in result

    def test_format_with_partial_exits(self):
        """Test formatting with partial exits."""
        detail = {
            "token": "TEST",
            "token_mint": "TOKEN123",
            "entry_price": 1.0,
            "current_price": 2.0,
            "entry_amount": 1000,
            "remaining_amount": 300,
            "entry_time": "2024-01-01 12:00 UTC",
            "signal_score": 0.90,
            "time_held_hours": 10.0,
            "unrealized_pnl": 300,
            "unrealized_pnl_pct": 100,
            "realized_pnl": 700,
            "realized_pnl_pct": 100,
            "total_pnl": 1000,
            "multiplier": 2.0,
            "stop_loss_price": None,
            "next_tp_level": None,
            "trailing_stop_active": True,
            "trailing_stop_level": 1.80,
            "exit_strategy_id": "preset-moonbag",
            "partial_exits": [
                {
                    "time": "2024-01-01 14:00",
                    "amount": 400,
                    "price": 1.75,
                    "pnl": 300,
                    "reason": "take_profit",
                },
                {
                    "time": "2024-01-01 16:00",
                    "amount": 300,
                    "price": 2.33,
                    "pnl": 400,
                    "reason": "take_profit",
                },
            ],
        }

        result = format_position_detail(detail)

        assert "Trailing Stop" in result
        assert "$1.800000" in result
        assert "Partial Exits" in result
        assert "take_profit" in result

    def test_format_empty_detail(self):
        """Test formatting empty detail."""
        result = format_position_detail({})
        assert "Select a position" in result

        result = format_position_detail({"error": "not found"})
        assert "Select a position" in result


class TestLoadTradeHistory:
    """Test trade history loading."""

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """Test loading empty trade history."""
        with patch("walltrack.ui.components.positions.get_trade_repo") as mock:
            mock.return_value.get_closed_positions = AsyncMock(return_value=[])

            df, total = await load_trade_history()

            assert df.empty
            assert total == 0

    @pytest.mark.asyncio
    async def test_pagination(self):
        """Test trade history pagination."""
        mock_positions = [MagicMock() for _ in range(20)]

        with patch("walltrack.ui.components.positions.get_trade_repo") as mock:
            mock_repo = AsyncMock()
            mock_repo.get_closed_positions = AsyncMock(return_value=mock_positions)
            mock.return_value = mock_repo

            df, total = await load_trade_history(page=2, page_size=20)

            # Should call with offset
            call_args = mock_repo.get_closed_positions.call_args
            assert call_args.kwargs.get("offset") == 20
```
