# 2. Defining Core Experience

### 2.1 Defining Experience

**"Discover → Add → Autopilot"**

WallTrack's defining experience is the seamless transition from wallet discovery to automated trade execution. The core interaction that users will describe to their friends is: **"I find a smart money wallet on GMGN, add it to WallTrack in 30 seconds, and the system automatically copies their trades while I sleep."**

This interaction makes users feel successful because it transforms manual, exhausting trading into high-level strategic curation. The operator never executes a single trade manually—they curate *who* to follow, and the system mirrors trades automatically with customizable exit strategies.

**The Magic Moment:**

The first time a profitable trade is copied automatically without operator intervention. User wakes up, checks Dashboard, sees:

```
✅ New Position Opened (Automated)
Wallet: vBn8x...k2Lp (GMGN Rank #47)
Token: $BONK
Entry: 0.000012 SOL | Current: 0.000018 SOL (+50%)
Mode: Simulation | Strategy: Scaling Out + Stop-Loss
```

This moment validates the entire premise: **"The system works while I don't."**

### 2.2 User Mental Model

**Social Media "Follow" Metaphor**

Users approach WallTrack with a mental model borrowed from social media platforms:

- **GMGN = Discovery Feed**: Browse high-performing wallets (like browsing recommended accounts)
- **WallTrack Watchlist = Following List**: Curate wallets to track (like following accounts)
- **Positions = Activity Feed**: See what wallets are doing (like seeing posts from followed accounts)
- **Promote/Remove = Engagement Actions**: Adjust watchlist based on performance (like unfollowing underperformers)

**Key Mental Model Differences:**

Unlike social media, WallTrack's "follow" has real consequences:

- **Financial Stakes**: Following a wallet = risking capital on their trades
- **Mode Distinction**: "Following" in Simulation (practice) ≠ "Following" in Live (real money)
- **Performance-Based Curation**: Unlike social media loyalty, wallets are added/removed purely on data (win rate, PnL, consistency)

**User Expectations:**

1. **Instant Activation**: Add wallet → tracking starts immediately (< 30s, like clicking "Follow" on Twitter)
2. **Clear Confirmation**: Visual feedback confirms wallet is now tracked (similar to "Following" badge appearing)
3. **Autopilot Execution**: First trade copied automatically without user needing to monitor or confirm

**Where Users Get Confused:**

- **Dual-Mode Complexity**: "Am I following this wallet in Simulation or Live?" → Must be crystal clear at Add Wallet moment
- **Delayed First Signal**: User adds wallet, expects immediate action, but wallet might not trade for hours/days → Need status indicator "Tracking Active, Waiting for Signal"
- **Exit Strategy Mystery**: "The system entered a trade... when will it exit?" → Transparency via strategy labels and expected behavior

### 2.3 Success Criteria

**Core Experience Success Indicators:**

1. **Speed - Add Wallet Flow < 30 seconds**
   - From "Copy wallet address from GMGN" to "Wallet tracked in WallTrack" must be < 30s
   - Form pre-filled with sensible defaults (Mode: Simulation, Strategy: Preset 1)
   - Success: User completes Add Wallet without needing documentation

2. **Confirmation - Immediate Visual Feedback**
   - Wallet appears in Watchlist Table Simple view within 5 seconds
   - Status badge shows "Tracking Active" (green indicator)
   - Sidebar detail shows "Waiting for Signal" state with live countdown/activity
   - Success: User feels confident the system is working

3. **Autopilot Trust - First Trade Copied Without Intervention**
   - System detects wallet trade via Helius webhook
   - Position opened automatically, appears on Dashboard
   - Notification sent (optional, future): "Trade copied from Wallet vBn8x..."
   - Success: User says "this just works"

**User Feels "Smart or Accomplished" When:**

- Adding a high-performing wallet discovered via research (GMGN top 100)
- Seeing first automated position open with clear rationale (wallet name, entry price, strategy)
- Reviewing morning Dashboard: multiple positions managed automatically overnight
- Promoting a wallet from Simulation → Live after validating performance

**Critical Feedback Loops:**

- **Add Wallet**: Immediate appearance in Watchlist + "Tracking Active" badge
- **First Signal Detected**: Position appears on Dashboard with wallet attribution
- **Exit Executed**: Position closes, PnL calculated, wallet performance metrics updated
- **Underperformance**: Wallet win rate drops below threshold → yellow warning badge in Watchlist

### 2.4 Novel UX Patterns

**Hybrid: Familiar Patterns + Novel Twist**

WallTrack combines **established social media patterns** (follow/unfollow, curation feeds) with **novel financial automation patterns** (dual-mode tracking, strategy inheritance).

