---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - 'docs/prd.md'
  - 'docs/analysis/product-brief-walltrack-2025-12-15.md'
workflowType: 'ux-design'
lastStep: 14
status: complete
project_name: 'walltrack'
user_name: 'Christophe'
date: '2025-12-26'
context: 'UX Redesign of existing Gradio dashboard'
---

# UX Design Specification - WallTrack

**Author:** Christophe
**Date:** 2025-12-26
**Context:** UX Redesign of existing Gradio dashboard (8 tabs → simplified architecture)

---

## Executive Summary

### Project Vision

WallTrack n'est pas un simple dashboard de monitoring — c'est un **système d'intelligence stratégique** pour le trading autonome de memecoins. L'opérateur doit pouvoir :

1. **Comprendre** le flux temps réel : Signal → Wallet → Score → Position
2. **Explorer** chaque maillon avec drill-down explicatif ("pourquoi cette décision ?")
3. **Optimiser** continuellement via un agent stratégique qui teste des variantes en parallèle

### Target Users

**Persona Unique : Christophe — L'Opérateur-Stratège**

| Attribut | Réalité Terrain |
|----------|-----------------|
| **Fréquence d'usage** | Plusieurs fois par jour |
| **Mode principal** | Exploration + Compréhension |
| **Besoin critique** | Traçabilité des décisions |
| **Évolution souhaitée** | Co-pilote stratégique IA |

**Ce que l'utilisateur veut vraiment :**
- "Le système tourne-t-il ?"
- "Est-ce rentable ?"
- "D'où viennent ces positions ?"
- "Pourquoi ce wallet a été retenu ?"
- "Quelle stratégie marche le mieux ?"

### Key Design Challenges

1. **Flux Opaque** — L'architecture actuelle (8 onglets) cache la logique métier. L'utilisateur ne peut pas tracer le raisonnement derrière chaque décision

2. **Navigation Déconnectée** — Chaque onglet est une île. Pas de drill-down contextuel (cliquer wallet → voir signaux associés)

3. **Pas de Synthèse** — Aucun "Home Dashboard" qui répond aux questions essentielles en 5 secondes

4. **Agent Absent** — Pas de capacité de test multi-stratégies ni d'optimisation assistée

### Design Opportunities

1. **Drill-Down Explicatif** — Chaque signal/position répond à "pourquoi ?" en un clic

2. **Navigation Contextuelle** — Chaque élément (wallet, signal, position) devient un point d'entrée vers ses connexions

3. **Dashboard Synthétique** — Répondre à "ça marche ?" en 5 secondes avec des KPIs visuels

4. **Agent Stratégique** — Interface pour définir, tester et comparer des stratégies parallèles avec recommandations IA

---

## Core UX Principles

### Principe 1 : Flux Temps Réel, Pas Archéologie

Le point d'entrée est **l'action en cours**, pas l'historique :

```
              TEMPS RÉEL (point d'entrée)
                       │
                       ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  SIGNAL  │───▶│  WALLET  │───▶│  SCORE   │───▶│ POSITION │
│ Incoming │    │  Source  │    │ Décision │    │  Active  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      │               │
      │               └──── DRILL-DOWN : "Pourquoi ce wallet ?"
      │                            │
      │                            ▼
      │               ┌─────────────────────────┐
      │               │ CONTEXTE (info, pas UI) │
      │               │ • Découvert sur pump X  │
      │               │ • Win rate 78%          │
      │               │ • Cluster avec Y, Z     │
      │               │ • Historique trades     │
      │               └─────────────────────────┘
      │
      └──── L'origine (pump) est une INFO de contexte
            pas le point de départ de la navigation
```

### Principe 2 : Deux Modes de Navigation

| Mode | Point d'entrée | Question | Usage |
|------|---------------|----------|-------|
| **Opérationnel** | Signal / Position | "Pourquoi cette décision ?" | Quotidien |
| **Exploration** | Discovery / Wallet | "Qu'est-ce qu'on a trouvé ?" | Occasionnel |

### Principe 3 : Agent Stratégique = Exit Optimizer

