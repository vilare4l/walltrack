# WallTrack - Project Context

Ce fichier contient les informations critiques pour tous les agents IA travaillant sur ce projet.

## Phase actuelle

**Rebuild V2** - Reconstruction from scratch, epic par epic.

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3.11+, FastAPI |
| UI | Gradio |
| Base relationnelle | Supabase (PostgreSQL) |
| Base graphe | Neo4j |
| HTTP client | httpx (async) |
| Validation | Pydantic v2 |
| Package manager | uv |

## Structure projet

```
walltrack/
├── src/                 # Code V2 (en construction)
├── tests/               # Tests V2
├── docs/                # Documentation active
└── legacy/              # Code V1 (référence seulement, ne pas modifier)
```

## Infrastructure de test

### Stack de test
- **pytest-playwright** - Tests E2E
- **factory-boy + Faker** - Génération de données
- **pytest-asyncio** - Tests async

### Structure tests/
```
tests/
├── conftest.py              # Fixtures Playwright, config env
├── e2e/                     # Tests E2E (Playwright)
│   └── test_example.py      # Templates + exemples
├── support/
│   ├── factories/           # WalletFactory, TokenFactory, SignalFactory
│   ├── helpers/             # wait_for_condition, format_sol_amount
│   └── page_objects/        # Page Object Model (par story)
```

### Commandes
```bash
uv run pytest                    # Tous les tests
uv run pytest -m e2e             # E2E seulement
uv run pytest -m smoke           # Smoke tests (CI)
```

### Factories disponibles
- `WalletFactory`, `HighPerformanceWalletFactory`, `DecayedWalletFactory`
- `TokenFactory`, `NewTokenFactory`, `MatureTokenFactory`
- `SignalFactory`, `ActionableSignalFactory`, `HighConvictionSignalFactory`

### Workflow Dev
1. Story a des tests skippés dans `tests/e2e/`
2. Enlever le `@pytest.mark.skip`
3. Coder jusqu'à ce que le test passe
4. Utiliser les factories pour les données de test

## Règles de développement

### Consultation Legacy (OBLIGATOIRE)

Avant de développer une fonctionnalité, **toujours** vérifier dans `legacy/src/` si une implémentation existe:

1. **Chercher** le code existant dans `legacy/src/walltrack/`
2. **Extraire** les patterns qui fonctionnent (à reproduire)
3. **Identifier** les anti-patterns (à éviter)
4. **Documenter** dans la story: "Legacy Reference" section

**Objectif:** Ne pas réinventer la roue, apprendre des erreurs V1.

**Structure legacy complète:**
```
legacy/
├── docs/        # Documentation V1 (PRD, architecture, notes)
├── migrations/  # Migrations SQL Supabase (schéma DB, triggers, RLS)
├── scripts/     # Scripts utilitaires (setup, déploiement)
├── src/         # Code source V1
└── tests/       # Tests V1 (patterns, fixtures)
```

**Emplacements clés par domaine:**
| Domaine | Location | À regarder pour |
|---------|----------|-----------------|
| API Clients | `legacy/src/walltrack/services/base.py` | BaseAPIClient, retry, circuit breaker |
| Exceptions | `legacy/src/walltrack/core/exceptions.py` | Hiérarchie d'erreurs |
| Circuit Breaker | `legacy/src/walltrack/core/risk/` | Logique drawdown, persistence |
| Data Layer | `legacy/src/walltrack/data/` | Models Pydantic, repos |
| UI Gradio | `legacy/src/walltrack/ui/` | Patterns dashboard, components |
| **DB Schema** | `legacy/migrations/` | Tables, triggers, RLS policies |
| **Scripts** | `legacy/scripts/` | Setup, seed data |
| **Tests** | `legacy/tests/` | Fixtures, patterns de test |

---

## Conventions

### Code style
- Ruff pour linting/formatting
- Type hints obligatoires
- Docstrings pour fonctions publiques

### Commits
- Format conventionnel : `feat:`, `fix:`, `refactor:`, `test:`, `docs:`
- En anglais

### Tests
- Format Given-When-Then dans les docstrings
- Sélecteurs : `data-testid` uniquement (pas de classes CSS)
- Timeouts : action 15s, navigation 30s, expect 10s

## Référence

- `docs/prd.md` - Product Requirements
- `docs/architecture.md` - Architecture technique
- `docs/epics.md` - Epics et stories
- `legacy/src/` - Code V1 (pour référence d'implémentation)
