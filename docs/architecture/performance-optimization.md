# Performance Optimization

### Database Query Optimization

**Use Indexes (defined in migrations):**
```sql
-- positions table (already in migration)
CREATE INDEX idx_positions_status ON walltrack.positions(status) WHERE status = 'open';
CREATE INDEX idx_positions_last_price_update ON walltrack.positions(last_price_update_at) WHERE status = 'open';
```

**Batch Queries:**
```python
# BAD (N+1 query problem):
for position in positions:
    token = await token_repo.get(position.token_id)

# GOOD (batch prefetch):
positions = await position_repo.get_all_open_with_tokens()  # JOIN in SQL
```

### External API Optimization

**Connection Pooling:**
```python
# src/walltrack/services/base.py
import httpx

class APIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
```

**Caching:**
- Token metadata (TTL 1h, implemented in tokens table)
- Jupiter prices (TTL 30s, in-memory cache)

### Worker Performance

**Async I/O (Non-Blocking):**
```python
# All workers use asyncio for concurrent operations
async def process_batch(signals):
    tasks = [process_signal(s) for s in signals]
    await asyncio.gather(*tasks)  # Process 10 signals concurrently
```

**Queue Size Limits:**
```python
# Prevent memory overflow
self.queue = asyncio.Queue(maxsize=1000)
```

---

### Backup Strategy

**Database:**
- Supabase automatic backups (Pro tier: daily)
- Manual export: `pg_dump walltrack > backup_$(date +%Y%m%d).sql`
- Restore: Supabase dashboard or `pg_restore backup.sql`

**Configuration:**
- `.env` file backup (contains API keys, encryption key)
- Store securely (password manager, encrypted storage)

---
