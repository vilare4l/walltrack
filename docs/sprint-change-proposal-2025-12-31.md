# Sprint Change Proposal - Epic 3 RPC Migration

**Project**: WallTrack V2
**Date**: 2025-12-31
**Author**: SM Agent (Correct-Course Workflow)
**User**: Christophe
**Status**: 🟠 PENDING APPROVAL

---

## Executive Summary

### Change Trigger
Epic 3 Stories 3.1, 3.2, 3.3 are marked "done" but were implemented using **Helius Enhanced API** (paid service, 125K+ req/month). User objective is to replace with **Solana RPC Public** (free, 240 req/min) to achieve cost-saving while maintaining identical functionality.

### Impact Scope
- **Code**: 3 core modules to re-implement + 1 new parser component + 70+ tests
- **Documentation**: 18 changes across PRD, Epics, Architecture, UX Design
- **Epics**: Epic 3 ("done" → "in-progress"), Epic 4 (clarification needed), Epic 5 (dual-mode approach)

### Recommended Solution
**Option D**: RPC for Epic 3 + Dual-mode for Epic 5
- Re-implement Stories 3.1, 3.2, 3.3 with Solana RPC Public
- Create shared RPC transaction parser
- Story 5.1 becomes dual-mode: RPC Polling (default, free) + Helius Webhooks (opt-in, premium)

### Timeline
- **Phase 1** (Epic 3 RPC): 18-26 hours (1-2 weeks)
- **Phase 2** (Documentation): 8-12 hours (2-3 days)
- **Phase 3** (Epic 5 dual-mode): Optional, 3-5 days

### Cost Impact
- **Before**: 125K+ Helius requests/month
- **After**: 0-75K requests/month (0 if RPC only, <75K if webhooks opt-in)
- **Savings**: ~100% cost reduction for Epic 3 operations

---

## 1. Change Trigger & Context

### 1.1 What Triggered This Change?

**Discovery**: Post-implementation analysis revealed Epic 3 Stories 3.1, 3.2, 3.3 use wrong API approach.

**Current Implementation (❌ WRONG)**:
```python
# Story 3.1 - Wallet Discovery
helius_client.get_token_transactions(mint, tx_type="SWAP")

# Story 3.2 - Performance Analysis
helius_client.get_wallet_transactions(wallet, tx_type="SWAP")

# Story 3.3 - Behavioral Profiling
helius_client.get_wallet_transactions(wallet)
```

**Required Implementation (✅ CORRECT)**:
```python
# All Stories 3.1, 3.2, 3.3
signatures = rpc_client.getSignaturesForAddress(address, limit=1000)
transactions = [rpc_client.getTransaction(sig) for sig in signatures]
parsed_swaps = [parse_rpc_transaction(tx, wallet_addr) for tx in transactions]
```

**Why This Matters**:
- Helius Enhanced API: $$ paid service, 125K+ req/month
- Solana RPC Public: Free tier, 240 req/min limit
- Same functionality achievable with RPC + manual parsing
- Objective: Minimize external API costs while maintaining feature parity

### 1.2 Global Context

**Strategic Goal**: Replace Helius with RPC for cost-saving
- **NOT reverting to Helius** (some old docs mentioned Helius)
- **IS migrating to RPC** (free alternative, same objectives)

**Current Status**:
- Epic 1-2: ✅ Complete and acceptable (no changes needed)
- Epic 3: ✅ Marked "done" but Stories 3.1, 3.2, 3.3 need RPC re-implementation
- Epic 4+: In backlog (blocked until Epic 3 validated)

**Technical Philosophy**:
- **Smart Money Discovery**: Find wallets that PERFORMED (early profitable buyers)
- **NOT Bag Holders**: Current token holders have no performance guarantee
- **Same Filters**: Early entry (<30min after launch) + Profitable exit (>50% profit)

### 1.3 Scope of Impact

**Code Files Affected**:
- `src/walltrack/core/discovery/wallet_discovery.py` (Story 3.1)
- `src/walltrack/core/analysis/performance_orchestrator.py` (Story 3.2)
- `src/walltrack/core/behavioral/profiler.py` (Story 3.3)
- `src/walltrack/services/solana/transaction_parser.py` (NEW - shared parser)
- `src/walltrack/services/solana/rpc_client.py` (add missing methods)
- `tests/` (70+ tests to adapt)

**Documentation Affected**:
- `docs/prd.md` (5 changes)
- `docs/epics.md` (6 changes)
- `docs/architecture.md` (4 changes)
- `docs/ux-design-specification.md` (3 changes)

**Database Impact**:
- Clear `wallets` table (existing wallets discovered via wrong method may be bag holders)

**Stories NOT Affected**:
- Story 3.4 (Decay Detection): Uses calculated metrics (win_rate, total_trades) - no change needed
- Story 3.5 (Watchlist): Evaluates existing metrics - no change needed
- Story 3.6 (E2E): Re-run validation after Stories 3.1-3.3 complete

---

## 2. Impact Analysis

### 2.1 Epic Impact Assessment