Focus uniquement sur les **stratégies de sortie** — le seul domaine où la comparaison est actionnable :

```
Position active → "Ma stratégie : TP à 2x, trailing 15%"
               → "Simulation : moonbag 20% aurait donné +45%"
               → "Recommandation : considérer moonbag pour high-conviction"
```

- Compare take-profit, trailing stop, moonbag sur positions réelles
- Simulations sur historique des positions passées
- Découverte et profiling = paramètres fixes, pas de comparaison (archéologie inutile)

---

## Nouvelle Architecture Proposée

**De 8 onglets déconnectés → 4 espaces cohérents :**

| Espace | Icône | Fonction | Contenu Principal |
|--------|-------|----------|-------------------|
| **Home** | 🏠 | Synthèse instantanée | Statut système, P&L, alertes, positions actives avec drill-down |
| **Explorer** | 🔍 | Navigation dans le flux | Signaux → Wallets → Clusters avec contexte explicatif |
| **Lab** | 🧪 | Exit Optimizer | Comparaison stratégies de sortie sur positions réelles, simulations, recommandations |
| **Config** | ⚙️ | Paramètres | Scoring, thresholds, webhooks, système |

---

## Core User Experience

### Defining Experience

L'expérience fondamentale de WallTrack est la **compréhension instantanée** :

| Question | Temps cible | Point d'entrée |
|----------|-------------|----------------|
| "Ça tourne ?" | < 2 sec | Home - Statut système |
| "C'est rentable ?" | < 5 sec | Home - KPIs P&L |
| "Pourquoi cette position ?" | 1 clic | Position → Drill-down |
| "D'où vient ce wallet ?" | 1 clic | Wallet → Contexte découverte |

**Core Loop** :
```
Signal (temps réel) → "Pourquoi ?" → Wallet source → "Pourquoi lui ?" → Score + Clusters
```

Le point d'entrée est **toujours l'action en cours**, pas l'historique.

### Platform Strategy

| Aspect | Choix | Justification |
|--------|-------|---------------|
| **Plateforme** | Web (Gradio) | Infrastructure existante, pas d'installation |
| **Device** | Desktop-first | Trading = écran large, multitâches |
| **Input** | Souris + Clavier | Précision pour explorer les données |
| **Responsive** | Non prioritaire | Usage bureau exclusif |
| **Offline** | Non requis | Système temps réel, connexion obligatoire |

### Effortless Interactions

**Ce qui doit être invisible :**

1. **Statut système** — Visible en permanence sans action (badge/indicateur)
2. **Navigation contextuelle** — Cliquer un élément = voir ses connexions
3. **Drill-down explicatif** — Chaque décision répond à "pourquoi ?"
4. **Rafraîchissement** — Temps réel, pas de bouton refresh manuel

**Ce qui doit être explicite :**

1. **Actions destructives** — Blacklist, stop position (confirmation)
2. **Modifications de stratégie** — Changement de paramètres (preview impact)

### Critical Success Moments

| Moment | Critère de succès | Risque si raté |
|--------|-------------------|----------------|
| **Ouverture dashboard** | "Je sais si ça marche" en 2 sec | Anxiété, sur-vérification |
| **Clic sur position** | Je comprends toute la chaîne décisionnelle | Perte de confiance dans le système |
| **Premier wallet drill-down** | "Ah, je comprends pourquoi il est là" | Frustration, sentiment de boîte noire |
| **Comparaison exit strategies** | Données claires pour décider | Paralysie décisionnelle |

### Experience Principles

1. **Temps Réel, Pas Archéologie**
   - Point d'entrée = ce qui se passe maintenant
   - L'historique est du contexte, pas le point de départ

2. **Chaque Élément Est Un Point D'Entrée**
   - Signal, Wallet, Position = cliquable vers ses connexions
   - Pas de cul-de-sac navigationnel

3. **"Pourquoi ?" En Un Clic**
   - Chaque décision du système est explicable
   - Drill-down = contexte complet (origine, métriques, relations)

