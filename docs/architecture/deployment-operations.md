# Deployment & Operations

### Local Development Setup

```bash
# 1. Clone repo
git clone <repo_url>
cd walltrack

# 2. Install dependencies (uv)
uv sync

# 3. Set environment variables
cp .env.example .env
# Edit .env with API keys

# 4. Run migrations
uv run python scripts/run_migrations.py

# 5. Start application
uv run uvicorn walltrack.main:app --reload --port 8000

# 6. Start Gradio dashboard (separate terminal)
uv run python walltrack/ui/app.py
```

### Environment Variables

```bash
# .env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# External APIs
HELIUS_API_KEY=your-helius-key
JUPITER_API_KEY=your-jupiter-key  # Optional (for Pro tier)
RUGCHECK_API_KEY=your-rugcheck-key  # Optional

# System
LOG_LEVEL=INFO
ENVIRONMENT=development  # or production

# Solana
WALLET_PRIVATE_KEY=<encrypted_or_env_var>  # NEVER commit to git
```

### Production Deployment (Future)

**Hosting Options:**
- **Phase 1 (MVP)**: Local machine (Windows, always-on)
- **Phase 2**: VPS (DigitalOcean $12/month, Ubuntu 22.04)
- **Phase 3**: Docker container on VPS

**Process Management:**
- **Local**: Manual start (`uv run uvicorn ...`)
- **VPS**: systemd service or PM2

**Database Backup:**
- Supabase automatic backups (Pro tier: daily)
- Manual export: `pg_dump walltrack > backup_$(date +%Y%m%d).sql`

### Monitoring & Alerts (Future)

**Uptime Monitoring:**
- Health check endpoint: `GET /api/v1/health`
- External ping: UptimeRobot (free tier, 5min intervals)

**Alert Channels:**
- Email (critical errors only)
- Gradio UI banner (warnings + errors)

**Alert Triggers:**
- Circuit breaker activated (immediate)
- Helius webhook down >30min (immediate)
- Jupiter API 429 errors >10/min (immediate)
- Supabase storage >400MB (daily check)

---
