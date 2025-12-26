# Epic 12: Positions Management & Exit Strategy Simulator

**Goal:** Créer une expérience complète de gestion des positions avec visualisation des stratégies de sortie, changement dynamique, et simulation "What-If" sur les trades passés.

**Dépendance:** Epic 11 (ConfigService, Exit Strategy CRUD)

---

## Epic Summary

| Aspect | Avant | Après |
|--------|-------|-------|
| Vue Positions | Tableau basique | Détails complets + sidebar |
| Stratégie active | Figée à la création | Modifiable en live |
| Analyse post-trade | Aucune | Simulation What-If |
| Optimisation | Manuelle/intuitive | Data-driven sur historique |

---

## Stories

### 12-1: Positions List - Refonte avec Actions

**As** the operator,
**I want** une liste de positions enrichie avec actions contextuelles,
**So that** je peux voir l'essentiel et agir rapidement.

**Acceptance Criteria:**

- **Given** je suis sur Home ou Explorer
- **When** je vois la section Positions
- **Then** je vois deux groupes:
  - **Actives**: positions en cours
  - **Clôturées récentes**: 10 dernières

- **Given** une position active
- **When** je la vois dans la liste
- **Then** je vois: Token, Entry, Current, P&L%, Stratégie, Actions
- **And** les actions sont: [👁️ Détails] [⚙️ Stratégie]

- **Given** une position clôturée
- **When** je la vois dans la liste
- **Then** je vois: Token, Entry, Exit, P&L%, Stratégie, Exit Type, Actions
- **And** les actions sont: [👁️ Détails] [📊 What-If]

- **Given** le P&L est positif
- **Then** il est affiché en vert
- **Given** le P&L est négatif
- **Then** il est affiché en rouge

**Technical Notes:**
- Fichier: `src/walltrack/ui/components/positions.py`
- Utiliser `gr.Dataframe` avec colonnes custom
- Ajouter boutons d'action via HTML dans les cellules

**Story Points:** 5

---

### 12-2: Position Details - Sidebar

**As** the operator,
**I want** voir les détails complets d'une position dans le sidebar,
**So that** je comprends le contexte sans quitter la page.

**Acceptance Criteria:**

- **Given** je clique sur [👁️] d'une position
- **When** le sidebar s'ouvre
- **Then** je vois les sections:

**Pour position ACTIVE:**
```
📊 Performance
- Entry price, Current price, P&L, Duration

🎯 Stratégie Active
- Nom de la stratégie
- Niveaux TP avec prix cibles
- Stop Loss avec prix
- Trailing Stop config
- Moonbag config
- "Prochain TP dans: +X%"

📈 Source
- Wallet source (lien cliquable)
- Signal ID et date
- Score au moment du signal
```

**Pour position CLÔTURÉE:**
```
📊 Résultat Final
- Entry, Exit, P&L, Duration
- Exit Type (TP1, TP2, SL, Trailing, Time, Manual)

🎯 Stratégie Utilisée
- Détails avec ✅/❌ pour chaque niveau atteint

📈 Source
- Même que active

📊 What-If
- Bouton "Ouvrir le Simulateur"
```

**Technical Notes:**
- Réutiliser le système de sidebar de l'Epic 10
- Créer `render_position_context(position_id)` dans sidebar.py

**Story Points:** 5

---

### 12-3: Change Strategy - Position Active

**As** the operator,
**I want** changer la stratégie d'une position active,
**So that** je peux adapter ma sortie selon l'évolution du marché.

**Acceptance Criteria:**

- **Given** je clique sur [⚙️] d'une position active
- **When** le panneau s'ouvre
- **Then** je vois:
  - Stratégie actuelle
  - Dropdown avec toutes les stratégies disponibles
  - Preview des nouveaux niveaux TP/SL
  - Bouton "Appliquer"

- **Given** je sélectionne une nouvelle stratégie
- **When** je clique "Appliquer"
- **Then** une confirmation est demandée
- **And** après confirmation, la stratégie est changée immédiatement
- **And** les nouveaux TP/SL sont calculés par rapport au prix d'entrée
- **And** un log est créé dans l'audit

- **Given** la position a déjà atteint un TP
- **When** je change de stratégie
- **Then** les TP déjà atteints restent marqués comme exécutés
- **And** seuls les TP restants sont recalculés

**Technical Notes:**
- API: `PATCH /api/positions/{id}/strategy`
- Recalculer les prix absolus des TP/SL
- Logger le changement pour traçabilité

**Story Points:** 5

---