4. **Synthèse D'Abord, Détails Ensuite**
   - Home = réponses en 5 secondes
   - Explorer = profondeur à la demande

5. **Exit Optimizer, Pas Wizard Généraliste**
   - Focus stratégies de sortie uniquement
   - Compare sur positions réelles, pas hypothèses
   - Découverte et profiling = paramètres fixes

---

## Desired Emotional Response

### Primary Emotional Goals

| Émotion | Manifestation | Anti-pattern |
|---------|---------------|--------------|
| **Confiance** | "Je sais que ça tourne" | Doute permanent, sur-vérification |
| **Contrôle** | "Je peux intervenir si besoin" | Impuissance face à l'automatisation |
| **Compréhension** | "Je sais pourquoi cette décision" | Boîte noire opaque |

**Hiérarchie émotionnelle :**
1. **Sérénité** — Le système fonctionne, je peux vaquer
2. **Curiosité satisfaite** — Chaque question trouve sa réponse en 1 clic
3. **Sentiment de maîtrise** — Je comprends la logique, je peux l'ajuster

### Emotional Journey Mapping

| Moment | Émotion visée | Design implication |
|--------|---------------|-------------------|
| **Ouverture dashboard** | Soulagement ou alerte claire | Statut visible en < 2 sec |
| **Vérification "ça tourne"** | Confiance que c'est vivant | Indicateurs de processus actifs |
| **Exploration signal** | Curiosité → Satisfaction | Drill-down fluide, pas de cul-de-sac |
| **Découverte d'un problème** | Clarté, pas panique | Message explicite + action suggérée |
| **Comparaison exit strategies** | Confiance dans les données | Chiffres clairs, pas d'ambiguïté |
| **Retour quotidien** | Familiarité efficace | Interface stable, pas de surprises |

### Background Processes Visibility

**Processus à rendre visibles :**

| Processus | Info critique | Émotion si absent |
|-----------|---------------|-------------------|
| **Discovery Scheduler** | Dernier run, prochain run, wallets trouvés | "Est-ce que ça cherche encore ?" |
| **Signal Pipeline** | Signaux reçus aujourd'hui, dernier traité | "Les webhooks arrivent-ils ?" |
| **Profiling Jobs** | Wallets en attente, derniers profilés | "Le scoring est-il à jour ?" |
| **Webhook Sync** | Wallets monitorés, statut Helius | "On surveille bien tout le monde ?" |

**Design implication — Barre de statut permanente :**

```
┌─────────────────────────────────────────────────────┐
│  🟢 Discovery: il y a 2h (prochain: 4h)  │  143 wallets │
│  🟢 Signals: 12 aujourd'hui (dernier: 14:32)        │
│  🟢 Webhooks: sync OK                               │
└─────────────────────────────────────────────────────┘
```

→ Réponse à "c'est vivant ?" sans cliquer.

### Micro-Emotions

**Critiques pour WallTrack :**

| Paire | Importance | Pourquoi |
|-------|------------|----------|
| **Confiance ↔ Confusion** | Critique | Trading = stress. Confusion = erreurs |
| **Compréhension ↔ Opacité** | Critique | "Pourquoi ce trade ?" doit avoir une réponse |
| **Calme ↔ Anxiété** | Haute | Plusieurs visites/jour = éviter la fatigue décisionnelle |
| **"C'est vivant" ↔ "C'est mort"** | Critique | Processus background doivent être visibles |
| **Accomplissement ↔ Frustration** | Moyenne | Trouver l'info = victoire. Pas trouver = abandon |

### Design Implications

| Émotion visée | Traduction UX |
|---------------|---------------|
| **"C'est vivant"** | Barre de statut des processus background toujours visible |
| **Confiance** | Timestamps "il y a X" plutôt que dates absolues |
| **Compréhension** | Chaque élément cliquable vers son contexte |
| **Calme** | Layout épuré, hiérarchie claire, pas de surcharge |
| **Contrôle** | Actions explicites + boutons pour déclencher manuellement |
| **Curiosité satisfaite** | Drill-down répond à "pourquoi" en 1 niveau max |

