# Table: config - Design Guide

## Pattern architectural
**Pattern**: **Configuration Singleton**
**Objectif**: Configuration système globale (1 seule row) avec Helius webhook global + risk management

---

## Vue d'ensemble - Schéma complet

| Groupe | Champ | Type | Contraintes | Default | Description |
|--------|-------|------|-------------|---------|-------------|
| **PK** | id | UUID | PRIMARY KEY | gen_random_uuid() | Identifiant unique |
| **Trading** | capital | NUMERIC(12,2) | NOT NULL | 300.00 | Capital total disponible |
| **Trading** | risk_per_trade_percent | NUMERIC(5,2) | NOT NULL | 2.00 | Risque par trade (% du capital) |
| **Trading** | position_sizing_mode | TEXT | NOT NULL | 'fixed_percent' | Mode de sizing |
| **Risk Mgmt** | slippage_tolerance_percent | NUMERIC(5,2) | NOT NULL | 3.00 | Tolérance slippage |
| **Risk Mgmt** | max_drawdown_percent | NUMERIC(5,2) | NOT NULL | 20.00 | Drawdown max avant CB |
| **Risk Mgmt** | min_win_rate_alert | NUMERIC(5,2) | NOT NULL | 40.00 | Win rate min avant CB |
| **Risk Mgmt** | consecutive_max_loss_trigger | INTEGER | NOT NULL | 6 | Pertes consécutives avant CB |
| **Safety** | safety_score_threshold | NUMERIC(3,2) | NOT NULL | 0.60 | Score safety minimum |
| **Safety** | min_liquidity_usd | NUMERIC(12,2) | NOT NULL | 50000.00 | Liquidité minimum requise |
| **Safety** | max_top_10_holder_percent | NUMERIC(5,2) | NOT NULL | 80.00 | % max détenu top 10 holders |
| **Safety** | min_token_age_hours | INTEGER | NOT NULL | 0 | Age minimum token (heures) |
| **Monitoring** | price_polling_interval_seconds | INTEGER | NOT NULL | 45 | Intervalle polling prix |
| **Monitoring** | webhook_timeout_alert_hours | INTEGER | NOT NULL | 48 | Timeout webhook avant alerte |
| **Monitoring** | max_price_staleness_minutes | INTEGER | NOT NULL | 5 | Staleness max prix |
| **Status** | webhook_last_signal_at | TIMESTAMPTZ | | NULL | Dernier signal webhook reçu |
| **Status** | circuit_breaker_active | BOOLEAN | NOT NULL | false | Circuit breaker actif |
| **Status** | circuit_breaker_reason | TEXT | | NULL | Raison activation CB |
| **Status** | circuit_breaker_activated_at | TIMESTAMPTZ | | NULL | Date activation CB |
| **Helius** | helius_webhook_id | TEXT | | NULL | ID du webhook Helius global |
| **Helius** | helius_webhook_url | TEXT | | NULL | URL endpoint webhook |
| **Helius** | helius_webhook_secret | TEXT | | NULL | Secret pour validation signatures |
| **Helius** | helius_last_sync_at | TIMESTAMPTZ | | NULL | Dernière sync liste wallets |
| **Helius** | helius_sync_error | TEXT | | NULL | Dernière erreur sync |
| **Metadata** | created_at | TIMESTAMPTZ | | NOW() | Date création |
| **Metadata** | updated_at | TIMESTAMPTZ | | NOW() | Date dernière MàJ |

---

## Rationale par groupe de champs

### Groupe Trading 💰

**Pourquoi ?**
Paramètres fondamentaux de position sizing - Combien risquer par trade ? Quel capital disponible ?

| Champ | Rationale |
|-------|-----------|
| `capital` | Capital total disponible pour trading (ex: $300 USD)<br/>**Update manuel** quand on ajoute/retire fonds |
| `risk_per_trade_percent` | Risque par trade en % du capital (ex: 2% = $6 max loss par trade si capital = $300)<br/>**Position sizing**: `position_size = capital * risk_per_trade / stop_loss_percent` |
| `position_sizing_mode` | Algorithme de sizing : `fixed_percent` (fixe), `kelly` (Kelly Criterion), `martingale` (progression)<br/>**MVP**: fixed_percent seulement |

**Exemple calcul position** :
```python
capital = 300
risk_per_trade = 2.0  # 2%
stop_loss = 20.0  # 20%

max_loss_usd = capital * (risk_per_trade / 100)  # $6
position_size_usd = max_loss_usd / (stop_loss / 100)  # $6 / 0.20 = $30
```

