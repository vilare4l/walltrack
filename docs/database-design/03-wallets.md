# Table: wallets - Design Guide

## Pattern architectural
**Pattern**: **Registry Pattern** (Watchlist)
**Objectif**: Liste des wallets Solana à surveiller avec contexte discovery, baseline performance, et sync Helius

---

## Vue d'ensemble - Schéma complet

| Groupe | Champ | Type | Contraintes | Default | Description |
|--------|-------|------|-------------|---------|-------------|
| **PK** | id | UUID | PRIMARY KEY | gen_random_uuid() | Identifiant unique |
| **Identity** | address | TEXT | NOT NULL, UNIQUE | | Adresse wallet Solana |
| **Identity** | label | TEXT | | NULL | Label lisible |
| **Config** | mode | TEXT | NOT NULL, CHECK IN ('simulation', 'live') | 'simulation' | Mode de trading |
| **Relations** | exit_strategy_id | UUID | NOT NULL, FK → exit_strategies(id) | | Stratégie assignée (obligatoire) |
| **Discovery** | discovery_source | TEXT | CHECK IN sources | NULL | Source découverte |
| **Discovery** | discovery_date | DATE | | NULL | Date découverte |
| **Discovery** | discovery_notes | TEXT | | NULL | Contexte découverte |
| **Initial Perf** | initial_win_rate_percent | NUMERIC(5,2) | CHECK >= 0 AND <= 100 | NULL | Win rate observé avant ajout |
| **Initial Perf** | initial_trades_observed | INTEGER | CHECK >= 0 | NULL | Nombre trades analysés |
| **Initial Perf** | initial_avg_pnl_percent | NUMERIC(8,4) | | NULL | PnL moyen % observé |
| **Initial Perf** | observation_period_days | INTEGER | CHECK > 0 | NULL | Période observation (jours) |
| **Helius Sync** | helius_synced_at | TIMESTAMPTZ | | NULL | Dernière sync vers webhook |
| **Helius Sync** | helius_sync_status | TEXT | CHECK IN ('pending', 'synced', 'error') | 'pending' | Status sync webhook |
| **Status** | is_active | BOOLEAN | NOT NULL | true | Wallet actif |
| **Metadata** | created_at | TIMESTAMPTZ | | NOW() | Date création |
| **Metadata** | updated_at | TIMESTAMPTZ | | NOW() | Date dernière MàJ |
| **Metadata** | last_signal_at | TIMESTAMPTZ | | NULL | Dernier signal reçu |
| **Metadata** | notes | TEXT | | NULL | Notes |

---

## Rationale par groupe de champs

### Groupe Identity 🆔
| Champ | Rationale |
|-------|-----------|
| `address` | Adresse wallet Solana (base58, 32-44 chars) - **UNIQUE** car 1 wallet = 1 configuration |
| `label` | Nom lisible pour l'UI (ex: "CryptoWhale #1", "DegenApe", etc.) - Optionnel |

**Pourquoi ?**
On identifie le wallet par son address (clé primaire métier), mais on permet un label pour faciliter la reconnaissance humaine dans le dashboard.

**Validation** :
- Address format : Solana base58 (32-44 caractères)
- Address unique : Un wallet ne peut pas être ajouté 2 fois
- Label : Free text (255 chars max)

---

### Groupe Config ⚙️
| Champ | Rationale |
|-------|-----------|
| `mode` | **Simulation** = Paper trading (test sans risque) / **Live** = Vrai capital |

**Pourquoi ?**
On veut pouvoir tester un wallet en simulation avant de l'activer en live. Permet de valider la stratégie sans risque.

**Workflow** :
```
1. Découverte wallet → Ajouter en mode 'simulation'
2. Observer 7-30 jours performance simulée
3. Si performance OK → Passer en mode 'live'
4. Si performance KO → Désactiver (is_active = false)
```

**Contrainte** :
- Mode CHECK IN ('simulation', 'live')
- Default = 'simulation' (sécurité first)

---

### Groupe Relations 🔗
| Champ | Rationale |
|-------|-----------|
| `exit_strategy_id` | FK vers `exit_strategies` - Stratégie par défaut assignée au wallet |

**Pourquoi ?**
Chaque wallet doit avoir UNE stratégie de sortie par défaut (stop loss, trailing stop, scaling, mirror exit).

