# Epic 11: Configuration Centralization & Exit Strategy Simulation

**Goal:** Centraliser tous les paramètres configurables dans Supabase avec hot-reload, gestion de versions (default/active/draft/archived), et simulation de stratégies de sortie.

**Input Document:** `docs/config-refactoring-proposal.md`

---

## Epic Summary

| Aspect | Avant | Après |
|--------|-------|-------|
| Paramètres | ~50 hardcodés, ~30 .env, ~10 DB | 100% en DB (sauf secrets) |
| Modification | Redéploiement requis | Hot-reload en ~60s |
| Versioning | Aucun | Default → Draft → Active → Archived |
| Exit Strategies | 5 presets figés | Personnalisables + simulation |
| Audit | Aucun | Historique complet des changements |

---

## Architecture: Cycle de Vie des Configurations

```
┌─────────────────────────────────────────────────────────────┐
│                    LIFECYCLE DES CONFIGS                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   DEFAULT ──────────────────────────────────────────────►   │
│   (Presets système, non modifiables)                        │
│                        │                                     │
│                        │ Clone                               │
│                        ▼                                     │
│                     DRAFT ◄────────────────────────────►    │
│                   (En cours d'édition)                       │
│                        │                                     │
│                        │ Activate                            │
│                        ▼                                     │
│                    ACTIVE ──────────────────────────────►   │
│                  (Configuration live)                        │
│                        │                                     │
│                        │ Replace/Archive                     │
│                        ▼                                     │
│                   ARCHIVED                                   │
│                 (Historique, restaurable)                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Règles du Lifecycle

| Status | Éditable | Utilisé | Supprimable | Description |
|--------|----------|---------|-------------|-------------|
| `default` | Non | Fallback | Non | Presets système (Conservative, Balanced, etc.) |
| `draft` | Oui | Non | Oui | Brouillon en cours de création/modification |
| `active` | Non | Oui | Non | Configuration actuellement utilisée |
| `archived` | Non | Non | Oui | Ancienne config, restaurable |

### Transitions Autorisées

```
default → (clone) → draft
draft → (activate) → active
active → (archive) → archived
archived → (restore) → draft
draft → (delete) → supprimé
```

---

## Stories

### 11-1: Config Lifecycle Migration (ALTER TABLE)

**⚠️ Note:** Les tables existent déjà (V8). Cette story AJOUTE le lifecycle via ALTER TABLE.

**As** the architect,
**I want** ajouter un lifecycle aux tables de configuration existantes,
**So that** chaque config peut avoir des versions (default, draft, active, archived).

**Acceptance Criteria:**

- **Given** les tables de config existent déjà (V8)
- **When** la migration V13 s'exécute
- **Then** chaque table reçoit les colonnes lifecycle:
  - `name` (identifiant)
  - `status` (enum: default, draft, active, archived)
  - `version` (numéro auto-incrémenté)
  - `created_at`, `created_by`
- **And** la ligne existante (id=1) devient `status = 'active'`
- **And** la contrainte single-row (`CHECK id=1`) est supprimée
- **And** un partial index garantit une seule config `active` par table

**Technical Notes:**
- Fichier: `migrations/V13__config_lifecycle.sql`
- ALTER TABLE (pas CREATE) sur tables existantes
- Trigger: auto-increment `version` sur update

**Story Points:** 3

---

### 11-2: ConfigService avec Cache et Hot-Reload

**As** a developer,
**I want** un service centralisé pour accéder aux configurations,
**So that** je n'ai plus de constantes hardcodées et les changements sont hot-reloadés.

**Acceptance Criteria:**

- **Given** le ConfigService est initialisé
- **When** j'appelle `config.get("trading.score_threshold")`
- **Then** je reçois la valeur de la config `active`
- **And** la valeur est cachée pour 60 secondes

- **Given** une config est modifiée en DB
- **When** le cache expire (60s)
- **Then** la nouvelle valeur est automatiquement chargée
- **And** aucun restart n'est nécessaire

- **Given** la DB est indisponible
- **When** j'appelle `config.get()`
- **Then** je reçois la valeur default hardcodée (fallback)
- **And** un warning est loggé

**Technical Notes:**
```python
class ConfigService:
    async def get(self, key: str, default: Any = None) -> Any
    async def get_block(self, table: str) -> dict
    async def set(self, key: str, value: Any, updated_by: str) -> None
    async def refresh(self, table: str = None) -> None