---

### Groupe Risk Management 🛡️

**Pourquoi ?**
Seuils de circuit breaker - Quand arrêter de trader pour protéger le capital

| Champ | Rationale |
|-------|-----------|
| `slippage_tolerance_percent` | Slippage max accepté (ex: 3%)<br/>Si `slippage_actual > 3%` → Ordre rejected |
| `max_drawdown_percent` | Drawdown max avant activation circuit breaker (ex: -20%)<br/>Si PnL global < -20% → CB activated |
| `min_win_rate_alert` | Win rate min avant activation CB (ex: 40%)<br/>Si win_rate < 40% → CB activated |
| `consecutive_max_loss_trigger` | Pertes consécutives max (ex: 6)<br/>Si 6 trades perdants d'affilée → CB activated |

**Circuit breaker workflow** :
```python
if current_drawdown <= -max_drawdown_percent:
    activate_circuit_breaker(reason='max_drawdown')
elif current_win_rate < min_win_rate_alert:
    activate_circuit_breaker(reason='min_win_rate')
elif current_loss_streak >= consecutive_max_loss_trigger:
    activate_circuit_breaker(reason='consecutive_losses')
```

---

### Groupe Safety 🔒

**Pourquoi ?**
Filtres de sécurité token - Éviter les rugpulls, scams, low liquidity

| Champ | Rationale |
|-------|-----------|
| `safety_score_threshold` | Score minimum 0-1 (ex: 0.60 = 60%)<br/>Si `token.safety_score < 0.60` → Trade rejected |
| `min_liquidity_usd` | Liquidité minimum USD (ex: $50k)<br/>Évite les tokens illiquides (slippage énorme) |
| `max_top_10_holder_percent` | % max détenu par top 10 holders (ex: 80%)<br/>Si > 80% → Centralisé = rug risk |
| `min_token_age_hours` | Age minimum token en heures (ex: 0 = pas de filtre, 24 = > 1 jour)<br/>Filtre tokens trop récents (pump & dump) |

**Safety check example** :
```python
if token.safety_score < config.safety_score_threshold:
    return "REJECTED: Low safety score"
if token.liquidity_usd < config.min_liquidity_usd:
    return "REJECTED: Insufficient liquidity"
if token.holder_distribution_top_10_percent > config.max_top_10_holder_percent:
    return "REJECTED: Too centralized"
```

---

### Groupe Monitoring 👁️

**Pourquoi ?**
Paramètres de surveillance système - Fréquence polling, timeouts

| Champ | Rationale |
|-------|-----------|
| `price_polling_interval_seconds` | Intervalle mise à jour prix (ex: 45s)<br/>Cron job poll DexScreener/Helius toutes les 45s |
| `webhook_timeout_alert_hours` | Timeout webhook avant alerte (ex: 48h)<br/>Si `NOW() - webhook_last_signal_at > 48h` → Alert (webhook down ?) |
| `max_price_staleness_minutes` | Prix max staleness (ex: 5 min)<br/>Si `NOW() - last_price_update > 5 min` → Prix obsolète, ne pas trader |

---

### Groupe Status 🚦

**Pourquoi ?**
État runtime du système - Circuit breaker actif ? Dernier signal webhook ?

| Champ | Rationale |
|-------|-----------|
| `webhook_last_signal_at` | Timestamp dernier signal Helius reçu<br/>**Health check** : Si > 48h → Webhook potentiellement down |
| `circuit_breaker_active` | Circuit breaker actif ? (true/false)<br/>Si true → Nouvelles positions bloquées |
| `circuit_breaker_reason` | Raison activation CB (ex: 'max_drawdown', 'min_win_rate', 'consecutive_losses', 'manual') |
| `circuit_breaker_activated_at` | Timestamp activation CB<br/>Durée downtime = `NOW() - circuit_breaker_activated_at` |

---

### Groupe Helius 🌐

**Pourquoi ?**
**CRITIQUE** - Configuration du webhook GLOBAL Helius (1 seul webhook pour tous les wallets)

