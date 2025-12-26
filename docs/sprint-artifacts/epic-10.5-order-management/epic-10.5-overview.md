# Epic 10.5: Order Management, Price Oracle & Risk-Based Sizing

**Goal:** Implémenter un système d'ordres complet avec cycle de vie, monitoring de prix multi-source, et sizing basé sur le risque réel par trade.

**Priorité:** HAUTE - Fondation requise avant passage en LIVE

**Dépendances:** Aucune (Epic fondamental)

---

## Epic Summary

| Aspect | Avant | Après |
|--------|-------|-------|
| Ordres | Aucun modèle, trade direct | Cycle de vie complet avec retry |
| Prix | Polling 5s, source unique | Multi-source, priorité, historique |
| Sizing | % du capital fixe | Basé sur risque réel (SL) |
| Simulation | Bypass du flow réel | Même flow, mock execution |
| Échecs | Silencieux | Retry automatique + alertes |

---

## Architecture Cible

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SIGNAL PIPELINE                                 │
│                           (existing, unchanged)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RISK MANAGER                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. Check daily loss limit                                           │   │
│  │ 2. Check drawdown-based reduction                                   │   │
│  │ 3. Check concentration limits                                       │   │
│  │ 4. Calculate risk-based position size                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ORDER MANAGER                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Entry Order                                  │   │
│  │  PENDING → SUBMITTED → CONFIRMING → FILLED ──► Position Created     │   │
│  │                │            │                                        │   │
│  │                └──► FAILED ─┴──► Retry (max 3) → CANCELLED          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Exit Order                                   │   │
│  │  PENDING → SUBMITTED → CONFIRMING → FILLED ──► Position Updated     │   │
│  │                │            │                                        │   │
│  │                └──► FAILED ─┴──► Retry (max 5) → Alert!             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXECUTION LAYER                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐ │
│  │   LIVE      │    │ SIMULATION  │    │        Price Oracle             │ │
│  │  Jupiter    │    │   Mock      │    │  DexScreener → Birdeye → Jup   │ │
│  │  Execution  │    │  Execution  │    │  (fallback chain)              │ │
│  └─────────────┘    └─────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stories

### 10.5-1: Order Model & State Machine

**As** the system,
**I want** un modèle Order avec états et transitions,
**So that** chaque trade est tracé de la demande à l'exécution.

**Acceptance Criteria:**

- **Given** un Order est créé
- **Then** il a les champs:
  ```python
  class Order:
      id: UUID
      type: OrderType  # ENTRY, EXIT
      status: OrderStatus  # PENDING, SUBMITTED, CONFIRMING, FILLED, FAILED, CANCELLED

      # Links
      signal_id: str | None      # For entry orders
      position_id: str | None    # For exit orders

      # Trade details
      token_address: str
      side: Side  # BUY, SELL
      amount_sol: Decimal
      amount_tokens: Decimal | None  # Calculated after quote

      # Pricing
      expected_price: Decimal
      max_slippage_bps: int
      actual_price: Decimal | None

      # Execution
      tx_signature: str | None
      executed_at: datetime | None

      # Retry
      attempt_count: int = 0
      max_attempts: int = 3
      last_error: str | None
      next_retry_at: datetime | None

      # Timing
      created_at: datetime
      expires_at: datetime | None
      updated_at: datetime
  ```

- **Given** les transitions d'état:
  ```
  PENDING → SUBMITTED (order sent to Jupiter)
  SUBMITTED → CONFIRMING (tx hash received)
  CONFIRMING → FILLED (tx confirmed on-chain)
  CONFIRMING → FAILED (tx failed)
  SUBMITTED → FAILED (API error)
  FAILED → PENDING (retry)
  PENDING → CANCELLED (max retries or expired)
  ```

**Technical Notes:**
- Table: `walltrack.orders`
- Fichier: `src/walltrack/models/order.py`
- State machine pattern avec validation des transitions

**Story Points:** 5

---

### 10.5-2: Order Table Migration

**As** the database,
**I want** une table orders avec tous les champs nécessaires,
**So that** les ordres sont persistés correctement.

