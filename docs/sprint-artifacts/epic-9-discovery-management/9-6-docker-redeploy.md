# Story 9.6: Docker Rebuild & Redeploy

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: Stories 9.1-9.5

## User Story

**As an** operator,
**I want** to rebuild and redeploy the Docker containers with the new discovery features,
**So that** I can use the discovery management UI and scheduler in production.

## Acceptance Criteria

### AC 1: Database Migrations
**Given** new database tables are needed
**When** containers start
**Then** discovery_runs table is created
**And** discovery_run_wallets table is created
**And** discovery_config table is created
**And** existing data is preserved

### AC 2: API Endpoints Available
**Given** containers are running
**When** I call /api/discovery/* endpoints
**Then** all endpoints respond correctly
**And** authentication works (if enabled)
**And** CORS is configured properly

### AC 3: UI Discovery Tab
**Given** dashboard container is running
**When** I open the dashboard
**Then** Discovery tab is visible
**And** all sections load correctly
**And** API calls work from UI

### AC 4: Scheduler Running
**Given** app container is running
**When** scheduler is enabled
**Then** discovery runs automatically at configured interval
**And** results are stored in database
**And** UI shows run history

### AC 5: Health Check Updated
**Given** health endpoint
**When** I call /health/detailed
**Then** scheduler status is included
**And** last discovery run is shown

## Technical Specifications

### Docker Compose Updates

**docker-compose.yml changes:**
```yaml
services:
  walltrack-app:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      # ... existing env vars ...
      DISCOVERY_SCHEDULER_ENABLED: ${DISCOVERY_SCHEDULER_ENABLED:-true}
      DISCOVERY_SCHEDULE_HOURS: ${DISCOVERY_SCHEDULE_HOURS:-6}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Migration Script

**src/walltrack/data/supabase/migrations/019_discovery_management.sql:**
```sql
-- Discovery runs table
CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',

    trigger_type VARCHAR(20) NOT NULL,
    triggered_by VARCHAR(100),

    min_price_change_pct DECIMAL(5,2),
    min_volume_usd DECIMAL(15,2),
    max_token_age_hours INTEGER,
    early_window_minutes INTEGER,
    min_profit_pct DECIMAL(5,2),
    max_tokens INTEGER,

    tokens_analyzed INTEGER DEFAULT 0,
    new_wallets INTEGER DEFAULT 0,
    updated_wallets INTEGER DEFAULT 0,
    profiled_wallets INTEGER DEFAULT 0,
    duration_seconds DECIMAL(10,2),

    errors JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_started
    ON discovery_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_status
    ON discovery_runs(status);

-- Discovery run wallets link table
CREATE TABLE IF NOT EXISTS discovery_run_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    wallet_address VARCHAR(44) NOT NULL,
    source_token VARCHAR(44) NOT NULL,
    is_new BOOLEAN DEFAULT TRUE,
    initial_score DECIMAL(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drw_run
    ON discovery_run_wallets(run_id);
CREATE INDEX IF NOT EXISTS idx_drw_wallet
    ON discovery_run_wallets(wallet_address);

-- Discovery configuration (single row)
CREATE TABLE IF NOT EXISTS discovery_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    enabled BOOLEAN DEFAULT TRUE,
    schedule_hours INTEGER DEFAULT 6,

    min_price_change_pct DECIMAL(5,2) DEFAULT 100.0,
    min_volume_usd DECIMAL(15,2) DEFAULT 50000.0,
    max_token_age_hours INTEGER DEFAULT 72,
    early_window_minutes INTEGER DEFAULT 30,
    min_profit_pct DECIMAL(5,2) DEFAULT 50.0,
    max_tokens INTEGER DEFAULT 20,
    profile_immediately BOOLEAN DEFAULT TRUE,

    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100),

    CONSTRAINT single_config_row CHECK (id = 1)
);

-- Insert default config if not exists
INSERT INTO discovery_config (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;
```

### Deployment Steps

```bash
# 1. Stop current containers
docker compose down

# 2. Rebuild with no cache (to get new code)
docker compose build --no-cache walltrack-app walltrack-dashboard

# 3. Run database migrations
docker compose run --rm walltrack-app python -m walltrack.data.supabase.migrate

# 4. Start all services
docker compose up -d

# 5. Verify health
curl http://localhost:8080/health/detailed

# 6. Check logs
docker compose logs -f walltrack-app

# 7. Verify UI
# Open http://localhost:7865 and check Discovery tab
```

### Environment Variables

Add to `.env`:
```bash
# Discovery Scheduler
DISCOVERY_SCHEDULER_ENABLED=true
DISCOVERY_SCHEDULE_HOURS=6
```

### Health Check Update

**Update src/walltrack/api/routes/health.py:**
```python
@router.get("/detailed")
async def detailed_health() -> dict:
    """Detailed health check with all components."""
    # ... existing checks ...

    # Add scheduler status
    from walltrack.scheduler.discovery_scheduler import get_discovery_scheduler

    try:
        scheduler = await get_discovery_scheduler()
        result["scheduler"] = {
            "enabled": scheduler.enabled,
            "next_run": scheduler.next_run.isoformat() if scheduler.next_run else None,
            "last_run": scheduler.last_run.isoformat() if scheduler.last_run else None,
        }
    except Exception as e:
        result["scheduler"] = {"error": str(e)}

    return result
```

## Implementation Tasks

- [ ] Create migration file 019_discovery_management.sql
- [ ] Update docker-compose.yml with new env vars
- [ ] Update health check endpoint
- [ ] Add scheduler startup to main.py
- [ ] Test migration on local Supabase
- [ ] Rebuild Docker images
- [ ] Run migrations in container
- [ ] Verify all endpoints work
- [ ] Verify UI loads correctly
- [ ] Verify scheduler runs

## Deployment Checklist

```
Pre-deployment:
[ ] All stories 9.1-9.5 implemented
[ ] Tests pass locally
[ ] Migration tested locally
[ ] .env updated with new vars

Deployment:
[ ] docker compose down
[ ] docker compose build --no-cache
[ ] Run migrations
[ ] docker compose up -d
[ ] Check logs for errors

Post-deployment:
[ ] /health/detailed returns OK
[ ] Discovery tab visible in UI
[ ] Can trigger manual discovery
[ ] Scheduler status shows in UI
[ ] First scheduled run completes
```

## Rollback Plan

If deployment fails:
```bash
# 1. Stop new containers
docker compose down

# 2. Revert to previous image (if tagged)
docker compose up -d --no-build

# 3. Or rebuild from previous commit
git checkout HEAD~1
docker compose build
docker compose up -d
```

## Definition of Done

- [ ] All migrations applied successfully
- [ ] Containers start without errors
- [ ] API endpoints respond correctly
- [ ] UI Discovery tab works
- [ ] Scheduler runs on schedule
- [ ] Health check includes scheduler
- [ ] No regression in existing features

## File List

### New Files
- `src/walltrack/data/supabase/migrations/019_discovery_management.sql`

### Modified Files
- `docker-compose.yml` - Add env vars
- `docker-compose.override.yml` - Update if needed
- `.env.example` - Document new vars
- `src/walltrack/api/routes/health.py` - Add scheduler status
- `src/walltrack/main.py` - Start scheduler on startup
