-- ============================================
-- Exit Strategies Lifecycle Migration
-- Adds versioning and status to existing table
-- ============================================

-- Add lifecycle columns
ALTER TABLE exit_strategies
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

-- Add rules column (unified structure)
ALTER TABLE exit_strategies
    ADD COLUMN IF NOT EXISTS rules JSONB DEFAULT '[]';

-- Add stagnation columns (extracted from time_rules)
ALTER TABLE exit_strategies
    ADD COLUMN IF NOT EXISTS max_hold_hours INTEGER DEFAULT 24,
    ADD COLUMN IF NOT EXISTS stagnation_hours INTEGER DEFAULT 6,
    ADD COLUMN IF NOT EXISTS stagnation_threshold_pct DECIMAL(5,2) DEFAULT 2.0;

-- Migrate existing data: convert is_default to status
UPDATE exit_strategies
SET status = CASE WHEN is_default = true THEN 'active' ELSE 'draft' END,
    activated_at = CASE WHEN is_default = true THEN NOW() ELSE NULL END
WHERE status IS NULL OR status = 'draft';

-- Migrate time_rules into separate columns
UPDATE exit_strategies
SET max_hold_hours = COALESCE((time_rules->>'max_hold_hours')::INTEGER, 24),
    stagnation_hours = COALESCE((time_rules->>'stagnation_hours')::INTEGER, 6),
    stagnation_threshold_pct = COALESCE((time_rules->>'stagnation_threshold_pct')::DECIMAL, 2.0)
WHERE max_hold_hours IS NULL OR max_hold_hours = 24;

-- Migrate existing fields to unified rules format (only if rules is empty)
UPDATE exit_strategies
SET rules = (
    SELECT COALESCE(jsonb_agg(rule), '[]'::jsonb) FROM (
        -- Take profit levels
        SELECT jsonb_build_object(
            'rule_type', 'take_profit',
            'trigger_pct', (tp->>'multiplier')::DECIMAL * 100,
            'exit_pct', (tp->>'sell_percentage')::DECIMAL,
            'priority', tp_idx,
            'enabled', true,
            'params', '{}'::JSONB
        ) as rule
        FROM jsonb_array_elements(take_profit_levels) WITH ORDINALITY AS t(tp, tp_idx)
        WHERE take_profit_levels IS NOT NULL AND take_profit_levels != '[]'::jsonb
        UNION ALL
        -- Stop loss
        SELECT jsonb_build_object(
            'rule_type', 'stop_loss',
            'trigger_pct', -stop_loss * 100,
            'exit_pct', 100,
            'priority', 0,
            'enabled', true,
            'params', '{}'::JSONB
        )
        WHERE stop_loss IS NOT NULL
        UNION ALL
        -- Trailing stop (if enabled)
        SELECT jsonb_build_object(
            'rule_type', 'trailing_stop',
            'trigger_pct', -(trailing_stop->>'distance_percentage')::DECIMAL,
            'exit_pct', 100,
            'priority', 10,
            'enabled', COALESCE((trailing_stop->>'enabled')::BOOLEAN, false),
            'params', jsonb_build_object('activation_pct', (trailing_stop->>'activation_multiplier')::DECIMAL * 100)
        )
        WHERE trailing_stop IS NOT NULL AND (trailing_stop->>'enabled')::BOOLEAN = true
    ) subq
)
WHERE rules IS NULL OR rules = '[]'::jsonb;

-- Add status check constraint (only if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_exit_strategy_status'
    ) THEN
        ALTER TABLE exit_strategies
            ADD CONSTRAINT chk_exit_strategy_status
            CHECK (status IN ('draft', 'active', 'archived'));
    END IF;
END $$;

-- Partial unique index: only one active per name
CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_strategies_single_active
    ON exit_strategies(name) WHERE status = 'active';

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_exit_strategies_status ON exit_strategies(status);
CREATE INDEX IF NOT EXISTS idx_exit_strategies_name_status ON exit_strategies(name, status);
CREATE INDEX IF NOT EXISTS idx_exit_strategies_version ON exit_strategies(name, version);