**Important** :
- ⚠️ **Pas d'override ici** - Override se fait au niveau `positions.exit_strategy_override` (snapshot à création position)
- Obligatoire (NOT NULL) - Un wallet sans stratégie ne peut pas être ajouté
- Modifiable - On peut changer la stratégie d'un wallet (affecte les NOUVELLES positions seulement)

**Exemple** :
```sql
-- Wallet "CryptoWhale #1" utilise stratégie "Aggressive" par défaut
INSERT INTO wallets (address, label, exit_strategy_id)
VALUES ('ABC...XYZ', 'CryptoWhale #1', 'uuid-strategy-aggressive');

-- Toutes les positions futures de ce wallet utiliseront "Aggressive"
-- SAUF si on override au niveau position
```

---

### Groupe Discovery 🔍
| Champ | Rationale |
|-------|-----------|
| `discovery_source` | **Provenance** du wallet (Twitter, Telegram, Scanner, Referral, Manual, Other) |
| `discovery_date` | **Quand** on a découvert ce wallet |
| `discovery_notes` | **Contexte** libre (ex: "Trouvé via thread Twitter @CryptoGuru, focus memecoins") |

**Pourquoi ?**
**Audit trail** - Si un wallet performe mal, on peut investiguer : "Ah, il vient de Twitter, tous les wallets Twitter sont mauvais, on arrête de sourcer là-bas."

**Use cases** :
- Analyser quel canal de découverte donne les meilleurs wallets
- Tracer l'origine d'un cluster de wallets (ex: tous référés par même personne)
- Justifier l'ajout d'un wallet (notes = contexte décisionnel)

**Validation** :
```sql
discovery_source CHECK IN ('twitter', 'telegram', 'scanner', 'referral', 'manual', 'other')
```

**Exemples** :
```sql
-- Découvert via Twitter
discovery_source = 'twitter'
discovery_date = '2025-01-05'
discovery_notes = 'Thread viral @DegenAlpha - 85% win rate claim, focus low-cap gems'

-- Découvert via scanner automatique
discovery_source = 'scanner'
discovery_date = '2025-01-04'
discovery_notes = 'Auto-detected: 10 trades, 9 wins (+450% avg), cluster "SOL Whales"'
```

---

### Groupe Initial Performance 📊
| Champ | Rationale |
|-------|-----------|
| `initial_win_rate_percent` | **Win rate observé AVANT ajout** - Baseline pour comparaison future |
| `initial_trades_observed` | **Nombre de trades analysés** pour calculer le win rate initial |
| `initial_avg_pnl_percent` | **PnL moyen %** observé sur la période d'observation |
| `observation_period_days` | **Durée observation** (ex: 7, 14, 30 jours) |

**Pourquoi ?**
**Baseline metrics** - On capture la performance AVANT de commencer à copier pour :
1. Valider que la performance reste cohérente après ajout
2. Détecter les red flags (performance réelle << performance initiale)

**Formulas** :
```python
initial_win_rate_percent = (winning_trades / initial_trades_observed) * 100
initial_avg_pnl_percent = SUM(pnl_percent) / initial_trades_observed
```

**Exemple concret** :
```sql
-- Wallet analysé pendant 14 jours AVANT ajout
initial_win_rate_percent = 68.00      -- 68% win rate observé
initial_trades_observed = 25          -- Sur 25 trades
initial_avg_pnl_percent = 12.50       -- +12.5% PnL moyen par trade
observation_period_days = 14          -- Période d'observation 14j

-- Après 30 jours de copy trading, on compare :
SELECT
    w.initial_win_rate_percent AS "Expected Win Rate",
    p.win_rate AS "Actual Win Rate",
    CASE
        WHEN p.win_rate >= w.initial_win_rate_percent * 0.8 THEN 'OK'
        ELSE 'RED FLAG'
    END AS "Status"
FROM wallets w
JOIN performance p ON p.wallet_id = w.id
WHERE w.address = 'ABC...XYZ';
```

**Red flag detection** :
- Si `actual_win_rate < initial_win_rate * 0.8` → Wallet dégradé (pause ou désactivation)
- Si `actual_avg_pnl < initial_avg_pnl * 0.5` → Position sizing ou timing problématique

---