**Established Patterns (Leverage User Familiarity):**

1. **"Follow" Metaphor for Wallet Tracking**
   - Users already understand: Browse → Follow → See Activity
   - WallTrack adaptation: GMGN → Add Wallet → See Positions
   - No user education needed—metaphor is intuitive

2. **Table + Sidebar Detail (Notion Pattern)**
   - Users familiar with database views: Click row → See details
   - WallTrack adaptation: Click wallet row → Sidebar shows performance charts, actions (Promote, Remove)
   - Gradio implementation: `gr.Dataframe.select()` → toggle `gr.Column(visible=True)`

**Novel Patterns (Require User Education):**

1. **Dual-Mode Wallet Tracking (Simulation vs Live)**
   - **What's Novel**: Same wallet can be tracked in two modes simultaneously
   - **User Education Strategy**:
     - Visual distinction: Blue labels (Simulation), Amber labels (Live)
     - Add Wallet form: Mode selector with tooltip "Start in Simulation to test wallet performance"
     - Promote Wallet action: Clear confirmation dialog "Move Wallet vBn8x... from Simulation → Live?"
   - **Familiar Metaphor**: Like "Drafts vs Published" in content platforms

2. **Strategy Inheritance (Wallet → Position)**
   - **What's Novel**: Exit strategy defined at wallet level, inherited by all positions from that wallet
   - **User Education Strategy**:
     - Add Wallet form: "Default Strategy" dropdown with preset descriptions (e.g., "Scaling Out: Exit 50% at 2x, 50% at 3x")
     - Position detail sidebar: Shows inherited strategy with "From Wallet: vBn8x... (Strategy: Scaling Out)"
     - Future: Override strategy per-position if needed
   - **Familiar Metaphor**: Like "Folder settings inherited by files" in file systems

**Innovation Within Familiar Patterns:**

- **Watchlist Table = Smart Curation Interface**: Beyond static tables, WallTrack's Watchlist dynamically updates performance metrics, enabling data-driven follow/unfollow decisions
- **Dashboard = Monitoring Command Center**: Unlike passive feeds, Dashboard shows *consequences* of followed wallets (active positions, PnL, capital at risk)

### 2.5 Experience Mechanics

**Core Experience Flow: "Add Wallet → Automatic Trade Mirroring"**

#### 1. Initiation: "Add Wallet" Action

