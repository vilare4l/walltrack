# Table: tokens - Design Guide

## Pattern architectural
**Pattern**: **Read-Through Cache** (avec TTL invalidation)
**Objectif**: Cache analyse sécurité tokens (RugCheck, Helius, DexScreener) avec refresh automatique

---

## Rationale - Read-Through Cache Pattern

**Pourquoi un cache ?**
- Analyse token coûteuse (3 API calls : RugCheck + Helius + DexScreener)
- Résultats stables court terme (safety score change peu sur 1h)
- Éviter rate limiting API

**Workflow** :
```python
def get_token_safety(token_address):
    cached = db.query("SELECT * FROM tokens WHERE address = ? AND last_analyzed_at > NOW() - INTERVAL '1 hour'")

    if cached:
        return cached  # Hit cache

    # Miss cache → Fetch from APIs
    safety_data = fetch_token_analysis(token_address)
    db.upsert(tokens, safety_data)  # Update cache
    return safety_data
```

---

## Rationale par groupe de champs

### Groupe Safety (Score global) 🔒

| Champ | Rationale |
|-------|-----------|
| `safety_score` | Score 0-1 agrégé (ex: 0.75 = 75%)<br/>Formula: `AVG(liquidity_check + holder_check + contract_check + age_check)` |
| `liquidity_usd` | Liquidité USD (DexScreener)<br/>Filter: `> $50k` pour éviter slippage |
| `holder_distribution_top_10_percent` | % détenu top 10 holders (RugCheck)<br/>Red flag si > 80% (centralisé) |
| `contract_analysis_score` | Score analyse contrat 0-1 (RugCheck)<br/>Détecte honeypots, mint authority, etc. |
| `age_hours` | Age token en heures<br/>Filter: Tokens < 24h souvent pumps |

### Groupe Safety Checks (Booleans) ✅

Pré-calculs pour accélérer filtering :
- `liquidity_check_passed` = `liquidity_usd >= config.min_liquidity_usd`
- `holder_distribution_check_passed` = `holder_distribution_top_10_percent <= config.max_top_10_holder_percent`
- etc.

**Pourquoi booleans en plus des valeurs numériques ?**
→ Index partiel ultra-rapide : `WHERE liquidity_check_passed = true AND holder_distribution_check_passed = true`

### Groupe Analysis Metadata 📊

| Champ | Rationale |
|-------|-----------|
| `last_analyzed_at` | Timestamp dernière analyse<br/>**TTL**: Si > 1h → Re-fetch |
| `analysis_source` | Source primaire ('rugcheck', 'helius', 'dexscreener')<br/>Audit trail + fallback logic |
| `analysis_error` | Dernière erreur (si fetch failed)<br/>Ex: "RugCheck API timeout", "Token not found" |

**TTL Invalidation** :
```sql
-- Tokens stale (> 1h)
SELECT * FROM tokens
WHERE last_analyzed_at < NOW() - INTERVAL '1 hour'
  AND is_blacklisted = false;
```

### Groupe Blacklist 🚫

| Champ | Rationale |
|-------|-----------|
| `is_blacklisted` | Token définitivement banni (rug confirmé)<br/>**Immutable** : Une fois blacklisted, jamais retradé |
| `blacklist_reason` | Raison ban (ex: "Rugpull 2025-01-05", "Honeypot contract") |

---

## Multi-source fallback

**Ordre priorité** : RugCheck → Helius → DexScreener

```python
try:
    data = rugcheck_client.analyze(token_address)
    analysis_source = 'rugcheck'
except:
    try:
        data = helius_client.get_token_info(token_address)
        analysis_source = 'helius'
    except:
        data = dexscreener_client.search(token_address)
        analysis_source = 'dexscreener'

db.insert(tokens, {..., 'analysis_source': analysis_source})
```

---

## Relations avec autres tables

```
tokens (1)
    ↓ (1-to-N)
    ↓
signals (N) ← Signaux détectés pour ce token
positions (N) ← Positions tradées sur ce token
orders (N) ← Ordres pour ce token
```

---

## Exemples SQL

### Check si token safe
```sql
SELECT
    address,
    safety_score,
    liquidity_usd,
    is_blacklisted
FROM tokens
WHERE address = 'TOKEN_ADDRESS'
  AND last_analyzed_at > NOW() - INTERVAL '1 hour';
```

### Tokens à re-analyser (stale)
```sql
SELECT address, last_analyzed_at
FROM tokens
WHERE last_analyzed_at < NOW() - INTERVAL '1 hour'
  AND is_blacklisted = false
ORDER BY last_analyzed_at ASC
LIMIT 100;
```

### Blacklist token (rugpull confirmé)
```sql
UPDATE tokens
SET is_blacklisted = true,
    blacklist_reason = 'Rugpull confirmed 2025-01-05 - LP drained'
WHERE address = 'RUG_TOKEN';
```

---

## Edge cases & FAQ

### Q: Que se passe-t-il si token pas dans cache ?
**R**: Read-through fetch automatique → APIs externes → Insert cache.

### Q: Token blacklisted peut-il être "unblacklisted" ?
**R**: Non (immutable). Si erreur, créer nouvelle entry avec nouvelle address.

### Q: Pourquoi TTL 1h et pas temps réel ?
**R**: Trade-off : Safety score change rarement sur 1h, API rate limits coûteux.

---

## Pour les agents

**Stories concernées** :
- **Story 4.1** : Token Safety Analysis (cache implementation)
- **Story 4.2** : Token Blacklist Management

**Tests critiques** :
- Read-through logic (cache hit/miss)
- TTL invalidation après 1h
- Multi-source fallback (RugCheck → Helius → DexScreener)
- Blacklist immutability