### Groupe Helius Sync 🔄
| Champ | Rationale |
|-------|-----------|
| `helius_synced_at` | **Timestamp dernière sync** vers le webhook Helius global |
| `helius_sync_status` | **Status sync** : `pending`, `synced`, `error` |

**Pourquoi ?**
⚠️ **Architecture critique** : Helius utilise **1 seul webhook GLOBAL** pour surveiller TOUS les wallets (pas 1 webhook par wallet).

**Workflow batch sync** (toutes les 5 minutes) :
```python
# Cron job: Toutes les 5 min
async def sync_wallets_to_helius():
    # 1. Récupérer tous les wallets actifs
    active_addresses = db.query("""
        SELECT address
        FROM wallets
        WHERE is_active = true
    """)

    # 2. Mettre à jour le webhook global Helius
    try:
        helius_client.update_webhook(
            webhook_id=config.helius_webhook_id,
            addresses=active_addresses  # Array de toutes les addresses
        )

        # 3. Marquer wallets comme synced
        db.execute("""
            UPDATE wallets
            SET helius_synced_at = NOW(),
                helius_sync_status = 'synced'
            WHERE is_active = true
        """)
    except Exception as e:
        # 4. Si erreur, marquer comme error
        db.execute("""
            UPDATE wallets
            SET helius_sync_status = 'error'
            WHERE is_active = true
        """)
```

**États possibles** :
- `pending` : Wallet ajouté mais pas encore sync vers Helius (< 5 min)
- `synced` : Wallet dans le webhook Helius, surveillance active
- `error` : Erreur lors sync (API Helius down, rate limit, etc.)

**Edge cases importants** :
1. **Wallet `is_active = true` mais `helius_sync_status = 'error'`**
   → Wallet pas surveillé ! Aucun signal reçu.
   → Dashboard doit afficher warning ⚠️

2. **Wallet désactivé (`is_active = false`)**
   → Batch sync le retire du webhook Helius
   → Plus de signaux reçus

3. **Latence 5 minutes**
   → Trade-off : Latence acceptable vs limite API Helius (1000 requêtes/min)
   → Wallet ajouté à 14h00 → Surveillé à partir de 14h05

---

### Groupe Status ✅
| Champ | Rationale |
|-------|-----------|
| `is_active` | **Actif/Inactif** - Wallet surveillé ou pausé |

**Pourquoi ?**
On peut désactiver un wallet temporairement (mauvaise performance, doute, maintenance) sans le supprimer (historique conservé).

**Impact `is_active = false`** :
- Retiré du webhook Helius au prochain batch sync (plus de signaux)
- Positions ouvertes continuent leur exit strategy normalement
- Performance historique conservée
- Peut être réactivé plus tard

---

### Groupe Metadata 🕐
| Champ | Rationale |
|-------|-----------|
| `created_at` | Date ajout du wallet dans la watchlist |
| `updated_at` | Dernière modification (auto-trigger) |
| `last_signal_at` | **Timestamp dernier signal reçu** de Helius pour ce wallet |
| `notes` | Notes libres admin |

**Pourquoi `last_signal_at` ?**
**Health check** - Si un wallet est `is_active = true` et `helius_sync_status = 'synced'` mais `last_signal_at` est NULL ou > 7 jours :
→ Soit le wallet est inactif (pas de trades)
→ Soit problème sync Helius (faux "synced")

**Query diagnostic** :
```sql
-- Wallets "morts" (actifs mais aucun signal depuis 7j)
SELECT address, label, last_signal_at
FROM wallets
WHERE is_active = true
  AND helius_sync_status = 'synced'
  AND (last_signal_at IS NULL OR last_signal_at < NOW() - INTERVAL '7 days');
```

---

## Relations avec autres tables

```
wallets (1)
    ↓ (1-to-N)
    ↓
positions (N) ← Toutes les positions prises en copiant ce wallet
    ↓
    └─ entry_tx_signature, exit_tx_signature (blockchain)

wallets (1)
    ↓ (1-to-N)
    ↓
signals (N) ← Tous les swaps détectés par Helius webhook
    ↓
    └─ signal_type ('swap_detected', 'liquidity_add', etc.)

wallets (1)
    ↓ (1-to-1)
    ↓
performance (1) ← Métriques agrégées (win rate, total PnL, etc.)

wallets (N)
    ↓ (N-to-1)
    ↓
exit_strategies (1) ← Stratégie par défaut assignée
```