**Anti-patterns à éviter :**

- ❌ Spinners de chargement longs (anxiété)
- ❌ Tableaux sans explication (opacité)
- ❌ Actions sans confirmation (perte de contrôle)
- ❌ Données sans contexte temporel (confusion)
- ❌ Absence de feedback sur processus background ("c'est mort ?")

### Emotional Design Principles

1. **Statut Avant Tout**
   - L'état du système est la première info visible
   - Vert/Rouge/Orange — pas d'ambiguïté

2. **Chaque Nombre A Une Histoire**
   - Un P&L n'est pas juste un chiffre
   - C'est cliquable vers : quelles positions, quels wallets

3. **Calme Par Défaut, Alerte Par Exception**
   - Interface neutre en fonctionnement normal
   - Couleurs vives uniquement pour anomalies

4. **Vocabulaire Humain**
   - "Ce wallet a été découvert sur le pump X" > "source_pump_id: abc123"
   - L'explication précède le code technique

5. **Pas de Cul-de-Sac**
   - Chaque écran offre une navigation vers l'avant ou l'arrière
   - "Retour" et "Voir plus" toujours disponibles

6. **Processus Visibles**
   - Background jobs affichés en permanence
   - "Il y a X" pour timestamps relatifs

---

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

#### TradingView — Données Temps Réel

| Force | Application WallTrack |
|-------|----------------------|
| **Watchlist latérale** | Liste des wallets avec statut rapide |
| **Clic → Détail** | Drill-down vers contexte wallet |
| **Indicateurs colorés** | Vert/Rouge pour P&L, statut |
| **Alertes intégrées** | Notifications de signaux high-conviction |

**Pattern clé :** Information dense mais scannable — hiérarchie visuelle claire.

#### Grafana — Monitoring de Systèmes

| Force | Application WallTrack |
|-------|----------------------|
| **Status bar** | Barre de processus background en haut |
| **Panels flexibles** | Zones KPIs, listes, graphiques |
| **Time range selector** | Filtrer par période (signaux, positions) |
| **Drill-down sur alertes** | Clic alerte → contexte complet |

**Pattern clé :** "Est-ce que tout va bien ?" répondu en < 2 secondes.

#### Linear — Navigation Contextuelle

| Force | Application WallTrack |
|-------|----------------------|
| **Sidebar persistante** | Navigation entre espaces |
| **Breadcrumbs** | Chemin de navigation visible |
| **Keyboard shortcuts** | Power user efficiency |
| **Clean minimal UI** | Focus sur le contenu, pas la déco |

**Pattern clé :** Chaque élément est un point d'entrée vers ses relations.

### Gradio-Specific Architecture (Party Mode Consensus)

#### Composants Natifs Gradio 5.x

| Composant | Description | Usage WallTrack |
|-----------|-------------|-----------------|
| **`gr.Navbar`** | Barre navigation multi-page | Navigation Home/Explorer/Config |
| **`gr.Sidebar`** | Panel latéral collapsible | Contexte wallet/signal sélectionné |
| **Multipage `.route()`** | Routes URL distinctes | Deep links vers pages |
| **`every=N`** | Auto-refresh composant | Status bar temps réel (30s) |
| **`gr.Tabs`** | Sous-navigation | Signals/Wallets/Clusters dans Explorer |
| **`gr.State`** | État partagé | Contexte entre composants |

#### Architecture Finale (3 Pages + Sidebar)

```
┌─────────────────────────────────────────────────────────────────┐
│  [gr.Navbar]  Home  |  Explorer  |  Config                      │
├─────────────────────────────────────────────────────────────────┤
│  [Status Bar - gr.HTML every=30]                                │
│  🟢 Discovery: 2h ago │ 🟢 Signals: 12 today │ 143 wallets      │
├─────────────────────────────────────────────────────────┬───────┤
│                                                         │       │
│  [Contenu principal de la page]                         │ Side  │
│                                                         │ bar   │
│  HOME: KPIs + Positions actives (cliquables)            │       │
│  EXPLORER: Tabs (Signals/Wallets/Clusters)              │ Con-  │
│  CONFIG: Settings, thresholds, webhooks                 │ texte │
│                                                         │       │
│  Clic sur élément → Sidebar s'ouvre avec contexte       │ Sel.  │
│                                                         │       │
└─────────────────────────────────────────────────────────┴───────┘
```