**SQL Migration:**
```sql
CREATE TABLE walltrack.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL CHECK (type IN ('entry', 'exit')),
    status TEXT NOT NULL DEFAULT 'pending',

    -- Links
    signal_id UUID REFERENCES signals(id),
    position_id UUID REFERENCES positions(id),

    -- Trade details
    token_address TEXT NOT NULL,
    token_symbol TEXT,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    amount_sol DECIMAL(20,10) NOT NULL,
    amount_tokens DECIMAL(30,10),

    -- Pricing
    expected_price DECIMAL(30,15),
    max_slippage_bps INTEGER DEFAULT 100,
    actual_price DECIMAL(30,15),
    actual_amount_sol DECIMAL(20,10),
    actual_amount_tokens DECIMAL(30,10),
    fees_sol DECIMAL(20,10),

    -- Execution
    tx_signature TEXT,
    executed_at TIMESTAMPTZ,

    -- Retry logic
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Simulation flag
    simulated BOOLEAN DEFAULT FALSE,

    CONSTRAINT valid_status CHECK (
        status IN ('pending', 'submitted', 'confirming', 'filled', 'partial', 'failed', 'cancelled', 'expired')
    )
);

-- Indexes
CREATE INDEX idx_orders_status ON walltrack.orders(status);
CREATE INDEX idx_orders_position ON walltrack.orders(position_id);
CREATE INDEX idx_orders_signal ON walltrack.orders(signal_id);
CREATE INDEX idx_orders_retry ON walltrack.orders(status, next_retry_at)
    WHERE status = 'failed' AND next_retry_at IS NOT NULL;
```

**Story Points:** 3

---

### 10.5-3: Order Executor with Retry Logic

**As** the system,
**I want** un executor qui gère les retries automatiquement,
**So that** les trades ont plusieurs chances de réussir.

**Acceptance Criteria:**

- **Given** un Order en status PENDING
- **When** l'executor le traite
- **Then** il:
  1. Obtient un quote de Jupiter
  2. Soumet la transaction
  3. Attend la confirmation
  4. Met à jour le status

- **Given** un Order échoue (slippage, liquidity, timeout)
- **When** attempt_count < max_attempts
- **Then**:
  - Status → FAILED
  - next_retry_at = now + backoff (1s, 2s, 4s...)
  - Le retry worker le reprendra

- **Given** un Order atteint max_attempts
- **When** il échoue encore
- **Then**:
  - Status → CANCELLED
  - Alerte envoyée
  - Position non créée (entry) ou reste ouverte (exit)

- **Given** le mode SIMULATION
- **When** un Order est soumis
- **Then**:
  - Même flow, mais MockExecutor au lieu de Jupiter
  - Prix simulé avec slippage aléatoire
  - Tx signature = "SIM-{uuid}"

**Technical Notes:**
```python
class OrderExecutor:
    async def execute(self, order: Order) -> OrderResult:
        """Execute an order with retry support."""

    async def _execute_live(self, order: Order) -> OrderResult:
        """Execute via Jupiter."""

    async def _execute_simulated(self, order: Order) -> OrderResult:
        """Execute in simulation mode."""
```

**Story Points:** 8

---

### 10.5-4: Entry Order Flow

**As** the signal pipeline,
**I want** créer un Order d'entrée au lieu d'une Position directe,
**So that** le trade passe par le cycle de vie complet.

**Nouveau Flow:**
```
Signal (score OK)
    │
    ▼
Risk Manager
    │ Check limits, calculate size
    ▼
Order Created (type=ENTRY, status=PENDING)
    │
    ▼
Order Executor
    │
    ├─► SUCCESS: Order FILLED
    │       │
    │       ▼
    │   Position Created (status=OPEN)
    │
    └─► FAILURE (after retries): Order CANCELLED
            │
            ▼
        Signal marked as "execution_failed"
        Alert sent
```

**Acceptance Criteria:**

- **Given** un signal eligible
- **When** le pipeline l'approuve
- **Then** un Order ENTRY est créé, PAS une position directement

