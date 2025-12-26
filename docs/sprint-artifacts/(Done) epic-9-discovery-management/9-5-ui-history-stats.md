# Story 9.5: UI History and Statistics

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: Medium
- **Depends on**: Story 9.1, Story 9.4

## User Story

**As an** operator,
**I want** to see discovery history and statistics in the UI,
**So that** I can monitor discovery performance over time.

## Acceptance Criteria

### AC 1: History Table
**Given** the Discovery tab
**When** I view the history section
**Then** I see a table of recent runs
**And** each row shows date, tokens, wallets found
**And** status (success/failed) is indicated
**And** I can click to see details

### AC 2: Run Details Modal
**Given** the history table
**When** I click on a run row
**Then** a modal shows full details
**And** includes all parameters used
**And** includes discovered wallets list
**And** includes any errors

### AC 3: Statistics Cards
**Given** the Discovery tab
**When** I view the stats section
**Then** I see key metrics cards
**And** includes total runs, wallets discovered
**And** includes success rate, avg per run
**And** updates after each run

### AC 4: Trend Charts
**Given** statistics data
**When** I view the charts section
**Then** I see wallets discovered over time
**And** I see runs per day/week
**And** charts are interactive

### AC 5: Date Range Filter
**Given** history and stats
**When** I select a date range
**Then** history is filtered
**And** stats are recalculated
**And** charts update

## Technical Specifications

### Extended Discovery Component

**Add to src/walltrack/ui/components/discovery.py:**
```python
async def fetch_discovery_history(
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
) -> pd.DataFrame:
    """Fetch discovery run history."""
    settings = get_settings()
    base_url = settings.api_base_url or f"http://localhost:{settings.port}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            params = {"page": page, "page_size": 10}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await client.get("/api/discovery/runs", params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("runs"):
                return pd.DataFrame(
                    columns=["Date", "Tokens", "New", "Updated", "Duration", "Status"]
                )

            rows = []
            for run in data["runs"]:
                rows.append({
                    "Date": run["started_at"][:16].replace("T", " "),
                    "Tokens": run["tokens_analyzed"],
                    "New": run["new_wallets"],
                    "Updated": run["updated_wallets"],
                    "Duration": f"{run['duration_seconds']:.1f}s",
                    "Status": run["status"].upper(),
                })

            return pd.DataFrame(rows)

        except Exception as e:
            log.error("history_fetch_failed", error=str(e))
            return pd.DataFrame()


async def fetch_discovery_stats(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Fetch discovery statistics."""
    settings = get_settings()
    base_url = settings.api_base_url or f"http://localhost:{settings.port}"

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        try:
            params = {}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = await client.get("/api/discovery/stats", params=params)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            log.error("stats_fetch_failed", error=str(e))
            return {}


def format_stats_display(stats: dict) -> str:
    """Format statistics for display."""
    if not stats:
        return "No statistics available"

    total_runs = stats.get("total_runs", 0)
    successful = stats.get("successful_runs", 0)
    success_rate = (successful / total_runs * 100) if total_runs > 0 else 0

    return f"""
## Discovery Statistics

| Metric | Value |
|--------|-------|
| Total Runs | {total_runs} |
| Successful | {successful} |
| Failed | {stats.get('failed_runs', 0)} |
| Success Rate | {success_rate:.1f}% |
| | |
| Total Wallets Discovered | {stats.get('total_wallets_discovered', 0)} |
| Total Wallets Updated | {stats.get('total_wallets_updated', 0)} |
| Avg Wallets/Run | {stats.get('avg_wallets_per_run', 0):.1f} |
| Avg Duration | {stats.get('avg_duration_seconds', 0):.1f}s |
| | |
| Last Run | {stats.get('last_run_at', 'Never')[:16] if stats.get('last_run_at') else 'Never'} |
"""


def create_history_section() -> tuple:
    """Create history and stats section."""
    with gr.Group():
        gr.Markdown("## History & Statistics")

        with gr.Row():
            start_date = gr.Textbox(
                label="Start Date (YYYY-MM-DD)",
                value="",
                placeholder="Leave empty for all",
            )
            end_date = gr.Textbox(
                label="End Date (YYYY-MM-DD)",
                value="",
                placeholder="Leave empty for all",
            )
            filter_btn = gr.Button("Filter", variant="secondary")

        # Stats display
        stats_display = gr.Markdown("Loading statistics...")

        # History table
        history_table = gr.Dataframe(
            headers=["Date", "Tokens", "New", "Updated", "Duration", "Status"],
            interactive=False,
            wrap=True,
        )

        # Pagination
        with gr.Row():
            prev_btn = gr.Button("Previous", variant="secondary")
            page_info = gr.Textbox(value="Page 1", interactive=False)
            next_btn = gr.Button("Next", variant="secondary")

    return (
        start_date,
        end_date,
        filter_btn,
        stats_display,
        history_table,
        prev_btn,
        page_info,
        next_btn,
    )


def create_discovery_tab() -> None:
    """Create the complete discovery tab UI."""
    # ... existing sections ...

    # Add history section
    (
        start_date,
        end_date,
        filter_btn,
        stats_display,
        history_table,
        prev_btn,
        page_info,
        next_btn,
    ) = create_history_section()

    # Track current page
    current_page = gr.State(value=1)

    async def load_history_and_stats(start: str, end: str, page: int):
        history = await fetch_discovery_history(start or None, end or None, page)
        stats = await fetch_discovery_stats(start or None, end or None)
        return history, format_stats_display(stats), f"Page {page}"

    filter_btn.click(
        fn=lambda s, e: load_history_and_stats(s, e, 1),
        inputs=[start_date, end_date],
        outputs=[history_table, stats_display, page_info],
    )

    prev_btn.click(
        fn=lambda s, e, p: load_history_and_stats(s, e, max(1, p - 1)),
        inputs=[start_date, end_date, current_page],
        outputs=[history_table, stats_display, page_info],
    )

    next_btn.click(
        fn=lambda s, e, p: load_history_and_stats(s, e, p + 1),
        inputs=[start_date, end_date, current_page],
        outputs=[history_table, stats_display, page_info],
    )
```

## Implementation Tasks

- [x] Implement history fetching
- [x] Implement stats fetching
- [x] Create history table UI
- [x] Create stats display
- [x] Add date range filtering
- [x] Add pagination
- [x] Integrate with discovery tab
- [x] Test UI functionality

## Definition of Done

- [x] History table shows recent runs
- [x] Stats are displayed correctly
- [x] Date filtering works
- [x] Pagination works
- [x] UI updates after new runs
- [x] Tests pass (29 tests)

## Dev Agent Record

### Implementation Notes (2024-12-24)
- Extended `discovery.py` with history and stats sections
- Added `fetch_discovery_history` function with pagination support
- Updated `fetch_discovery_stats` to return dict instead of DataFrame
- Added `format_stats_display` function for markdown rendering
- Created helper functions: `_create_config_section`, `_create_history_section`
- Added pagination functions: `go_prev_page`, `go_next_page`, `apply_filter`
- Full-width history section with date filtering and pagination controls
- Stats display shows key metrics in markdown table format
- All 29 tests passing

## File List

### Modified Files
- `src/walltrack/ui/components/discovery.py` - Add history/stats sections
- `tests/unit/ui/components/test_discovery.py` - Extended to 29 tests
