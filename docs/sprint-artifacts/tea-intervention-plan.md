# Plan d'Intervention TEA (Test Architect)

**Projet:** WallTrack
**Date:** 2025-12-16
**Agent:** Murat (TEA - Master Test Architect)

---

## Stratégie en 3 Points

| Point | Timing | Workflow | Objectif | Status |
|-------|--------|----------|----------|--------|
| **1** | Sprint 0 / Epic 1 | `*test-design` | Architecture de testabilité | ✅ FAIT |
| **2** | Après Epic 6 | `*framework` | Setup Playwright + fixtures Gradio | ✅ FAIT |
| **3** | Après Epic 8 | `*automate` + `*trace` | Suite E2E complète + quality gate | ⏳ À venir |

---

## Point 1 : Test Design (COMPLÉTÉ)

**Date:** 2025-12-16

### Livrables

- [x] `docs/test-design-system.md` - Document de testabilité système
- [x] `docs/TESTING.md` - Guide des conventions de test
- [x] `pyproject.toml` - Configuration pytest, ruff, mypy, coverage
- [x] `tests/conftest.py` - Fixtures partagées
- [x] `tests/factories/` - Factories pour Wallet, Signal, Trade
- [x] Structure de tests alignée avec l'architecture

### Décisions Clés

| Décision | Choix |
|----------|-------|
| Test levels | Unit 50% / Integration 35% / E2E 15% |
| Coverage cible | >= 80% |
| Framework UI | Playwright (post Epic 6) |
| Factories | factory-boy + Faker |
| Mocking HTTP | respx |

### Concerns Identifiés

| ID | Concern | Action | Status |
|----|---------|--------|--------|
| TC-001 | Gradio sans elem_id | Convention documentée dans TESTING.md | ✅ |
| TC-002 | Pas de factory pattern | factories/ créé | ✅ |
| TC-003 | Async cleanup | Fixtures dans conftest.py | ✅ |
| TC-004 | API mocking | respx installé | ✅ |

---

## Point 2 : Framework Setup (COMPLÉTÉ)

**Date:** 2025-12-21

### Livrables

- [x] `pytest-playwright>=0.5.0` ajouté à pyproject.toml
- [x] Chromium installé via `playwright install`
- [x] `tests/e2e/conftest.py` - Fixtures Playwright pour Gradio
- [x] `tests/e2e/gradio/test_dashboard.py` - Tests E2E initiaux
- [x] `tests/e2e/README.md` - Documentation des tests E2E
- [x] `elem_id` ajoutés aux composants Gradio critiques

### Composants Instrumentés (elem_id)

| Fichier | Éléments |
|---------|----------|
| `dashboard.py` | main-tabs, tab-status/wallets/clusters/signals/positions/performance/config |
| `config_panel.py` | config-wallet-weight, config-cluster-weight, config-token-weight, config-context-weight, config-apply-weights-btn, config-normalize-btn, config-reset-btn, config-trade-threshold, config-high-conviction |
| `wallets.py` | wallets-table, wallets-refresh-btn, wallets-status-filter, wallets-min-score, wallets-new-address, wallets-add-btn, wallets-blacklist-btn |
| `positions.py` | positions-table, positions-refresh-btn, positions-id-input, history-table, history-date-from, history-date-to, history-pnl-filter, history-search-btn |

### Tests E2E Créés

| Classe | Tests |
|--------|-------|
| `TestDashboardLoads` | title_visible, subtitle_visible, main_tabs_visible |
| `TestTabNavigation` | navigate_to_wallets, navigate_to_config, navigate_to_positions, tab_round_trip |
| `TestWalletsTab` | table_exists, filter_options, add_wallet_input |
| `TestConfigTab` | weight_sliders, threshold_sliders, reset_button |
| `TestPositionsTab` | table_exists, trade_history_tab, history_filters |

### Commandes

```bash
# Lancer les tests E2E (nécessite dashboard actif sur :7865)
uv run pytest tests/e2e -m e2e

# Mode visuel
HEADED=1 uv run pytest tests/e2e -m e2e
```

---

## Point 3 : Automation Complète (APRÈS EPIC 8)

**Trigger:** Quand tout le système est implémenté

### Objectifs

- [ ] Générer la suite de tests E2E complète
- [ ] Créer la matrice de traçabilité (requirements → tests)
- [ ] Évaluer la couverture NFR
- [ ] Décision quality gate (PASS/CONCERNS/FAIL)

### Workflows à Exécuter

```
*automate    # Génération tests E2E
*trace       # Traçabilité + quality gate
*nfr-assess  # Validation NFRs (optionnel)
```

### Critères Quality Gate

| Critère | Seuil |
|---------|-------|
| P0 tests pass rate | 100% |
| P1 tests pass rate | >= 95% |
| High-risk mitigations | 100% complete |
| Coverage critical paths | >= 80% |

---

## ASRs Critiques (à surveiller)

| ASR | Score | Description |
|-----|-------|-------------|
| ASR-003 | **9** | HMAC validation Helius |
| ASR-004 | **9** | Private keys env-only |
| ASR-001 | 6 | Signal-to-trade < 5s |
| ASR-002 | 6 | Webhook processing < 500ms |
| ASR-005 | 6 | Zero data loss |

---

## Commandes Utiles

```bash
# Tests unitaires (rapide)
uv run pytest -m unit

# Tests avec coverage
uv run pytest --cov=walltrack --cov-fail-under=80

# Tests E2E (nécessite dashboard actif)
uv run pytest tests/e2e -m e2e

# Tests E2E mode visuel
HEADED=1 uv run pytest tests/e2e -m e2e

# Type checking
uv run mypy src/walltrack --strict

# Linting
uv run ruff check src/

# Tout vérifier
uv run ruff check src/ && uv run mypy src/walltrack --strict && uv run pytest --cov=walltrack
```

---

## Pour Invoquer TEA

```
/bmad:bmm:agents:tea
```

Puis sélectionner le workflow approprié dans le menu.

---

**Note:** Ce document sera mis à jour après chaque intervention TEA.