- **Given** l'Order ENTRY est FILLED
- **When** on reçoit la confirmation
- **Then** une Position est créée avec:
  - `entry_order_id` = order.id
  - `entry_price` = order.actual_price
  - `entry_amount_sol` = order.actual_amount_sol

- **Given** l'Order ENTRY échoue définitivement
- **When** status = CANCELLED
- **Then**:
  - Aucune position créée
  - Signal.execution_status = "failed"
  - Alerte créée

**Story Points:** 5

---

### 10.5-5: Exit Order Flow

**As** the exit manager,
**I want** créer un Order de sortie au lieu d'exécuter directement,
**So that** les exits ont aussi le retry logic.

**Nouveau Flow:**
```
Position (TP/SL triggered)
    │
    ▼
Exit Order Created (type=EXIT, status=PENDING)
    │ position_id, exit_reason, sell_percentage
    ▼
Order Executor
    │
    ├─► SUCCESS: Order FILLED
    │       │
    │       ▼
    │   Position Updated
    │   - current_amount -= sold
    │   - realized_pnl += pnl
    │   - status = PARTIAL/CLOSED
    │
    └─► FAILURE (after retries): Order CANCELLED
            │
            ▼
        Position stays OPEN (problème!)
        ALERT CRITIQUE envoyée
        Manual intervention required
```

**Acceptance Criteria:**

- **Given** une condition de sortie est déclenchée
- **When** ExitManager détecte TP/SL/Trailing
- **Then** un Order EXIT est créé, PAS d'exécution directe

- **Given** l'Order EXIT échoue
- **When** max retries atteint
- **Then**:
  - ALERTE CRITIQUE (position bloquée)
  - UI affiche "Exit Failed - Manual Action Required"
  - Nouveau bouton "Retry Exit" ou "Force Close"

**Story Points:** 5

---

### 10.5-6: Price Oracle - Multi-Source Aggregator

**As** the system,
**I want** agréger les prix de plusieurs sources,
**So that** j'ai un prix fiable même si une source tombe.

**Acceptance Criteria:**

- **Given** je demande le prix d'un token
- **When** le Price Oracle répond
- **Then** il a essayé dans l'ordre:
  1. DexScreener (primary)
  2. Birdeye (fallback 1)
  3. Jupiter Quote (fallback 2)

- **Given** une source retourne un prix aberrant (>50% différent)
- **When** d'autres sources sont disponibles
- **Then** le prix aberrant est ignoré (outlier filter)

- **Given** toutes les sources échouent
- **When** je demande un prix
- **Then** retourne le dernier prix connu + warning

**Technical Notes:**
```python
class PriceOracle:
    async def get_price(self, token_address: str) -> PriceResult:
        """Get aggregated price from multiple sources."""

    async def get_prices_batch(self, addresses: list[str]) -> dict[str, PriceResult]:
        """Batch price fetch for efficiency."""
```

**Story Points:** 5

---

### 10.5-7: Price History Collection

**As** the system,
**I want** stocker l'historique des prix pour les positions actives,
**So that** le What-If simulator a des données.

**Acceptance Criteria:**

- **Given** une position est ouverte
- **When** le PriceMonitor check le prix
- **Then** le prix est aussi stocké dans `position_price_history`

- **Given** la position dure 6h avec polling 5s
- **When** je regarde l'historique
- **Then** j'ai ~4320 points (mais on peut sampler à 1/min = 360)

- **Given** la position est clôturée depuis >7 jours
- **When** le cleanup job tourne
- **Then** l'historique est compressé (1 point / 5 min)

**Story Points:** 5

---

### 10.5-8: Risk-Based Position Sizing

**As** the operator,
**I want** que la taille de position soit basée sur le risque réel,
**So that** je ne risque jamais plus de X% de mon capital par trade.

**Concept:**
```
Avant (sizing actuel):
  position_size = capital × 2% × multiplier

  Problème: Si SL = 50%, je risque 1% du capital
            Si SL = 20%, je risque 0.4% du capital
            → Incohérent!

Après (risk-based):
  max_risk_per_trade = capital × 1%  (je veux risquer max 1%)
  position_size = max_risk_per_trade / stop_loss_pct

  Exemple:
  - Capital = 10 SOL
  - Max risk = 0.1 SOL (1%)
  - SL = 50%
  - Position = 0.1 / 0.5 = 0.2 SOL

  Si SL = 20%:
  - Position = 0.1 / 0.2 = 0.5 SOL

  → Risque constant de 1% peu importe le SL!
```