| Epic | Status | Impact | Reason |
|------|--------|--------|--------|
| **Epic 3** | done → in-progress | 🔴 CRITICAL | Stories 3.1, 3.2, 3.3 need RPC re-implementation |
| **Epic 4** | backlog | 🟡 CLARIFICATION NEEDED | Story 4.1 (funding sources) - RPC method unclear |
| **Epic 5** | backlog | 🟡 APPROACH CHANGE | Story 5.1 dual-mode (RPC Polling default + Helius Webhooks opt-in) |
| Epic 1-2 | done | ✅ NO IMPACT | Complete and validated |
| Epic 6-8 | backlog | ✅ NO IMPACT | Use generated signals, no direct Helius dependency |

### 2.2 Story-Level Impact

**Stories Requiring Re-Implementation**:

| Story | Current Lines | Helius Calls | RPC Alternative | Effort |
|-------|---------------|--------------|-----------------|--------|
| 3.1 | 513 lines | `get_token_transactions()` | `getSignaturesForAddress(mint)` + parser | 6-8h |
| 3.2 | 385 lines | `get_wallet_transactions()` | `getSignaturesForAddress(wallet)` + parser | 4-6h |
| 3.3 | 232 lines | `get_wallet_transactions()` | `getSignaturesForAddress(wallet)` + parser | 4-6h |
| **Parser** | NEW | N/A | Parse raw RPC → SwapTransaction | 4-6h |
| **Tests** | 70+ tests | Mock Helius | Mock RPC + new fixtures | 4-6h |

**Total Effort**: 18-26 hours (1-2 weeks)

### 2.3 Documentation Conflicts Identified

**6 Critical Conflicts**:

1. **PRD ↔ Code**: PRD positions RPC as "fallback for webhooks", code uses Helius everywhere
2. **Epics ↔ Objective**: Epics describe Helius primary, objective says RPC required
3. **Architecture ↔ Implementation**: Architecture says Helius = "webhooks only", code uses for transaction history
4. **Architecture ↔ Epic 4**: Funding sources via Helius, RPC equivalent unclear
5. **UX ↔ Dual-Mode**: UX mentions webhooks, missing dual-mode UI (Polling vs Webhooks)
6. **Positioning Inconsistency**: Helius vs RPC priority varies across documents

**Impact if Not Fixed**:
- Developer confusion (docs say Helius OK, objective says RPC required)
- Cost explosion (125K+ req/month instead of <75K)
- Epic 4 blocked (funding sources method undocumented)
- Epic 5 confusion (webhooks vs polling unclear)

---

## 3. Proposed Solution

### 3.1 Options Evaluated

| Option | Description | Cost-Saving | Complexity | Recommendation |
|--------|-------------|-------------|------------|----------------|
| **A** | RPC for Epic 3 only | ✅ Yes | Low | ⚠️ Incomplete (Epic 5 unclear) |
| **B** | Abstraction (Helius + RPC) | ⚠️ Partial | High | ❌ Over-engineering |
| **C** | Keep Helius, optimize | ❌ No | Low | ❌ Doesn't meet objective |
| **D** | RPC Epic 3 + Dual-mode Epic 5 | ✅ Yes | Medium | ✅ **RECOMMENDED** |

### 3.2 Recommended Approach: Option D

**Why Option D?**
- ✅ Achieves cost-saving objective (0 Helius req if RPC only)
- ✅ Flexibility for Epic 5 (free polling OR premium webhooks)
- ✅ Complete documentation alignment
- ✅ RPC becomes foundation (Helius 100% optional)
- ✅ Reasonable complexity (no abstraction layer)

**What Changes**:
1. **Epic 3**: RPC replaces Helius for discovery + profiling
2. **Epic 5**: Dual-mode approach (RPC Polling default, Helius Webhooks opt-in)
3. **Documentation**: All docs updated to reflect RPC primary, Helius optional
4. **Architecture**: Clear boundaries (RPC = data layer, Helius = premium signals)

### 3.3 Implementation Phases

#### **Phase 1: Epic 3 RPC Migration** (1-2 weeks) - 🔴 CRITICAL

**Sequence**:
```
1.1 Create RPC transaction parser (4-6h)
    └─ Shared component for Stories 3.1, 3.2, 3.3

1.2 Re-implement Story 3.1 - Wallet Discovery (6-8h)
    └─ getSignaturesForAddress(token_mint) + parser

1.3 Re-implement Story 3.2 - Performance Analysis (4-6h)
    └─ getSignaturesForAddress(wallet) + metrics calculation

1.4 Re-implement Story 3.3 - Behavioral Profiling (4-6h)
    └─ Same as 3.2, different metrics (position sizing, hold duration)

1.5 Adapt tests (4-6h)
    └─ 70+ tests: Mock RPC instead of Helius

1.6 Validate E2E Story 3.6 (2h)
    └─ 19 E2E tests must pass with RPC-discovered wallets
```

