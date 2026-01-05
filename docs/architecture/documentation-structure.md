# Documentation Structure

This architecture document is complemented by detailed design guides and SQL migrations:

### Database Design Guides (`docs/database-design/`)

Each table has a dedicated design guide explaining the "why" behind every field:

- **[README.md](./database-design/README.md)** - Architectural patterns overview + ADRs (Architecture Decision Records)
- **[01-config.md](./database-design/01-config.md)** - Configuration Singleton pattern
- **[02-exit-strategies.md](./database-design/02-exit-strategies.md)** - Catalog pattern (DRY templates)
- **[03-wallets.md](./database-design/03-wallets.md)** - Registry pattern (watchlist)
- **[04-tokens.md](./database-design/04-tokens.md)** - Read-Through Cache pattern
- **[05-signals.md](./database-design/05-signals.md)** - Event Sourcing pattern (immutable)
- **[06-orders.md](./database-design/06-orders.md)** - Command Log pattern (retry mechanism)
- **[07-positions.md](./database-design/07-positions.md)** - Aggregate Root pattern (PnL tracking)
- **[08-performance.md](./database-design/08-performance.md)** - Materialized View pattern (batch refresh)
- **[09-circuit-breaker-events.md](./database-design/09-circuit-breaker-events.md)** - Event Sourcing pattern (audit trail)

**Each design guide contains:**
- Pattern rationale
- Field-by-field "why" explanations
- SQL examples
- Edge cases & FAQ
- Related stories for implementation

### SQL Migrations (`src/walltrack/data/supabase/migrations/`)

Executable SQL scripts with inline documentation (COMMENT ON):

- `000_helper_functions.sql` - Schema + utility functions
- `001_config_table.sql` - Config singleton
- `002_exit_strategies_table.sql` - Exit strategies catalog + default templates
- `003_wallets_table.sql` - Wallets registry
- `004_tokens_table.sql` - Tokens cache
- `005_signals_table.sql` - Signals event log
- `006_orders_table.sql` - Orders transaction log
- `007_positions_table.sql` - Positions tracking
- `008_performance_table.sql` - Performance metrics
- `009_circuit_breaker_events_table.sql` - Circuit breaker audit trail

**Agent workflow:** For any table-related task, read the design guide first, then consult the migration SQL for implementation details.