---

## Exemples SQL

### Ajouter un wallet en watchlist (simulation)
```sql
INSERT INTO wallets (
    address,
    label,
    mode,
    exit_strategy_id,
    discovery_source,
    discovery_date,
    discovery_notes,
    initial_win_rate_percent,
    initial_trades_observed,
    initial_avg_pnl_percent,
    observation_period_days
) VALUES (
    'ABC123...XYZ789',
    'CryptoWhale #1',
    'simulation',  -- Mode simulation pour tester
    'uuid-strategy-default',
    'twitter',
    '2025-01-05',
    'Found via @CryptoGuru thread - Focus low-cap memecoins',
    68.00,  -- 68% win rate observé
    25,     -- Sur 25 trades
    12.50,  -- +12.5% avg PnL
    14      -- Observation 14 jours
);
```

### Passer un wallet de simulation → live
```sql
UPDATE wallets
SET mode = 'live',
    notes = 'Promoted to live after 30 days simulation - 65% win rate confirmed'
WHERE address = 'ABC123...XYZ789'
  AND mode = 'simulation';
```

### Wallets actifs non synchro Helius (problème !)
```sql
SELECT
    address,
    label,
    helius_sync_status,
    helius_synced_at,
    last_signal_at
FROM wallets
WHERE is_active = true
  AND helius_sync_status != 'synced';
```

### Wallets "silencieux" (pas de signal depuis 7j)
```sql
SELECT
    address,
    label,
    last_signal_at,
    EXTRACT(DAY FROM NOW() - last_signal_at) AS days_silent
FROM wallets
WHERE is_active = true
  AND helius_sync_status = 'synced'
  AND (last_signal_at IS NULL OR last_signal_at < NOW() - INTERVAL '7 days')
ORDER BY last_signal_at ASC NULLS FIRST;
```

### Analyser performance par source de découverte
```sql
SELECT
    w.discovery_source,
    COUNT(*) AS total_wallets,
    AVG(p.win_rate) AS avg_win_rate,
    AVG(p.total_pnl_usd) AS avg_total_pnl
FROM wallets w
JOIN performance p ON p.wallet_id = w.id
WHERE w.is_active = true
GROUP BY w.discovery_source
ORDER BY avg_win_rate DESC;
```

---

## Edge cases & FAQ

### Q: Pourquoi `exit_strategy_override` n'est PAS dans cette table ?
**R**: Moved to `positions.exit_strategy_override` (JSONB) pour **immutabilité**.

**Rationale** :
Si on change la stratégie d'un wallet, on ne veut PAS affecter les positions déjà ouvertes (snapshot à création).

**Exemple problématique si override était ici** :
```sql
-- Position ouverte avec stop loss 20%
INSERT INTO positions (wallet_id, entry_price, ...) VALUES (...);
-- → Stratégie snapshot: stop_loss = 20%

-- Admin change stratégie wallet → stop loss 30%
UPDATE wallets SET exit_strategy_override = '{"stop_loss_percent": 30}' WHERE id = X;

-- ❌ MAUVAIS: Position existante devrait garder 20%, pas 30%
-- ✅ BON: Override au niveau position = immutable snapshot
```

---

### Q: Que se passe-t-il si `helius_synced_at` est NULL ?
**R**: Wallet jamais sync → **Pas de surveillance webhook** → Aucun signal reçu.

**Causes possibles** :
1. Wallet ajouté il y a < 5 min (batch sync pas encore passé)
2. Batch sync en erreur (`helius_sync_status = 'error'`)
3. Wallet `is_active = false` (désactivé, pas sync)

**Action** :
Dashboard doit afficher warning ⚠️ si wallet actif mais pas sync depuis > 10 min.

---

### Q: Peut-on ajouter le même wallet plusieurs fois ?
**R**: ❌ Non - Contrainte `UNIQUE` sur `address`.

**Rationale** :
1 wallet = 1 configuration (mode, stratégie, etc.). Si on veut tester 2 stratégies différentes sur le même wallet, on utilise `positions.exit_strategy_override`.

---

### Q: Différence entre `is_active = false` et supprimer le wallet ?
**R**: `is_active = false` = **Pause** (réversible, historique conservé)
**DELETE** = **Suppression permanente** (CASCADE supprime positions, signals, performance)