#### Structure Code Proposée

```python
with gr.Blocks() as app:
    gr.Navbar(main_page_name="WallTrack", value=[
        ("Home", "/"),
        ("Explorer", "/explorer"),
        ("Config", "/config"),
    ])

    # Status bar globale - auto-refresh 30s
    gr.HTML(render_status_bar, every=30, elem_id="status-bar")

    # Sidebar globale - contexte sélectionné
    with gr.Sidebar(position="right", width=380, open=False):
        selected_context = gr.State(None)
        context_display = gr.Markdown("Sélectionnez un élément...")
        with gr.Accordion("Actions", open=True):
            blacklist_btn = gr.Button("Blacklist", variant="stop")
            reprofile_btn = gr.Button("Re-profiler")

@app.route("/")
def home_page():
    # KPIs, positions actives cliquables, alertes
    ...

@app.route("/explorer")
def explorer_page():
    with gr.Tabs():
        with gr.Tab("Signals"): ...
        with gr.Tab("Wallets"): ...
        with gr.Tab("Clusters"): ...

@app.route("/config")
def config_page():
    # Settings, thresholds, webhooks
    ...
```

### Transferable UX Patterns

| Pattern | Source | Usage WallTrack |
|---------|--------|-----------------|
| **Status bar auto-refresh** | Grafana | `gr.HTML(every=30)` en haut |
| **Sidebar contextuelle** | Linear | `gr.Sidebar(open=False)` |
| **Click-to-drill** | TradingView | Chaque élément ouvre son contexte |
| **Tabs pour sous-catégories** | Grafana | Explorer → Signals/Wallets/Clusters |
| **Color coding** | TradingView | 🟢🟡🔴 universel |
| **Relative timestamps** | Vercel | "il y a 2h" pas dates absolues |

### Anti-Patterns to Avoid

| Anti-pattern | Problème | Solution |
|--------------|----------|----------|
| **8 tabs déconnectés** | Contexte perdu | 3 pages + sidebar persistante |
| **Refresh manuel** | "C'est à jour ?" | `every=30` pour status |
| **Nouveaux onglets pour détails** | Navigation cassée | Sidebar inline |
| **Tables statiques** | Pas d'interaction | Chaque ligne cliquable |
| **IDs techniques visibles** | Confusion | Labels humains |
| **Pas de gr.State** | Rechargement constant | State pour contexte partagé |

### Design Inspiration Strategy

#### À Adopter

1. **Navbar Gradio** → Navigation 3 pages avec URLs
2. **Sidebar collapsible** → Contexte drill-down persistant
3. **Status bar `every=30`** → Réponse à "c'est vivant ?"
4. **Tabs dans Explorer** → Sous-navigation claire

#### À Adapter

1. **Watchlist TradingView** → Positions actives sur Home
2. **Panels Grafana** → KPIs cards sur Home
3. **Breadcrumbs Linear** → Markdown custom si besoin

#### Phase 2 (Lab)

- **Exit Strategy Optimizer** → Documenté mais pas implémenté MVP
- Nécessite infrastructure de simulation comparée
- À intégrer comme 4ème page quand prêt

### Testabilité (Insight TEA)

| Composant | Considération Test |
|-----------|-------------------|
| `every=30` status | Mocker les appels API |
| Sidebar state | Test persistence cross-page |
| Navbar routing | Test chaque route |
| `elem_id` | Maintenir sur tous composants clés |

---

## Design System Foundation

### Design System Choice

**Approche : Gradio Theme + CSS Design Tokens**

WallTrack utilise Gradio comme framework UI, ce qui impose un système de design spécifique :

