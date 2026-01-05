# Epic List

### Epic 1: Data Foundation & UI Framework
Operator can visualize the system structure and interact with mockup data, validating the information architecture before connecting real logic. All 9 database tables migrated with comprehensive mock data, complete Gradio UI (Dashboard, Watchlist, Config tabs) displaying mock data with table + sidebar interactions.

**FRs covered:** Foundation for ALL (FR-1 to FR-9)
**Additional Requirements:** AR-2 (Database Schema), AR-3 (Project Structure), DBR-1 to DBR-10 (All DB patterns & ADRs), UXR-1 to UXR-9 (All UI layouts)

### Epic 2: Smart Money Discovery & Token Safety
Operator can discover smart money wallets via GMGN, add them to watchlist, receive real-time swap signals via Helius webhooks, and automatically filter unsafe tokens before any positions are created.

**FRs covered:** FR-1 (Watchlist Management), FR-2 (Real-Time Signal Detection), FR-3 (Token Safety Analysis)
**Additional Requirements:** AR-5 (External API Client Pattern), DBR-2 (ADR-001 Helius Global Webhook), DBR-7 (Token Safety Cache), DBR-8 (Signal Filtering & Audit Trail)

### Epic 3: Automated Position Management & Exit Strategies
Operator can automatically create positions from safe signals (dual-mode: simulation + live), monitor prices in real-time via Jupiter Price API V3 and DexScreener fallback, and execute sophisticated exit strategies (stop-loss, trailing-stop, scaling-out, mirror-exit) without manual trading.

**FRs covered:** FR-4 (Position Creation & Management), FR-5 (Price Monitoring), FR-6 (Exit Strategy Execution)
**Additional Requirements:** AR-5 (Jupiter + DexScreener clients), DBR-3 (ADR-002 Exit Strategy Override), DBR-9 (Orders Retry Mechanism), DBR-10 (Position PnL Separation)

### Epic 4: Wallet Intelligence & Performance Analytics
Operator can monitor source wallet activity for mirror-exit triggers, track performance per wallet (win rate, PnL, signal counts all/30d/7d/24h), and make data-driven curation decisions (remove underperformers, promote high-performers to live mode).

**FRs covered:** FR-7 (Wallet Activity Monitoring), FR-8 (Performance Tracking & Analytics)
**Additional Requirements:** DBR-4 (ADR-003 Performance Materialized View), DBR-6 (Wallet Discovery & Performance Baseline for fake wallet detection)

### Epic 5: System Configuration & Risk Management
Operator can configure all system parameters (capital, risk limits, safety thresholds, exit strategy templates), monitor system health (webhook status, circuit breakers), and receive automated protection against excessive losses via circuit breakers.

**FRs covered:** FR-9 (System Configuration & Status)
**NFRs covered:** NFR-2 (Reliability via circuit breakers), NFR-5 (Observability via structured logging)
**Additional Requirements:** AR-7 (Structured Logging), AR-8 (Deployment Strategy), DBR-5 (ADR-004 Circuit Breaker Non-Closing)
