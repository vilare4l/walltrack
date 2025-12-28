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

## Stack technique

- Python 3.11+ / FastAPI / Gradio
- Supabase (PostgreSQL) - données, config
- Neo4j - clusters/relations wallets
- httpx async / Pydantic v2

---

## Flow fonctionnel à reconstruire

1. Discovery tokens (manuel)
2. Surveillance tokens (scheduler)
3. Discovery wallets
4. Profiling + Clustering (Neo4j)
5. Webhooks Helius
6. Scoring signals
7. Positions
8. Orders (entry/exit)

---

## Communication

- Langue: Français
- Utilisateur: Christophe
- Approche: Pédagogique - expliquer chaque étape
