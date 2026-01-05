# Table: signals - Design Guide

## Pattern architectural
**Pattern**: **Event Sourcing** (Audit trail complet, immutable)
**Objectif**: Journal de TOUS les signaux Helius (swaps détectés) pour audit et analytics

---

## Rationale - Event Sourcing Pattern

**Pourquoi immutable ?**
- Audit complet : Traçabilité de chaque signal reçu (RGPD, compliance)
- Analytics : "Combien de signaux wallet X génère par jour ?"
- Debug : "Pourquoi position pas créée pour ce signal ?"

**Never UPDATE, only INSERT** :
```python
# ✅ BON
db.insert(signals, {...})

# ❌ MAUVAIS
db.update(signals, id=X, {...})  # Interdit !
```

---

## Rationale par groupe de champs

### Groupe Signal Data 📡

| Champ | Rationale |
|-------|-----------|
| `wallet_address` | Wallet source du signal (ex: "ABC...XYZ")<br/>**Pas FK** vers wallets (peut recevoir signaux de wallets non-tracked) |
| `token_address` | Token concerné par le swap |
| `signal_type` | Type signal ('swap_detected', 'liquidity_add', 'liquidity_remove', 'other') |
| `action` | Action swap ('buy' ou 'sell') |
| `amount` | Montant tokens swappés |
| `price_usd` | Prix USD au moment du swap |
| `value_usd` | Valeur totale USD du swap |

**Pourquoi wallet_address TEXT et pas FK ?**
→ Helius envoie signaux pour TOUTES addresses surveillées (même si wallet désactivé temporairement).

### Groupe Processing 🔄

| Champ | Rationale |
|-------|-----------|
| `processed` | Signal traité ? (false → pending, true → processed)<br/>Worker poll `WHERE processed = false ORDER BY received_at` |
| `processed_at` | Timestamp traitement<br/>**Latency metric**: `processed_at - received_at` |
| `action_taken` | Action prise ('position_created', 'rejected_safety', 'ignored_sell', 'circuit_breaker_active', etc.) |
| `rejection_reason` | Raison rejet si applicable (ex: "Token safety score too low")<br/>Debug + analytics |

**Processing workflow** :
```python
# 1. Signal reçu de Helius
db.insert(signals, {processed: false, received_at: NOW()})

# 2. Worker traite
signal = db.query("SELECT * FROM signals WHERE processed = false LIMIT 1")

# 3. Décision
if should_create_position(signal):
    create_position(signal)
    action_taken = 'position_created'
else:
    action_taken = 'rejected_safety'
    rejection_reason = 'Low liquidity'

# 4. Mark processed
db.update(signals, id=signal.id, {
    processed: true,
    processed_at: NOW(),
    action_taken: action_taken,
    rejection_reason: rejection_reason
})
```

### Groupe Metadata 🕐

| Champ | Rationale |
|-------|-----------|
| `received_at` | Timestamp réception webhook Helius<br/>**PAS created_at** : On veut timestamp réel du signal |
| `helius_signature` | Signature HMAC payload Helius<br/>**Sécurité** : Valide que payload vient vraiment de Helius |
| `raw_payload` | Payload JSON brut de Helius (JSONB)<br/>**Forensics** : Debug si parsing échoue |

---

## Relations avec autres tables

```
signals (N)
    ↓
wallets (1) ← wallet_address lookup (pas FK)

signals (N)
    ↓
tokens (1) ← token_address lookup (pas FK)

signals (1)
    ↓
positions (1) ← position.signal_id FK (si position créée)
```

---

## Exemples SQL

### Signaux non traités (worker queue)
```sql
SELECT *
FROM signals
WHERE processed = false
ORDER BY received_at ASC
LIMIT 100;
```

### Taux de rejet par raison
```sql
SELECT
    rejection_reason,
    COUNT(*) AS count
FROM signals
WHERE action_taken LIKE 'rejected%'
GROUP BY rejection_reason
ORDER BY count DESC;
```

### Latency moyenne traitement
```sql
SELECT
    AVG(EXTRACT(EPOCH FROM (processed_at - received_at))) AS avg_latency_seconds
FROM signals
WHERE processed = true
  AND received_at > NOW() - INTERVAL '24 hours';
```

### Signaux wallet spécifique (24h)
```sql
SELECT
    signal_type,
    action,
    value_usd,
    action_taken
FROM signals
WHERE wallet_address = 'ABC...XYZ'
  AND received_at > NOW() - INTERVAL '24 hours'
ORDER BY received_at DESC;
```

---

## Edge cases & FAQ

### Q: Pourquoi stocker raw_payload (JSONB) ?
**R**: Debug - Si parsing échoue, on peut re-parser le payload brut manuellement.

### Q: Signaux peuvent-ils être supprimés ?
**R**: Techniquement oui, mais **déconseillé** (event sourcing = immutable). Archivage plutôt que DELETE.

### Q: Que se passe-t-il si même signal reçu 2 fois (duplicate) ?
**R**: Idempotency check via `helius_signature` UNIQUE ou dedup logic dans worker.

---

## Pour les agents

**Stories concernées** :
- **Story 3.3** : Helius Webhook Handler (receive & insert signals)
- **Story 3.4** : Signal Processing Worker (process pending signals)

**Tests critiques** :
- Signals immutability (no UPDATE allowed)
- Processing queue (FIFO order)
- Latency tracking (processed_at - received_at)
- Rejection reason analytics
