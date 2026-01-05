# Table: performance - Design Guide

## Pattern architectural
**Pattern**: **Materialized View** (Métriques agrégées précalculées avec batch refresh)
**Objectif**: Dashboard wallet avec win rate, PnL total, streaks - Recalcul quotidien 00:00 UTC

---

## Rationale - Materialized View Pattern

**Pourquoi précalculer ?**
Dashboard charge rapide → Calculs temps réel trop coûteux.

**Comparaison** :
```sql
-- ❌ MAUVAIS : Temps réel (trop lent pour dashboard)
SELECT
    COUNT(*) AS total_positions,
    AVG(CASE WHEN realized_pnl_usd > 0 THEN 1 ELSE 0 END) AS win_rate
FROM positions
WHERE wallet_id = X AND status = 'closed';
-- Query time: 500ms (unacceptable)

-- ✅ BON : Précalculé (ultra-rapide)
SELECT win_rate, total_positions FROM performance WHERE wallet_id = X;
-- Query time: 2ms
```

**Refresh strategy** :
```python
# Batch job quotidien à 00:00 UTC
def refresh_performance_metrics():
    for wallet in active_wallets:
        metrics = calculate_metrics(wallet)
        db.upsert(performance, wallet_id=wallet.id, **metrics)
```

---

## Rationale par groupe de champs

### Groupe Win Rate 🎯

| Champ | Rationale |
|-------|-----------|
| `total_positions` | Total positions fermées (dénominateur) |
| `winning_positions` | Positions PnL > 0 (numérateur) |
| `losing_positions` | Positions PnL < 0 |
| `win_rate` | **KPI #1** : `(winning_positions / total_positions) * 100`<br/>Ex: 68% = bon trader |

**Formula** :
```python
win_rate = (winning_positions / total_positions) * 100 if total_positions > 0 else NULL
```

### Groupe PnL 💰

| Champ | Rationale |
|-------|-----------|
| `total_pnl_usd` | PnL cumulé USD : `SUM(realized_pnl_usd)` (positions fermées) |
| `total_pnl_percent` | PnL moyen % : `AVG(realized_pnl_percent)` |
| `average_win_usd` | Gain moyen : `SUM(pnl WHERE > 0) / winning_positions` |
| `average_loss_usd` | Perte moyenne : `SUM(pnl WHERE < 0) / losing_positions` |
| `profit_ratio` | **Risk/Reward** : `average_win_usd / ABS(average_loss_usd)`<br/>Ex: 2.5 = gains 2.5x plus gros que pertes |

**Pourquoi profit_ratio critique ?**
→ 55% win rate + profit_ratio 3.0 > 70% win rate + profit_ratio 1.2

### Groupe Signals 📡

| Champ | Rationale |
|-------|-----------|
| `signal_count_all` | Total signaux reçus du wallet (lifetime) |
| `signal_count_30d` | Fenêtre 30j - Détecte wallets actifs |
| `signal_count_7d` | Fenêtre 7j - Détecte refroidissement |
| `signal_count_24h` | Fenêtre 24h - Détecte hyperactivité (pump farming) |

**Pourquoi fenêtres glissantes ?**
→ Wallet qui fait 200 trades/jour = suspect (wash trading). Wallet qui fait 3 trades/semaine = crédible.

**Recalcul quotidien** :
```sql
-- Batch job à 00:00 UTC
UPDATE performance
SET signal_count_30d = (
    SELECT COUNT(*)
    FROM signals
    WHERE wallet_address = (SELECT address FROM wallets WHERE id = performance.wallet_id)
      AND received_at > NOW() - INTERVAL '30 days'
);
```

### Groupe Positions Time ⏱️

| Champ | Rationale |
|-------|-----------|
| `positions_30d` | Positions PRISES (nous) sur signaux du wallet - 30j |
| `positions_7d` | Positions PRISES (nous) - 7j |
| `positions_24h` | Positions PRISES (nous) - 24h |