### 12-4: Price History - Data Collection

**As** the system,
**I want** stocker l'historique des prix pour chaque position,
**So that** je peux simuler des stratégies alternatives.

**Acceptance Criteria:**

- **Given** une position est ouverte
- **When** le prix change
- **Then** un snapshot est enregistré:
  - Timestamp
  - Price
  - Position ID

- **Given** la position dure 6 heures
- **When** je regarde l'historique
- **Then** j'ai des points toutes les ~1 minute (360 points)

- **Given** la position est clôturée
- **When** 7 jours passent
- **Then** l'historique détaillé est compressé (1 point / 5 min)
- **And** après 30 jours, supprimé (garder seulement résumé)

**Technical Notes:**
```sql
CREATE TABLE walltrack.position_price_history (
    id SERIAL PRIMARY KEY,
    position_id UUID REFERENCES positions(id),
    timestamp TIMESTAMP NOT NULL,
    price DECIMAL(20,10) NOT NULL,

    INDEX idx_position_time (position_id, timestamp)
);
```

- Source: DexScreener WebSocket ou polling toutes les minutes
- Background job pour la collecte
- Compression job quotidien

**Story Points:** 8

---

### 12-5: Exit Simulator - Engine

**As** the system,
**I want** un moteur de simulation qui rejoue une stratégie sur un historique de prix,
**So that** je peux calculer le résultat alternatif.

**Acceptance Criteria:**

- **Given** un historique de prix et une stratégie
- **When** je lance la simulation
- **Then** le moteur:
  1. Initialise la position au prix d'entrée
  2. Parcourt chaque point de prix chronologiquement
  3. Vérifie les conditions de sortie à chaque point:
     - TP atteint → vendre le %
     - SL atteint → tout vendre
     - Trailing activé → mettre à jour le stop
     - Trailing touché → tout vendre
     - Time limit → tout vendre
  4. Retourne le résultat final

- **Given** une stratégie avec TP1=2x(33%), TP2=3x(50%)
- **When** le prix atteint 2.5x puis redescend à 1.5x
- **Then** la simulation montre:
  - TP1 hit à 2x → vendu 33%
  - TP2 non atteint
  - Reste: 67% à 1.5x
  - P&L total calculé

- **Given** une stratégie avec trailing stop
- **When** le prix monte à 3x puis redescend
- **Then** le trailing s'active à 2x
- **And** le stop suit le pic
- **And** la sortie se fait au bon niveau

**Technical Notes:**
```python
class ExitSimulator:
    def simulate(
        self,
        entry_price: Decimal,
        price_history: list[PricePoint],
        strategy: ExitStrategy
    ) -> SimulationResult:
        """
        Returns:
            SimulationResult with:
            - final_pnl_percent
            - final_pnl_absolute
            - exit_events: list of (timestamp, type, price, amount_sold)
            - remaining_position_percent
        """
```

- Fichier: `src/walltrack/services/simulation/exit_simulator.py`

**Story Points:** 8

---

### 12-6: Exit Simulator - Comparison

**As** the operator,
**I want** comparer plusieurs stratégies sur une même position,
**So that** je peux identifier la meilleure.

**Acceptance Criteria:**

- **Given** une position clôturée avec historique
- **When** je lance une comparaison multi-stratégies
- **Then** je reçois un tableau:
  | Strategy | Simulated P&L | Actual P&L | Delta | Exit Point |

- **Given** les résultats
- **When** je les affiche
- **Then** la meilleure stratégie est mise en évidence (★)
- **And** les deltas positifs sont en vert, négatifs en rouge

- **Given** plusieurs stratégies
- **When** je compare
- **Then** je vois aussi les exit points sur un graphique commun

**Technical Notes:**
```python
class ExitSimulator:
    def compare(
        self,
        position: Position,
        strategies: list[ExitStrategy]
    ) -> ComparisonResult:
        """Compare multiple strategies on same position."""
```

**Story Points:** 3

---

### 12-7: UI - What-If Modal

**As** the operator,
**I want** une interface visuelle pour le simulateur What-If,
**So that** je peux explorer les alternatives facilement.

**Acceptance Criteria:**

- **Given** je clique [📊 What-If] sur une position clôturée
- **When** le modal s'ouvre
- **Then** je vois:
  - Graphique de prix avec entry/exit réels marqués
  - Checkboxes pour sélectionner les stratégies à simuler
  - Bouton "Simuler"

