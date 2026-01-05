# Table: orders - Design Guide

## Pattern architectural
**Pattern**: **Command Log** (Transaction history avec retry mechanism)
**Objectif**: Journal de TOUS les ordres (entry/exit) avec tracking execution + slippage

---

## Rationale - Command Log Pattern

**Pourquoi un log ?**
- **Idempotency** : Retry safe (même ordre pas exécuté 2 fois)
- **Audit trail** : Compliance + analytics
- **Slippage tracking** : Requested vs actual price

**Workflow** :
```python
# 1. Create order (pending)
order_id = db.insert(orders, {
    status: 'pending',
    requested_price: 1.00,
    requested_amount: 100
})

# 2. Submit to blockchain
tx_signature = submit_swap(order)
db.update(orders, id=order_id, {status: 'submitted', tx_signature: tx_signature})

# 3. Confirm execution
actual_price = get_execution_price(tx_signature)
db.update(orders, id=order_id, {
    status: 'executed',
    executed_price: actual_price,
    executed_at: NOW()
})
```

---

## Rationale par groupe de champs

### Groupe Order Type 📋

| Champ | Rationale |
|-------|-----------|
| `order_type` | Type ordre : `entry`, `exit_stop_loss`, `exit_trailing_stop`, `exit_scaling`, `exit_mirror`, `exit_manual`<br/>**Analytics** : Combien de stop loss triggered vs scaling exits ? |

**Order types** :
- `entry` : Ordre d'entrée (copie wallet source)
- `exit_stop_loss` : Exit stop loss
- `exit_trailing_stop` : Exit trailing stop
- `exit_scaling` : Exit scaling out (2x, 3x)
- `exit_mirror` : Exit mirror (wallet source a vendu)
- `exit_manual` : Exit manuelle (user click)

### Groupe Request (Ce qu'on voulait) 📝

| Champ | Rationale |
|-------|-----------|
| `requested_price` | Prix demandé<br/>**Slippage calc** : `(executed_price - requested_price) / requested_price` |
| `requested_amount` | Montant demandé |
| `requested_value_usd` | Valeur USD demandée |
| `requested_at` | Timestamp demande |

### Groupe Execution (Ce qu'on a eu) ✅

| Champ | Rationale |
|-------|-----------|
| `executed_price` | Prix réel exécution<br/>NULL si pas encore exécuté |
| `executed_amount` | Montant réel exécuté |
| `executed_value_usd` | Valeur USD réelle |
| `executed_at` | Timestamp exécution blockchain |
| `tx_signature` | Signature transaction Solana<br/>**Idempotency** : UNIQUE si non-NULL |

### Groupe Slippage 📉

| Champ | Rationale |
|-------|-----------|
| `slippage_percent` | Slippage réel calculé : `((executed - requested) / requested) * 100`<br/>**KPI** : Moyenne slippage par DEX/token |

**Auto-calculated** :
```sql
CREATE TRIGGER orders_calculate_slippage
AFTER UPDATE ON orders
FOR EACH ROW
WHEN (NEW.executed_price IS NOT NULL AND OLD.executed_price IS NULL)
EXECUTE FUNCTION calculate_slippage();
```

### Groupe Retry 🔄

| Champ | Rationale |
|-------|-----------|
| `retry_count` | Nombre de tentatives (0 = 1ère tentative) |
| `max_retries` | Max retries autorisés (ex: 3) |
| `retry_reason` | Raison dernier retry (ex: "RPC timeout", "Insufficient balance") |

**Retry logic** :
```python
if order.status == 'failed' and order.retry_count < order.max_retries:
    retry_order(order)
    db.update(orders, id=order.id, {retry_count: order.retry_count + 1})
```

### Groupe Status 🚦

| Champ | Rationale |
|-------|-----------|
| `status` | Workflow : `pending` → `submitted` → `executed` / `failed` / `cancelled`<br/>**Index** : Query pending orders for worker |

**Status workflow** :
```
pending → submitted → executed (success)
       ↓           ↓
       ↓           → failed (retry if retry_count < max_retries)
       ↓
       → cancelled (manual cancel or timeout)
```

---

## Relations avec autres tables

```
orders (N)
    ↓
wallet_id FK → wallets (1)
token_id FK → tokens (1)
position_id FK → positions (1)
signal_id FK → signals (1) ← Si order créé depuis signal
```

---

## Exemples SQL

### Pending orders (worker queue)
```sql
SELECT *
FROM orders
WHERE status IN ('pending', 'submitted')
  AND retry_count < max_retries
ORDER BY requested_at ASC;
```

### Slippage moyen par token
```sql
SELECT
    t.symbol,
    AVG(o.slippage_percent) AS avg_slippage,
    COUNT(*) AS total_orders
FROM orders o
JOIN tokens t ON o.token_id = t.id
WHERE o.status = 'executed'
  AND o.slippage_percent IS NOT NULL
GROUP BY t.symbol
ORDER BY avg_slippage DESC;
```

### Orders failed (pour investigation)
```sql
SELECT
    order_type,
    retry_reason,
    COUNT(*) AS count
FROM orders
WHERE status = 'failed'
  AND retry_count >= max_retries
GROUP BY order_type, retry_reason
ORDER BY count DESC;
```

---

## Edge cases & FAQ

### Q: Ordre peut-il être UPDATE après executed ?
**R**: ❌ Non - Executed orders immutable (command log pattern).

### Q: Que se passe-t-il si tx_signature identique reçu 2 fois ?
**R**: UNIQUE constraint → 2ème INSERT rejected (idempotency).

### Q: Slippage négatif possible ?
**R**: Oui ! Slippage < 0 = meilleur prix que demandé (rare mais possible).

---

## Pour les agents

**Stories concernées** :
- **Story 5.1** : Order Submission (create & submit orders)
- **Story 5.2** : Order Execution Tracking (poll blockchain, update executed_*)
- **Story 5.3** : Slippage Analytics

**Tests critiques** :
- Status workflow (pending → submitted → executed)
- Retry logic (max_retries enforcement)
- Slippage auto-calculation trigger
- tx_signature uniqueness (idempotency)
