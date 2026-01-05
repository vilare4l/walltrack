# WallTrack - Contexte Projet

## Phase actuelle: Rebuild V2

On reconstruit le projet de zéro, étape par étape, en validant chaque fonctionnalité (UI + test E2E) avant de passer à la suivante.

---

## Structure du projet

```
walltrack/
├── src/                 # NOUVEAU CODE V2 (en construction)
├── tests/               # NOUVEAUX TESTS V2
├── docs/                # Documentation active
│   ├── prd.md           # Product Requirements (référence)
│   ├── architecture.md  # Architecture V1 (référence)
│   └── rebuild-v2-notes.md  # Notes de reconstruction
│
└── legacy/              # CODE V1 - DOCUMENTATION SEULEMENT
    ├── src/             # Ancien code (ne pas modifier)
    ├── tests/           # Anciens tests
    ├── docs/            # Anciens documents
    ├── migrations/      # SQL migrations V1
    └── scripts/         # Scripts V1
```

---

## Règles importantes

1. **Ne jamais modifier `legacy/`** - C'est de la documentation/référence
2. **Consulter `legacy/src/`** pour voir comment c'était implémenté
3. **Nouveau code dans `src/`** uniquement
4. **Valider chaque étape** avant de passer à la suivante (UI + test E2E)

---

## Règles OBLIGATOIRES pour les agents

### 1. Consultation Legacy (AVANT de coder)

**TOUJOURS** vérifier dans `legacy/` avant de développer :

| Domaine | Où chercher |
|---------|-------------|
| API Clients | `legacy/src/walltrack/services/base.py` |
| Exceptions | `legacy/src/walltrack/core/exceptions.py` |
| Data Layer | `legacy/src/walltrack/data/` |
| UI Gradio | `legacy/src/walltrack/ui/` |
| **DB Schema** | `legacy/migrations/` |
| Tests | `legacy/tests/` |

**Objectif:** Ne pas réinventer la roue, reproduire les patterns qui marchent.

### 2. Migrations DB (OBLIGATOIRE)

**La base Supabase V2 est VIDE.** Les migrations dans `legacy/migrations/` sont de la **documentation seulement**.

**Toute création de table ou modification de schéma DOIT s'accompagner d'une migration SQL dans V2 :**

```
src/walltrack/data/supabase/migrations/
├── 001_config_table.sql      # Exemple
├── 002_tokens_table.sql
└── ...
```

**Workflow:**
1. Consulter `legacy/migrations/` pour voir le schéma V1 (référence)
2. Créer la migration V2 dans `src/walltrack/data/supabase/migrations/`
3. Exécuter la migration sur Supabase

**Format migration:**
```sql
-- Migration: NNN_description.sql
-- Date: YYYY-MM-DD
-- Story: X.Y

CREATE TABLE IF NOT EXISTS walltrack.table_name (
    ...
);

-- Rollback (commenté)
-- DROP TABLE IF EXISTS walltrack.table_name;
```

**Ne JAMAIS supposer qu'une table existe** - la base V2 est vide, il faut créer les migrations.

---

## Stack technique (MVP)

- Python 3.11+ / FastAPI / Gradio
- Supabase (PostgreSQL) - données, config
- httpx async / Pydantic v2

**Future Extensions:**
- Neo4j - clusters/relations wallets (Phase 3+)

---

## Flow fonctionnel à reconstruire (MVP)

1. Discovery tokens (manuel)
2. Surveillance tokens (scheduler)
3. Discovery wallets
4. Webhooks Helius
5. Scoring signals
6. Positions
7. Orders (entry/exit)

**Future Enhancements:**
- Profiling + Clustering (Neo4j) - Phase 3+

---

## Tests

**IMPORTANT:** Ne pas lancer tous les tests ensemble. Playwright (E2E) interfère avec les autres tests.

```bash
# Tests unitaires + intégration (rapides, ~40s)
uv run pytest tests/unit tests/integration -v

# Tests E2E Playwright (séparément, ouvre le navigateur)
uv run pytest tests/e2e -v
```

**Structure des tests:**
```
tests/
├── unit/           # Tests isolés avec mocks
├── integration/    # Tests avec composants réels mockés
└── e2e/            # Tests Playwright (navigateur)
```

---

## Communication

- Langue: Français
- Utilisateur: Christophe
- Approche: Pédagogique - expliquer chaque étape