- **Given** je sélectionne des stratégies et clique Simuler
- **When** la simulation tourne
- **Then** je vois:
  - Points de sortie simulés ajoutés au graphique (couleurs différentes)
  - Tableau comparatif en dessous
  - Meilleure stratégie mise en avant

- **Given** une stratégie performe mieux
- **When** je la vois dans les résultats
- **Then** je peux cliquer "Utiliser comme défaut pour [High Conviction / Standard]"

**Technical Notes:**
- Utiliser `gr.Plot` avec Plotly pour le graphique interactif
- Modal via `gr.Modal` ou page dédiée
- Fichier: `src/walltrack/ui/components/whatif_simulator.py`

**Story Points:** 8

---

### 12-8: UI - Price Chart Component

**As** the operator,
**I want** un graphique de prix avec annotations,
**So that** je visualise clairement les points d'entrée/sortie.

**Acceptance Criteria:**

- **Given** un historique de prix
- **When** le graphique s'affiche
- **Then** je vois:
  - Courbe de prix (ligne)
  - Point d'entrée (●) avec label
  - Points de sortie réels (●) avec labels (TP1, TP2, SL, etc.)
  - Ligne horizontale pour les niveaux TP/SL

- **Given** des simulations sont ajoutées
- **When** le graphique se met à jour
- **Then** je vois:
  - Points simulés (◆) en couleurs différentes par stratégie
  - Légende avec les stratégies

- **Given** je survole un point
- **When** le tooltip s'affiche
- **Then** je vois: Prix, Date/Heure, Type (Entry/TP1/SL...), P&L à ce point

**Technical Notes:**
```python
def create_price_chart(
    price_history: list[PricePoint],
    actual_exits: list[ExitEvent],
    simulated_exits: dict[str, list[ExitEvent]] = None
) -> go.Figure:
    """Create Plotly figure with annotations."""
```

- Utiliser Plotly (compatible Gradio)
- Fichier: `src/walltrack/ui/components/price_chart.py`

**Story Points:** 5

---

### 12-9: Global Analysis - Multi-Position Simulation

**As** the operator,
**I want** simuler une stratégie sur tous mes trades passés,
**So that** je peux optimiser ma stratégie par défaut.

**Acceptance Criteria:**

- **Given** je suis sur Config > Exit
- **When** je clique "Analyser mes trades passés"
- **Then** un panneau s'ouvre avec:
  - Sélection de la période (7j, 30j, 90j, all)
  - Sélection des stratégies à comparer
  - Bouton "Lancer l'analyse"

- **Given** je lance l'analyse sur 50 trades
- **When** l'analyse termine
- **Then** je vois un tableau:
  | Strategy | Total P&L | Avg P&L | Win Rate | Best For |
  - "Best For" indique si mieux pour High Conviction ou Standard

- **Given** une stratégie est clairement meilleure
- **When** je vois les résultats
- **Then** je peux cliquer "Appliquer comme défaut" en un clic

- **Given** l'analyse prend du temps
- **When** elle tourne
- **Then** je vois une progress bar
- **And** je peux annuler

**Technical Notes:**
- Exécuter en background (async)
- Limiter à positions avec price_history disponible
- Cache les résultats pendant 1h

**Story Points:** 8

---

### 12-10: Position Timeline - Exit Events Log

**As** the operator,
**I want** voir la timeline complète des events d'une position,
**So that** je comprends exactement ce qui s'est passé.

**Acceptance Criteria:**

- **Given** je suis dans les détails d'une position
- **When** je clique sur "Timeline"
- **Then** je vois une liste chronologique:
  ```
  10:32 - Position ouverte
          Entry: 0.10 SOL @ $0.00012
          Strategy: Balanced

  12:45 - TP1 Triggered
          Price reached 2.0x ($0.00024)
          Sold: 33% (0.033 SOL) → +0.033 SOL profit

  14:20 - Strategy Changed
          Balanced → Diamond Hands
          By: operator

  16:15 - Trailing Stop Activated
          Price reached 3.0x ($0.00036)
          Stop set at $0.00025 (30% below peak)

  16:47 - Trailing Stop Hit
          Price dropped to $0.00025
          Sold: remaining 67% → +0.11 SOL profit

  FINAL: +150% (+0.143 SOL)
  ```

**Technical Notes:**
- Table: `position_events` déjà existe partiellement
- Enrichir avec strategy changes, trailing updates
- Fichier: `src/walltrack/ui/components/position_timeline.py`

**Story Points:** 3

---

### 12-11: API Endpoints - Positions & Simulation

**As** the frontend,
**I want** des endpoints pour gérer les positions et simulations,
**So that** l'UI peut fonctionner.

