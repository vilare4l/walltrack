# Table: exit_strategies - Design Guide

## Pattern architectural
**Pattern**: **Catalog Pattern** (DRY - Don't Repeat Yourself)
**Objectif**: Templates réutilisables de stratégies de sortie (stop loss, trailing stop, scaling out, mirror exit)

---

## Vue d'ensemble - Schéma complet

| Groupe | Champ | Type | Contraintes | Default | Description |
|--------|-------|------|-------------|---------|-------------|
| **PK** | id | UUID | PRIMARY KEY | gen_random_uuid() | Identifiant unique |
| **Identity** | name | TEXT | NOT NULL, UNIQUE | | Nom de la stratégie |
| **Identity** | description | TEXT | | NULL | Description |
| **Stop Loss** | stop_loss_percent | NUMERIC(5,2) | NOT NULL, CHECK > 0 AND <= 100 | 20.00 | % stop loss |
| **Trailing Stop** | trailing_stop_enabled | BOOLEAN | NOT NULL | false | Trailing stop activé |
| **Trailing Stop** | trailing_stop_percent | NUMERIC(5,2) | CHECK > 0 AND <= 100 | 15.00 | % trailing stop |
| **Trailing Stop** | trailing_activation_threshold_percent | NUMERIC(5,2) | CHECK >= 0 | 20.00 | Seuil activation trailing |
| **Scaling** | scaling_enabled | BOOLEAN | NOT NULL | true | Scaling out activé |
| **Scaling** | scaling_level_1_percent | NUMERIC(5,2) | | 50.00 | % vendu niveau 1 |
| **Scaling** | scaling_level_1_multiplier | NUMERIC(4,2) | | 2.00 | Multiplicateur niveau 1 |
| **Scaling** | scaling_level_2_percent | NUMERIC(5,2) | | 25.00 | % vendu niveau 2 |
| **Scaling** | scaling_level_2_multiplier | NUMERIC(4,2) | | 3.00 | Multiplicateur niveau 2 |
| **Scaling** | scaling_level_3_percent | NUMERIC(5,2) | | 25.00 | % vendu niveau 3 |
| **Scaling** | scaling_level_3_multiplier | NUMERIC(4,2) | | NULL | Multiplicateur niveau 3 (NULL = ride forever) |
| **Mirror** | mirror_exit_enabled | BOOLEAN | NOT NULL | true | Mirror exit activé |
| **Status** | is_default | BOOLEAN | NOT NULL | false | Stratégie par défaut |
| **Status** | is_active | BOOLEAN | NOT NULL | true | Stratégie active |
| **Metadata** | created_at | TIMESTAMPTZ | | NOW() | Date création |
| **Metadata** | updated_at | TIMESTAMPTZ | | NOW() | Date dernière MàJ |
| **Metadata** | created_by | TEXT | | NULL | Créateur de la stratégie |
| **Metadata** | notes | TEXT | | NULL | Notes |

---

## Rationale - Catalog Pattern

**Pourquoi un catalog ?**
Éviter duplication : 100 wallets avec même stratégie "20% stop loss + scaling 2x/3x" → 1 seul template, 100 FK.

**Alternative naïve** :
```sql
-- ❌ MAUVAIS : Duplication dans chaque wallet
CREATE TABLE wallets (
    stop_loss_percent NUMERIC,  -- Répété 100 fois
    scaling_level_1_multiplier NUMERIC,  -- Répété 100 fois
    ...
);
```

**Solution catalog** :
```sql
-- ✅ BON : 1 template, N références
exit_strategies (3 templates: Default, Conservative, Aggressive)
    ↓
wallets (100 wallets) → exit_strategy_id FK
```

---

## Rationale par groupe de champs

### Groupe Stop Loss 🛑

| Champ | Rationale |
|-------|-----------|
| `stop_loss_percent` | % loss maximum accepté (ex: 20% = -20%)<br/>**Obligatoire** (NOT NULL) - Toute position doit avoir un stop loss |

**Workflow** :
```python
entry_price = 1.00
stop_loss_percent = 20.0

stop_loss_price = entry_price * (1 - stop_loss_percent / 100)  # $0.80
if current_price <= stop_loss_price:
    trigger_exit(reason='stop_loss')
```

---

### Groupe Trailing Stop 📈

| Champ | Rationale |
|-------|-----------|
| `trailing_stop_enabled` | Activer trailing stop ? (true/false) |
| `trailing_stop_percent` | % de retrait depuis peak (ex: 15%)<br/>Si prix baisse de 15% depuis peak → Exit |
| `trailing_activation_threshold_percent` | Seuil d'activation (ex: 20%)<br/>Trailing stop démarre seulement si PnL >= +20% |

**Workflow** :
```python
entry_price = 1.00
trailing_activation = 20.0  # Démarre à +20%
trailing_percent = 15.0  # Exit si baisse de 15% depuis peak

peak_price = 1.50  # PnL = +50% (> activation 20%)
trailing_stop_price = peak_price * (1 - trailing_percent / 100)  # $1.275

if current_price <= trailing_stop_price:
    trigger_exit(reason='trailing_stop')
```

**Pourquoi activation threshold ?**
Évite de trigger trailing stop trop tôt (ex: prix monte à +5% puis baisse de 15% → Loss de -10% alors qu'on voulait protéger profits).

---

### Groupe Scaling Out 📊

**Concept** : Vente progressive aux multiples 2x, 3x, 5x pour sécuriser profits.

| Champ | Rationale |
|-------|-----------|
| `scaling_enabled` | Activer scaling ? |
| `scaling_level_1_percent` | % vendu au niveau 1 (ex: 50%) |
| `scaling_level_1_multiplier` | Multiplicateur niveau 1 (ex: 2.0 = 2x = +100%) |
| `scaling_level_2_percent` | % vendu au niveau 2 (ex: 25%) |
| `scaling_level_2_multiplier` | Multiplicateur niveau 2 (ex: 3.0 = 3x = +200%) |
| `scaling_level_3_percent` | % vendu au niveau 3 (ex: 25%) |
| `scaling_level_3_multiplier` | Multiplicateur niveau 3 (ex: NULL = "ride forever") |

**Contrainte** :
```sql
scaling_level_1_percent + scaling_level_2_percent + scaling_level_3_percent = 100
```

**Exemple scaling** :
```python
entry_amount = 100 tokens
entry_price = $1.00

# Level 1: 2x (+100%)
if current_price >= entry_price * 2.0:
    sell_amount = entry_amount * 0.50  # 50 tokens
    remaining_amount = 50 tokens

# Level 2: 3x (+200%)
if current_price >= entry_price * 3.0:
    sell_amount = entry_amount * 0.25  # 25 tokens
    remaining_amount = 25 tokens

# Level 3: NULL multiplier = ride forever (ou manual exit)
# 25 tokens restants continuent de monter indéfiniment
```

**Pourquoi scaling ?**
- **Sécurise profits** : 50% sold à 2x = breakeven garanti
- **Laisse upside** : 25% reste pour capter moonshot (10x, 50x)

---

### Groupe Mirror Exit 🪞

| Champ | Rationale |
|-------|-----------|
| `mirror_exit_enabled` | Activer mirror exit ? (true/false)<br/>Si wallet source vend → On vend aussi |

**Workflow** :
```python
# Signal Helius reçu
signal = {
    'wallet_address': 'ABC...XYZ',
    'signal_type': 'swap_detected',
    'action': 'sell',  # Wallet source a VENDU
    'token_address': 'TOKEN123'
}

if mirror_exit_enabled:
    # Trouver notre position ouverte sur ce token pour ce wallet
    position = db.query(
        "SELECT * FROM positions WHERE wallet_id = X AND token_id = Y AND status = 'open'"
    )
    if position:
        trigger_exit(reason='mirror_exit')
```

**Rationale** :
"Smart money" vend souvent avant dump → Suivre leur sortie = protection downside.

---

### Groupe Status ✅

| Champ | Rationale |
|-------|-----------|
| `is_default` | Stratégie par défaut ? (1 seule stratégie peut être default)<br/>**UNIQUE constraint** sur `is_default WHERE is_default = true` |
| `is_active` | Stratégie active ? (false = archivée, non sélectionnable dans UI) |

**Workflow default** :
```sql
-- 1 seule stratégie peut être default
SELECT * FROM exit_strategies WHERE is_default = true;
-- → 1 seule row maximum

-- Nouvelle stratégie devient default
UPDATE exit_strategies SET is_default = false;  -- Unset all
UPDATE exit_strategies SET is_default = true WHERE id = 'new-uuid';
```

---

## Strategies par défaut (MVP)

```sql
-- Default: Balanced (20% SL, scaling 2x/3x, mirror)
{
    "name": "Default",
    "stop_loss_percent": 20.00,
    "trailing_stop_enabled": false,
    "scaling_enabled": true,
    "scaling_level_1_percent": 50.00,
    "scaling_level_1_multiplier": 2.00,
    "scaling_level_2_percent": 25.00,
    "scaling_level_2_multiplier": 3.00,
    "scaling_level_3_percent": 25.00,
    "scaling_level_3_multiplier": NULL,  -- Ride forever
    "mirror_exit_enabled": true
}

-- Conservative: Tight SL (15%), early profit (1.5x/2x)
{
    "stop_loss_percent": 15.00,
    "scaling_level_1_multiplier": 1.50,  -- Take profit tôt
    "scaling_level_2_multiplier": 2.00
}

-- Aggressive: Wide SL (30%), trailing, let winners run (3x/5x)
{
    "stop_loss_percent": 30.00,
    "trailing_stop_enabled": true,
    "scaling_level_1_multiplier": 3.00,
    "scaling_level_2_multiplier": 5.00
}
```

---

## Override au niveau position

**IMPORTANT** : Stratégies sont des **templates**. Override se fait au niveau `positions.exit_strategy_override` (JSONB).

**Exemple** :
```sql
-- Position utilise strategy "Default" mais override scaling level 1
INSERT INTO positions (
    exit_strategy_id = 'uuid-default',
    exit_strategy_override = '{"scaling_level_1_multiplier": 5.0}'  -- Override 2x → 5x
)
```

**Merge logic** :
```python
strategy = db.get(exit_strategies, id='uuid-default')
override = position.exit_strategy_override or {}

final_config = {**strategy, **override}
# scaling_level_1_multiplier = 5.0 (overridden)
# stop_loss_percent = 20.00 (from template)
```

---

## Relations avec autres tables

```
exit_strategies (1)
    ↓ (1-to-N)
    ↓
wallets (N) ← Wallet.exit_strategy_id FK
    ↓
    └─ Default strategy assignée

exit_strategies (1)
    ↓ (1-to-N)
    ↓
positions (N) ← Position.exit_strategy_id FK
    ↓
    └─ Strategy snapshot à création position
```

---

## Exemples SQL

### Créer nouvelle stratégie custom
```sql
INSERT INTO exit_strategies (
    name,
    description,
    stop_loss_percent,
    scaling_enabled,
    scaling_level_1_multiplier,
    mirror_exit_enabled
) VALUES (
    'Moonshot Hunter',
    'Wide SL 40%, scaling at 5x/10x, no mirror (hold through dips)',
    40.00,
    true,
    5.00,
    false  -- No mirror exit
);
```

### Changer stratégie par défaut
```sql
-- Unset current default
UPDATE exit_strategies SET is_default = false;

-- Set new default
UPDATE exit_strategies
SET is_default = true
WHERE name = 'Aggressive';
```

### Lister toutes stratégies actives
```sql
SELECT id, name, description, stop_loss_percent
FROM exit_strategies
WHERE is_active = true
ORDER BY is_default DESC, name ASC;
```

---

## Edge cases & FAQ

### Q: Peut-on modifier une stratégie utilisée par des positions ouvertes ?
**R**: Oui, MAIS positions existantes ne sont PAS affectées (snapshot immutable).

**Workflow safe** :
```sql
-- Position créée avec strategy "Default" (stop_loss = 20%)
INSERT INTO positions (exit_strategy_id = 'uuid-default') VALUES (...);
-- → Position snapshot: stop_loss = 20%

-- Admin modifie strategy "Default" → stop_loss = 25%
UPDATE exit_strategies SET stop_loss_percent = 25.00 WHERE id = 'uuid-default';

-- Position existante garde stop_loss = 20% (snapshot)
-- Nouvelles positions utiliseront stop_loss = 25%
```

### Q: Que se passe-t-il si scaling_level_3_multiplier = NULL ?
**R**: "Ride forever" - Les derniers 25% ne sont jamais vendus automatiquement (seulement manual exit ou mirror exit).

### Q: Peut-on désactiver TOUS les exits (pas de stop loss, pas de scaling) ?
**R**: ❌ Non - `stop_loss_percent` est **NOT NULL** (protection obligatoire).

---

## Pour les agents

**Stories concernées** :
- **Story 2.2** : Exit Strategy Catalog CRUD (UI Gradio)
- **Story 4.3** : Position Exit Strategy Override (JSONB merge logic)

**Tests critiques** :
- Unique constraint sur `is_default = true` (1 seule stratégie default)
- Scaling percentages sum = 100%
- Strategy modification n'affecte pas positions existantes (snapshot)
