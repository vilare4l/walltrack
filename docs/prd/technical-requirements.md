# Technical Requirements

### TR-1: Technology Stack

**Backend:**
- Python 3.11+ with type hints
- FastAPI for API endpoints
- Pydantic v2 for data validation
- httpx for async HTTP clients

**Data Layer:**
- Supabase (PostgreSQL) for application data (config, tokens, positions, wallets)
- SQL migrations in `src/walltrack/data/supabase/migrations/`

**Blockchain Integration:**
- Helius API for Solana webhooks (swap notifications, wallet monitoring)
- Jupiter API for decentralized swap execution (live mode)
- Solana Web3.py for wallet operations

**Price Data:**
- DexScreener API for real-time token price monitoring

**UI:**
- Gradio for rapid operator interface development
- Pages: Dashboard, Watchlist, Config

**Testing:**
- Pytest for unit + integration tests
- Playwright for E2E UI tests (separate from other tests)

---

### TR-2: Database Schema

**Tables Required (MVP):**

1. **config**: System configuration (capital, risk %, safety threshold)
2. **wallets**: Watchlist wallets (address, mode, exit_strategy_default)
3. **tokens**: Token metadata cache (address, safety_score, last_analyzed)
4. **signals**: Raw signals from Helius (wallet_id, token, timestamp, filtered_reason)
5. **positions**: Open/closed positions (wallet_id, token, entry_price, exit_price, pnl, mode)
6. **performance**: Aggregated wallet performance (wallet_id, win_rate, total_pnl, signal_counts)

**Migration Strategy:**
- All table creation via SQL migration files
- Migrations numbered sequentially (001_config_table.sql, 002_wallets_table.sql, etc.)
- Rollback scripts included as comments in each migration

---

### TR-3: External API Integration

**Helius API:**
- Webhook configuration for swap events
- Rate limits: TBD (check Helius free tier)
- Authentication: API key in environment variable

**Jupiter API:**
- Swap execution endpoint
- Quote endpoint for price estimation
- Rate limits: TBD (check Jupiter limits)
- Authentication: None required (public API)

**DexScreener API:**
- Token price endpoint
- Polling frequency: 30-60s per active position
- Rate limits: TBD (check DexScreener limits)
- Authentication: None required (public API)

---

### TR-4: Testing Strategy

**Unit Tests:**
- Test coverage for business logic (signal filtering, safety scoring, exit strategy logic)
- Mocked external APIs (Helius, Jupiter, DexScreener)
- Target: ≥ 70% coverage

**Integration Tests:**
- Test data layer (Supabase operations)
- Test API client integrations with mocked responses
- Test end-to-end pipelines (signal → position → exit) in simulation mode

**E2E Tests (Playwright):**
- UI workflows (add wallet, view dashboard, change config)
- Run separately from unit/integration tests (different test command)

**Testing Commands:**
```bash
# Unit + Integration (fast, ~40s)
uv run pytest tests/unit tests/integration -v

# E2E Playwright (separate, opens browser)
uv run pytest tests/e2e -v
```

---

### TR-5: Deployment & Operations

**Development:**
- Local development with Supabase local instance or cloud free tier
- Environment variables for API keys (.env file, never committed)

**Production:**
- Single server deployment (personal use, not multi-tenant)
- Process manager for auto-restart (systemd or supervisor)
- Logs to file with rotation (max 100MB, keep 7 days)

**Monitoring:**
- Health check endpoint (FastAPI /health)
- Circuit breaker status exposed via API
- Alert on prolonged downtime (email or Telegram bot - future)

---

### TR-6: Security Measures

**Wallet Security:**
- Private key in environment variable or encrypted file (never in code/database)
- No private key logging or UI exposure
- Use Solana Keypair library for secure key management

**API Security:**
- Helius/Jupiter API keys in environment variables
- Rate limiting on API endpoints (prevent abuse)
- Input validation on all wallet addresses (Solana address format check)

**Data Security:**
- Supabase RLS policies (if using cloud Supabase)
- Database connection over TLS
- No sensitive data in logs (mask wallet addresses in non-critical logs)
