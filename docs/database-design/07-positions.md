# Table: positions - Design Guide

## Pattern architectural
**Pattern**: **Aggregate Root** (PnL tracking central avec realized/unrealized séparation)
**Objectif**: Positions trading ouvertes/fermées avec tracking PnL et exit strategy snapshot

---

## Rationale - Aggregate Root Pattern

**Pourquoi aggregate root ?**
Position = **entité centrale** qui agrège :
- Entry data (prix, montant, timestamp)
- Current state (prix actuel, PnL unrealized)
- Realized PnL (exits partiels déjà faits)
- Exit strategy (snapshot immutable)

**Immutability principe** :
```python
# ❌ MAUVAIS : Modifier stratégie d'une position ouverte
position.exit_strategy_id = new_strategy  # Affecte risk management !

# ✅ BON : Snapshot à création, override si besoin
position = create_position(
    exit_strategy_id=default_strategy,
    exit_strategy_override={'stop_loss_percent': 25.0}  # Override immutable
)
```

---

## Rationale par groupe de champs

### Groupe Entry 🚪

| Champ | Rationale |
|-------|-----------|
| `entry_price` | Prix entrée (ex: $1.00) |
| `entry_amount` | Montant initial acheté (ex: 100 tokens) |
| `entry_value_usd` | Valeur USD entrée (ex: $100) |
| `entry_timestamp` | Date entrée |
| `entry_tx_signature` | Signature tx entrée (live mode)<br/>NULL en simulation |

**Immutable** : Entry data jamais modifié (snapshot permanent).

### Groupe Current 📊

| Champ | Rationale |
|-------|-----------|
| `current_amount` | Montant restant (décrémenté sur exits)<br/>**Formula** : `entry_amount - SUM(exit_amounts)` |
| `current_price` | Prix actuel (polled périodiquement)<br/>**Staleness** : Si > 5 min, re-poll |
| `current_value_usd` | Valeur USD actuelle : `current_amount * current_price` |
| `current_pnl_usd` | **PnL total** : `realized_pnl_usd + unrealized_pnl_usd` |
| `current_pnl_percent` | **PnL total %** : `(current_pnl_usd / entry_value_usd) * 100` |
| `peak_price` | Prix peak atteint (pour trailing stop)<br/>**Auto-update** : `IF current_price > peak_price THEN peak_price = current_price` |
| `peak_value_usd` | Valeur peak : `entry_amount * peak_price` |
| `last_price_update_at` | Timestamp dernière MàJ prix<br/>**Health check** : Si > 5 min, prix stale |

**Auto-calculated triggers** :
```sql
CREATE TRIGGER positions_update_current_pnl
AFTER UPDATE ON positions
FOR EACH ROW
WHEN (NEW.current_price IS DISTINCT FROM OLD.current_price)
EXECUTE FUNCTION recalculate_pnl();
```

### Groupe PnL (Realized vs Unrealized) 💰

**Concept critique** : Séparation PnL réalisé (exits déjà faits) vs non réalisé (position restante).

| Champ | Rationale |
|-------|-----------|
| `unrealized_pnl_usd` | PnL non réalisé : `(current_price - entry_price) * current_amount` |
| `unrealized_pnl_percent` | PnL non réalisé % : `((current_price - entry_price) / entry_price) * 100` |
| `realized_pnl_usd` | PnL réalisé (somme des exits partiels)<br/>**Accumulé** : `SUM((exit_price - entry_price) * exit_amount)` |
| `realized_pnl_percent` | PnL réalisé % : `(realized_pnl_usd / entry_value_usd) * 100` |

**Exemple scaling out** :
```python
# Entry
entry_price = $1.00
entry_amount = 100 tokens
entry_value = $100

# Price goes to $2.00 (2x)
current_price = $2.00
current_amount = 100  # Pas encore vendu
unrealized_pnl_usd = ($2.00 - $1.00) * 100 = $100
realized_pnl_usd = $0

# Scaling exit level 1 (50% sold at $2.00)
exit_amount = 50 tokens
exit_price = $2.00
realized_pnl_usd = ($2.00 - $1.00) * 50 = $50
current_amount = 50
unrealized_pnl_usd = ($2.00 - $1.00) * 50 = $50

# Total PnL = $50 (realized) + $50 (unrealized) = $100
```

### Groupe Exit 🚪

