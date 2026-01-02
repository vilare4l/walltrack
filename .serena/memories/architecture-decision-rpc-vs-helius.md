# Décision Architecturale: RPC Public vs Helius Enhanced API

**Date:** 2025-12-31  
**Participant:** Christophe (utilisateur), Winston (architecte)  
**Contexte:** Refonte architecture V2 - Optimisation coûts API

---

## 🎯 Problématique Initiale

**Constat:** Tests V1 consomment des tokens Helius de manière excessive.

**Question clé:** "Quelle est la vraie valeur d'Helius comparé à consulter on-chain directement?"

---

## 🔍 Investigation Menée

### Services API Évalués

| Service | Free Tier | Wallet Profiling Gratuit? | Conclusion |
|---------|-----------|--------------------------|------------|
| **Birdeye** | 30K CU/mois (1 RPS) | ❌ Wallet analytics = $99+/mois | Rejeté |
| **Shyft** | API key gratuite | ⚠️ Limites floues, historique 3-4 jours | Insuffisant |
| **Helius** | 1M credits/mois | ❌ Enhanced API = Business plan ($500+) | Webhooks only |
| **RPC Public Solana** | 240 req/min (gratuit) | ✅ Tout accessible via RPC standard | **RETENU** |

### Analyse Helius Enhanced API vs RPC Public

**Ce que RPC Public fait GRATUITEMENT:**

| Besoin | RPC Public | Helius Enhanced |
|--------|------------|-----------------|
| Get signatures wallet | ✅ `getSignaturesForAddress` | ✅ même endpoint |
| Get détails transaction | ✅ `getTransaction` | ✅ même endpoint |
| Parser swaps | ✅ On parse nous-mêmes | ✅ Pré-parsé (lazy bonus) |
| Discovery wallets | ✅ 100% possible | ✅ même data |
| Profiling wallets | ✅ 100% possible | ✅ même data |
| **Webhooks temps réel** | ❌ **Impossible** (faut poller) | ✅ **Push <500ms** |

**SEULE vraie valeur Helius:** Webhooks push (vs polling RPC toutes les 10s)

---

## ✅ Décision Architecturale Finale

### Architecture Retenue: **RPC Public + Helius Webhooks (Dual-Mode Optionnel)**

```
┌─────────────────────────────────────────────────┐
│  GRATUIT (RPC Public Solana)                    │
├─────────────────────────────────────────────────┤
│  ✅ Discovery tokens (DexScreener)              │
│  ✅ Discovery wallets (early buyer performers)  │
│  ✅ Profiling wallets (win_rate, PnL, metrics)  │
│  ✅ Signal Detection MODE 1: Polling 10s        │
│  ✅ Tests (mocks, 0 API calls)                  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  OPTIONNEL (Helius Webhooks - 7.5% quota)       │
├─────────────────────────────────────────────────┤
│  ⚠️  Signal Detection MODE 2: Webhook <500ms    │
│     (activable dynamiquement en prod)           │
└─────────────────────────────────────────────────┘
```

### Configuration Dual-Mode Signal Detection

**3 modes disponibles (config dynamique):**

1. **POLLING** (défaut, gratuit)
   - Scheduler toutes les 10s
   - Check wallets watchlistés via RPC
   - Latence max 10s
   - 100% gratuit

2. **WEBHOOK** (optionnel, quota)
   - Helius push instantané
   - Latence <500ms
   - 75K credits/mois (7.5% quota Helius free tier)

3. **HYBRID** (prod optimal)
   - Démarre en webhook
   - Auto-fallback polling si webhook down
   - Meilleure résilience

---

## 📊 Impact Quantifié

### Consommation API V1 vs V2