| Couche | Technologie | Usage |
|--------|-------------|-------|
| **Base Theme** | `gr.themes.Soft()` | Fondation visuelle |
| **CSS Tokens** | Variables CSS custom | Couleurs, spacing, typography |
| **Component Classes** | Classes CSS dédiées | Status indicators, cards |

### Rationale for Selection

1. **Contrainte technique** — Gradio n'est pas compatible avec les design systems JS (MUI, Chakra)
2. **Déjà en place** — Le code actuel utilise déjà CSS custom, on étend plutôt que reconstruire
3. **Simplicité** — Un opérateur unique n'a pas besoin d'un design system enterprise
4. **Cohérence** — Les tokens CSS garantissent la consistance visuelle

### Implementation Approach

#### CSS Design Tokens

```css
:root {
  /* Status Colors */
  --status-healthy: #10b981;
  --status-warning: #f59e0b;
  --status-error: #ef4444;
  --status-neutral: #6b7280;

  /* Semantic Colors */
  --color-positive: #10b981;
  --color-negative: #ef4444;
  --color-info: #3b82f6;

  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  /* Typography */
  --font-mono: 'JetBrains Mono', monospace;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;

  /* Cards & Panels */
  --border-radius: 8px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
}
```

#### Component Classes

```css
/* Status Indicators */
.status-healthy { color: var(--status-healthy); }
.status-warning { color: var(--status-warning); }
.status-error { color: var(--status-error); }

/* Metric Display */
.metric-positive { color: var(--color-positive); font-weight: 600; }
.metric-negative { color: var(--color-negative); font-weight: 600; }

/* Status Bar */
.status-bar {
  background: var(--color-surface);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--border-radius);
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
}

/* Cards */
.kpi-card {
  background: white;
  padding: var(--space-md);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-sm);
}
```

### Customization Strategy

| Élément | Approche |
|---------|----------|
| **Couleurs principales** | Tokens CSS, pas hardcodé |
| **Status indicators** | 🟢🟡🔴 + classes CSS |
| **Typography** | Monospace pour données, sans-serif pour labels |
| **Spacing** | Grille 8px (multiples de --space-sm) |
| **Dark mode** | Non prioritaire MVP, mais tokens facilitent l'ajout |

### Gradio Theme Extension (optionnel)

```python
import gradio as gr
from gradio.themes.base import Base

class WallTrackTheme(Base):
    def __init__(self):
        super().__init__(
            primary_hue="emerald",
            secondary_hue="slate",
            neutral_hue="slate",
            font=("Inter", "sans-serif"),
            font_mono=("JetBrains Mono", "monospace"),
        )

# Usage
gr.Blocks(theme=WallTrackTheme())
```

---

## Defining Core Experience

### Defining Experience

**L'interaction signature de WallTrack :**

> "Je clique sur n'importe quel élément du système et je comprends immédiatement la chaîne de décision qui l'a produit."

**Comparaison avec des produits connus :**

| Produit | Defining Experience |
|---------|---------------------|
| Tinder | "Swipe pour matcher" |
| Spotify | "Play n'importe quelle chanson instantanément" |
| **WallTrack** | "Click pour comprendre la décision" |

**Ce que Christophe dira à un ami :**
> "Mon bot de trading me montre exactement pourquoi il a pris chaque position. Je clique sur un trade et je vois tout : le wallet source, son score, comment il a été découvert, ses connexions cluster..."

### User Mental Model

**Comment l'opérateur pense :**

| Mental Model | Implication UX |
|--------------|----------------|
| "Le système est une boîte noire" | → Rendre transparent |
| "Je veux valider ses décisions" | → Montrer le raisonnement |
| "Si je comprends, je fais confiance" | → Chaque élément explicable |
| "Je ne veux pas micro-manager" | → Synthèse d'abord, détails à la demande |

**Attentes utilisateur :**

1. **Status instantané** — "Ça marche ?" en 2 secondes
2. **Drill-down naturel** — Clic = contexte
3. **Chaîne causale visible** — Signal ← Wallet ← Discovery ← Pump
4. **Actions disponibles** — Blacklist, re-profile, stop position

