"""Apply discovery migrations to the database."""

import asyncio
import asyncpg


async def run_migrations() -> None:
    """Run discovery-related migrations."""
    conn = await asyncpg.connect(
        "postgresql://postgres:postgres@localhost:6543/postgres"
    )

    try:
        # Migration 019: discovery_runs
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS discovery_runs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                status VARCHAR(20) NOT NULL DEFAULT 'running',
                trigger_type VARCHAR(20) NOT NULL,
                triggered_by VARCHAR(100),
                min_price_change_pct DECIMAL(5,2),
                min_volume_usd DECIMAL(15,2),
                max_token_age_hours INTEGER,
                early_window_minutes INTEGER,
                min_profit_pct DECIMAL(5,2),
                max_tokens INTEGER,
                tokens_analyzed INTEGER DEFAULT 0,
                new_wallets INTEGER DEFAULT 0,
                updated_wallets INTEGER DEFAULT 0,
                profiled_wallets INTEGER DEFAULT 0,
                duration_seconds DECIMAL(10,2),
                errors JSONB DEFAULT '[]',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("Created discovery_runs table")

        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_discovery_runs_started "
            "ON discovery_runs(started_at DESC)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_discovery_runs_status "
            "ON discovery_runs(status)"
        )

        # Migration 019: discovery_run_wallets
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS discovery_run_wallets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                run_id UUID NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
                wallet_address VARCHAR(44) NOT NULL,
                source_token VARCHAR(44) NOT NULL,
                is_new BOOLEAN DEFAULT TRUE,
                initial_score DECIMAL(5,4),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("Created discovery_run_wallets table")

        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_drw_run ON discovery_run_wallets(run_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_drw_wallet "
            "ON discovery_run_wallets(wallet_address)"
        )

        # Migration 020: discovery_config
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS discovery_config (
                id INTEGER PRIMARY KEY DEFAULT 1,
                enabled BOOLEAN DEFAULT TRUE,
                schedule_hours INTEGER DEFAULT 6,
                min_price_change_pct DECIMAL(5,2) DEFAULT 100.0,
                min_volume_usd DECIMAL(15,2) DEFAULT 50000.0,
                max_token_age_hours INTEGER DEFAULT 72,
                early_window_minutes INTEGER DEFAULT 30,
                min_profit_pct DECIMAL(5,2) DEFAULT 50.0,
                max_tokens INTEGER DEFAULT 20,
                profile_immediately BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by VARCHAR(100),
                CONSTRAINT single_row CHECK (id = 1)
            )
        """)
        print("Created discovery_config table")

        await conn.execute(
            "INSERT INTO discovery_config (id) VALUES (1) ON CONFLICT DO NOTHING"
        )
        print("Inserted default config")

        # Verify
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'discovery%'"
        )
        print(f"Discovery tables: {[t['table_name'] for t in tables]}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