**Acceptance Criteria:**

- **Given** la config a `risk_per_trade_pct = 1.0`
- **When** je calcule une position avec SL = 50%
- **Then** position_size = capital × 1% / 50% = capital × 2%

- **Given** la même config
- **When** je calcule une position avec SL = 25%
- **Then** position_size = capital × 1% / 25% = capital × 4%

- **Given** le sizing dépasse max_position_sol
- **Then** il est cappé à max_position_sol

**New Config Fields:**
```python
class PositionSizingConfig:
    # Existing fields...

    # NEW: Risk-based sizing
    sizing_mode: SizingMode = SizingMode.RISK_BASED  # or FIXED_PERCENT
    risk_per_trade_pct: float = 1.0  # Max 1% risk per trade
```

**Story Points:** 5

---

### 10.5-9: Drawdown-Based Size Reduction

**As** the system,
**I want** réduire automatiquement la taille des positions en cas de drawdown,
**So that** je préserve le capital restant.

**Acceptance Criteria:**

- **Given** drawdown = 10%
- **When** je calcule une position
- **Then** la taille est réduite de 25%

- **Given** drawdown = 15%
- **When** je calcule une position
- **Then** la taille est réduite de 50%

- **Given** drawdown >= 20%
- **When** je calcule une position
- **Then** circuit breaker (no new trades)

**Config:**
```python
class RiskConfig:
    drawdown_reduction_tiers: list[DrawdownTier] = [
        DrawdownTier(threshold_pct=10, size_reduction_pct=25),
        DrawdownTier(threshold_pct=15, size_reduction_pct=50),
        DrawdownTier(threshold_pct=20, size_reduction_pct=100),  # = stop
    ]
```

**Story Points:** 3

---

### 10.5-10: Daily Loss Limit

**As** the operator,
**I want** que le système arrête de trader si je perds trop aujourd'hui,
**So that** une mauvaise journée ne détruit pas mon capital.

**Acceptance Criteria:**

- **Given** daily_loss_limit_pct = 5%
- **When** les pertes réalisées du jour atteignent 5%
- **Then**:
  - Aucun nouveau trade jusqu'à minuit UTC
  - Alerte envoyée
  - UI affiche "Daily Limit Reached"

- **Given** daily_loss_limit est atteint
- **When** les positions ouvertes touchent leur SL
- **Then** les exits sont toujours exécutés (on ne laisse pas les positions mourir)

**Story Points:** 3

---

### 10.5-11: Concentration Limits

**As** the operator,
**I want** limiter ma concentration sur un cluster ou token,
**So that** un rug d'un groupe ne me ruine pas.

**Acceptance Criteria:**

- **Given** max_positions_per_cluster = 2
- **When** j'ai déjà 2 positions de wallets du même cluster
- **Then** les signaux de ce cluster sont bloqués

- **Given** max_exposure_per_token_pct = 20%
- **When** un signal veut ajouter une position sur un token où j'ai déjà 20% du capital
- **Then** le signal est bloqué

**Story Points:** 3

---

### 10.5-12: Order Retry Worker

**As** the system,
**I want** un worker qui retente les ordres échoués,
**So that** les retries sont automatiques.

**Acceptance Criteria:**

- **Given** un Order avec status=FAILED et next_retry_at <= now
- **When** le retry worker tourne (every 5s)
- **Then** l'order est resoumis avec attempt_count++

- **Given** un Order a expiré (expires_at <= now)
- **When** le worker le voit
- **Then** status → EXPIRED (pas de retry)

**Technical Notes:**
```python
class OrderRetryWorker:
    async def run(self):
        """Main loop checking for orders to retry."""
        while self._running:
            orders = await self._get_retriable_orders()
            for order in orders:
                await self._retry_order(order)
            await asyncio.sleep(5)
```