### Success Criteria

**L'interaction est réussie quand :**

| Critère | Mesure |
|---------|--------|
| **Temps de compréhension** | < 5 secondes après clic |
| **Profondeur** | Max 2 clics pour remonter à l'origine |
| **Complétude** | Toutes les infos dans la sidebar, pas besoin de changer de page |
| **Action possible** | Boutons d'action visibles dans le contexte |

**Feedback utilisateur attendu :**
- "Ah ok, je comprends maintenant"
- "C'est logique"
- "Je vois d'où ça vient"

### Experience Mechanics

#### Flow : Drill-Down Explicatif

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INITIATION                                               │
│    User voit une position active sur Home                   │
│    "Position: ABC... | +0.34 SOL | Wallet: xyz..."          │
│    → Curiosité : "Pourquoi ce trade ?"                      │
├─────────────────────────────────────────────────────────────┤
│ 2. INTERACTION                                              │
│    User clique sur la ligne                                 │
│    → Sidebar s'ouvre (ou se met à jour)                     │
├─────────────────────────────────────────────────────────────┤
│ 3. FEEDBACK - Sidebar Contexte                              │
│    ┌─────────────────────────────────┐                      │
│    │ Position ABC...                 │                      │
│    │ ─────────────────────           │                      │
│    │ Wallet: xyz... (score 82%)      │ ← cliquable          │
│    │ Signal reçu: il y a 2h          │                      │
│    │ Entry: 0.0012 SOL               │                      │
│    │ Current: 0.0016 SOL (+33%)      │                      │
│    │ ─────────────────────           │                      │
│    │ 📍 Pourquoi ce wallet ?         │                      │
│    │ • Découvert sur pump XYZ        │                      │
│    │ • Win rate: 78%                 │                      │
│    │ • Cluster avec 3 autres wallets │ ← cliquable          │
│    │ ─────────────────────           │                      │
│    │ [Close Position] [View Wallet]  │                      │
│    └─────────────────────────────────┘                      │
├─────────────────────────────────────────────────────────────┤
│ 4. COMPLETION                                               │
│    User comprend la chaîne : Position ← Wallet ← Discovery  │
│    Peut agir (close, blacklist) ou continuer à explorer     │
│    → Sentiment : "Je comprends, je fais confiance"          │
└─────────────────────────────────────────────────────────────┘
```

#### Pattern Établi vs Novel

| Aspect | Type | Référence |
|--------|------|-----------|
| **Click-to-detail** | Établi | TradingView, Grafana |
| **Sidebar contextuelle** | Établi | Linear, Notion |
| **Chaîne causale explicite** | **Novel** | Spécifique WallTrack |
| **Auto-refresh status** | Établi | Grafana, Vercel |

**Innovation WallTrack :** La **chaîne causale explicite** dans la sidebar n'est pas standard. C'est notre différenciateur UX — montrer non seulement "quoi" mais "pourquoi depuis l'origine".

### Implementation Priority

| Élément | Priorité | Justification |
|---------|----------|---------------|
| **Sidebar drill-down** | P0 | Core experience |
| **Chaîne causale dans sidebar** | P0 | Différenciateur |
| **Status bar auto-refresh** | P0 | "C'est vivant ?" |
| **Click-to-drill sur tables** | P0 | Point d'entrée |
| **Actions dans sidebar** | P1 | Complémentaire |

---

## Visual Design Foundation

### Color System

| Usage | Couleur | Hex |
|-------|---------|-----|
| **Healthy / Positive** | Emerald | `#10b981` |
| **Warning / Decay** | Amber | `#f59e0b` |
| **Error / Negative** | Red | `#ef4444` |

→ Déjà en place dans le CSS actuel. On garde.

### Typography

| Usage | Font |
|-------|------|
| **Données** | Monospace (défaut système) |
| **UI** | Gradio default (Inter) |

→ Pas de custom fonts. On utilise les défauts Gradio.

### Spacing

- Utiliser les defaults Gradio
- CSS custom uniquement pour status bar et KPI cards
- Pas de design system complexe