```
- Fichier: `src/walltrack/services/config_service.py`
- Pattern: Singleton avec cache TTL
- Dépendance: SupabaseClient

**Story Points:** 5

---

### 11-3: Migration des Composants vers ConfigService

**As** the architect,
**I want** tous les composants existants migrés vers ConfigService,
**So that** plus aucun paramètre n'est hardcodé.

**Acceptance Criteria:**

- **Given** les fichiers `constants/scoring.py`, `constants/threshold.py`
- **When** la migration est terminée
- **Then** ces fichiers sont supprimés ou réduits aux fallback defaults

- **Given** `SignalScorer`, `ThresholdChecker`, `SignalFilter`
- **When** ils sont instanciés
- **Then** ils reçoivent `ConfigService` en injection
- **And** ils utilisent `await config.get()` pour chaque paramètre

- **Given** `DecayDetector`, `PumpFinder`, `Profiler`
- **When** ils sont instanciés
- **Then** ils utilisent `ConfigService` pour leurs seuils

**Files to Modify:**
| Composant | Fichier |
|-----------|---------|
| SignalScorer | `services/scoring/signal_scorer.py` |
| ThresholdChecker | `services/signal/threshold_checker.py` |
| SignalFilter | `services/signal/signal_filter.py` |
| SignalAmplifier | `core/cluster/signal_amplifier.py` |
| SyncDetector | `core/cluster/sync_detector.py` |
| LeaderDetection | `core/cluster/leader_detection.py` |
| DecayDetector | `discovery/decay_detector.py` |
| PumpFinder | `discovery/pump_finder.py` |
| Profiler | `discovery/profiler.py` |

**Story Points:** 8

---

### 11-4: API Endpoints pour Config Management

**As** the operator,
**I want** des endpoints REST pour gérer les configurations,
**So that** je peux lire, modifier et versionner les configs via API.

**Acceptance Criteria:**

- **GET** `/api/config/{table}`
  - Retourne la config `active` pour la table donnée
  - 200: `{status: "active", version: 3, data: {...}}`

- **GET** `/api/config/{table}/all`
  - Retourne toutes les versions (default, active, draft, archived)
  - 200: `[{status: "default", ...}, {status: "active", ...}]`

- **POST** `/api/config/{table}/draft`
  - Crée un draft à partir de la config active
  - 201: `{status: "draft", id: "...", data: {...}}`

- **PATCH** `/api/config/{table}/draft`
  - Modifie le draft existant
  - 200: `{status: "draft", data: {...}}`

- **POST** `/api/config/{table}/activate`
  - Active le draft → devient `active`, l'ancien `active` → `archived`
  - 200: `{status: "active", version: 4}`

- **POST** `/api/config/{table}/{id}/restore`
  - Restaure une config archived en draft
  - 201: `{status: "draft", source: "archived-v2"}`

- **GET** `/api/config/audit`
  - Retourne l'historique des changements
  - Query params: `table`, `from_date`, `to_date`

**Technical Notes:**
- Fichier: `src/walltrack/api/routes/config.py` (étendre l'existant)
- Validation Pydantic pour chaque table
- Autorisation: seul `updated_by` avec droits peut modifier

**Story Points:** 5

---

### 11-5: UI - Page Configuration Redesign

**As** the operator,
**I want** une page Config complète dans le dashboard,
**So that** je peux visualiser et modifier toutes les configurations.

**Acceptance Criteria:**

- **Given** je navigue vers la page Config
- **When** elle se charge
- **Then** je vois des onglets pour chaque domaine:
  - Trading | Scoring | Discovery | Cluster | Risk | Exit | API

- **Given** je suis sur un onglet
- **When** je regarde le contenu
- **Then** je vois:
  - Badge du status actuel (Active, Draft, Default)
  - Version number
  - Tableau des paramètres avec nom, valeur, description
  - Bouton "Edit" (crée un draft si aucun)

- **Given** je suis en mode édition (draft)
- **When** je modifie une valeur
- **Then** la modification est sauvegardée en draft
- **And** je vois un bouton "Activate" pour appliquer
- **And** je vois un bouton "Discard" pour annuler

- **Given** j'active un draft
- **When** je clique sur "Activate"
- **Then** une confirmation est demandée
- **And** après confirmation, la config devient active
- **And** un toast confirme le changement

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Configuration                                    [Active v3] │
├─────────────────────────────────────────────────────────────┤
│ Trading | Scoring | Discovery | Cluster | Risk | Exit | API │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Position Sizing                                              │
│ ┌──────────────────────┬──────────┬───────────────────────┐ │
│ │ Parameter            │ Value    │ Description           │ │
│ ├──────────────────────┼──────────┼───────────────────────┤ │
│ │ base_position_pct    │ 2.0%     │ % du capital par trade│ │
│ │ max_position_sol     │ 1.0 SOL  │ Taille max par trade  │ │
│ │ max_concurrent       │ 5        │ Positions simultanées │ │
│ └──────────────────────┴──────────┴───────────────────────┘ │
│                                                              │
│ Thresholds                                                   │
│ ┌──────────────────────┬──────────┬───────────────────────┐ │
│ │ score_threshold      │ 0.70     │ Score min pour trader │ │
│ │ high_conviction      │ 0.85     │ Score high conviction │ │
│ └──────────────────────┴──────────┴───────────────────────┘ │
│                                                              │
│                              [Edit] [History] [Reset Default]│
└─────────────────────────────────────────────────────────────┘
```

