# Table: circuit_breaker_events - Design Guide

## Pattern architectural
**Pattern**: **Event Sourcing** (Audit trail activations/désactivations circuit breaker)
**Objectif**: Tracer TOUS les déclenchements CB pour compliance + post-mortem analysis

---

## Rationale - Event Sourcing Pattern

**Pourquoi immutable ?**
- **Compliance** : Audit trail complet des arrêts de trading
- **Post-mortem** : Analyser pourquoi CB activé (drawdown ? win rate ? pertes consécutives ?)
- **Calibration** : Seuils trop sensibles ? Pas assez ?

**Event pairs** :
```python
# 1. Activation
db.insert(circuit_breaker_events, {
    event_type: 'activated',
    trigger_reason: 'max_drawdown',
    current_drawdown_percent: -18.5
})

# 2. Désactivation (manuel ou auto après résolution)
db.insert(circuit_breaker_events, {
    event_type: 'deactivated'
})
```

---

## Rationale par groupe de champs

### Groupe Data 📋

| Champ | Rationale |
|-------|-----------|
| `event_type` | Lifecycle : `activated` ou `deactivated`<br/>**Pattern** : Event pairs (1 activation → 1 deactivation) |
| `trigger_reason` | Root cause : `max_drawdown`, `min_win_rate`, `consecutive_losses`, `manual` |

**Trigger reasons** :
- `max_drawdown` : Drawdown global > seuil (ex: -20%)
- `min_win_rate` : Win rate < seuil (ex: < 40%)
- `consecutive_losses` : Pertes consécutives >= seuil (ex: 5 trades perdants)
- `manual` : Admin activation manuelle

### Groupe Metrics (Snapshot au moment activation) 📊

| Champ | Rationale |
|-------|-----------|
| `current_drawdown_percent` | Drawdown au moment exact (ex: -18.5%)<br/>**Forensics** : Valide calibration seuil |
| `current_win_rate` | Win rate au moment exact (ex: 52%)<br/>Utile si trigger = `min_win_rate` |
| `consecutive_losses` | Pertes consécutives au moment exact (ex: 5)<br/>Utile si trigger = `consecutive_losses` |

**Pourquoi snapshots ?**
→ État EXACT du système au moment du trigger. Permet de valider si seuils bien calibrés.

**Exemple analysis** :
```sql
SELECT
    trigger_reason,
    AVG(current_drawdown_percent) AS avg_drawdown_at_activation
FROM circuit_breaker_events
WHERE event_type = 'activated'
  AND trigger_reason = 'max_drawdown'
GROUP BY trigger_reason;
-- → Si avg_drawdown = -19.8% et seuil = -20%, on est très proche (seuil bien calibré)
```

### Groupe Thresholds (Seuils utilisés au moment activation) ⚙️

| Champ | Rationale |
|-------|-----------|
| `max_drawdown_threshold` | Seuil drawdown qui a déclenché (ex: -20.0%)<br/>Snapshot de `config.max_drawdown_percent` |
| `min_win_rate_threshold` | Seuil win rate qui a déclenché (ex: 40.0%)<br/>Snapshot de `config.min_win_rate_alert` |
| `consecutive_loss_threshold` | Seuil pertes consécutives (ex: 5)<br/>Snapshot de `config.consecutive_max_loss_trigger` |

**Pourquoi snapshot thresholds ?**
→ Config peut changer dans le temps. On veut savoir quel seuil était actif au moment du trigger.

**Exemple** :
```python
# 05/01/2026 : CB activé avec seuil -20%
circuit_breaker_events.insert({
    max_drawdown_threshold: -20.0,
    current_drawdown_percent: -20.1
})

# 10/01/2026 : Admin change seuil → -15%
config.update(max_drawdown_percent: -15.0)

# Événement historique conserve seuil -20% (comparabilité)
```

### Groupe Impact (Business impact quantification) 🚫

| Champ | Rationale |
|-------|-----------|
| `new_positions_blocked` | Compteur signaux rejetés pendant CB actif<br/>**FOMO metric** : Combien d'opportunités manquées ? |
| `open_positions_at_activation` | Snapshot positions ouvertes au moment activation<br/>**Exposure** : Combien de positions encore exposées ? |

