# Component Architecture

### System Components Overview

WallTrack is composed of 8 main components orchestrated through async workers and FastAPI endpoints:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Gradio UI (Dashboard)                   │
│  - Watchlist management - Config - Positions - Performance      │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼────────────────────────────────────────────┐
│                      FastAPI Application                        │
│  - REST API endpoints - Webhook receiver - Health checks        │
└─────┬──────────┬──────────┬──────────┬──────────┬──────────────┘
      │          │          │          │          │
      ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ ┌──────────────┐
│ Signal   │ │ Token   │ │Position │ │ Price  │ │ Performance  │
│Processor │ │Analyzer │ │ Manager │ │Monitor │ │  Aggregator  │
│ Worker   │ │ Worker  │ │ Worker  │ │ Worker │ │   Worker     │
└────┬─────┘ └────┬────┘ └────┬────┘ └───┬────┘ └──────┬───────┘
     │            │           │          │             │
     └────────────┴───────────┴──────────┴─────────────┘
                          │
                 ┌────────▼─────────┐
                 │  Data Layer      │
                 │ (Supabase PG)    │
                 └──────────────────┘

External APIs:
- Helius (Webhooks + RPC)
- Jupiter (Price + Swap)
- DexScreener (Fallback Price)
- RugCheck (Token Safety)
```

### 1. FastAPI Application (Core Server)

**Responsibilities:**
- REST API endpoints (CRUD wallets, positions, config)
- Helius webhook receiver (`POST /webhooks/helius`)
- Health checks and status endpoints
- Worker lifecycle management

**Key Endpoints:**
```python
# Watchlist Management
POST   /api/v1/wallets              # Add wallet to watchlist
GET    /api/v1/wallets              # List wallets
PUT    /api/v1/wallets/{id}         # Update wallet config
DELETE /api/v1/wallets/{id}         # Remove wallet

# Positions & Orders
GET    /api/v1/positions            # List positions (open/closed)
GET    /api/v1/positions/{id}       # Position details
POST   /api/v1/positions/{id}/exit  # Manual exit

# Config & Status
GET    /api/v1/config               # System config
PUT    /api/v1/config               # Update config
GET    /api/v1/health               # Health check
GET    /api/v1/status               # Workers status

# Webhooks
POST   /webhooks/helius             # Helius webhook receiver
```

**Startup Sequence:**
```python
# src/walltrack/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("starting_walltrack_application")

    # 1. Initialize database connections
    await db.connect()

    # 2. Load config from database
    config = await config_service.load()

    # 3. Start background workers
    await workers.start_all([
        signal_processor,
        token_analyzer,
        position_manager,
        price_monitor,
        performance_aggregator
    ])

    # 4. Sync Helius webhook
    await helius_service.sync_webhook_addresses()

    logger.info("walltrack_ready")

    yield

    # Shutdown
    logger.info("shutting_down_walltrack")
    await workers.stop_all()
    await db.disconnect()

app = FastAPI(lifespan=lifespan)
```

### 2. Signal Processor Worker

**Trigger:** New signal inserted in database (via Helius webhook)
**Frequency:** Event-driven (processes unprocessed signals)
**Responsibility:** Transform raw Helius webhook events into actionable signals

**Processing Pipeline:**
```python
class SignalProcessorWorker:
    """Process incoming signals from Helius webhooks"""

    async def run(self):
        while True:
            # Fetch unprocessed signals
            signals = await db.query(
                "SELECT * FROM walltrack.signals WHERE processed = false ORDER BY created_at LIMIT 10"
            )

            for signal in signals:
                try:
                    # 1. Validate signal (is wallet still active?)
                    wallet = await wallet_repo.get_by_address(signal.source_wallet)
                    if not wallet.is_active:
                        await signal_repo.mark_processed(signal.id, status="ignored_inactive_wallet")
                        continue

                    # 2. Enqueue token safety analysis
                    await token_analyzer.enqueue(
                        token_address=signal.token_out,
                        priority="high" if signal.amount_usd > 1000 else "normal"
                    )

                    # 3. Mark signal as processed
                    await signal_repo.mark_processed(signal.id, status="analyzed")

                    logger.info(
                        "signal_processed",
                        signal_id=signal.id,
                        wallet=wallet.label,
                        token=signal.token_out[:8]
                    )

                except Exception as e:
                    logger.error("signal_processing_failed", signal_id=signal.id, error=str(e))
                    await signal_repo.mark_processed(signal.id, status="error")

            await asyncio.sleep(5)  # Poll every 5 seconds
