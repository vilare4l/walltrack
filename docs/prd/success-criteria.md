# Success Criteria

### User Success

**Primary Success Indicator:** Progressive validation from simulation to profitable live trading.

The system succeeds when Christophe (the operator) achieves:

**Simulation Phase (Weeks 1-4):**
- System runs 7+ days without crashes
- Win rate ≥ 55-60% over 50+ simulated trades (profit ratio ≥ 3:1 makes this profitable)
- Complete understanding of every trade decision (transparency = trust)
- Daily synthesis shows consistent performance patterns

**Live Validation (Week 5+):**
- First profitable trade (+5€ minimum) = validation moment "It works!"
- Progressive capital increase as confidence builds (300€ → 500€ → 1000€+)
- Daily synthesis shows sustained profitable execution
- Autonomous 24/7 operation with minimal intervention

**Long-Term Operation (Months 2+):**
- Watchlist refinement based on performance data (exclude underperforming wallets)
- Customized exit strategies per wallet based on behavior patterns
- Daily high-level curation only (no manual trading required)
- Continuous learning and system mastery

**Emotional Success:** "It was worth it" = The profit validates the learning investment in Python, Solana/DeFi, and trading infrastructure.

### Business Success

**Phase 1: Proof of Concept (Months 1-2)**
- Simulation stability: 7+ consecutive days without system crashes
- Trading performance: 55-60% win rate across 50+ simulated trades (with 3:1 profit ratio = net positive)
- Signal generation: 5-20 signals per day per wallet across watchlist
- Complete transparency: Operator understands every automated decision

**Phase 2: Live Capital Validation (Months 3-4)**
- First profitable trade execution: +5€ minimum realized profit
- Progressive capital scaling: 300€ → 500€ → 1000€ as confidence builds
- Sustained win rate: 55%+ in live mode (with profit ratio ≥ 3:1)
- Net profitable over 30-day periods (focus on monthly profitability, not daily volatility)

**Phase 3: Operational Maturity (Months 5+)**
- Profit ratio: ≥ 3:1 (average win / average loss)
- System uptime: ≥ 95% (critical for 24/7 opportunity capture)
- Watchlist optimization: Data-driven curation based on wallet performance
- Skills acquisition: Permanent competence in Solana/DeFi infrastructure

**Long-Term Vision (Year 2+):**
- Capital scaling validated on Solana
- Multi-chain expansion (Base, Arbitrum) once foundation is mastered
- Optional productization (SaaS) if personally profitable and validated

### Technical Success

**System Reliability Metrics:**

| Metric | Target | Why It Matters |
|--------|--------|----------------|
| **System Uptime** | ≥ 95% | Must run 24/7 to catch insider opportunities |
| **Execution Latency** | < 5 seconds | Signal → trade before price moves significantly |
| **Webhook Reliability** | > 99% | Cannot miss insider movements |
| **Daily Signals** | 5-20 per wallet | Enough opportunities without noise/spam |
| **Price Monitoring Accuracy** | ±1% | Accurate stop-loss and trailing-stop triggers |

**Circuit Breakers (Automated Protection):**

| Trigger | Action | Rationale |
|---------|--------|-----------|
| **Drawdown > 20%** | Pause all trading, manual review required | Capital protection threshold |
| **Win rate < 40%** over 50 trades | Halt and recalibrate system | Strategy no longer effective |
| **3 consecutive max-loss trades** | Flag for operator review | Pattern indicates systemic problem |
| **No signals for 48 hours** | System health check required | Potential webhook or API failure |

**Technical Validation Criteria:**

- **Token Safety Pipeline**: All signals pass safety threshold (≥ 0.60 score) before position creation
- **Dual-Mode Execution**: Both simulation and live modes operational from MVP
- **Position Management**: Stop-loss, trailing-stop, scaling-out, and mirror-exit all functional
- **Performance Tracking**: Per-wallet win rate, PnL, and signal analytics operational
- **Wallet Security**: Private key management secure and audited

### Measurable Outcomes

**MVP Completion Criteria (Before Live Trading):**

| Criteria | Threshold | Validation Method |
|----------|-----------|-------------------|
| **Core Features Operational** | All 9 features working | Manual testing + E2E tests |
| **Dashboard Functional** | All pages operational | UI walkthrough |
| **Simulation Stability** | 7 days no crashes | Stability monitoring |
| **Signal Generation** | 5+ signals per day per wallet | Signal logs review |
| **Trading Performance** | 55-60% win rate (simulation) with 3:1 profit ratio | Performance analytics |

**Live Trading Validation:**
- First profitable exit: +5€ realized profit minimum
- Progressive capital test: 50€ → 300€ → 500€ success sequence
- Sustained performance: 55%+ win rate over 30+ live trades (with 3:1 profit ratio)
- Zero manual trading: Full automation validated

**North Star Metric:** Profit generated with zero manual trading intervention—validated first in simulation, then in live mode.
