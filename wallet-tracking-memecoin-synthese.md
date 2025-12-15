# Wallet Tracking Memecoin Solana

## Vision du projet

Système d'intelligence pour identifier et suivre les wallets "smart money" sur Solana, détecter leurs mouvements en temps réel, et générer des signaux de trading exploitables.

L'objectif n'est pas du copy trading aveugle, mais une analyse approfondie des acteurs informés pour se positionner avant le retail.

---

## Positionnement stratégique

```
Timing d'entrée sur un token

T+0ms      Insiders / Dev / Bots MEV
T+500ms    → TOI (signal wallet détecté)
T+5min     Early followers
T+30min    KOL tweets
T+1h       Retail FOMO
```

L'edge n'est pas la vitesse d'exécution mais la qualité du signal. Un bon signal avec 2 secondes de retard bat un mauvais signal instantané.

---

## Architecture conceptuelle

### Phase 1 : Discovery — Trouver les bons wallets

**Objectif** : Constituer une watchlist de wallets performants.

**Sources** :
- Top holders des tokens ayant fait x10+ récemment
- Premiers acheteurs sur Pump.fun des succès
- Wallets apparaissant régulièrement "early" sur plusieurs tokens gagnants

**Critères de sélection** :
- Win rate > 50%
- Timing early récurrent (top 5% des acheteurs)
- Sizing consistant (pas de la chance sur un gros bet)
- Historique suffisant (20+ trades minimum)

---

### Phase 2 : Profiling — Comprendre chaque wallet

Chaque wallet surveillé a un profil comportemental complet.

**Métriques clés** :

| Catégorie | Métriques |
|-----------|-----------|
| Performance | Win rate, PnL moyen, meilleur/pire trade, Sharpe |
| Timing | Percentile d'entrée, durée moyenne de hold, pattern de sortie |
| Sizing | Position moyenne, position max, concentration |
| Meta | Date première activité, nombre de trades, catégorie |

**Patterns comportementaux** :
- Heures d'activité
- Types de tokens préférés (narratifs)
- Style : DCA vs all-in
- Horizon : quick flip vs diamond hands

---

### Phase 3 : Clustering — Détecter les réseaux

Les insiders opèrent rarement seuls. Identifier les groupes coordonnés.

**Signaux de connexion** :

| Relation | Signification |
|----------|---------------|
| `FUNDED_BY` | Même source de SOL = probable même entité |
| `SYNCED_BUY` | Achat du même token à < 5 min d'écart = coordination |
| `SAME_EARLY_TOKENS` | Présents ensemble sur 5+ tokens early = réseau |

**Valeur du clustering** :
- Signal renforcé quand plusieurs wallets d'un cluster bougent
- Identification du leader (qui initie les mouvements)
- Early warning : un wallet bouge → les autres suivent ?

---

### Phase 4 : Monitoring — Surveillance temps réel

**Flux** :

```
Blockchain Solana
      │
      ▼
Transaction implique wallet surveillé ?
      │
  NON │ OUI
      │   │
 ignore   ▼
      Wallet achète un token ?
      │
  NON │ OUI
      │   │
  log     ▼
      SIGNAL DÉTECTÉ
```

---

### Phase 5 : Scoring — Évaluer le signal

Un wallet surveillé achète. Faut-il suivre ?

**Facteurs de scoring** :

| Catégorie | Poids | Éléments |
|-----------|-------|----------|
| Wallet | 30% | Score historique, cohérence pattern, activité récente |
| Cluster | 25% | Confirmation autres wallets, leader impliqué |
| Token | 25% | Âge, market cap, liquidité, distribution holders |
| Contexte | 20% | Heure, conditions marché, exposition actuelle |

**Décision** :

```
signal_score > 0.70 → TRADE
signal_score < 0.70 → LOG uniquement
```

---

### Phase 6 : Exécution

**Mode paper (MVP)** :
- Enregistrement trade fictif avec prix actuel
- Suivi automatique (snapshots prix)
- Calcul PnL théorique