**IMPORTANT** : Circuit breaker NE FERME PAS les positions existantes.

**Workflow** :
```python
if circuit_breaker.active:
    # ✅ Positions ouvertes continuent exit strategies normalement
    continue_exit_strategies()

    # ❌ Nouvelles positions bloquées
    if signal.action == 'buy':
        reject_signal(reason='circuit_breaker_active')
        increment_new_positions_blocked()
```

**Impact analysis** :
```sql
-- CB activé 2h, 47 signaux bloqués
-- → Si tokens ont pumped +50% → Opportunité manquée (mauvais)
-- → Si tokens ont dumped -30% → Protection efficace (bon)
```

### Groupe Metadata 🕐

| Champ | Rationale |
|-------|-----------|
| `created_at` | Timestamp activation CB |
| `deactivated_at` | Timestamp désactivation CB<br/>NULL si encore actif |
| `notes` | Free text admin (ex: "Manually deactivated - False positive") |

**Downtime calculation** :
```sql
SELECT
    created_at AS activation,
    deactivated_at AS deactivation,
    EXTRACT(HOUR FROM (deactivated_at - created_at)) AS hours_downtime
FROM circuit_breaker_events
WHERE event_type = 'activated'
ORDER BY hours_downtime DESC;
```

---

## Relations avec autres tables

Aucune FK - Table standalone (audit trail global).

**Usage** :
- Circuit breaker lit `config.max_drawdown_percent`, `config.min_win_rate_alert`
- Circuit breaker insère event dans `circuit_breaker_events`

---

## Exemples SQL

### CB actuellement actif ?
```sql
SELECT *
FROM circuit_breaker_events
WHERE event_type = 'activated'
  AND deactivated_at IS NULL
ORDER BY created_at DESC
LIMIT 1;
```

### Durée moyenne downtime par trigger reason
```sql
SELECT
    trigger_reason,
    AVG(EXTRACT(HOUR FROM (deactivated_at - created_at))) AS avg_hours_downtime,
    COUNT(*) AS activation_count
FROM circuit_breaker_events
WHERE event_type = 'activated'
  AND deactivated_at IS NOT NULL
GROUP BY trigger_reason
ORDER BY avg_hours_downtime DESC;
```

### Impact analysis (signaux bloqués)
```sql
SELECT
    DATE_TRUNC('day', created_at) AS date,
    SUM(new_positions_blocked) AS total_blocked
FROM circuit_breaker_events
WHERE event_type = 'activated'
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY total_blocked DESC;
```

### Dernières activations (dashboard alert)
```sql
SELECT
    trigger_reason,
    current_drawdown_percent,
    current_win_rate,
    consecutive_losses,
    created_at
FROM circuit_breaker_events
WHERE event_type = 'activated'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Edge cases & FAQ

### Q: Circuit breaker peut-il être activé plusieurs fois simultanément ?
**R**: ❌ Non - 1 seul CB global. Si déjà actif, pas de nouveau event (idempotency).

### Q: Positions ouvertes fermées automatiquement lors activation CB ?
**R**: ❌ NON ! Circuit breaker bloque NOUVELLES positions seulement.

**Workflow** :
```python
if circuit_breaker.active:
    reject_new_signals()  # ✅ Bloquer nouvelles entrées
    # continue_exit_strategies()  # ✅ Positions ouvertes terminent normalement
```

**Rationale** :
- Panic selling = mauvais (capitulation au pire moment)
- Protection seulement sur nouvelles entrées = bon (stop bleeding)

### Q: Que se passe-t-il si CB activé manuellement sans trigger metrics ?
**R**: Metrics peuvent être NULL (trigger_reason = 'manual').

---

## Pour les agents

**Stories concernées** :
- **Story 2.1** : Circuit Breaker Implementation (activation/deactivation logic)
- **Story 2.3** : Circuit Breaker Analytics (impact analysis)

**Tests critiques** :
- Event pairs (activation → deactivation)
- Snapshots metrics/thresholds précis au moment activation
- new_positions_blocked increment
- Positions ouvertes continuent (pas de fermeture auto)
