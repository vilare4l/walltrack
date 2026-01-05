# Functional Requirements

### FR-1: Watchlist Management

**Description:** Manual CRUD operations for managing wallet addresses in the watchlist.

**User Stories:**
- As an operator, I can add a wallet address to the watchlist so that I can track its trading activity
- As an operator, I can remove a wallet from the watchlist so that I stop receiving signals from underperforming wallets
- As an operator, I can view all wallets in my watchlist with their current status (simulation/live, win rate, recent signals)
- As an operator, I can toggle a wallet between simulation and live mode so that I can progressively validate performance

**Acceptance Criteria:**
- UI provides add/remove/edit functionality for wallet addresses
- Each wallet has configurable mode (simulation/live)
- Wallet status visible in Dashboard (signals count, win rate, mode)
- Changes persist in Supabase database

**Priority:** MUST HAVE (MVP)

---

### FR-2: Real-Time Signal Detection

**Description:** Helius webhooks deliver real-time swap notifications for all watchlist wallets.

**User Stories:**
- As an operator, I want to receive real-time notifications when a watchlist wallet executes a swap so that I can copy the trade immediately
- As an operator, I want webhook status visible in the Config page so that I can verify the system is receiving signals
- As an operator, I want signal logs accessible so that I can audit what signals were received and processed

**Acceptance Criteria:**
- Helius webhooks configured for all active watchlist wallets
- Swap events trigger signal processing pipeline
- Webhook status visible in Config UI (connected/disconnected, last signal timestamp)
- Signal logs stored in Supabase for audit trail

**Priority:** MUST HAVE (MVP)

---

### FR-3: Token Safety Analysis

**Description:** Automated scoring system to detect rug pulls and honeypots before creating positions.

**User Stories:**
- As an operator, I want all tokens automatically analyzed for safety so that I avoid rug pulls
- As an operator, I want to see safety scores for each signal so that I can understand why trades are filtered
- As an operator, I want configurable safety thresholds so that I can adjust risk tolerance

**Acceptance Criteria:**
- Safety scoring uses 4 checks: Liquidity (≥$50K), Holder Distribution (top 10 < 80%), Contract Analysis (honeypot detection), Age (≥24h)
- Weighted average score calculated (each check = 25%)
- Configurable threshold (default 0.60)
- Signals below threshold filtered out automatically
- Safety scores logged and visible in UI

**Priority:** MUST HAVE (MVP)

---

### FR-4: Position Creation & Management

**Description:** Create positions from safe signals with dual-mode execution (simulation/live).

**User Stories:**
- As an operator, I want positions created automatically from safe signals so that I don't miss opportunities
- As an operator, I want simulation mode to track positions without real execution so that I can validate wallet quality
- As an operator, I want live mode to execute real trades via Jupiter API so that I can generate profit
- As an operator, I want to see all active positions in the Dashboard so that I can monitor performance

**Acceptance Criteria:**
- Simulation mode: Full pipeline (signal → position → exit) without Jupiter API execution
- Live mode: Full pipeline WITH Jupiter swap execution
- Position data includes: entry price, amount, source wallet, timestamp, mode
- Positions visible in Dashboard with real-time status

**Priority:** MUST HAVE (MVP)

---

### FR-5: Price Monitoring

**Description:** Track token prices for active positions using DexScreener API to trigger exit strategies.

**User Stories:**
- As an operator, I want real-time price updates for active positions so that stop-loss and trailing-stop triggers work correctly
- As an operator, I want price monitoring accuracy ±1% so that exit strategies execute at intended levels

**Acceptance Criteria:**
- DexScreener API polling (30-60s intervals) for all active position tokens
- Price updates logged and trigger exit strategy evaluation
- Accuracy within ±1% of actual market price
- Monitoring continues until position closed

**Priority:** MUST HAVE (MVP)

---

### FR-6: Exit Strategy Execution

**Description:** Multiple exit strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) with per-wallet configuration and per-position overrides.

**User Stories:**
- As an operator, I want stop-loss protection so that I limit downside risk (-20% default)
- As an operator, I want trailing-stop to capture upside while protecting profits (configurable trail %)
- As an operator, I want scaling-out at predefined levels so that I take partial profits (e.g., 50% @ 2x)
- As an operator, I want mirror-exit so that I sell when the source wallet sells
- As an operator, I want to configure exit strategies per wallet so that I can adapt to different wallet behaviors
- As an operator, I want to override exit strategies per position so that I can manually adjust for specific trades

**Acceptance Criteria:**
- Stop-loss triggers first (capital protection priority)
- Mirror-exit overrides scaling if source wallet sells
- Trailing-stop activates after profit threshold
- Scaling-out executes at configured levels
- Per-wallet default strategies configurable in UI
- Per-position overrides available in Dashboard

**Priority:** MUST HAVE (MVP)

---

### FR-7: Wallet Activity Monitoring

**Description:** Monitor source wallet sales via Helius webhooks to trigger mirror-exit strategy.

**User Stories:**
- As an operator, I want to be notified when a source wallet sells a token I'm holding so that I can mirror the exit
- As an operator, I want mirror-exit to execute automatically when enabled so that I follow smart money exits

**Acceptance Criteria:**
- Helius webhooks monitor ALL source wallets for sell events
- Sell events matched against active positions
- Mirror-exit triggers position close if enabled
- Execution logged for audit trail

**Priority:** MUST HAVE (MVP)

---

### FR-8: Performance Tracking & Analytics

**Description:** Track win rate, PnL, and signal analytics per wallet for data-driven curation.

**User Stories:**
- As an operator, I want to see win rate per wallet so that I can identify underperforming wallets for removal
- As an operator, I want PnL tracking per wallet so that I understand which wallets drive profit
- As an operator, I want signal analytics (count all/30d/7d/24h) so that I can monitor wallet activity levels
- As an operator, I want performance data available in Dashboard so that I can make curation decisions

**Acceptance Criteria:**
- Win rate calculated per wallet: (profitable trades / total trades)
- PnL aggregated per wallet: sum of all closed position profits/losses
- Signal counts tracked with time windows (all/30d/7d/24h)
- Analytics visible in Dashboard with sortable columns
- Historical data persisted in Supabase

**Priority:** MUST HAVE (MVP)

---

### FR-9: System Configuration & Status

**Description:** Centralized configuration interface for system parameters and status monitoring.

**User Stories:**
- As an operator, I want to configure capital allocation and risk parameters so that I control position sizing
- As an operator, I want to see webhook status so that I can verify signal reception
- As an operator, I want to see circuit breaker status so that I know if trading is paused
- As an operator, I want to configure safety thresholds so that I adjust risk tolerance

**Acceptance Criteria:**
- Config UI provides: capital amount, risk % per trade, safety threshold
- Webhook status visible (connected/disconnected, last signal)
- Circuit breaker status visible (active/paused, reason)
- Configuration changes persist and apply immediately

**Priority:** MUST HAVE (MVP)

---