**Mode live (v2)** :
- Vérifications pré-trade (liquidité, slippage)
- Exécution via Jupiter API
- Gestion stop-loss / take-profit

---

### Phase 7 : Feedback loop

Chaque trade alimente le système.

```
Trade terminé
      │
      ▼
Analyse : PnL, timing entry/exit, prédictivité du score
      │
      ▼
Mise à jour : ajuste score wallet, poids des facteurs
      │
      ▼
Le système s'améliore avec le temps
```

---

## Stack technique

### Base de données

| Composant | Rôle |
|-----------|------|
| **Neo4j** | Relations : wallet↔wallet, wallet↔token, clusters |
| **Supabase PostgreSQL** | Données plates : métriques, historique trades, résultats |
| **Supabase Vectors** | Embeddings profils comportementaux, similarity search |

### Infrastructure

| Composant | Usage |
|-----------|-------|
| **n8n** | Orchestration workflows |
| **Python** | Core logic, ingestion, scoring |
| **RTX 3090** | LLM local pour analyse contextuelle |

### APIs externes (free tiers)

Approche hybride : on garde le contrôle sur les données et la logique, on utilise les APIs gratuites comme accélérateurs.

| API | Usage | Dépendance critique ? |
|-----|-------|----------------------|
| **Helius webhook** | Notification temps réel des swaps wallets surveillés | Non — fallback RPC polling possible |
| **DexScreener** | Prix tokens, liquidité, market cap, âge | Non — données publiques, alternatives existent |
| **Jupiter** | Exécution swaps (quand live) | Non — Raydium direct en fallback |
| **RPC public** | Backup, queries ad-hoc, historique | Non — plusieurs providers |

**Principe** : Les APIs gratuites sont des tuyaux d'entrée/sortie. Si l'une tombe, on switch. Les données (wallets, scores, historique) et la logique (scoring, clustering, décision) restent chez nous.

### Helius Webhook — Configuration

**Free tier** :
- 500k credits/mois (1 event = 1 credit)
- 1 webhook, jusqu'à 100 000 adresses
- 10 req/sec pour les appels API

**Ce qu'on configure** :
- Adresses : liste dynamique des wallets surveillés
- Types : `SWAP` uniquement (achats/ventes de tokens)

**Données reçues (parsées)** :
```json
{
  "type": "SWAP",
  "source": "RAYDIUM",
  "signature": "5K2H...",
  "tokenInputs": [{
    "mint": "So111...112",
    "amount": 1.5
  }],
  "tokenOutputs": [{
    "mint": "7xKX...",
    "amount": 150000
  }],
  "wallet": "ABC..."
}
```

**Avantages vs websocket RPC natif** :
- Parsing des transactions déjà fait (Raydium, Jupiter, Pump.fun)
- Intégration directe dans n8n (HTTP POST)
- Pas de connexion persistante à maintenir
- Latence acceptable (~100-500ms)

### Gestion dynamique de la watchlist

La liste des wallets surveillés évolue programmatiquement via l'API Helius.

```python
import requests

HELIUS_API_KEY = "xxx"
WEBHOOK_ID = "yyy"

def add_wallets_to_webhook(new_addresses: list):
    # Récupérer les adresses actuelles
    response = requests.get(
        f"https://api.helius.xyz/v0/webhooks/{WEBHOOK_ID}",
        params={"api-key": HELIUS_API_KEY}
    )
    current = response.json()["accountAddresses"]
    
    # Fusionner et mettre à jour
    updated = list(set(current + new_addresses))
    
    requests.put(
        f"https://api.helius.xyz/v0/webhooks/{WEBHOOK_ID}",
        params={"api-key": HELIUS_API_KEY},
        json={
            "accountAddresses": updated,
            "transactionTypes": ["SWAP"]
        }
    )

def remove_wallet_from_webhook(address: str):
    response = requests.get(
        f"https://api.helius.xyz/v0/webhooks/{WEBHOOK_ID}",
        params={"api-key": HELIUS_API_KEY}
    )
    current = response.json()["accountAddresses"]
    updated = [a for a in current if a != address]
    
    requests.put(
        f"https://api.helius.xyz/v0/webhooks/{WEBHOOK_ID}",
        params={"api-key": HELIUS_API_KEY},
        json={"accountAddresses": updated, "transactionTypes": ["SWAP"]}
    )
```