**Story Points:** 8

---

### 11-6: UI - Historique et Audit des Configs

**As** the operator,
**I want** visualiser l'historique des changements de configuration,
**So that** je peux comprendre qui a changé quoi et quand.

**Acceptance Criteria:**

- **Given** je clique sur "History" dans la page Config
- **When** le panneau s'ouvre
- **Then** je vois une timeline des changements:
  - Date/heure
  - Utilisateur
  - Paramètre modifié
  - Ancienne valeur → Nouvelle valeur
  - Raison (si fournie)

- **Given** je vois un changement dans l'historique
- **When** je clique dessus
- **Then** je peux voir le diff complet de cette version
- **And** je peux "Restaurer cette version" (crée un draft)

**Mockup:**
```
┌─────────────────────────────────────────────────────────────┐
│ Configuration History - Trading                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 26 Dec 15:32 - admin                                         │
│ ├─ score_threshold: 0.70 → 0.75                              │
│ └─ Reason: "Testing higher threshold for quality"            │
│                                                   [Restore]  │
│                                                              │
│ 26 Dec 14:10 - system                                        │
│ ├─ max_concurrent: 5 → 3                                     │
│ └─ Reason: "Risk reduction during volatility"                │
│                                                   [Restore]  │
│                                                              │
│ 25 Dec 10:00 - admin                                         │
│ └─ Initial activation from defaults                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Story Points:** 3

---

### 11-7: Exit Strategy - CRUD et Versioning (ALTER TABLE)

**⚠️ Note:** La table `exit_strategies` existe déjà (008_exit_strategies.sql). Cette story AJOUTE le lifecycle.

**As** the operator,
**I want** gérer mes stratégies de sortie comme des configurations versionnées,
**So that** je peux créer, modifier et archiver des stratégies personnalisées.

**Acceptance Criteria:**

- **Given** la table `exit_strategies` existe avec `is_default`
- **When** la migration V14 s'exécute
- **Then** les colonnes lifecycle sont ajoutées:
  - `version` INTEGER
  - `status` VARCHAR (draft, active, archived)
  - `rules` JSONB
- **And** `is_default=true` migre vers `status='active'`

- **Given** je veux créer une stratégie custom
- **When** je clone un preset ou crée from scratch
- **Then** une nouvelle stratégie `status = 'draft'` est créée
- **And** je peux la modifier librement

- **Given** j'ai un draft de stratégie
- **When** je l'active
- **Then** elle devient disponible pour assignation aux positions

**Technical Notes:**
- Fichier: `migrations/V14__exit_strategies_lifecycle.sql`
- ALTER TABLE (pas CREATE) sur table existante
- Migration des données: `is_default=true` → `status='active'`

**Story Points:** 5

---

### 11-8: Exit Strategy - Simulation Engine (CORE)

**⚠️ Important:** Ceci est LE simulateur unique du système. Story 12-5 crée un wrapper position-aware autour de ce moteur.

| Composant | Rôle |
|-----------|------|
| `ExitSimulationEngine` (11-8) | Core simulation logic |
| `PositionSimulator` (12-5) | Position-specific wrapper (uses 11-8) |

**As** the operator,
**I want** simuler différentes stratégies de sortie sur des positions passées,
**So that** je peux évaluer "what if" et optimiser mes stratégies.

**Acceptance Criteria:**

- **Given** une position clôturée avec son historique de prix
- **When** je lance une simulation avec une stratégie différente
- **Then** je vois:
  - Le résultat simulé (P&L, % gain/loss)
  - Les points de sortie simulés sur un graphique
  - La comparaison avec le résultat réel

- **Given** plusieurs stratégies à comparer
- **When** je lance une simulation comparative
- **Then** je vois un tableau comparatif

- **Given** une stratégie avec partial exits (TP1, TP2)
- **When** je simule
- **Then** les exits partiels sont correctement calculés

**Technical Notes:**
```python
class ExitSimulationEngine:
    async def simulate_position(
        self,
        strategy: ExitStrategy,
        position_id: str,
        entry_price: Decimal,
        entry_time: datetime,
        position_size_sol: Decimal,
        token_address: str,
    ) -> SimulationResult:
        """Core simulation logic - fetches price history and simulates."""

    async def compare_strategies(
        self,
        position_id: str,
        strategies: list[ExitStrategy],
    ) -> list[SimulationResult]:
        """Compare multiple strategies on same position."""