| Opération | V1 (Helius partout) | V2 (RPC + dual-mode) |
|-----------|---------------------|----------------------|
| Discovery 100 tokens | 100 calls | 0 Helius (DexScreener) |
| Discovery 500 wallets | 500 calls | 0 Helius (RPC gratuit) |
| Profiling 500 wallets | 50,000 calls | 0 Helius (RPC gratuit) |
| Tests (mocks) | 500+ calls | 0 calls ✅ |
| Signaux MODE polling | N/A | 0 Helius (RPC gratuit) |
| Signaux MODE webhook | 75K/mois | 75K/mois (même) |
| **TOTAL Helius** | **125,500+/mois** | **0-75K/mois** (selon mode) |

**Gain:** Division par **17x minimum** (polling) à **∞** (mode polling only)

### Quota Mensuel Estimé

```python
# Mode POLLING ONLY (gratuit total):
monthly_helius_usage = 0 credits
monthly_rpc_usage = 12,000 calls (discovery + profiling)
# RPC limit: 240 req/min = largement suffisant

# Mode WEBHOOK (optionnel):
monthly_helius_usage = 75,000 credits
# Free tier: 1M credits
# Marge: 925K (92.5%) restants
```

---

## 🔧 Composants Techniques Impactés

### Nouveaux Composants à Créer

1. **`src/walltrack/services/solana/rpc_client.py`**
   - Client RPC public Solana
   - Méthodes: `getSignaturesForAddress`, `getTransaction`, batch queries
   - Rate limiting: 40 req/10s

2. **`src/walltrack/services/solana/transaction_parser.py`**
   - Parser custom transactions Solana → SwapEvent
   - Remplace Helius enhanced parsing
   - Detection DEX (Jupiter, Raydium, Orca, Pump.fun)
   - Extraction SOL change + token transfers

3. **`src/walltrack/core/signals/signal_detector.py`**
   - `PollingSignalDetector`: polling RPC toutes les 10s
   - `WebhookSignalDetector`: Helius webhooks (optionnel)
   - `HybridSignalDetector`: webhook + fallback polling

4. **`src/walltrack/core/signals/detector_factory.py`**
   - Factory pattern pour créer le bon detector selon config
   - Switch dynamique entre modes

### Composants Modifiés

1. **`src/walltrack/services/helius/`**
   - **AVANT:** Client complet (transactions, profiling, webhooks)
   - **APRÈS:** Webhooks UNIQUEMENT (create/update/delete/list)
   - Suppression: `get_wallet_transactions`, `get_token_transactions`, etc.

2. **`src/walltrack/core/discovery/wallet_discovery.py`**
   - **AVANT:** Utilise Helius pour early buyers
   - **APRÈS:** Utilise RPC public + parser custom

3. **`src/walltrack/core/wallets/profiler.py`**
   - **AVANT:** Utilise Helius pour historique transactions
   - **APRÈS:** Utilise RPC public + parser custom
   - Ajout cache Supabase (TTL 24h)

---

## 📄 Documents Nécessitant Mise à Jour

### 1. `docs/architecture.md`

**Sections impactées:**

- **"API & Communication Patterns"**
  - Retirer: Helius Enhanced API usage
  - Ajouter: RPC Public Solana client
  - Ajouter: Transaction parser custom

- **"Services Layer Structure"**
  ```diff
  - services/helius/          # Client complet
  + services/helius/          # Webhooks UNIQUEMENT
  + services/solana/          # RPC client + parser
  ```

- **"Signal Processing Flow"**
  - Ajouter: Dual-mode detection (polling vs webhook)
  - Configuration dynamique

- **"External Dependencies"**
  - Modifier: Helius = optionnel (webhooks only)
  - Ajouter: Solana RPC Public (gratuit, critique)

### 2. `docs/prd.md`

**Sections impactées:**

- **FR Epic 4: Signal Processing**
  - FR 4.1: "Real-time webhooks Helius" → "Signal detection (polling OU webhook)"
  - Ajouter mode polling comme alternative gratuite

- **NFR Performance**
  - Modifier: "<500ms webhook processing" → "Polling: 10s | Webhook: <500ms"
  