**Deliverables**:
- ✅ `src/walltrack/services/solana/transaction_parser.py` (new)
- ✅ 3 core modules re-implemented (discovery, performance, behavioral)
- ✅ 70+ tests passing
- ✅ Database cleared (wallets table reset)

#### **Phase 2: Documentation Update** (2-3 days) - 🟠 HIGH PRIORITY

**Sequence**:
```
2.1 Update PRD (3-4h)
    └─ 5 changes: FR4, FR23, External Integrations, Architecture diagram, NFR

2.2 Update Epics (3-4h)
    └─ 6 changes: Stories 3.1, 3.2, 3.3, 5.1, Epic 4 clarification

2.3 Update Architecture (2-3h)
    └─ 4 changes: External APIs, services/ layer, build sequence, network discovery

2.4 Update UX Design (1-2h)
    └─ 3 changes: Config page signal mode, status bar indicator, wireframe
```

**Deliverables**:
- ✅ All 4 docs updated with OLD → NEW changes
- ✅ Check-implementation-readiness re-run (validation)

#### **Phase 3: Epic 5 Dual-Mode** (3-5 days) - 🟡 OPTIONAL

**Only if Epic 5 starts**:
```
3.1 Implement RPC Polling worker (1-2 days)
    └─ Scheduler job: 10-second intervals, query watchlisted wallets

3.2 Create Config UI dual-mode selector (1 day)
    └─ Radio buttons: RPC Polling / Helius Webhooks

3.3 Helius Webhooks opt-in (1 day)
    └─ Conditional: Only activate if API key configured

3.4 Dual-mode tests (1 day)
    └─ Test both paths, mode switching
```

**Deliverables**:
- ✅ RPC Polling worker (default mode)
- ✅ Config UI mode selector
- ✅ Helius webhooks opt-in logic

---

## 4. Specific Changes Required

### 4.1 Code Changes

#### **Change C1: Create RPC Transaction Parser** 🔴 P0 NEW

**File**: `src/walltrack/services/solana/transaction_parser.py` (NEW)

**Purpose**:
Parse raw Solana RPC transactions into `SwapTransaction` models. Helius does this automatically via enhanced API, we must implement manually for RPC.

**Functionality**:
```python
async def parse_rpc_transaction(
    raw_tx: dict,
    wallet_address: str,
    token_mint: str
) -> SwapTransaction | None:
    """Parse raw RPC transaction into SwapTransaction model.

    Extracts:
    - Direction: BUY or SELL (based on token transfer direction)
    - Token amount: How much token was swapped
    - SOL amount: How much SOL was spent/received
    - Timestamp: Transaction timestamp

    Returns None if transaction is not a SWAP or parsing fails.
    """
```

**Dependencies**: Solana transaction structure knowledge, token transfer parsing

**Estimated Effort**: 4-6 hours (complex parsing logic + edge cases)

---

#### **Change C2: Re-implement Story 3.1 Wallet Discovery** 🔴 P0

**File**: `src/walltrack/core/discovery/wallet_discovery.py`

**OLD**:
```python
transactions_data = await self.helius_client.get_token_transactions(
    token_mint=token_address,
    limit=self.max_transactions,
    tx_type="SWAP",
)
transactions = [Transaction(**tx_data) for tx_data in transactions_data]
```

**NEW**:
```python
# Step 1: Get transaction signatures
signatures = await self.rpc_client.getSignaturesForAddress(
    address=token_address,
    limit=1000,  # RPC max
)

# Step 2: Fetch full transactions
transactions = []
for sig in signatures:
    tx_data = await self.rpc_client.getTransaction(sig['signature'])
    if tx_data:
        parsed = parse_rpc_transaction(tx_data, wallet_addr, token_address)
        if parsed:
            transactions.append(parsed)
```

**Justification**: Replace Helius pre-parsed transactions with RPC + manual parsing

**Estimated Effort**: 6-8 hours (logic + throttling + error handling)

---

#### **Change C3: Re-implement Story 3.2 Performance Analysis** 🔴 P0

**File**: `src/walltrack/core/analysis/performance_orchestrator.py`

**OLD**:
```python
tx_response = await self.helius_client.get_wallet_transactions(
    wallet_address=wallet_address,
    limit=100,
    tx_type="SWAP",
)
```

**NEW**:
```python
# Use RPC + shared parser (same as Story 3.1)
signatures = await self.rpc_client.getSignaturesForAddress(
    address=wallet_address,
    limit=100,
)
transactions = [
    parsed for sig in signatures
    if (tx_data := await self.rpc_client.getTransaction(sig['signature']))
    and (parsed := parse_rpc_transaction(tx_data, wallet_address, None))
]
```

**Justification**: Same approach as Story 3.1, different address (wallet instead of token)

**Estimated Effort**: 4-6 hours (reuse parser logic)

---

#### **Change C4: Re-implement Story 3.3 Behavioral Profiling** 🔴 P0

**File**: `src/walltrack/core/behavioral/profiler.py`

**OLD**:
```python
transactions = await self.helius_client.get_wallet_transactions(
    wallet_address=wallet_address
)
```