| Champ | Rationale |
|-------|-----------|
| `exit_price` | Prix moyen pondéré de TOUS les exits<br/>**Formula** : `SUM(exit_price * exit_amount) / SUM(exit_amount)` |
| `exit_amount` | Montant total vendu (somme exits partiels) |
| `exit_value_usd` | Valeur totale exits : `exit_price * exit_amount` |
| `exit_timestamp` | Date DERNIER exit (fermeture complète) |
| `exit_tx_signature` | Signature DERNIER exit |
| `exit_reason` | Raison DERNIER exit ('stop_loss', 'trailing_stop', 'scaling_out', 'mirror_exit', 'manual') |

**Partial exits** :
- Multiple exits partiels (scaling) → `exit_price` = weighted average
- Dernier exit (100% vendu) → `status = 'closed'`, `closed_at = exit_timestamp`

### Groupe Strategy 🎯

| Champ | Rationale |
|-------|-----------|
| `exit_strategy_id` | FK vers exit_strategies<br/>**Obligatoire** : Toute position doit avoir une stratégie |
| `exit_strategy_override` | Overrides JSONB (ex: `{"stop_loss_percent": 25.0}`)<br/>**Immutable** : Snapshot à création |

**Merge logic** :
```python
strategy = db.get(exit_strategies, id=position.exit_strategy_id)
override = position.exit_strategy_override or {}

final_config = {**strategy, **override}
# stop_loss_percent = 25.0 (overridden)
# scaling_level_1_multiplier = 2.0 (from template)
```

**Pourquoi snapshot immutable ?**
→ Si admin change stratégie "Default", positions existantes pas affectées (risk management stable).

---

## Relations avec autres tables

```
positions (N)
    ↓
wallet_id FK → wallets (1) ← Wallet source copié
token_id FK → tokens (1) ← Token tradé
signal_id FK → signals (1) ← Signal déclencheur (si copy trading)
exit_strategy_id FK → exit_strategies (1) ← Stratégie snapshot

positions (1)
    ↓ (1-to-N)
    ↓
orders (N) ← Tous les ordres (entry + exits partiels)
```

---

## Exemples SQL

### Positions ouvertes (dashboard)
```sql
SELECT
    w.label AS wallet,
    t.symbol AS token,
    p.entry_price,
    p.current_price,
    p.current_pnl_percent,
    p.unrealized_pnl_usd,
    p.realized_pnl_usd
FROM positions p
JOIN wallets w ON p.wallet_id = w.id
JOIN tokens t ON p.token_id = t.id
WHERE p.status = 'open'
ORDER BY p.current_pnl_percent DESC;
```

### Positions fermées (performance analysis)
```sql
SELECT
    t.symbol,
    AVG(p.realized_pnl_percent) AS avg_pnl_percent,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN p.realized_pnl_usd > 0 THEN 1 ELSE 0 END) AS wins
FROM positions p
JOIN tokens t ON p.token_id = t.id
WHERE p.status = 'closed'
GROUP BY t.symbol
ORDER BY avg_pnl_percent DESC;
```

### Positions trailing stop actives
```sql
SELECT
    p.*,
    s.trailing_stop_percent,
    s.trailing_activation_threshold_percent
FROM positions p
JOIN exit_strategies s ON p.exit_strategy_id = s.id
WHERE p.status = 'open'
  AND s.trailing_stop_enabled = true
  AND p.current_pnl_percent >= s.trailing_activation_threshold_percent;
```

---

## Edge cases & FAQ

### Q: Pourquoi exit_strategy_override en JSONB ?
**R**: Flexibilité - Override 1 seul champ sans dupliquer toute la stratégie.

### Q: Que se passe-t-il si current_amount = 0 mais status != 'closed' ?
**R**: Bug ! Trigger doit auto-close :
```sql
CREATE TRIGGER positions_auto_close
AFTER UPDATE ON positions
FOR EACH ROW
WHEN (NEW.current_amount = 0 AND NEW.status = 'open')
EXECUTE FUNCTION close_position();
```

### Q: current_pnl_usd vs realized_pnl_usd + unrealized_pnl_usd ?
**R**: `current_pnl_usd = realized_pnl_usd + unrealized_pnl_usd` (auto-calculated).

---

## Pour les agents

**Stories concernées** :
- **Story 4.4** : Position Creation (snapshot strategy)
- **Story 4.5** : Position Tracking (price updates, PnL calc)
- **Story 4.6** : Position Exit (scaling, stop loss, trailing)

**Tests critiques** :
- Realized vs unrealized PnL separation
- Exit strategy snapshot immutability
- Peak price tracking (trailing stop)
- Auto-close when current_amount = 0