| Champ | Rationale |
|-------|-----------|
| `helius_webhook_id` | ID webhook Helius (ex: `wh_abc123`)<br/>Créé 1 fois via API Helius, stocké ici |
| `helius_webhook_url` | URL endpoint webhook (ex: `https://walltrack.app/api/webhooks/helius`)<br/>Notre serveur reçoit les payloads ici |
| `helius_webhook_secret` | Secret HMAC pour valider signatures payloads<br/>Sécurité : vérifie que payload vient bien de Helius |
| `helius_last_sync_at` | Timestamp dernière sync liste wallets vers webhook<br/>Batch sync toutes les 5 min |
| `helius_sync_error` | Dernière erreur sync (ex: "API rate limit exceeded")<br/>NULL si sync OK |

**Helius webhook lifecycle** :
```python
# 1. Initial setup (one-time)
webhook = helius_client.create_webhook(
    url="https://walltrack.app/api/webhooks/helius",
    events=["SWAP"],
    addresses=[]  # Empty initially
)
config.helius_webhook_id = webhook.id
config.helius_webhook_secret = webhook.secret

# 2. Batch sync (every 5 minutes)
active_addresses = db.query("SELECT address FROM wallets WHERE is_active = true")
helius_client.update_webhook(
    webhook_id=config.helius_webhook_id,
    addresses=active_addresses
)
config.helius_last_sync_at = NOW()
```

---

## Singleton Pattern

**Contrainte UNIQUE** : 1 seule row dans cette table

**Implementation** :
```sql
-- Trigger pour empêcher INSERT si row existe déjà
CREATE TRIGGER config_singleton_check
BEFORE INSERT ON config
FOR EACH ROW
EXECUTE FUNCTION prevent_multiple_rows();

-- Function
CREATE FUNCTION prevent_multiple_rows() RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT COUNT(*) FROM config) >= 1 THEN
        RAISE EXCEPTION 'config table is singleton - only 1 row allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

**Usage** :
```sql
-- Initial insert (setup)
INSERT INTO config (capital, risk_per_trade_percent, ...) VALUES (...);

-- Updates only
UPDATE config SET capital = 500.00 WHERE id = (SELECT id FROM config LIMIT 1);
```

---

## Relations avec autres tables

Aucune FK directe - Config est référencée par l'application mais pas par les autres tables.

**Usage** :
- `wallets` batch sync lit `config.helius_webhook_id`
- Circuit breaker lit `config.max_drawdown_percent`, `config.min_win_rate_alert`, etc.
- Position sizing lit `config.capital`, `config.risk_per_trade_percent`

---

## Exemples SQL

### Get current config
```sql
SELECT * FROM config LIMIT 1;
```

### Update capital
```sql
UPDATE config
SET capital = 500.00,
    notes = 'Increased capital from $300 to $500'
WHERE id = (SELECT id FROM config LIMIT 1);
```

### Check circuit breaker status
```sql
SELECT
    circuit_breaker_active,
    circuit_breaker_reason,
    circuit_breaker_activated_at,
    EXTRACT(HOUR FROM NOW() - circuit_breaker_activated_at) AS hours_active
FROM config
WHERE circuit_breaker_active = true;
```

### Health check webhook
```sql
SELECT
    webhook_last_signal_at,
    EXTRACT(HOUR FROM NOW() - webhook_last_signal_at) AS hours_since_last_signal,
    CASE
        WHEN NOW() - webhook_last_signal_at > INTERVAL '48 hours' THEN 'ALERT'
        ELSE 'OK'
    END AS status
FROM config;
```

---

## Edge cases & FAQ

### Q: Pourquoi singleton ? Pourquoi pas multiple configs ?
**R**: Simplicité MVP - 1 seul compte, 1 seule config. Future : Multi-account support = config table devient `account_configs` avec account_id FK.

### Q: Que se passe-t-il si helius_webhook_id est NULL ?
**R**: Aucun signal reçu - Workflow setup doit créer le webhook Helius au démarrage de l'app.

### Q: Circuit breaker peut-il être désactivé manuellement ?
**R**: Oui :
```sql
UPDATE config
SET circuit_breaker_active = false,
    circuit_breaker_reason = NULL,
    notes = 'Manually deactivated - Issue resolved'
WHERE id = (SELECT id FROM config LIMIT 1);
```

---

## Pour les agents

**Stories concernées** :
- **Story 1.1** : Configuration Management (CRUD config via UI Gradio)
- **Story 2.1** : Circuit Breaker Implementation
- **Story 3.5** : Helius Webhook Setup & Batch Sync

**Tests critiques** :
- Singleton constraint (2nd INSERT rejected)
- Circuit breaker auto-activation sur drawdown > threshold
- Webhook health check alerts