**Story Points:** 5

---

### 10.5-13: Order UI - Liste et Actions

**As** the operator,
**I want** voir tous les ordres et leur status,
**So that** je comprends ce qui se passe et peux intervenir.

**Acceptance Criteria:**

- **Given** je vais sur Explorer > Orders (nouvel onglet)
- **When** la page charge
- **Then** je vois:
  - Ordres en cours (PENDING, SUBMITTED, CONFIRMING)
  - Ordres récents (FILLED, FAILED, CANCELLED)
  - Filtres par status, type, token

- **Given** un ordre est FAILED
- **When** je le vois dans la liste
- **Then** je peux:
  - Voir l'erreur (tooltip)
  - Cliquer "Retry Now" (force retry immédiat)
  - Cliquer "Cancel" (abandonner)

- **Given** un ordre EXIT est CANCELLED
- **When** je le vois
- **Then** je vois un badge "ATTENTION" et un bouton "Create New Exit Order"

**Story Points:** 5

---

### 10.5-14: Alerts on Order Failures

**As** the operator,
**I want** être alerté quand un ordre échoue définitivement,
**So that** je peux intervenir manuellement si nécessaire.

**Acceptance Criteria:**

- **Given** un ordre ENTRY est CANCELLED
- **When** c'est le dernier retry
- **Then** alerte "Entry Failed" (severity: warning)

- **Given** un ordre EXIT est CANCELLED
- **When** c'est le dernier retry
- **Then** alerte "EXIT FAILED - MANUAL ACTION REQUIRED" (severity: critical)

- **Given** le daily loss limit est atteint
- **Then** alerte "Daily Loss Limit Reached" (severity: warning)

**Story Points:** 3

---

### 10.5-15: Position Queue with Priority

**As** the system,
**I want** prioriser les positions proches des niveaux critiques,
**So that** les exits urgents sont traités en premier.

**Acceptance Criteria:**

- **Given** Position A à -48% (proche SL -50%)
- **And** Position B à +50% (loin du TP 2x)
- **When** le PriceMonitor check
- **Then** Position A est vérifiée avant Position B

**Priority Calculation:**
```python
def calculate_priority(position: Position, current_price: float) -> int:
    """Higher = more urgent."""
    distance_to_sl = abs(current_price - position.levels.stop_loss_price)
    distance_to_tp = abs(current_price - position.levels.next_take_profit.trigger_price)

    min_distance = min(distance_to_sl, distance_to_tp)

    # Closer to trigger = higher priority
    if min_distance < 0.05:  # Within 5%
        return 100  # Critical
    elif min_distance < 0.10:
        return 50   # High
    else:
        return 10   # Normal
```

**Story Points:** 3

---

## Implementation Order

```
Phase 1: Order Foundation (Stories 10.5-1 to 10.5-5)
├── 10.5-1: Order Model
├── 10.5-2: Order Table
├── 10.5-3: Order Executor
├── 10.5-4: Entry Order Flow
└── 10.5-5: Exit Order Flow

Phase 2: Price Oracle (Stories 10.5-6, 10.5-7, 10.5-15)
├── 10.5-6: Multi-Source Aggregator
├── 10.5-7: Price History Collection
└── 10.5-15: Priority Queue

Phase 3: Risk Management (Stories 10.5-8 to 10.5-11)
├── 10.5-8: Risk-Based Sizing
├── 10.5-9: Drawdown Reduction
├── 10.5-10: Daily Loss Limit
└── 10.5-11: Concentration Limits

Phase 4: Operations (Stories 10.5-12 to 10.5-14)
├── 10.5-12: Retry Worker
├── 10.5-13: Order UI
└── 10.5-14: Alerts
```

---

## Story Points Summary

