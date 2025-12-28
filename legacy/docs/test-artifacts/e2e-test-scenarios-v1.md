# WallTrack E2E Test Scenarios - Full User Journey

> **Document Version:** 1.0
> **Epic:** 14 - Simplification
> **Date:** 2024-12-27
> **Author:** Murat (TEA Agent)
> **Target:** Playwright + Gradio Dashboard

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Test Environment Setup](#2-test-environment-setup)
3. [Flow 1: Dashboard Launch & Navigation](#3-flow-1-dashboard-launch--navigation)
4. [Flow 2: Token Discovery](#4-flow-2-token-discovery)
5. [Flow 3: Wallet Discovery from Token](#5-flow-3-wallet-discovery-from-token)
6. [Flow 4: Wallet Profiling](#6-flow-4-wallet-profiling)
7. [Flow 5: Cluster Detection & Visualization](#7-flow-5-cluster-detection--visualization)
8. [Flow 6: 2nd Round Wallet Profiling (Cluster Extraction)](#8-flow-6-2nd-round-wallet-profiling-cluster-extraction)
9. [Flow 7: Watchlist Management](#9-flow-7-watchlist-management)
10. [Flow 8: Helius Webhook Configuration](#10-flow-8-helius-webhook-configuration)
11. [Flow 9: Webhook Reception & Signal Pipeline](#11-flow-9-webhook-reception--signal-pipeline)
12. [Flow 10: Signal Scoring (Epic 14 Simplified)](#12-flow-10-signal-scoring-epic-14-simplified)
13. [Flow 11: Position Opening & Sizing](#13-flow-11-position-opening--sizing)
14. [Flow 12: Entry Order Execution](#14-flow-12-entry-order-execution)
15. [Flow 13: Exit Order Execution](#15-flow-13-exit-order-execution)
16. [Flow 14: Position Lifecycle Management](#16-flow-14-position-lifecycle-management)
17. [Flow 15: Configuration Panel (Scoring)](#17-flow-15-configuration-panel-scoring)
18. [Flow 16: Order Management UI](#18-flow-16-order-management-ui)
19. [Flow 17: Simulation Mode Toggle](#19-flow-17-simulation-mode-toggle)
20. [Test Data & Fixtures](#20-test-data--fixtures)
21. [Appendix: Gradio Element IDs](#21-appendix-gradio-element-ids)

---

## 1. Executive Summary

### Scope

Ce document définit les scénarios E2E complets pour valider WallTrack après l'Epic 14 (Simplification). Les tests couvrent:

- **Discovery Flow**: Token → Wallet → Profile → Cluster
- **Signal Flow**: Webhook → Scoring → Decision
- **Trading Flow**: Position → Entry Order → Exit Order
- **Configuration Flow**: All settings views

### Risk Assessment

| Flow | Impact | Complexity | Priority |
|------|--------|------------|----------|
| Webhook Reception | Critical | High | P0 |
| Signal Scoring | Critical | Medium | P0 |
| Order Execution | Critical | High | P0 |
| Position Management | High | Medium | P1 |
| Discovery Pipeline | High | High | P1 |
| Configuration | Medium | Low | P2 |

### Epic 14 Changes Impacting Tests

1. **Exit Simulation Removed** - No `exit_simulator.py` page tests needed
2. **WalletCache Simplified** - Cluster data from ClusterService, not cache
3. **Scoring Simplified** - 8 params instead of 30+, single threshold (0.65)
4. **Automatic Network Onboarding** - New cluster formation flow

---

## 2. Test Environment Setup

### Prerequisites

```bash
# Start services
docker compose up -d  # Supabase, Neo4j, API

# Start Gradio dashboard
uv run python -m walltrack.ui.dashboard

# Verify services
curl http://localhost:8000/health
curl http://localhost:7865  # Gradio
```

### Environment Variables

```env
GRADIO_HOST=localhost
GRADIO_PORT=7865
API_BASE_URL=http://localhost:8000
SIMULATION_MODE=true  # Start in simulation
```

### Playwright Config

```python
# conftest.py pattern
GRADIO_BASE_URL = f"http://{GRADIO_HOST}:{GRADIO_PORT}"
DEFAULT_TIMEOUT = 30_000
NAVIGATION_TIMEOUT = 60_000
```

---

## 3. Flow 1: Dashboard Launch & Navigation

### Scenario F1.1: Dashboard Cold Start

**Objective:** Verify dashboard loads and displays main structure

**Steps:**
1. Navigate to `GRADIO_BASE_URL`
2. Wait for `#dashboard-title` visible
3. Verify subtitle contains "Solana Memecoin"
4. Verify all main tabs visible

**Locators:**
```python
title = page.locator("#dashboard-title")
subtitle = page.locator("#dashboard-subtitle")
tabs = ["Status", "Wallets", "Clusters", "Signals", "Positions", "Discovery", "Config"]
```

**Expected:**
- Title: "WallTrack Dashboard"
- Subtitle contains: "Solana Memecoin"
- All 7 tabs visible

---

### Scenario F1.2: Tab Navigation Round-Trip

**Objective:** Verify all tabs load correctly

**Steps:**
1. For each tab in [Status, Wallets, Clusters, Signals, Positions, Discovery, Config]:
   - Click tab using `page.get_by_role("tab", name=tab_name)`
   - Wait 500ms for Gradio render
   - Verify key component visible

**Tab Components:**

| Tab | Key Element ID |
|-----|----------------|
| Status | `#status-overview` |
| Wallets | `#wallets-table` |
| Clusters | `#clusters-table` |
| Signals | `#signals-table` |
| Positions | `#positions-table` |
| Discovery | `#discovery-token-input` |
| Config | `#config-trade-threshold` |

---

## 4. Flow 2: Token Discovery

### Scenario F2.1: Discover Token by Address

**Objective:** User enters token mint address and triggers discovery

**Preconditions:**
- Dashboard loaded
- Discovery tab active

**Steps:**
1. Click "Discovery" tab
2. Locate `#discovery-token-input`
3. Enter valid token mint: `So11111111111111111111111111111111111111112` (SOL)
4. Click "Discover" button (`#discovery-discover-btn`)
5. Wait for spinner/loading state
6. Verify results appear in discovery table

**Locators:**
```python
token_input = page.locator("#discovery-token-input")
discover_btn = page.locator("#discovery-discover-btn")
results_table = page.locator("#discovery-results-table")
```

**Expected:**
- Token info displayed (symbol, launch time)
- Early buyer count shown
- "Start Discovery" or similar action available

---

### Scenario F2.2: Token Discovery Error Handling

**Objective:** Invalid token address shows error

**Steps:**
1. Enter invalid address: "invalid_token_address"
2. Click Discover
3. Verify error message appears

**Expected:**
- Error toast/message: "Invalid token address" or similar
- No crash, table remains functional

---

## 5. Flow 3: Wallet Discovery from Token

### Scenario F3.1: Discover Wallets from Successful Token

**Objective:** Discover profitable wallets from token launch

**Preconditions:**
- Valid token entered in Discovery
- Token has early buyers

**Steps:**
1. After token discovery, click "Find Wallets" or equivalent
2. Configure discovery params:
   - Early window: 30 minutes (default)
   - Min profit: 50% (default)
3. Click "Start Discovery"
4. Wait for discovery to complete (may take 30-60s)
5. Verify wallet results table populated

**Locators:**
```python
early_window_slider = page.locator("#discovery-early-window")
min_profit_slider = page.locator("#discovery-min-profit")
start_btn = page.locator("#discovery-start-btn")
wallet_results = page.locator("#discovery-wallet-results")
```

**Data Validation:**
- Each wallet row has: address (truncated), PnL%, trade count
- Wallets sorted by profitability

---

### Scenario F3.2: Add Discovered Wallet to Watchlist

**Objective:** Select wallet and add to monitoring

**Steps:**
1. From discovery results, select a wallet row
2. Click "Add to Watchlist" (`#discovery-add-wallet-btn`)
3. Verify confirmation message
4. Navigate to Wallets tab
5. Verify wallet appears in watchlist

**Expected:**
- Wallet added with status "PENDING_PROFILE" or "ACTIVE"
- Wallet visible in Wallets tab

---

## 6. Flow 4: Wallet Profiling

### Scenario F4.1: View Wallet Profile

**Objective:** View detailed wallet profile after profiling

**Preconditions:**
- Wallet exists in watchlist
- Wallet has been profiled (or trigger profiling)

**Steps:**
1. Navigate to Wallets tab
2. Find wallet in table
3. Click wallet row to open details
4. Verify profile metrics displayed

**Profile Metrics Expected:**
- Win rate (0-100%)
- Total PnL
- Total trades
- Average hold time
- Preferred trading hours
- Last profiled timestamp

**Locators:**
```python
wallets_table = page.locator("#wallets-table")
wallet_row = page.locator(f"#wallets-table tr:has-text('{wallet_address[:8]}')")
profile_panel = page.locator("#wallet-profile-panel")
```

---

### Scenario F4.2: Trigger Manual Re-profile

**Objective:** Force wallet profile update

**Steps:**
1. Open wallet details
2. Click "Refresh Profile" button
3. Wait for profiling to complete
4. Verify updated metrics

**Expected:**
- `last_profiled_at` updated
- Metrics refreshed from Helius API

---

## 7. Flow 5: Cluster Detection & Visualization

### Scenario F5.1: View Cluster List

**Objective:** Display all detected clusters

**Steps:**
1. Navigate to Clusters tab
2. Verify clusters table loads
3. Check cluster columns: ID, Size, Leader, Cohesion, Signal Multiplier

**Locators:**
```python
clusters_tab = page.get_by_role("tab", name="Clusters")
clusters_table = page.locator("#clusters-table")
```

**Expected:**
- Clusters listed with size >= 3
- Leader address highlighted
- Cohesion score 0.0-1.0
- Signal multiplier 1.0-1.8x

---

### Scenario F5.2: View Cluster Details

**Objective:** Drill into cluster members and relationships

**Steps:**
1. Click a cluster row
2. Verify member list appears
3. Check each member shows:
   - Wallet address
   - Join reason
   - Connection count
   - Is leader indicator

**Locators:**
```python
cluster_row = page.locator("#clusters-table tr:first-child")
member_list = page.locator("#cluster-members-list")
```

---

### Scenario F5.3: Cluster Graph Visualization

**Objective:** View cluster relationship graph (if implemented)

**Steps:**
1. Click "View Graph" on cluster
2. Verify graph component renders
3. Check nodes (wallets) and edges (relationships) visible

**Expected:**
- FUNDED_BY edges shown
- BUYS_WITH edges shown
- Leader node highlighted differently

---

## 8. Flow 6: 2nd Round Wallet Profiling (Cluster Extraction)

### Scenario F6.1: Discover Connected Wallets from Cluster

**Objective:** Extract new wallet candidates from cluster relationships

**Preconditions:**
- At least one cluster exists
- Cluster has 3+ members

**Steps:**
1. Open cluster details
2. Click "Find Connected" or "Expand Cluster"
3. Verify new wallet candidates appear
4. Select candidates to add to watchlist

**Business Logic:**
- Uses Neo4j: `MATCH path = (start)-[:FUNDED_BY|BUYS_WITH|CO_OCCURS*1..3]-(connected)`
- Minimum 2 edges required
- Returns wallets not already in cluster

**Expected:**
- Candidate wallets with connection count
- Option to add each to watchlist
- Option to add all to cluster

---

### Scenario F6.2: Automatic Network Onboarding (Epic 14 Story 14-4)

**Objective:** New wallets auto-discovered from cluster signal

**Trigger:**
- Webhook receives signal from clustered wallet
- Wallet not yet in watchlist

**Expected Flow:**
1. Signal received → WalletCache entry created
2. ClusterService queries Neo4j for relationships
3. Connected wallets identified
4. NetworkOnboarder creates cluster or adds to existing
5. New wallets appear in Wallets tab with `discovery_source: CLUSTER_NETWORK`

---

## 9. Flow 7: Watchlist Management

### Scenario F7.1: Add Wallet Manually

**Objective:** Add wallet by pasting address

**Steps:**
1. Navigate to Wallets tab
2. Find add wallet input (`#wallets-new-address`)
3. Paste address: `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` (BONK holder)
4. Click "Add" (`#wallets-add-btn`)
5. Verify wallet added to table

**Locators:**
```python
add_input = page.locator("#wallets-new-address")
add_btn = page.locator("#wallets-add-btn")
```

**Expected:**
- Wallet appears in table
- Status: "PENDING_PROFILE" initially
- Profiling triggered in background

---

### Scenario F7.2: Filter Wallets by Status

**Objective:** Use status filter dropdown

**Steps:**
1. Click status filter (`#wallets-status-filter`)
2. Select "Active"
3. Verify table filtered
4. Select "Insufficient Data"
5. Verify different results

**Filter Options:**
- All
- Active
- Inactive
- Insufficient Data
- Blacklisted

---

### Scenario F7.3: Remove Wallet from Watchlist

**Objective:** Remove wallet from monitoring

**Steps:**
1. Select wallet row
2. Click "Remove" or "Blacklist" button
3. Confirm action
4. Verify wallet removed or status changed

---

## 10. Flow 8: Helius Webhook Configuration

### Scenario F8.1: View Webhook Status

**Objective:** Display current webhook configuration

**Location:** Config tab → Webhooks sub-tab (or Status tab)

**Steps:**
1. Navigate to webhook config section
2. Verify current webhook URL displayed
3. Check subscription count
4. Verify "Active" status indicator

**Expected Display:**
- Webhook URL: `https://yourapp.com/api/webhooks/helius`
- Subscriptions: N wallets
- Last event: timestamp
- Status: Active/Inactive

---

### Scenario F8.2: Register New Webhook (API Integration)

**Objective:** Register wallet for Helius webhook notifications

**Note:** This is typically triggered automatically when adding wallets

**Steps:**
1. Add new wallet to watchlist
2. Verify webhook registration triggered
3. Check Helius API integration logs

**Expected:**
- Wallet address added to Helius webhook subscription
- Wallet status updated to include webhook ID

---

## 11. Flow 9: Webhook Reception & Signal Pipeline

### Scenario F9.1: Receive Helius Webhook

**Objective:** Process incoming transaction webhook

**Trigger:** POST to `/api/webhooks/helius`

**Test Data:**
```json
{
  "type": "TRANSACTION",
  "transactions": [{
    "signature": "5wHuEn...",
    "type": "SWAP",
    "feePayer": "watchlisted_wallet_address",
    "tokenTransfers": [{
      "mint": "token_address",
      "fromUserAccount": "...",
      "toUserAccount": "watchlisted_wallet_address",
      "tokenAmount": 1000000
    }]
  }]
}
```

**Steps:**
1. Send webhook via test script or Playwright API call
2. Verify webhook processed (check API logs or status)
3. Navigate to Signals tab
4. Verify new signal appears in table

**Locators:**
```python
signals_table = page.locator("#signals-table")
latest_signal = page.locator("#signals-table tr:first-child")
```

---

### Scenario F9.2: Signal Filtering (Pre-scoring)

**Objective:** Verify signal filter rules applied

**Filter Checks:**
1. Wallet is watchlisted → PASS
2. Token not blacklisted → PASS
3. Direction is BUY → PASS
4. Cooldown not active → PASS

**Expected Signal States:**
- `filtered_in` → Proceeds to scoring
- `filtered_out` → Logged with reason, not scored

---

## 12. Flow 10: Signal Scoring (Epic 14 Simplified)

### Scenario F10.1: View Signal Score Breakdown

**Objective:** Verify simplified 2-component scoring

**Preconditions:**
- Signal exists from webhook

**Steps:**
1. Navigate to Signals tab
2. Click signal row to expand details
3. Verify score breakdown displayed

**Epic 14 Scoring Formula:**
```
1. Token Safety Gate: Binary (honeypot, freeze, mint) → REJECT or PASS
2. Wallet Score: win_rate × 0.6 + pnl_norm × 0.4 × leader_bonus
3. Cluster Boost: 1.0x to 1.8x multiplier
4. Final Score: wallet_score × cluster_boost >= 0.65 → TRADE
```

**Expected Display:**
| Component | Value |
|-----------|-------|
| Token Safe | ✅ |
| Wallet Score | 0.72 |
| Win Rate | 0.68 |
| Cluster Boost | 1.3x |
| Final Score | 0.94 |
| Decision | TRADE ✅ |

---

### Scenario F10.2: Token Safety Rejection

**Objective:** Verify honeypot/freeze/mint rejection

**Test Cases:**
1. Token with `is_honeypot=true` → Rejected
2. Token with `has_freeze_authority=true` → Rejected
3. Token with `has_mint_authority=true` → Rejected

**Expected:**
- Signal logged with `token_reject_reason`
- `should_trade=false`
- No position created

---

### Scenario F10.3: Threshold Decision

**Objective:** Verify single threshold (0.65)

**Test Cases:**
1. Final score 0.64 → NO TRADE
2. Final score 0.65 → TRADE
3. Final score 0.80 → TRADE with position multiplier

**Expected:**
- Clear TRADE/NO TRADE indicator
- Position multiplier = cluster_boost for TRADE signals

---

## 13. Flow 11: Position Opening & Sizing

### Scenario F11.1: Automatic Position Creation from Signal

**Objective:** Signal triggers position with correct sizing

**Preconditions:**
- Signal scored with `should_trade=true`
- Risk checks pass

**Flow:**
1. Signal passes threshold
2. RiskManager.check_entry_allowed()
3. RiskManager.calculate_position_size()
4. PositionService.create_position()

**Expected Position:**
- `signal_id` linked
- `entry_price` from PriceOracle
- `size_sol` from RiskManager
- `exit_strategy_id` assigned
- `conviction_tier` based on score (high if >= 0.85)

---

### Scenario F11.2: View Position in UI

**Objective:** New position appears in Positions tab

**Steps:**
1. Navigate to Positions tab
2. Verify new position in table
3. Check columns: Token, Entry, Size, Strategy, Status

**Locators:**
```python
positions_table = page.locator("#positions-table")
position_row = page.locator("#positions-table tr:has-text('TOKEN_SYMBOL')")
```

---

### Scenario F11.3: Position Details Sidebar

**Objective:** Click position to view full details

**Steps:**
1. Click position row
2. Sidebar opens (`#position-details-sidebar`)
3. Verify:
   - Entry price
   - Current price
   - P&L (% and SOL)
   - Active strategy
   - Strategy levels (TP/SL thresholds)

**Locators:**
```python
sidebar = page.locator("#position-details-sidebar")
sidebar_content = page.locator("#sidebar-content")
strategy_btn = page.locator("#sidebar-strategy-btn")
```

---

## 14. Flow 12: Entry Order Execution

### Scenario F12.1: Entry Order Created and Filled

**Objective:** Verify order execution flow

**Flow:**
1. EntryOrderService.process_signal()
2. OrderFactory.create_entry_order()
3. OrderExecutor.execute()
4. Order status: PENDING → SUBMITTED → CONFIRMING → FILLED

**Expected:**
- Order visible in Orders tab/section
- Order linked to signal
- Position created on FILLED

---

### Scenario F12.2: Entry Order Retry on Failure

**Objective:** Verify retry mechanism

**Scenario:**
1. Order execution fails (slippage, network error)
2. Order status → FAILED
3. `can_retry=true` if attempts < max_attempts (3)
4. Order scheduled for retry

**Expected:**
- Retry scheduled with exponential backoff
- UI shows retry count and next retry time

---

### Scenario F12.3: Manual Order Retry

**Objective:** User triggers retry from UI

**Steps:**
1. Navigate to Orders view
2. Find failed order
3. Click "Retry" button
4. Verify order status changes to PENDING

**Locators:**
```python
retry_btn = page.locator("#order-retry-btn")
order_status = page.locator("#order-status")
```

---

## 15. Flow 13: Exit Order Execution

### Scenario F13.1: Automatic Exit on Take Profit

**Objective:** Position exits when TP level hit

**Preconditions:**
- Active position with exit strategy
- Price rises to TP trigger level

**Flow:**
1. PriceOracle updates current price
2. Exit checker evaluates rules
3. ExitOrderService.create_exit()
4. Order executes

**Expected:**
- Position status → CLOSED
- `exit_type: take_profit`
- P&L calculated and displayed

---

### Scenario F13.2: Automatic Exit on Stop Loss

**Objective:** Position exits when SL level hit

**Expected:**
- Position status → CLOSED
- `exit_type: stop_loss`
- Negative P&L displayed

---

### Scenario F13.3: Manual Position Close

**Objective:** User manually closes position

**Steps:**
1. Open position details sidebar
2. Click "Close Position" button
3. Confirm action
4. Verify exit order created

**Expected:**
- Exit order created with `order_type: exit`
- `exit_type: manual`

---

## 16. Flow 14: Position Lifecycle Management

### Scenario F14.1: Change Exit Strategy

**Objective:** Switch strategy on active position

**Steps:**
1. Open active position sidebar
2. Click "Change Strategy" (`#sidebar-strategy-btn`)
3. Select new strategy from list
4. Confirm change

**Expected:**
- New strategy levels calculated
- Timeline event logged: `STRATEGY_CHANGED`
- UI shows new TP/SL levels

---

### Scenario F14.2: View Position Timeline

**Objective:** Display position event history

**Steps:**
1. Open position details
2. Click "Timeline" tab/section
3. Verify events listed

**Timeline Events:**
- `position_opened`
- `price_update`
- `strategy_changed`
- `partial_exit`
- `position_closed`

---

### Scenario F14.3: Filter Positions by Status

**Objective:** Toggle between Active and Closed positions

**Steps:**
1. Click "Active" filter
2. Verify only open positions shown
3. Click "Closed" filter
4. Verify only closed positions shown

---

## 17. Flow 15: Configuration Panel (Scoring)

### Scenario F15.1: View Current Scoring Config

**Objective:** Display simplified scoring parameters

**Steps:**
1. Navigate to Config tab
2. Click "Configuration" sub-tab
3. Verify sliders/inputs visible

**Epic 14 Parameters (8 total):**

| Parameter | Default | Range |
|-----------|---------|-------|
| Trade Threshold | 0.65 | 0.5-0.9 |
| Win Rate Weight | 0.60 | 0.0-1.0 |
| PnL Weight | 0.40 | 0.0-1.0 |
| Leader Bonus | 1.15 | 1.0-2.0 |
| PnL Normalize Min | -50 | -500-0 |
| PnL Normalize Max | 200 | 100-1000 |
| Min Cluster Boost | 1.0 | 1.0-1.5 |
| Max Cluster Boost | 1.8 | 1.0-2.5 |

---

### Scenario F15.2: Modify Scoring Weights

**Objective:** Adjust wallet score composition

**Steps:**
1. Adjust Win Rate Weight slider to 0.70
2. PnL Weight auto-adjusts to 0.30 (must sum to 1.0)
3. Click "Apply Changes"
4. Verify chart updates

**Validation:**
- Win Rate + PnL = 1.0
- Error shown if sum != 1.0

---

### Scenario F15.3: Score Preview Calculator

**Objective:** Test hypothetical scores

**Steps:**
1. Click "Score Preview" sub-tab
2. Set inputs:
   - Win Rate: 0.65
   - PnL: 75%
   - Is Leader: true
   - Cluster Boost: 1.3
3. Click "Calculate Score"
4. Verify result breakdown

**Expected Output:**
```
Final Score: 0.91
- Wallet Score: 0.70 (win_rate: 0.65 × 0.6 + pnl: 0.625 × 0.4)
- Leader Bonus: × 1.15 = 0.805
- Cluster Boost: × 1.3
- Decision: TRADE ELIGIBLE (1.3x position)
```

---

### Scenario F15.4: Reset to Defaults

**Objective:** Reset all config to defaults

**Steps:**
1. Click "Reset to Defaults" button
2. Confirm action
3. Verify all sliders return to defaults

---

## 18. Flow 16: Order Management UI

### Scenario F16.1: View Order List

**Objective:** Display all orders with filters

**Location:** Orders page or Positions tab sub-section

**Steps:**
1. Navigate to Orders view
2. Verify order table with columns:
   - ID, Type, Token, Amount, Status, Attempts, Created

---

### Scenario F16.2: Filter Orders by Status

**Objective:** Use status filter

**Filters:**
- All
- Pending
- Submitted
- Confirming
- Filled
- Failed
- Cancelled

---

### Scenario F16.3: Cancel Pending Order

**Objective:** Cancel order before execution

**Steps:**
1. Find pending order
2. Click "Cancel" button
3. Enter reason (optional)
4. Confirm

**Expected:**
- Order status → CANCELLED
- Reason logged

---

## 19. Flow 17: Simulation Mode Toggle

### Scenario F17.1: Verify Simulation Mode Active

**Objective:** Confirm simulation mode indicators

**Steps:**
1. Check dashboard header/status bar
2. Verify "SIMULATION" badge visible
3. Verify orders marked as `is_simulated=true`

**Indicators:**
- Header badge: "🧪 SIMULATION MODE"
- Orders show simulation icon
- No real trades executed

---

### Scenario F17.2: Toggle to Live Mode

**Objective:** Switch from simulation to live (with confirmation)

**Steps:**
1. Navigate to Config → Mode Settings
2. Toggle "Simulation Mode" off
3. Confirm warning dialog
4. Verify mode changed

**Warning Dialog:**
```
⚠️ LIVE MODE WARNING

Switching to live mode will execute REAL trades with REAL funds.

Are you sure you want to continue?

[Cancel] [Confirm]
```

---

## 20. Test Data & Fixtures

### Token Test Data

```python
VALID_TOKENS = [
    # SOL wrapped
    {
        "mint": "So11111111111111111111111111111111111111112",
        "symbol": "SOL",
        "is_safe": True,
    },
    # BONK
    {
        "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "symbol": "BONK",
        "is_safe": True,
    },
]

HONEYPOT_TOKEN = {
    "mint": "HONEYPOT111111111111111111111111111111111",
    "is_honeypot": True,
}
```

### Wallet Test Data

```python
HIGH_PERFORMER = {
    "address": "HighPerf11111111111111111111111111111111111",
    "win_rate": 0.75,
    "total_pnl": 150.0,
    "is_leader": True,
}

LOW_PERFORMER = {
    "address": "LowPerf111111111111111111111111111111111111",
    "win_rate": 0.30,
    "total_pnl": -50.0,
    "is_leader": False,
}
```

### Webhook Payload Templates

```python
def create_swap_webhook(wallet: str, token: str, direction: str = "buy"):
    return {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"tx_{uuid4()}",
            "type": "SWAP",
            "feePayer": wallet,
            "tokenTransfers": [{
                "mint": token,
                "fromUserAccount": "..." if direction == "sell" else "pool",
                "toUserAccount": wallet if direction == "buy" else "pool",
                "tokenAmount": 1000000,
            }]
        }]
    }
```

---

## 21. Appendix: Gradio Element IDs

### Dashboard Structure

```
#dashboard-title
#dashboard-subtitle
#tab-status
#tab-wallets
#tab-clusters
#tab-signals
#tab-positions
#tab-discovery
#tab-config
```

### Wallets Tab

```
#wallets-table
#wallets-refresh-btn
#wallets-status-filter
#wallets-new-address
#wallets-add-btn
#wallet-profile-panel
```

### Config Tab

```
#config-trade-threshold
#config-wallet-weight (now win-rate-weight)
#config-cluster-weight (deprecated in Epic 14)
#config-apply-weights-btn
#config-normalize-btn
#config-reset-btn
#config-status
```

### Positions Tab

```
#positions-table
#positions-refresh-btn
#positions-filter-active
#positions-filter-closed
#history-table
#history-date-from
#history-date-to
#history-pnl-filter
#history-search-btn
```

### Position Details Sidebar

```
#position-details-sidebar
#sidebar-title
#sidebar-content
#sidebar-close-btn
#sidebar-strategy-btn
#strategy-row
```

### Signals Tab

```
#signals-table
#signals-refresh-btn
#signals-filter
```

### Discovery Tab

```
#discovery-token-input
#discovery-discover-btn
#discovery-results-table
#discovery-early-window
#discovery-min-profit
#discovery-start-btn
#discovery-wallet-results
#discovery-add-wallet-btn
```

### Clusters Tab

```
#clusters-table
#cluster-members-list
#cluster-expand-btn
#cluster-graph
```

---

## Document Changelog

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-27 | Murat (TEA) | Initial complete E2E test scenarios |

---

**Next Steps:**
1. Découper ce document en specs exécutables par flux
2. Créer les fichiers pytest correspondants
3. Implémenter les fixtures de test data
4. Exécuter en mode headed pour validation visuelle