- **External API Dependencies**
  - Helius: Enhanced API → Webhooks only (optionnel)
  - Ajouter: Solana RPC Public (gratuit, critique)

### 3. `docs/epics.md`

**Epics impactés:**

- **Epic 3: Wallet Discovery**
  - Story 3.1: Discovery méthode (RPC au lieu de Helius)
  - Story 3.2: Profiling (RPC + parser custom)

- **Epic 4: Signal Processing**
  - Story 4.1: Detection mode (dual-mode au lieu de webhook only)
  - Story 4.2: Configuration dynamique (polling/webhook/hybrid)

### 4. `docs/sprint-artifacts/sprint-status.yaml`

**Stories à vérifier:**
- Stories mentionnant Helius Enhanced API
- Tests consommant des tokens
- Stories Epic 3 et 4

---

## 🎯 Stratégie d'Implémentation

### Phase 1: MVP Gratuit (Polling Only)

**Objectif:** Système 100% fonctionnel, 0€/mois

```
1. RPC Client + Transaction Parser
2. Discovery wallets (RPC)
3. Profiling wallets (RPC)
4. Polling Signal Detector (10s)
5. Tests avec mocks (0 API calls)
```

**Validation:** Tout fonctionne, latence 10s acceptable

### Phase 2: Webhook Optionnel (Si Besoin)

**Objectif:** Latence temps réel <500ms

```
1. Helius Webhook Client (minimal)
2. Webhook Signal Detector
3. FastAPI webhook endpoint
4. Hybrid mode (webhook + fallback)
```

**Activation:** Config dynamique, pas de code change

---

## ⚠️ Risques & Mitigations

### Risque 1: Parser Custom Incomplet

**Risque:** Notre parser rate des patterns de swap

**Mitigation:**
- Tests exhaustifs avec transactions réelles
- Comparaison parsing custom vs Helius (validation)
- Support progressif DEX (Jupiter d'abord, puis Raydium, etc.)

### Risque 2: RPC Rate Limiting

**Risque:** 240 req/min insuffisant en peak

**Mitigation:**
- Batch requests (10 transactions par call)
- Cache agressif (24h profiling)
- Monitoring usage RPC

### Risque 3: Latence 10s Insuffisante

**Risque:** Signaux trop lents, prix déjà bougé

**Mitigation:**
- Démarrer polling, mesurer impact réel
- Switch webhook si nécessaire (config dynamique)
- Hybrid mode pour meilleur des deux mondes

---

## 📊 Métriques de Succès

### Objectifs Quantifiables

| Métrique | V1 | V2 Cible |
|----------|----|---------| 
| Coût API mensuel | Variable (quota) | **0€** (mode polling) |
| Helius quota utilisé | >125K/mois | **0-75K/mois** |
| Tests consommant tokens | 500+ calls | **0 calls** |
| Latence signal detection | <500ms (webhook) | 10s (polling) ou <500ms (webhook) |
| Setup complexity | Webhook requis | **Zero config** (polling) |

---

## 🔄 Prochaines Étapes

1. **Lancer `*implementation-readiness` workflow**
   - Analyser gap PRD/Architecture/Epics
   - Détecter incohérences Helius Enhanced API
   - Générer rapport corrections nécessaires

2. **Mettre à jour documents selon rapport**
   - architecture.md
   - prd.md
   - epics.md
   - sprint-status.yaml

3. **Commencer Phase 1 implémentation**
   - RPC Client + Parser
   - Discovery RPC
   - Profiling RPC
   - Polling detector

---

## 💡 Décision Clé Retenue

**"Full RPC SAUF webhook"** = Architecture optimale:

- ✅ Gratuit par défaut (polling)
- ✅ Optionnel webhooks (si latence critique)
- ✅ Pas de vendor lock-in Helius
- ✅ Dual-mode = flexibilité maximale
- ✅ Zero config pour démarrer

**Citation Christophe:** "Full RPC SAUF webhook"  
**Confirmation Architecte:** Architecture validée et optimale pour système personnel évolutif.
