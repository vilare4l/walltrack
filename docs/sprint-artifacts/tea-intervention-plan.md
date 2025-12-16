# Plan d'Intervention TEA (Test Architect)

**Projet:** WallTrack
**Date:** 2025-12-16
**Agent:** Murat (TEA - Master Test Architect)

---

## Stratégie en 3 Points

| Point | Timing | Workflow | Objectif | Status |
|-------|--------|----------|----------|--------|
| **1** | Sprint 0 / Epic 1 | `*test-design` | Architecture de testabilité | ✅ FAIT |
| **2** | Après Epic 6 | `*framework` | Setup Playwright + fixtures Gradio | ⏳ À venir |
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

## Point 2 : Framework Setup (APRÈS EPIC 6)

**Trigger:** Quand le dashboard Gradio est fonctionnel

### Objectifs

- [ ] Installer Playwright pour Python
- [ ] Configurer les fixtures Gradio (browser, page)
- [ ] Créer les premiers tests E2E du dashboard
- [ ] Valider que tous les `elem_id` sont en place

### Workflow à Exécuter

```
*framework
```

### Prérequis

- Dashboard Gradio déployé localement
- Tous les composants interactifs ont `elem_id`
- Epic 6 (Feedback Loop) complété

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