**Endpoints:**

```
GET  /api/positions
     Query: status=active|closed, limit, offset
     Returns: list of positions with summary

GET  /api/positions/{id}
     Returns: full position details with strategy

GET  /api/positions/{id}/history
     Returns: price history for simulation

PATCH /api/positions/{id}/strategy
     Body: {strategy_id: "..."}
     Returns: updated position

POST /api/positions/{id}/simulate
     Body: {strategy_ids: ["...", "..."]}
     Returns: simulation results for each strategy

POST /api/positions/simulate-bulk
     Body: {position_ids: [...], strategy_ids: [...]}
     Returns: aggregated results

GET  /api/positions/{id}/timeline
     Returns: chronological events
```

**Story Points:** 5

---

## Implementation Order

```
Phase 1: Foundation (Stories 12-4, 12-5, 12-11)
├── 12-4: Price History Collection
├── 12-5: Exit Simulator Engine
└── 12-11: API Endpoints

Phase 2: UI Basic (Stories 12-1, 12-2, 12-3)
├── 12-1: Positions List Refonte
├── 12-2: Position Details Sidebar
└── 12-3: Change Strategy

Phase 3: What-If UI (Stories 12-6, 12-7, 12-8)
├── 12-6: Comparison Logic
├── 12-7: What-If Modal
└── 12-8: Price Chart Component

Phase 4: Advanced (Stories 12-9, 12-10)
├── 12-9: Global Analysis
└── 12-10: Position Timeline
```

---

## Story Points Summary

| Story | Points | Priority |
|-------|--------|----------|
| 12-1: Positions List | 5 | P0 |
| 12-2: Position Details Sidebar | 5 | P0 |
| 12-3: Change Strategy | 5 | P1 |
| 12-4: Price History Collection | 8 | P0 |
| 12-5: Exit Simulator Engine | 8 | P0 |
| 12-6: Comparison Logic | 3 | P1 |
| 12-7: What-If Modal | 8 | P1 |
| 12-8: Price Chart Component | 5 | P1 |
| 12-9: Global Analysis | 8 | P2 |
| 12-10: Position Timeline | 3 | P2 |
| 12-11: API Endpoints | 5 | P0 |
| **Total** | **63** | |

---

## Definition of Done

- [ ] Liste positions avec actions contextuelles
- [ ] Sidebar avec détails complets
- [ ] Changement de stratégie sur positions actives
- [ ] Collection automatique du price history
- [ ] Moteur de simulation fonctionnel
- [ ] UI What-If avec graphique interactif
- [ ] Comparaison multi-stratégies
- [ ] Analyse globale sur trades passés
- [ ] Timeline des events
- [ ] API complète
- [ ] Tests pour le simulator engine
- [ ] Documentation

---

## Dépendances avec Epic 11

| Epic 12 Story | Dépend de Epic 11 |
|---------------|-------------------|
| 12-3: Change Strategy | 11-7: Exit CRUD (liste des stratégies) |
| 12-5: Simulator Engine | 11-7: Exit Strategy model |
| 12-7: What-If Modal | 11-9: Exit Strategy Editor (pour voir/créer) |
| 12-9: Global Analysis | 11-8: Simulation Engine (réutilise) |

**Recommandation:** Faire Epic 11 Phase 1-2 avant Epic 12.

---

## Données Techniques

### Price History Storage

```sql
-- ~360 points par position de 6h (1/min)
-- ~1000 positions/mois = 360k rows/mois
-- Compression après 7j: /5 = 72k rows
-- Suppression après 30j (garder summary seulement)

CREATE TABLE walltrack.position_price_history (
    id BIGSERIAL PRIMARY KEY,
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20,10) NOT NULL,

    CONSTRAINT unique_position_time UNIQUE (position_id, timestamp)
);

CREATE INDEX idx_pph_position ON position_price_history(position_id);
CREATE INDEX idx_pph_time ON position_price_history(timestamp);

-- Compression job (daily)
-- DELETE FROM position_price_history
-- WHERE position_id IN (SELECT id FROM positions WHERE closed_at < NOW() - INTERVAL '7 days')
-- AND timestamp NOT IN (SELECT DISTINCT ON (position_id, date_trunc('5min', timestamp)) timestamp ...);
```

### Simulation Performance

- 360 points × 1 stratégie = ~5ms
- 360 points × 5 stratégies = ~25ms
- 50 positions × 5 stratégies = ~1.25s
- Acceptable pour UX, pas besoin de background job pour individuel