**Cycle de vie des wallets surveillés** :
```
Wallet performant découvert
         │
         ▼
Ajout Neo4j + Supabase + Webhook Helius
         │
         ▼
    Surveillance active
         │
         ▼
Performance se dégrade ?
         │
    OUI  │  NON
         │    └──► Continue surveillance
         ▼
Retrait du webhook
         │
         ▼
Archivage (données conservées, plus surveillé)
```

### Flux de données complet

```
                EXTERNE (gratuit)                     INTERNE (toi)
                      │                                    │
Helius webhook ──────►│                                    │
  (wallet a swappé)   │         ┌──────────────────────────┤
                      │         │                          │
                      ▼         ▼                          │
                ┌─────────────────┐                        │
                │   n8n workflow  │                        │
                └────────┬────────┘                        │
                         │                                 │
    ┌────────────────────┼────────────────────┐            │
    │                    │                    │            │
    ▼                    ▼                    ▼            │
DexScreener API    Neo4j query         Supabase query     │
(prix token)       (cluster actif?)    (score wallet)     │
    │                    │                    │            │
    └────────────────────┼────────────────────┘            │
                         │                                 │
                         ▼                                 │
                ┌─────────────────┐                        │
                │  Score signal   │◄───────────────────────┘
                └────────┬────────┘
                         │
                score > seuil ?
                         │
                 OUI     │     NON
                  │      │      │
                  ▼      │      ▼
           Jupiter API   │    Log only
           (execute)     │
                         │
                         ▼
                Supabase (save result)
```

### Estimation consommation Helius

```
100 wallets × 5 swaps/jour  = 500 events/jour   = 15k credits/mois
300 wallets × 5 swaps/jour  = 1 500 events/jour = 45k credits/mois
1000 wallets × 5 swaps/jour = 5 000 events/jour = 150k credits/mois

Budget free tier : 500k credits/mois → Large marge
```

---

## Potentiel d'intégration IA

| Niveau | Application | Techno |
|--------|-------------|--------|
| Classification wallets | smart money vs retail vs bot vs scammer | XGBoost |
| Scoring tokens | probabilité rug, potentiel pump | XGBoost + règles |
| Profils comportementaux | embedding et similarity search | Supabase vectors |
| Analyse contextuelle | Q&A sur historique, explication signaux | LLM local |
| Apprentissage continu | ajustement poids selon résultats | Feedback loop |

---

## Ce qui est hors scope (MVP)

| Élément | Raison |
|---------|--------|
| Sentiment social (Twitter, Telegram) | Signal retardé, le on-chain suffit |
| Mapping KOL automatisé | Bruit > signal, KOL = distribution pas accumulation |
| Funding arbitrage | Requiert plus de capital, v2 |
| Pair trading | Idem, stratégie pour plus tard |
| Sniper ultra-rapide | Pas notre edge, on vise signal > vitesse |
| APIs payantes | On reste sur les free tiers, indépendance maximale |
| Parsing transactions maison | Helius le fait gratuitement, on économise du dev |

## Principe d'indépendance

**Ce qu'on possède (critique)** :
- Données wallets et métriques (Neo4j + Supabase)
- Logique de scoring et clustering
- Historique des trades et résultats
- Algorithme de décision

**Ce qu'on consomme (substituable)** :
- Helius → fallback : RPC polling + parsing maison
- DexScreener → fallback : Birdeye, CoinGecko, on-chain direct
- Jupiter → fallback : Raydium direct

Si une API gratuite disparaît ou devient payante, on peut reconstruire la fonctionnalité. Les données et la logique restent.

---

## Modèle économique réaliste

### Hypothèses conservatrices

```
3 trades/jour (sélectif)
Win rate : 55-60%
Ratio gain/perte : 2:1
Risque par trade : 2%
```

