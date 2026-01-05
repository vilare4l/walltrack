# WallTrack - Database Design Guides

Ce dossier contient les **design guides** détaillés pour chaque table de la base de données WallTrack.

Chaque guide explique :
- Le **pattern architectural** utilisé
- La **rationale** de chaque groupe de champs
- Les **relations** avec les autres tables
- Des **exemples SQL** concrets
- Les **edge cases** et FAQ
- Les **décisions architecturales** clés

---

## Patterns architecturaux utilisés

| Pattern | Tables | Description |
|---------|--------|-------------|
| **Event Sourcing** | signals, circuit_breaker_events | Audit trail complet de tous les événements (immutable) |
| **Materialized View** | performance | Métriques agrégées précalculées (batch refresh) |
| **Command Log** | orders | Journal des transactions avec retry mechanism |
| **Catalog Pattern** | exit_strategies | Templates réutilisables (DRY principle) |
| **Registry Pattern** | wallets | Watchlist configuration avec modes simulation/live |
| **Read-Through Cache** | tokens | Cache sécurité avec TTL invalidation |
| **Aggregate Root** | positions | PnL tracking central avec séparation realized/unrealized |
| **Configuration Singleton** | config | Configuration globale centralisée (1 seule row) |

---

## Tables par domaine

| # | Table | Pattern | Objectif | Guide |
|---|-------|---------|----------|-------|
| 1 | config | Configuration Singleton | Config globale + Helius webhook | [01-config.md](./01-config.md) |
| 2 | exit_strategies | Catalog | Templates stratégies de sortie réutilisables | [02-exit-strategies.md](./02-exit-strategies.md) |
| 3 | wallets | Registry | Watchlist wallets avec discovery + performance baseline | [03-wallets.md](./03-wallets.md) |
| 4 | tokens | Read-Through Cache | Cache analyse sécurité tokens (RugCheck, Helius, DexScreener) | [04-tokens.md](./04-tokens.md) |
| 5 | signals | Event Sourcing | Audit trail webhooks Helius (tous les swaps détectés) | [05-signals.md](./05-signals.md) |
| 6 | orders | Command Log | Journal transactions avec retry + slippage tracking | [06-orders.md](./06-orders.md) |
| 7 | positions | Aggregate Root | Tracking positions avec PnL realized/unrealized | [07-positions.md](./07-positions.md) |
| 8 | performance | Materialized View | Métriques agrégées par wallet (dashboard) | [08-performance.md](./08-performance.md) |
| 9 | circuit_breaker_events | Event Sourcing | Audit trail activations/désactivations circuit breaker | [09-circuit-breaker-events.md](./09-circuit-breaker-events.md) |

---

## Relations clés

```
config (1)
   ↓ helius_webhook_id (global)

exit_strategies (N) ←──┐
   ↓                    │
   ↓ (catalog)          │ FK exit_strategy_id
   ↓                    │
wallets (N) ────→ positions (N) ────→ orders (N)
   ↓                    ↓                 ↓
   ↓ address            ↓ token_id        ↓ tx_signature
   ↓                    ↓                 ↓
signals (N)         tokens (N)       (blockchain)
   ↑
   └─ Helius webhook global (tous les wallets actifs)

performance (N) ← 1-to-1 avec wallets (métriques agrégées)

circuit_breaker_events (N) ← Audit trail global (pas de FK)
```

---

## Décisions architecturales majeures

### ADR-001: Helius Global Webhook
**Contexte**: Helius ne permet pas 1 webhook par wallet
**Décision**: Un seul webhook global pour tous les wallets
**Conséquence**: Batch sync toutes les 5min pour mettre à jour la liste d'adresses surveillées
**Détails**: Voir [03-wallets.md](./03-wallets.md) section "Helius Sync"

### ADR-002: Exit Strategy Override au niveau Position
**Contexte**: Besoin de flexibilité par position, pas par wallet
**Décision**: `exit_strategy_override` (JSONB) dans `positions`, pas dans `wallets`
**Conséquence**: Immutabilité (snapshot à création position) + override granulaire
**Détails**: Voir [07-positions.md](./07-positions.md) section "Strategy"

### ADR-003: Performance Materialized View
**Contexte**: Calculs temps réel trop coûteux pour dashboard
**Décision**: Précalcul quotidien des métriques agrégées (fenêtres glissantes)
**Conséquence**: Dashboard ultra-rapide, mais données refresh 1x/jour
**Détails**: Voir [08-performance.md](./08-performance.md)

### ADR-004: Circuit Breaker Non-Closing
**Contexte**: Protéger contre pertes excessives sans panic selling
**Décision**: Circuit breaker bloque NOUVELLES positions, continue exit strategies sur positions ouvertes
**Conséquence**: Risk management sans force liquidation
**Détails**: Voir [09-circuit-breaker-events.md](./09-circuit-breaker-events.md)

---

## Migrations SQL

Les migrations SQL correspondantes sont dans :
```
src/walltrack/data/supabase/migrations/
├── 001_config_table.sql
├── 002_exit_strategies_table.sql
├── 003_wallets_table.sql
├── 004_tokens_table.sql
├── 005_signals_table.sql
├── 006_orders_table.sql
├── 007_positions_table.sql
├── 008_performance_table.sql
└── 009_circuit_breaker_events_table.sql
```

Chaque migration contient :
- `COMMENT ON TABLE` pour le pattern et l'objectif
- `COMMENT ON COLUMN` pour la rationale de chaque champ
- Rollback SQL en commentaire

---

## Pour les agents

**Workflow recommandé** :
1. Lire le design guide de la table concernée (ex: `03-wallets.md`)
2. Consulter la migration SQL correspondante (ex: `003_wallets_table.sql`)
3. Implémenter avec le contexte complet (pattern + rationale + edge cases)

**Exemples** :
- Story 3.2 "Wallet Discovery" → Lire [03-wallets.md](./03-wallets.md) section "Groupe Discovery"
- Story 4.3 "Exit Strategy Override" → Lire [07-positions.md](./07-positions.md) section "Strategy"
- Debug "Circuit breaker activé alors que win_rate OK" → Lire [09-circuit-breaker-events.md](./09-circuit-breaker-events.md) section "Edge cases"
