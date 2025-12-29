# WallTrack Rebuild V2 - Notes Architecte

_Document de travail pour la reconstruction progressive du projet_

---

## Contexte

**Date:** 2025-12-28
**Raison du rebuild:** Trop de revirements de trajectoire ont corrompu la cohérence du codebase. Les tests E2E Gradio tournent en rond. Décision de repartir progressivement en validant chaque étape.

**Approche:** Reconstruction incrémentale avec validation (UI + test E2E) à chaque étape.

---

## Analyse de l'Architecture V1

### Ce qui fonctionnait bien

| Module | État | Notes |
|--------|------|-------|
| Discovery tokens | OK | Pipeline de base fonctionnel |
| Discovery wallets | OK | Extraction depuis tokens |
| Stack technique | OK | FastAPI, Gradio, Supabase, Neo4j |
| Pydantic models | OK | Validation solide |

### Ce qui a dérivé

| Problème | Cause | Impact |
|----------|-------|--------|
| Explosion des modules services/ | Refactoring successifs | 15+ sous-modules au lieu de 4-5 |
| Duplication core/ vs services/ | Frontières floues | cluster/, scoring/, wallet/ en double |
| Tests E2E non fonctionnels | UI instable | Impossible de valider le flux |
| Modules supprimés en cours de route | Pivots de direction | backtest, simulation, feedback |

### Complexité accumulée

**Structure V1 (réelle):**
```
services/
├── alerts/
├── birdeye/
├── cluster/        <- duplique core/cluster/
├── config/
├── dexscreener/
├── execution/
├── exit/
├── helius/
├── jupiter/
├── order/
├── positions/
├── pricing/
├── raydium/
├── risk/
├── scoring/        <- duplique core/scoring/
├── signal/
├── solana/
├── token/
├── trade/
└── wallet/         <- duplique discovery/
```

**Problème:** Impossible de savoir où mettre la logique. Trop de choix = incohérence.

---

## Architecture V2 Simplifiée

### Principes directeurs

1. **UN seul endroit pour chaque responsabilité**
2. **services/ = clients API externes UNIQUEMENT**
3. **core/ = logique métier UNIQUEMENT**
4. **Valider chaque étape avant la suivante**

### Structure cible

```
src/walltrack/
├── api/
│   └── routes/
│       ├── health.py
│       ├── webhooks.py       # Helius inbound
│       ├── discovery.py      # Tokens + Wallets
│       ├── clusters.py
│       ├── signals.py
│       ├── positions.py
│       ├── orders.py
│       └── config.py
│
├── core/                     # LOGIQUE MÉTIER
│   ├── discovery/            # Token + Wallet discovery
│   │   ├── token_scanner.py
│   │   ├── wallet_scanner.py
│   │   └── profiler.py
│   ├── cluster/              # Profiling + Clustering
│   │   ├── analyzer.py
│   │   └── grouping.py
│   ├── signal/               # Scoring + Filtering
│   │   ├── scorer.py
│   │   ├── filter.py
│   │   └── pipeline.py
│   ├── position/             # Position management
│   │   └── manager.py
│   ├── order/                # Entry + Exit UNIFIÉ
│   │   ├── entry.py
│   │   └── exit.py
│   └── risk/                 # Risk management
│       └── manager.py
│
├── data/
│   ├── models/               # Pydantic models (UN SEUL endroit)
│   ├── supabase/
│   │   ├── client.py
│   │   └── repositories/
│   └── neo4j/
│       ├── client.py
│       └── queries/
│
├── services/                 # CLIENTS API EXTERNES SEULEMENT
│   ├── base.py               # BaseAPIClient avec retry
│   ├── helius/               # Webhooks management
│   ├── jupiter/              # Swap execution
│   ├── dexscreener/          # Token data
│   └── solana/               # RPC client
│
├── ui/
│   ├── dashboard.py
│   └── components/
│
├── config/
│   └── settings.py
│
└── scheduler/
    └── tasks/
```

