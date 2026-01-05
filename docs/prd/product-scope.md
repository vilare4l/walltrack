# Product Scope

### MVP - Minimum Viable Product

**Core Features (All 9 support BOTH simulation and live modes):**

| # | Feature | Description | Success Validation |
|---|---------|-------------|-------------------|
| 1 | **Watchlist Management** | Manual CRUD for wallet addresses | UI shows watchlist with status indicators |
| 2 | **Helius Webhooks** | Real-time swap notifications | Webhook status visible in Config page |
| 3 | **Token Safety Analysis** | Rug/honeypot detection scoring | Safety scores logged and displayed |
| 4 | **Signal Filtering** | Filter by safety threshold | Only safe signals proceed to positions |
| 5 | **Position Creation** | Simulated positions from signals | Positions visible in Dashboard |
| 6 | **Price Monitoring** | Track prices for exit triggers | Price updates logged (DexScreener API) |
| 7 | **Wallet Activity Monitoring** | Monitor source wallet sales | Mirror-exit signals detected via Helius |
| 8 | **Order Execution (Dual Mode)** | Entry/exit with custom strategies | Simulation/Live toggle per wallet |
| 9 | **Performance Tracking** | Win rate, PnL per wallet | Analytics visible per wallet |

**Technical Stack:**
- **Backend**: Python 3.11+, FastAPI
- **Data Layer**: Supabase (PostgreSQL) for config, tokens, positions
- **Blockchain**: Solana (Helius webhooks, Jupiter API)
- **Price Data**: DexScreener API (30-60s polling)
- **UI**: Gradio (rapid iteration, operator-friendly)
- **Testing**: Pytest (unit + integration + E2E with Playwright)

**Token Safety Model (Simplified for MVP):**

| Check | Weight | Purpose |
|-------|--------|---------|
| **Liquidity Check** | 25% | Avoid low-liquidity rugs (min $50K) |
| **Holder Distribution** | 25% | Detect centralized ownership (top 10 < 80%) |
| **Contract Analysis** | 25% | Identify honeypot patterns |
| **Age Threshold** | 25% | Filter brand new tokens (min 24h age) |

**Safety Score = Weighted average ≥ 0.60 → Safe to trade**

**Exit Strategy Customization:**

| Strategy Type | Description | Example Configuration |
|---------------|-------------|----------------------|
| **Scaling Out (Paliers)** | Take profit at predefined levels | 50% @ 2x, 25% @ 3x, 25% hold |
| **Mirror Wallet Exit** | Sell when original wallet sells | If Liberty sells Token X → WallTrack sells |
| **Stop Loss** | Exit if price drops below threshold | -20% from entry (capital protection) |
| **Trailing Stop** | Follow price up, sell on reversal | Trail 15% below peak price |

**Priority Logic:**
1. Stop loss triggers first (capital protection)
2. Mirror wallet exit overrides scaling if source wallet sells
3. Trailing stop activates after profit threshold
4. Scaling out executes at predefined levels

**Execution Modes:**

| Mode | Description | Technical Implementation |
|------|-------------|--------------------------|
| **Simulation** | Full pipeline, no real execution | All features active, Jupiter API call skipped |
| **Live** | Real execution via Jupiter API | Full pipeline + Jupiter swap execution |

**Per-Wallet Mode Selection:** Operator can set each wallet to simulation or live independently, enabling progressive validation (simulation → small live test → full live).

### Growth Features (Post-MVP)

**V2 — Enhanced Intelligence (Months 6-12):**

**Optional if manual curation proves insufficient:**
- Token discovery automation (if GMGN manual approach becomes bottleneck)
- Automated wallet profiling with ML-based win rate prediction
- Feedback loop for automatic wallet score adjustment based on performance
- Advanced exit strategy optimization per wallet behavior patterns
- Portfolio rebalancing across multiple positions

**Enhanced Analytics:**
- Wallet clustering to identify insider networks
- Signal pattern analysis across wallet types
- Performance attribution (which wallets/strategies drive profit)
- Risk exposure visualization across positions

### Vision (Future)

**V3 — Capital Scaling (Year 2+):**

**Multi-Chain Expansion:**
- Base (Coinbase L2) integration once Solana mastered
- Arbitrum integration for EVM memecoin markets
- Unified watchlist management across chains
- Cross-chain performance comparison

**Advanced Network Analysis:**
- Neo4j clustering for insider network detection
- Social graph analysis of wallet connections
- Cluster-based signal weighting (insider network proximity)
- Network visualization for manual curation assistance

**Potential Productization:**
- SaaS offering if personally profitable and validated
- Community wallet sharing (curated watchlists)
- API access for external integrations
- White-label infrastructure for other operators

**Long-Term North Star:** Complete trading infrastructure mastery—skills are permanent, system scales with capital, potential to productize once validated at personal scale.