**NEW**:
```python
# Same as Change C3 (reuse RPC + parser)
signatures = await self.rpc_client.getSignaturesForAddress(
    address=wallet_address,
    limit=100,
)
transactions = [...]  # Same parsing logic as C3
```

**Justification**: Identical to Story 3.2, different metrics calculated downstream

**Estimated Effort**: 4-6 hours

---

#### **Change C5: Add RPC Client Methods** 🔴 P0

**File**: `src/walltrack/services/solana/rpc_client.py`

**NEW Methods**:
```python
async def getSignaturesForAddress(
    self,
    address: str,
    limit: int = 1000
) -> list[dict]:
    """Fetch transaction signatures for address.

    RPC method: getSignaturesForAddress
    Returns: List of {signature, slot, blockTime, ...}
    """

async def getTransaction(
    self,
    signature: str
) -> dict | None:
    """Fetch full transaction details.

    RPC method: getTransaction
    Returns: Full transaction data with instructions, accounts, etc.
    """
```

**Justification**: Required RPC methods currently missing from client

**Estimated Effort**: 2-3 hours (straightforward RPC wrapper)

---

### 4.2 Documentation Changes

#### **PRD Changes** (5 changes)

**Change D1: FR4 - Wallet Discovery Method** 🔴 P0

**Location**: Line ~332

**OLD**:
```markdown
- FR4: System can discover wallets from token transaction history
```

**NEW**:
```markdown
- FR4: System can discover wallets from token transaction history via Solana RPC Public API (`getSignaturesForAddress` + `getTransaction` with manual parsing)
```

---

**Change D2: FR23 - Signal Detection Dual-Mode** 🔴 P0

**Location**: Line ~366

**OLD**:
```markdown
- FR23: System can receive real-time swap notifications via Helius webhooks
```

**NEW**:
```markdown
- FR23: System can detect swap signals via dual-mode approach:
  - **Default**: RPC Polling (10-second intervals, free tier, no external dependencies)
  - **Optional**: Helius Webhooks (real-time, requires Helius API key, opt-in via Config UI)
```

---

**Change D3: External Integrations Table** 🔴 P0

**Location**: Line ~308

**OLD**:
```markdown
| **Helius** | Real-time swap webhooks | RPC polling |
| **Solana RPC** | Blockchain queries | Multiple providers |
```

**NEW**:
```markdown
| **Solana RPC Public** | Primary: Transaction history, wallet profiling, signal detection (polling) | Multiple providers (Helius RPC, QuickNode, Alchemy) |
| **Helius Enhanced** | Optional: Webhooks for real-time signals (opt-in), fallback if RPC fails | Solana RPC Public |
```

---

**Change D4: Architecture Diagram** 🟠 P1

**Location**: Line ~287

**OLD**:
```markdown
Helius Webhook → FastAPI → Signal Processing → Neo4j/Supabase Query
```

**NEW**:
```markdown
**Default Flow (RPC Polling)**:
RPC Polling Worker (10s) → Signal Processing → Neo4j/Supabase Query

**Optional Flow (Helius Webhooks)**:
Helius Webhook → FastAPI → Signal Processing → Neo4j/Supabase Query
```

---

**Change D5: NFR Cost Optimization** 🟡 P2

**Location**: New section after NFR

**NEW**:
```markdown
### Cost Optimization (NFR)

- **Target**: Reduce external API costs from 125K+ req/month (Helius) to 0-75K req/month
- **Strategy**:
  - Use Solana RPC Public (free, 240 req/min) for Epic 3 (discovery, profiling)
  - Use RPC Polling (10s intervals) for Epic 5 signals (default mode)
  - Reserve Helius for opt-in webhooks only (premium feature)
- **Measurement**: Track monthly Helius API usage via Config dashboard
```

---

#### **Epics Changes** (6 changes)

**Change D6: Story 3.1 Description** 🔴 P0

**Location**: Line ~473

**OLD**:
```markdown
**When** wallet discovery runs (via Helius transaction history)
```

**NEW**:
```markdown
**When** wallet discovery runs (via Solana RPC Public: `getSignaturesForAddress` + `getTransaction`)
**Then** wallets who bought early (<30min) and sold profitably (>50%) are identified

**Technical Implementation**:
- Use `rpc.getSignaturesForAddress(token_mint, limit=1000)` to get transaction signatures
- For each signature: `rpc.getTransaction(signature)` to get full transaction data
- Parse transactions manually to detect BUY/SELL events
- Apply filters: early entry (<30min) AND profitable exit (>50%)
- Result: Smart money wallets (performers), not bag holders (current holders)
```

---

**Change D7: Story 3.1 Acceptance Criteria** 🔴 P0

**Location**: Line ~475-481

**OLD**:
```markdown
**AC1**: Helius client can fetch token transaction history
**AC2**: Transactions are parsed to identify BUY/SELL events
```

