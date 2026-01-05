# Observability & Monitoring

### Logging Strategy

**Format:** Structured JSON logs (compatible with CloudWatch, Datadog, etc.)

**Pattern:** Consistent key-value pairs

```python
# src/walltrack/core/logging.py
import structlog

logger = structlog.get_logger()

# Good examples (from Implementation Patterns):
logger.info(
    "signal_received",
    wallet=wallet.label,
    token=token_address[:8],
    amount_usd=signal.amount_usd
)

logger.error(
    "swap_failed",
    error=str(e),
    token=token_address[:8],
    priority=request.priority.name
)

logger.warning(
    "rate_limit_threshold_approached",
    metric="helius_events_daily",
    current=25000,
    threshold=30000
)
```

**Log Levels:**
- **DEBUG**: Development only (price updates, cache hits)
- **INFO**: Normal operations (signals processed, positions created)
- **WARNING**: Degraded state (API fallback, approaching rate limits)
- **ERROR**: Failures requiring attention (swap failed, webhook down)

### Metrics to Track

**System Health:**
- Webhook uptime (alerts if >30min down)
- Worker heartbeats (each worker reports alive every 60s)
- Database connection pool (active/idle connections)

**Business Metrics:**
- Signals/day per wallet
- Positions created/day (simulation vs live)
- Win rate (overall + per wallet)
- Total PnL USD

**Performance Metrics:**
- Webhook latency (Helius event → signal processed)
- Position creation latency (signal → position open)
- Price update latency (Jupiter API response time)

**Rate Limit Metrics:**
- Helius events/day (alert at 25K, hard limit 30K)
- Jupiter swap requests/minute (alert at 50, limit 60)
- Jupiter price requests/minute (alert at 250, estimated limit 300)
- Supabase storage MB (alert at 400MB, limit 500MB)

### Dashboard Requirements

**Gradio UI Tabs:**
1. **Overview**: Current positions, total PnL, open orders
2. **Watchlist**: Wallet management + per-wallet performance
3. **Signals**: Recent signals (all/30d/7d/24h) with processing status
4. **Config**: System configuration + API status
5. **Health**: Worker status, API health checks, rate limit usage

**Real-Time Updates:**
- WebSocket for live price updates (every 30s)
- Auto-refresh position table
- Alert banner for circuit breaker activation

---