| Story | Points | Priority |
|-------|--------|----------|
| 10.5-1: Order Model | 5 | P0 |
| 10.5-2: Order Table | 3 | P0 |
| 10.5-3: Order Executor | 8 | P0 |
| 10.5-4: Entry Order Flow | 5 | P0 |
| 10.5-5: Exit Order Flow | 5 | P0 |
| 10.5-6: Price Oracle | 5 | P0 |
| 10.5-7: Price History | 5 | P1 |
| 10.5-8: Risk-Based Sizing | 5 | P0 |
| 10.5-9: Drawdown Reduction | 3 | P1 |
| 10.5-10: Daily Loss Limit | 3 | P1 |
| 10.5-11: Concentration Limits | 3 | P2 |
| 10.5-12: Retry Worker | 5 | P0 |
| 10.5-13: Order UI | 5 | P1 |
| 10.5-14: Alerts | 3 | P1 |
| 10.5-15: Priority Queue | 3 | P2 |
| **Total** | **66** | |

---

## Definition of Done

- [ ] Table `orders` créée et migrée
- [ ] Order state machine avec transitions validées
- [ ] Entry flow passe par Order
- [ ] Exit flow passe par Order
- [ ] Retry automatique avec backoff
- [ ] Price Oracle multi-source fonctionnel
- [ ] Risk-based sizing implémenté
- [ ] Daily loss limit fonctionnel
- [ ] Simulation suit le même flow (MockExecutor)
- [ ] UI pour visualiser les ordres
- [ ] Alertes sur échecs critiques
- [ ] Tests unitaires et intégration
- [ ] Documentation

---

## Simulation Mode Behavior

**Principe:** Même code, exécution mockée.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Order Executor                              │
│                                                                  │
│  async def execute(self, order: Order) -> OrderResult:           │
│      if is_simulation_mode():                                    │
│          return await self._execute_simulated(order)             │
│      else:                                                       │
│          return await self._execute_live(order)                  │
│                                                                  │
│  async def _execute_simulated(self, order: Order) -> OrderResult:│
│      # 1. Add realistic delay (100-500ms)                        │
│      await asyncio.sleep(random.uniform(0.1, 0.5))               │
│                                                                  │
│      # 2. Simulate slippage (0-2%)                               │
│      slippage = random.uniform(0, 0.02)                          │
│      actual_price = order.expected_price * (1 + slippage)        │
│                                                                  │
│      # 3. Simulate occasional failures (5%)                      │
│      if random.random() < 0.05:                                  │
│          return OrderResult(success=False, error="Simulated fail")│
│                                                                  │
│      # 4. Return success with simulated values                   │
│      return OrderResult(                                         │
│          success=True,                                           │
│          tx_signature=f"SIM-{uuid4()}",                          │
│          actual_price=actual_price,                              │
│          ...                                                     │
│      )                                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Risk-Based Sizing: Exemple Complet

```
Configuration:
- Capital: 10 SOL
- risk_per_trade_pct: 1% (0.1 SOL max risk)
- high_conviction_multiplier: 1.5x
- max_position_sol: 2.0 SOL

Signal HIGH conviction (score 0.90):
- Exit Strategy: Conservative (SL = 50%)

Calcul:
1. Base risk = 10 SOL × 1% = 0.1 SOL
2. Position before multiplier = 0.1 / 0.5 = 0.2 SOL
3. Apply multiplier: 0.2 × 1.5 = 0.3 SOL
4. Check max: 0.3 < 2.0 ✓
5. Final: 0.3 SOL

Vérification du risque:
- Si SL hit: perte = 0.3 × 50% = 0.15 SOL = 1.5% du capital
- Avec multiplier, on accepte 1.5% pour high conviction
- Sans multiplier (standard): 0.2 × 50% = 0.1 SOL = 1% ✓

Signal STANDARD conviction avec SL = 25%:
1. Base risk = 0.1 SOL
2. Position = 0.1 / 0.25 = 0.4 SOL
3. No multiplier (1.0x): 0.4 SOL
4. Si SL hit: 0.4 × 25% = 0.1 SOL = 1% ✓
```

---

## Dépendances avec autres Epics

| Epic 13 fournit | Utilisé par |
|-----------------|-------------|
| Order model | Epic 12 (position details) |
| Price History | Epic 12 (What-If simulator) |
| Risk-based sizing | Epic 11 (config UI) |
| Alerts | Dashboard (status bar) |
