# Project Context Analysis

### Requirements Overview

**Functional Requirements:**

WallTrack implements a 9-feature intelligent copy-trading pipeline for Solana memecoins:

1. **Watchlist Management (FR-1)**: Manual CRUD for wallet addresses with per-wallet mode toggle (simulation/live) and exit strategy defaults
2. **Real-Time Signal Detection (FR-2)**: Helius webhooks deliver swap notifications from watchlist wallets
3. **Token Safety Analysis (FR-3)**: Automated scoring system (4 checks: liquidity ≥$50K, holder distribution, contract analysis, age ≥24h) with configurable threshold (default 0.60)
4. **Position Creation & Management (FR-4)**: Dual-mode execution (simulation = full pipeline without Jupiter API, live = real swaps via Jupiter)
5. **Price Monitoring (FR-5)**: Jupiter Price API V3 (30-60s polling) for exit strategy triggers with ±1% accuracy requirement, DexScreener fallback
6. **Exit Strategy Execution (FR-6)**: Multiple strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) with priority logic and per-wallet/per-position configuration
7. **Wallet Activity Monitoring (FR-7)**: Helius webhooks monitor source wallet sales for mirror-exit triggers
8. **Performance Tracking & Analytics (FR-8)**: Per-wallet win rate, PnL, signal analytics (all/30d/7d/24h) for data-driven curation
9. **System Configuration & Status (FR-9)**: Centralized config UI for capital, risk parameters, safety thresholds, webhook/circuit breaker status

**Architectural Implications:**
- Event-driven architecture required (webhook-triggered pipeline)
- State machine for position lifecycle (created → monitored → exit triggered → closed)
- Multi-strategy exit logic with priority resolution
- Dual-mode execution pattern (simulation/live) without code duplication
- Real-time data flow orchestration across 3 external APIs

**Non-Functional Requirements:**

Critical NFRs shaping architectural decisions:

| NFR | Requirement | Architectural Impact |
|-----|-------------|---------------------|
| **Performance (NFR-1)** | Webhook→execution < 5s (P95) | Async processing, minimal I/O blocking, optimized data layer queries |
| **Reliability (NFR-2)** | ≥95% uptime, auto-restart on crash | Health checks, circuit breakers, graceful degradation, process supervision |
| **Security (NFR-3)** | Private key encryption, zero exposure in logs/UI | Secure key management, input validation, TLS for DB connections |
| **Data Integrity (NFR-4)** | Atomic position lifecycle, audit trail | Database transactions, event sourcing for audit, data validation |
| **Observability (NFR-5)** | Complete visibility into decisions | Structured logging, metrics, dashboard real-time state, queryable history |
| **Maintainability (NFR-6)** | ≥70% test coverage, clear separation of concerns | Layered architecture, dependency injection, comprehensive test suite |
| **Scalability (NFR-7)** | 10-20 wallets, 50-400 signals/day, burst handling | Async processing, database indexing, rate limiting, webhook queue |

**Scale & Complexity:**

- **Primary domain**: Blockchain/Web3 + Fintech (backend-heavy with operator UI)
- **Complexity level**: HIGH
  - Real-time trading system with sub-5s latency requirements
  - Financial data protection and wallet security
  - Multi-API orchestration with failure handling
  - Cryptocurrency regulations (future productization consideration)
  - Fraud prevention (rug detection, honeypot analysis)
- **Estimated architectural components**: 8-10 major components
  - Webhook receiver & signal processor
  - Token safety analyzer
  - Position manager (state machine)
  - Price monitor (polling worker)
  - Exit strategy executor
  - Jupiter swap client (live mode)
  - Performance analytics engine
  - Configuration service
  - Dashboard UI (Gradio)

### Technical Constraints & Dependencies

**Critical External Dependencies (system cannot function without):**
- **Helius API**: Webhook delivery for signal detection + wallet monitoring (SLA impact: missed signals = missed trades)
- **Jupiter API**: Swap execution + price monitoring (SLA impact: cannot execute live trades or monitor prices if down, simulation unaffected)
- **DexScreener API**: Fallback price monitoring if Jupiter Price API unavailable (SLA impact: degraded price monitoring reliability)
- **Supabase**: PostgreSQL for state persistence (SLA impact: system inoperable without database)

**Technology Stack Constraints:**
- Python 3.11+ (operator's learning path)
- Gradio for UI (rapid iteration requirement)
- Supabase free tier initially (cost constraint, can upgrade to $25/month)
- FastAPI for API endpoints (async support needed)

**Data Volume Constraints:**
- Supabase free tier limits: 500MB storage, 2GB bandwidth/month
- Mitigation: 90-day data retention policy, archive old signals/positions

**Development Constraints:**
- Solo operator (Christophe) learning Python
- Code must be approachable, well-documented, testable
- AI-assisted development (Claude Code) = accessible complex infrastructure

### Cross-Cutting Concerns Identified

**Security:**
- Wallet private key management (encryption at rest, no logs/UI exposure)
- API authentication (Helius/Jupiter keys in env variables)
- Input validation (Solana address format checks)
- Audit trail for all wallet operations
- Rate limiting on API endpoints

**Error Handling & Resilience:**
- External API failure handling (Helius/Jupiter/DexScreener)
- Webhook delivery reliability monitoring (48h timeout alert)
- Circuit breakers (max drawdown 20%, win rate < 40%, 3 consecutive losses)
- Retry logic with exponential backoff
- Graceful degradation (use last known price if API unavailable)

**Logging & Observability:**
- Structured logging for all signals, positions, exits, circuit breaker triggers
- Performance metrics (execution latency, API response times)
- Dashboard real-time state view
- Historical logs queryable for debugging
- Transparency = operator trust

**Configuration Management:**
- Hierarchical configuration: System defaults → per-wallet defaults → per-position overrides
- 30+ configurable parameters (trading, risk management, safety analysis, exit strategies)
- Config persistence in Supabase with JSON backup on every change
- Parameter validation and range checks
- Real-time config changes without restart

**Testing Strategy:**
- Unit tests with mocked external APIs (≥70% coverage target)
- Integration tests for data layer and API clients
- E2E tests with Playwright (separate test run to avoid interference)
- Simulation mode as built-in testing environment

**Data Consistency:**
- Atomic database transactions for position lifecycle
- Event sourcing for audit trail
- PnL calculation reconciliation checks
- Price data staleness monitoring (5-minute threshold)
