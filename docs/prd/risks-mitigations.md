# Risks & Mitigations

### High Risk

**Risk 1: Helius Webhook Reliability**

**Description:** If Helius webhooks fail or deliver signals late, WallTrack misses trades or executes at worse prices.

**Impact:** HIGH - Core signal detection depends on webhook reliability

**Likelihood:** MEDIUM - Third-party API dependencies always carry risk

**Mitigation:**
- Monitor webhook status (last signal timestamp visible in UI)
- Circuit breaker triggers alert if no signals for 48 hours
- Consider backup signal source (direct Solana RPC polling) in V2
- Test webhook delivery during simulation phase before live trading

---

**Risk 2: Jupiter API Execution Failures**

**Description:** Jupiter swap execution fails due to slippage, insufficient liquidity, or API errors.

**Impact:** HIGH - Live trading depends on successful execution

**Likelihood:** MEDIUM - DEX liquidity varies by token

**Mitigation:**
- Implement retry logic with exponential backoff
- Set slippage tolerance appropriately (e.g., 2-5%)
- Log all execution failures with reason codes
- Fall back to simulation mode manually if persistent failures
- Monitor execution success rate in analytics

---

**Risk 3: Token Rug Pulls Despite Safety Checks**

**Description:** Token safety analysis fails to detect sophisticated rug pulls, leading to capital loss.

**Impact:** MEDIUM - Safety scoring reduces but doesn't eliminate risk

**Likelihood:** MEDIUM - Memecoin scams are sophisticated

**Mitigation:**
- Conservative safety threshold (0.60 default, adjustable)
- Stop-loss protection on all positions (-20% default)
- Manual review of safety scores for unfamiliar tokens
- Iterate safety model based on false negatives (V2 improvement)
- Start with small capital in live mode to limit downside

---

**Risk 4: Smart Money Wallet Performance Degradation**

**Description:** Previously profitable wallets become unprofitable (market conditions change, wallet strategy shifts).

**Impact:** MEDIUM - Watchlist quality affects overall profitability

**Likelihood:** HIGH - Wallet performance is dynamic

**Mitigation:**
- Performance tracking with win rate per wallet
- Automatic alerts for wallets dropping below 40% win rate
- Regular watchlist curation (weekly review recommended)
- Simulation mode for new wallets before live promotion
- Data-driven removal of underperforming wallets

### Medium Risk

**Risk 5: Price Monitoring Lag**

**Description:** DexScreener API polling delay causes stop-loss/trailing-stop triggers to execute late.

**Impact:** MEDIUM - Exit strategy effectiveness reduced

**Likelihood:** LOW-MEDIUM - API latency varies

**Mitigation:**
- 30-60s polling frequency (balance API load vs. responsiveness)
- Use last known price if API unavailable temporarily
- Alert if price data stale >5 minutes
- Consider WebSocket price feeds in V2 for real-time updates

---

**Risk 6: System Downtime During Critical Market Events**

**Description:** System crashes or restarts during high-volatility period, missing exit opportunities.

**Impact:** MEDIUM - Could result in missed exits or larger losses

**Likelihood:** LOW - Python/FastAPI reasonably stable

**Mitigation:**
- Auto-restart on crash (process manager)
- Health checks and monitoring
- Circuit breakers prevent cascade failures
- Graceful shutdown handling (close positions before restart if possible)

### Low Risk

**Risk 7: Supabase Free Tier Limits**

**Description:** MVP data volume exceeds Supabase free tier limits (storage, API calls).

**Impact:** LOW - Can upgrade to paid tier if needed

**Likelihood:** LOW - Free tier generous for personal use

**Mitigation:**
- Monitor Supabase usage dashboard
- Implement data retention policy (archive old signals/positions after 90 days)
- Upgrade to paid tier if approaching limits ($25/month acceptable)

---

**Risk 8: Regulatory Compliance (Future)**

**Description:** If productized, WallTrack may require KYC/AML compliance and financial licensing.

**Impact:** LOW (MVP is personal use only)

**Likelihood:** N/A for MVP, HIGH if productized

**Mitigation:**
- Architecture supports multi-tenancy and user data (future-proof)
- Audit trail already captures required transaction data
- Consult legal counsel before any productization
- Focus on personal use in MVP to avoid regulatory complexity