```

- Fichier: `src/walltrack/services/exit/simulation_engine.py`
- Utilise price_history via 10.5-7 infrastructure

**Story Points:** 8

---

### 11-9: UI - Exit Strategy Editor

**As** the operator,
**I want** un éditeur visuel pour créer et modifier des stratégies de sortie,
**So that** je peux configurer des stratégies sans écrire de JSON.

**Acceptance Criteria:**

- **Given** je suis sur la page Config > Exit
- **When** je vois la liste des stratégies
- **Then** je vois:
  - Les 5 presets (badge "Default")
  - Mes stratégies custom (badge "Active" ou "Draft")
  - Bouton "New Strategy"

- **Given** je crée/édite une stratégie
- **When** l'éditeur s'ouvre
- **Then** je peux configurer via formulaire:
  - Nom et description
  - Take Profits (ajouter/supprimer niveaux, drag to reorder)
  - Stop Loss (slider)
  - Trailing Stop (toggle + config)
  - Moonbag (toggle + % + SL optionnel)
  - Time Rules (max hold, stagnation)

- **Given** je configure les Take Profits
- **When** j'ajoute un niveau
- **Then** je vois un formulaire:
  - Multiplier (ex: 2.0x)
  - Sell % (ex: 50%)
- **And** les niveaux sont auto-triés par multiplier

**Mockup - Editor:**
```
┌─────────────────────────────────────────────────────────────┐
│ Edit Strategy: My Custom Strategy                    [Draft] │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Name: [My Custom Strategy        ]                           │
│ Description: [Aggressive moonbag with tight trailing]        │
│                                                              │
│ ─── Take Profits ──────────────────────────────────────────  │
│ │ 2.0x → Sell 33% │ [Edit] [×]                               │
│ │ 3.0x → Sell 50% │ [Edit] [×]                               │
│ │ 5.0x → Sell 100% │ [Edit] [×]                              │
│ [+ Add Level]                                                │
│                                                              │
│ ─── Stop Loss ─────────────────────────────────────────────  │
│ [████████░░] 50%                                             │
│                                                              │
│ ─── Trailing Stop ─────────────────────────────────────────  │
│ [✓] Enabled                                                  │
│ Activation: [2.0]x    Distance: [30]%                        │
│                                                              │
│ ─── Moonbag ───────────────────────────────────────────────  │
│ [✓] Enabled                                                  │
│ Keep: [25]%    Stop Loss: [✓] [20]% / [ ] Ride to zero       │
│                                                              │
│ ─── Time Rules ────────────────────────────────────────────  │
│ Max Hold: [168] hours                                        │
│ [ ] Stagnation Exit                                          │
│                                                              │
│                     [Cancel] [Save Draft] [Activate]         │
└─────────────────────────────────────────────────────────────┘
```

**Story Points:** 8

---

### 11-10: UI - Exit Strategy Simulator

**As** the operator,
**I want** une interface pour simuler des stratégies sur mes positions passées,
**So that** je peux visualiser et comparer les résultats.

**Acceptance Criteria:**

- **Given** je suis sur la page d'une position clôturée
- **When** je clique sur "Simulate Exit Strategies"
- **Then** un panneau s'ouvre avec:
  - Graphique du prix historique
  - Points de sortie réels marqués
  - Dropdown pour sélectionner une stratégie à simuler

- **Given** je sélectionne une stratégie
- **When** la simulation tourne
- **Then** je vois sur le graphique:
  - Points de sortie simulés (différente couleur)
  - Zones TP atteintes
  - Point SL ou trailing stop
- **And** je vois le P&L simulé vs réel

- **Given** je veux comparer plusieurs stratégies
- **When** je clique "Compare All"
- **Then** je vois un tableau comparatif
- **And** la meilleure stratégie est mise en évidence

**Mockup - Simulator:**
```
┌─────────────────────────────────────────────────────────────┐
│ Exit Strategy Simulator - Position #123                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ [Price Chart with Entry/Exit Points]                         │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │     ●───────────●────────●─────────────●                │ │
│ │    Entry      TP1       TP2      Actual Exit            │ │
│ │                 ◆         ◆                             │ │
│ │              Simulated exits (Conservative)             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ Strategy: [Conservative        ▼]  [Run Simulation]          │
│                                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Results                                                  │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ Actual Result:     +30% (+0.15 SOL)                      │ │
│ │ Simulated Result:  +45% (+0.22 SOL)                      │ │
│ │ Difference:        +15% (+0.07 SOL) ✓ Better             │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ [Compare All Strategies]                                     │
│                                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Strategy         │ Simulated │ Actual │ Delta │          │ │
│ ├──────────────────┼───────────┼────────┼───────┤          │ │
│ │ Conservative     │ +45%      │ +30%   │ +15%  │ ★ Best   │ │
│ │ Balanced         │ +38%      │ +30%   │ +8%   │          │ │
│ │ Quick Flip       │ +22%      │ +30%   │ -8%   │          │ │
│ │ Diamond Hands    │ +12%      │ +30%   │ -18%  │          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│             [Use Conservative for Future Positions]          │
└─────────────────────────────────────────────────────────────┘
```

**Story Points:** 8

---

### 11-11: Assignment - Stratégie par Conviction Tier

**As** the operator,
**I want** assigner une stratégie de sortie par défaut selon le niveau de conviction,
**So that** les positions high conviction utilisent automatiquement Diamond Hands et les standards utilisent Balanced.

**Acceptance Criteria:**

- **Given** je suis sur la page Config > Exit
- **When** je vois la section "Default Assignments"
- **Then** je vois:
  - High Conviction: [Dropdown: stratégie]
  - Standard: [Dropdown: stratégie]

- **Given** je change l'assignment pour High Conviction
- **When** une nouvelle position high conviction est créée
- **Then** elle utilise automatiquement la stratégie assignée

- **Given** une position existe avec une stratégie
- **When** je veux override manuellement
- **Then** je peux assigner une stratégie spécifique à cette position
- **And** ça override l'assignment par défaut

**Story Points:** 3

---

## Implementation Order

```
Phase 1: Foundation (Stories 11-1 à 11-3)
├── 11-1: Schema et Migration
├── 11-2: ConfigService
└── 11-3: Migration des Composants