```

### 3. Token Analyzer Worker

**Trigger:** Token enqueued for analysis (from signal processor)
**Frequency:** Event-driven (processes queue)
**Responsibility:** Fetch token metadata and run safety checks

**Analysis Pipeline:**
```python
class TokenAnalyzerWorker:
    """Analyze tokens for safety (RugCheck + DexScreener)"""

    def __init__(self):
        self.queue = asyncio.Queue()

    async def enqueue(self, token_address: str, priority: str = "normal"):
        await self.queue.put((priority, token_address))

    async def run(self):
        while True:
            priority, token_address = await self.queue.get()

            try:
                # Check if token already cached (TTL 1h)
                token = await token_repo.get_by_address(token_address)
                if token and (datetime.now() - token.last_analyzed_at) < timedelta(hours=1):
                    logger.debug("token_cache_hit", token=token_address[:8])
                    continue

                # 1. RugCheck analysis
                rug_data = await rugcheck_client.analyze(token_address)

                # 2. DexScreener metadata
                dex_data = await dexscreener_client.get_token(token_address)

                # 3. Calculate safety score
                score = self._calculate_safety_score(rug_data, dex_data)

                # 4. Update token cache
                await token_repo.upsert({
                    "address": token_address,
                    "symbol": dex_data.get("symbol"),
                    "name": dex_data.get("name"),
                    "liquidity_usd": dex_data.get("liquidity", {}).get("usd"),
                    "safety_score": score,
                    "is_honeypot": rug_data.get("isHoneypot", False),
                    "has_mint_authority": rug_data.get("hasMintAuthority", False),
                    "holder_count": rug_data.get("holderCount"),
                    "age_hours": self._calculate_age_hours(dex_data),
                    "last_analyzed_at": datetime.now()
                })

                logger.info(
                    "token_analyzed",
                    token=token_address[:8],
                    score=score,
                    safe=score >= 0.60
                )

            except Exception as e:
                logger.error("token_analysis_failed", token=token_address[:8], error=str(e))

            finally:
                self.queue.task_done()
```

### 4. Position Manager Worker

**Trigger:** New signal with safe token + wallet in live mode
**Frequency:** Event-driven
**Responsibility:** Create positions and manage lifecycle (entry → exit)

**Position Lifecycle:**
```python
class PositionManagerWorker:
    """Manage position lifecycle (creation + exit detection)"""

    async def run(self):
        while True:
            # 1. Check for signals ready to create positions
            await self._create_positions_from_signals()

            # 2. Monitor open positions for exit triggers
            await self._check_exit_triggers()

            await asyncio.sleep(10)

    async def _create_positions_from_signals(self):
        """Create positions from processed signals with safe tokens"""
        signals = await db.query("""
            SELECT s.*, t.safety_score, w.mode, w.capital_allocation_percent
            FROM walltrack.signals s
            JOIN walltrack.tokens t ON s.token_out = t.address
            JOIN walltrack.wallets w ON s.source_wallet = w.address
            WHERE s.processed = true
              AND s.position_created = false
              AND t.safety_score >= (SELECT token_safety_threshold FROM walltrack.config)
              AND w.is_active = true
        """)

        for signal in signals:
            try:
                # Calculate position size
                config = await config_service.get()
                position_size_usd = (
                    config.total_capital_usd *
                    signal.wallet.capital_allocation_percent / 100
                )

                # Create position
                position = await position_repo.create({
                    "wallet_id": signal.wallet_id,
                    "token_id": signal.token_id,
                    "signal_id": signal.id,
                    "mode": signal.wallet.mode,  # simulation or live
                    "entry_price": signal.token_out_price,
                    "entry_amount": position_size_usd / signal.token_out_price,
                    "entry_value_usd": position_size_usd,
                    "exit_strategy_id": signal.wallet.default_exit_strategy_id,
                    "status": "open"
                })

                # Execute entry order (if live mode)
                if signal.wallet.mode == "live":
                    await jupiter_client.execute_buy(
                        token_address=signal.token_out,
                        amount_usd=position_size_usd
                    )

                # Mark signal as processed
                await signal_repo.update(signal.id, {"position_created": true})

                logger.info(
                    "position_created",
                    position_id=position.id,
                    mode=signal.wallet.mode,
                    size_usd=position_size_usd
                )

            except Exception as e:
                logger.error("position_creation_failed", signal_id=signal.id, error=str(e))

    async def _check_exit_triggers(self):
        """Check if open positions should exit (strategy triggers)"""
        positions = await position_repo.get_all_open()

        for position in positions:
            try:
                strategy = await exit_strategy_repo.get(position.exit_strategy_id)

                # Merge strategy with position override
                config = {**strategy.dict(), **(position.exit_strategy_override or {})}

                # Check exit conditions
                should_exit, reason = self._evaluate_exit_strategy(position, config)

                if should_exit:
                    await self._execute_exit(position, reason)

            except Exception as e:
                logger.error("exit_check_failed", position_id=position.id, error=str(e))

    def _evaluate_exit_strategy(self, position, config):
        """Evaluate if position should exit based on strategy"""
        # Stop-loss
        if config.get("stop_loss_percent"):
            if position.current_pnl_percent <= -config["stop_loss_percent"]:
                return True, "stop_loss"

        # Trailing stop
        if config.get("trailing_stop_percent"):
            if position.peak_price:
                drawdown_from_peak = (
                    (position.current_price - position.peak_price) / position.peak_price * 100
                )
                if drawdown_from_peak <= -config["trailing_stop_percent"]:
                    return True, "trailing_stop"

        # Scaling out (partial exits at profit levels)
        if config.get("scaling_levels"):
            for level in config["scaling_levels"]:
                if position.current_pnl_percent >= level["profit_percent"]:
                    # Check if this level already executed
                    if not self._is_level_executed(position, level):
                        return True, f"scaling_out_{level['profit_percent']}%"

        return False, None
