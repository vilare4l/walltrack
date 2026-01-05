# User Journeys

### Primary User: Christophe (System Operator)

**Journey 1: Discovery & Setup (Day 1)**

**Context:** Christophe decides to build WallTrack after researching copy-trading bots and concluding "They work, but I can do better while learning."

**Steps:**
1. Configure system parameters (capital: 300€, risk: 2% per trade)
2. Discover 2-3 promising wallets on GMGN (on-chain discovery tool)
3. Add wallets to watchlist in **simulation mode** via Watchlist Management UI
4. Launch system and wait for first signals

**Emotion:** Mix of excitement and uncertainty—"Will this actually work?"

**Success Criteria:**
- System configured without errors
- Wallets added to watchlist successfully
- Helius webhooks operational (visible in Config page)
- First signals received within 24 hours

---

**Journey 2: Validation Through Simulation (Weeks 2-4)**

**Context:** Daily operator workflow establishes confidence through simulation validation.

**Daily Workflow:**
- **Morning:** Dashboard review—active positions, PnL, watchlist analytics (signals all/30d/7d/24h, win rates)
- **During Day:** Curate watchlist (add/remove wallets based on performance), adjust exit strategies per wallet
- **Evening:** Review daily synthesis (PnL, signals executed, circuit breaker status)

**Confidence-Building Criteria:**
- ✅ 55-60% win rate over 50+ simulated trades (with 3:1 profit ratio = net profitable)
- ✅ System runs 7+ days without crashes
- ✅ Complete understanding of every trade decision (transparency = trust)

**Key Moment:** After 2 weeks of stable simulation: "I understand how this works. Time to test with real capital."

**Success Criteria:**
- Simulation mode operational for 7+ consecutive days
- Performance analytics show 55-60% win rate with 3:1 profit ratio
- All safety checks pass (token safety, signal filtering)
- Operator confident in system behavior

---

**Journey 3: First Live Capital (Week 5)**

**Context:** System already supports live mode (Jupiter API integrated in MVP), but Christophe has been using simulation only. Now he toggles one high-performing wallet to live mode with minimal capital (50€ test).

**First Signal in Live Mode:**
1. Helius webhook triggers: Wallet X swaps into Token Y
2. System evaluates: safety checks pass, creates position
3. Executes REAL entry order via Jupiter API
4. Christophe monitors but doesn't intervene
5. Position tracked with configured exit strategies (stop-loss, scaling-out, mirror-exit)
6. Exit triggers automatically → **First profitable trade: +5€ realized profit**

**The "Aha" Moment:** "It works. Not theoretical, not simulated—real profit from real execution. Now I increase the stakes."

**Emotion:** Validation and confidence-building

**Success Criteria:**
- First live trade executes successfully via Jupiter API
- Position management (entry + exit) works in production
- Profitable outcome validates simulation predictions
- Zero manual intervention required

---

**Journey 4: Long-Term Operation (Months 2+)**

**Context:** Progressive capital increase and system mastery.

**Activities:**
- Increase capital allocation progressively (300€ → 500€ → 1000€+)
- Refine watchlist based on performance data (exclude underperforming wallets)
- Customize exit strategies per wallet based on behavior patterns
- Maintain daily high-level curation without manual trading

**Success Criteria:**
- Sustained 55%+ win rate in live mode (with 3:1 profit ratio)
- System uptime ≥ 95%
- Net profitable over monthly periods (memecoin volatility makes daily targets unrealistic)
- Complete system ownership—skills are permanent

**Future Vision:**
- Multi-chain expansion (Base, Arbitrum) once Solana foundation is mastered
- Potential productization if personally profitable
