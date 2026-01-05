# Non-Functional Requirements

### NFR-1: Performance

**Requirement:** System must execute trades within 5 seconds of signal receipt to capture price before significant movement.

**Rationale:** Copy-trading effectiveness depends on execution speed—smart money moves fast, and delays erode profit potential.

**Acceptance Criteria:**
- Webhook → Signal processing → Trade execution < 5 seconds (P95)
- Price monitoring polling: 30-60s intervals (sufficient for position management)
- Dashboard loads < 2 seconds (operator experience)

**Priority:** CRITICAL

---

### NFR-2: Reliability

**Requirement:** System uptime ≥ 95% to ensure 24/7 opportunity capture.

**Rationale:** Memecoin opportunities occur at any time—downtime means missed profitable trades.

**Acceptance Criteria:**
- System restarts automatically on crash
- Health checks monitor critical components (webhooks, API connections, database)
- Alerting for prolonged downtime (>30 minutes)
- Circuit breakers prevent cascade failures

**Priority:** CRITICAL

---

### NFR-3: Security

**Requirement:** Wallet private keys must be securely managed with no exposure in logs or UI.

**Rationale:** Compromise of trading wallet = total capital loss.

**Acceptance Criteria:**
- Private keys stored encrypted at rest (Supabase encryption or environment variables)
- No private key exposure in logs, error messages, or UI
- Jupiter API calls signed securely without key exposure
- Audit trail for all wallet operations

**Priority:** CRITICAL

---

### NFR-4: Data Integrity

**Requirement:** All trade execution, PnL, and performance data must be accurate and auditable.

**Rationale:** Operator trust depends on data accuracy—incorrect performance tracking undermines decision-making.

**Acceptance Criteria:**
- Atomic database transactions for position lifecycle (create → update → close)
- Audit trail for all state changes (signals, positions, exits)
- Data validation on all inputs (wallet addresses, prices, amounts)
- Reconciliation checks for PnL calculations

**Priority:** HIGH

---

### NFR-5: Observability

**Requirement:** Complete visibility into system state and trade decisions for operator trust.

**Rationale:** "Transparency = Trust"—operator must understand every automated decision to build confidence.

**Acceptance Criteria:**
- All signals logged with safety scores and filter decisions
- All positions logged with entry/exit details and PnL
- Circuit breaker triggers logged with reason
- Dashboard provides real-time system state view
- Historical logs queryable for debugging

**Priority:** HIGH

---

### NFR-6: Maintainability

**Requirement:** Codebase must be simple, well-documented, and testable for solo operator maintenance.

**Rationale:** Christophe is learning Python—code must be approachable for ongoing evolution and debugging.

**Acceptance Criteria:**
- Test coverage ≥ 70% (unit + integration + E2E)
- Clear separation of concerns (API clients, data layer, business logic)
- Type hints throughout codebase (Pydantic models)
- README with architecture overview and setup instructions

**Priority:** MEDIUM

---

### NFR-7: Scalability

**Requirement:** System must handle 10-20 watchlist wallets generating 50-400 signals per day.

**Rationale:** MVP target is 5-20 signals/day/wallet × 10 wallets = 50-200 signals/day. System must handle peak load.

**Acceptance Criteria:**
- Webhook processing handles burst of 10 signals within 30 seconds
- Database queries optimized for dashboard load (indexes on wallet_id, timestamp)
- Supabase free tier sufficient for MVP data volumes

**Priority:** MEDIUM

---

### NFR-8: Compliance Readiness (Future)

**Requirement:** System architecture must support future KYC/AML compliance if productized.

**Rationale:** If WallTrack becomes SaaS offering, fintech regulations will apply.

**Acceptance Criteria:**
- User data model extensible for KYC information
- Audit trail already captures required transaction data
- Architecture supports multi-tenancy (future)

**Priority:** LOW (Future consideration)
