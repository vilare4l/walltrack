-- ============================================================================
-- Helper Functions (à exécuter AVANT les migrations)
-- ============================================================================

-- Create schema
CREATE SCHEMA IF NOT EXISTS walltrack;

-- Function: update_updated_at_column
CREATE OR REPLACE FUNCTION walltrack.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION walltrack.update_updated_at_column() IS
'Auto-update updated_at column on row modification. Used by all tables via trigger.';