### Principe

**Gradio fait le travail.** On ajoute du CSS custom uniquement là où c'est nécessaire (status colors, status bar). Le reste = defaults.

---

## Design Direction

### Direction Choisie

**Gradio Navbar + Sidebar + Status Bar**

| Élément | Choix | Justification |
|---------|-------|---------------|
| **Navigation** | `gr.Navbar` (3 pages) | Pattern Gradio natif |
| **Contexte** | `gr.Sidebar` (right, 380px) | Drill-down sans perte de contexte |
| **Status** | `gr.HTML(every=30)` | "C'est vivant ?" instantané |
| **Sous-nav** | `gr.Tabs` dans Explorer | Signals/Wallets/Clusters |

### Layout Final

```
┌─────────────────────────────────────────────────────────────────┐
│  [Navbar]  Home  |  Explorer  |  Config                         │
├─────────────────────────────────────────────────────────────────┤
│  [Status Bar - auto-refresh 30s]                                │
│  🟢 Discovery: 2h ago │ 🟢 Signals: 12 │ 143 wallets            │
├─────────────────────────────────────────────────────────┬───────┤
│                                                         │       │
│  [Contenu principal]                                    │ Side  │
│                                                         │ bar   │
│  Tables cliquables → Sidebar contextuelle               │       │
│                                                         │       │
└─────────────────────────────────────────────────────────┴───────┘
```

### Pas de Mockups HTML

- Gradio impose les composants
- Direction claire, pas besoin de variations
- Wireframes ASCII suffisent

---

## User Journeys Essentiels

### Journey 1 : Status Check (quotidien)

```
Christophe ouvre WallTrack
        ↓
Status bar visible immédiatement
🟢 Discovery OK │ 🟢 12 signals │ 3 positions
        ↓
"Ça tourne" ✓ (< 2 sec)
        ↓
Optionnel: clic position → sidebar contexte
```

### Journey 2 : Drill-Down Explicatif

```
Voit une position sur Home
        ↓
Clic sur la ligne
        ↓
Sidebar s'ouvre :
• Token: ABC...
• Wallet: xyz... (score 82%) ← cliquable
• Pourquoi ce wallet ?
  - Découvert sur pump XYZ
  - Win rate 78%
  - Cluster avec 3 autres
        ↓
Comprend la décision ✓
        ↓
Optionnel: [Blacklist] [View Wallet]
```

### Journey 3 : Exploration Wallets

```
Navbar → Explorer
        ↓
Tab "Wallets"
        ↓
Table avec filtres (status, score min)
        ↓
Clic wallet → Sidebar contexte
        ↓
Voir clusters associés, historique signals
```

---

## Récapitulatif UX Specification

### Architecture Finale

| Composant | Implementation |
|-----------|----------------|
| **Navigation** | `gr.Navbar` - 3 pages (Home, Explorer, Config) |
| **Status** | `gr.HTML(every=30)` - auto-refresh |
| **Contexte** | `gr.Sidebar(right, 380px, open=False)` |
| **Sous-nav** | `gr.Tabs` dans Explorer |
| **Tables** | `gr.Dataframe` avec `.select()` |

### Priorités Implementation

| P0 (MVP) | P1 (Next) |
|----------|-----------|
| Status bar auto-refresh | Actions dans sidebar |
| Navbar 3 pages | Keyboard shortcuts |
| Sidebar drill-down | Filters avancés |
| Tables cliquables | Graphiques performance |

### Ce Qui Change vs Actuel

| Avant (8 tabs) | Après (Navbar + Sidebar) |
|----------------|-------------------------|
| Tabs déconnectés | Navigation contextuelle |
| Refresh manuel | Auto-refresh 30s |
| Détails = nouvel onglet | Détails = sidebar |
| Pas de "pourquoi" | Chaîne causale explicite |

---

## Document Complete

**UX Design Specification - WallTrack**
- Date: 2025-12-26
- Author: Christophe + Sally (UX Designer)
- Status: ✅ Complete

Prêt pour implementation.