**Recommandation** : Toujours utiliser `is_active = false` sauf si vraiment besoin de purger data (GDPR, etc.).

---

### Q: Comment détecter un wallet "fake" (wash trading) ?
**R**: Comparer `initial_win_rate` vs `actual_win_rate` après 30 jours :

```sql
SELECT
    w.address,
    w.initial_win_rate_percent AS expected,
    p.win_rate AS actual,
    ROUND((p.win_rate - w.initial_win_rate_percent) / w.initial_win_rate_percent * 100, 2) AS delta_percent
FROM wallets w
JOIN performance p ON p.wallet_id = w.id
WHERE w.initial_win_rate_percent IS NOT NULL
  AND p.total_positions >= 20  -- Au moins 20 trades pour statistique valide
ORDER BY delta_percent ASC;  -- Les plus gros écarts en premier
```

**Red flags** :
- `delta_percent < -30%` → Performance réelle 30% pire qu'observé (fake wash trading)
- `p.signal_count_24h > 100` → Hyperactivité suspecte (bot)

---

## Indexes expliqués

| Index | Rationale |
|-------|-----------|
| `idx_wallets_address` | Recherche wallet par address (UI, API) |
| `idx_wallets_mode WHERE is_active = true` | Dashboard filtré par mode (simulation/live) - Wallets actifs seulement |
| `idx_wallets_active` | Toggle actif/inactif rapide |
| `idx_wallets_last_signal` | Health check (détecter wallets silencieux) |
| `idx_wallets_exit_strategy_id` | JOIN avec exit_strategies |
| `idx_wallets_discovery_source WHERE discovery_source IS NOT NULL` | Analytics par canal de découverte |
| `idx_wallets_sync_pending WHERE is_active AND status = 'pending'` | Batch sync cible les wallets pending |
| `idx_wallets_sync_health ON (helius_synced_at, last_signal_at) WHERE is_active` | Dashboard health check (sync OK mais pas de signaux) |

---

## Triggers

### `wallets_updated_at`
Auto-update `updated_at` à chaque modification :
```sql
CREATE TRIGGER wallets_updated_at
BEFORE UPDATE ON wallets
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
```

---

## Décisions architecturales

### ADR-001: Helius Global Webhook (Critique !)

**Contexte** :
Helius ne permet pas de créer 1 webhook par wallet (limite API, coût, complexité).

**Décision** :
Un seul webhook global pour tous les wallets actifs.

**Implementation** :
```python
# Webhook global configuré 1 seule fois
config.helius_webhook_id = "wh_abc123"
config.helius_webhook_url = "https://walltrack.app/api/webhooks/helius"

# Batch sync toutes les 5 min (cron job)
active_addresses = [wallet.address for wallet in wallets if wallet.is_active]
helius.update_webhook(webhook_id, addresses=active_addresses)
```

**Conséquences** :
- ✅ Scalable (1000+ wallets avec 1 seul webhook)
- ✅ Coût fixe (pas de multiplication webhooks)
- ❌ Latence 5 min (wallet ajouté → surveillé 5 min après)
- ❌ Complexité batch sync (cron job à maintenir)

**Trade-offs acceptés** :
Latence 5 min acceptable (trading positions > 1h typiquement).

---

## Pour les agents

**Stories concernées** :
- **Story 3.1** : Wallet Registry CRUD (UI Gradio + repository)
- **Story 3.2** : Wallet Discovery Flow (sources, initial performance)
- **Story 3.5** : Helius Batch Sync Worker (cron 5 min)

**Workflow implémentation** :
1. Créer migration `003_wallets_table.sql` avec COMMENT ON
2. Créer repository `WalletRepository` (CRUD)
3. Créer service `WalletDiscoveryService` (capture initial metrics)
4. Créer worker `HeliusSyncWorker` (batch sync 5 min)
5. Créer UI Gradio watchlist management

**Tests critiques** :
- Constraint `address UNIQUE` (reject duplicate)
- Constraint `discovery_source CHECK IN` (reject invalid source)
- Batch sync updates `helius_synced_at` correctement
- Wallet `is_active = false` retiré du webhook
- Health check détecte wallets silencieux (no signals > 7d)
