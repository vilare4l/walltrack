# Executive Summary

### Project Vision

WallTrack is a personal trading intelligence system for Solana memecoin copy-trading that transforms the insider's game into a systematic, transparent, and controllable operation. The core philosophy is **"Manual curation + Automated execution = Control + Efficiency"**—the operator curates a watchlist of high-performing smart money wallets discovered via GMGN, and the system automatically copies their trades with customizable exit strategies.

The unique value proposition combines zero fees (100% profit retention), complete transparency (understanding every automated decision), progressive validation (simulation-first approach), and granular control (per-wallet and per-position strategy customization). Built with AI assistance (Claude Code), WallTrack makes sophisticated trading infrastructure accessible to solo technical operators while building permanent skills in Solana/DeFi.

### Target Users

**Primary User: Christophe (System Operator)**

- **Profile**: Solo technical operator building personal trading infrastructure with AI assistance, beginner across Python/Solana/DeFi/Trading, learning by building
- **Role**: System operator performing daily high-level curation (watchlist management, strategy adjustments), zero manual trading required
- **Daily Workflow**:
  - Morning: Dashboard review focusing on active positions and 4 key metrics (Win rate, PnL total, Capital utilization, Active wallets simulation/live)
  - During Day: Curate watchlist (add/remove wallets based on performance), adjust exit strategies
  - Evening: Review daily synthesis (PnL, signals executed, circuit breaker status)
- **Journey**: Progressive validation from simulation (Weeks 1-4) → small live capital test (50€) → progressive stake increases (300€ → 500€ → 1000€+)
- **Success Vision**: Autonomous 24/7 operation with complete system mastery, sustained profitability validating the learning investment

**Technical Context**:
- UI Platform: Gradio (rapid iteration, operator-friendly)
- Usage Context: Desktop/laptop primary (morning/evening reviews), occasional mobile checks
- Complexity Tolerance: High (building complex system) but needs clarity in UI to avoid decision paralysis

### Key Design Challenges

1. **Dual-Mode Complexity Management**
   - Challenge: Visualize simulation vs live mode clearly across wallets and positions without confusion or accidents
   - Impact: Operator must never confuse simulation positions with live capital positions
   - UX Requirement: Clear visual distinction (color coding, labels, separated views) between modes

2. **Information Density in Gradio**
   - Challenge: Display rich data (positions, wallets, metrics, signals, safety scores) within Gradio's constraints without overwhelming the operator
   - Impact: Too much info = decision paralysis, too little = missed insights
   - UX Requirement: Progressive disclosure, smart defaults, scannable layouts prioritizing critical info

3. **Progressive Validation Journey Support**
   - Challenge: Interface must naturally support the operator's journey from simulation → small live test → capital scaling
   - Impact: Unclear progression path = hesitation to move to live mode or premature risk-taking
   - UX Requirement: Visual indicators of validation readiness (simulation performance thresholds), easy mode promotion per wallet

4. **Transparency for Trust Building**
   - Challenge: Show WHY decisions are made (safety scores, exit triggers, signal filtering) without cluttering the interface
   - Impact: Black box feeling = operator distrust and hesitation to rely on automation
   - UX Requirement: Contextual explanations, audit trails, decision reasoning visible on-demand

### Design Opportunities

1. **Transparency as Competitive Advantage**
   - Opportunity: Unlike black-box bots (Trojan, TradeWiz), WallTrack can show complete decision logic
   - UX Approach: Make safety scores, exit trigger reasoning, and performance analytics highly visible—transparency builds operator confidence
   - Differentiation: "I understand every trade" becomes the core UX value proposition

2. **Data-Driven Curation Interface**
   - Opportunity: Performance tracking per wallet (win rate, PnL, signal counts all/30d/7d/24h) enables systematic watchlist management
   - UX Approach: Sortable wallet analytics table, visual performance trends, quick add/remove actions based on data
   - Operator Value: Replace gut feeling with data-driven decisions on which wallets to keep/promote/remove

3. **Operator Sweet Spot: High-Level Control Without Manual Trading**
   - Opportunity: Interface balances quick high-level actions (toggle mode, adjust strategy) with deep visibility when needed
   - UX Approach: Dashboard emphasizes monitoring (positions + 4 key metrics at-a-glance), quick-action buttons for common curation tasks, detailed views accessible but not intrusive
   - Operator Experience: "I'm in control without being buried in details or forced to trade manually"

4. **Progressive Confidence Building**
   - Opportunity: UI can visually reinforce the simulation → live validation journey
   - UX Approach: Show simulation performance thresholds (e.g., "7 days stable, 55%+ win rate"), celebration moments (first live profit), progressive mode promotion flows
   - Emotional Design: Reduce anxiety about live trading by making validation milestones visible and achievable