Phase 2: API & UI Config (Stories 11-4 à 11-6)
├── 11-4: API Endpoints
├── 11-5: UI Page Config
└── 11-6: UI Historique

Phase 3: Exit Strategies (Stories 11-7 à 11-11)
├── 11-7: Exit CRUD & Versioning
├── 11-8: Simulation Engine
├── 11-9: UI Editor
├── 11-10: UI Simulator
└── 11-11: Assignment par Tier
```

---

## Story Points Summary

| Story | Points | Priority |
|-------|--------|----------|
| 11-1: Schema Migration | 3 | P0 |
| 11-2: ConfigService | 5 | P0 |
| 11-3: Component Migration | 8 | P0 |
| 11-4: API Endpoints | 5 | P1 |
| 11-5: UI Config Page | 8 | P1 |
| 11-6: UI History | 3 | P2 |
| 11-7: Exit CRUD | 5 | P1 |
| 11-8: Simulation Engine | 8 | P1 |
| 11-9: UI Exit Editor | 8 | P2 |
| 11-10: UI Simulator | 8 | P2 |
| 11-11: Assignment | 3 | P2 |
| **Total** | **64** | |

---

## Definition of Done

- [ ] Toutes les tables de config créées avec lifecycle
- [ ] ConfigService fonctionnel avec cache et hot-reload
- [ ] Plus aucune constante hardcodée (sauf fallbacks)
- [ ] API CRUD complète pour toutes les configs
- [ ] UI Config avec édition et historique
- [ ] 5 presets exit strategy migrés avec status=default
- [ ] Exit simulator fonctionnel sur positions passées
- [ ] UI Editor pour créer des stratégies custom
- [ ] UI Simulator avec comparaison
- [ ] Tests pour ConfigService et Simulator
- [ ] Documentation mise à jour

---

## Données Requises pour Simulation

Pour que la simulation fonctionne, il faut stocker ou récupérer:

1. **Price History** - Prix du token pendant la durée de la position
   - Source: DexScreener API (candles)
   - Granularité: 1 minute idéalement, 5 min acceptable
   - Stockage: `position_price_history` ou fetch on-demand

2. **Position Timeline** - Events de la position
   - Entry time, entry price
   - Each exit (TP hit, SL hit, trailing, time exit)
   - Final close time, final price

3. **Exit Strategy Used** - Stratégie appliquée
   - Référence vers la stratégie utilisée
   - Paramètres au moment de l'application

---

## Technical Decisions

### Q: Pourquoi une seule config `active` par table ?
**A:** Simplicité. Le système lit toujours la config active. Pas de logique de sélection complexe.

### Q: Pourquoi cache de 60s et pas temps réel ?
**A:** Compromis performance/réactivité. 60s est suffisant pour les ajustements non-urgents. Pour les urgences (circuit breaker), le code peut forcer un `refresh()`.

### Q: Pourquoi simuler sur positions passées uniquement ?
**A:** Les positions actives évoluent en temps réel. Simuler sur le passé donne des résultats définitifs et comparables.

### Q: Comment gérer les price history manquants ?
**A:** Fetch on-demand via DexScreener. Cache pendant 24h. Si indisponible, simulation impossible avec message clair.
