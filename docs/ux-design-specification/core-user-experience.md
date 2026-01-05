# Core User Experience

### Defining Experience

WallTrack's core experience revolves around two primary actions that must be absolutely effortless:

**1. Morning Dashboard Review (Monitoring)**

The most frequent and critical user action—a rapid assessment of system health and trading performance:
- **Action**: Scan active positions + 4 key metrics (Win rate, PnL total, Capital utilization, Active wallets simulation/live)
- **Decision**: Immediate "Tout va bien" ✅ (continue monitoring) or "Action requise" ⚠️ (investigate/adjust)
- **Importance**: This daily ritual builds trust, maintains risk awareness, and validates confidence progression for simulation → live transitions
- **Success Criteria**: Operator gains complete situational awareness in < 30 seconds

**2. Watchlist Adjustment (Curation)**

The second core action enabling data-driven wallet management:
- **Action**: Add/Remove/Promote wallets based on performance data
- **Required Information**: 3 critical data points must be visible together:
  - Performance metrics (win rate, PnL per wallet)
  - Signal activity (recent signal counts: all/30d/7d/24h)
  - Current mode (simulation vs live status)
- **Importance**: Systematic watchlist curation replaces gut feeling with data-driven decisions, directly impacting profitability
- **Success Criteria**: Operator can make confident add/remove/promote decisions in < 2 minutes per wallet

### Platform Strategy

**Primary Platform: Gradio Web Interface**

- **Deployment**: Desktop/laptop browser (primary usage context)
- **Input Method**: Mouse/keyboard interaction (tables, dropdowns, buttons)
- **Usage Pattern**: Morning/evening reviews (5-10 minutes), quick checks during day (< 1 minute)
- **Technical Constraint**: Gradio framework limitations—no complex custom UI components, focus on clarity over visual sophistication

**Platform Decisions:**
- Web-based eliminates installation friction (accessible from any browser)
- Desktop-optimized layout (sufficient screen real estate for data density)
- No offline functionality required (trading system requires live connection)
- Responsive design not critical (primary use = desktop, mobile = occasional checks only)

### Effortless Interactions

The following interactions must feel completely natural and require zero cognitive load:

**1. Instant Status Visibility**
- Dashboard loads and displays system health in < 2 seconds
- At-a-glance status indicators (green = all good, yellow = review needed, red = action required)
- Circuit breaker status immediately visible (active/paused, reason displayed)
- No need to navigate multiple pages to assess system state

**2. One-Click Wallet Actions**
- Add wallet: Paste GMGN address → one-click add to watchlist in simulation mode
- Remove wallet: Select underperformer → one-click remove with confirmation
- Promote wallet: Simulation → Live toggle with visual confirmation and safety check
- No multi-step wizards or complex configuration for common tasks

**3. Transparent Decision Logic**
- See WHY trades executed: Safety scores, signal details, exit triggers visible without digging
- Click position → see complete audit trail (entry reason, current status, exit strategy)
- No black box mystery—every automated decision has visible justification
- Progressive disclosure: summary visible, details on-demand

**4. Zero Manual Trading**
- System executes all trades automatically based on configured strategies
- Operator monitors and curates, never manually buys/sells
- Interface reinforces monitoring role, not trading role
- Reduces stress and time commitment while maintaining control

### Critical Success Moments

These make-or-break moments determine operator confidence and system adoption:

**1. First Simulation Validation (Week 2-4)**
- **Moment**: Dashboard shows "7 days stable, 55%+ win rate" milestone achieved
- **Emotion**: Confidence building → "The system works in simulation, I understand the logic"
- **UX Support**: Visual milestone indicator, clear path to live mode activation
- **Failure Risk**: If dashboard doesn't clearly show validation progress, operator hesitates indefinitely

**2. First Live Profit (Week 5)**
- **Moment**: First position closes with +5€ realized profit (live mode)
- **Emotion**: Validation → "It works! Not theoretical, not simulated—real profit from real execution"
- **UX Support**: Celebration notification, clear profit attribution to wallet/strategy
- **Failure Risk**: If first live trade fails or profit isn't clearly visible, operator loses confidence

**3. Data-Driven Curation Decision (Ongoing)**
- **Moment**: Remove underperforming wallet based on visible analytics (e.g., win rate dropped to 35%)
- **Emotion**: Control and mastery → "I'm making systematic decisions based on data, not guessing"
- **UX Support**: Sortable performance table, trend visualization, clear remove action
- **Failure Risk**: Without clear performance data, operator keeps bad wallets or removes good ones arbitrarily

**4. Progressive Confidence Scaling (Months 2-3)**
- **Moment**: Increase capital allocation (300€ → 500€ → 1000€) based on sustained live performance
- **Emotion**: Trust and validation → "The learning investment paid off, I'm scaling profitably"
- **UX Support**: Visual capital progression, performance history, configurable capital allocation
- **Failure Risk**: If progression path unclear or performance data unreliable, operator never scales beyond initial capital

### Experience Principles

These guiding principles inform all UX design decisions for WallTrack:

**1. Transparency Builds Trust**
- Principle: Show WHY every decision is made, not just WHAT happened
- Application: Visible safety scores, exit trigger reasoning, performance attribution, audit trails
- Rationale: Operator must understand automated decisions to trust the system—transparency is competitive advantage vs black-box bots
- Design Impact: Progressive disclosure pattern—summary always visible, details accessible on-demand without clutter

**2. Data Over Gut Feeling**
- Principle: Make performance data hyper-visible for systematic curation decisions
- Application: Sortable analytics tables, win rate trends, signal activity metrics, PnL per wallet prominently displayed
- Rationale: Data-driven watchlist management outperforms intuition—replace gut feeling with evidence
- Design Impact: Analytics-first interface design, quick data access, comparison features

**3. High-Level Control Without Overwhelm**
- Principle: Quick actions for common tasks, deep visibility when needed
- Application: Dashboard emphasizes monitoring (at-a-glance metrics), quick-action buttons for curation, detailed views non-intrusive
- Rationale: Operator wants control without being buried in details or forced to trade manually
- Design Impact: Two-tier information hierarchy—critical info surface-level, comprehensive data one-click away

**4. Progressive Validation Journey**
- Principle: UI reinforces simulation → live transition with clear milestones
- Application: Visual validation thresholds (7 days stable, 55%+ win rate), mode status indicators, progressive capital scaling support
- Rationale: Reduce anxiety about live trading by making validation milestones visible and achievable
- Design Impact: Journey-aware design with celebration moments, clear next-step guidance, risk awareness indicators