**Résultat** : ~0.3-0.5% par jour → ~100% par an

### Hypothèses optimistes (bon système)

```
3 trades/jour
Win rate : 70%
Ratio gain/perte : 3:1
Risque par trade : 2%
```

**Résultat** : ~1-2% par jour → bien plus

### Capital de départ

- MVP / validation : 1-2 SOL (~200-400€)
- Positions : 0.05-0.1 SOL par trade
- Objectif : valider le système, pas générer des revenus

---

## Risques identifiés

| Risque | Mitigation |
|--------|------------|
| Alpha decay (wallets repérés perdent leur edge) | Découverte continue de nouveaux wallets |
| Faux positifs (chance vs skill) | Historique suffisant, minimum 20+ trades |
| Rug pulls | Score token, distribution holders, ne pas all-in |
| Wallets jetables | Clustering, tracer les connexions |
| Latence RPC | Acceptable pour notre stratégie, upgrade si besoin |

---

## Stratégie moonbag

Pour capturer les x10-x100 potentiels :

```
Entry sur signal wallet insider
      │
      ├── Take profit 50% à x2-x3 (sécurise capital)
      └── Laisse 50% courir (moonbag)
            │
            ├── Si x10-x100 → payé
            └── Si dump → capital déjà sécurisé
```

---

## Roadmap

### MVP v1

- [ ] Setup Helius webhook + endpoint n8n
- [ ] Modèle de données Neo4j (wallets, relations)
- [ ] Modèle de données Supabase (métriques, trades)
- [ ] Discovery : identification wallets performants (via historique)
- [ ] Scoring performance basique (win rate, PnL)
- [ ] Intégration DexScreener pour prix tokens
- [ ] Alertes quand wallet scoré swappe
- [ ] Paper trading pour validation

### MVP v2

- [ ] Détection clusters (Neo4j)
- [ ] Gestion dynamique watchlist (ajout/retrait auto)
- [ ] Scoring ML auto-apprenant
- [ ] Dashboard Gradio
- [ ] Exécution live micro-positions (Jupiter)
- [ ] Feedback loop (résultats → ajustement scores)

### v3 (avec capital)

- [ ] Funding arbitrage opportuniste
- [ ] Pair trading
- [ ] Multi-stratégie coordonnée
- [ ] Scaling infra si nécessaire

---

## Questions clés à résoudre

1. **Bootstrap wallets** : Comment constituer la watchlist initiale ? Options : scraper les top holders des tokens qui ont pumpé, analyser les premiers acheteurs Pump.fun, utiliser des listes publiques de "smart money"
2. **Historique initial** : Comment récupérer l'historique des wallets avant de les surveiller ? RPC queries batch ou service d'indexation
3. **Seuils scoring** : Quel score minimum pour trader ? À calibrer en paper trading
4. **Clustering algo** : Quel algorithme Neo4j pour détecter les groupes ? (Louvain, Label Propagation)
5. **Decay detection** : Comment détecter quand un wallet perd son edge ? Fenêtre glissante sur les performances
6. **Position sizing** : Fixe ou dynamique selon conviction ?

---

## Conclusion

Le projet exploite une asymétrie informationnelle réelle : les insiders laissent des traces publiques sur la blockchain. L'edge vient de l'analyse systématique de ces traces, pas de la vitesse d'exécution.

**Stack technique** :
- Données : Neo4j (graphe) + Supabase (métriques)
- Orchestration : n8n
- APIs gratuites : Helius (webhooks), DexScreener (prix), Jupiter (swaps)
- IA : scoring, clustering, analyse contextuelle

**Philosophie** :
- Indépendance maximale : on possède les données et la logique
- APIs gratuites comme accélérateurs, pas comme dépendances
- Fallbacks identifiés pour chaque service externe

**Coût d'infra** : Quasi nul pour le MVP (free tiers suffisants)

**Prochaine étape** : Setup Helius webhook + modèle de données Neo4j pour commencer l'indexation.