**NEW**:
```markdown
**AC1**: Solana RPC client can fetch token signatures (`getSignaturesForAddress`)
**AC2**: RPC client can fetch full transaction details (`getTransaction`)
**AC3**: Transaction parser can identify BUY/SELL events from raw RPC data
**AC4**: Parser extracts: wallet_address, token_amount, sol_amount, timestamp, direction
**AC5**: Filters applied correctly: early entry + profitable exit
```

---

**Change D8: Story 3.2 Description** 🔴 P0

**Location**: Line ~520 (approx)

**OLD**:
```markdown
**When** wallet profiling runs (via Helius transaction history)
```

**NEW**:
```markdown
**When** wallet profiling runs (via Solana RPC Public: `getSignaturesForAddress(wallet_address)`)
**Then** performance metrics calculated: win_rate, pnl_total, total_trades

**Technical Implementation**:
- Use RPC transaction parser (shared from Story 3.1)
- Fetch wallet history via `getSignaturesForAddress`
- Same business logic, different data source
```

---

**Change D9: Story 3.3 Description** 🔴 P0

**Location**: Line ~570 (approx)

**OLD**:
```markdown
**When** behavioral profiling runs (via Helius transaction history)
```

**NEW**:
```markdown
**When** behavioral profiling runs (via Solana RPC Public: `getSignaturesForAddress(wallet_address)`)
**Then** behavioral metrics calculated: position_size_style, hold_duration_style

**Technical Implementation**:
- Use RPC transaction parser (shared from Story 3.1)
- Same behavioral analysis logic
```

---

**Change D10: Story 5.1 Dual-Mode** 🔴 P0

**Location**: Line ~756

**OLD**:
```markdown
#### Story 5.1: Helius Webhook Reception
```

**NEW**:
```markdown
#### Story 5.1: Signal Detection (Dual-Mode: RPC Polling + Helius Webhooks)

**Mode 1: RPC Polling (Default)**
**Given** RPC polling worker configured (10-second intervals)
**When** polling detects new SWAP transactions on watchlisted wallets
**Then** signal is queued for processing

**Mode 2: Helius Webhooks (Optional)**
**Given** Helius API key configured + webhooks enabled in Config
**When** Helius sends swap notification
**Then** signal is queued for processing

**Configuration**: Config UI selector for mode (Polling / Webhooks)
```

---

**Change D11: Epic 4 Story 4.1 Clarification** 🟡 P2

**Location**: Line ~623

**OLD**:
```markdown
**Then** funder(s) are identified via Helius funding sources API
```

**NEW**:
```markdown
**Then** funder(s) are identified via Solana RPC Public:
- Fetch `getSignaturesForAddress(wallet)` and filter `SOL_TRANSFER` transactions
- Extract sender addresses where `amount >= min_funding_amount`
- Note: More complex than Helius API but feasible

**Alternative**: Helius funding sources API as opt-in if RPC too complex
```

---

#### **Architecture Changes** (4 changes)

**Change D12: External APIs Priority** 🔴 P0

**Location**: Line ~56

**OLD**:
```markdown
| External APIs | Helius, Jupiter, DexScreener, Solana RPC (all with fallbacks) |
```

**NEW**:
```markdown
| External APIs | Solana RPC Public (primary), Jupiter, DexScreener, Helius Enhanced (optional) |
| API Priorities | RPC for discovery/profiling/signals, Helius for opt-in webhooks only |
```

---

**Change D13: services/ Layer Description** 🔴 P0

**Location**: Line ~195-198

**OLD**:
```markdown
services/
├── helius/          # Webhook management (fallback: RPC polling)
└── solana/          # RPC client (multi-provider rotation)
```

**NEW**:
```markdown
services/
├── solana/          # PRIMARY: RPC client + transaction parser
│   ├── rpc_client.py         # getSignaturesForAddress, getTransaction
│   └── transaction_parser.py # Parse raw RPC → SwapTransaction
├── helius/          # OPTIONAL: Webhooks only (opt-in)
│   └── webhook_manager.py
```

---

**Change D14: Build Sequence** 🟠 P1

**Location**: Line ~722

**OLD**:
```markdown
| 3. Discovery wallets | `core/discovery/`, `services/helius/` | `wallets`, Neo4j |
| 7. Webhooks Helius | `api/webhooks/`, `services/helius/` | `webhooks` |
```

**NEW**:
```markdown
| 3. Discovery wallets | `core/discovery/`, `services/solana/` (RPC) | `wallets`, Neo4j |
| 7. Signal Detection | `scheduler/` (RPC polling) OR `api/webhooks/` (Helius opt-in) | `signals` |
```

---

**Change D15: Network Discovery Example** 🟡 P2

**Location**: Line ~640

**OLD**:
```python
funders = await helius_client.get_funding_sources(wallet_id)
```

**NEW**:
```python
# Primary: RPC approach
signatures = await rpc_client.getSignaturesForAddress(wallet_id)
funding_txs = [tx for tx in transactions if tx.type == "SOL_TRANSFER"]
funders = [tx.sender for tx in funding_txs]

# Alternative: Helius opt-in (if RPC too complex)
```

---

#### **UX Design Changes** (3 changes)

**Change D16: Config Page Signal Mode** 🔴 P0