```

### 5. Price Monitor Worker

**Trigger:** Scheduled (every 30-60s)
**Frequency:** Polling
**Responsibility:** Update current prices for all open positions

**Price Update Pipeline:**
```python
class PriceMonitorWorker:
    """Poll Jupiter Price API to update position prices"""

    async def run(self):
        while True:
            try:
                # Fetch all open positions
                positions = await position_repo.get_all_open()

                if not positions:
                    await asyncio.sleep(60)
                    continue

                # Batch price requests (100 tokens per request)
                token_addresses = list(set(p.token.address for p in positions))

                for batch in self._batch(token_addresses, size=100):
                    try:
                        # Jupiter Price API V3 (batch request)
                        prices = await jupiter_price_client.get_prices(batch)

                        # Update positions
                        for position in positions:
                            if position.token.address in prices:
                                new_price = prices[position.token.address]

                                await position_repo.update_price(
                                    position_id=position.id,
                                    current_price=new_price,
                                    peak_price=max(position.peak_price or 0, new_price)
                                )

                        logger.debug(
                            "prices_updated",
                            count=len(batch),
                            positions_affected=len(positions)
                        )

                    except Exception as e:
                        logger.error("price_batch_update_failed", error=str(e))
                        # Fallback to DexScreener for critical positions
                        await self._fallback_price_update(positions)

                # Wait before next poll
                await asyncio.sleep(30)  # 30s polling interval

            except Exception as e:
                logger.error("price_monitor_worker_failed", error=str(e))
                await asyncio.sleep(60)
```

### 6. Performance Aggregator Worker

**Trigger:** Scheduled (daily at 00:00 UTC)
**Frequency:** Batch (daily)
**Responsibility:** Calculate wallet performance metrics (win rate, PnL, streaks)

**Aggregation Logic:**
```python
class PerformanceAggregatorWorker:
    """Daily batch job to recalculate wallet performance metrics"""

    async def run(self):
        while True:
            # Wait until 00:00 UTC
            await self._wait_until_midnight_utc()

            try:
                wallets = await wallet_repo.get_all_active()

                for wallet in wallets:
                    # Calculate metrics
                    metrics = await self._calculate_wallet_metrics(wallet.id)

                    # Upsert performance record
                    await performance_repo.upsert({
                        "wallet_id": wallet.id,
                        "total_positions": metrics["total_positions"],
                        "winning_positions": metrics["winning_positions"],
                        "losing_positions": metrics["losing_positions"],
                        "win_rate": metrics["win_rate"],
                        "total_pnl_usd": metrics["total_pnl_usd"],
                        "signal_count_30d": metrics["signal_count_30d"],
                        "positions_30d": metrics["positions_30d"],
                        "current_win_streak": metrics["current_win_streak"],
                        "last_calculated_at": datetime.now()
                    })

                    logger.info(
                        "wallet_performance_updated",
                        wallet=wallet.label,
                        win_rate=metrics["win_rate"],
                        total_pnl=metrics["total_pnl_usd"]
                    )

            except Exception as e:
                logger.error("performance_aggregation_failed", error=str(e))
```

---