### Réduction de complexité

| V1 | V2 | Changement |
|----|----|-----------:|
| 19 sous-modules services/ | 4 clients API | -79% |
| 2 endroits pour models | 1 seul (data/models/) | -50% |
| Frontières floues | Responsabilités claires | - |

---

## Plan de Reconstruction

### Flow fonctionnel (Mode Simulation)

```
1. Discovery tokens (manuel)
      ↓
2. Surveillance tokens (périodique)
      ↓
3. Discovery wallets depuis tokens
      ↓
4. Profiling + Clustering (Neo4j)
      ↓
5. Construction webhooks Helius (tokens watchlist)
      ↓
6. Réception alertes webhooks
      ↓
7. Scoring signals
      ↓
8. Création position
      ↓
9. Order entrée + sizing (risk management)
      ↓
10. Préparation order sortie (exit strategy)
      ↓
11. Exécution sortie
```

### Étapes de reconstruction

| # | Étape | Core | UI | Settings | Test E2E | Status |
|---|-------|------|----|---------| ---------|--------|
| 1 | Discovery Tokens | token_scanner.py | Tab Discovery | Sources, filtres | Lancer discovery → tokens listés | TODO |
| 2 | Surveillance Tokens | scheduler task | Status scheduler | Intervalle | Tokens rafraîchis automatiquement | TODO |
| 3 | Discovery Wallets | wallet_scanner.py | Tab Wallets | Seuils volume | Token → wallets trouvés | TODO |
| 4 | Profiling + Clustering | cluster/ + Neo4j | Tab Clusters | Params clustering | Clusters affichés | TODO |
| 5 | Webhooks Helius | services/helius/ | Tab Watchlist | API keys, events | Webhook créé sur Helius | TODO |
| 6 | Signals | signal/ | Tab Signals | Seuils scoring | Webhook reçu → signal scoré | TODO |
| 7 | Positions | position/ | Tab Positions | Risk %, sizing | Position créée | TODO |
| 8 | Orders | order/ | Tab Orders | Exit strategies | Orders entry/exit visibles | TODO |

### Règle d'or

**CHAQUE ÉTAPE DOIT ÊTRE:**
1. Implémentée (core + API)
2. Configurable (settings)
3. Visible (UI Gradio)
4. Testée (E2E qui passe)
5. **VALIDÉE avant de passer à l'étape suivante**

---

## Stack technique conservée

| Technologie | Usage | Pourquoi garder |
|-------------|-------|-----------------|
| Python 3.11+ | Runtime | Stable, typé |
| FastAPI | API | Async, moderne |
| Gradio | Dashboard | Rapide à prototyper |
| Supabase | Données, config | Fonctionne bien |
| Neo4j | Clusters/relations | Adapté aux graphes |
| httpx | HTTP async | Fiable |
| Pydantic v2 | Validation | Intégré FastAPI |
| structlog | Logging | Structuré |

## Stack retirée (pour V2)

| Technologie | Raison retrait |
|-------------|----------------|
| XGBoost/ML | Trop tôt, V3+ |
| Backtest engine | Supprimé, pas prioritaire |
| Simulation complexe | Simplifié |

---

## Leçons apprises

1. **Trop de modules = confusion** - Garder une structure plate et claire
2. **Frontières floues = duplication** - services/ UNIQUEMENT pour API externes
3. **Tester au fur et à mesure** - Pas d'empilement sans validation
4. **L'UI doit fonctionner** - Si on ne peut pas voir, on ne peut pas valider
5. **Simplicité > Sophistication** - Commencer simple, complexifier si nécessaire

---

## Références

- Code legacy: `./legacy/src/` et `./legacy/tests/`
- Architecture V1: `./docs/architecture.md`
- PRD: `./docs/prd.md`
- Brief produit: `./docs/analysis/product-brief-walltrack-2025-12-15.md`

---

_Document vivant - mis à jour au fil de la reconstruction_