**Location**: Line ~322

**OLD**:
```markdown
| **Webhooks** | Helius status, Sync button |
```

**NEW**:
```markdown
| **Signal Detection** | Mode selector: RPC Polling (default) / Helius Webhooks (opt-in) |
| **RPC Polling Config** | Interval (10s), Watchlist size, Last poll timestamp |
| **Helius Webhooks** | API key input, Status, Sync button (only if Webhooks selected) |
```

---

**Change D17: Status Bar Mode Indicator** 🟠 P1

**Location**: Line ~225

**OLD**:
```markdown
🟢 Signals: 12 today (last: 14:32)
🟢 Webhooks: sync OK
```

**NEW**:
```markdown
🟢 Signals: 12 today (last: 14:32) [Mode: RPC Polling 10s]
  OR
🟢 Signals: 12 today (last: 14:32) [Mode: Helius Webhooks]
```

---

**Change D18: Config Page Wireframe** 🟡 P2

**Location**: New section

**NEW**:
```markdown
### Config Page - Signal Detection Mode UI

┌─────────────────────────────────────────┐
│ Signal Detection                        │
├─────────────────────────────────────────┤
│ Mode: ◉ RPC Polling (Free)             │
│       ○ Helius Webhooks (Premium)      │
│                                         │
│ [If RPC Polling]                        │
│ Interval: [10] seconds                  │
│ Last Poll: 2s ago                       │
│                                         │
│ [If Helius Webhooks]                    │
│ API Key: [********************]        │
│ Status: 🟢 Active                       │
│ [Sync] button                           │
└─────────────────────────────────────────┘
```

---

### 4.3 Change Summary by Priority

| Priority | Count | Changes |
|----------|-------|---------|
| 🔴 P0 (Critical) | 12 | D1-D3, D6-D10, D12-D13, D16 |
| 🟠 P1 (Important) | 3 | D4, D14, D17 |
| 🟡 P2 (Nice-to-have) | 3 | D5, D11, D15, D18 |

**Total**: 18 documentation changes + 5 code changes

---

## 5. Risk Assessment & Mitigation

### Risk Matrix

| # | Risk | Probability | Impact | Mitigation | Owner |
|---|------|-------------|--------|------------|-------|
| 1 | Test regression (70+ tests break) | 80% 🔴 | MEDIUM 🟠 | Adapt tests during re-implementation | Dev |
| 2 | RPC rate limit (429 errors) | 40% 🟡 | LOW 🟢 | Throttle 2 req/sec, exponential backoff | Dev |
| 3 | Transaction parsing incomplete (edge cases) | 60% 🟠 | MEDIUM 🟠 | Parser based on Helius model, test with real samples | Architect + Dev |
| 4 | Epic 4 funding sources RPC unfeasible | 30% 🟡 | LOW 🟢 | Research before Epic 4, fallback to Helius opt-in | Architect |
| 5 | Timeline explosion (>2 weeks) | 50% 🟠 | MEDIUM 🟠 | Buffer 30-35h worst case, daily checkpoints | SM |

### Detailed Mitigations

#### **Risk #1: Test Regression** 🔴

**Symptom**: Tests fail after RPC migration

**Prevention**:
- Adapt unit tests incrementally (Story by Story)
- Create RPC mocks matching Helius mock structure
- Clear database before E2E tests (fresh wallets)

**Contingency**:
- Rollback to Helius if >50% tests fail
- Extend timeline +1 week for test fixes

#### **Risk #2: RPC Rate Limit** 🟡

**Symptom**: 429 errors during discovery batch

**Prevention**:
- Throttle to 2 req/sec (safety margin below 4 req/sec limit)
- Exponential backoff: 1s → 2s → 4s on 429
- Batch discovery: Max 10 tokens/day

**Contingency**:
- Fallback to Helius for discovery if RPC consistently fails
- Reduce batch size further

#### **Risk #3: Parsing Incomplete** 🟠

**Symptom**: Wallets missed, false positives

**Prevention**:
- Use Helius Transaction model as parser template
- Test with real Solana transactions (samples)
- Verbose logging for debug

**Contingency**:
- Helius as validation source (compare results)
- Iterative parser improvements

#### **Risk #4: Epic 4 Funding Sources** 🟡

**Symptom**: RPC method too complex/slow

**Prevention**:
- Research RPC approach before Epic 4 starts
- Document alternative: Helius opt-in

**Contingency**:
- Epic 4 Story 4.1 uses Helius opt-in (acceptable)
- V2 scope: Network discovery optional

#### **Risk #5: Timeline Explosion** 🟠

**Symptom**: Epic 3 exceeds 2 weeks

**Prevention**:
- Daily standups, progress tracking
- Checkpoint after each Story (3.1 → 3.2 → 3.3)
- Buffer: 30-35h worst case

**Contingency**:
- Epic 4/5 delayed (acceptable)
- Split work: Documentation parallel to code

---

## 6. Success Criteria

### 6.1 Epic 3 RPC Success ✅