**Trigger:**
- User browses GMGN, finds high-performing wallet (e.g., rank #47, 70% win rate, 8.5x avg profit)
- Copies wallet address to clipboard
- Navigates to WallTrack Watchlist tab
- Clicks **"Add Wallet"** button

**System Response:**
- Add Wallet form appears (modal or sidebar)
- Form pre-filled with defaults:
  - **Mode**: Simulation (blue radio button selected)
  - **Default Strategy**: Preset 1 - Scaling Out + Stop-Loss (dropdown selected)
  - **Wallet Address**: Empty (focus on input)
  - **Label** (optional): Empty placeholder "e.g., GMGN Rank #47"

**User Action:**
- Pastes wallet address (validation: Solana address format)
- Optionally adds label (e.g., "GMGN #47 - Memecoin Hunter")
- Clicks **"Add Wallet"** button

**Validation:**
- Address format check (Solana base58)
- Duplicate check (wallet not already in watchlist)
- Mode confirmation (if Live mode selected, show warning: "Live mode will use real capital")

**Time: 20-30 seconds from click to confirmation**

#### 2. Interaction: Wallet Tracked in System

**System Actions (Immediate - < 5s):**

1. **Database Insert**: Wallet record created in Supabase `wallets` table
   - `address`, `mode`, `default_strategy`, `label`, `tracking_status: 'active'`, `added_at: now()`

2. **Helius Webhook Subscription**: Subscribe to wallet address for transaction notifications
   - Webhook type: `accountTransfer` for this wallet address
   - Status confirmation: Helius returns subscription ID

3. **UI Update**: Watchlist table refreshes, new wallet appears
   - Row added to Watchlist Table Simple view
   - Columns: Label | Address (truncated) | Mode | Status | Signals (0) | Win Rate (-) | PnL (-)
   - Status badge: 🟢 **Tracking Active** (green)

**User Feedback:**
- Form closes, returns to Watchlist tab
- New wallet visible in table (top row, sorted by `added_at` desc)
- Toast notification (optional): "Wallet added successfully. Tracking active, waiting for signals."

**Background Process (Ongoing):**
- Discovery Worker polls wallet for existing positions (optional: backfill recent trades)
- System monitors Helius webhook endpoint for incoming signals

#### 3. Feedback: "Waiting for Signal" → "Signal Detected"

**State 1: Waiting for Signal (0-48 hours)**

**User Checks Watchlist:**
- Wallet row shows:
  - Status: 🟢 **Tracking Active**
  - Signals: 0
  - Win Rate: - (no data yet)
  - Last Activity: "Waiting for signal" (gray text)

**User Clicks Wallet Row:**
- Sidebar appears with detail view
- **Status Section**: "🟢 Tracking Active - No signals detected yet"
- **Activity Timeline**: "Added 2 hours ago | Monitoring transactions..."
- **Actions**: Remove Wallet (button), Edit Strategy (future)

**State 2: Signal Detected (automatic)**

**Helius Webhook Triggers:**
- Wallet executes a swap transaction: Buy $BONK with 2 SOL
- Helius sends POST to WallTrack webhook endpoint: `{ wallet_address, transaction_signature, token_address, amount_sol, type: 'buy' }`

**Signal Worker Processes:**
1. Validate signal (token safety checks, liquidity thresholds)
2. Create `signals` record (wallet_id, token_address, action: 'entry', detected_at: now())
3. Execute mirror trade:
   - If Mode = Simulation: Paper trade (no real swap, position marked `mode: 'simulation'`)
   - If Mode = Live: Real swap via Jupiter API (execute buy order)
4. Create `positions` record (wallet_id, token_address, entry_price, quantity, mode, strategy_id, opened_at: now())

**UI Updates (Real-time via Gradio refresh):**

**Dashboard Tab:**
- New row appears in Positions Table Simple:
  - Token: $BONK | Entry: 0.000012 SOL | Current: 0.000012 SOL | PnL: 0% | Mode: 🔵 Simulation | Status: 🟢 Open
  - Wallet attribution: "From: GMGN #47 - Memecoin Hunter"

**Watchlist Tab:**
- Wallet row updates:
  - Signals: **1** (counter increments)
  - Last Activity: "Buy $BONK 2 mins ago"

**User Clicks Wallet Row → Sidebar Detail:**
- **Recent Signals** section shows:
  - 🟢 Buy $BONK (2 mins ago) | Position opened | Status: Tracking
- **Performance Metrics** section: Still accumulating data

#### 4. Completion: Position Lifecycle Completes

**Exit Execution (Automatic):**
- Position Monitor Worker evaluates exit strategy every 30s
- $BONK price reaches 2x (0.000024 SOL) → Triggers "Scaling Out" strategy
- System executes: Sell 50% of position at 2x (Simulation: paper trade, Live: Jupiter swap)
- Position record updated: `status: 'partially_closed'`, `exit_price_1: 0.000024`, `pnl_realized: +100%`

**Second Exit:**
- $BONK price reaches 3x (0.000036 SOL) → Triggers second exit
- System executes: Sell remaining 50% at 3x
- Position record updated: `status: 'closed'`, `exit_price_2: 0.000036`, `pnl_final: +150%`, `closed_at: now()`

**Wallet Performance Update:**
- Wallet metrics recalculated:
  - Signals: 1 → Signals: 1
  - Win Rate: - → Win Rate: **100%** (1 win, 0 losses)
  - PnL: - → PnL: **+150%**

**User Experience:**

**Morning Dashboard Check (Next Day):**
- User opens WallTrack, navigates to Dashboard
- Positions table shows:
  - $BONK position row: Status: ✅ **Closed** | PnL: **+150%** (green text) | Mode: 🔵 Simulation
- Performance Metrics (top of Dashboard):
  - Win Rate: 100% (1/1) | PnL Total: +150% | Active Positions: 0

**User Clicks Position Row → Sidebar Detail:**
- **Position Lifecycle Timeline**:
  - Entry: 0.000012 SOL (2 days ago)
  - Exit 1: 0.000024 SOL (+100%, 50% sold, 1 day ago)
  - Exit 2: 0.000036 SOL (+150%, 50% sold, 6 hours ago)
  - Strategy Used: Scaling Out (from Wallet GMGN #47)

**User Navigates to Watchlist:**
- Wallet row shows updated metrics:
  - Signals: 1 | Win Rate: **100%** | PnL: **+150%** (green) | Last Activity: "Closed $BONK 6h ago"
- User feels: **"This just works. The system copied a profitable trade while I slept."**

**What's Next:**
- User decides to **Promote Wallet** from Simulation → Live (future action)
- User adds more wallets from GMGN (repeats core experience)
- User adjusts exit strategy for this wallet if needed (future customization)

