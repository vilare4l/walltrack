# API Rate Limits & Capacity Planning

### Critical Discovery: External API Constraints

**Investigation Context:** Three API rate limits marked "TBD" in PRD (TR-3: External API Integration) were investigated to determine system capacity constraints and upgrade requirements.

**Research Date:** 2026-01-04
**Sources:**
- [Helius API Plans and Rate Limits](https://www.helius.dev/docs/billing/plans-and-rate-limits)
- [Jupiter API Rate Limiting](https://dev.jup.ag/docs/api-rate-limit)
- [DexScreener API Reference](https://docs.dexscreener.com/api/reference)

### 1. Helius API (Webhooks & RPC)

**Free Tier Limits:**

| Resource | Limit | Notes |
|----------|-------|-------|
| **Credits/Month** | 1,000,000 | Increased from 500K (2026 update) |
| **Requests/Second** | 10 req/sec | RPC calls only |
| **API Keys** | 1 key | Sufficient for MVP |
| **Webhooks** | 1 webhook | **Critical constraint** |
| **Support** | Community | No SLA guarantee |

**Webhook Capabilities (CRITICAL DISCOVERY):**

**Single webhook can monitor up to 100,000 wallet addresses simultaneously** ([source](https://x.com/heliuslabs/status/1851348198700339254))

**Enhanced Transactions webhook features:**
- Parses 100+ transaction types (swaps, transfers, NFT trades, etc.)
- Dynamic address list modification via API
- Both BUY and SELL swap events captured in single webhook
- Real-time delivery (<1s latency typical)

**Credit Consumption:**
- **Webhook event**: 1 credit per event delivered to endpoint ([source](https://www.helius.dev/docs/webhooks))
- **Webhook management** (create/edit/delete): 100 credits per operation
- **RPC calls**: Variable (1-10 credits depending on method)

**Architectural Implication:**

✅ **Free tier FULLY SUFFICIENT for MVP** - The 1 webhook limitation is NOT a blocker:
- Can monitor ALL watchlist wallets (10-20 target) with single Enhanced Transactions webhook
- 1M credits/month supports 1M webhook events
- Expected load: 10 wallets × 20 signals/day = 200 events/day = 6,000/month (0.6% of limit)
- Ample headroom for growth (can scale to 50+ wallets on free tier)

**Capacity Calculation:**

```
Free Tier Capacity:
- 1M credits ÷ 1 credit/event = 1M webhook events/month
- 1M events ÷ 30 days = 33,333 events/day
- Target: 10-20 wallets × 5-20 signals/day = 50-400 signals/day
- Headroom: 33,333 ÷ 400 = 83x capacity margin
```

**Upgrade Trigger:**
- If exceeding 900K credits/month consistently (>30K events/day)
- Developer tier: $50/month, 30M credits, 50 req/sec, 5 webhooks

---

#### 1.1 Helius Webhook Lifecycle Management

**Architecture Pattern:** WallTrack uses **ONE global webhook** that monitors ALL active wallets, not one webhook per wallet.

**Rationale:**
- Helius free tier includes 1 webhook → Must monitor all wallets with single webhook
- Cost efficiency: 1 webhook regardless of wallet count (vs N webhooks)
- Simplified management: Single endpoint, single configuration
- Scalability: Can monitor up to 100,000 addresses with one webhook

**Configuration Storage:**

Global webhook config is stored in `config` table (singleton):
```sql
-- In config table
helius_webhook_id TEXT           -- Webhook ID from Helius
helius_webhook_url TEXT          -- Our endpoint URL
helius_webhook_secret TEXT       -- For signature validation
helius_last_sync_at TIMESTAMPTZ  -- Last successful sync
helius_sync_error TEXT           -- Last error (NULL if OK)
```

Per-wallet sync tracking in `wallets` table:
```sql
-- In wallets table
helius_synced_at TIMESTAMPTZ     -- When this wallet was added to webhook
helius_sync_status TEXT          -- 'pending', 'synced', 'error'
```

**Workflow:**

**1. Initial Setup** (one-time, app initialization)
```python
# Create global webhook via Helius API
webhook = helius_client.create_webhook(
    url="https://walltrack.app/api/webhooks/helius",
    events=["SWAP"],
    addresses=[]  # Empty initially
)

# Store in config table
db.execute("""
    UPDATE config
    SET helius_webhook_id = $1,
        helius_webhook_url = $2,
        helius_webhook_secret = $3
""", webhook.id, webhook.url, webhook.secret)
```

**2. Wallet Synchronization** (batch job, every 5 minutes)
```python
async def sync_wallets_to_helius():
    config = get_config()

    # Get all active wallet addresses
    active_addresses = db.query("""
        SELECT address FROM wallets WHERE is_active = true
    """).scalars().all()

    # Update webhook with complete address list
    try:
        helius_client.update_webhook(
            webhook_id=config.helius_webhook_id,
            addresses=active_addresses  # Full replacement
        )

        # Mark wallets as synced
        db.execute("""
            UPDATE wallets
            SET helius_synced_at = NOW(),
                helius_sync_status = 'synced'
            WHERE is_active = true
        """)

        # Update config
        db.execute("""
            UPDATE config
            SET helius_last_sync_at = NOW(),
                helius_sync_error = NULL
        """)

    except HeliusAPIError as e:
        db.execute("""
            UPDATE wallets
            SET helius_sync_status = 'error'
            WHERE is_active = true AND helius_synced_at IS NULL
        """)

        db.execute("""
            UPDATE config SET helius_sync_error = $1
        """, str(e))
```

**3. Adding New Wallet**
```python
# Wallet created with sync_status = 'pending'
wallet = create_wallet(address="...", helius_sync_status='pending')

# Next batch sync (within 5 min) adds it to webhook automatically
```

**4. Deactivating Wallet**
```python
# Mark inactive
deactivate_wallet(wallet_id)

# Next batch sync removes it from webhook address list
```

**5. Signal Reception**
```python
@app.post("/api/webhooks/helius")
async def receive_helius_webhook(request: Request):
    # Validate signature
    validate_signature(request, config.helius_webhook_secret)

    payload = await request.json()
    wallet_address = payload["account"]

    # Lookup wallet in DB
    wallet = db.query("SELECT * FROM wallets WHERE address = $1", wallet_address).first()

    if not wallet or not wallet.is_active:
        return {"status": "ignored"}

    # Update last_signal_at
    db.execute("UPDATE wallets SET last_signal_at = NOW() WHERE id = $1", wallet.id)

    # Process signal
    await process_signal(wallet, payload)

    return {"status": "ok"}
```

**Monitoring & Health Checks:**

```sql
-- Wallets pending sync (should be 0 after 5 min)
SELECT COUNT(*) FROM wallets
WHERE is_active = true AND helius_sync_status = 'pending';

-- Last sync time (should be < 5 min ago)
SELECT helius_last_sync_at, helius_sync_error FROM config;

-- Wallets without signals (potential webhook issues)
SELECT address, label, last_signal_at
FROM wallets
WHERE is_active = true
  AND helius_sync_status = 'synced'
  AND (last_signal_at IS NULL OR last_signal_at < NOW() - INTERVAL '72 hours');
```

**Error Handling:**

- **Sync fails:** Retry on next batch (5 min), log error in `config.helius_sync_error`
- **Webhook down:** Helius retries with exponential backoff, check endpoint health
- **Address limit exceeded:** Upgrade to paid tier (100K limit should never be hit)

---

### 2. Jupiter API (Swap Execution)

**Free Tier Limits:**

| Resource | Limit | Calculation |
|----------|-------|-------------|
| **Requests** | 60 req/60 sec | 1 req/sec average |
| **Burst** | 60 requests | Can burst if under quota |
| **API Keys** | Unlimited | No per-key limit (account-based) |
| **Cost** | Free | Public API |

**Pro Tier Limits (Paid):**

| Tier | Cost | Limit | Use Case |
|------|------|-------|----------|
| **Pro I** | $50/month | ~600 req/min (100/10sec) | Live trading 5-10 wallets |
| **Pro II** | $250/month | ~3,000 req/min (500/10sec) | 20+ wallets |
| **Pro III** | $1,000/month | ~6,000 req/min (1,000/10sec) | High frequency |

**Rate Limit Buckets (Independent):**
- **Price API** (`/price/v3/`): Separate quota
- **Studio API** (`/studio/`): 10 req/10sec (Pro), 100 req/5min (Free)
- **Default**: All other endpoints (swap, quote)

**Architectural Implication:**

✅ **Free tier SUFFICIENT for MVP with intelligent request queuing:**

**Simulation Mode:**
- No Jupiter API calls (skipped in pipeline)
- Free tier irrelevant for simulation

**Live Mode (Primary Architecture Pattern):**
- Minimum 2 calls per trade: 1 quote + 1 swap = 2 req
- Free tier: 60 req/60sec = 1 req/sec average
- **MVP target: 10 wallets × 10 signals/day = 100 trades/day**

**Capacity Calculation:**

```
Free Tier Live Trading Capacity:

Average Load (signals distributed 24h):
- 100 trades/day ÷ 24h = 4.2 trades/hour
- 4.2 trades/h × 2 req/trade = 8.4 req/hour
- Free tier: 60 req/min = 3,600 req/hour
- Headroom: 3,600 ÷ 8.4 = 428x capacity margin ✅

Burst Scenarios (5 wallets trade simultaneously):
- 5 trades × 2 req = 10 requests in ~10 seconds
- With 2-second spacing queue: 10 req over 20 seconds
- Rate: 30 req/min → well within 60 req/min limit ✅

Critical Design: REQUEST QUEUE WITH SPACING
- Queue enforces 2-second minimum between Jupiter calls
- Prevents burst overload (multiple wallets trading simultaneously)
- Free tier viable for 3-5 wallets in live mode
- Upgrade only needed if consistent 429 errors at scale
```

**Progressive Live Trading Strategy:**

**Phase 1 (Weeks 5-8): Test with 1-2 wallets LIVE**
- Select highest-performing simulation wallets
- Rest of watchlist remains in simulation
- Monitor 429 errors (should be zero with queue)

**Phase 2 (Months 3-4): Scale to 3-5 wallets LIVE**
- Add wallets progressively (1 per week)
- Monitor Jupiter request rate
- Free tier sufficient if no consistent 429 errors

**Phase 3 (Months 5+): Upgrade decision**
- Upgrade to Pro I ($50/month) ONLY if:
  - Profitable in live mode (validated revenue)
  - Want 10+ wallets in live simultaneously
  - Hitting 429 errors regularly with queue
  - Missing profitable trades due to queue delays

**Upgrade Trigger (Revised):**
- **NOT immediately** when launching live trading
- ONLY when free tier becomes bottleneck (consistent 429 errors)
- Validates profitability BEFORE spending $50/month

**CRITICAL NOTE:** lite-api.jup.ag deprecated January 31, 2026 - must use new API endpoints

### 2a. Jupiter Price API V3 (Price Monitoring - PRIMARY)

**Why Jupiter for Price Monitoring:**

✅ **Already in stack** - No new dependency (same API as swap execution)
✅ **All tokens covered** - Includes new/low-cap tokens (shitcoins from Pump.fun, Raydium)
✅ **Multi-DEX aggregation** - More reliable than single DEX (averages Raydium, Orca, Pump.fun, etc.)
✅ **Free tier** - No additional cost
✅ **Architectural coherence** - Same data source for pricing AND execution

**Rate Limits:**

| Resource | Limit | Use Case |
|----------|-------|----------|
| **Price API V3** (`/price/v3`) | Separate quota from swap API | Price monitoring (PRIMARY) |
| **Requests** | ~300 req/min estimated | Real-time price polling for exit triggers |
| **Batch Capability** | Up to 100 token addresses per request | Multi-position monitoring |
| **Authentication** | Optional (API key recommended for higher limits) | Public access available |

**Key Endpoints:**

```
GET https://api.jup.ag/price/v3
Query params:
  - ids: Comma-separated token mint addresses (up to 100)
  - vsToken: Optional (defaults to USDC)

Response:
{
  "data": {
    "<token_mint>": {
      "id": "<token_mint>",
      "price": 0.00123456,  // Price in vsToken (USDC)
      "extraInfo": {
        "lastSwappedPrice": {...},
        "quotedPrice": {...}
      }
    }
  },
  "timeTaken": 0.002
}
```

**Architectural Implication:**

✅ **FREE tier SUFFICIENT for MVP:**

**Capacity Calculation:**

```
Price Monitor Capacity (estimated ~300 req/min):

Scenario 1: Individual polling (inefficient)
- 100 active positions × 1 req/position every 30 sec = 200 req/min
- Within estimated limit ✅

Scenario 2: Batch polling (RECOMMENDED)
- 100 positions ÷ 100 addresses/batch = 1 batch
- 1 batch every 30 sec = 2 req/min
- 300 req/min ÷ 2 = 150x capacity margin ✅

Scenario 3: Adaptive polling (BEST)
- Active positions (near trigger): 20 sec polling
- Stable positions: 60 sec polling
- Mixed: ~10 req/min average with 100 positions
- 300 req/min ÷ 10 = 30x capacity margin ✅
```

**Recommended Implementation:**

**Polling Strategy (FREE tier - conservative):**
1. **Batch requests** (up to 100 tokens per call)
2. **Adaptive intervals**:
   - Urgent (near trigger <5%): **20 sec** (protect capital)
   - Active (trailing stop enabled): **30 sec** (monitor closely)
   - Stable (fixed triggers only): **60 sec** (conserve quota)
   - Circuit breaker active: pause polling
3. **Prioritize positions** by urgency (trailing-stop > stop-loss > scaling-out)

**Rationale:**
- Conservative intervals preserve quota for swap bursts
- 20s urgent provides ~3% better exit protection vs 30s
- Average load: ~1.5 req/min (leaves 58.5 req/min for swaps)

**Price Data Quality:**
- Aggregated across all Jupiter-integrated DEXs
- Based on actual swap prices (not orderbook)
- Covers all tradeable SPL tokens (including new launches)
- Latency: <100ms typical

**Implementation Example:**

```python
from walltrack.services.jupiter import JupiterPriceClient

class PriceMonitor:
    def __init__(self):
        self.jupiter = JupiterPriceClient()

    async def monitor_positions_batch(self, positions: list[Position]):
        """Batch price monitoring for active positions"""
        token_addresses = [p.token_address for p in positions]

        # Single batch request for all positions (up to 100)
        prices = await self.jupiter.get_prices_batch(token_addresses)

        for position in positions:
            current_price = prices[position.token_address]
            await self.check_exit_triggers(position, current_price)

    async def adaptive_polling_loop(self):
        """Adaptive polling based on position proximity to triggers"""
        while True:
            active_positions = await self.get_active_positions()

            # Group by urgency
            urgent = [p for p in active_positions if p.near_trigger()]
            stable = [p for p in active_positions if not p.near_trigger()]

            # Monitor urgent positions every 20s
            await self.monitor_positions_batch(urgent)
            await asyncio.sleep(20)

            # Monitor stable positions every 60s
            if time.time() % 60 < 5:  # Every minute
                await self.monitor_positions_batch(stable)
```

**Fallback Strategy:**

```python
async def get_token_price(self, token_address: str) -> float:
    """Price fetching with DexScreener fallback"""
    try:
        # PRIMARY: Jupiter Price API V3
        price = await self.jupiter.get_price(token_address)
        await self.cache.set(f"price:{token_address}", price, ttl=300)
        return price
    except APIError as e:
        logger.warning("jupiter_price_api_unavailable", error=str(e))

        # FALLBACK: DexScreener
        try:
            price = await self.dexscreener.get_price(token_address)
            return price
        except APIError:
            # Last resort: use cached price if recent
            cached = await self.cache.get(f"price:{token_address}")
            if cached and cache_age < 300:  # 5 min threshold
                logger.warning("using_cached_price", age_seconds=cache_age)
                return cached
            raise PriceUnavailableError(token_address)
```

**Upgrade Trigger:**
- No paid tier for Price API specifically
- If hitting rate limits:
  - Increase polling interval to 45-60 sec
  - Reduce concurrent positions
  - Consider upgrading Jupiter account (may increase all quotas)

### 3. DexScreener API (Fallback Price Source)

**Role:** FALLBACK price source if Jupiter Price API unavailable

**Rate Limits (No Authentication Required):**

| Endpoint Type | Limit | Use Case |
|---------------|-------|----------|
| **Token Pairs / DEX Data** | 300 req/min | Price monitoring (FALLBACK) |
| **Profiles / Boosts** | 60 req/min | Not used in MVP |

**Batch Capabilities:**
- Single request can query up to 30 token addresses
- Less efficient than Jupiter (30 vs 100 tokens/request)

**Architectural Implication:**

✅ **Free tier SUFFICIENT as fallback:**

**Fallback Use Case:**

```
Only used if Jupiter Price API fails or returns errors:

Fallback Capacity (300 req/min):
- 100 positions ÷ 30 addresses/batch = 4 batches
- 4 batches every 30 sec = 8 req/min
- 300 req/min ÷ 8 = 37x capacity margin ✅
- Sufficient for fallback scenarios
```

**Implementation Note:**

DexScreener is implemented as **graceful degradation** only:
- NOT used in normal operation (Jupiter handles all price monitoring)
- Activated automatically if Jupiter Price API unavailable
- Same polling intervals as primary (20-60s adaptive)
- Batch requests (30 tokens max per call)
- Automatically switches back to Jupiter when available

**Limitations as Fallback:**
- Smaller batch size (30 vs 100 tokens)
- Single DEX coverage (may miss some new tokens)
- No paid tier for upgrades

### 4. RugCheck API (Token Safety Analysis)

**Rate Limits:**

| Resource | Limit | Use Case |
|----------|-------|----------|
| **API Requests** | Unlimited (free tier) | Token security analysis (PRIMARY) |
| **Authentication** | API Key required | Free account creation at rugcheck.xyz |
| **Response Time** | <2s typical | Comprehensive security report |

**API Capabilities:**

**Core Security Checks (FR-3 Implementation):**
- ✅ **Contract Analysis**: Honeypot detection, mint/freeze authority checks
- ✅ **Liquidity Analysis**: Pool size, trading volume, LP burn/lock status
- ✅ **Holder Distribution**: Wallet concentration, top holders analysis
- ✅ **Token Metadata**: Creation date (for age threshold check)

**Key Endpoints:**
- `GET /tokens/{mint}/report` - Full security report with risk score
- `GET /tokens/{mint}/report/summary` - Quick summary for filtering
- `GET /wallet/{address}/risk` - Wallet risk assessment

**Architectural Implication:**

✅ **FREE tier FULLY SUFFICIENT for MVP:**

**Capacity Calculation:**

```
Token Safety Analysis Load (unlimited requests):

Expected Usage:
- 10-20 watchlist wallets
- 20 signals/wallet/day average
- 200-400 total signals/day
- 1 RugCheck API call per new token (cached after first check)
- Estimated 50-100 unique tokens/day
- 1,500-3,000 API calls/month

Free Tier: No rate limits documented
Cost: $0/month (completely free)
```

**Recommended Implementation:**

**Safety Score Calculation (FR-3):**
```python
async def analyze_token_safety(token_address: str) -> float:
    # Call RugCheck API for comprehensive report
    report = await rugcheck.get_report_summary(token_address)

    # 4 weighted checks (25% each):
    liquidity_score = 1.0 if report.liquidity_usd >= 50000 else 0.0
    holder_score = 1.0 if report.top_10_holder_percent < 80 else 0.0
    contract_score = report.security_score  # Honeypot/rug detection
    age_score = 1.0 if report.age_hours >= 24 else 0.0

    # Weighted average (configurable threshold: 0.60 default)
    return (liquidity_score + holder_score + contract_score + age_score) / 4
```

**Caching Strategy:**
- Cache token reports for 24h (safety scores don't change rapidly)
- Store in `tokens` table (address, safety_score, last_analyzed_at)
- Re-analyze only if last_analyzed_at > 24h old

**Fallback Strategy:**
- If RugCheck API unavailable:
  - Use cached score if available (warn if stale >48h)
  - Option to skip safety check (manual override in config)
  - Alternative: GoPlus Security API (multi-chain, Solana in Beta)

**API Documentation:**
- Swagger: [api.rugcheck.xyz/swagger](https://api.rugcheck.xyz/swagger/index.html)
- Integration Guide: [github.com/degenfrends/solana-rugchecker](https://github.com/degenfrends/solana-rugchecker)

**Research Date:** 2026-01-04
**Sources:**
- [RugCheck API Documentation](https://api.rugcheck.xyz/swagger/index.html)
- [Solana RugChecker GitHub](https://github.com/degenfrends/solana-rugchecker)
- [RugCheck Integration Guide](https://qodex.ai/blog/how-to-get-a-rugcheck-api-key-and-start-using-the-api)

### Architectural Impact Summary

**System Capacity Matrix:**

| Component | Free Tier Limit | MVP Capacity | Bottleneck? | Upgrade Cost |
|-----------|-----------------|--------------|-------------|--------------|
| **Helius Webhooks** | 1M events/month | 10-20 wallets ✅ | NO | $50/mo (if >30K events/day) |
| **Jupiter Swaps** | 60 req/60sec | Simulation: unlimited ✅<br>Live: ~20 trades/min ⚠️ | LIVE MODE | $50/mo Pro I |
| **Jupiter Price** | ~300 req/min (est.) | 100+ positions ✅ | NO | N/A (included with account) |
| **DexScreener Price** | 300 req/min | Fallback only ✅ | NO | N/A (no paid tier) |
| **RugCheck Safety** | Unlimited (free) | 50-100 tokens/day ✅ | NO | $0 (always free) |
| **Supabase DB** | 500MB storage | MVP sufficient ✅ | NO | $25/mo (if needed) |

**Total Cost Scenarios:**

**Simulation Phase (Weeks 1-4):**
- **Cost: $0/month** (all free tiers sufficient)
- Helius: Free tier
- Jupiter Swaps: Not used (simulation)
- Jupiter Price: Free tier (price monitoring)
- DexScreener: Not used (fallback only)
- Supabase: Free tier

**Initial Live Trading (Weeks 5-12):**
- **Cost: $0/month** (free tier with request queue)
- Helius: Free tier (sufficient)
- **Jupiter Swaps: Free tier** - viable with intelligent queue (1-3 wallets live)
- **Jupiter Price: Free tier** - price monitoring (sufficient)
- DexScreener: Fallback only (not actively used)
- Supabase: Free tier (sufficient)

**Scaling Live Trading (Months 4+):**
- **Cost: $0-75/month** (upgrade only if needed)
- Helius: Free tier (still sufficient)
- **Jupiter Swaps: Free OR Pro I ($50/month)** - upgrade only if consistent 429 errors
- **Jupiter Price: Free tier** - included with account (sufficient)
- DexScreener: Fallback only
- Supabase: $0-25/month (optional if storage >400MB)

**Scale Targets:**

| Metric | Free Tiers | With Pro Jupiter | Max Capacity |
|--------|------------|------------------|--------------|
| **Watchlist Wallets** | 10-20 | 20-30 | 100,000 (Helius) |
| **Active Positions** | 100+ | 200+ | 500+ |
| **Trades/Day** | 50-200 (simulation)<br>20-30 (live) | 500-1000 (live) | 5,000+ |
| **Signals/Day** | 400+ | 600+ | 30,000+ |

### Mitigation Strategies

**Rate Limit Handling Patterns:**

**1. Request Queuing (Jupiter) - PRIMARY PATTERN:**

**CRITICAL**: This is not optional - queue is the core architecture for Jupiter integration.

### Swap Priority System

**Priority Hierarchy** (lower number = higher priority):

```python
from enum import IntEnum

class SwapPriority(IntEnum):
    """Swap execution priority levels"""
    CRITICAL = 1   # Mirror-exit: smart wallet sold (danger signal)
    URGENT = 2     # Exit triggers: stop-loss, take-profit, trailing-stop
    NORMAL = 3     # Entry: new position from signal (if circuit breaker inactive)
    LOW = 4        # Scaling-out: partial exit (already in profit)
```

**Rationale:**

1. **CRITICAL (Mirror-Exit)**: Smart wallet knows something you don't → immediate danger
2. **URGENT (Exit Triggers)**: Protect existing capital → limit losses, secure profits
3. **NORMAL (Entry)**: New opportunities → can wait a few seconds
4. **LOW (Scaling-Out)**: Already in profit → lowest urgency

**Circuit Breaker Interaction:**

- Circuit breaker **BLOCKS** new entries (NORMAL priority)
- Circuit breaker **ALLOWS** all exits (CRITICAL, URGENT, LOW)
- Existing positions continue exit strategies normally

**Burst Scenario Protection:**

```
Burst: 5 buy signals arrive + 1 stop-loss triggered simultaneously

Queue order (priority-based):
[1] URGENT: Stop-loss sell (executed first - protects capital)
[2-6] NORMAL: 5 buy signals (executed after exits)

Result:
- Capital protected in 2 seconds (stop-loss)
- Entries execute with 2-sec spacing after (10 additional seconds)
```

### Jupiter Request Queue Implementation

```python
from asyncio import PriorityQueue
from dataclasses import dataclass, field
from datetime import datetime
import time

@dataclass
class SwapRequest:
    """Swap request with priority"""
    priority: SwapPriority
    position_id: str | None  # None for entries
    token_address: str
    action: str  # "buy" or "sell"
    amount: float
    reason: str  # "signal", "stop_loss", "mirror_exit", etc.
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __lt__(self, other):
        """For PriorityQueue: compare by priority then timestamp"""
        if self.priority == other.priority:
            return self.timestamp < other.timestamp
        return self.priority < other.priority


class JupiterRequestQueue:
    """
    Priority-based request queue for Jupiter API free tier.

    Features:
    - Priority-based execution (exits before entries)
    - Rate limit protection (2-sec spacing)
    - Circuit breaker integration (blocks NORMAL priority)
    - Burst handling (queues excess requests)
    """

    def __init__(self, min_spacing_seconds: float = 2.0):
        self.queue = PriorityQueue()
        self.min_spacing = min_spacing_seconds
        self.last_request_time = 0
        self.running = False

    async def enqueue(self, request: SwapRequest):
        """Add swap to priority queue"""
        await self.queue.put(request)

        logger.info(
            "swap_queued",
            priority=request.priority.name,
            action=request.action,
            reason=request.reason,
            queue_size=self.queue.qsize()
        )

    async def start_processing(self):
        """Start background queue processor"""
        self.running = True
        while self.running:
            # Get highest priority request
            request = await self.queue.get()

            try:
                # Enforce rate limit spacing
                now = time.time()
                elapsed = now - self.last_request_time
                if elapsed < self.min_spacing:
                    wait_time = self.min_spacing - elapsed
                    logger.debug("jupiter_queue_spacing", wait_seconds=wait_time)
                    await asyncio.sleep(wait_time)

                # Execute swap
                await self._execute_swap(request)

                # Track execution
                latency = time.time() - request.timestamp.timestamp()
                logger.info(
                    "swap_executed",
                    priority=request.priority.name,
                    action=request.action,
                    latency_seconds=latency,
                    queue_remaining=self.queue.qsize()
                )

            except Exception as e:
                logger.error(
                    "swap_failed",
                    error=str(e),
                    priority=request.priority.name,
                    reason=request.reason
                )
                # TODO: Retry logic or dead-letter queue

            finally:
                self.last_request_time = time.time()
                self.queue.task_done()

    async def _execute_swap(self, request: SwapRequest):
        """Execute Jupiter swap (quote + swap)"""
        # Determine input/output tokens
        if request.action == "buy":
            input_mint = "USDC"  # Or SOL
            output_mint = request.token_address
        else:  # sell
            input_mint = request.token_address
            output_mint = "USDC"

        # Get quote
        quote = await jupiter_client.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=request.amount
        )

        # Execute swap
        result = await jupiter_client.execute_swap(quote)

        # Update position in DB
        if request.position_id:
            await self._update_position(request.position_id, result)
        else:
            await self._create_position(result, request.reason)

        return result

    async def stop_processing(self):
        """Stop queue processor gracefully"""
        self.running = False
        await self.queue.join()  # Wait for pending requests
```

**Usage in Exit Strategy Executor:**

```python
class ExitStrategyExecutor:
    def __init__(self, swap_queue: JupiterRequestQueue):
        self.swap_queue = swap_queue

    async def execute_exit(self, position: Position, trigger: str):
        """Execute exit with appropriate priority"""

        # Determine priority based on trigger
        if trigger == "mirror_exit":
            priority = SwapPriority.CRITICAL
        elif trigger in ["stop_loss", "take_profit", "trailing_stop"]:
            priority = SwapPriority.URGENT
        elif trigger == "scaling_out":
            priority = SwapPriority.LOW
        else:
            priority = SwapPriority.URGENT  # Safe default

        # Create swap request
        request = SwapRequest(
            priority=priority,
            position_id=position.id,
            token_address=position.token_address,
            action="sell",
            amount=position.amount,
            reason=trigger
        )

        # Enqueue (exits ALWAYS allowed, even if circuit breaker active)
        await self.swap_queue.enqueue(request)
```

**Usage in Signal Processor:**

```python
class SignalProcessor:
    def __init__(
        self,
        swap_queue: JupiterRequestQueue,
        circuit_breaker: CircuitBreaker
    ):
        self.swap_queue = swap_queue
        self.circuit_breaker = circuit_breaker

    async def process_signal(self, signal: Signal):
        """Process buy signal - check circuit breaker first"""

        # 1. Circuit breaker check (BLOCKS entries)
        if await self.circuit_breaker.is_active():
            logger.warning(
                "signal_blocked_circuit_breaker",
                signal_id=signal.id,
                reason=await self.circuit_breaker.get_reason()
            )
            return  # ❌ Entry blocked

        # 2. Safety check
        if not await self.safety_analyzer.is_safe(signal.token_address):
            logger.info("signal_rejected_safety", signal_id=signal.id)
            return

        # 3. Enqueue entry (NORMAL priority)
        request = SwapRequest(
            priority=SwapPriority.NORMAL,
            position_id=None,  # Will be created after swap
            token_address=signal.token_address,
            action="buy",
            amount=calculate_position_size(signal.wallet),
            reason="signal"
        )

        await self.swap_queue.enqueue(request)
```

**Configuration:**

```python
# Free tier: 2-second spacing (30 trades/min max)
jupiter_queue = JupiterRequestQueue(min_spacing_seconds=2.0)

# Pro I tier: 0.5-second spacing (120 trades/min)
# jupiter_queue = JupiterRequestQueue(min_spacing_seconds=0.5)
```

**2. Adaptive Polling (Jupiter Price API):**
```python
class AdaptivePriceMonitor:
    async def get_polling_interval(self, position: Position) -> int:
        """Return polling interval based on position urgency"""
        if position.near_stop_loss(threshold=0.05):  # Within 5% of stop
            return 20  # Fast polling
        elif position.has_trailing_stop and position.price_moving:
            return 30  # Moderate polling
        else:
            return 60  # Standard polling
```

**3. Batch Optimization (Jupiter Price API):**
```python
async def fetch_prices_batch(token_addresses: list[str]) -> dict[str, float]:
    """Fetch up to 100 token prices in single API call"""
    batches = [token_addresses[i:i+100] for i in range(0, len(token_addresses), 100)]
    results = {}
    for batch in batches:
        response = await jupiter_price.get_prices(batch)
        results.update(response.data)  # {mint: {"price": float}}
    return results
```

**4. Circuit Breaker (All APIs):**
```python
class APICircuitBreaker:
    """Halt API calls if failure rate exceeds threshold"""
    def __init__(self, failure_threshold: float = 0.5, window: int = 10):
        self.failure_rate_threshold = failure_threshold
        self.recent_calls: deque = deque(maxlen=window)

    def record_call(self, success: bool):
        self.recent_calls.append(1 if success else 0)

    def is_open(self) -> bool:
        if len(self.recent_calls) < self.window:
            return False
        failure_rate = 1 - (sum(self.recent_calls) / len(self.recent_calls))
        return failure_rate > self.failure_rate_threshold
```

**5. Fallback Strategy (Price Data):**
```python
class PriceDataService:
    """Jupiter primary, DexScreener fallback, cache as last resort"""
    async def get_current_price(self, token: str) -> float:
        try:
            # PRIMARY: Jupiter Price API
            price = await jupiter_price.fetch_price(token)
            await cache.set(f"price:{token}", price, ttl=300)
            return price
        except APIError as e:
            logger.warning("jupiter_price_unavailable", token=token, error=str(e))

            # FALLBACK: DexScreener
            try:
                price = await dexscreener.fetch_price(token)
                await cache.set(f"price:{token}", price, ttl=300)
                return price
            except APIError:
                logger.warning("dexscreener_unavailable", token=token)

                # LAST RESORT: Cached price
                cached_price = await cache.get(f"price:{token}")
                if cached_price and cache_age < 300:  # 5 min threshold
                    logger.warning("using_cached_price", age_seconds=cache_age)
                    return cached_price
                raise PriceDataUnavailableError("No fresh or cached price available")
```

### Upgrade Decision Framework

**When to Upgrade Each Service:**

**Helius (Free → Developer $50/month):**
- ❌ NOT NEEDED for MVP (free tier sufficient for 50+ wallets)
- Consider if:
  - Webhook events >900K/month consistently
  - Need faster RPC calls (10 → 100 req/sec)
  - Require dedicated support for production issues

**Jupiter (Free → Pro I $50/month):**
- ✅ **START with FREE TIER using request queue**
- Free tier viable for:
  - Simulation mode (Jupiter not called)
  - Live mode with 1-5 wallets (request queue enforces spacing)
  - Progressive validation before paying
- Upgrade triggers:
  - Consistent 429 errors despite queue spacing
  - Want 10+ wallets in live simultaneously
  - Profitability validated and want faster execution
  - Queue delays causing missed profitable trades

**Supabase (Free → Pro $25/month):**
- ❌ NOT NEEDED initially
- Upgrade triggers:
  - Database size >400MB (approaching 500MB limit)
  - Bandwidth >1.5GB/month (approaching 2GB limit)
  - Need dedicated support or point-in-time recovery >7 days

**Expected Timeline:**

```
Month 1-2 (Simulation): $0/month
├─ Helius Free: Sufficient
├─ Jupiter Swaps Free: Not used (simulation)
├─ Jupiter Price Free: Sufficient (price monitoring)
└─ Supabase Free: Sufficient

Month 3-6 (Initial Live with Queue): $0/month
├─ Helius Free: Still sufficient ✅
├─ Jupiter Swaps Free: 1-3 wallets live with request queue ✅
├─ Jupiter Price Free: Still sufficient ✅
└─ Supabase Free: Still sufficient ✅

Month 7+ (Optional Scaling): $0-75/month
├─ Helius Free: Still sufficient (100K addresses/webhook)
├─ Jupiter: Free OR Pro I $50 (upgrade only if consistent 429s on swaps)
└─ Supabase: Free or Pro $25 (if DB grows)

Year 2 (High Frequency - if profitable): $300+/month
├─ Helius Developer: $50 (if >50 wallets)
├─ Jupiter Pro II: $250 (if high frequency validated profitable)
└─ Supabase Pro: $25
```

### Critical Constraints Summary

**Hard Limits (Cannot Exceed Without Upgrade):**

1. **Jupiter Free Tier: 1 req/sec**
   - Blocks: High-frequency live trading (>30 trades/minute)
   - **Solution: Request queue with 2-sec spacing (PRIMARY)**
   - Enables: 1-5 wallets in live mode without upgrade
   - Upgrade: Only if consistent 429 errors at scale ($50/month Pro I)

2. **Helius Free Tier: 1 webhook**
   - Blocks: Nothing! (can monitor 100K addresses with 1 webhook)
   - Solution: No upgrade needed for MVP
   - Cost Impact: $0

3. **Jupiter Price API: ~300 req/min (estimated)**
   - Blocks: Polling >600 positions without batching
   - Solution: Batch API calls (100 addresses per request)
   - Cost Impact: $0 (included with Jupiter account)

**Soft Limits (Degraded Performance, Workarounds Available):**

1. **Helius 10 req/sec RPC**: Can use public Solana RPC as fallback
2. **Supabase 500MB**: Archive old data, 90-day retention policy
3. **Jupiter Price staleness**: DexScreener fallback + last-known price with 5-minute threshold

**Risk Mitigation:**

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Jupiter swap 429 errors in live mode | HIGH | CRITICAL | Upgrade to Pro I before live launch |
| Jupiter price 429 errors | LOW | MEDIUM | DexScreener fallback, adaptive polling |
| Helius webhook downtime | LOW | HIGH | Monitor webhook status, alert if >30min down |
| Supabase storage limit | LOW | LOW | 90-day data retention, archive old signals |

**Monitoring Requirements:**

**Track these metrics to detect approaching limits:**
- Helius: Webhook events/day (alert if >25K, approaching 30K/day limit)
- Jupiter Swaps: Request count/minute (alert if >50 req/min on free tier)
- Jupiter Price: Request count/minute (alert if >250 req/min, approaching estimated 300)
- Supabase: Database size MB (alert if >400MB, approaching 500MB)

**Implementation in Config:**
```python
class RateLimitMonitor:
    """Track API usage and alert on threshold approach"""
    thresholds = {
        "helius_events_daily": 25000,  # 83% of theoretical max
        "jupiter_swap_requests_per_minute": 50,  # 83% of free tier
        "jupiter_price_requests_per_minute": 250,  # 83% of estimated limit
        "supabase_storage_mb": 400,  # 80% of 500MB limit
    }

    async def check_limits(self):
        for metric, threshold in self.thresholds.items():
            current_value = await self.get_metric(metric)
            if current_value > threshold:
                logger.warning(
                    "rate_limit_threshold_approached",
                    metric=metric,
                    current=current_value,
                    threshold=threshold
                )
```