- [ ] All 70+ tests pass (unit + integration + E2E)
- [ ] Wallets discovered via RPC = "smart money" (early profitable buyers, NOT bag holders)
- [ ] Performance metrics identical: win_rate, pnl_total, total_trades
- [ ] Behavioral profiling functional: position_size_style, hold_duration_style
- [ ] Zero Helius API calls during Epic 3 operations
- [ ] No regression in Epic 1-2 functionality

### 6.2 Documentation Update Success ✅

- [ ] Check-implementation-readiness workflow: 🟢 READY (no critical conflicts)
- [ ] PRD, Epics, Architecture, UX all updated (18 changes applied)
- [ ] Developers can implement without ambiguity
- [ ] No conflicts between PRD ↔ Epics ↔ Architecture ↔ UX

### 6.3 Cost-Saving Success ✅

- [ ] Helius API monthly usage < 75K requests (baseline: 125K+)
- [ ] RPC rate limit respected (zero 429 errors)
- [ ] Epic 3 operations 100% free (0 Helius requests)
- [ ] Cost tracking dashboard implemented (Config UI)

### 6.4 Quality Gates

| Gate | Criteria | Go/No-Go |
|------|----------|----------|
| Story 3.1 | 16 tests pass, wallets discovered | Story 3.2 blocked |
| Story 3.2 | Performance metrics calculated | Story 3.3 blocked |
| Story 3.3 | Behavioral metrics calculated | Story 3.6 blocked |
| Story 3.6 | 19 E2E tests pass | Epic 3 "done" |
| Documentation | Check-implementation-readiness 🟢 | Phase 1 approved |

---

## 7. Gaps & Actions Required

### Gap #1: Transaction Parser Spec 🔴 BLOCKER

**What's Missing**: Detailed specification for RPC transaction parser

**Required Before**: Story 3.1 implementation

**Action**:
- [ ] Create tech spec: `transaction_parser.py` design
- [ ] Document edge cases (multi-hop swaps, complex transactions)
- [ ] Provide test samples (real Solana transactions)

**Owner**: Architect agent
**Deadline**: Before Phase 1 starts
**Estimate**: 4-6 hours

---

### Gap #2: Epic 4 Funding Sources Research 🟡 CLARIFICATION

**What's Missing**: RPC method for funding sources unclear

**Required Before**: Epic 4 Story 4.1 start

**Action**:
- [ ] Research: Can RPC extract funding sources via `getSignaturesForAddress` + SOL_TRANSFER parsing?
- [ ] Document method OR fallback to Helius opt-in
- [ ] Update Epic 4 Story 4.1 description

**Owner**: Architect agent
**Deadline**: Before Epic 4 starts
**Estimate**: 3-4 hours

---

### Gap #3: Epic 5 Dual-Mode Config Schema 🟠 CONFIG

**What's Missing**: Database schema for dual-mode configuration

**Required Before**: Epic 5 Story 5.1 implementation

**Action**:
- [ ] Create migration: Add `signal_detection_mode` column to config table
- [ ] Enum: `'rpc_polling'` | `'helius_webhooks'`
- [ ] Defaults: `mode = 'rpc_polling'`, `interval = 10`

**Owner**: Dev agent
**Deadline**: Before Epic 5 starts
**Estimate**: 2-3 hours

---

### Gap #4: E2E Test Data Strategy 🟠 VALIDATION

**What's Missing**: E2E test data refresh strategy

**Required Before**: Story 3.6 validation

**Action**:
- [ ] Decide: Re-generate test data OR use fixed mocks?
- [ ] Create RPC-based fixtures if re-generating
- [ ] Document expected wallet count/metrics

**Owner**: QA/TEA agent
**Deadline**: Before Story 3.6 validation
**Estimate**: 3-4 hours

---

## 8. Next Steps & Routing

### 8.1 Approval Required 🔴 BLOCKER

**Awaiting User Decision**:

1. [ ] **Approve Option D** (RPC Epic 3 + Dual-mode Epic 5)?
2. [ ] **Approve Timeline** (1-2 weeks Epic 3)?
3. [ ] **Approve Documentation Effort** (8-12h)?
4. [ ] **Approve Epic 4 Delay** (until funding sources clarified)?

**Decision Maker**: Christophe (user)

**If Approved** → Proceed to Step 8.2
**If Rejected** → Revise proposal per feedback

---

### 8.2 Phase 1: Documentation Update (IF APPROVED)

**Owner**: Tech Writer agent OR SM agent
**Duration**: 8-12 hours (2-3 days)
**Priority**: 🟠 HIGH (must complete before code work)

**Tasks**:
- [ ] Apply 12 P0 changes (PRD, Epics, Architecture, UX)
- [ ] Apply 3 P1 changes (diagrams, build sequence, status bar)
- [ ] Apply 3 P2 changes (optional, nice-to-have)
- [ ] Run check-implementation-readiness validation

**Deliverables**:
- Updated `docs/prd.md`
- Updated `docs/epics.md`
- Updated `docs/architecture.md`
- Updated `docs/ux-design-specification.md`