**Différence signals vs positions** :
- **Signals** = Swaps détectés du wallet (on observe)
- **Positions** = Swaps qu'on a **copiés** (on trade)

**Copy rate** :
```python
copy_rate = (positions_30d / signal_count_30d) * 100
# Si < 20% → Wallet fait beaucoup de mouvements qu'on ne copie pas (sécurité filtre bien)
```

### Groupe Best/Worst 🏆💀

| Champ | Rationale |
|-------|-----------|
| `best_trade_pnl_usd` | Meilleur trade USD (lucky punch ?) |
| `best_trade_pnl_percent` | Meilleur trade % (multiples 10x, 50x) |
| `worst_trade_pnl_usd` | Pire trade USD (risk management ?) |
| `worst_trade_pnl_percent` | Pire trade % (stop loss efficace ?) |

**Analytics** :
```python
if best_trade_pnl_usd > total_pnl_usd * 5:
    # 1 lucky punch >> tous les autres trades
    return "Non reproductible - Outlier dépendant"
```

### Groupe Streaks 🔥❄️

| Champ | Rationale |
|-------|-----------|
| `current_win_streak` | Série victoires en cours (incrémenté à chaque win) |
| `current_loss_streak` | Série pertes en cours (incrémenté à chaque loss) |
| `max_win_streak` | Record série victoires (max historique) |
| `max_loss_streak` | Record série pertes (max historique) |

**Circuit breaker trigger** :
```python
if current_loss_streak >= config.consecutive_max_loss_trigger:
    activate_circuit_breaker(reason='consecutive_losses')
```

**Psychologie trading** :
- `current_loss_streak = 5` → Pause wallet ? (variance temporaire)
- `max_loss_streak = 15` → Instabilité structurelle

---

## Relations avec autres tables

```
performance (1)
    ↓ (1-to-1)
    ↓
wallets (1) ← wallet_id FK UNIQUE
```

**1-to-1 relationship** : 1 wallet = 1 row performance

---

## Exemples SQL

### Top wallets par win rate
```sql
SELECT
    w.label,
    p.win_rate,
    p.total_pnl_usd,
    p.profit_ratio
FROM performance p
JOIN wallets w ON p.wallet_id = w.id
WHERE p.total_positions >= 20  -- Min 20 trades pour stat valide
ORDER BY p.win_rate DESC
LIMIT 10;
```

### Wallets en loss streak (red flag)
```sql
SELECT
    w.label,
    p.current_loss_streak,
    p.max_loss_streak
FROM performance p
JOIN wallets w ON p.wallet_id = w.id
WHERE p.current_loss_streak >= 5
ORDER BY p.current_loss_streak DESC;
```

### Copy rate analysis
```sql
SELECT
    w.label,
    p.signal_count_30d AS signals,
    p.positions_30d AS positions,
    ROUND((p.positions_30d::NUMERIC / NULLIF(p.signal_count_30d, 0)) * 100, 2) AS copy_rate_percent
FROM performance p
JOIN wallets w ON p.wallet_id = w.id
WHERE p.signal_count_30d > 0
ORDER BY copy_rate_percent DESC;
```

---

## Edge cases & FAQ

### Q: Fenêtres glissantes (*_30d, *_7d) comment recalculées ?
**R**: Batch job quotidien à 00:00 UTC rescanne positions/signaux avec filtres temporels.

### Q: Données temps réel ou J-1 ?
**R**: J-1 (last_calculated_at = 00:00 UTC). Trade-off : Fraîcheur vs performance.

### Q: Que se passe-t-il si wallet désactivé ?
**R**: Métriques conservées (historique), mais plus de refresh (is_active = false).

---

## Pour les agents

**Stories concernées** :
- **Story 6.1** : Performance Metrics Batch Job (calcul quotidien)
- **Story 6.2** : Dashboard UI (affichage métriques)

**Tests critiques** :
- Win rate calculation accuracy
- Fenêtres glissantes (30d/7d/24h) correctes
- Profit ratio formula
- Batch job idempotency