**Next**: Parallel to Step 8.3

---

### 8.3 Phase 1: Transaction Parser Spec (IF APPROVED)

**Owner**: Architect agent
**Duration**: 4-6 hours
**Priority**: 🔴 CRITICAL (blocks Story 3.1)

**Tasks**:
- [ ] Design transaction_parser.py interface
- [ ] Document parsing logic (BUY/SELL detection)
- [ ] List edge cases (multi-hop, partial swaps, etc.)
- [ ] Provide test samples (real Solana transactions)

**Deliverables**:
- Tech spec: `docs/tech-spec-transaction-parser.md`

**Next**: Step 8.4

---

### 8.4 Phase 1: Epic 3 RPC Implementation (AFTER 8.2 + 8.3)

**Owner**: Dev agent
**Duration**: 18-26 hours (1-2 weeks)
**Priority**: 🔴 CRITICAL

**Sequence**:
1. [ ] Implement transaction parser (4-6h)
2. [ ] Re-implement Story 3.1 (6-8h)
3. [ ] Re-implement Story 3.2 (4-6h)
4. [ ] Re-implement Story 3.3 (4-6h)
5. [ ] Adapt tests (4-6h)
6. [ ] Validate E2E Story 3.6 (2h)

**Deliverables**:
- `src/walltrack/services/solana/transaction_parser.py` (new)
- 3 core modules re-implemented (discovery, performance, behavioral)
- 70+ tests passing
- Database wallets table cleared

**Validation**: Code review + all tests passing

**Next**: Step 8.5

---

### 8.5 Phase 1: Epic 3 Closure

**Owner**: SM agent
**Duration**: 1 hour
**Priority**: 🟢 CLOSURE

**Tasks**:
- [ ] Update `sprint-status.yaml`: Epic 3 "in-progress" → "done"
- [ ] Document lessons learned (retrospective optional)
- [ ] Measure cost-saving impact (Helius usage before/after)

**Deliverables**:
- Updated sprint-status.yaml
- Cost metrics report

**Next**: Epic 4 unblocked (if funding sources clarified)

---

### 8.6 Phase 2: Epic 5 Dual-Mode (OPTIONAL, FUTURE)

**Owner**: Dev agent
**Duration**: 3-5 days
**Priority**: 🟡 OPTIONAL

**Prerequisites**:
- Epic 3 validated
- Config schema migration complete
- UX wireframe approved

**Tasks**:
- [ ] Implement RPC Polling worker
- [ ] Create Config UI mode selector
- [ ] Helius webhooks opt-in logic
- [ ] Dual-mode tests

**Deliverables**:
- RPC Polling scheduler job
- Config page dual-mode UI
- Helius webhooks conditional activation

**Validation**: E2E tests for both modes

---

## 9. Appendix

### 9.1 Related Documents

- **Trigger Document**: `docs/implementation-readiness-report-2025-12-31.md` (Issue #3 Epic 3 Story 3.1)
- **Sprint Status**: `docs/sprint-artifacts/sprint-status.yaml` (Epic 3 marked "done")
- **Story Files**: `docs/sprint-artifacts/epic-3/3-1-wallet-discovery-from-tokens.md` (CORRECTION NOTICE)

### 9.2 Workflow Context

- **Workflow**: `correct-course` (bmad:bmm:workflows:correct-course)
- **Mode**: Incremental (collaborative refinement)
- **Sections Completed**: 1-6 (Trigger → Epic Impact → Conflicts → Options → Changes → Review)

### 9.3 Change Statistics

**Code Changes**: 5 files (3 re-implemented, 1 new parser, 1 RPC client methods)
**Documentation Changes**: 18 changes (12 P0, 3 P1, 3 P2)
**Tests Affected**: 70+ tests
**Estimated Effort**: 26-38 hours total (18-26h code + 8-12h docs)
**Timeline**: 1-2 weeks for Phase 1 (Epic 3)

### 9.4 Cost-Saving Projection

| Scenario | Helius Req/Month | Cost |
|----------|------------------|------|
| **Before** (Helius Epic 3) | 125K+ | $$$ |
| **After** (RPC Epic 3, no webhooks) | 0 | FREE |
| **After** (RPC Epic 3, webhooks opt-in) | 0-75K | $ |

**Savings**: ~60-100% reduction in API costs

---

## 10. Approval Section

### User Approval

**Approved by**: _____________________ (Christophe)
**Date**: _____________________
**Signature**: _____________________

**Approvals**:
- [ ] Option D (RPC Epic 3 + Dual-mode Epic 5) approved
- [ ] Timeline (1-2 weeks Epic 3) acceptable
- [ ] Documentation effort (8-12h) approved
- [ ] Epic 4 delay (until funding sources clarified) acceptable

**Comments / Adjustments**:
```
[User feedback here]
```

---

**Status**: 🟠 AWAITING APPROVAL
**Next Action**: User review and approval decision
**Document Version**: 1.0
**Generated**: 2025-12-31 by SM Agent (Correct-Course Workflow)
